"""规则加载与匹配。

规则以 JSON 存放（`deslopkit/rules/*.json`），零第三方依赖即可解析，便于社区贡献；
每条规则是「定位 + 处置建议 + 可选确定性改写模板」，**匹配永远可复现**。

一条规则的字段
--------------
``id``          唯一标识，形如 ``zh.neg.001``
``lang``        ``zh`` / ``en``
``registers``   适用语域列表，或 ``["all"]``
``category``    见 ``register.py`` 的类别常量
``pattern``     Python 正则
``flags``       可选，``"i"``/``"m"``
``severity``    ``high`` / ``medium`` / ``low``
``action``      ``rewrite``（有确定性改写模板）或 ``review``（只提示）
``strategy``    改写策略名，由 ``rewriters.py`` 实现
``replacement`` 可选替换模板（支持 ``\\1`` 反向引用），空串表示删除
``skip_quoted`` 命中落在引号/书名号内时跳过（默认 ``true``，保护引文）
``message``     人话说明
``fix_hint``    修改提示
"""

from __future__ import annotations

import json
import re
from dataclasses import dataclass
from functools import cache
from pathlib import Path
from typing import Dict, Iterable, List, Optional, Sequence, Tuple

RULES_DIR = Path(__file__).resolve().parent

QUOTE_SPANS = re.compile(r"“[^”]{1,200}”|《[^》]{1,200}》|\"[^\"]{1,200}\"")


@dataclass(frozen=True)
class Rule:
    id: str
    lang: str
    registers: Tuple[str, ...]
    category: str
    pattern: str
    severity: str = "medium"
    action: str = "review"
    strategy: str = ""
    replacement: Optional[str] = None
    flags: str = ""
    skip_quoted: bool = True
    message: str = ""
    fix_hint: str = ""

    def applies_to(self, register_key: str) -> bool:
        return "all" in self.registers or register_key in self.registers


@dataclass
class RuleHit:
    rule: Rule
    text: str
    start: int
    end: int
    line: int = 1
    groups: Tuple[str, ...] = ()

    def to_dict(self) -> Dict[str, object]:
        return {
            "id": self.rule.id,
            "category": self.rule.category,
            "severity": self.rule.severity,
            "action": self.rule.action,
            "strategy": self.rule.strategy,
            "match": self.text,
            "line": self.line,
            "message": self.rule.message,
            "fix_hint": self.rule.fix_hint,
        }


def _load_file(path: Path) -> List[Rule]:
    data = json.loads(path.read_text(encoding="utf-8"))
    out: List[Rule] = []
    for raw in data.get("rules", []):
        out.append(
            Rule(
                id=raw["id"],
                lang=raw.get("lang", "zh"),
                registers=tuple(raw.get("registers", ["all"])),
                category=raw["category"],
                pattern=raw["pattern"],
                severity=raw.get("severity", "medium"),
                action=raw.get("action", "review"),
                strategy=raw.get("strategy", ""),
                replacement=raw.get("replacement"),
                flags=raw.get("flags", ""),
                skip_quoted=raw.get("skip_quoted", True),
                message=raw.get("message", ""),
                fix_hint=raw.get("fix_hint", ""),
            )
        )
    return out


@cache
def load_rules(lang: Optional[str] = None, path: Optional[str] = None) -> Tuple[Rule, ...]:
    """加载规则库。`lang` 为 ``zh``/``en``/``None``（全部）。"""
    files: Iterable[Path]
    if path:
        files = [Path(path)]
    elif lang:
        files = [RULES_DIR / f"{lang}.json"]
    else:
        files = sorted(RULES_DIR.glob("*.json"))
    rules: List[Rule] = []
    for f in files:
        if f.exists():
            rules.extend(_load_file(f))
    seen = set()
    uniq: List[Rule] = []
    for r in rules:
        if r.id in seen:
            continue
        seen.add(r.id)
        uniq.append(r)
    return tuple(uniq)


def _line_of(text: str, pos: int) -> int:
    return text.count("\n", 0, pos) + 1


def _inside_quotes(text: str, start: int, end: int) -> bool:
    for m in QUOTE_SPANS.finditer(text):
        if m.start() <= start and end <= m.end():
            return True
    return False


def find_hits(
    text: str,
    rules: Sequence[Rule],
    register_key: str = "all",
    include_quoted: bool = False,
) -> List[RuleHit]:
    """在文本里定位所有命中，按位置排序返回。确定性、无副作用。"""
    hits: List[RuleHit] = []
    for rule in rules:
        if register_key != "all" and not rule.applies_to(register_key):
            continue
        flags = re.UNICODE
        if "i" in rule.flags:
            flags |= re.IGNORECASE
        if "m" in rule.flags:
            flags |= re.MULTILINE
        try:
            rx = re.compile(rule.pattern, flags)
        except re.error:
            continue
        for m in rx.finditer(text):
            if rule.skip_quoted and not include_quoted and _inside_quotes(text, m.start(), m.end()):
                continue
            hits.append(
                RuleHit(
                    rule=rule,
                    text=m.group(0),
                    start=m.start(),
                    end=m.end(),
                    line=_line_of(text, m.start()),
                    groups=tuple(g or "" for g in m.groups()),
                )
            )
    hits.sort(key=lambda h: (h.start, h.rule.id))
    return hits


def category_counts(hits: Sequence[RuleHit]) -> Dict[str, int]:
    counts: Dict[str, int] = {}
    for h in hits:
        counts[h.rule.category] = counts.get(h.rule.category, 0) + 1
    return dict(sorted(counts.items(), key=lambda kv: (-kv[1], kv[0])))
