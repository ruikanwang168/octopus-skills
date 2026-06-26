# 写入摘要与校验清单

## 写入前摘要

创建或更新规则文件前，必须先输出摘要，不要静默写入。

摘要必须包含：

- 模式：初始化模式 / 更新模式。
- 将创建的基础文件：`AGENTS.md`、`PROJECT.md`、`USER_RULES.md`、`AI_IGNORE.md` 中哪些会被创建。
- 将更新的基础文件：`AGENTS.md`、`PROJECT.md` 中哪些会被更新。
- `USER_RULES.md` 处理方式：创建占位 / 读取但不修改 / 用户明确要求修改。
- `AI_IGNORE.md` 处理方式：创建默认忽略模板 / 读取并应用但不修改 / 用户明确要求修改。
- 工具入口选择：Claude Code、Cursor、Windsurf、旧版 Cursor 规则、暂不生成工具入口。
- 将创建或更新的工具入口文件路径。
- 将创建的空目录：`AiCoder/prd/`、`AiCoder/task/`、`AiCoder/design/`、`AiCoder/db/`。
- `PROJECT.md` 已识别的技术栈、入口、核心目录和命令摘要。
- 待确认事项。

## 写入后校验

写入完成后必须检查：

- `AGENTS.md` 存在，并包含“进入仓库必读”章节。
- `AGENTS.md` 明确要求读取 `PROJECT.md`、`USER_RULES.md` 和 `AI_IGNORE.md`。
- `AGENTS.md` 写明规则优先级：`USER_RULES.md` > `AI_IGNORE.md` > `PROJECT.md` > `AGENTS.md` > 工具入口指针文件。
- `PROJECT.md` 存在，且四个章节都不是空标题。
- `PROJECT.md` 的技术栈、命令、目录职责能追溯到真实文件；无法追溯的内容应写“待确认”。
- `PROJECT.md` 的源码事实没有来自 `AI_IGNORE.md` 声明的忽略路径，除非用户明确要求并在摘要中说明原因。
- `PROJECT.md` 正文没有“本次新增”“旧规则已移除”“原来是”等更新过程痕迹。
- `USER_RULES.md` 存在；如果原文件已存在，哈希或内容不得被自动修改。
- `AI_IGNORE.md` 存在；如果原文件已存在，哈希或内容不得被自动修改。
- 如果用户选择 Cursor，必须创建或更新 `.cursor/rules/project.mdc`，不要创建 `.cursor/rules` 普通文件。
- 工具入口文件只包含短指针，并直接要求读取 `AGENTS.md`、`PROJECT.md`、`USER_RULES.md`、`AI_IGNORE.md`。
- 初始化代码仓库时，`AiCoder/prd/`、`AiCoder/task/`、`AiCoder/design/`、`AiCoder/db/` 四个空目录存在。

如果任一检查失败，先修正再结束任务。
