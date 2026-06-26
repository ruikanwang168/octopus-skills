---
name: airule-init
description: |
  初始化或更新 AI 编码规则文件与项目协作约束。
  固定生成或维护 `AGENTS.md`、`PROJECT.md`、`USER_RULES.md`、`AI_IGNORE.md` 四个基础规则文件，
  并按用户选择的编程工具生成 `CLAUDE.md`、`.cursor/rules`、`.windsurfrules`、`.cursorrules` 等入口文件，
  也支持在已有规则文件基础上学习项目变化并增量更新规则内容。
  当用户需要为一个代码项目创建、补全或更新 AI 编码规则、Agent 说明、开发约束、
  仓库级工作规范，或明确提到“初始化 AI rules”“生成 AGENTS.md”“整理编码规则”时使用。
---

# AI 编码规则初始化

## 何时使用

- 用户需要为现有项目初始化 AI 编码规则文件。
- 用户的项目还没有 `AGENTS.md`、`PROJECT.md`、`USER_RULES.md`、`AI_IGNORE.md` 等基础规则文件，需要从 0 生成。
- 用户的项目已经有部分或全部规则文件，需要根据当前项目结构和已有规则做增量更新。
- 用户需要整理仓库级开发约束、编码规范、协作方式或 Agent 使用说明。
- 用户要生成类似 `AGENTS.md`、`CLAUDE.md`、`.cursor/rules`、`.windsurfrules`、`.cursorrules` 的规则文件。
- 用户希望让 AI 先学习项目，再沉淀成可复用的编码规则。

## 不适用场景

- 不直接实现业务功能或修改业务代码。
- 不生成泛泛的编程规范模板，必须结合目标项目实际结构和技术栈。
- 不替代需求分析、开发计划或代码审查类任务。
- 不在未学习项目结构的情况下编造项目规则。

## 规则文件职责

- `AGENTS.md` 是主入口，负责定义 AI 的角色边界、执行 SOP、文档与状态管理规范、代码输出规范。
- `PROJECT.md` 是项目快照和技术基准，负责记录项目概述、核心技术栈、架构目录规约、代码规范与红线。
- `USER_RULES.md` 是用户手写规则文件，负责保存项目维护者的个人偏好、特殊约束和长期不希望被自动覆盖的规则。
- `AI_IGNORE.md` 是用户维护的扫描忽略规则，负责声明 AI 在项目分析、规则生成、增量更新和源码检索时默认跳过的路径、glob 和正则匹配。
- `CLAUDE.md`、`.cursor/rules`、`.windsurfrules`、`.cursorrules` 只作为指针文件，统一引导 AI 优先阅读 `AGENTS.md`、`PROJECT.md`、`USER_RULES.md` 和 `AI_IGNORE.md`。
- `/AiCoder/` 是 AI 协作的外挂记忆和工程状态机，规则必须说明 `prd`、`task`、`design`、`db` 四类目录的读写边界。

## 规则优先级

生成的规则文件必须明确优先级：

1. `USER_RULES.md`
2. `AI_IGNORE.md`（扫描范围与忽略边界）
3. `PROJECT.md`
4. `AGENTS.md`
5. 工具入口指针文件

如果规则之间冲突，优先遵守用户手写的 `USER_RULES.md`；`AI_IGNORE.md` 专门控制扫描范围和忽略边界；仍不确定时先问用户，不要自行合并冲突规则。

## 工具入口选择

`AGENTS.md`、`PROJECT.md`、`USER_RULES.md`、`AI_IGNORE.md` 是基础规则文件，不需要用户选择，初始化和更新时都必须处理。

如果用户没有明确说明使用哪种编程软件或 AI 编码工具，先让用户多选要生成的工具入口文件：

- Claude Code：生成 `CLAUDE.md`
- Cursor：生成 `.cursor/rules`
- Windsurf：生成 `.windsurfrules`
- 旧版 Cursor 规则：生成 `.cursorrules`
- 暂不生成工具入口：只生成基础规则文件

这是固定分支问题，必须给出上面的选项，不要让用户自由描述。

## 模式区分

### 初始化模式

适用：

- 目标项目没有任何 AI 编码规则文件。
- 用户明确说“新项目”“初始化规则”“生成规则文件”。
- 目标项目只有空规则文件或明显无效的占位内容。

处理方式：

- 先学习项目结构和技术栈，再生成规则文件。
- `AGENTS.md`、`PROJECT.md`、`USER_RULES.md`、`AI_IGNORE.md` 四个基础规则文件必须生成。
- 如果用户未说明编程工具，先让用户从工具入口选项中多选；用户选择后再生成对应入口文件。
- 用户选择“暂不生成工具入口”时，只生成四个基础规则文件。
- `AGENTS.md` 和 `PROJECT.md` 写实质规则；`USER_RULES.md` 只创建用户可手写的占位内容；`AI_IGNORE.md` 创建用户可维护的默认忽略模板；其他工具入口文件只写统一指针内容。
- 生成 `AGENTS.md` 时读取 `references/agents-template.md`。
- 生成 `PROJECT.md` 时读取 `references/project-template.md`。
- 生成 `USER_RULES.md` 时读取 `references/user-rules-template.md`。
- 生成 `AI_IGNORE.md` 时读取 `references/ai-ignore-template.md`。
- 生成指针文件时读取 `references/pointer-files-template.md`。

### 更新模式

适用：

- 目标项目已经存在一个或多个 AI 编码规则文件。
- 用户明确说“更新规则”“补充规则”“同步项目变化”“优化 AGENTS.md”。
- 项目结构、技术栈、命令或协作约束发生变化，需要同步到规则文件。

处理方式：

- 更新模式的目标是同步代码事实和协作入口，不改用户手写规则。
- 执行更新模式时读取 `references/incremental-mode.md`。
- 先读取已有规则文件，识别仍然有效的约束、过期内容和缺失内容。
- 读取并应用 `AI_IGNORE.md` 后重新深度扫描源码，优先更新 `PROJECT.md` 中的项目概述、技术栈、目录规约、命令和代码红线。
- 按需更新 `AGENTS.md` 中的协作 SOP、`/AiCoder/` 目录规则和工具入口引用，不把技术细节堆回 `AGENTS.md`。
- 补齐缺失的基础规则文件：`AGENTS.md`、`PROJECT.md`、`USER_RULES.md`、`AI_IGNORE.md`。
- 如果不同规则文件之间存在冲突，先列出冲突点，不直接覆盖。
- `USER_RULES.md` 是用户所有文件，更新模式禁止自动修改或重写；只有用户明确点名要求修改 `USER_RULES.md` 时才处理。
- `AI_IGNORE.md` 是用户维护的扫描边界文件，更新模式禁止自动修改或重写；只有用户明确点名要求修改 `AI_IGNORE.md` 或忽略列表时才处理。
- 指针文件如果偏离统一入口策略，默认收敛为 `references/pointer-files-template.md` 中的指针内容。

## 核心流程

1. 先扫描目标项目中是否存在 `AGENTS.md`、`PROJECT.md`、`USER_RULES.md`、`AI_IGNORE.md`、`CLAUDE.md`、`.cursor/rules`、`.windsurfrules`、`.cursorrules`。
2. 根据扫描结果进入初始化模式或更新模式；如果用户明确指定模式，优先遵循用户指定。
3. 如果存在 `AI_IGNORE.md`，先读取并应用；如果不存在，在写入前临时采用 `references/ai-ignore-template.md` 的默认忽略范围。
4. 读取目标项目的目录结构、README、包管理文件、配置文件、启动脚本、测试脚本和已有规则文件，跳过 `AI_IGNORE.md` 声明的忽略路径。
5. 识别技术栈、模块边界、启动方式、测试命令、代码风格、协作边界和禁止事项。
6. 如果没有发现源码、包管理文件、构建配置或测试入口，判定为非典型代码仓库，先向用户确认是否仍要初始化 AI 编码规则和 `/AiCoder/` 状态机，不要直接写入完整开发规则。
7. 需要生成或更新 `AGENTS.md` 时，读取 `references/agents-template.md`。
8. 需要生成或更新 `PROJECT.md` 时，读取 `references/project-template.md`，并深度检索源码后再写入。
9. 需要创建缺失的 `USER_RULES.md` 时，读取 `references/user-rules-template.md`；更新模式不得自动修改已有 `USER_RULES.md`。
10. 需要创建缺失的 `AI_IGNORE.md` 时，读取 `references/ai-ignore-template.md`；更新模式不得自动修改已有 `AI_IGNORE.md`。
11. 需要生成或更新 `CLAUDE.md`、`.cursor/rules`、`.windsurfrules`、`.cursorrules` 时，读取 `references/pointer-files-template.md`。
12. 初始化模式下，如果用户未说明编程工具，先让用户多选工具入口；基础规则文件不参与选择，始终生成。
13. 更新模式下，读取 `references/incremental-mode.md`，先对已有规则做差异分析：保留内容、过期内容、缺失内容、冲突内容。
14. 写入前读取 `references/write-checklist.md`，输出写入前摘要，说明将创建或更新哪些文件、覆盖哪些协作约束。
15. 明确开始写入后，再创建或更新对应规则文件。
16. 写入后按 `references/write-checklist.md` 执行校验，发现不满足项必须修正后再结束。

## 输出要求

- 规则必须基于真实项目文件，不要写成通用模板。
- 必须写清楚项目结构、常用命令、编码边界、测试要求和注意事项。
- 如果信息不足，先列出缺口，不要硬写确定性规则。
- 非典型代码仓库必须先确认是否仍要使用代码项目规则；确认前不要写入 `/AiCoder/` 开发状态机规则。
- 更新已有规则文件时，保留仍然有效的项目约束。
- 初始化新规则文件时，必须说明每个文件面向哪个工具或 Agent。
- `AGENTS.md`、`PROJECT.md`、`USER_RULES.md`、`AI_IGNORE.md` 是必须文件，不允许因为用户未选择工具而跳过。
- 未指定开发工具时，不默认生成 `CLAUDE.md`、`.cursor/rules`、`.windsurfrules`、`.cursorrules`，必须先让用户多选。
- 更新已有规则文件时，必须说明新增、修改、保留和待确认内容。
- `PROJECT.md` 必须基于源码级检索结果填写，不能只看 README 或配置文件，也不能只保留空标题；源码检索必须遵守 `AI_IGNORE.md`。
- `AGENTS.md` 必须包含进入仓库后的必读顺序，明确要求读取 `PROJECT.md`、`USER_RULES.md` 和 `AI_IGNORE.md`。
- `AGENTS.md` 必须包含 `/AiCoder/` 目录的读写约束。
- `AGENTS.md` 必须声明 `USER_RULES.md` 由用户维护，AI 不得在增量更新中自动覆盖。
- `AGENTS.md` 必须声明 `AI_IGNORE.md` 由用户维护，AI 在扫描源码前必须读取并遵守。
- 初始化代码仓库时，默认创建空目录 `AiCoder/prd/`、`AiCoder/task/`、`AiCoder/design/`、`AiCoder/db/`；只创建目录，不写入业务内容。
- 规则文件必须写明优先级：`USER_RULES.md` > `AI_IGNORE.md` > `PROJECT.md` > `AGENTS.md` > 工具入口指针文件。
- `USER_RULES.md` 初始化时只写占位说明；更新模式不修改它，除非用户明确点名。
- `AI_IGNORE.md` 初始化时写入默认忽略模板；更新模式不修改它，除非用户明确点名。
- 指针文件必须保持短小，不写项目细节。
- 聊天窗口只输出摘要和文件路径，不要把整份规则全文堆出来。

## 风格约束

- 第一段直接进入项目规则结论，不写套话。
- 少写抽象原则，多写可执行约束。
- 不使用“高质量”“专业”“最佳实践”等缺少判断标准的空话。
- 不编造不存在的命令、目录、框架或测试方式。
- 不把 `AGENTS.md`、`PROJECT.md`、`USER_RULES.md`、`AI_IGNORE.md` 和指针文件简单复制成同一份内容。
- 不自动改写用户手写的 `USER_RULES.md`。
- 不自动改写用户维护的 `AI_IGNORE.md`。

## 读取 references 的条件

- 当需要生成或更新 `AGENTS.md` 时，读取 `references/agents-template.md`。
- 当需要生成或更新 `PROJECT.md` 时，读取 `references/project-template.md`，并按其中的源码检索要求执行。
- 当需要创建缺失的 `USER_RULES.md` 时，读取 `references/user-rules-template.md`。
- 当需要创建缺失的 `AI_IGNORE.md` 时，读取 `references/ai-ignore-template.md`。
- 当用户选择 Claude Code、Cursor、Windsurf、旧版 Cursor 规则，或需要更新已有对应规则文件时，读取 `references/pointer-files-template.md`。
- 当进入更新模式时，读取 `references/incremental-mode.md`。
- 写入前输出摘要、写入后做校验时，读取 `references/write-checklist.md`。

## 容易出错的地方

- 没有学习项目就直接生成通用规则。
- 覆盖用户已有规则文件，导致历史约束丢失。
- 把 `AGENTS.md`、`PROJECT.md`、`USER_RULES.md`、`AI_IGNORE.md` 和指针文件写成完全相同内容，导致主次不清。
- 写了很多建议，但没有明确哪些命令、目录和文件边界必须遵守。
- 更新模式下只追加新内容，不清理已经过期或相互冲突的旧规则。
- `PROJECT.md` 只写空标题，或只根据 README 猜测，没有从真实源码中抽取技术栈、架构分层和代码红线。
- 增量更新时误改 `USER_RULES.md`，覆盖了用户手写规则。
- 深度扫描时没有读取或遵守 `AI_IGNORE.md`，把依赖目录、构建产物、日志、环境变量或密钥纳入项目事实。
- 增量更新时误改 `AI_IGNORE.md`，覆盖了用户维护的忽略边界。
- 用户没有说明编程工具时，擅自生成 `CLAUDE.md`、`.cursor/rules`、`.windsurfrules` 或 `.cursorrules`。
- 写入后没有校验 `AGENTS.md`、`PROJECT.md`、`USER_RULES.md`、`AI_IGNORE.md`、工具入口和 `AiCoder/` 目录是否符合约束。
