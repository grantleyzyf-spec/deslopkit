"""保真护栏（Fidelity Guard）—— 本项目的核心差异点。

现有同类项目（含 humanizer/humanizer-zh-academic/DeSlop 等）几乎都只做「改写」，
不做「改写有没有偷偷改掉事实」的自动核对。学术与公文场景里，数字、文号、书名、引号内术语
被改掉是不可接受的，因此 deslopkit 把保真校验做成流水线的一道**强制闸门**：

* 改写前抽取受保护片段（protected spans）：数字/百分比、拉丁词与缩写、中文引号内术语、
  书名号、文号与标准号、引用标记、URL、邮箱、以及用户自定义的保留词表；
* 改写后按 `(kind, value)` 多重集逐项比对：**丢失即为违规，新增同样为违规**（防模型编数）；
* 任一违规 ⇒ 该处改写被回滚，并在报告里列为 `rejected`，附原因。
"""

from __future__ import annotations

import re
from collections import Counter
from dataclasses import dataclass, field
from typing import Dict, Iterable, List, Tuple

# (kind, regex) —— 顺序即优先级；同一片段只归属第一个命中的 kind
PATTERNS: Tuple[Tuple[str, str], ...] = (
    ("url", r"https?://[^\s，。；）)】」]+"),
    ("email", r"[A-Za-z0-9._%+\-]+@[A-Za-z0-9.\-]+\.[A-Za-z]{2,}"),
    ("doc_no", r"[\u4e00-\u9fff]{2,8}〔\d{4}〕\d{1,4}\s?号"),
    ("std_no", r"[A-Z]{1,3}\s?\d{3,5}(?:\.\d+)?[—\-]\d{4}"),
    ("book_title", r"《[^》]{1,60}》"),
    ("zh_quote", r"“[^”]{1,60}”"),
    ("citation", r"\[\s?\d{1,3}(?:\s?[-,，]\s?\d{1,3})*\s?\]"),
    ("percent", r"\d+(?:\.\d+)?\s?%"),
    ("number", r"\d+(?:[.,，]\d+)*"),
)
# 术语型拉丁串（AI / GenAI / C-STEAM / 5E / AI+ / SSCI …）用「token + 谓词」判定，
# 而不是写死正则：普通英文单词（teachers / Technology）不保护，否则英文文本任何改写
# 都会被误判为保真失败（实测回滚 5/5）。
TERM_TOKEN = re.compile(r"[A-Za-z0-9][A-Za-z0-9+#.\-]*")


def is_latin_term(tok: str) -> bool:
    if not any(c.isalpha() for c in tok):
        return False
    if any(c in tok for c in "+#"):
        return True
    if any(ch.isdigit() for ch in tok):
        return True
    if len(tok) >= 2 and tok.isupper():
        return True
    return any(ch.isupper() for ch in tok[1:])

# 说明：机构名不做自动抽取 —— 「…小学」「…大学」这类后缀会把前文任意汉字吞进匹配，
# 造成保真误报（实测「人工智能赋能中小学」被当成机构名，导致 赋能→助力 被误回滚）。
# 机构名、专有名词请用 `--keep` / `--keep-from 原稿.txt` 显式传入，见 docs/rules.md。


@dataclass(frozen=True)
class Span:
    kind: str
    value: str
    start: int
    end: int


@dataclass
class FidelityReport:
    """保真校验结果。`ok=False` 表示有受保护片段被改写动过。"""

    ok: bool = True
    missing: List[Span] = field(default_factory=list)
    added: List[Span] = field(default_factory=list)
    kept: int = 0
    detail: str = ""

    def to_dict(self) -> Dict[str, object]:
        return {
            "ok": self.ok,
            "kept": self.kept,
            "missing": [f"{s.kind}:{s.value}" for s in self.missing],
            "added": [f"{s.kind}:{s.value}" for s in self.added],
            "detail": self.detail,
        }

    def summary(self) -> str:
        if self.ok:
            return f"保真通过：{self.kept} 个受保护片段逐字保留"
        return (
            f"保真失败：丢失 {len(self.missing)} 项"
            + (f"（示例 {self.missing[0].kind}:{self.missing[0].value}）" if self.missing else "")
            + (f"、新增 {len(self.added)} 项" if self.added else "")
        )


def protected_spans(text: str, extra_keep: Iterable[str] = ()) -> List[Span]:
    """抽取受保护片段。`extra_keep` 是用户自定义保留词（整词匹配）。"""
    spans: List[Span] = []
    taken: List[Tuple[int, int]] = []
    for kind, pat in PATTERNS:
        for m in re.finditer(pat, text):
            if any(m.start() < e and s < m.end() for s, e in taken):
                continue
            spans.append(Span(kind, m.group(0), m.start(), m.end()))
            taken.append((m.start(), m.end()))
    for word in extra_keep:
        if not word:
            continue
        for m in re.finditer(re.escape(word), text):
            if any(m.start() < e and s < m.end() for s, e in taken):
                continue
            spans.append(Span("keep", m.group(0), m.start(), m.end()))
            taken.append((m.start(), m.end()))
    for m in TERM_TOKEN.finditer(text):
        tok = m.group(0)
        if not is_latin_term(tok):
            continue
        if any(m.start() < e and s < m.end() for s, e in taken):
            continue
        spans.append(Span("latin_term", tok, m.start(), m.end()))
        taken.append((m.start(), m.end()))
    spans.sort(key=lambda s: s.start)
    return spans


def check_fidelity(before: str, after: str, extra_keep: Iterable[str] = ()) -> FidelityReport:
    """逐项比对受保护片段：丢失或新增都算违规。"""
    b = protected_spans(before, extra_keep)
    a = protected_spans(after, extra_keep)
    cb = Counter((s.kind, s.value) for s in b)
    ca = Counter((s.kind, s.value) for s in a)
    missing_keys = cb - ca
    added_keys = ca - cb
    missing: List[Span] = []
    for (kind, value), cnt in missing_keys.items():
        picked = [s for s in b if s.kind == kind and s.value == value][:cnt]
        missing.extend(picked)
    added: List[Span] = []
    for (kind, value), cnt in added_keys.items():
        picked = [s for s in a if s.kind == kind and s.value == value][:cnt]
        added.extend(picked)
    kept = sum(min(cb[k], ca[k]) for k in cb.keys() | ca.keys())
    ok = not missing and not added
    detail = "" if ok else f"缺失 {len(missing)} / 新增 {len(added)}"
    return FidelityReport(ok=ok, missing=missing, added=added, kept=kept, detail=detail)


def keep_terms_from(text: str, extra_keep: Iterable[str] = ()) -> List[str]:
    """把一份文本里的保留词提出来，供 `--keep-from` 复用（如从原始素材文件）。"""
    seen: Dict[str, int] = {}
    for s in protected_spans(text, extra_keep):
        if len(s.value) >= 2:
            seen[s.value] = seen.get(s.value, 0) + 1
    return sorted(seen, key=lambda w: (-seen[w], w))
