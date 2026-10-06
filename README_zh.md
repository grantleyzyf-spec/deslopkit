# deslopkit

> **语域感知 + 保真护栏的中英双语文本去 AI 化工具包** —— Python 库 / CLI / Agent Skill 三合一。
> Register-aware, fidelity-preserving AI-text de-slopping toolkit for Chinese and English.

[![CI](https://github.com/grantleyzyf-spec/deslopkit/actions/workflows/ci.yml/badge.svg)](https://github.com/grantleyzyf-spec/deslopkit/actions/workflows/ci.yml)
[![License: Apache-2.0](https://img.shields.io/badge/license-Apache--2.0-blue.svg)](LICENSE)
[![Python](https://img.shields.io/badge/python-3.9%20%7C%203.10%20%7C%203.11%20%7C%203.12%20%7C%203.13-blue)](pyproject.toml)
[![运行时依赖: 0](https://img.shields.io/badge/%E8%BF%90%E8%A1%8C%E6%97%B6%E4%BE%9D%E8%B5%96-0-success)](pyproject.toml)

`deslopkit` 找出文本里的机器写作痕迹，用**可复算的数字**报出来，只做**能确定性做对**的改写，
**任何会破坏事实的改写一律拒绝**，并且**未过自己的闸门就不算完成**。

```console
$ deslopkit audit 开题报告.txt --register zh-gov
开题报告.txt: [zh-gov] 汉字 9291 ｜ 句长CV 0.747 ｜ 段长CV 0.897 ｜ 短句占比 0.1036 ｜ 命中 13 处（jargon:6, negation_pivot:4, …）
  L23 [zh.neg.001] 翻案腔：先立一个不存在的误解再推翻（“不是A，而是B”）。 → 不是单纯的技术问题，而是技术、教学、评价与治理交织的系统问题

$ deslopkit rewrite 开题报告.txt -o out/ --register zh-gov --exit-code
[zh-gov] 过闸 ｜ 应用 8 处 ｜ 因保真/安全回滚 0 处 ｜ 仅提示 10 处 ｜ 汉字 9291→9282
```

---

## 为什么还要再造一个「去 AI 味」工具

这个领域已有很好的成果（详见 [docs/design.md](docs/design.md) 的对照表）。`deslopkit` 是在读完之后写的，
它针对的是它们留下的缺口：

| 已有成果 | 我们吸收的优点 | 我们补的缺口 |
|---|---|---|
| [`blader/humanizer`](https://github.com/blader/humanizer)（54k★） | 基于维基百科 *Signs of AI writing* 的征候清单、前后对照示范 | 它是**提示词 Skill**：无法被代码调用、无指标、无回归测试、偏英文 |
| [`humanizer-zh-academic`](https://github.com/redbaronyyyyy-eng/humanizer-zh-academic) | 中文学术语域、噪声预算、硬约束、16 类模式 | 仍由 LLM 执行 ⇒ **不可复现**；无机器可校验的保真；无 CLI/CI |
| [`ProfSynapse/DeSlop`](https://github.com/ProfSynapse/DeSlop) | 机械定位痕迹、对误报先裁定、**未过自查门禁不交付** | 门禁是提示词约定而非代码；英文；不校验事实保真 |
| [`ilyautov/humanizer-ru`](https://github.com/ilyautov/humanizer-ru) | 67 项特征目录、体裁例外、附带扫描器/CLI | 俄语优先；特征目录未做成可共享、可测试的规则格式 |
| [`chi111i/BypassAIGC`](https://github.com/chi111i/BypassAIGC)（2.1k★）、[`Abnerla/AI_paper`](https://github.com/Abnerla/AI_paper) | 中文学术定位、端到端流程 | 效果以截图宣称；无基线指标；无法验证改了什么 |

`deslopkit` 做了五件同类项目基本没做的事：

1. **确定性内核、零运行时依赖。** 规则匹配 + 模板展开，同一输入永远同一输出，可进 CI、可写回归测试。
2. **保真护栏。** 数字、百分比、文号、标准号、书名号、引号内术语、引用标记、URL、邮箱、
   用户声明的必保词——改写前后逐项比对，**丢失或新增都回滚该处改写**并写进报告。
3. **语域感知。** 中文公文、中文学术、中文网帖、英文学术、英文散文各有一套规则开关与阈值。
   用来「洗网帖」的规则在公文语域**会被关掉**——把合规机构腔改成口语，是缺陷不是修复。
4. **可复算证据。** 句长 CV、段长 CV、短句占比、n-gram 重复率、标点指纹
   （**连接号与修辞破折号分开统计**）、长定语句——处理前后对照，并与同语域人工参照带比对。
5. **交付闸门 + 诚实边界。** 六项检查全过才算完成；报告里内置「使用边界」一节，明确写出工具的做不到。

---

## 安装

```bash
pip install deslopkit          # 发布后可从 PyPI 安装
pip install -e ".[dev]"        # 源码安装（含测试/静态检查工具）
python -m deslopkit --help
```

要求 Python ≥ 3.9，**无运行时依赖**。

## 快速上手

```bash
deslopkit registers                    # 查看 5 套语域画像与阈值
deslopkit rules --lang zh --category jargon

deslopkit audit 文稿.md --md audit.md --json audit.json            # 只诊断
deslopkit rewrite 文稿.md -o fixed/ --register zh-academic \
        --keep-from 原稿.txt --md rewrite.md --exit-code            # 改写 + 报告 + 闸门退出码
```

作为库调用：

```python
from deslopkit import audit, rewrite

a = audit(text, register="zh-gov")            # 只读，不改文本
print(a.summary(), a.counts, a.bands)

r = rewrite(text, register="zh-gov", keep=["重庆", "四维机理"], passes=3)
print(r.text, r.gate.passed, [c.name for c in r.gate.failures()])
print(r.fidelity.summary())                   # 保真：N 个受保护片段逐字保留
```

真实前后对照（中文课题报告段落）：

```text
处理前  本课题的研究不是单纯的技术问题，而是技术、教学、评价与治理交织的系统问题。
        人工智能赋能中小学课堂教学质量提升，形成教研闭环。
        上述问题值得注意的是：研究具有一定的参考价值，且具有统计学意义。

处理后  本课题的研究是技术、教学、评价与治理交织的系统问题，而不是单纯的技术问题。
        人工智能助力中小学课堂教学质量提升，形成教研闭环。
        上述问题，研究有参考价值，且差异在统计上显著。
```

## 语域画像

| key | 适用范围 | 自动改写 | 仅提示 | 闸门类别 |
|---|---|---|---|---|
| `zh-gov` | 中文公文体（课题报告 / 公文 / 方案 / 公示） | 翻案腔、黑话、名词化、填充词 | 路标词、排比、抒情、标点 | `negation_pivot` |
| `zh-academic` | 中文学术体（论文 / 研究报告 / 学位论文） | 上列 + 路标词 | 排比、抒情、标点 | 翻案腔、黑话 |
| `zh-forum` | 中文网帖体（知乎 / 论坛 / 公众号） | 全部 | 排比 | 翻案腔、黑话、路标词 |
| `en-academic` | 英文学术体 | 陈词滥调、翻案腔、黑话、填充词 | 路标、三项排比、抒情、标点 | `english_cliche`、翻案腔 |
| `en-essay` | 英文散文 / 博客 | 上列全部 | 三项排比 | 再 + 路标词 |

`--register auto` 会按 CJK 占比与政策/格式关键词自动判定语域。

**连接号永远不被当作痕迹。** 中文里 `2026.10—2029.09`、`学—教—研—评`、`T 0646—2022` 都是国标本义用法，
指标代码把它们与修辞破折号 `——` 分开计数。

## 它不会做什么（用之前请读）

- **不改变文本的生成来源。** 用过这个工具，不等于文本成了人写的；本项目也从不这样宣称。
- **不承诺任何第三方检测器的分数。** 检测器是概率模型，换版本换时间结果就会变。
  如果所在机构使用检测，请**先拿基线报告**，再按它指出的段落定点处理——不要盲改全篇。
- **不把「骗过检测器」当作产品目标。** 目的是更好的写作：更少的模板句、更少的空泛路标、
  更少的名词堆叠，以及**可证未坏的事实**。
- **结构性改写需人工过目。** 翻案句重排在报告里标为 `needs_review`。
- 请遵守所在单位的 AI 使用规定，需要时如实说明工具使用情况（详见 [docs/ethics.md](docs/ethics.md)）。

## 指标与参照带

报告里的每个数字都能用 `deslopkit audit` 复算。各语域的参照带（来自同语域真人样本）见
[docs/metrics.md](docs/metrics.md)：

| 指标 | 抓什么 |
|---|---|
| 句长 CV / 段长 CV | 句段长度过于规整（检测器真正在看的两个量） |
| ≤8 字短句占比 | 缺不缺呼吸感 |
| 4-gram 重复率 | 资料拼接、同义反复、注水 |
| 长定语句（≥4 个「的」） | 模型偏好的多重定语长句 |
| 标点指纹 | 修辞破折号 vs 国标连接号、提示性冒号、全半角混用 |
| 重复整句 | 同一句出现两次 |

## 目录结构

```
src/deslopkit/
├── metrics.py       指标（纯函数、可复算）
├── fidelity.py      保真护栏：受保护片段抽取 + 前后比对
├── rules/           zh.json / en.json 规则库（JSON，可直接改）
├── rewriters.py     确定性改写器（模板展开 + 回滚）
├── engine.py        audit / rewrite / 交付闸门
├── register.py      5 套语域画像与参照带
├── report.py        Markdown / JSON 报告
└── cli.py           命令行
tests/               44 个用例（指标 / 保真 / 规则 / 改写 / 引擎与 CLI）
docs/                设计说明、指标参照带、规则格式、使用边界
examples/            输入样例 + 真实改写输出 + 报告样例
skills/deslopkit/    Agent Skill 入口（Claude Code / Codex / Hermes 可直接加载）
```

## 贡献

新增一条规则 = 一个 JSON 对象 + 一个测试用例，见 [CONTRIBUTING.md](CONTRIBUTING.md)。
请先读 [docs/ethics.md](docs/ethics.md)：**承诺检测器分数的 PR 一律拒绝。**

```bash
make install && make test && make lint
```

## 致谢与先行工作

本项目的英文征候清单来自社区整理的模式目录：维基百科 **WikiProject AI Cleanup**（*Signs of AI writing*）、
[`blader/humanizer`](https://github.com/blader/humanizer)、[`ProfSynapse/DeSlop`](https://github.com/ProfSynapse/DeSlop)
（「未过门禁不交付」的思路）、[`ilyautov/humanizer-ru`](https://github.com/ilyautov/humanizer-ru)（特征目录 + 体裁例外）、
[`humanizer-zh-academic`](https://github.com/redbaronyyyyy-eng/humanizer-zh-academic)（噪声预算、语域适配）、
[`chi111i/BypassAIGC`](https://github.com/chi111i/BypassAIGC) 与 [`Abnerla/AI_paper`](https://github.com/Abnerla/AI_paper)（中文学术定位）。
本项目新增的是工程实现：确定性规则、保真闸门、语域策略、可复算指标与 CI。

## 许可

[Apache-2.0](LICENSE) © 2026 deslopkit contributors
