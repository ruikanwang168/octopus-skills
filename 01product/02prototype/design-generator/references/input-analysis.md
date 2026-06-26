# 输入分析

## 证据模式选择

每次工作只选择一个主证据模式：

- **Source + screenshot mode**：源码加截图或页面抓取；两者一致时保真度最高。
- **Source-only mode**：只有本地源码路径或项目目录，没有截图。
- **Screenshot-only mode**：只有截图，没有源码或 live DOM。
- **URL mode**：在线网站、本地 dev URL 或已抓取 HTML。
- **Brief mode**：只有产品想法、功能概念或工作流描述。

如果用户提供既有产品并要求新增页面，使用最强可用的提取模式。既有产品的设计系统仍是事实源。

当源码、URL、截图、`theme-data/` 和用户描述同时存在时，以 `source+screenshot` 为主模式，把 URL/runtime capture、截图、`theme.json` 和用户描述作为证据层。不要因为存在 URL 就切换为 URL mode。

## 证据优先级

### 通用优先级

优先使用最强证据：

1. 用户明确目标约束和纠正。
2. live URL 或本地渲染 UI 的 runtime computed styles、DOM 和 CSS variables。
3. 源码 tokens、组件定义、布局 wrappers、routes 和 active theme files。
4. 用户提供的截图或页面抓取。
5. 抓取的 `theme.json` 频率统计和 CSS variable 清单。
6. 用户 brief、业务上下文和产品术语。
7. 从重复视觉模式中做出的保守推断。

重复信号优先于一次性装饰细节。

源码或 computed styles 可用时，不要用截图决定精确颜色、字号、间距、阴影或圆角。截图用于识别 active runtime theme、layout state、page structure、density、component composition、content hierarchy 和 conflicts。截图观察到的重要决策，应尽量追溯到源码 selector、变量、组件、DOM 或 computed styles。

把抓取到的 `theme.json` 当候选池，不当权威设计系统。它可以帮助发现重复硬编码颜色、CSS variables、字体栈、间距、圆角、阴影和动效值。只有当某个值被 computed styles、源码证据、重复截图或 `evidence.decisions` 中的明确当前决策支持时，才提升到 `tokens`。落选候选和 inactive values 放进 `legacyTokens` 或 `openQuestions`。

shell chrome 必须显式且有证据：

- product primary color、top navigation background、tags/tab background、sidebar surface 和 content canvas 是不同角色。
- 在源码支撑模式下，top-nav height、sidebar expanded width、sidebar collapsed width 和 tags height 应使用源码或 computed-style 值。
- 截图可以确认当前 shell 状态，但不要用粗略截图测量覆盖精确源码尺寸，除非记录真实冲突。
- 用户明确纠正的主色或 top-navigation color 会覆盖源码/截图推断；若证据不一致，保留为已记录冲突。

### Brief 模式

使用最强意图信号：

1. 用户 brief、目标用户、业务上下文和明确约束。
2. 同项目既有产品家族或品牌约束。
3. 用户选择的 benchmark 产品或语料示例。
4. 适合该品类的有理由默认值。

不要让 benchmark 盖过用户自身产品需求。

## 证据包

写 `DESIGN.md` 前，先整理一个紧凑的内部 evidence packet。相关内容写入统一 front matter、第 2 章（产品与界面画像）、第 9 章（原型生成规则）和第 10 章（证据、限制与默认决策）。

| 字段 | 用途 |
|---|---|
| `language` | 先看用户要求；否则从产品 UI、截图、路由标签、源码注释、领域术语和目标用户推断。中文项目使用 `zh-CN`，面向人读的文档写简体中文。 |
| `mode` | `source+screenshot`、`source-only`、`screenshot-only`、`url` 或 `brief`。 |
| `evidence.confidence` | 后续原型使用的 high / medium / low 置信度。 |
| `sources` | 源码、URL、截图或 brief 假设。 |
| `runtime` | 观察到的主题、shell 状态、视口、导航状态、内容区域。 |
| `technology.framework` | React、Vue、Angular、Svelte、plain HTML 或原型实现推荐。 |
| `technology.styleSystem` | CSS variables、SCSS、Tailwind、CSS modules、styled-components 等。 |
| `technology.componentLibraries` | Ant Design、Element UI、MUI、Radix、Bootstrap、custom 等。 |
| `components` | 源组件原语和未来原型组件配方。 |
| `pageTemplates` | 发现或合成的可复用页面模板。 |
| `legacyTokens` / `openQuestions` | 备用主题、legacy surfaces、源码冲突，并带当前决策。 |

如果存在 URL 证据包，将其作为证据记录，而不是作为单独输出产物：

```yaml
runtime:
  evidenceMode: source+screenshot
  runtimeSources:
    urls:
      - "https://example.com/dashboard"
    themeData:
      path: "./theme-data/theme.json"
      role: "candidate-token-frequency"
    screenshots:
      - "./theme-data/screenshot.png"

evidence:
  sources:
    sourceFiles: []
    urls: []
    screenshots: []
    themeData:
      path: "./theme-data/theme.json"
      summaryPath: "./theme-data/url-theme-evidence.json"
      role: "candidate-token-frequency"
    userBrief:
      role: "scope-and-corrections"
```

最终包不要求 `summaryPath` 存在；除非用户要求保留调试证据，否则它只是内部分析辅助。

## 本地源码路径工作流

### 需要检查的内容

- App shell 文件：导航、布局 wrappers、route containers。
- Token 载体：`tailwind.config.*`、主题文件、CSS variables、SCSS variables、design-token JSON、组件库 overrides。
- 全局样式：reset、typography、body background、focus rules、responsive breakpoints。
- 可复用原语：button、input、card、badge、modal、drawer、table、tabs、sidebar、topbar。
- 页面示例：dashboard、table management、tree/table management、master/detail、detail、form、settings、auth、editor/workbench、modal 或 drawer flows。
- 资产线索：fonts、icons、illustrations、screenshots、Storybook stories。

### 建议搜索模式

- `rg -n "theme|token|palette|color|font|shadow|radius|spacing|var\\(|:root|tailwind|typography"`
- `rg -n "button|input|table|drawer|modal|sidebar|header|topbar|layout|container|shell|page"`
- `rg --files | rg "story|stories|screenshot|preview|theme|token|layout|page|screen"`

### 提取目标

- 找到真实 hex 值、字体栈、圆角值、阴影、间距和动效。
- 区分基础组件和路由专用 UI。
- 判断产品是 marketing-led、dashboard-led、admin-led、editor-led、docs-heavy 还是 consumer productivity。
- 记录未来 Agent 必须保留的真实实现语法：wrappers、layout names、component libraries、utility systems 和命名约定。
- 识别 app shell、page shell 和重复页面模式。高保真原型指导不能只有 tokens。
- 将源组件原语映射到原型组件，例如 design-system Button、AntD Table、Element UI `el-table`、自定义 `TopSearch`、项目 drawer wrapper，或源项目真实使用的 native HTML。

### 源码对齐规则

- 优先使用观察值，而不是更好看的推断值。
- 保留框架和组件库，例如 Element UI、Tailwind、Chakra、Radix、Ant Design 或项目专用 wrappers。
- 保留密度、平台语气和术语。
- 除非明确要求，不要重塑品牌。
- legacy 和新 surface 共存时，聚焦用户要求区域，并在 `DESIGN_GAPS.md` 和 `DESIGN.md` 第 10 章记录范围。
- 多主题或多 shell 共存时，若截图或 computed styles 可识别 active runtime state，就选它。备用主题放入 `DESIGN_GAPS.md` 或第 10 章，不作为主规则。

## 页面模式分类

使用可复用 pattern name 分类代表性界面。只包含源码、截图、URL 证据或 brief 支持的模式。

- `app-shell`：全局导航、持久侧栏、路由标签、内容框架。
- `marketing-page`：导航、hero、proof、feature、pricing、CTA、footer。
- `dashboard-overview`：指标、图表、筛选、近期活动。
- `table-management`：搜索/筛选区、标题/操作行、表格/列表、分页。
- `tree-table-management`：搜索/筛选区、标题/操作行、左侧树或分类面板、右侧表格、分页。
- `master-detail`：列表或树加详情面板。
- `form-create-edit`：表单分组、校验、sticky footer actions。
- `settings-page`：分组设置、tabs、save/cancel 操作。
- `editor-workbench`：工具栏、侧栏、画布/编辑器、检查器、状态区。
- `data-analysis-canvas`：查询控件、图表/表格区、检查器或配置面板。
- `card-list-gallery`：筛选、卡片 grid/list、状态/操作 chips。
- `auth-flow`：登录、重置、2FA、SSO、租户选择。
- `detail-profile`：头部摘要、元数据、tabs、活动/历史。
- `wizard-stepper`：步骤导航、表单/内容面板、next/back 操作。
- `modal-drawer-flow`：dialog/drawer 尺寸、scrim、分区、footer actions。

## 在线网站 URL 工作流

### 需要捕获

- 桌面 hero 或 app shell。
- 一个内页或二级 section，不只首页。
- 可用时捕获列表、表格、dashboard、pricing、docs 或内容密集状态。
- 表单或输入状态。
- 可见时捕获 modal、drawer、dropdown 或 secondary panel。
- 营销站 footer 或最终 CTA。
- 至少一个窄视口状态。

### 需要检查

- computed colors、type、spacing、width constraints 和 radius。
- hover、focus、active、selected、disabled 状态。
- 页面家族之间重复的布局节奏。
- URL 代表 marketing pages、logged-in app surfaces、docs 还是混合 surface。
- 可揭示组件映射、shell selector 或页面模式的 DOM 和 CSS variable 名称。

### 抓取主题数据包

用户提供 URL capture 文件夹时，可能形如：

```text
theme-data/
  theme.json
  meta.json
  screenshot.png
  responsive/
  sections/
```

写 `DESIGN.md` 前先运行：

```bash
python3 scripts/extract_url_theme_evidence.py /absolute/path/to/theme-data
```

脚本输出候选证据 JSON。只用于内部 token lockup 和冲突分析，默认不要复制到必需输出包。

字段解释：

- `cssVariables`：页面已有变量时，是高价值命名证据。
- `colors.*`：按频率排序的候选值，可用于发现硬编码颜色，但不能单独决定最终语义角色。
- `typography`、`spacing`、`radius`、`shadow`、`motion`：观察到的候选尺度，需要再做语义分组。
- `screenshotInventory`：runtime layout、density 和 responsive behavior 的覆盖证据。
- `semanticColorHints`：仅为建议；必须经 DOM/computed styles、源码、截图或明确决策确认后，才能提升到 `tokens`。

### 源码 + URL + 截图 + Brief 混合工作流

所有证据类型都存在时，每个字段只保留一个当前决策：

| 决策区域 | 首选证据 | 说明 |
|---|---|---|
| 当前精确颜色、字体、间距、圆角 | URL computed styles 和 active CSS variables | computed styles 不可用时，截图只用于校准。 |
| 框架、组件库、wrappers、routes | 源码 | URL DOM 可能提示组件映射，但源码拥有实现语法。 |
| 主题状态、密度、层级、组件组合 | 截图和页面抓取 | 不要覆盖 computed-style 精确值，除非记录冲突。 |
| 产品范围、业务术语、页面家族重点 | 用户描述 | 用户明确纠正高于其它证据。 |
| 硬编码 token 候选池 | `theme.json` summary | 频率影响置信度，但永远不能单独成为最终角色。 |

证据冲突时，把当前值写进 `tokens`、`layout`、`components` 或 `pageTemplates`，把落选候选记录到 `legacyTokens`、`openQuestions` 或低置信度 `evidence.decisions`。

### 兜底规则

如果 URL 无法可靠检查，向用户要截图或导出的 HTML/CSS，不要凭空编造细节。

### URL 注意事项

- 如果产品包含 app surface，不要只基于单个 hero 建系统。
- 区分品牌装饰和可复用产品规则。
- 动效可见但不可测时，定性描述并标为 inferred。
- 用户给出具体页面 URL 时，优先该页面家族，而不是相邻 section。

## 截图工作流

### 最小有用集合

建议三到八张图，覆盖：

- shell 或落地页
- 内容密集页
- 表单、modal 或 drawer
- mobile 或 compact layout

### 安全推断方式

- 先用截图校准 theme/layout/page-template。只有源码或 computed styles 无法提供目标状态值时，才采样重复颜色；采样值写入 `evidence.decisions` 并标为 screenshot-calibrated。
- 从重复 gap、padding 和 grid rhythm 估算间距。
- 只有多张截图支持时，才推断组件状态。
- 不确定项标为 approximate 或 inferred。

### 不要做的事

- 不要从一张截图发明完整 token scale。
- 不要描述不可见或无证据的 dark mode。
- 不要声称视觉感知得到精确 hex、字号、间距或圆角。
- 不要让截图覆盖源码确认的 token。截图用于判断哪个源码主题或布局分支处于 active 状态。

## 产品想法工作流

Brief mode 在合成前先进行轻量设计咨询。目标是恢复足够产品意图，做出有观点且连贯的设计决策；交互会话中应确认方向，然后把这些决策写入正常五件套设计系统包。不要创建单独咨询产物，不要求 gstack 或 Claude 专用工具，也不要使用其它生态的 preambles、telemetry、routed skill prompts 或 AskUserQuestion 格式。

### 内部需要补全的最小 brief

- 产品是什么，给谁用，核心任务是什么。
- 主要界面 archetype 和使用场景。
- 一个最值得记住的视觉/交互结果。
- 应遵守的品类惯例。
- 可以有意突破的 1-2 个设计风险。
- 必需资产、品牌、内容或禁用项。

### 需要确认视觉方向的情况

如果用户只给产品定义、PRD、功能列表、流程、导航或布局草图，而没有明确视觉语气、颜色、字体、密度、圆角、动效、品牌参考或类似约束，必须先给出简洁方向提案并等待确认。

方向提案应包括：

- 产品姿态和 archetype。
- 视觉方向一句话。
- 色彩和字体大方向。
- 密度、布局和组件风格。
- 一个保守品类惯例。
- 一个刻意设计风险。
- 明确询问用户是否确认。

### 可以不提问的情况

只有以下情况可以不等待确认：

- 用户已明确给出视觉方向、品牌约束、颜色、字体、密度、布局或参考产品。
- 正在再生成已确认过的设计系统。
- 用户或宿主环境明确要求非交互、批量、CI、自动化、无人值守、不要提问或跳过确认。

此时在 `briefConsultation` 中使用 `not-required` 或 `skipped`，并写明依据。
