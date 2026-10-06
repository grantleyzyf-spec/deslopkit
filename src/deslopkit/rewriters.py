"""确定性改写器。

设计原则（这是与「纯 LLM 改写」类项目的根本区别）：

* **每个改写都是模板展开**，同一输入永远得到同一输出，可写单元测试、可进 CI；
* **只改策略允许的类别**：`register.policy(category) == "fix"` 且 `rule.action == "rewrite"` 才动手，
  其余一律只提示（公文语域下分点陈述、连接号、机构腔都因此被保护）；
* **每处改写都要过保真护栏**：改写前片段与改写后片段逐个受保护片段比对，丢失/新增即回滚；
* **结构性改写标记 `needs_review`**：翻案句重排改变了语序，报告里明确列出，人复核一遍再定稿。
"""

from __future__ import annotations

import re
from dataclasses import dataclass, field
from typing import Iterable, List, Sequence, Tuple

from .fidelity import check_fidelity
from .register import RegisterProfile
from .rules import RuleHit, load_rules

# 改写后如果否定分句失去动词，需要补一个系动词；这些开头视为「已有谓语」
COPULA_OK = (
    "是", "为", "在于", "属于", "以", "通过", "由", "存在", "需要", "重在", "取决于",
    "包括", "体现", "指向", "构成", "来自", "源于", "应当", "应", "须", "应把", "要",
)
# 紧邻匹配前若已是系动词，则不再补
PREV_COPULA = ("是", "为", "在于", "属于", "成了", "成为", "作为")

TIDY = (
    ("，，", "，"), ("，。", "。"), ("。，", "。"), ("；，", "；"), ("，；", "；"),
    ("。。", "。"), ("，、", "、"), ("、，", "，"), ("：，", "："),
)


def _flags(rule_flags: str) -> int:
    f = re.UNICODE
    if "i" in rule_flags:
        f |= re.IGNORECASE
    if "m" in rule_flags:
        f |= re.MULTILINE
    return f


def tidy(text: str) -> str:
    """规范化标点与行内空白。⚠️ 只压缩空格/制表符，**不动换行** ——
    早期版本用 `\\s{2,}` 会把段落之间的空行一起吃掉，整篇被并成一段（已加回归测试）。"""
    prev = None
    while prev != text:
        prev = text
        for a, b in TIDY:
            text = text.replace(a, b)
    text = re.sub(r"^[，、；：]+", "", text)
    text = re.sub(r"[ \t]{2,}", " ", text)
    return text.strip() if not text.endswith("\n") else text.strip("\n")


@dataclass
class AppliedEdit:
    rule_id: str
    category: str
    strategy: str
    before: str
    after: str
    line: int = 1
    needs_review: bool = False
    note: str = ""

    def to_dict(self):
        return self.__dict__.copy()


@dataclass
class RejectedEdit:
    rule_id: str
    category: str
    before: str
    after: str
    reason: str
    line: int = 1

    def to_dict(self):
        return self.__dict__.copy()


@dataclass
class EditResult:
    text: str
    applied: List[AppliedEdit] = field(default_factory=list)
    rejected: List[RejectedEdit] = field(default_factory=list)
    skipped_review: int = 0


def expand_replacement(hit: RuleHit, prev_context: str) -> str:
    """按规则模板展开替换文本；结构性改写补系动词并整理标点。"""
    rule = hit.rule
    rx = re.compile(rule.pattern, _flags(rule.flags))
    m = rx.fullmatch(hit.text)
    if m is None:
        m = rx.match(hit.text)
    template = rule.replacement or ""
    if m is not None:
        try:
            out = m.expand(template)
        except re.error:
            out = template
    else:
        out = template
        for i, g in enumerate(hit.groups, start=1):
            out = out.replace(f"\\{i}", g)
    out = tidy(out)
    if rule.strategy == "neg_pivot" and out and rule.lang == "zh":
        first = out[:2]
        prev_tail = prev_context.strip()[-3:]
        needs_copula = (
            not first.startswith(COPULA_OK)
            and not any(prev_tail.endswith(c) for c in PREV_COPULA)
            and bool(prev_context.strip())
            and not prev_context.strip().endswith(("，", "。", "；", "：", "、", "）", ")", "”", "》"))
        )
        if needs_copula:
            out = "是" + out
        # 若否定分句被降为句末补充，去掉可能重复的“而不是”叠字
        out = out.replace("而不是而不是", "而不是").replace("而不在于而不在于", "而不在于")
    return tidy(out)


def _overlaps(start: int, end: int, used: Sequence[Tuple[int, int]]) -> bool:
    return any(start < e and s < end for s, e in used)


def apply_edits(
    text: str,
    hits: Sequence[RuleHit],
    profile: RegisterProfile,
    extra_keep: Iterable[str] = (),
) -> EditResult:
    """应用可自动改写的命中；返回新文本、已应用与被拒清单。确定性执行。"""
    result = EditResult(text=text)
    used: List[Tuple[int, int]] = []
    # 从后往前改，保证偏移量不失效
    for hit in sorted(hits, key=lambda h: h.start, reverse=True):
        category = hit.rule.category
        if profile.policy(category) != "fix" or hit.rule.action != "rewrite":
            result.skipped_review += 1
            continue
        if _overlaps(hit.start, hit.end, used):
            continue
        prev_context = text[max(0, hit.start - 30) : hit.start]
        new_segment = expand_replacement(hit, prev_context)
        end = hit.end
        # 删除型改写：删除后若前后都没有标点，补一个逗号，避免出现「上述问题四个维度…」这种病句
        if hit.rule.strategy == "delete":
            new_segment = ""
            # 吞掉紧随其后的中英标点与空格，避免删除后留下「，teachers must…」这类残句
            while end < len(text) and text[end] in "，,、：:；;":
                end += 1
            while end < len(text) and text[end] in " \t":
                end += 1
            prev_char = text[hit.start - 1] if hit.start > 0 else ""
            nxt = text[end] if end < len(text) else ""
            if (hit.rule.replacement or "") != "":
                pass
            elif hit.rule.lang == "en":
                # 英文：删除句首成分后首字母要大写（In today's … , teachers → Teachers）
                at_start = hit.start == 0 or text[hit.start - 1] in "\n"
                if at_start and end < len(text) and text[end].islower():
                    new_segment = text[end].upper()
                    end += 1
            else:
                # 中文：两侧都是实字时补一个逗号，否则会出现「上述问题四个维度…」
                banned = "，。；：、！？\n"
                if prev_char and nxt and prev_char not in banned and nxt not in banned:
                    new_segment = "，"
        if not new_segment and hit.rule.strategy not in ("delete", "punct"):
            result.rejected.append(
                RejectedEdit(hit.rule.id, category, hit.text, new_segment, "模板展开为空，安全起见不改", hit.line)
            )
            continue
        if new_segment == hit.text:
            continue
        if len(new_segment) > len(hit.text) * 3 + 40:
            result.rejected.append(
                RejectedEdit(hit.rule.id, category, hit.text, new_segment, "替换文本异常膨胀，安全起见不改", hit.line)
            )
            continue
        # 局部保真校验：这两段之间不允许任何受保护片段丢失或新增
        keep = tuple(extra_keep)
        local_ctx_before = text[max(0, hit.start - 12) : end]
        local_ctx_after = text[max(0, hit.start - 12) : hit.start] + new_segment
        rep = check_fidelity(local_ctx_before, local_ctx_after, keep)
        if not rep.ok:
            result.rejected.append(
                RejectedEdit(hit.rule.id, category, hit.text, new_segment, f"保真校验失败（{rep.detail}）", hit.line)
            )
            continue
        text = text[: hit.start] + new_segment + text[end :]
        used.append((hit.start, end))
        result.applied.append(
            AppliedEdit(
                rule_id=hit.rule.id,
                category=category,
                strategy=hit.rule.strategy,
                before=hit.text,
                after=new_segment,
                line=hit.line,
                needs_review=hit.rule.strategy == "neg_pivot",
                note=hit.rule.fix_hint,
            )
        )
    result.text = tidy(text)
    return result


def rewrite_once(text: str, profile: RegisterProfile, extra_keep: Iterable[str] = ()) -> EditResult:
    """跑一轮：加载规则 → 定位 → 应用（含保真回滚）。"""
    rules = load_rules(lang=profile.lang)
    from .rules import find_hits

    hits = find_hits(text, rules, register_key=profile.key)
    return apply_edits(text, hits, profile, extra_keep)
