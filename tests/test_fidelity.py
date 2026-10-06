"""保真护栏测试：这是本项目与同类项目最大的区别，必须有回归覆盖。"""

from deslopkit.fidelity import check_fidelity, keep_terms_from, protected_spans


def kinds(text):
    return {s.kind for s in protected_spans(text)}


def test_extracts_all_protected_kinds():
    text = (
        "见 http://example.com/a 与 a@b.org ，文号渝教规办〔2026〕4 号，标准 T 0646—2022，"
        "《教师数字素养》与“四维机理”，引用[1,2]，覆盖 90.7% 与 11 428 份，模型 GenAI 与 AI+ 均已应用。"
    )
    k = kinds(text)
    for expected in ("url", "email", "doc_no", "std_no", "book_title", "zh_quote", "citation", "percent", "number", "latin_term"):
        assert expected in k, expected


def test_plain_english_words_are_not_protected():
    """普通英文单词不保护，否则英文文本任何改写都会被误判为保真失败。"""
    spans = protected_spans("teachers must examine the data carefully")
    assert spans == []


def test_latin_terms_are_protected():
    values = {s.value for s in protected_spans("使用 AI、GenAI、C-STEAM、5E、AI+ 与 T 0646—2022")}
    assert "AI" in values
    assert "GenAI" in values
    assert "C-STEAM" in values


def test_fidelity_flags_missing_number():
    rep = check_fidelity("有效问卷 11 428 份", "有效问卷 11 429 份")
    assert not rep.ok
    assert rep.missing and rep.added


def test_fidelity_flags_dropped_book_title():
    rep = check_fidelity("依据《教师数字素养》标准", "依据教师数字素养标准")
    assert not rep.ok
    assert rep.missing[0].kind == "book_title"


def test_fidelity_ok_when_only_wording_changes():
    rep = check_fidelity(
        "研究具有一定的参考价值，覆盖 90.7% 的区县。",
        "这项研究有参考价值，覆盖 90.7% 的区县。",
    )
    assert rep.ok
    assert rep.kept >= 1


def test_extra_keep_terms():
    rep = check_fidelity("重庆市教育科学研究院承担", "重庆市教科院承担", extra_keep=("重庆市教育科学研究院",))
    assert not rep.ok
    rep2 = check_fidelity("重庆市教育科学研究院承担", "重庆市教育科学研究院组织", extra_keep=("重庆市教育科学研究院",))
    assert rep2.ok


def test_keep_terms_from_prefers_repeated_terms():
    terms = keep_terms_from("重庆市教育科学研究院；重庆市教育科学研究院。AI；AI。")
    assert terms[0] in ("重庆市教育科学研究院", "AI")


def test_report_summary_is_human_readable():
    rep = check_fidelity("覆盖 90.7%", "覆盖 90.8%")
    assert "保真失败" in rep.summary()
    assert check_fidelity("无数字", "无数字").summary().startswith("保真通过")
