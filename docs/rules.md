# 规则格式与贡献指南

规则库是两份 JSON：`src/deslopkit/rules/zh.json` 与 `src/deslopkit/rules/en.json`。
新增一条规则 = 一个 JSON 对象 + 一个测试用例。不需要改 Python 代码（除非要新增**策略**）。

## 1. 一条规则长什么样

```json
{
  "id": "zh.jar.001",
  "lang": "zh",
  "registers": ["all"],
  "category": "jargon",
  "pattern": "赋能",
  "flags": "",
  "severity": "high",
  "action": "rewrite",
  "strategy": "replace",
  "replacement": "助力",
  "skip_quoted": true,
  "message": "“赋能”是典型的 AI 时代公文黑话。",
  "fix_hint": "换成具体动词（助力/支撑/推动），并补出具体动作或作用点。"
}
```

| 字段 | 取值 | 说明 |
|---|---|---|
| `id` | `zh.<类>.<序号>` / `en.<类>.<序号>` | 全局唯一，测试会断言不重复 |
| `lang` | `zh` / `en` | 决定默认加载哪份规则库 |
| `registers` | `["all"]` 或具体语域列表 | 见 `register.py`；只列出的语域会命中 |
| `category` | 见下表 | 决定语域策略与闸门归组 |
| `pattern` | Python 正则 | 用 `re` 编译；`flags` 支持 `i` / `m` |
| `severity` | `high` / `medium` / `low` | `high` 用于 `audit --exit-code` 判定 |
| `action` | `rewrite` / `review` | `rewrite` 必须有 `strategy`；`review` 只进报告 |
| `strategy` | `neg_pivot` / `replace` / `delete` / `nominal` / `punct` / `signpost` / `jargon` / `filler` / `lyric` / `parallel_triplet` | 由 `rewriters.py` 实现 |
| `replacement` | 字串，可用 `\1`…`\9` 反向引用 | `delete` 策略下为空串 |
| `skip_quoted` | `true`（默认） | 命中落在 `“引号”`、`《书名号》`、`"引号"` 内时跳过（保护引文） |
| `message` | 一句话说明「这是什么痕迹」 | 出现在报告里 |
| `fix_hint` | 一句话说明「怎么改」 | 出现在报告与 `--verbose` 输出 |

### 类别（category）

| 类别 | 含义 | 典型例子 |
|---|---|---|
| `negation_pivot` | 翻案腔：先立误解再推翻 | 不是A，而是B / is not just A, but B |
| `jargon` | 黑话与宣传腔 | 赋能 / 抓手 / delve into / leverage |
| `nominalization` | 名词化、纸面化 | 具有一定的参考价值 / 进行描述统计 |
| `signposting` | 路标词 | 其一是 / 首先其次 / In conclusion |
| `parallelism` | 同构排比（三项以上） | 缺乏A，缺乏B，缺乏C |
| `abstract_lyric` | 抽象抒情、升华 | 彰显…价值 / 注入新动能 |
| `punctuation` | 标点用法 | 修辞破折号 `——` / 提示性冒号 |
| `filler` | 空泛填充 | 值得注意的是 / it goes without saying |
| `english_cliche` | 英文陈词滥调 | In today's fast-paced world |

### 策略（strategy）

| 策略 | 行为 | 是否自动 |
|---|---|---|
| `neg_pivot` | 把否定分句降为句末限定（`Y，而不是X`），必要时补系动词 | ✓（标 `needs_review`） |
| `replace` | 按 `replacement` 替换（支持反向引用） | ✓ |
| `delete` | 删除；若后接标点一并吞掉，中文两侧为实字时补一个逗号 | ✓ |
| `nominal` / `punct` | 与 `replace` 同，语义上归入名词化/标点类 | ✓ |
| `signpost` / `jargon` / `filler` / `lyric` / `parallel_triplet` | 默认仅提示（需人工判断上下文） | ✗ |

## 2. 新增一条规则（四步）

```bash
# 1) 写规则：追加到 rules/zh.json（或 en.json）的 rules 数组末尾
# 2) 写测试：在 tests/test_rules_rewriters.py 加一个用例
# 3) 跑门禁
make test && make lint
# 4) 提 PR：说明「这条痕迹为什么是痕迹」「为什么不会误伤」并附真实文本片段
```

测试至少覆盖两点：**能命中**（正例）与**不误伤**（反例，例如出现在引号内、
或属于国标本义用法时不应命中）。

## 3. 规则设计的四条纪律

1. **宁可漏，不可误伤。** 一条会误改公文合规表达的规则，比漏掉一处痕迹的代价大得多。
   拿不准就把 `action` 设为 `review`。
2. **改写必须是模板展开。** 需要「理解上下文」才能做的改写，一律不要写成 `rewrite`，
   留给人工判断（这是本项目与 LLM 改写项目的分界）。
3. **不要吞掉受保护片段。** 若你的规则会改动数字、书名、引号内术语，
   保真护栏会回滚它并在报告里记为 `rejected`——那不是 bug，是护栏在工作。
   如果你的规则确实需要改动这类片段，请改规则，而不是改护栏。
4. **专有名词（机构名、地名、人名）不要硬编码在规则里。**
   用 `--keep` / `--keep-from` 交给使用者声明。

## 4. 新增一套语域

在 `register.py` 的 `REGISTERS` 里加一个 `RegisterProfile`：

* `auto_fix` / `review_only` / `disabled`：类别策略；
* `gate`：处理后必须清零的**可自动改写**残留类别；
* `sent_cv_min` / `para_cv_min` / `short_sent_ratio_min`：参照带（请按 `docs/metrics.md` §3 自建并附证据）；
* 在 `detect_register()` 里补判定关键词。

## 5. 两个已踩过的坑（别再踩）

* **机构名自动抽取 → 保真误报。** `[\u4e00-\u9fff]{2,12}(?:大学|学院|小学|…)` 会把
  「人工智能赋能中小学」整段吞成机构名，导致正常改写被回滚。已移除，改由用户 `--keep` 声明。
* **把普通英文单词当受保护片段 → 英文改写全废。** 首次实现用宽正则保护拉丁词，
  实测英文样本 5/5 改写被回滚。现改为「token + 谓词」：含 `+`/`#`、含数字、全大写、
  或内部有大写字母（驼峰）才算术语。
