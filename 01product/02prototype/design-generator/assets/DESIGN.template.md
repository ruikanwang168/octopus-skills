---
version: 1
language: "{{LANGUAGE}}"
name: {{PROJECT_NAME_YAML}}
summary: "MUST_REPLACE_WITH_EXECUTABLE_DESIGN_SYSTEM_SUMMARY"

product:
  type: "MUST_REPLACE_PRODUCT_TYPE"
  archetype: "MUST_REPLACE_INTERFACE_ARCHETYPE_DESCRIPTION"
  density: "MUST_REPLACE_DENSITY"
  primaryUseCases:
    - "MUST_REPLACE_PRIMARY_USE_CASE"

technology:
  framework:
    name: "MUST_REPLACE_FRAMEWORK_OR_PROTOTYPE_RECOMMENDATION"
    version: "MUST_REPLACE_VERSION_OR_RECOMMENDED_TARGET"
    source: "source-derived | user-provided | inferred | recommended-default"
  componentLibraries:
    - "MUST_REPLACE_COMPONENT_LIBRARY_OR_PROTOTYPE_PRIMITIVE"
  targetPrototype:
    type: "static-html"
    recommendation: "MUST_REPLACE_PROTOTYPE_IMPLEMENTATION_RECOMMENDATION"

runtime:
  evidenceMode: "source+screenshot | source-only | screenshot-only | url | brief"
  observedTheme: "MUST_REPLACE_THEME_OR_DEFAULT_DECISION"
  viewport: "MUST_REPLACE_VIEWPORT_OR_DEFAULT_DECISION"
  shell: "observed | inferred | recommended"

tokens:
  colors:
    primary: "MUST_REPLACE_PRIMARY_COLOR"
    primaryHover: "MUST_REPLACE_PRIMARY_HOVER_COLOR"
    primaryActive: "MUST_REPLACE_PRIMARY_ACTIVE_COLOR"
    onPrimary: "MUST_REPLACE_ON_PRIMARY_COLOR"
    text: "MUST_REPLACE_TEXT_COLOR"
    textStrong: "MUST_REPLACE_STRONG_TEXT_COLOR"
    textMuted: "MUST_REPLACE_MUTED_TEXT_COLOR"
    canvas: "MUST_REPLACE_CANVAS_COLOR"
    surface: "MUST_REPLACE_SURFACE_COLOR"
    surfaceMuted: "MUST_REPLACE_MUTED_SURFACE_COLOR"
    border: "MUST_REPLACE_BORDER_COLOR"
    borderLight: "MUST_REPLACE_LIGHT_BORDER_COLOR"
    success: "MUST_REPLACE_SUCCESS_COLOR"
    warning: "MUST_REPLACE_WARNING_COLOR"
    danger: "MUST_REPLACE_DANGER_COLOR"
    shellTopbar: "MUST_REPLACE_SHELL_TOPBAR_COLOR"
    shellSidebar: "MUST_REPLACE_SHELL_SIDEBAR_COLOR"
  typography:
    baseFontFamily: "MUST_REPLACE_FONT_STACK"
    heading:
      fontSize: "MUST_REPLACE_HEADING_SIZE"
      fontWeight: "MUST_REPLACE_HEADING_WEIGHT"
      lineHeight: "MUST_REPLACE_HEADING_LINE_HEIGHT"
    body:
      fontSize: "MUST_REPLACE_BODY_SIZE"
      fontWeight: "MUST_REPLACE_BODY_WEIGHT"
      lineHeight: "MUST_REPLACE_BODY_LINE_HEIGHT"
    caption:
      fontSize: "MUST_REPLACE_CAPTION_SIZE"
      fontWeight: "MUST_REPLACE_CAPTION_WEIGHT"
      lineHeight: "MUST_REPLACE_CAPTION_LINE_HEIGHT"
    button:
      fontSize: "MUST_REPLACE_BUTTON_SIZE"
      fontWeight: "MUST_REPLACE_BUTTON_WEIGHT"
      lineHeight: 1
  spacing:
    xs: "MUST_REPLACE_SPACING_XS"
    sm: "MUST_REPLACE_SPACING_SM"
    md: "MUST_REPLACE_SPACING_MD"
    lg: "MUST_REPLACE_SPACING_LG"
    xl: "MUST_REPLACE_SPACING_XL"
    section: "MUST_REPLACE_SECTION_SPACING"
  radius:
    sm: "MUST_REPLACE_RADIUS_SM"
    md: "MUST_REPLACE_RADIUS_MD"
    lg: "MUST_REPLACE_RADIUS_LG"
    pill: 999
  shadow:
    card: "MUST_REPLACE_CARD_SHADOW_OR_NONE"
    shell: "MUST_REPLACE_SHELL_SHADOW_OR_NONE"
  motion:
    fast: "MUST_REPLACE_FAST_MOTION"
    base: "MUST_REPLACE_BASE_MOTION"

layout:
  appShell:
    topbar:
      height: "MUST_REPLACE_TOPBAR_HEIGHT"
      background: "{tokens.colors.shellTopbar}"
      textColor: "{tokens.colors.onPrimary}"
    sidebar:
      width: "MUST_REPLACE_SIDEBAR_WIDTH"
      collapsedWidth: "MUST_REPLACE_SIDEBAR_COLLAPSED_WIDTH"
      background: "{tokens.colors.shellSidebar}"
      activeBackground: "MUST_REPLACE_SIDEBAR_ACTIVE_BACKGROUND"
      activeIndicator: "MUST_REPLACE_SIDEBAR_ACTIVE_INDICATOR"
    content:
      background: "{tokens.colors.canvas}"
      leftOffset: "MUST_REPLACE_CONTENT_LEFT_OFFSET"
  responsive:
    strategy: "MUST_REPLACE_RESPONSIVE_STRATEGY"
    rule: "MUST_REPLACE_RESPONSIVE_DEFAULT_RULE"

components:
  button:
    source: "MUST_REPLACE_BUTTON_SOURCE"
    primary:
      use: "MUST_REPLACE_PRIMARY_BUTTON_USE"
      height: "MUST_REPLACE_BUTTON_HEIGHT"
      background: "{tokens.colors.primary}"
      hoverBackground: "{tokens.colors.primaryHover}"
      textColor: "{tokens.colors.onPrimary}"
      radius: "{tokens.radius.sm}"
  input:
    source: "MUST_REPLACE_INPUT_SOURCE"
    height: "MUST_REPLACE_INPUT_HEIGHT"
    border: "{tokens.colors.borderLight}"
    placeholderColor: "{tokens.colors.textMuted}"
  table:
    source: "MUST_REPLACE_TABLE_SOURCE"
    headerTextColor: "{tokens.colors.textStrong}"
    bodyTextColor: "{tokens.colors.text}"
  container:
    source: "MUST_REPLACE_CONTAINER_SOURCE"
    background: "{tokens.colors.surface}"
    radius: "{tokens.radius.lg}"

pageTemplates:
  - id: "MUST_REPLACE_TEMPLATE_ID"
    name: "MUST_REPLACE_TEMPLATE_NAME"
    priority: primary
    appliesTo:
      - "MUST_REPLACE_SCENARIO"
    structure:
      - "MUST_REPLACE_SECTION"
    components:
      - button
      - table
    rules:
      - "MUST_REPLACE_TEMPLATE_RULE"
    sampleContent:
      title: "MUST_REPLACE_SAMPLE_TITLE"
    evidence: "observed | source-derived | screenshot-calibrated | url-observed | brief-synthesized | inferred"
    confidence: "high | medium | low"

generationRules:
  must:
    - "必须使用 tokens 中定义的颜色、字号、间距和圆角。"
    - "MUST_REPLACE_GENERATION_MUST_RULE"
  mustNot:
    - "不要把 legacyTokens 当作推荐值。"
    - "MUST_REPLACE_GENERATION_FORBIDDEN_RULE"
  selfCheck:
    - "是否使用 tokens 中的权威值，而不是重新发明颜色或尺寸？"
    - "MUST_REPLACE_SELF_CHECK_ITEM"

evidence:
  mode: "source+screenshot | source-only | screenshot-only | url | brief"
  priority:
    - "用户明确要求"
    - "图片/URL 可见运行态"
    - "源码已启用样式"
    - "推荐默认值"
  sources:
    sourceFiles: []
    screenshots: []
    urls: []
    inferredFrom: []
  decisions:
    - field: "MUST_REPLACE_FIELD_PATH"
      source: "source-derived | screenshot-calibrated | url-observed | user-provided | inferred | recommended-default"
      confidence: "high | medium | low"
      rationale: "MUST_REPLACE_DECISION_RATIONALE"
  confidence:
    overall: "MUST_REPLACE_OVERALL_CONFIDENCE"
    tokens: "MUST_REPLACE_TOKEN_CONFIDENCE"
    components: "MUST_REPLACE_COMPONENT_CONFIDENCE"
    layout: "MUST_REPLACE_LAYOUT_CONFIDENCE"
    pageTemplates: "MUST_REPLACE_TEMPLATE_CONFIDENCE"
    darkMode: "MUST_REPLACE_DARK_MODE_CONFIDENCE"
    mobile: "MUST_REPLACE_MOBILE_CONFIDENCE"

briefConsultation:
  required: "true | false"
  status: "approved | skipped | not-required"
  proposalSummary: "MUST_REPLACE_BRIEF_DIRECTION_PROPOSAL_SUMMARY_OR_NOT_APPLICABLE"
  approvedBy: "user | explicit-brief | non-interactive | batch-generation | ci | automation | unattended | previous-design | not-applicable"
  approvedAt: "MUST_REPLACE_ISO8601_TIME_OR_NOT_APPLICABLE"
  skipReason: "MUST_REPLACE_ONLY_WHEN_STATUS_IS_SKIPPED_WITH_EXPLICIT_NON_INTERACTIVE_OR_USER_SKIP_CONFIRMATION_EVIDENCE"

legacyTokens: []

openQuestions:
  - id: "MUST_REPLACE_OPEN_QUESTION_ID"
    question: "MUST_REPLACE_QUESTION"
    currentDecision: "MUST_REPLACE_CURRENT_DECISION"
    fallbackRule: "MUST_REPLACE_FALLBACK_RULE"
    impact: "MUST_REPLACE_IMPACT"

knownLimits:
  - "MUST_REPLACE_LIMIT_WITH_DEFAULT_HANDLING"

assumptions:
  - "MUST_REPLACE_ASSUMPTION_FOR_RECOMMENDED_DEFAULTS"
---

## 1. 使用说明

本文件是当前产品的可执行设计规范，用于指导后续产品原型设计和 vibe coding。后续生成页面时，应直接读取 YAML front matter 中的 `tokens`、`layout`、`components`、`pageTemplates` 和 `generationRules`。

## 2. 产品与界面画像

说明 `product`、`technology` 和 `runtime` 中的产品类型、界面骨架、密度、技术栈或原型实现建议。

## 3. 设计原则

说明该产品的视觉气质、信息密度、内容优先级、适合与不适合的页面风格。

## 4. 设计令牌

解释 `tokens` 中的颜色、字体、间距、圆角、阴影和动效。正文可以用表格展示值，但不得新增 front matter 中没有的第二套 token。

## 5. 布局与应用壳

解释 `layout` 中的应用壳、内容区、响应式策略和默认处理方式。

## 6. 组件系统

解释 `components` 中的组件来源、使用场景、样式配方、推荐组合和禁止事项。

## 7. 页面模板

解释 `pageTemplates` 中的页面结构、适用场景、组件组合和示例内容。`pageTemplates` 是页面语法，不是代码预设模板。`example.html` 的具体样例输入不得写回本文件，应在生成的 `example.html` 元数据中记录。

## 8. 交互状态与响应式规则

说明已确认状态、推荐默认状态和未观察能力的默认处理方式。

## 9. 原型生成规则与自检

解释 `generationRules.must`、`generationRules.mustNot` 和 `generationRules.selfCheck`。

## 10. 证据、限制与默认决策

说明 `evidence`、`briefConsultation`、`legacyTokens`、`openQuestions`、`knownLimits` 和 `assumptions`。每个待确认项都必须有当前默认决策，不能阻塞后续原型生成。Brief mode 必须说明设计方向是否已由用户确认，或为什么可跳过确认。
