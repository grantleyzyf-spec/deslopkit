"""引擎（审计/改写/闸门）与 CLI 测试。"""

import json
import os

from deslopkit import audit, rewrite
from deslopkit.cli import main
from deslopkit.register import REGISTERS, detect_register, get_register

SAMPLE = (
    "本课题的研究不是单纯的技术问题，而是技术、教学、评价与治理交织的系统问题。"
    "人工智能赋能中小学课堂教学质量提升。\n"
    "\n"
    "上述问题值得注意的是：四个维度不是并列堆放，而是以过程重构为枢纽、以要素重构为基础。"
    "研究具有一定的参考价值，具有统计学意义。\n"
    "\n"
    "调查覆盖 38 个区县、20 所高校，发放问卷 12 600 份，回收有效 11 428 份，有效率 90.7%。\n"
    "\n"
    "按“理论建构—事实调查—机理检验—进路生成”推进，周期为 2026.10—2029.09。\n"
)


def test_audit_is_read_only():
    before = SAMPLE
    audit(SAMPLE, register="zh-gov")
    assert SAMPLE == before


def test_detect_register():
    assert detect_register(SAMPLE) == "zh-gov"
    assert detect_register("摘要：本研究采用问卷法。参考文献：[1] 张三. 论文[J]. 2023.") == "zh-academic"
    assert detect_register("今天聊聊这个事儿，老铁们。") == "zh-forum"
    assert detect_register("Abstract: this paper studies the effect. References: [1] Smith, J.") == "en-academic"
    assert detect_register("Just some plain prose without markers.") == "en-essay"


def test_registers_have_policy_and_bands():
    for key, p in REGISTERS.items():
        assert 0 < p.sent_cv_min < 1 and 0 < p.para_cv_min < 2
        assert p.gate, key
        assert p.policy("negation_pivot") != "off"
    assert get_register("zh-forum").policy("jargon") == "fix"


def test_rewrite_gate_passes_and_keeps_facts():
    res = rewrite(SAMPLE, register="zh-gov")
    assert res.gate.passed, [c.name for c in res.gate.failures()]
    assert res.fidelity.ok
    assert "11 428" in res.text and "90.7%" in res.text and "12 600" in res.text
    assert "赋能" not in res.text
    assert "不是单纯的技术问题，而是" not in res.text


def test_review_only_hits_do_not_fail_gate():
    text = SAMPLE + "\n其一是要素层面，其二是过程层面，其三是评价层面。\n"
    res = rewrite(text, register="zh-gov")
    assert res.gate.passed
    assert res.skipped_review >= 1


def test_gate_reports_small_sample_exemption():
    res = rewrite("人工智能赋能课堂。", register="zh-gov")
    cv_checks = [c for c in res.gate.checks if "CV" in c.name]
    assert cv_checks and all("样本过小" in c.detail for c in cv_checks)


def test_rewrite_preserves_paragraph_breaks():
    """回归：早期用 `\\s{2,}` 清理空白会把段落空行吃掉，整篇被并成一段。"""
    from deslopkit.metrics import split_paragraphs

    text = "第一段文字，人工智能赋能课堂。\n\n第二段文字，具有一定的参考价值。\n"
    out = rewrite(text, register="zh-gov").text
    assert "\n\n" in out, out
    assert len(split_paragraphs(out)) == len(split_paragraphs(text)) == 2


def test_short_input_uses_absolute_length_tolerance():
    """回归：26 字短句删掉「赋能」就是 15% 变动，按 ±10% 判会误报闸门。"""
    res = rewrite("人工智能赋能课堂教学，研究具有一定的参考价值，覆盖 90.7% 的区县。", register="zh-gov")
    drift = [c for c in res.gate.checks if c.name.startswith("字数变动")][0]
    assert drift.passed, drift.detail
    assert res.gate.passed


def test_english_delete_at_paragraph_start_capitalises():
    text = "In today's fast-paced world, teachers examine new tools.\n"
    out = rewrite(text, register="en-academic").text
    assert out.startswith("Teachers"), out


def test_rewrite_is_deterministic():
    a = rewrite(SAMPLE, register="zh-gov").text
    b = rewrite(SAMPLE, register="zh-gov").text
    assert a == b


def test_cli_audit_writes_markdown_and_json(tmp_path):
    src = tmp_path / "in.txt"
    src.write_text(SAMPLE, encoding="utf-8")
    md = tmp_path / "report.md"
    js = tmp_path / "report.json"
    rc = main(["audit", str(src), "--register", "zh-gov", "--md", str(md), "--json", str(js), "--quiet"])
    assert rc == 0
    assert md.exists() and "审计报告" in md.read_text(encoding="utf-8")
    data = json.loads(js.read_text(encoding="utf-8"))
    assert data[0]["kind"] == "audit" and data[0]["metrics"]["han"] > 0


def test_cli_audit_exit_code_on_high_severity(tmp_path):
    src = tmp_path / "in.txt"
    src.write_text("人工智能赋能课堂。\n", encoding="utf-8")
    assert main(["audit", str(src), "--exit-code", "--quiet"]) == 1
    clean = tmp_path / "clean.txt"
    clean.write_text("本课题按计划完成了调查与试点，结果为教师素养提升。\n", encoding="utf-8")
    assert main(["audit", str(clean), "--exit-code", "--quiet"]) == 0


def test_cli_rewrite_out_dir_and_gate_exit(tmp_path):
    src = tmp_path / "in.txt"
    src.write_text(SAMPLE, encoding="utf-8")
    outdir = tmp_path / "out"
    md = tmp_path / "rw.md"
    rc = main(["rewrite", str(src), "-o", str(outdir), "--register", "zh-gov", "--md", str(md), "--exit-code"])
    out = outdir / "in.deslop.txt"
    assert out.exists()
    text = out.read_text(encoding="utf-8")
    assert "赋能" not in text and "11 428" in text
    assert rc == 0
    assert "闸门检查" in md.read_text(encoding="utf-8")


def test_cli_rewrite_stdout_and_in_place(tmp_path, capsys):
    src = tmp_path / "in.txt"
    src.write_text("人工智能赋能课堂。\n", encoding="utf-8")
    assert main(["rewrite", str(src), "--register", "zh-gov", "--passes", "1"]) == 0
    out = capsys.readouterr().out
    assert "助力" in out
    src2 = tmp_path / "in2.txt"
    src2.write_text("人工智能赋能课堂。\n", encoding="utf-8")
    assert main(["rewrite", str(src2), "--in-place", "--register", "zh-gov"]) == 0
    assert "助力" in src2.read_text(encoding="utf-8")


def test_cli_rules_and_registers(capsys):
    assert main(["rules", "--lang", "zh", "--category", "jargon"]) == 0
    out = capsys.readouterr().out
    assert "赋能" in out
    assert main(["registers"]) == 0
    out2 = capsys.readouterr().out
    assert "zh-gov" in out2 and "英文" in out2


def test_cli_missing_file_returns_usage_error(tmp_path):
    assert main(["audit", str(tmp_path / "nope.txt")]) == 2


def test_package_data_rules_are_shipped():
    import deslopkit.rules as rules_pkg

    assert os.path.isdir(rules_pkg.RULES_DIR)
    assert (rules_pkg.RULES_DIR / "zh.json").exists()
    assert (rules_pkg.RULES_DIR / "en.json").exists()
