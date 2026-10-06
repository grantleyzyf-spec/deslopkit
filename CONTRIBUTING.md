# 贡献指南（Contributing to deslopkit）

感谢你愿意为 deslopkit 做贡献！本项目是一个**语域感知 + 保真护栏**的中英双语
文本去 AI 化工具包。请在动手之前阅读本指南。

> **统一口径**：deslopkit 的目标是**降低模板化表达与机器痕迹**，并让所有改动
> **可复算、可审计、可验证保真**。我们**不承诺**任何第三方检测器（AI 检测、
> 查重、抄袭检测等）的结果，也**不接受**以「绕过检测」为目的的贡献。

## 1. 搭建开发环境

```bash
git clone https://github.com/grantleyzyf-spec/deslopkit
cd deslopkit

# 建议使用虚拟环境
python -m venv .venv
source .venv/bin/activate          # Windows: .venv\Scripts\activate

# 安装带开发依赖的可编辑版本
python -m pip install -e ".[dev]"
# 或等价地
make install
```

运行测试与检查：

```bash
make test     # pytest -q
make lint     # ruff check src tests
make fmt      # ruff format src tests
```

## 2. 如何新增一条规则

规则是纯数据文件，位于 `src/deslopkit/rules/*.json`。**新增规则时，向对应语言/
语域的文件追加一个条目即可**，不要为了单条规则去改引擎代码。

每个规则条目至少包含以下字段：

| 字段 | 类型 | 说明 |
| --- | --- | --- |
| `id` | string | 全局唯一标识，建议 `lang-register-短名`，如 `zh-gongwen-xu-shi` |
| `lang` | string | 语言，`zh` 或 `en` |
| `register` | string | 语域，如 `zh_gongwen` / `zh_academic` / `zh_forum` / `en_academic` / `en_essay` |
| `category` | string | 类别，如 `connective` / `filler` / `template` / `hedging` |
| `pattern` | string | 匹配模式（正则或字面量），需能以 `re` 编译并在规则加载时校验 |
| `severity` | string | 严重度，`info` / `low` / `medium` / `high` |
| `message` | string | 面向人的说明，解释为什么该表达是机器痕迹 |
| `fix_hint` | string | 修复建议（可以有指导性，但不要伪装成自动改写承诺） |
| `replacement` | string \| null | 可选的默认替换文本；为 `null` 表示只提示不替换 |
| `protect` | bool | 是否受保真护栏保护（命中片段若含数字/专名/引文，禁止自动改动） |

### 新增规则的硬性要求

1. **必须附带测试用例**：新增或修改规则必须同时在 `tests/` 下补充覆盖用例，
   至少验证「命中」「不命中（负例）」「保真护栏生效」三种情形。
2. **不得引入第三方运行时依赖**：核心规则与引擎保持零第三方依赖。
   正则/词表/纯标准库可用的方案优先。
3. **不得削弱保真护栏默认行为**：任何改动都不得让默认配置下的数字、专名、
   引文被静默修改。
4. **正例与负例都要给**：只测命中的 PR 会被要求补负例，避免规则过度触发。

规则 JSON 结构示例：

```json
{
  "id": "zh-gongwen-xu-shi",
  "lang": "zh",
  "register": "zh_gongwen",
  "category": "template",
  "pattern": "综上所述",
  "severity": "low",
  "message": "‘综上所述’是公文模板化连接词，连续出现会显得机械。",
  "fix_hint": "尝试用具体结论句替代泛化的总结连接词。",
  "replacement": null,
  "protect": true
}
```

## 3. 如何新增一个语域画像

语域画像定义「某类文本用哪套规则、阈值如何」。新增一个语域时：

1. 在语域画像注册处（`src/deslopkit/registers/`，或等价模块）声明语域标识、
   启用的规则文件、以及该语域下的阈值配置。
2. 在 `src/deslopkit/rules/` 下新增或复用对应的规则 JSON。
3. 在 `tests/` 中补充该语域的加载测试与端到端用例。
4. 在文档（`docs/`）与 `CHANGELOG.md` 的 `Unreleased` 一节记录新增语域。

## 4. 提交信息规范

本项目采用 [Conventional Commits](https://www.conventionalcommits.org/)：

```
<type>(<scope>): <subject>
```

常用 `type`：

- `feat`：新功能（新规则、新语域、新指标）
- `fix`：修复
- `docs`：文档
- `test`：测试
- `refactor`：重构（不改变行为）
- `chore`：杂项（构建、依赖、CI）
- `perf`：性能

示例：

```
feat(rules): 新增中文网帖语气词规则
fix(fidelity): 修正引号内数字被误判为待改写
test(zh-gongwen): 补充 ‘综上所述’ 的负例
```

## 5. Pull Request 检查清单

提交 PR 前请逐项确认：

- [ ] 测试通过：`make test`
- [ ] Lint 通过：`make lint`
- [ ] 新增/修改的规则带测试用例（含正例与负例）
- [ ] 文档已更新（`docs/`、`CHANGELOG.md` 的 `Unreleased`）
- [ ] 未新增任何第三方**运行时**依赖
- [ ] 未改动保真护栏的默认行为
- [ ] 提交信息符合 Conventional Commits
- [ ] 变更不涉及任何「绕过检测」「保证通过检测」类诉求

感谢你的贡献！
