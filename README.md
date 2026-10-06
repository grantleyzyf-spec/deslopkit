# deslopkit

> **Register-aware, fidelity-preserving AI-text de-slopping toolkit for Chinese and English.**
> 语域感知 + 保真护栏的中英双语文本去 AI 化工具包 —— Python 库 / CLI / Agent Skill 三合一。

[![CI](https://github.com/grantleyzyf-spec/deslopkit/actions/workflows/ci.yml/badge.svg)](https://github.com/grantleyzyf-spec/deslopkit/actions/workflows/ci.yml)
[![License: Apache-2.0](https://img.shields.io/badge/license-Apache--2.0-blue.svg)](LICENSE)
[![Python](https://img.shields.io/badge/python-3.9%20%7C%203.10%20%7C%203.11%20%7C%203.12%20%7C%203.13-blue)](pyproject.toml)
[![Runtime deps: 0](https://img.shields.io/badge/runtime%20dependencies-0-success)](pyproject.toml)

`deslopkit` finds machine-writing tells in text, reports them with **recomputable numbers**, rewrites only what it
can rewrite deterministically, **refuses any rewrite that would damage a fact**, and refuses to call a job done
unless its own gates pass.

```console
$ deslopkit audit report.txt --register zh-gov
report.txt: [zh-gov] 汉字 9291 ｜ 句长CV 0.747 ｜ 段长CV 0.897 ｜ 短句占比 0.1036 ｜ 命中 13 处（jargon:6, negation_pivot:4, ...）
  L23 [zh.neg.001] 翻案腔：先立一个不存在的误解再推翻（“不是A，而是B”）。 → 不是单纯的技术问题，而是技术、教学、评价与治理交织的系统问题
  ...

$ deslopkit rewrite report.txt -o out/ --register zh-gov --exit-code
[zh-gov] 过闸 ｜ 应用 8 处 ｜ 因保真/安全回滚 0 处 ｜ 仅提示 10 处 ｜ 汉字 9291→9282
```

---

## Why another "AI-text humanizer"?

The space already has excellent work. `deslopkit` was built after reading them, and it targets the gaps they leave.

| Existing work | Strength we keep | Gap we close |
|---|---|---|
| [`blader/humanizer`](https://github.com/blader/humanizer) (54k★) | The pattern catalogue from Wikipedia's *Signs of AI writing*; before/after prose pairs | It is an **agent prompt**: not callable from code, no metrics, no regression tests, English-centric |
| [`humanizer-zh-academic`](https://github.com/redbaronyyyyy-eng/humanizer-zh-academic) | Chinese academic register, noise budget, hard constraints, 16 pattern families | Still LLM-executed ⇒ **not reproducible**; no machine-checkable fidelity; no CLI/CI |
| [`ProfSynapse/DeSlop`](https://github.com/ProfSynapse/DeSlop) | Mechanically locate tells, adjudicate against false positives, **refuse to deliver if its own gates still trip** | Gate is a prompt instruction, not code; English; no fact-preservation check |
| [`ilyautov/humanizer-ru`](https://github.com/ilyautov/humanizer-ru) | 67-feature catalogue, genre exceptions, ships a scanner/CLI | Russian-first; feature catalogue not expressed as a shareable rule format with tests |
| [`chi111i/BypassAIGC`](https://github.com/chi111i/BypassAIGC)(2.1k★), [`Abnerla/AI_paper`](https://github.com/Abnerla/AI_paper) | Chinese academic focus, end-to-end flow | Effect shown as screenshots; no baseline metrics; no way to verify what changed |
| Commercial humanizers | Convenience | Closed, unreproducible, unverifiable, and often falsely claim a specific detector score |

Five things `deslopkit` does that the field mostly does not:

1. **Deterministic core, zero runtime dependencies.** Rule matching and rewriting are template expansion —
   the same input always yields the same output, so it can live in CI and in a regression suite.
2. **Fidelity Guard (自动保真护栏).** Every protected span — numbers, percentages, units, doc numbers,
   standard numbers, book titles, quoted terms, citation markers, URLs, e-mails, and user-supplied keep-terms —
   is compared before/after rewrite. **Any loss *or* addition rolls that edit back**, and the rollback is reported.
3. **Register awareness (语域).** Chinese officialese, Chinese academic, Chinese forum, English academic and
   English essay have different rule switches and thresholds. Rules meant to freshen blog prose are *switched off*
   for government-style documents, because turning compliant officialese into chatty prose is a defect, not a fix.
4. **Recomputable evidence.** Sentence-length CV, paragraph-length CV, short-sentence ratio, n-gram repetition,
   punctuation fingerprints (with **connector dashes separated from rhetorical dashes**), long-attributive clauses —
   printed before/after and compared against documented human baselines (`docs/metrics.md`).
5. **Delivery gates + honest boundary.** The run is not "done" unless the gate passes: fidelity intact,
   gate categories at zero, CV not degraded, length drift ≤10%, no new repeated sentences. And the report states
   plainly what the tool *cannot* do (see below).

---

## Install

```bash
pip install deslopkit            # from PyPI, once released
pip install -e ".[dev]"          # from source, with test/lint tooling
python -m deslopkit --help
```

Requires Python ≥ 3.9. No runtime dependencies.

## Quickstart

```bash
deslopkit registers                       # 看 5 套语域画像与阈值
deslopkit rules --lang zh --category jargon

deslopkit audit essay.md --md audit.md --json audit.json      # 只诊断，不改动
deslopkit rewrite essay.md -o fixed/ --register zh-academic \
        --keep-from 原稿.txt --md rewrite.md --exit-code       # 改写 + 报告 + 闸门退出码
```

As a library:

```python
from deslopkit import audit, rewrite

a = audit(text, register="zh-gov")          # 只读
print(a.summary(), a.counts, a.bands)

r = rewrite(text, register="zh-gov", keep=["重庆", "四维机理"], passes=3)
print(r.text, r.gate.passed, [c.name for c in r.gate.failures()])
print(r.fidelity.summary())                 # 保真：N 个受保护片段逐字保留
```

Real before/after on a Chinese research-report paragraph:

```text
before  本课题的研究不是单纯的技术问题，而是技术、教学、评价与治理交织的系统问题。
        人工智能赋能中小学课堂教学质量提升，形成教研闭环。
        上述问题值得注意的是：研究具有一定的参考价值，且具有统计学意义。

after   本课题的研究是技术、教学、评价与治理交织的系统问题，而不是单纯的技术问题。
        人工智能助力中小学课堂教学质量提升，形成教研闭环。
        上述问题，研究有参考价值，且差异在统计上显著。
```

## Registers

| key | scope | auto-rewrite | advisory only | gate categories |
|---|---|---|---|---|
| `zh-gov` | 中文公文体（课题报告 / 公文 / 方案 / 公示） | 翻案腔、黑话、名词化、填充词 | 路标词、排比、抒情、标点 | `negation_pivot` |
| `zh-academic` | 中文学术体（论文 / 研究报告 / 学位论文） | 上列 + 路标词 | 排比、抒情、标点 | `negation_pivot`,`jargon` |
| `zh-forum` | 中文网帖体（知乎 / 论坛 / 公众号） | 全部 | 排比 | 翻案腔、黑话、路标词 |
| `en-academic` | English paper / report | clichés, negation pivot, jargon, filler | signposts, triads, lyric, punctuation | `english_cliche`,`negation_pivot` |
| `en-essay` | English prose / blog | all of the above | triads | + `signposting` |

`--register auto` detects the register from CJK ratio plus policy/format keywords.

**Connector dashes are never treated as a tell.** In Chinese, `2026.10—2029.09`, `学—教—研—评`, `T 0646—2022`
are standard GB usage; the metrics code counts them separately from rhetorical `——`.

## What it will not do (read this before using it)

- **It does not change who wrote the text.** Using it does not make a machine-generated text human-authored, and
  this project never claims otherwise.
- **It does not promise any third-party detector score.** Detectors are probabilistic; results move between runs and
  versions. If your institution uses one, get its **baseline report first**, then fix the paragraphs it flags —
  don't rewrite blind.
- **It does not "beat" a detector as a product goal.** The purpose is better writing: fewer template sentences,
  fewer empty signposts, fewer noun-stacked clauses, and provably intact facts.
- **Structural rewrites need human eyes.** Negation-pivot reordering is flagged `needs_review` in the report.
- Follow your institution's AI-use policy, and disclose tool use where required.

## Metrics & baselines

Every number in a report is reproducible by re-running `deslopkit audit`. Baselines for each register are in
[`docs/metrics.md`](docs/metrics.md) — they come from human-written samples of the same register, not from taste.

| metric | what it catches |
|---|---|
| 句长 CV / 段长 CV | uniform sentence and paragraph lengths (the two numbers detectors look at) |
| ≤8 字短句占比 | absence of rhythm / breathing room |
| 4-gram 重复率 | spliced or padded text |
| 长定语句（≥4 个「的」） | model-favoured stacked attributives |
| 标点指纹 | rhetorical `——` vs GB connector `—`, promptive colons, half/full-width mixing |
| 重复整句 | the same sentence twice |

## Project layout

```
src/deslopkit/
├── metrics.py       指标（纯函数、可复算）
├── fidelity.py      保真护栏：受保护片段抽取 + 前后比对
├── rules/           zh.json / en.json 规则库（JSON，可直接改）
├── rewriters.py     确定性改写器（模板展开 + 回滚）
├── engine.py        audit / rewrite / 交付闸门
├── register.py      5 套语域画像与参照带
├── report.py        Markdown / JSON 报告
└── cli.py           CLI
tests/               44 个用例（指标 / 保真 / 规则 / 改写 / 引擎与 CLI）
docs/                设计说明、指标参照带、规则格式、使用边界
examples/            输入样例 + 真实改写输出 + 报告样例
skills/deslopkit/    Agent Skill 入口（Claude Code / Codex / Hermes 可直接加载）
```

## Contributing

New rules are one JSON object plus one test. See [CONTRIBUTING.md](CONTRIBUTING.md) — and please read
[docs/ethics.md](docs/ethics.md) first; PRs that promise detector scores will be declined.

```bash
make install && make test && make lint
```

## Prior art & acknowledgements

This project stands on the shoulders of the pattern catalogues the community has assembled:
Wikipedia **WikiProject AI Cleanup** (*Signs of AI writing*), [`blader/humanizer`](https://github.com/blader/humanizer),
[`ProfSynapse/DeSlop`](https://github.com/ProfSynapse/DeSlop) (gate-refusal idea),
[`ilyautov/humanizer-ru`](https://github.com/ilyautov/humanizer-ru) (feature catalogue + genre exceptions),
[`humanizer-zh-academic`](https://github.com/redbaronyyyyy-eng/humanizer-zh-academic) (noise budget, register fit),
[`chi111i/BypassAIGC`](https://github.com/chi111i/BypassAIGC) and [`Abnerla/AI_paper`](https://github.com/Abnerla/AI_paper)
(Chinese academic focus). What is new here is the engineering: deterministic rules, a fidelity gate, register policy,
recomputable metrics, and CI.

## License

[Apache-2.0](LICENSE) © 2026 deslopkit contributors
