"""规则库与改写器测试。"""

import re

from deslopkit.register import get_register
from deslopkit.rewriters import apply_edits, expand_replacement, rewrite_once, tidy
from deslopkit.rules import Rule, RuleHit, category_counts, find_hits, load_rules


def test_rule_library_loads_and_ids_are_unique():
    zh = load_rules("zh")
    en = load_rules("en")
    assert len(zh) >= 25 and len(en) >= 20
    ids = [r.id for r in zh] + [r.id for r in en]
    assert len(ids) == len(set(ids))
    assert all(r.pattern and r.category for r in zh + en)


def test_every_rewrite_rule_has_a_strategy():
    for r in load_rules():
        if r.action == "rewrite":
            assert r.strategy, r.id


def test_quoted_spans_are_skipped_by_default():
    text = "报告指出“人工智能赋能课堂”，随后又强调人工智能赋能课堂的价值。"
    hits = find_hits(text, load_rules("zh"), register_key="zh-gov")
    assertions = [h for h in hits if h.rule.category == "jargon"]
    assert len(assertions) == 1, [h.text for h in assertions]
    hits_all = find_hits(text, load_rules("zh"), register_key="zh-gov", include_quoted=True)
    assert len([h for h in hits_all if h.rule.category == "jargon"]) == 2


def test_register_filtering():
    rules = load_rules("zh")
    forum_only = [r for r in rules if r.registers == ("zh-forum",)]
    assert forum_only
    assert all(not r.applies_to("zh-gov") for r in forum_only)

    text = "这并不成立——它是另一回事。"
    ids_forum = {h.rule.id for h in find_hits(text, rules, register_key="zh-forum")}
    ids_gov = {h.rule.id for h in find_hits(text, rules, register_key="zh-gov")}
    assert "zh.pun.001" in ids_forum
    assert "zh.pun.001" not in ids_gov

    text2 = "综上所述，结论成立。"
    assert "zh.sig.003" in {h.rule.id for h in find_hits(text2, rules, register_key="zh-forum")}
    assert "zh.sig.003" not in {h.rule.id for h in find_hits(text2, rules, register_key="zh-gov")}


def test_category_counts_sorted_by_frequency():
    text = "赋能，赋能，赋能，深度融合。"
    counts = category_counts(find_hits(text, load_rules("zh"), register_key="zh-forum"))
    assert counts["jargon"] == 4
    assert list(counts)[0] == "jargon"


def test_neg_pivot_copula_insertion():
    rx = re.compile("(?:并非|不是|不在于)([^，。；：！？]{2,40})，(?:而是|而在于)([^。；！？]{4,80})")
    rule = Rule(
        id="t.neg", lang="zh", registers=("all",), category="negation_pivot",
        pattern=rx.pattern, action="rewrite", strategy="neg_pivot", replacement="\\2，而不是\\1",
    )
    text = "本课题的研究不是单纯的技术问题，而是技术、教学与治理交织的系统问题"
    m = rx.search(text)
    hit = RuleHit(rule=rule, text=m.group(0), start=m.start(), end=m.end())
    out = expand_replacement(hit, text[: m.start()])
    assert out.startswith("是"), out
    assert "而不是" in out

    # 主语以“以/通过”等已有谓语开头时，不再补“是”
    text2 = "四个维度不是并列堆放，而是以过程重构为枢纽"
    m2 = rx.search(text2)
    hit2 = RuleHit(rule=rule, text=m2.group(0), start=m2.start(), end=m2.end())
    out2 = expand_replacement(hit2, text2[: m2.start()])
    assert out2.startswith("以过程重构为枢纽")


def test_english_neg_pivot_keeps_copula():
    rules = {r.id: r for r in load_rules("en")}
    rule = rules["en.neg.001"]
    text = "The reform is not just about technology, but about how teachers use it."
    hit = find_hits(text, [rule], register_key="en-academic")[0]
    out = expand_replacement(hit, text[: hit.start])
    assert out.lower().startswith("is about")
    assert "not just" in out


def test_delete_strategy_consumes_following_punctuation():
    text = "上述问题值得注意的是：四个维度并非并列。"
    res = rewrite_once(text, get_register("zh-gov"))
    assert "值得注意的是" not in res.text
    assert "上述问题，四个维度" in res.text, res.text


def test_delete_strategy_english_does_not_leave_stray_comma():
    text = "In today's fast-paced world, teachers examine new tools."
    res = rewrite_once(text, get_register("en-academic"))
    assert not res.text.startswith(",")
    assert res.text.startswith("teachers") or res.text.startswith("Teachers"), res.text


def test_fidelity_rollback_on_protected_token():
    """构造一条会吃掉受保护数字的规则：必须被回滚，不写入正文。"""
    rule = Rule(
        id="t.bad", lang="zh", registers=("all",), category="jargon",
        pattern="赋能 90\\.7%", action="rewrite", strategy="replace", replacement="助力",
    )
    text = "覆盖率赋能 90.7% 的区县。"
    hit = find_hits(text, [rule], register_key="zh-gov")[0]
    res = apply_edits(text, [hit], get_register("zh-gov"))
    assert res.text == text
    assert res.rejected and "保真" in res.rejected[0].reason


def test_tidy_collapses_double_punctuation():
    assert tidy("文本，，文本") == "文本，文本"
    assert tidy("文本，。") == "文本。"
    assert tidy("，文本") == "文本"


def test_rewrite_once_is_deterministic():
    text = "人工智能赋能课堂教学，研究具有一定的参考价值。"
    a = rewrite_once(text, get_register("zh-gov")).text
    b = rewrite_once(text, get_register("zh-gov")).text
    assert a == b
    assert "助力" in a and "有参考价值" in a
