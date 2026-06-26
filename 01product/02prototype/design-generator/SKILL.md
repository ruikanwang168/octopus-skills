---
name: design-generator
description: >
  根据本地源码、截图、在线 URL、页面抓取数据或产品 brief，生成一套带证据边界的可执行设计系统包。
  产物固定包含 `DESIGN.md` 或 `design.md`、`preview.html`、`preview-dark.html`、`example.html`
  和 `DESIGN_GAPS.md`。当 Codex 需要提取或合成可直接指导 AI 编程工具、前端工程师、
  设计系统维护者或产品原型生成的设计规则时使用，尤其适用于后续 UI 必须保留既有产品真实视觉语法、
  页面模式、组件映射和布局行为，而不是退回通用 SaaS 默认风格的场景。
---

# 设计系统生成器

## 概览

本 Skill 用于生成一套可复用的设计系统包：

- `DESIGN.md` 或 `design.md`：设计系统单一事实源，也是 AI 页面生成约束文件。文件必须包含统一可执行 YAML front matter 和 10 个可读章节。
- `preview.html`：面向人工复核的可视化预览，用于检查设计令牌、组件和页面模式。
- `preview-dark.html`：真实暗色模式预览，或明确标注为暗色检查视图。
- `example.html`：由 Agent 根据 `DESIGN.md` 生成的源产品匹配样例，用于证明规范可指导后续 UI 生成。Python 脚本可以生成诊断占位页，但不能替代最终样例。
- `DESIGN_GAPS.md`：待确认项与冲突日志，记录分析过程中的不确定、冲突、缺失和低置信度判断。默认始终生成。

统一格式的 `DESIGN.md` 同时回答两个问题：

1. 这套设计系统是什么？
2. AI 应该怎样按照这套设计系统生成页面？

不要生成 moodboard、泛化落地页或通用后台模板。输出必须足够具体，让另一个 Agent 或工程师仅凭 Markdown 文件就能继续构建新 UI。

## 快速流程

1. 判断输入证据模式：`source+screenshot`、`source-only`、`screenshot-only`、`url` 或 `brief`。
2. 决定输出语言。用户当前对话语言是最强信号。中文用户、中文项目、中文产品名、中文截图、中文源码注释/路由、面向中文用户的产品，都应使用简体中文编写 Markdown、预览文案、样例、清单和缺口说明。代码标识、token 名称、selector、class、文件路径、库名、API 名称保持原样。
3. 阅读 [references/design-md-corpus.md](references/design-md-corpus.md)，选择最接近的界面 archetype 和预览组成。
4. 阅读 [references/input-analysis.md](references/input-analysis.md)，按证据模式执行分析。
   - 在 `brief` 模式下，先完成轻量设计咨询：恢复产品上下文、识别一个最值得记住的设计结果、判断是否需要品类研究、定义安全的品类惯例和有意选择的设计风险。若用户尚未明确批准视觉方向，且当前会话可交互，应先给出简洁的 `Brief Direction Proposal` 并等待确认。确认前不要运行脚手架、写入 `DESIGN.md`、渲染预览或生成 `DESIGN_GAPS.md`。产品定义、PRD、需求文档、流程说明、导航列表或布局草图，只有在明确指定视觉语气、颜色、字体、密度、圆角、动效、品牌参考或同等级视觉约束时，才算视觉方向已批准。
   - 如果用户提供 `theme-data/` 这类 URL 抓取证据目录，先运行：

   ```bash
   python3 scripts/extract_url_theme_evidence.py /absolute/path/to/theme-data
   ```

   输出 JSON 只作为内部候选证据使用。除非用户要求保留调试证据，否则不要放进最终五件套。

5. 写产物前阅读 [references/output-contract.md](references/output-contract.md)。
6. 选择输出目录和 Markdown 文件名：
   - 用户指定输出目录时，使用该目录。
   - 分析本地项目且未指定输出目录时，写入 `<project-root>/DESIGN`。
   - URL-only、screenshot-only、brief-only 且没有本地项目根目录时，默认写入当前目录下的 `./DESIGN`。
   - 如果已有 `DESIGN.md` 或 `design.md` 约定，沿用现有命名。
   - 如果用户明确指定文件名，使用用户指定文件名。
   - 否则默认使用 `DESIGN.md`。
7. 生成脚手架：

```bash
python3 scripts/scaffold_design_folder.py --project-root /absolute/path/to/project --name "Product Name" --markdown-name DESIGN.md --format ai-design-system-v3
```

当用户指定目标目录时，使用 `--output /absolute/path/to/custom-folder`。中文项目或中文用户语境使用 `--language zh-CN`。

8. 用完整内容替换脚手架里的 Markdown，占满统一可执行 front matter 和 10 章正文。
9. 从 Markdown 渲染或刷新预览：

```bash
python3 scripts/render_preview_from_design_md.py /absolute/path/to/DESIGN --markdown-name DESIGN.md
```

10. 根据 `DESIGN.md` 手写 `example.html`。选择最有代表性的 `pageTemplates` 条目，把一次性样例请求写入 `example.html` 内的 `example-generation-input` 元数据，并在页面中可见展示。不要把这条样例请求写回 `DESIGN.md`。
11. 生成 `DESIGN_GAPS.md`：

```bash
python3 scripts/generate_gaps_doc.py /absolute/path/to/DESIGN --markdown-name DESIGN.md --language zh
```

脚本会从 `openQuestions`、`knownLimits`、`assumptions`、`legacyTokens` 和低置信度 `evidence.decisions` 中提取待确认信息。`DESIGN_GAPS.md` 是确认台账；AI 生成页面时以 `DESIGN.md` 为准。

12. 校验结果：

```bash
python3 scripts/validate_design_folder.py /absolute/path/to/DESIGN --markdown-name DESIGN.md --format ai-design-system-v3
```

## 输出规则

- 每个目标只生成一套设计系统包。
- 用户指定输出目录时，所有文件保存到该目录；否则本地项目写入 `<project-root>/DESIGN`，URL-only、screenshot-only 或 brief-only 写入 `./DESIGN`。
- 必须包含 `DESIGN.md`、`preview.html`、`preview-dark.html`、`example.html` 和 `DESIGN_GAPS.md`。
- 默认不要生成 `EVIDENCE.json`、`VALIDATION_REPORT.md` 或其它分析产物。只有用户要求保留证据、输出质量报告、批量回归或开启调试模式时，才把可选调试文件放入 `<target-folder>/.design-generator/`。
- `DESIGN.md` 是设计系统和 AI 生成约束的单一事实源；`preview.html` 只是可视化辅助。
- `DESIGN_GAPS.md` 独立记录不确定项、冲突和缺失覆盖，不能替代 `DESIGN.md` 的当前默认决策。
- `example.html` 必须是 Agent 根据 `DESIGN.md` 生成的源产品匹配样例。它可以包含样例请求元数据，但 `DESIGN.md` 不应包含一次性样例请求。
- 新脚手架始终使用统一可执行 schema 和 10 章结构。非 v3 校验模式只服务于单独提供的 `stitch-alpha` 或旧编号格式包。
- 保留真实源系统。不要把朴素企业产品膨胀成装饰性营销系统。
- 推断值或推荐值必须明确标注，不能伪装为已观察事实。
- 截图-only 的测量值要标注为近似，除非源码或 computed styles 能确认。
- 不要先套通用 SaaS/admin 设计系统再修改。应先分类证据、提取已有信息，只在缺失处用带标签的假设补齐。
- 只有 `brief` 模式可以从零合成设计系统。源码、URL、截图和混合模式必须 extraction-first，但为了后续原型生成所需的字段，仍要给出保守可执行推荐，并在 `evidence.decisions` 中说明理由。
- 不要添加与源产品矛盾的组件族、颜色、动效或布局。证据缺失但原型必须有决策时，选择最不意外、符合产品类型的默认值，并记录为 `recommended-default`。
- 如果 brief、URL、截图备注或源码分析包含必要视觉资产，必须把每个资产 URL/路径保存在 `DESIGN.md` 内。不要写“见原始规格”或依赖聊天历史。
- 源码支撑的原型指导必须记录 app shell、page shell、页面模式和组件映射；只有 tokens 不够。
- `DESIGN.md` 应是执行规范，不是冗长证据报告。压缩源码扫描过程和重复证据，但保留所有影响页面生成的规则。

## DESIGN.md 内容边界

必须放进 `DESIGN.md` 的内容：

- 真实 token 值和语义使用规则
- 组件配方、状态、组合方式和禁止模式
- app shell、page shell、内容区域、尺寸和响应式行为
- 页面模板和代表性结构
- in-source 和 no-source 两种生成规则
- 未确认能力的默认处理方式
- 生成后自检项

不要塞进 `DESIGN.md` 的内容：

- 冗长源码扫描叙述
- 重复文件路径证据
- 低优先级推断细节
- 已有当前默认值后的废弃候选值
- 不影响页面生成的实现历史
- 可能误导后续原型的一次性 `example.html` 样例请求

## DESIGN.md 与 DESIGN_GAPS.md

```text
DESIGN.md      = 当前可执行规则 / 权威设计系统
DESIGN_GAPS.md = 待确认台账 / 冲突清单 / 人工确认记录
```

后续 AI 工具可能只拿到 `DESIGN.md`，所以 `DESIGN.md` 必须自洽：

- `DESIGN.md` 必须声明当前默认决策。
- `DESIGN.md` 必须解释未确认能力的默认处理规则。
- `DESIGN.md` 不能只写“详情见 DESIGN_GAPS.md”。
- `DESIGN_GAPS.md` 记录完整证据、候选值、待确认项和回写记录。
- 人工确认 `DESIGN_GAPS.md` 后，要把确认结果写回 `DESIGN.md`，再重新生成预览。

## 工作流

### 1. 判断证据模式

选择一个主证据模式：

- **Source + screenshot mode**：本地源码加截图或页面抓取。源码和 computed styles 决定精确 token；截图用于识别当前运行态主题、布局状态、可见页面模式、密度和冲突。
- **Source-only mode**：只有本地源码或项目目录。提取精确 token 和组件映射；如果应用存在多主题或多布局，把运行态标为推断。
- **Screenshot-only mode**：只有截图。提取页面结构、组件组成、密度和近似视觉 token；精确颜色、间距、字体除非来自可靠设计导出，否则标为近似。
- **URL mode**：在线网站或本地渲染 URL。优先使用 DOM、CSS variables 和 computed styles，而不是视觉采样。尽量覆盖一个内容密集页和一个窄视口。
- **Brief mode**：只有产品想法、功能概念或流程描述。先做简洁设计咨询，再合成一致的可执行系统并清楚记录假设。

如果请求同时包含既有产品和新页面/新功能，使用最强证据模式，既有产品是设计源头。

当源码、URL、截图、`theme-data/` 和产品描述同时存在时，以 `source+screenshot` 为主模式，把 URL 运行态、截图、`theme.json` 和描述作为证据层。不要因为有 URL 就切换到 URL-only。

边界规则：

- `source+screenshot`、`source-only`、`screenshot-only`、`url` 模式下，不要使用脚手架里的通用 token、Inter 字体、8px 圆角或通用后台页面例子作为起点。脚手架只提供文件和章节骨架。
- `brief` 模式允许合成 token 和页面模式，但 `evidence.mode` 必须是 `brief`，`assumptions` 要说明合成选择，`confidence.tokens` / `confidence.components` 不应为 `high`，除非用户给了明确品牌或实现约束。
- `brief` 模式不能把咨询结果当成单独交付物。要把结果转入 `DESIGN.md` 的权威字段：产品姿态、设计原则、tokens、components、pageTemplates、generationRules、`assumptions` 和 `evidence.decisions`。
- `brief` 模式必须包含 `briefConsultation`，其 `status` 为 `approved`、`skipped` 或 `not-required`。`approved` 表示用户确认；`not-required` 表示原 brief 已有明确视觉方向或正在再生成已确认决策；`skipped` 只允许在用户或宿主环境明确要求非交互、批量、CI、自动化、无人值守或跳过确认时使用，并必须提供具体 `skipReason`。
- `screenshot-only` 模式的 token 置信度不能是 `high`。
- 不要输出 `unknown`、`unavailable`、空占位或空关键字段。证据不足时，写入安全当前决策，并在 `evidence.decisions` 中标注 `source: recommended-default` 和理由。

### 2. 证据优先级

按以下顺序使用证据：

1. 用户明确目标约束和纠正。
2. 目标状态下 URL/本地运行 UI 的 computed styles、DOM 和 CSS variables。
3. 目标状态下 active 源码 tokens、主题文件、CSS variables、组件原语、路由和布局容器。
4. 截图和页面抓取，用于主题状态、密度、层级、组件组合和布局校准。
5. `theme.json` / URL 主题证据摘要，只作为候选 token 频率数据。
6. 历史变量和备用主题，只作为候选。
7. 对缺失但必要字段使用保守、符合产品类型的推荐值。

源码或 computed styles 可用时，不用截图决定精确颜色、字号、间距或圆角。截图只用于判断当前主题、布局状态、页面模式、组件组合和冲突，并尽量回溯到源码 selector、变量、组件、DOM 或 computed styles。

把 `theme.json` 当候选池，不当权威设计系统。只有当 runtime computed styles、active source styles、重复截图或明确当前决策支持时，才把值提升到 `tokens`。落选候选放入 `legacyTokens`、`openQuestions` 或低置信度 `evidence.decisions`。

应用壳需要单独处理：

- 产品主色、顶部导航背景、标签栏背景、侧栏表面、内容画布是不同语义角色。
- 不要因为它们色相接近就都归成 `primary`。
- 源码支撑项目的 top-nav height、sidebar expanded width、sidebar collapsed width、tags height 应来自源码或 computed styles。
- 截图可以确认当前 shell 状态，但不能覆盖源码支撑的精确尺寸，除非存在明确 runtime override 或已记录冲突。
- 用户明确纠正 token 或 shell 值时，以用户纠正为当前交付权威值，并把源码不一致记录到 `DESIGN_GAPS.md`。

如果证据冲突，把当前决策写进权威字段（`tokens`、`layout`、`components` 或 `pageTemplates`），把落选值记录到 `legacyTokens` / `openQuestions`。每个 `openQuestions` 都必须包含 `currentDecision` 或 `fallbackRule`，让后续生成不中断。

### 3. 选择界面 archetype

写文档前先选择主 archetype：

- `enterprise-admin`：后台管理、CRUD、表格、权限、任务、审核、配置
- `settings-admin`：设置中心、账号、组织、权限、计费
- `marketing-site`：营销官网、落地页、功能介绍、CTA
- `brand-portfolio`：作品集、个人品牌、创作者主页
- `content-resource-portal`：资源门户、数字资源库、文化资源展示、媒体资料库、专题展
- `media-content`：新闻、视频、播客、内容流
- `ecommerce`：商品列表、商品详情、购物车、订单
- `marketplace`：多方资源、服务、房源、课程、人才匹配
- `analytics-dashboard`：分析仪表盘
- `data-screen`：全屏可视化大屏
- `mobile-app`：移动端应用
- `aigc-workbench`：AI 生成、Prompt、结果预览、任务历史
- `chat-agent`：聊天式 AI、Copilot、客服、知识问答
- `editor-workbench`：编辑器、画布、工具栏、属性面板
- `docs-portal`：文档站、API 文档、开发者中心、知识库
- `workflow-automation`：流程编排、节点画布、执行记录
- `collaboration-workspace`：协作文档、项目空间、任务看板
- `map-geospatial`：地图、点位、图层、空间分析
- `file-asset-manager`：文件库、素材库、上传、预览、版本管理
- `custom:<name>`：其它结构明确但无法归类的产品形态

不要混合多个 archetype，除非产品确实横跨多个形态。源码派生项目中，保真比新奇更重要。

不要因为页面里有筛选、元数据、卡片或图表，就把公共文化档案、数字资源门户、媒体库、作品集、文档站、落地页、移动 UI、大屏、AIGC 工作台或聊天 Agent 标为 admin/dashboard。后台/仪表盘只用于以 CRUD、表格、审批任务、管理工作流和权限设置为主的运营工具。

### 4. 先建立 token lockup

写正文前，先在内部整理 evidence packet 和 token lockup。

Evidence packet 应包含：

- 证据模式与置信度
- 使用的源码、URL、截图、`theme-data/`、主题摘要或 brief 假设
- 可观察的运行态主题和布局状态
- 框架、组件库、样式系统和 shell selector
- 代表性页面模式及来源页面
- 源组件到未来原型组件的映射
- 冲突、近似值和缺失证据的推荐默认决策

Token lockup 应包含：

- 产品姿态和密度
- 语义颜色角色
- 字体角色
- 间距尺度
- 圆角尺度
- 阴影和层级
- 动效规则
- 组件变体和状态
- 必要资产清单，包括准确 URL/路径及使用位置
- app shell、page shell 和可复用页面模式
- 响应式行为
- 已知推断或缺失证据

用同一份 evidence packet 和 lockup 写 YAML front matter。正文只能解释同一套 token、页面模式和组件映射，不能引入第二套设计语言。

### 5. 编写 DESIGN.md

遵循 [references/output-contract.md](references/output-contract.md)。Markdown 必须以统一 YAML front matter 开头，不要创建并行兼容层，也不要在多个字段重复同一事实。

必需顶层字段：

```yaml
---
version: 1
language: zh-CN
name: Product Name
summary: 一段产品特定的设计系统摘要
product:
technology:
runtime:
tokens:
layout:
components:
pageTemplates:
generationRules:
evidence:
briefConsultation:
legacyTokens:
openQuestions:
knownLimits:
assumptions:
---
```

随后写 10 个章节。中文标准标题：

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

源码派生系统需要：

- 说明真实框架、组件库、布局容器、工具类和 token 载体。
- 保留密度、语言、术语、实现语法和重复页面模式。
- 中文产品输出中文说明、prompt 指南、清单、缺口、预览文本和样例 UI。
- 把源码组件映射到未来原型应使用的组件。
- 说明截图只用于运行态、主题和布局校准时，不把截图当精确 token 来源。
- 标注近似值和缺失状态。
- 不要无证据重塑品牌或美化产品。

概念派生系统需要：

- 说明目标用户、使用场景和界面 archetype。
- 选择一个连贯视觉方向。
- 记录假设和参考影响。
- 足够具体，避免后续 Agent 回退到通用默认值。

### 5.1 统一 schema 规则

每个 `DESIGN.md` 都必须在 `tokens` 下暴露扁平语义别名。下游 AI 工具和预览必须能直接读取这些名称：

```yaml
tokens:
  colors:
    primary: "#003EB3"
    primaryHover: "#0958d9"
    onPrimary: "#ffffff"
    text: "rgba(0,0,0,0.68)"
    textStrong: "rgba(0,0,0,0.83)"
    textMuted: "rgba(0,0,0,0.4)"
    canvas: "#ffffff"
    surface: "#fafafa"
    surfaceMuted: "#f5f5f5"
    border: "#d9d9d9"
    borderLight: "#f0f0f0"
```

如果源码使用 `primary-colors.primary.value` 这类分组 token，只能作为补充证据或 legacy detail。推荐规则、预览和样例应优先使用 `tokens.*`。

第 4 章必须区分当前 token 与 legacy/conflict token。第 6 章必须写组件配方，而不是只列样式。第 5 章必须区分 in-source 开发和 no-source 原型生成。

### 5.2 页面模板

`pageTemplates` 定义未来 Agent 可使用的页面语法，不是代码侧硬编码模板目录。页面模板要写真实产品页面，而不是泛化管理页或营销整页。

每个模板应包含：

- `name`
- `archetype`
- `purpose`
- `priority`: `primary` / `secondary` / `optional`
- `structure` 或 `sections`
- `components`
- `sampleContent` 或 `sampleData`
- `evidence`
- `confidence`

`structure` / `sections` 要能被渲染成真实页面。使用稳定 section 名称，例如 `top-nav`、`sidebar`、`hero-search`、`search-toolbar`、`filter-panel`、`resource-card-grid`、`media-card-grid`、`data-table`、`pagination`、`prompt-input`、`generation-controls`、`result-preview`、`chat-thread`、`map-panel`、`canvas-workspace`、`detail-panel`。

多个模板时，选择代表页的优先级：

1. 用户当前验证目标指定的模板。
2. `priority: primary`。
3. `structure` / `sections` 最完整的模板。
4. 最贴近主要用户任务的模板。

### 5.3 example.html 边界

不要把一次性样例请求写进 `DESIGN.md`。`example.html` 是验证产物，不属于可复用规范。

`example.html` 必须：

- 从 `pageTemplates` 里选择代表性模板。
- 在 `<script type="application/json" id="example-generation-input">` 中写入样例请求。
- 可见展示 `userRequest`。
- 声明 `data-example-source`、`data-example-archetype`、`data-example-pattern` 和 `data-example-pattern-source`。
- 不使用渲染器内置的产品级硬编码 preset。若 `DESIGN.md` 页面结构不足，生成诊断页并把缺口记录到 `DESIGN_GAPS.md`。

### 6. 生成预览和样例页

完成 `DESIGN.md` 后运行：

```bash
python3 scripts/render_preview_from_design_md.py /absolute/path/to/DESIGN --markdown-name DESIGN.md
```

预览是证据驱动的校验手册，不是 token dump、落地页或通用 demo dashboard。

之后由 Agent 编写或完善 `example.html`。Python 渲染器只保留旧兼容 fallback；默认不应覆盖 Agent 已经写好的样例。

### 7. 生成 DESIGN_GAPS.md

默认始终生成：

```bash
python3 scripts/generate_gaps_doc.py /absolute/path/to/DESIGN --markdown-name DESIGN.md --language zh
```

`DESIGN_GAPS.md` 结构：

- 文件说明、证据模式、置信度、生成时间
- §1 总体置信度摘要
- §1b 当前默认决策（存在默认决策时出现）
- §2 高优先级待确认项
- §3 中优先级待确认项
- §4 低优先级待确认项
- §5 设计冲突清单
- §6 未覆盖 / 未观察到的内容
- §7 人工确认记录
- 确认流程

缺口来源：`openQuestions`、`knownLimits`、`assumptions`、`legacyTokens`、低置信度或 `recommended-default` 的 `evidence.decisions`。

缺口类型：`unconfirmed`、`approximate`、`conflict`、`inferred`、`recommended-default`、`legacy`、`unsupported`。

每个缺口都应包含 ID、优先级、类型、待确认问题、当前判断、证据来源、置信度、影响范围、当前处理策略、需要人工确认的问题和回写位置。每个缺口都必须有当前决策或兜底规则。

### 8. 校验与修正

运行：

```bash
python3 scripts/validate_design_folder.py /absolute/path/to/DESIGN --format ai-design-system-v3 --markdown-name DESIGN.md
```

修复硬错误，并手动检查：

- 只有一个 Markdown 设计源文件。
- `DESIGN_GAPS.md` 存在。
- front matter 和正文描述同一套系统。
- `tokens.colors` 暴露 `primary`、`text`、`canvas`、`surface`、`border` 等扁平语义别名。
- 证据模式、运行态、源码置信度和缺口清楚。
- 源码派生产物引用真实组件原语和页面模板。
- token 引用如 `{tokens.colors.primary}` 可解析。
- 预览使用真实 token 值，不使用泛化默认值。
- `preview-dark.html` 的暗色策略不与运行态说明或 gaps 矛盾。
- `example.html` 展示代表性页面模式，且不与 `DESIGN.md` 矛盾。
- `example.html` 不是脚手架诊断页，并声明 `data-example-source="design-md"`。
- `example-generation-input.selectedPageTemplate` 匹配已有 `pageTemplates` id/name。
- 源码派生产物仍然像源产品。
- 概念派生产物连贯且不泛化。
- 中文产物不保留大段英文占位文案。
- 第 10 章提供自洽默认决策，而不是只写“见 DESIGN_GAPS.md”。
- 第 4 章区分当前 token 和 legacy token。
- 第 6 章区分 in-source 与 no-source。
- 第 9 章包含生成规则、禁止模式和自检项。

## 迭代更新

初始设计系统包生成后，可按以下方式迭代：

1. 用户审阅 `DESIGN_GAPS.md`。
2. 用户提供确认信息，例如“侧栏宽度确认是 240px”。
3. 更新 `DESIGN.md` 中对应 front matter 和章节。
4. 重新生成预览。
5. 更新 `DESIGN_GAPS.md`，把已确认项移动到人工确认记录。

## 资源

- `references/design-md-corpus.md`：界面 archetype 和预览组成参考。
- `references/input-analysis.md`：源码、URL、截图和 brief 的证据工作流。
- `references/output-contract.md`：`DESIGN.md`、预览和 gaps 的完整输出契约。
- `scripts/scaffold_design_folder.py`：生成五件套骨架。
- `scripts/extract_url_theme_evidence.py`：汇总 `theme-data/theme.json` 和截图清单。
- `scripts/render_preview_from_design_md.py`：从完成的 `DESIGN.md` 生成 `preview.html` 和 `preview-dark.html`。
- `scripts/generate_gaps_doc.py`：从 front matter 生成 `DESIGN_GAPS.md`。
- `scripts/validate_design_folder.py`：校验文件、schema、token 引用、重复字面量、预览结构和证据纪律。
- `assets/*.template.*`：仅作为骨架模板，不能当作默认设计系统值。
