# Pull Request

## 变更说明

<!-- 简要描述这个 PR 做了什么、为什么。关联的 Issue：Fixes #___ -->

## 类型

- [ ] 新功能（新规则 / 新语域 / 新指标）
- [ ] 缺陷修复
- [ ] 文档
- [ ] 重构 / 性能
- [ ] 构建 / CI / 杂项

## 检查清单

- [ ] 测试通过（`make test` / `pytest -q`）
- [ ] Lint 通过（`make lint` / `ruff check src tests`）
- [ ] 新增或修改的规则带测试用例（含正例与负例）
- [ ] 相关文档已更新（`docs/`、`CHANGELOG.md` 的 `Unreleased`）
- [ ] 未新增任何第三方**运行时**依赖（核心保持零依赖）
- [ ] 未改动保真护栏（Fidelity Guard）的默认行为
- [ ] 提交信息符合 [Conventional Commits](https://www.conventionalcommits.org/)
- [ ] 变更不涉及任何「绕过 / 对抗检测器」类诉求

## 备注

<!-- 需要 reviewer 特别注意的点、已知限制、后续计划等 -->
