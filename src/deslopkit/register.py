"""语域画像（register profiles）。

**为什么需要语域**：现有同类项目基本只有一套规则，于是把「活人感散文」规则套到公文/学术文本上，
把合规的机构腔、连接号、分点陈述一并改坏。deslopkit 的做法是：同一套规则库，按语域决定
「自动改写 / 仅供参考 / 完全关闭」，并给出该语域的指标参照带。

参照带来自同语域人工撰写样本的实测口径（见 `docs/metrics.md`），不是拍脑袋的阈值。
"""

from __future__ import annotations

import re
from dataclasses import dataclass
from typing import Dict, Optional, Tuple

HAN = re.compile(r"[\u4e00-\u9fff]")

CORE = "negation_pivot"          # 翻案腔：最典型的机器痕迹，任何语域都要求清零
JARGON = "jargon"                # 黑话（赋能/抓手/闭环/深度融合…）
NOMINAL = "nominalization"       # 名词化
SIGNPOST = "signposting"         # 路标词（其一是/首先其次/综上所述/由此可见）
PARALLEL = "parallelism"         # 同构排比
LYRIC = "abstract_lyric"         # 抽象抒情/升华
PUNCT = "punctuation"            # 标点用法（修辞破折号、提示性冒号）
FILLER = "filler"                # 空泛填充词
EN_CLICHE = "english_cliche"     # 英文陈词滥调


@dataclass(frozen=True)
class RegisterProfile:
    key: str
    label: str
    lang: str
    family: str
    sent_cv_min: float
    para_cv_min: float
    short_sent_ratio_min: float
    auto_fix: Tuple[str, ...] = ()
    review_only: Tuple[str, ...] = ()
    disabled: Tuple[str, ...] = ()
    gate: Tuple[str, ...] = (CORE,)
    notes: str = ""

    def policy(self, category: str) -> str:
        """返回某类别在本语域下的处理策略：fix / review / off。"""
        if category in self.disabled:
            return "off"
        if category in self.auto_fix:
            return "fix"
        if category in self.review_only:
            return "review"
        return "review"


def _p(**kw) -> RegisterProfile:
    return RegisterProfile(**kw)


REGISTERS: Dict[str, RegisterProfile] = {
    "zh-gov": _p(
        key="zh-gov",
        label="中文公文体（课题报告 / 公文 / 方案 / 公示）",
        lang="zh",
        family="gov",
        sent_cv_min=0.45,
        para_cv_min=0.35,
        short_sent_ratio_min=0.015,
        auto_fix=(CORE, JARGON, NOMINAL, FILLER),
        review_only=(SIGNPOST, PARALLEL, LYRIC, PUNCT),
        disabled=(),
        gate=(CORE,),
        notes="保留机构腔与国标本义连接号；分点陈述、提示性冒号属合规文体，仅提示不自动改。",
    ),
    "zh-academic": _p(
        key="zh-academic",
        label="中文学术体（论文 / 研究报告 / 学位论文）",
        lang="zh",
        family="academic",
        sent_cv_min=0.45,
        para_cv_min=0.35,
        short_sent_ratio_min=0.015,
        auto_fix=(CORE, JARGON, NOMINAL, SIGNPOST, FILLER),
        review_only=(PARALLEL, LYRIC, PUNCT),
        gate=(CORE, JARGON),
        notes="术语与统计表述优先保真；结果段不宜口语化，只清模板痕迹。",
    ),
    "zh-forum": _p(
        key="zh-forum",
        label="中文网帖体（知乎 / 论坛 / 公众号 / 博客）",
        lang="zh",
        family="forum",
        sent_cv_min=0.50,
        para_cv_min=0.40,
        short_sent_ratio_min=0.05,
        auto_fix=(CORE, JARGON, NOMINAL, SIGNPOST, FILLER, LYRIC, PUNCT),
        review_only=(PARALLEL,),
        gate=(CORE, JARGON, SIGNPOST),
        notes="要求最强：翻案句、路标词、修辞破折号与提示性冒号都要清。",
    ),
    "en-academic": _p(
        key="en-academic",
        label="English academic（英文学术体：论文 / 报告 / 学位论文）",
        lang="en",
        family="academic",
        sent_cv_min=0.45,
        para_cv_min=0.35,
        short_sent_ratio_min=0.03,
        auto_fix=(EN_CLICHE, CORE, JARGON, FILLER),
        review_only=(SIGNPOST, PARALLEL, LYRIC, PUNCT),
        gate=(EN_CLICHE, CORE),
        notes="Keeps hedging and citations intact; only removes template clichés.",
    ),
    "en-essay": _p(
        key="en-essay",
        label="English prose / blog / forum（英文散文与网帖）",
        lang="en",
        family="forum",
        sent_cv_min=0.55,
        para_cv_min=0.45,
        short_sent_ratio_min=0.06,
        auto_fix=(EN_CLICHE, CORE, JARGON, FILLER, SIGNPOST, LYRIC, PUNCT),
        review_only=(PARALLEL,),
        gate=(EN_CLICHE, CORE, SIGNPOST),
        notes="Strongest policy, mirroring prose-humanising rule sets.",
    ),
}

GOV_HINTS = ("课题", "公示", "通知", "办法", "方案", "规划", "工作报告", "请示", "批复", "纪要", "公文")
ACADEMIC_HINTS = ("摘要", "关键词", "参考文献", "文献综述", "研究方法", "假设", "显著性", "Abstract", "References")


def get_register(key: str) -> RegisterProfile:
    """按 key 取语域画像；`auto` 走自动判定。"""
    if key in REGISTERS:
        return REGISTERS[key]
    raise KeyError(f"未知语域 {key!r}；可选：{', '.join(REGISTERS)}, auto")


def detect_register(text: str) -> str:
    """粗粒度语域判定：CJK 占比决定语种，关键词决定 family。"""
    han = len(HAN.findall(text))
    total = max(1, len(re.sub(r"\s", "", text)))
    zh = han / total > 0.25
    academic = any(h in text for h in ACADEMIC_HINTS)
    gov = any(h in text for h in GOV_HINTS)
    if zh:
        if gov:
            return "zh-gov"
        return "zh-academic" if academic else "zh-forum"
    return "en-academic" if academic else "en-essay"


def band_check(profile: RegisterProfile, metrics) -> Dict[str, Optional[bool]]:
    """把指标与语域参照带比对，返回 {指标名: 是否达标}（None 表示该语域不判）。"""
    return {
        "sent_cv": metrics.sent_cv >= profile.sent_cv_min,
        "para_cv": metrics.para_cv >= profile.para_cv_min,
        "short_sentence_ratio": metrics.short_sentence_ratio >= profile.short_sent_ratio_min,
    }
