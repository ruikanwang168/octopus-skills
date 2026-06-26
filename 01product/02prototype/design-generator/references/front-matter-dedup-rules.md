# 前置信息去重校验规则（统一可执行 schema）

本文件定义 `scripts/validate_design_folder.py` 对 `DESIGN.md` / `design.md` YAML front matter 的重复与冲突检测规则。目标是让 front matter 成为后续原型生成的单一事实源。

## 核心原则

同一个设计事实只允许一个权威位置：

| 信息类型 | 权威位置 |
|---|---|
| 颜色、字体、间距、圆角、阴影、动效 | `tokens.*` |
| 应用壳、内容区、响应式 | `layout.*` |
| 组件来源、样式、使用场景 | `components.*` |
| 页面结构与样例内容 | `pageTemplates` |
| 生成规则、禁止事项、自检 | `generationRules` |
| 历史值、冲突候选 | `legacyTokens` |
| 待确认但不阻塞生成的事项 | `openQuestions` |
| 证据、来源、字段级决策 | `evidence` |

其它位置只能解释或引用，不能重新写一套字面量。

## 规则

### U1 — 关键字段不可为空或 unknown

`product`、`technology`、`tokens`、`layout`、`components`、`pageTemplates`、`generationRules` 中不能出现：

- `unknown`
- `unavailable`
- `unverified`
- `TODO`
- `MUST_REPLACE`
- 空对象或空数组

证据不足时，应写入可执行推荐值，并在 `evidence.decisions` 中标记：

```yaml
source: recommended-default
confidence: medium
rationale: "为什么这个默认值适合后续原型生成"
```

### U2 — token 字面量只能权威存于 `tokens`

组件、布局、页面模板、生成规则引用 token 时应使用：

```yaml
background: "{tokens.colors.primary}"
radius: "{tokens.radius.sm}"
```

不要在多个位置重复写 `#003EB3`、`4px`、`PingFang SC` 等字面量。

### U3 — 布局尺寸只能权威存于 `layout`

顶栏高度、侧栏宽度、内容区偏移、响应式策略应写在 `layout`。页面模板可以写“使用 appShell”，不要重复 `64/240/80`。

### U4 — 页面结构只能权威存于 `pageTemplates`

`pageTemplates` 是 `example.html` 的主要输入。不要再另建平行的 `pagePatterns` 或 prose-only 页面骨架。

### U5 — 生成规则只能权威存于 `generationRules`

必须遵守、禁止事项、自检清单分别写入：

```yaml
generationRules:
  must: []
  mustNot: []
  selfCheck: []
```

正文第 9 章只解释这些规则，不新增另一套。

### U6 — 冲突值不得污染权威字段

当前采用值写在 `tokens` / `layout` / `components` / `pageTemplates`。落选候选写入：

- `legacyTokens`
- `openQuestions`
- `evidence.decisions`

每个 `openQuestions` 项都必须有 `currentDecision` 或 `fallbackRule`。

### U7 — 推荐默认值必须有理由

凡是 `source: recommended-default`、`source: inferred` 或低置信度决策，都应写入 `evidence.decisions`，包含：

- `field`
- `source`
- `confidence`
- `rationale`

## 旧字段适配

脚本中存在 `front_matter_schema.normalize_design_data()`，会把统一 schema 投影成旧渲染器可读路径，例如：

- `tokens.colors` → `colors`
- `tokens.radius` → `rounded`
- `layout` → `layoutRules`
- `generationRules` → `aiGenerationRules` / `forbiddenRules` / `selfCheck`
- `openQuestions` → `unresolvedItems`

这是运行时适配层，不代表新产物应继续写旧字段。
