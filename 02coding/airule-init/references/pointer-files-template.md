# CLAUDE.md 指针文件生成规则

## 文件职责

`CLAUDE.md` 是 Claude Code 的入口指针文件，只负责引导读取 `AGENTS.md`、`harness/PROJECT.md`、`harness/USER_RULES.md` 和 `harness/AI_IGNORE.md`。Codex 直接使用 `AGENTS.md`，其生成规则见 `agents-template.md`。

初始化和更新模式都默认生成或维护 `CLAUDE.md`，不询问工具选择；文件缺失时直接补齐。

## 适用文件

- `CLAUDE.md`

## 默认模板

如果用户没有额外要求，`CLAUDE.md` 写入：

```md
---
last_updated: YYYY-MM-DD
status: active
owner: unassigned
---

本仓库的主协作入口是项目根目录的 `AGENTS.md`，项目快照和配套规则统一存放在 `harness/`。下列路径均相对于项目根目录。
首次进入仓库时，请优先阅读：
1. `AGENTS.md`：了解你的核心职责、行为边界以及项目文档的维护规范。
2. `harness/PROJECT.md`：了解本项目的技术栈底线、架构分层与代码风格约束。
3. `harness/USER_RULES.md`：了解项目维护者手写的特殊约束和个人偏好；除非用户明确要求，否则不要修改此文件。
4. `harness/AI_IGNORE.md`：了解扫描、分析和生成规则时必须忽略的文件、目录和匹配模式；除非用户明确要求，否则不要修改此文件。
```

## 生成规则

- 默认创建或更新 `CLAUDE.md`，与 Codex 入口 `AGENTS.md` 同时提供。
- 头部遵守 `agents-template.md` 的元信息约定，日期使用实际生成或内容更新日，负责人未指定时填 `unassigned`；元信息之后仍只保留短指针正文。
- 指针文件保持短小，不写项目结构、命令、技术栈细节。
- 更新模式下，如果指针文件里已有大量项目细节，默认将可复用细节迁移到 `AGENTS.md` 或 `harness/PROJECT.md`，指针文件收敛回短入口。
- 如果用户明确要求 Claude Code 保留专属规则，只保留该工具必须独有的最小内容，其余规则仍指向 `AGENTS.md`、`harness/PROJECT.md`、`harness/USER_RULES.md` 和 `harness/AI_IGNORE.md`。
