"""可复算文本指标：句长/段长分布、短句占比、n-gram 重复、标点指纹、长定语句。

所有指标都是纯函数、零依赖、可复现；报告里给出的每个数字都能被第三方用同样代码重算。
"""

from __future__ import annotations

import math
import re
from dataclasses import dataclass, field
from typing import Dict, List, Sequence, Tuple

HAN = re.compile(r"[\u4e00-\u9fff]")
CJK_ANY = re.compile(r"[\u3000-\u303f\u4e00-\u9fff\uff00-\uffef]")
LATIN_WORD = re.compile(r"[A-Za-z][A-Za-z'\-]*")
SENT_END_ZH = "。！？!?"
SENT_END_ALL = "。！？!?…"
RHETORIC_DASH = "——"
CONNECTOR_DASH = "—"


def han_count(text: str) -> int:
    """汉字数（只数 CJK 统一表意文字，不含标点/数字/空格）。"""
    return len(HAN.findall(text))


def char_count(text: str) -> int:
    """含标点字符数（去掉空白）。"""
    return len(re.sub(r"\s", "", text))


def split_paragraphs(text: str) -> List[str]:
    """段落切分：以空行分块；无空行时以非空行分块（兼容 docx 抽文本）。"""
    blocks = [b.strip() for b in re.split(r"\n\s*\n", text) if b.strip()]
    if len(blocks) > 1:
        return blocks
    return [line.strip() for line in text.splitlines() if line.strip()]


def split_sentences(text: str, min_han: int = 1) -> List[str]:
    """句子切分：中文句末标点为主，兼容英文句末标点后的空白。"""
    parts: List[str] = []
    buf = []
    for ch in text:
        buf.append(ch)
        if ch in SENT_END_ZH or ch == "…":
            parts.append("".join(buf))
            buf = []
    if buf:
        parts.append("".join(buf))
    out = []
    for p in parts:
        p = p.strip()
        if not p:
            continue
        # 句内换行视作句界
        for sub in [s.strip() for s in p.split("\n") if s.strip()]:
            if han_count(sub) >= min_han or LATIN_WORD.search(sub):
                out.append(sub)
    return out


def _mean(xs: Sequence[float]) -> float:
    return sum(xs) / len(xs) if xs else 0.0


def _std(xs: Sequence[float]) -> float:
    if len(xs) < 2:
        return 0.0
    m = _mean(xs)
    return math.sqrt(sum((x - m) ** 2 for x in xs) / (len(xs) - 1))


def _cv(xs: Sequence[float]) -> float:
    m = _mean(xs)
    return (_std(xs) / m) if m else 0.0


def _median(xs: Sequence[float]) -> float:
    if not xs:
        return 0.0
    s = sorted(xs)
    n = len(s)
    return s[n // 2] if n % 2 else (s[n // 2 - 1] + s[n // 2]) / 2


def ngram_repeat(text: str, n: int = 4, top: int = 10) -> Tuple[float, List[Tuple[str, int]]]:
    """n-gram 重复率 = 1 - 唯一 n-gram / 总 n-gram；并返回高频 n-gram。"""
    chars = [c for c in re.sub(r"\s+", "", text)]
    grams = ["".join(chars[i : i + n]) for i in range(len(chars) - n + 1)]
    if not grams:
        return 0.0, []
    counts: Dict[str, int] = {}
    for g in grams:
        counts[g] = counts.get(g, 0) + 1
    rate = 1.0 - len(counts) / len(grams)
    hot = sorted(((g, c) for g, c in counts.items() if c >= 2), key=lambda kv: (-kv[1], kv[0]))[:top]
    return rate, hot


def repeated_sentences(text: str, min_han: int = 8) -> List[Tuple[str, int]]:
    counts: Dict[str, int] = {}
    for s in split_sentences(text):
        if han_count(s) >= min_han:
            counts[s] = counts.get(s, 0) + 1
    return sorted(((s, c) for s, c in counts.items() if c >= 2), key=lambda kv: -kv[1])


def punctuation_fingerprint(text: str) -> Dict[str, int]:
    """标点指纹。连接号与修辞破折号分开统计，避免把国标本义的连接号误判为 AI 痕迹。"""
    fp = {
        "dash_rhetoric": 0,      # —— 独立使用的破折号
        "dash_connector": 0,     # — 单字连接号（年段/链式/标准号）
        "dash_halfwidth": 0,     # - 半角连字符
        "colon_zh": 0,           # 中文冒号
        "colon_half": 0,         # 半角冒号
        "colon_prompt": 0,       # 提示性冒号（后接非引语）
        "quote_zh": 0,
        "quote_half": 0,
        "semicolon_zh": 0,
    }
    fp["dash_rhetoric"] = text.count(RHETORIC_DASH)
    stripped = text.replace(RHETORIC_DASH, "\x00\x00")
    fp["dash_connector"] = stripped.count(CONNECTOR_DASH)
    fp["dash_halfwidth"] = len(re.findall(r"(?<![0-9A-Za-z])-(?![0-9A-Za-z])", text))
    fp["colon_zh"] = text.count("：")
    fp["colon_half"] = text.count(":")
    for m in re.finditer(r"：", text):
        nxt = text[m.end() : m.end() + 1]
        if nxt not in "“”\"'":
            fp["colon_prompt"] += 1
    fp["quote_zh"] = len(re.findall(r"[“”]", text))
    fp["quote_half"] = len(re.findall(r"(?<![A-Za-z])[\"'](?![A-Za-z])", text))
    fp["semicolon_zh"] = text.count("；")
    return fp


def long_attributive_sentences(text: str, de_min: int = 4) -> List[str]:
    """含 ≥ de_min 个「的」的句子：长定语句是模型最典型的舒适区。"""
    out = []
    for s in split_sentences(text):
        if s.count("的") >= de_min:
            out.append(s)
    return out


@dataclass
class TextMetrics:
    """一份文本的全部可复算指标。"""

    han: int = 0
    chars_no_space: int = 0
    latin_words: int = 0
    sentences: int = 0
    sent_mean: float = 0.0
    sent_std: float = 0.0
    sent_cv: float = 0.0
    sent_min: int = 0
    sent_max: int = 0
    short_sentences: int = 0          # ≤8 汉字的短句数
    short_sentence_ratio: float = 0.0
    paragraphs: int = 0
    para_mean: float = 0.0
    para_median: float = 0.0
    para_std: float = 0.0
    para_cv: float = 0.0
    para_min: int = 0
    para_max: int = 0
    ngram4_repeat: float = 0.0
    ngram4_hot: List[Tuple[str, int]] = field(default_factory=list)
    repeated_sentences: List[Tuple[str, int]] = field(default_factory=list)
    long_attributive: int = 0
    punctuation: Dict[str, int] = field(default_factory=dict)

    def as_dict(self) -> Dict[str, object]:
        d = dict(self.__dict__)
        d["ngram4_hot"] = [list(x) for x in self.ngram4_hot]
        d["repeated_sentences"] = [list(x) for x in self.repeated_sentences]
        return d


def measure(text: str, short_len: int = 8) -> TextMetrics:
    """算出一份文本的全部指标（唯一入口，报告与测试都走这里）。"""
    sents = split_sentences(text)
    paras = split_paragraphs(text)
    sent_lens = [han_count(s) for s in sents]
    para_lens = [han_count(p) for p in paras]
    rate, hot = ngram_repeat(text)
    text_probe = text.replace(RHETORIC_DASH, "\x00\x00")
    return TextMetrics(
        han=han_count(text),
        chars_no_space=char_count(text),
        latin_words=len(LATIN_WORD.findall(text)),
        sentences=len(sents),
        sent_mean=round(_mean(sent_lens), 2),
        sent_std=round(_std(sent_lens), 2),
        sent_cv=round(_cv(sent_lens), 3),
        sent_min=min(sent_lens) if sent_lens else 0,
        sent_max=max(sent_lens) if sent_lens else 0,
        short_sentences=sum(1 for n in sent_lens if 0 < n <= short_len),
        short_sentence_ratio=round(sum(1 for n in sent_lens if 0 < n <= short_len) / max(1, len(sents)), 4),
        paragraphs=len(paras),
        para_mean=round(_mean(para_lens), 2),
        para_median=round(_median(para_lens), 2),
        para_std=round(_std(para_lens), 2),
        para_cv=round(_cv(para_lens), 3),
        para_min=min(para_lens) if para_lens else 0,
        para_max=max(para_lens) if para_lens else 0,
        ngram4_repeat=round(rate, 4),
        ngram4_hot=hot,
        repeated_sentences=repeated_sentences(text),
        long_attributive=len(long_attributive_sentences(text)),
        punctuation=punctuation_fingerprint(text_probe.replace("\x00\x00", RHETORIC_DASH)),
    )
