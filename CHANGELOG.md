# Changelog

All notable changes to this project will be documented in this file.

The format is based on [Keep a Changelog](https://keepachangelog.com/en/1.1.0/),
and this project adheres to [Semantic Versioning](https://semver.org/spec/v2.0.0.html).

## [Unreleased]

### Planned

- 扩展英文规则库（散文 / 学术之外的口语与新闻语域）。
- 更细粒度的可复算指标（句长方差、n-gram 复用率、连接词密度）。
- 规则命中原因的逐条可读解释。

## [0.1.0] - 2026-10-06

首个公开版本。deslopkit 是一个**语域感知 + 保真护栏**的中英双语文本去 AI 化工具包
（Python 库 + CLI + Agent Skill），用于降低模板化表达与机器痕迹，全部指标可复算，
并且**不承诺任何第三方检测器的结果**。

### Added

- **确定性规则引擎**：核心流程零 LLM 依赖，纯规则 + 正则 + 词表驱动，结果可复现。
- **保真护栏（Fidelity Guard）**：改写后自动逐字校验数字、专名、引文是否被保留，
  一旦发现被改动即拦截并报告，默认行为不可静默关闭。
- **语域画像（register profiles）**：内置五类语域——中文公文、中文学术、中文网帖、
  英文学术、英文散文——不同语域切换不同的规则集与阈值。
- **CLI**：`deslopkit` 命令行入口，四个子命令 `audit` / `rewrite` / `rules` / `registers`，
  支持 `--exit-code` 闸门退出码、`--md` / `--json` 双报告、`--keep` / `--keep-from` 必保词。
- **报告**：`deslopkit audit` 生成可复算的 Markdown 报告与 JSON（含全部原始计数），
  便于回归比较；`rewrite` 报告含「闸门检查 / 已应用改写 / 被回滚改写 / 保真校验 / 使用边界」五节。
- **双语规则库**：`src/deslopkit/rules/*.json` 结构化的中英文规则条目（首版 31 条中文 + 25 条英文），
  字段为 `id/lang/registers/category/pattern/flags/severity/action/strategy/replacement/skip_quoted/message/fix_hint`。
- **Agent Skill 入口**：`skills/deslopkit/SKILL.md`，提供面向 Agent 的调用契约与汇报格式。
- **诚实声明**：明确不保证任何第三方 AI 检测器的判定结果，只保证过程可复算、
  改动可审计、保真可验证（`docs/ethics.md`）。

### Fixed（首版实测中修正的真实缺陷，均有回归测试）

- **段落结构被改写吃掉**：`tidy()` 原用 `\s{2,}` 清理空白，会把段落之间的空行一起压缩，
  整篇被并成一段。改为只压缩空格/制表符，新增 `test_rewrite_preserves_paragraph_breaks`。
- **保真护栏误报（机构名自动抽取）**：`…小学/…大学` 这类后缀会把前文任意汉字吞进匹配，
  实测「人工智能赋能中小学」被当作机构名，导致正常改写被回滚。移除自动抽取，改由 `--keep` 声明。
- **英文改写全部被回滚**：首版把普通英文单词也列为受保护片段，实测 5/5 改写回滚。
  改为「token + 谓词」判定术语（含 `+`/`#`、含数字、全大写、内部有大写字母）。
- **英文取否定分句时丢失系动词**：`The reform is not just about A, but about B` 原会产出残句，
  改为把系动词纳入捕获组（`\1 \3, not just \2`），并补一条规则避免重叠命中。
- **删除句首成分后残句**：中文删除后两侧均为实字时补逗号；英文删除句首成分后自动大写首字母。
- **闸门与语域策略不一致**：闸门原按全部命中计数，导致 `action=review` 的规则使闸门永不可达；
  改为只统计**可自动改写的残留**，评审类命中在报告里单列。
- **短文本字数门禁误报**：26 字的输入删掉「赋能」这类词即超出 ±10%，现对 <200 汉字的文本改用
  绝对字数容差（≤30 字）判定，新增 `test_short_input_uses_absolute_length_tolerance`。

### Evidence（首版实测口径）

用 3 份真实中文课题报告（开题 9 291 字 / 中期 6 455 字 / 结题研究报告 23 703 字，
`--register zh-gov`）实测：三份**全部过闸**，分别应用 8 / 1 / 11 处改写，
保真护栏分别校验 251 / 198 / 532 个受保护片段且**零回滚**，
句长 CV 0.747 / 0.828 / 0.722、段长 CV 0.897 / 1.171 / 0.922 均高于参照带下限。

[Unreleased]: https://github.com/grantleyzyf-spec/deslopkit/compare/v0.1.0...HEAD
[0.1.0]: https://github.com/grantleyzyf-spec/deslopkit/releases/tag/v0.1.0
