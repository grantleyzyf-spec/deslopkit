"""指标层测试：所有数字都必须能被第三方用同样代码重算。"""

from deslopkit.metrics import (
    han_count,
    long_attributive_sentences,
    measure,
    ngram_repeat,
    punctuation_fingerprint,
    repeated_sentences,
    split_paragraphs,
    split_sentences,
)

TEXT = (
    "本课题以四维机理为框架。调查覆盖 38 个区县与 20 所高校，发放问卷 12 600 份，回收有效 11 428 份。\n"
    "\n"
    "教师智能素养总体均分为 3.42，其中伦理与数据安全维度最低。区域差异显著（F=23.6，p<0.01）。\n"
    "\n"
    "研究周期为 2026.10—2029.09，按“理论建构—事实调查—机理检验—进路生成”推进。\n"
)


def test_han_count_only_counts_cjk():
    assert han_count("abc 123 汉字") == 2
    assert han_count("90.7%") == 0
    assert han_count("") == 0


def test_split_paragraphs_and_sentences():
    paras = split_paragraphs(TEXT)
    assert len(paras) == 3
    sents = split_sentences(TEXT)
    assert len(sents) >= 5
    assert all(s.strip() for s in sents)


def test_measure_core_metrics():
    m = measure(TEXT)
    assert m.han >= 80
    assert m.paragraphs == 3
    assert m.sentences >= 5
    assert m.sent_min <= m.sent_mean <= m.sent_max
    assert 0 <= m.ngram4_repeat <= 1


def test_cv_is_zero_for_uniform_and_positive_for_varied():
    uniform = "一。二。三。"
    varied = "一。二三四五六七八九十。短。"
    assert measure(uniform).sent_cv == 0
    assert measure(varied).sent_cv > 0


def test_connector_dash_is_not_counted_as_rhetoric_dash():
    """连接号（年段/链式/标准号）是国标本义，不能当成修辞破折号。"""
    fp = punctuation_fingerprint("周期为 2026.10—2029.09，按“理论建构—事实调查”推进，见 T 0646—2022。")
    assert fp["dash_rhetoric"] == 0
    assert fp["dash_connector"] >= 3
    fp2 = punctuation_fingerprint("问题在于——它并不成立。")
    assert fp2["dash_rhetoric"] == 1


def test_colon_prompt_detection():
    fp = punctuation_fingerprint("核心是：三件事。原话说：“就这样办”。")
    assert fp["colon_zh"] == 2
    assert fp["colon_prompt"] == 1


def test_ngram_and_repeated_sentences():
    rate, hot = ngram_repeat("人工智能与教师教育人工智能与教师教育", n=4)
    assert rate > 0
    assert hot and hot[0][1] >= 2
    rep = repeated_sentences("这句话一共十个字以上。这句话一共十个字以上。")
    assert rep and rep[0][1] == 2


def test_long_attributive_detection():
    s = "本课题的研究的设计的思路的框架的表述需要重写。"
    assert s.count("的") >= 4
    assert long_attributive_sentences(s) == [s]
    assert long_attributive_sentences("短句没有结构助词。") == []


def test_measure_is_deterministic():
    assert measure(TEXT).as_dict() == measure(TEXT).as_dict()
