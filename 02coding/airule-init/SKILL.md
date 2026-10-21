---
name: airule-init
description: |
  初始化或更新 AI 编码规则文件与项目协作约束。
  仅支持 Codex 和 Claude Code，默认生成或维护 `AGENTS.md`、`CLAUDE.md`、
  `harness/PROJECT.md`、`harness/USER_RULES.md`、`harness/AI_IGNORE.md` 五个规则文件，无需选择工具，
  也支持在已有规则文件基础上学习项目变化并增量更新规则内容。
  当用户需要为一个代码项目创建、补全或更新 AI 编码规则、Agent 说明、开发约束、
  仓库级工作规范，或明确提到“初始化 AI rules”“生成 AGENTS.md”“整理编码规则”时使用。
---

# AI 编码规则初始化

## 何时使用

- 用户需要为现有项目初始化 AI 编码规则文件。
- 用户的项目还没有 `AGENTS.md`、`harness/PROJECT.md`、`harness/USER_RULES.md`、`harness/AI_IGNORE.md` 等基础规则文件，需要从 0 生成。
- 用户的项目已经有部分或全部规则文件，需要根据当前项目结构和已有规则做增量更新。
- 用户需要整理仓库级开发约束、编码规范、协作方式或 Agent 使用说明。
- 用户要为 Codex 或 Claude Code 生成 `AGENTS.md`、`CLAUDE.md` 等项目规则文件。
- 用户希望让 AI 先学习项目，再沉淀成可复用的编码规则。

## 不适用场景

- 不直接实现业务功能或修改业务代码。
- 不生成泛泛的编程规范模板，必须结合目标项目实际结构和技术栈。
- 不替代需求分析、开发计划或代码审查类任务。
- 不在未学习项目结构的情况下编造项目规则。

## 规则文件职责

- `AGENTS.md` 是 Codex 入口和项目主记忆文件，负责定义 AI 的角色边界、执行 SOP、文件快速导航、文档与状态管理规范、需求进度跟踪和代码输出规范。
- `harness/PROJECT.md` 是项目快照和技术基准，负责记录项目概述、核心技术栈、架构目录规约、代码规范与红线。
- `harness/USER_RULES.md` 是用户手写规则文件，负责保存项目维护者的个人偏好、特殊约束和长期不希望被自动覆盖的规则。
- `harness/AI_IGNORE.md` 是用户维护的扫描忽略规则，负责声明 AI 在项目分析、规则生成、增量更新和源码检索时默认跳过的路径、glob 和正则匹配。
- `CLAUDE.md` 是 Claude Code 入口，只作为指针文件，引导 AI 优先阅读 `AGENTS.md`、`harness/PROJECT.md`、`harness/USER_RULES.md` 和 `harness/AI_IGNORE.md`。
- `harness/` 是项目规则与研发资料的统一根目录。`harness/plan/` 按计划建目录，保存该计划的 `需求.md`、`进度.md`，以及每次执行的任务 Markdown、数据库变更文件及其他相关文件；`harness/design/` 保存长期维护的设计文档。

## 默认目录结构

以下路径均相对于目标项目根目录：

```text
项目根目录/
├── AGENTS.md
├── CLAUDE.md
└── harness/
    ├── PROJECT.md
    ├── USER_RULES.md
    ├── AI_IGNORE.md
    ├── plan/
    │   └── 20261021-登录功能改造/   # YYYYMMDD-计划标识
    │       ├── 需求.md              # 本次任务的背景、目标、范围、约束和验收标准
    │       ├── 进度.md              # 按需求条目跟踪状态、执行任务、验收结果和下一步
    │       ├── 001-任务.md          # 本次执行的目标、任务、状态和结果
    │       ├── 001-db.sql           # 本次数据库变更，按需创建
    │       └── ...                  # 本次执行的其他相关文件
    └── design/                      # 设计文档
```

初始化只创建五个规则文件及空目录 `harness/plan/`、`harness/design/`，不创建示例计划或业务文件。实际开发时，每个计划独立建目录，根据真实需求编写 `需求.md`，并创建 `进度.md` 跟踪各需求条目的完成情况。每次执行前先读取这两个文件及关联任务记录，再以执行编号区分各次执行的文件；执行中持续更新需求进度，结束或交接前同步状态、验收结果和下一步。数据库文件采用项目实际使用的格式，不强制使用 SQL。

计划目录名统一采用 `YYYYMMDD-<计划标识>`，日期取用户本地时区的计划创建日期，后缀使用计划简名或编号，例如 `20261021-登录功能改造`。同日不同计划使用不同后缀；继续执行已有计划时沿用原目录，不因日期变化另建目录。

## 规则优先级

生成的规则文件必须明确优先级：

1. `harness/USER_RULES.md`
2. `harness/AI_IGNORE.md`（扫描范围与忽略边界）
3. `harness/PROJECT.md`
4. `AGENTS.md`
5. `CLAUDE.md`（入口指针）

如果规则之间冲突，优先遵守用户手写的 `harness/USER_RULES.md`；`harness/AI_IGNORE.md` 专门控制扫描范围和忽略边界；仍不确定时先问用户，不要自行合并冲突规则。

## 工具支持与默认产物

仅支持 Codex 和 Claude Code，初始化和更新时默认同时处理两个工具入口，不询问工具选择：

- Codex：`AGENTS.md`，同时承担项目主协作入口职责。
- Claude Code：`CLAUDE.md`，指向主协作入口和配套规则文件。

加上 `harness/PROJECT.md`、`harness/USER_RULES.md`、`harness/AI_IGNORE.md`，默认产物共五个文件；只有两个工具入口位于项目根目录。更新时补齐缺失文件，并遵守已有用户维护文件的保护规则。

其他工具入口不属于本技能维护范围，不创建、更新、迁移或删除。

## 模式区分

### 初始化模式

适用：

- 目标项目没有任何 AI 编码规则文件。
- 用户明确说“新项目”“初始化规则”“生成规则文件”。
- 目标项目只有空规则文件或明显无效的占位内容。

处理方式：

- 先学习项目结构和技术栈，再生成规则文件。
- `AGENTS.md`、`harness/PROJECT.md`、`harness/USER_RULES.md`、`harness/AI_IGNORE.md` 四个基础规则文件必须生成。
- 同时生成 Codex 入口 `AGENTS.md` 和 Claude Code 入口 `CLAUDE.md`，无需用户选择工具。
- `AGENTS.md` 和 `harness/PROJECT.md` 写实质规则；`harness/USER_RULES.md` 只创建用户可手写的占位内容；`harness/AI_IGNORE.md` 创建用户可维护的默认忽略模板；`CLAUDE.md` 只写指针内容。
- 生成 `AGENTS.md` 时读取 `references/agents-template.md`。
- 生成 `harness/PROJECT.md` 时读取 `references/project-template.md`。
- 生成 `harness/USER_RULES.md` 时读取 `references/user-rules-template.md`。
- 生成 `harness/AI_IGNORE.md` 时读取 `references/ai-ignore-template.md`。
- 生成 `CLAUDE.md` 时读取 `references/pointer-files-template.md`。

### 更新模式

适用：

- 目标项目已经存在一个或多个 AI 编码规则文件。
- 用户明确说“更新规则”“补充规则”“同步项目变化”“优化 AGENTS.md”。
- 项目结构、技术栈、命令或协作约束发生变化，需要同步到规则文件。

处理方式：

- 更新模式的目标是同步代码事实和协作入口，不改用户手写规则。
- 执行更新模式时读取 `references/incremental-mode.md`。
- 先读取已有规则文件，识别仍然有效的约束、过期内容和缺失内容。
- 读取并应用 `harness/AI_IGNORE.md` 后重新深度扫描源码，优先更新 `harness/PROJECT.md` 中的项目概述、技术栈、目录规约、命令和代码红线。
- 按需更新 `AGENTS.md` 中的协作 SOP、`harness/plan/` 和 `harness/design/` 目录规则及工具入口引用，不把技术细节堆回 `AGENTS.md`。
- 如果项目仍使用旧版根目录规则文件或旧版研发目录，按 `references/incremental-mode.md` 的迁移规则处理，避免把已有内容当作缺失而重新生成。
- 补齐缺失的基础规则文件：`AGENTS.md`、`harness/PROJECT.md`、`harness/USER_RULES.md`、`harness/AI_IGNORE.md`。
- 如果不同规则文件之间存在冲突，先列出冲突点，不直接覆盖。
- `harness/USER_RULES.md` 是用户所有文件，更新模式禁止自动修改或重写；只有用户明确点名要求修改 `harness/USER_RULES.md` 时才处理。
- `harness/AI_IGNORE.md` 是用户维护的扫描边界文件，更新模式禁止自动修改或重写；只有用户明确点名要求修改 `harness/AI_IGNORE.md` 或忽略列表时才处理。
- 默认创建缺失的 `CLAUDE.md`；已有文件如果偏离统一入口策略，按 `references/pointer-files-template.md` 更新。

## 核心流程

1. 先扫描目标项目中是否存在 `AGENTS.md`、`CLAUDE.md`、`harness/PROJECT.md`、`harness/USER_RULES.md`、`harness/AI_IGNORE.md`；发现旧版布局时，先读取 `references/incremental-mode.md` 的迁移规则，再判断哪些文件缺失。
2. 根据扫描结果进入初始化模式或更新模式；如果用户明确指定模式，优先遵循用户指定。
3. 如果存在 `harness/AI_IGNORE.md`，先读取并应用；如果只有旧版忽略文件，先读取并应用原内容，再按增量迁移规则处理；两者都不存在时，在写入前临时采用 `references/ai-ignore-template.md` 的默认忽略范围。忽略模式始终相对于项目根目录解释。
4. 读取目标项目的目录结构、README、包管理文件、配置文件、启动脚本、测试脚本和已有规则文件，跳过 `harness/AI_IGNORE.md` 声明的忽略路径；对 Markdown 文档按 `references/agents-template.md` 的元信息约定判断有效性，默认不将已废弃文档作为现行事实，不能仅按日期较早就忽略有效文档。
5. 识别技术栈、模块边界、启动方式、测试命令、代码风格、协作边界和禁止事项。
6. 如果没有发现源码、包管理文件、构建配置或测试入口，判定为非典型代码仓库，先向用户确认是否仍要初始化 AI 编码规则和 `harness/` 研发资料结构，不要直接写入完整开发规则。
7. 需要生成或更新 `AGENTS.md` 时，读取 `references/agents-template.md`。
8. 需要生成或更新 `harness/PROJECT.md` 时，读取 `references/project-template.md`，并深度检索源码后再写入。
9. 需要创建缺失的 `harness/USER_RULES.md` 时，读取 `references/user-rules-template.md`；更新模式不得自动修改已有 `harness/USER_RULES.md`。
10. 需要创建缺失的 `harness/AI_IGNORE.md` 时，读取 `references/ai-ignore-template.md`；更新模式不得自动修改已有 `harness/AI_IGNORE.md`。
11. 读取 `references/pointer-files-template.md`，准备创建或更新 `CLAUDE.md`，确保 Codex 和 Claude Code 两个入口齐全。
12. 更新模式下，读取 `references/incremental-mode.md`，先对已有规则做差异分析：保留内容、过期内容、缺失内容、冲突内容。
13. 写入前读取 `references/write-checklist.md`，输出写入前摘要，说明将创建或更新哪些文件、覆盖哪些协作约束。
14. 明确开始写入后，再创建或更新对应规则文件，并同步 `AGENTS.md` 中的“快速导航”，登记本次在 `harness/` 下创建或迁移的每个文件。
15. 写入后按 `references/write-checklist.md` 执行校验，发现不满足项必须修正后再结束。

## 输出要求

- 项目事实必须基于真实项目文件；硬性规则将实际项目约束翻译为明确的适用范围、判定条件和检查方式，不把参考示例或观察到的代码习惯当成强制规则。
- 必须写清楚项目结构、常用命令、编码边界、测试要求和注意事项。
- 如果信息不足，先列出缺口，不要硬写确定性规则。
- 非典型代码仓库必须先确认是否仍要使用代码项目规则；确认前不要写入 `harness/` 研发协作规则。
- 更新已有规则文件时，保留仍然有效的项目约束。
- 初始化新规则文件时，必须说明每个文件面向哪个工具或 Agent。
- 新生成的 Markdown 文档均须在头部包含 `last_updated`、`status`、`owner`；实际值、状态过滤和更新规则按 `references/agents-template.md` 执行，不能把模板日期或示例负责人当作真实值。已有用户维护文件和原样迁移文件仍按保护规则处理。
- 默认生成或维护 `AGENTS.md`、`CLAUDE.md`、`harness/PROJECT.md`、`harness/USER_RULES.md`、`harness/AI_IGNORE.md` 五个文件，不因用户未指定工具而跳过入口。
- 更新已有规则文件时，必须说明新增、修改、保留和待确认内容。
- `harness/PROJECT.md` 必须基于源码级检索结果填写，不能只看 README 或配置文件，也不能只保留空标题；源码检索必须遵守 `harness/AI_IGNORE.md`。
- `harness/PROJECT.md` 的“核心技术栈”使用列表，写清技术、版本和技术红线，不附配置或来源；“硬性规则（必须遵守）”使用可机械判定的规则列表，生成方式见 `references/project-template.md`，缺失的条件列为待确认，后续保留开发人员的修改。
- `harness/PROJECT.md` 的“核心架构与目录规约”必须用目录树展示真实项目层级，并在节点旁简注职责和必要约束。
- `AGENTS.md` 必须包含进入仓库后的必读顺序，明确要求读取 `harness/PROJECT.md`、`harness/USER_RULES.md` 和 `harness/AI_IGNORE.md`。
- `AGENTS.md` 必须包含“快速导航”表格，表头为“你想做什么”“去哪里看”；`harness/` 下每个新生成文件均须登记，文件移动、重命名、删除或用途变化时同步维护，细则按 `references/agents-template.md` 生成。
- `AGENTS.md` 必须包含“提交规范”，按 `references/agents-template.md` 列出五种提交类型。
- `AGENTS.md` 必须包含“文档元信息与有效性”，要求后续文档带元信息，并明确 `deprecated` 的默认跳过行为、日期不能单独判定过期和元信息缺失时的处理方式。
- `AGENTS.md` 必须说明 `harness/plan/YYYYMMDD-<计划标识>/` 的命名规则及其与 `harness/design/` 的读写约束，以及计划内 `需求.md`、`进度.md` 的用途、读取和更新时机及按次保存任务、数据库变更和其他文件的规则。进度跟踪细则按 `references/agents-template.md` 生成。
- `AGENTS.md` 必须声明 `harness/USER_RULES.md` 由用户维护，AI 不得在增量更新中自动覆盖。
- `AGENTS.md` 必须声明 `harness/AI_IGNORE.md` 由用户维护，AI 在扫描源码前必须读取并遵守。
- 初始化代码仓库时，默认创建空目录 `harness/plan/`、`harness/design/`；实际研发时创建计划子目录及 `需求.md`、`进度.md`，任务、数据库和其他执行文件按需创建。
- 规则文件必须写明优先级：`harness/USER_RULES.md` > `harness/AI_IGNORE.md` > `harness/PROJECT.md` > `AGENTS.md` > `CLAUDE.md`。
- `harness/USER_RULES.md` 初始化时只写占位说明；更新模式不修改它，除非用户明确点名。
- `harness/AI_IGNORE.md` 初始化时写入默认忽略模板；更新模式不修改它，除非用户明确点名。
- 指针文件必须保持短小，不写项目细节。
- 聊天窗口只输出摘要和文件路径，不要把整份规则全文堆出来。

## 风格约束

- 第一段直接进入项目规则结论，不写套话。
- 少写抽象原则，多写可执行约束。
- 不使用“高质量”“专业”“最佳实践”等缺少判断标准的空话。
- 不编造不存在的命令、目录、框架或测试方式。
- 不把 `AGENTS.md`、`harness/PROJECT.md`、`harness/USER_RULES.md`、`harness/AI_IGNORE.md` 和指针文件简单复制成同一份内容。
- 不自动改写用户手写的 `harness/USER_RULES.md`。
- 不自动改写用户维护的 `harness/AI_IGNORE.md`。

## 读取 references 的条件

- 当需要生成或更新 `AGENTS.md` 时，读取 `references/agents-template.md`。
- 当需要生成或更新 `harness/PROJECT.md` 时，读取 `references/project-template.md`，并按其中的源码检索要求执行。
- 当需要创建缺失的 `harness/USER_RULES.md` 时，读取 `references/user-rules-template.md`。
- 当需要创建缺失的 `harness/AI_IGNORE.md` 时，读取 `references/ai-ignore-template.md`。
- 当生成或更新 Claude Code 入口 `CLAUDE.md` 时，读取 `references/pointer-files-template.md`；初始化和更新模式默认都执行。
- 当进入更新模式时，读取 `references/incremental-mode.md`。
- 写入前输出摘要、写入后做校验时，读取 `references/write-checklist.md`。

## 容易出错的地方

- 没有学习项目就直接生成通用规则。
- 覆盖用户已有规则文件，导致历史约束丢失。
- 把 `AGENTS.md`、`harness/PROJECT.md`、`harness/USER_RULES.md`、`harness/AI_IGNORE.md` 和指针文件写成完全相同内容，导致主次不清。
- 写了很多建议，但没有明确哪些命令、目录和文件边界必须遵守。
- 更新模式下只追加新内容，不清理已经过期或相互冲突的旧规则。
- `harness/PROJECT.md` 只写空标题，或只根据 README 猜测，没有从真实源码中抽取技术栈、架构分层和代码红线。
- 增量更新时误改 `harness/USER_RULES.md`，覆盖了用户手写规则。
- 深度扫描时没有读取或遵守 `harness/AI_IGNORE.md`，把依赖目录、构建产物、日志、环境变量或密钥纳入项目事实。
- 增量更新时误改 `harness/AI_IGNORE.md`，覆盖了用户维护的忽略边界。
- 仍要求用户选择工具，或没有补齐 Codex 入口 `AGENTS.md` 和 Claude Code 入口 `CLAUDE.md`。
- 写入后没有校验五个规则文件、`harness/plan/` 和 `harness/design/` 是否符合约束。
