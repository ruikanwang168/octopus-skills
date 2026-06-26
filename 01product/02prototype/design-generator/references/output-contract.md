# 输出契约

本 Skill 生成用于产品原型生成的可执行设计系统包。包内文件应保留既有产品的视觉语法、布局行为、组件用法和页面模式，使后续 AI 编程工具生成的原型与源产品保持一致。

## 必需文件

```text
<target-folder>/
  DESIGN.md | design.md
  preview.html
  preview-dark.html
  example.html
  DESIGN_GAPS.md
```

五个文件都必须存在。`DESIGN.md` 是单一事实源。`DESIGN_GAPS.md` 是确认台账，不是下游原型生成的必要输入。

## 输出位置和命名

- 用户指定输出目录时，所有生成文件都保存到该目录。
- 本地源码分析且未指定输出目录时，保存到 `<project-root>/DESIGN`。
- URL-only、screenshot-only 或 brief-only 且没有本地项目根目录时，保存到 `./DESIGN`。
- 只允许一个 Markdown 源文件：`DESIGN.md` 或 `design.md`。沿用已有约定或用户明确文件名；否则默认 `DESIGN.md`。

## DESIGN.md 前置信息

Markdown 文件必须以一个统一 YAML front matter 开头。不要把数据拆成兼容层，也不要在并行字段重复同一设计事实。

```yaml
---
version: 1
language: "<用户或证据语言>"
name: "<真实产品名称>"
summary: "<一段产品特定的设计系统摘要>"

product:
  type: "<观察到或 brief 推导的 archetype key>"
  archetype: "<具体界面语法，不是泛化分类>"
  density: "<观察或文档化的密度>"
  primaryUseCases:
    - <来自源码、URL、截图或 brief 的真实用例>

technology:
  framework:
    name: "<观察到的框架或原型推荐>"
    version: "<观察版本或推荐目标>"
    source: source-derived | user-provided | inferred | recommended-default
  componentLibraries:
    - "<观察到的组件库或自定义系统>"
  targetPrototype:
    type: "<static-html | react | vue | other>"
    recommendation: "<与证据绑定的原型实现建议>"

runtime:
  evidenceMode: source+screenshot | source-only | screenshot-only | url | brief
  observedTheme: "<观察主题或当前默认决策>"
  viewport: "<观察或目标视口>"
  shell: observed | inferred | recommended

tokens:
  colors:
    primary: "<证据支持或已记录推荐值>"
    text: "<证据支持或已记录推荐值>"
    canvas: "<证据支持或已记录推荐值>"
    surface: "<证据支持或已记录推荐值>"
    border: "<证据支持或已记录推荐值>"
  typography:
    baseFontFamily: "<观察或记录的字体栈>"
    body:
      fontSize: "<观察或记录值>"
      fontWeight: "<观察或记录值>"
      lineHeight: "<观察或记录值>"
  spacing:
    md: "<观察或记录值>"
  radius:
    sm: "<观察或记录值>"
  shadow:
    card: "<观察或记录值>"
  motion:
    base: "<观察或记录值>"

layout:
  appShell:
    shellPart:
      dimensionOrColorRole: "<观察或记录值>"
  responsive:
    strategy: "<观察或当前默认>"
    rule: "<响应式处理规则>"

components:
  componentName:
    source: "<真实组件原语或记录的原型原语>"
    variantOrState:
      use: "<真实使用规则>"
      dimensionOrTokenRef: "<观察值或 {tokens.*} 引用>"

pageTemplates:
  - id: "<真实模板 id>"
    name: "<真实产品页面或可复用页面语法>"
    priority: primary
    structure:
      - <真实 section 或区域>
    sampleContent:
      field: "<来自证据或产品领域的真实样例内容>"
    evidence: observed | source-derived | screenshot-calibrated | url-observed | brief-synthesized | inferred
    confidence: high | medium | low

generationRules:
  must:
    - "<证据特定的生成规则>"
  mustNot:
    - "<证据特定的禁止模式>"
  selfCheck:
    - "<证据特定的自检项>"

evidence:
  mode: source+screenshot | source-only | screenshot-only | url | brief
  sources:
    sourceFiles: []
    screenshots: []
    urls: []
    inferredFrom: []
  decisions:
    - field: "<field.path>"
      source: source-derived | screenshot-calibrated | url-observed | user-provided | inferred | recommended-default
      confidence: high | medium | low
      rationale: "<为什么这是当前决策>"
  confidence:
    overall: high | medium | low
    tokens: high | medium | low
    components: high | medium | low
    layout: high | medium | low
    pageTemplates: high | medium | low

briefConsultation:
  required: false
  status: not-required
  proposalSummary: "not-applicable"
  approvedBy: "not-applicable"
  approvedAt: "not-applicable"
  skipReason: "not-applicable"

legacyTokens: []
openQuestions: []
knownLimits: []
assumptions: []
---
```

这个 schema 示例只说明结构，不能把占位文本复制到产物里。不要仅凭本契约推断企业后台 shell、蓝色主色、Element UI、固定 32px 控件、64px 顶栏、240px 侧栏或表格/列表页模板。

### 必需 Front Matter 字段

必需顶层字段：

- `version`、`language`、`name`、`summary`
- `product`、`technology`、`runtime`
- `tokens`、`layout`、`components`、`pageTemplates`、`generationRules`
- `evidence`、`briefConsultation`、`legacyTokens`、`openQuestions`、`knownLimits`、`assumptions`

### 单一事实源

- token 值只放在 `tokens`。
- app shell 尺寸和响应式行为只放在 `layout`。
- 组件样式配方只放在 `components`。
- 页面结构只放在 `pageTemplates`。
- 原型生成约束只放在 `generationRules`。
- brief 模式方向确认只放在 `briefConsultation`。
- 历史值或冲突值只放在 `legacyTokens`。
- 待确认项放在 `openQuestions`，每一项都必须包含 `currentDecision` 或 `fallbackRule`。
- `example.html` 的一次性验证请求不能写进 `DESIGN.md`，只能嵌在 `example.html` 的 `example-generation-input` 中。

使用 `{tokens.colors.primary}` 这样的引用，避免重复字面量。

### 不允许 Unknown

本 Skill 生成的是可用设计规格，不是被动审计。任何后续原型生成所需字段都必须有可执行值。证据无法证明时，选择保守推荐值并记录：

```yaml
evidence:
  decisions:
    - field: "tokens.colors.primary"
      source: recommended-default
      confidence: medium
      rationale: "用户未指定品牌色，采用稳健的企业后台蓝。"
```

不要在 `product`、`technology`、`tokens`、`layout`、`components`、`pageTemplates` 或 `generationRules` 中输出 `unknown`、`unavailable`、`unverified`、占位符或空的必需结构。

## 证据模式逻辑

所有输入使用同一个 schema，只改变证据来源、置信度和默认决策。

### 源码

- 源码决定技术栈、组件库、组件原语、页面模板、token 载体和布局容器。
- 缺失的运行态或响应式细节使用带理由的推荐默认值。

### 截图

- 截图用于校准可见视觉语言、密度、shell 状态、布局和组件外观。
- 从截图推断的值也是可用推荐值，不写 `unknown`；在 `evidence.decisions` 中标为 `screenshot-calibrated` 或 `inferred`。

### URL

- URL/runtime 证据可确认 computed styles、视口、shell 状态和可见交互模式。
- 若没有源码，不要假装观察到框架；`technology` 可以写 `targetPrototype` 推荐。
- `theme-data/theme.json` 这类抓取数据可放在 `evidence.sources.themeData`，但只是候选证据。没有 computed styles、源码、截图或用户纠正支持时，不能把频率值直接提升为 `tokens`。

### 源码 + URL + 截图 + Brief 混合模式

源码、URL、截图、theme data 和用户描述同时存在时，以 `source+screenshot` 作为主证据模式，并在 `runtime.runtimeSources` 或 `evidence.sources` 中记录每类来源。

责任拆分：

- 用户纠正和明确约束决定范围并覆盖冲突。
- URL computed styles 和 active CSS variables 决定当前精确渲染值。
- 源码决定框架、组件库、wrappers、routes 和可复用页面模式。
- 截图校准主题状态、密度、层级和可见组件组合。
- `theme.json` 总结候选 token 和硬编码值；频率影响置信度，不直接成为最终语义角色。

### Brief 模式

- Brief 模式根据产品想法合成连贯、可直接使用的规格。
- 所有关键字段都必须填入推荐默认值和假设。
- Brief 模式必须包含 `briefConsultation.status`，取值为 `approved`、`skipped` 或 `not-required`。
- `approved` 表示用户确认方向；`not-required` 表示原 brief 已明确给出视觉方向、品牌约束、布局、颜色、字体或此前确认的设计决策；`skipped` 只用于用户或环境明确要求非交互、批量、CI、自动化、无人值守、无需提问或跳过确认，并在 `skipReason` 中写明证据。产品定义、PRD、需求文档、流程说明、导航列表和布局草图本身不是合法跳过理由。

### 源码 + 截图

源码说明产品如何实现，截图说明用户实际看到什么。优先级：

```text
用户明确要求
> 图片/URL 中可见运行态视觉
> 源码中已启用样式
> 源码历史变量或候选值
> 合理推荐默认值
```

当前决策写进 `tokens`、`layout`、`components` 或 `pageTemplates`。落选候选放进 `legacyTokens` 或 `openQuestions`，并始终给出当前决策。

## 可读章节

`DESIGN.md` 应保留 10 个章节。章节解释同一份 front matter，不能引入第二套设计语言。

中文标准标题：

1. 使用说明
2. 产品与界面画像
3. 设计原则
4. 设计令牌
5. 布局与应用壳
6. 组件系统
7. 页面模板
8. 交互状态与响应式规则
9. 原型生成规则与自检
10. 证据、限制与默认决策

英文标题仅在用户明确要求英文产物时使用：

1. Usage Guide
2. Product & Interface Profile
3. Design Principles
4. Design Tokens
5. Layout & App Shell
6. Component System
7. Page Templates
8. Interaction States & Responsive Rules
9. Prototype Generation Rules & Self-Check
10. Evidence, Limits & Default Decisions

正文必须与 front matter 一致。第 10 章必须自包含，说明证据摘要、当前默认决策、未确认能力及其默认处理、高影响待确认项摘要。
