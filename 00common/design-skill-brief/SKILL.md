---
name: design-skill-brief
description: |
  在创建或更新 Codex Skill 前，先校验 skill-creator 是否可用，再通过分轮访谈梳理 Skill 需求，输出可交付给 skill-creator 的 Markdown 需求文档。适用于用户想“创建技能”“设计 Skill”“梳理技能需求”“把想法变成 SKILL.md”“先问清楚再调用 skill-creator 创建技能”，或需要评审一个 Skill 想法是否边界清楚、触发准确、输出稳定时使用。
---

# Design Skill Brief

## 目标

把模糊的 Skill 想法整理成一份可执行的 Skill 需求文档，再把这份文档交给 `$skill-creator` 创建或更新 Skill。

## 不适用场景

- 用户已经给出完整、已确认的 Skill 需求文档，只要求直接创建文件时，优先使用 `$skill-creator`。
- 用户只是咨询某个领域知识，不打算创建或更新 Skill 时，不触发本 Skill。
- 不替代 `$skill-creator` 手写最终 Skill，除非用户明确要求在缺少 `$skill-creator` 的环境里继续。
- 不一次性读取所有 references；只在下方条件满足时读取指定文件。

## 第一步：校验 skill-creator

在访谈前先确认 `$skill-creator` 是否可用：

1. 先查看当前会话可用 Skills 列表中是否有 `skill-creator`。
2. 如果不确定，运行 `scripts/check_skill_creator.py`。
3. 如果找到，第一轮回复必须说明“已检测到 skill-creator”，然后开始访谈。
4. 如果没找到，停止最终创建流程，并让用户在固定选项中选择：
   - 安装或启用 `skill-creator`
   - 继续只生成 Skill 需求文档
   - 暂停

不要读取 `skill-creator` 目录里的文件来完成本 Skill 的访谈；只有在需求文档确认后，才按 `$skill-creator` 自身规则调用它。

## 访谈规则

- 每轮最多问 3 个问题；信息不足时继续追问，不要一次塞满长问卷。
- 固定分支必须给选项，开放细节才让用户自由输入。
- 优先确认这些固定分支：
  - 模式：新建 Skill、更新现有 Skill
  - 类型：创意型、流程型、精确型、混合型
  - 交付：只生成需求文档、需求文档确认后创建 Skill
  - 资源：仅 SKILL.md、需要 references、需要 scripts、需要 assets、暂不确定
  - 位置：当前工作区、`$CODEX_HOME/skills`、用户指定路径
- 必须收集至少 2 个应该触发该 Skill 的真实用户说法。
- 必须收集至少 1 个不应该触发该 Skill 的边界例子。
- 如果用户已经给出足够信息，先归纳假设并请用户确认，不要重复问已回答的问题。

## 需求文档

当信息足够形成文档时：

1. 读取 `references/skill-brief-template.md`。
2. 读取 `references/skill-quality-rules.md`。
3. 输出或写入一份 Markdown 需求文档，文件名优先用 `skill-brief.md`。
4. 文档末尾必须包含“待确认问题”和“创建前检查清单”。

需求文档必须直接进入结论，不要用背景铺垫。不要出现“在当今”“随着……发展”“综上所述”“总之”“非常专业”“深度思考”等套话或空泛评价。

## 调用 skill-creator

只有在用户确认需求文档后，才调用 `$skill-creator`。调用时传递以下信息：

- Skill 名称候选和推荐名称
- 目标路径
- 新建或更新模式
- Skill 类型和自由度
- 触发场景和不适用场景
- 输出结构和验收标准
- 需要创建的 `references/`、`scripts/`、`assets/`
- 需要遵守的质量规则

如果用户明确授权“文档确认后自动创建”，可以在展示文档后直接进入 `$skill-creator`；否则先问一句是否开始创建。

## 输出要求

- 第一段先给状态或判断，例如是否检测到 `skill-creator`、当前缺少什么信息。
- 问题要短，带编号或选项，避免开放式长段落。
- 需求文档用 Markdown，适合直接交给 `$skill-creator`。
- 涉及事实、路径、脚本、资源目录时给出具体名称，不用“高质量”“更专业”替代判断标准。

## 读取 references 的条件

- 起草或修改 Skill 需求文档前，读取 `references/skill-brief-template.md`。
- 评审 Skill 想法、写创建前检查清单、准备交给 `$skill-creator` 前，读取 `references/skill-quality-rules.md`。
- 仅校验 `skill-creator` 是否存在时，运行 `scripts/check_skill_creator.py`，不需要读取 references。
