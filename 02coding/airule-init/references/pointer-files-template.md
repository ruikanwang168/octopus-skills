# 指针规则文件生成规则

## 文件职责

`CLAUDE.md`、`.cursor/rules`、`.windsurfrules`、`.cursorrules` 是工具入口指针文件，只负责把不同 AI 工具的入口收敛到 `AGENTS.md`、`PROJECT.md`、`USER_RULES.md` 和 `AI_IGNORE.md`。

初始化模式下不默认生成任何工具入口文件。只有用户明确选择对应编程工具，或目标项目已经存在这些文件需要更新时才处理。

## 适用文件

- `CLAUDE.md`
- `.cursor/rules`
- `.windsurfrules`
- `.cursorrules`

## 默认模板

如果用户没有额外要求，上述文件统一写入：

```md
本仓库的协作入口已切换到根目录 `AGENTS.md`，后续规则和项目快照以 `AGENTS.md` 为准。
首次进入仓库时，请优先阅读：
1. `AGENTS.md`：了解你的核心职责、行为边界以及项目文档的维护规范。
2. `PROJECT.md`：了解本项目的技术栈底线、架构分层与代码风格约束。
3. `USER_RULES.md`：了解项目维护者手写的特殊约束和个人偏好；除非用户明确要求，否则不要修改此文件。
4. `AI_IGNORE.md`：了解扫描、分析和生成规则时必须忽略的文件、目录和匹配模式；除非用户明确要求，否则不要修改此文件。
```

## 生成规则

- 新项目没有任何规则文件时，不默认创建工具入口文件。
- 用户选择 Claude Code 时，才创建或更新 `CLAUDE.md`。
- 用户选择 Cursor 时，才创建或更新 `.cursor/rules`。
- 用户选择 Windsurf 时，才创建或更新 `.windsurfrules`。
- 用户选择旧版 Cursor 规则或明确要求 `.cursorrules` 时，才创建或更新 `.cursorrules`。
- 用户选择“暂不生成工具入口”时，不创建本文件列表中的任何文件。
- 指针文件保持短小，不写项目结构、命令、技术栈细节。
- 如果目标项目中 `.cursor/rules` 已经是目录，不要删除或替换目录；改为创建或更新 `.cursor/rules/project.mdc`，并保持同样的入口指针策略。
- 如果目标项目中 `.cursor/rules` 不存在，优先创建目录 `.cursor/rules/` 和文件 `.cursor/rules/project.mdc`，不要创建同名普通文件。
- 更新模式下，如果指针文件里已有大量项目细节，默认将可复用细节迁移到 `AGENTS.md` 或 `PROJECT.md`，指针文件收敛回短入口。
- 如果用户明确要求某个工具保留专属规则，只保留该工具必须独有的最小内容，其余规则仍指向 `AGENTS.md`、`PROJECT.md`、`USER_RULES.md` 和 `AI_IGNORE.md`。
