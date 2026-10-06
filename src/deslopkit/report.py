"""报告渲染：Markdown（给人看）与 JSON（给 CI/流水线看）。

报告刻意包含「**使用边界**」一节：不承诺任何第三方检测器结果、不改变文本的生成来源、
无基线不盲改。同类项目普遍只展示“效果截图”，本项目把可验证性写进报告本身。
"""

from __future__ import annotations

import json
from dataclasses import asdict
from typing import Dict, List, Optional

from .engine import AuditResult, RewriteResult

BOUNDARY = [
    "本工具降低的是**可数的机器写作痕迹**（模板句、黑话、名词化、路标词、句段长度过于规整等），"
    "不改变文本的生成来源，也不承诺任何第三方 AIGC 检测服务的具体数值。",
    "任何检测器都是概率模型：换一段文本、换一个版本，结果可能不同。请以你所用平台的**实际检测报告**为准。",
    "正确用法是**先送检拿基线**（哪几处被判高），再用本工具定点处理，而不是全篇盲改。",
    "自动改写只覆盖有确定性模板的类别；结构性改写（翻案句重排）在报告里标为 `needs_review`，请人工复核后再定稿。",
    "学术与公文场景请遵守所在单位的 AI 使用规定；必要时如实说明工具使用情况。",
]


def _fmt(v) -> str:
    if isinstance(v, float):
        return f"{v:.3f}".rstrip("0").rstrip(".")
    return str(v)


def metrics_table(before, after) -> List[str]:
    rows = [
        ("汉字数", before.han, after.han),
        ("句数", before.sentences, after.sentences),
        ("平均句长", before.sent_mean, after.sent_mean),
        ("句长 CV", before.sent_cv, after.sent_cv),
        ("最短/最长句", f"{before.sent_min}/{before.sent_max}", f"{after.sent_min}/{after.sent_max}"),
        ("≤8 字短句", before.short_sentences, after.short_sentences),
        ("段落数", before.paragraphs, after.paragraphs),
        ("段长 CV", before.para_cv, after.para_cv),
        ("4-gram 重复率", before.ngram4_repeat, after.ngram4_repeat),
        ("长定语句（≥4 个“的”）", before.long_attributive, after.long_attributive),
        ("修辞破折号 ——", before.punctuation.get("dash_rhetoric", 0), after.punctuation.get("dash_rhetoric", 0)),
        ("连接号 —（国标本义，保留）", before.punctuation.get("dash_connector", 0), after.punctuation.get("dash_connector", 0)),
        ("中文冒号", before.punctuation.get("colon_zh", 0), after.punctuation.get("colon_zh", 0)),
        ("提示性冒号", before.punctuation.get("colon_prompt", 0), after.punctuation.get("colon_prompt", 0)),
    ]
    out = ["| 指标 | 处理前 | 处理后 |", "|---|---|---|"]
    for name, b, a in rows:
        out.append(f"| {name} | {_fmt(b)} | {_fmt(a)} |")
    return out


def audit_markdown(res: AuditResult, keep=()) -> str:
    L: List[str] = []
    L.append("# deslopkit 审计报告（只读）\n")
    L.append(f"- 语域：`{res.register}`" + (f" ｜ 自定义保留词 {len(tuple(keep))} 个" if keep else ""))
    L.append(f"- 汉字数：{res.metrics.han} ｜ 句长 CV：{res.metrics.sent_cv} ｜ 段长 CV：{res.metrics.para_cv}")
    L.append("")
    L.append("## 一、语域参照带比对\n")
    L.append("| 指标 | 实测 | 参照带下限 | 结论 |")
    L.append("|---|---|---|---|")
    m = res.metrics
    L.append(f"| 句长 CV | {m.sent_cv} | — | {'达标' if res.bands.get('sent_cv') else '偏低（句式偏模具化）'} |")
    L.append(f"| 段长 CV | {m.para_cv} | — | {'达标' if res.bands.get('para_cv') else '偏低（段落过于等长）'} |")
    L.append(
        f"| 短句占比 | {m.short_sentence_ratio} | — | "
        f"{'达标' if res.bands.get('short_sentence_ratio') else '偏低（缺少呼吸感）'} |"
    )
    L.append("")
    L.append("## 二、命中明细\n")
    if not res.hits:
        L.append("无命中。\n")
    else:
        by_cat: Dict[str, List] = {}
        for h in res.hits:
            by_cat.setdefault(h.rule.category, []).append(h)
        for cat, hits in sorted(by_cat.items(), key=lambda kv: -len(kv[1])):
            L.append(f"### {cat}（{len(hits)} 处）\n")
            L.append("| 行 | 严重度 | 处置 | 命中片段 | 说明 |")
            L.append("|---|---|---|---|---|")
            for h in hits[:40]:
                snippet = h.text.replace("|", "\\|")[:60]
                act = "自动改写" if (h.rule.action == "rewrite") else "人工判断"
                L.append(f"| {h.line} | {h.rule.severity} | {act} | `{snippet}` | {h.rule.message} |")
            if len(hits) > 40:
                L.append(f"| … | | | 其余 {len(hits) - 40} 处见 JSON | |")
            L.append("")
    L.append("## 三、4-gram 高频片段（前 10）\n")
    if res.metrics.ngram4_hot:
        L.append("| 片段 | 次数 |")
        L.append("|---|---|")
        for g, c in res.metrics.ngram4_hot[:10]:
            L.append(f"| `{g}` | {c} |")
    else:
        L.append("无重复片段。")
    L.append("")
    L.append("## 四、使用边界\n")
    for b in BOUNDARY:
        L.append(f"- {b}")
    L.append("")
    return "\n".join(L)


def rewrite_markdown(res: RewriteResult, keep=()) -> str:
    L: List[str] = []
    gate = "**通过**" if res.gate.passed else "**未通过**"
    L.append("# deslopkit 改写报告\n")
    L.append(f"- 语域：`{res.register}` ｜ 轮次：{res.passes_run} ｜ 交付闸门：{gate}")
    L.append(f"- {res.summary()}")
    L.append("")
    L.append("## 一、指标对照\n")
    if res.metrics_before and res.metrics_after:
        L.extend(metrics_table(res.metrics_before, res.metrics_after))
    L.append("")
    L.append("## 二、闸门检查\n")
    L.append("| 检查项 | 结果 | 明细 |")
    L.append("|---|---|---|")
    for c in res.gate.checks:
        L.append(f"| {c.name} | {'✅ 通过' if c.passed else '❌ 未通过'} | {c.detail} |")
    L.append("")
    L.append("## 三、已应用改写\n")
    if not res.applied:
        L.append("无（没有可确定性改写的命中）。\n")
    else:
        L.append("| 行 | 规则 | 类别 | 改写前 | 改写后 | 需人工复核 |")
        L.append("|---|---|---|---|---|---|")
        for e in res.applied[:80]:
            b = e.before.replace("|", "\\|")[:60]
            a = e.after.replace("|", "\\|")[:60]
            L.append(f"| {e.line} | {e.rule_id} | {e.category} | `{b}` | `{a}` | {'是' if e.needs_review else '否'} |")
        if len(res.applied) > 80:
            L.append(f"| … | | | 其余 {len(res.applied) - 80} 处见 JSON | | |")
    L.append("")
    if res.rejected:
        L.append("## 四、被回滚的改写（保真或安全校验未通过）\n")
        L.append("| 规则 | 类别 | 原片段 | 拟改为 | 回滚原因 |")
        L.append("|---|---|---|---|---|")
        for r in res.rejected[:40]:
            b = r.before.replace("|", "\\|")[:50]
            a = r.after.replace("|", "\\|")[:50]
            L.append(f"| {r.rule_id} | {r.category} | `{b}` | `{a}` | {r.reason} |")
        L.append("")
    L.append("## 五、保真校验\n")
    if res.fidelity:
        L.append(f"- {res.fidelity.summary()}")
        if res.fidelity.missing:
            L.append(f"- 丢失片段（示例）：{', '.join(f'{s.kind}:{s.value}' for s in res.fidelity.missing[:10])}")
        if res.fidelity.added:
            L.append(f"- 新增片段（示例）：{', '.join(f'{s.kind}:{s.value}' for s in res.fidelity.added[:10])}")
    L.append("")
    if res.skipped_review:
        L.append(f"## 六、仅提示未自动改写：{res.skipped_review} 处\n")
        L.append("这些命中在报告正文里逐条列出，需要人工判断（语域策略为 review）。\n")
    L.append("## 七、使用边界\n")
    for b in BOUNDARY:
        L.append(f"- {b}")
    L.append("")
    return "\n".join(L)


def audit_json(res: AuditResult, keep=()) -> str:
    return json.dumps(
        {
            "kind": "audit",
            "register": res.register,
            "metrics": res.metrics.as_dict(),
            "counts": res.counts,
            "bands": res.bands,
            "hits": [h.to_dict() for h in res.hits],
            "keep": list(keep),
        },
        ensure_ascii=False,
        indent=2,
    )


def rewrite_json(res: RewriteResult, keep=()) -> str:
    return json.dumps(
        {
            "kind": "rewrite",
            "register": res.register,
            "passes_run": res.passes_run,
            "gate": {
                "passed": res.gate.passed,
                "checks": [asdict(c) for c in res.gate.checks],
            },
            "fidelity": res.fidelity.to_dict() if res.fidelity else None,
            "metrics_before": res.metrics_before.as_dict() if res.metrics_before else None,
            "metrics_after": res.metrics_after.as_dict() if res.metrics_after else None,
            "applied": [e.to_dict() for e in res.applied],
            "rejected": [e.to_dict() for e in res.rejected],
            "skipped_review": res.skipped_review,
            "kept_review_hits": [h.to_dict() for h in (res.audit_after.hits if res.audit_after else [])],
            "text": res.text,
            "keep": list(keep),
            "boundary": BOUNDARY,
        },
        ensure_ascii=False,
        indent=2,
    )


def write(path: Optional[str], content: str) -> None:
    if not path:
        return
    with open(path, "w", encoding="utf-8") as fh:
        fh.write(content)
