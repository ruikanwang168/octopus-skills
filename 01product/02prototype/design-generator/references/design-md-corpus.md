# Design.md 语料参考说明

## 语料角色

本地和外部 `design-md` 示例是参考语料，不是样式 preset。使用它们理解：

- 统一可执行 `DESIGN.md` 结构
- token 命名密度
- 组件配方颗粒度
- preview 目录组成
- 不同 archetype 的表达方式

不要把某个品牌样式复制到无关产品中。

## 统一可执行模式

当前格式把 `DESIGN.md` 变成 **设计系统源文件 + 原型生成约束文件**。front matter 是一个结构化数据模型：

```md
---
version: 1
language: zh-CN
name: Product Name
summary: 一段密集、可执行的设计摘要

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

## 1. 使用说明
## 2. 产品与界面画像
## 3. 设计原则
## 4. 设计令牌
## 5. 布局与应用壳
## 6. 组件系统
## 7. 页面模板
## 8. 交互状态与响应式规则
## 9. 原型生成规则与自检
## 10. 证据、限制与默认决策
```

章节作用：

- **1-3**：说明产品和设计系统是什么。
- **4-8**：说明可执行设计系统，包括 `tokens`、`layout`、`components`、`pageTemplates` 和交互默认值。
- **9**：说明 AI 应如何根据这套设计系统生成原型。
- **10**：说明证据边界、当前默认决策、未确认能力和兜底规则。

## 关键区别

- **单一事实源**：token 字面量只放在 `tokens`；应用壳尺寸只放在 `layout`；页面结构只放在 `pageTemplates`；生成约束只放在 `generationRules`。
- **原型必需字段不能 unknown**：证据无法证明某个必要值时，选择保守默认值，并写入 `evidence.decisions`。
- **历史值不能污染当前规则**：废弃或冲突候选放入 `legacyTokens`。
- **开放问题不能阻塞生成**：每个 `openQuestions` 项都必须包含 `currentDecision` 或 `fallbackRule`。
- **第 10 章必须自洽**：另一个 AI 只拿到 `DESIGN.md` 时，也能安全生成原型，而不必读取 `DESIGN_GAPS.md`。

## DESIGN_GAPS.md

默认始终生成。它把可确认、非阻塞的改进项从权威 `DESIGN.md` 中分离出来。

缺口来源：

- `openQuestions`
- `knownLimits`
- `assumptions`
- `legacyTokens`
- `evidence.decisions` 中低置信度或 `recommended-default` 项

缺口类型：`unconfirmed`、`approximate`、`conflict`、`inferred`、`recommended-default`、`legacy`、`unsupported`。

每个缺口都必须包含当前决策和回写目标。

## 优质样例的共同点

### 前置信息

优质样例通常：

- 用密集 `summary` 概括产品姿态、视觉系统、布局语法、组件系统和原型生成姿态。
- 在 `tokens.colors` 下使用语义 token，而不是原始色板列表。
- 暴露扁平 token 别名，例如 `primary`、`text`、`canvas`、`surface`、`border`、`success`、`warning`、`danger`。
- 将 typography、spacing、radius、shadow 和 motion 定义为角色 token。
- 在 `components` 中用引用 token 的方式描述组件配方。
- 组件命名贴近真实 UI 族群或明确的原型原语。
- `pageTemplates` 包含结构、规则、样例内容、证据和置信度。
- 包含 `generationRules.must`、`generationRules.mustNot` 和 `generationRules.selfCheck`。
- 对推断值和推荐默认值写入 `evidence.decisions`。

### 正文

优质样例通常：

- 开头就给出清晰产品姿态。
- 解释颜色如何使用，以及哪里不能使用。
- 通过角色和行为说明字体，而不是只列字体名。
- 解释页面语法、密度、shell 结构和重复布局模式。
- 给出组件配方，而不是只列样式。
- 区分 in-source 开发和 no-source 原型生成。
- 给未来 Agent 直接可执行的约束。
- 明确当前默认值和推断值，不隐藏不确定性。
- 压缩证据路径，但保留可执行规则；`DESIGN.md` 应像实现约束文件，而不是源码审计记录。

### 预览

好的预览应当：

- 像简洁的设计系统手册，而不是原始 token dump。
- 先给复核者摘要：证据模式、置信度、开放问题、legacy/conflict 候选和最重要的风格事实。
- 靠前展示 CSS variables。
- 展示符合 archetype 的真实组件族。
- 在原始配方数据前，展示一个贴近源产品的代表性 shell 或页面模板。
- 让 token 能快速检查。
- 将字体呈现为层级和语义系统。
- 用具体使用场景解释 token 含义。
- 先展示组件视觉，再展开较长实现细节。
- 展示状态覆盖情况，而不是静默补齐缺失状态。
- 包含原型生成规则和已知限制快照，便于 AI 工具和维护者快速检查漂移。
- 不要通过通用阴影、尺寸、暗色模式声明或占位文案引入第二套设计语言。

在本 Skill 中，预览是设计系统的校验手册。应尽量从 `DESIGN.md` front matter 和章节文本生成。不要把预览手写成业务页面或独立品牌展示页。
