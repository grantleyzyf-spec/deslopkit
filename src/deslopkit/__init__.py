"""deslopkit —— 语域感知 + 保真护栏的中英双语文本去 AI 化工具包。

设计目标（相对现有同类开源项目的差异）：
1. **确定性**：核心规则引擎零 LLM 依赖，同一输入永远得到同一输出，可进 CI、可回归。
2. **保真护栏**：改写前后逐字校验数字、百分比、拉丁词、引号内术语、书名号、文号、标准号、
   引用标记与用户自定义保留词；任何一处丢失或新增即回滚该处改写。
3. **语域感知**：中文公文体（课题报告/公文）、中文学术体、中文网帖体、英文学术体、英文散文体
   使用不同的规则开关与阈值 —— 不用「活人感」规则去改坏公文。
4. **可复算**：句子长度 CV、段落长度 CV、短句占比、n-gram 重复率、标点指纹等指标前后对照，
   并与同语域人工样本参照带比较，而不是只给「效果截图」。
5. **诚实**：不承诺绕过任何第三方 AIGC 检测服务；不改变文本的生成来源；无基线不盲改。

Public API::

    from deslopkit import audit, rewrite, load_rules
    result = audit(text, register="zh-gov")
    fixed = rewrite(text, register="zh-gov")
    print(fixed.text, fixed.gate.passed)
"""

from .engine import AuditResult, RewriteResult, audit, rewrite
from .fidelity import FidelityReport, check_fidelity, protected_spans
from .metrics import TextMetrics, measure
from .register import REGISTERS, detect_register, get_register
from .rules import Rule, RuleHit, load_rules

__version__ = "0.1.0"
__all__ = [
    "__version__",
    "audit",
    "rewrite",
    "measure",
    "TextMetrics",
    "check_fidelity",
    "protected_spans",
    "FidelityReport",
    "load_rules",
    "Rule",
    "RuleHit",
    "REGISTERS",
    "get_register",
    "detect_register",
    "AuditResult",
    "RewriteResult",
]
