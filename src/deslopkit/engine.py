"""流水线：审计（只读）与改写（带闸门）。

`audit` 永不修改文本，只给证据；`rewrite` 默认一轮，逐轮重跑直到没有可自动改的命中，
每轮都做保真校验，最后过**交付闸门**（Gate）：闸门不过就不算完成，并在报告里写明哪一条没过。
"""

from __future__ import annotations

from dataclasses import dataclass, field
from typing import Dict, Iterable, List, Optional, Sequence

from .fidelity import FidelityReport, check_fidelity
from .metrics import TextMetrics, measure
from .register import RegisterProfile, band_check, detect_register, get_register
from .rewriters import AppliedEdit, RejectedEdit, rewrite_once
from .rules import RuleHit, category_counts, find_hits, load_rules


@dataclass
class AuditResult:
    text: str
    register: str
    metrics: TextMetrics
    hits: List[RuleHit] = field(default_factory=list)
    counts: Dict[str, int] = field(default_factory=dict)
    bands: Dict[str, Optional[bool]] = field(default_factory=dict)

    @property
    def high_severity(self) -> List[RuleHit]:
        return [h for h in self.hits if h.rule.severity == "high"]

    def summary(self) -> str:
        c = self.counts
        return (
            f"[{self.register}] 汉字 {self.metrics.han} ｜ 句长CV {self.metrics.sent_cv} ｜ "
            f"段长CV {self.metrics.para_cv} ｜ 短句占比 {self.metrics.short_sentence_ratio} ｜ "
            f"命中 {len(self.hits)} 处（{', '.join(f'{k}:{v}' for k, v in list(c.items())[:6]) or '无'}）"
        )


@dataclass
class GateCheck:
    name: str
    passed: bool
    detail: str = ""


@dataclass
class Gate:
    passed: bool = False
    checks: List[GateCheck] = field(default_factory=list)

    def failures(self) -> List[GateCheck]:
        return [c for c in self.checks if not c.passed]


@dataclass
class RewriteResult:
    original: str
    text: str
    register: str
    applied: List[AppliedEdit] = field(default_factory=list)
    rejected: List[RejectedEdit] = field(default_factory=list)
    skipped_review: int = 0
    passes_run: int = 0
    metrics_before: Optional[TextMetrics] = None
    metrics_after: Optional[TextMetrics] = None
    fidelity: Optional[FidelityReport] = None
    gate: Gate = field(default_factory=Gate)
    audit_after: Optional[AuditResult] = None

    @property
    def changed(self) -> bool:
        return self.text != self.original

    def summary(self) -> str:
        g = "过闸" if self.gate.passed else "未过闸"
        return (
            f"[{self.register}] {g} ｜ 应用 {len(self.applied)} 处 ｜ 因保真/安全回滚 {len(self.rejected)} 处 ｜ "
            f"仅提示 {self.skipped_review} 处 ｜ 汉字 {self.metrics_before.han}→{self.metrics_after.han}"
        )


def audit(
    text: str,
    register: str = "auto",
    keep: Iterable[str] = (),
    include_quoted: bool = False,
    rules: Optional[Sequence] = None,
) -> AuditResult:
    """只读审计：指标 + 命中清单 + 语域参照带比对。"""
    key = detect_register(text) if register in ("auto", "", None) else register
    profile = get_register(key)
    rules = rules or load_rules(lang=profile.lang)
    hits = find_hits(text, rules, register_key=key, include_quoted=include_quoted)
    m = measure(text)
    return AuditResult(
        text=text,
        register=key,
        metrics=m,
        hits=hits,
        counts=category_counts(hits),
        bands=band_check(profile, m),
    )


def _gate(
    profile: RegisterProfile,
    before: TextMetrics,
    after: TextMetrics,
    counts: Dict[str, int],
    fidelity: FidelityReport,
) -> Gate:
    checks: List[GateCheck] = []
    checks.append(GateCheck("保真护栏", fidelity.ok, fidelity.summary()))
    for cat in profile.gate:
        n = counts.get(cat, 0)
        checks.append(GateCheck(f"闸门类别 {cat} 清零", n == 0, f"剩余 {n} 处"))

    # CV 门禁：样本过小时统计量不稳定（少于 12 句或 6 段），列为不适用而不判失败；
    # 同时若处理后仍高于该语域参照带下限，允许小幅回落。
    small = before.sentences < 12 or before.paragraphs < 6
    if small:
        checks.append(
            GateCheck(
                "句长CV 不下降",
                True,
                f"样本过小（{before.sentences} 句 / {before.paragraphs} 段），CV 门禁不适用",
            )
        )
        checks.append(
            GateCheck(
                "段长CV 不下降",
                True,
                f"样本过小（{before.sentences} 句 / {before.paragraphs} 段），CV 门禁不适用",
            )
        )
    else:
        checks.append(
            GateCheck(
                "句长CV 不下降",
                after.sent_cv >= before.sent_cv - 0.02 or after.sent_cv >= profile.sent_cv_min,
                f"{before.sent_cv} → {after.sent_cv}（参照带下限 {profile.sent_cv_min}）",
            )
        )
        checks.append(
            GateCheck(
                "段长CV 不下降",
                after.para_cv >= before.para_cv - 0.02 or after.para_cv >= profile.para_cv_min,
                f"{before.para_cv} → {after.para_cv}（参照带下限 {profile.para_cv_min}）",
            )
        )
    delta = abs(after.han - before.han) / max(1, before.han)
    # 短文本（<200 汉字）用绝对字数判定：26 字里删掉「赋能」这种词就是 15%，按百分比判会误报。
    if before.han < 200:
        drift_ok = abs(after.han - before.han) <= 30
        drift_detail = f"{before.han} → {after.han}（短文本按绝对字数 ≤30 判定）"
    else:
        drift_ok = delta <= 0.10
        drift_detail = f"{before.han} → {after.han}（{delta:.1%}）"
    checks.append(GateCheck("字数变动在容许范围", drift_ok, drift_detail))
    checks.append(
        GateCheck(
            "无新增重复句",
            len(after.repeated_sentences) <= len(before.repeated_sentences),
            f"{len(before.repeated_sentences)} → {len(after.repeated_sentences)}",
        )
    )
    return Gate(passed=all(c.passed for c in checks), checks=checks)


def rewrite(
    text: str,
    register: str = "auto",
    keep: Iterable[str] = (),
    passes: int = 3,
    include_quoted: bool = False,
) -> RewriteResult:
    """改写：多轮直到收敛或无自动可改命中；每轮保真校验，最后过闸门。"""
    key = detect_register(text) if register in ("auto", "", None) else register
    profile = get_register(key)
    before = measure(text)
    applied: List[AppliedEdit] = []
    rejected: List[RejectedEdit] = []
    skipped = 0
    current = text
    runs = 0
    for _ in range(max(1, passes)):
        runs += 1
        res = rewrite_once(current, profile, keep)
        rejected.extend(res.rejected)
        skipped += res.skipped_review
        if not res.applied:
            break
        applied.extend(res.applied)
        current = res.text
    after = measure(current)
    fidelity = check_fidelity(text, current, keep)
    post = audit(current, register=key, keep=keep, include_quoted=include_quoted)
    # 闸门只看「可自动改写的残留」；review 类命中按设计需要人工判断，不计入闸门（但报告里单列）
    residual: Dict[str, int] = {}
    for h in post.hits:
        if h.rule.action == "rewrite":
            residual[h.rule.category] = residual.get(h.rule.category, 0) + 1
    gate = _gate(profile, before, after, residual, fidelity)
    return RewriteResult(
        original=text,
        text=current,
        register=key,
        applied=applied,
        rejected=rejected,
        skipped_review=skipped,
        passes_run=runs,
        metrics_before=before,
        metrics_after=after,
        fidelity=fidelity,
        gate=gate,
        audit_after=post,
    )
