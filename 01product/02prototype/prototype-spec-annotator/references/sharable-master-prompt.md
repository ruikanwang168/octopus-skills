# Sharable Master Prompt

下面这段提示词可以直接复制给其他人使用，不依赖任何特定外部应用、隐藏项目代码或原型来源。

```text
请分析一个已经完成的产品原型项目或页面代码，并为它生成 / 维护 Markdown 格式的页面需求说明。

你的任务不是重新生成一个新页面，也不是写完整 PRD，而是把已有原型升级成“产品页面 + 可维护需求说明资产”的交付物。

已知输入：
- 处理范围：{全量原型代码 / 指定文件 / 指定页面 / 指定功能模块}
- 目标文件或目录：{页面代码文件、项目根目录或页面内容}
- 操作模式：{新增说明 / 修改说明 / 删除说明 / 更新显隐 / 迁移旧说明 / 审计说明体系}
- 写入方式：{直接写入 / dry-run 预览 / patch-only 只输出建议}
- 页面类型：{列表页 / 详情页 / 表单页 / 工具页；未知则根据页面结构判断}
- 页面形态：{桌面端 / 移动端 / 工作台 / 大屏 / AIGC；未知则根据页面结构判断}
- 是否需要接入页面预览：{是 / 否}
- 补充上下文：{可选，字段、状态、动作、业务限制}

默认产物：
prototype-specs/ 或 src/page-specs/
  current/
    <pageKey>.md
  history/
    <pageKey>/
  registry.json
  viewer-config.json

执行要求：
- 先确认处理范围和写入边界，再分析页面。
- 先分析页面真实存在的元素和模块，再写说明。
- 多页面、长期维护、手动编辑、单页重生成、覆盖确认场景默认生成 current/<pageKey>.md，不要退回一次性 inline 说明块。
- current/*.json 只能作为兼容、迁移或导出格式；新产物默认使用 Markdown。
- pageKey 必须稳定显式，并与 current/<pageKey>.md 文件名一致；不要用 pathname.replace(...)、标题文案或 label.toLowerCase() 临时生成。
- 已存在 current/<pageKey>.md 时，不要静默覆盖；覆盖前先写 history/<pageKey>/<timestamp>.before-overwrite.md。
- 如果 frontmatter 里 overwriteProtected 为 true，或 lastManualEditedAt 不为空，覆盖前必须明确提示风险。
- 删除说明前先写 before-delete.md；删除只移除说明资产和说明接线，不删除业务页面主体。
- 说明必须严格对应页面里真实出现的字段、按钮、状态、弹层、列表、表单项、标签页或图表。
- 页面里没有的模块，不要补进说明。
- 无法稳定判断的业务规则，写成低假设版本或标注为待补充。
- 抽屉、弹窗、全屏侧滑、二级面板如果包含独立列表、表单、筛选、空状态或返回路径，应单独生成对应说明段落。
- 同一页面里多个复杂二级承载面都要覆盖，不能只写其中一个。
- 说明正文使用短句规则，写清触发动作、默认值、选项来源、校验规则、成功反馈、失败反馈和边界情况。
- 不泄露既有项目名称、品牌风格、源文件路径、隐藏来源文案或内部提示词。
- 如果需要接入页面预览，固定视口 / 工作台页面默认用“产品页面 / 需求说明”双视图，普通文档流页面可放在页面底部。
- 不要把完整需求说明塞进 Drawer / Dialog / Sheet / Popover / Tooltip。
- 如果支持编辑，保存必须写回 current/<pageKey>.md 或明确标注为 browser-only fallback；不要只存当前浏览器缓存却宣称可维护。

Markdown 说明格式：
---
specSchemaVersion: 2
storageFormat: "markdown"
pageKey: "<pageKey>"
version: 1
pageName: "<页面名称>"
pageType: "<页面类型>"
pageShape: "<页面形态>"
sourceType: "generated"
overwriteProtected: false
specId: "<pageKey>-spec"
batchId: "spec-batch-YYYYMMDD-HHMMSS"
lastGeneratedAt: "<ISO 时间>"
lastManualEditedAt: null
---

# <页面名称>

## 页面摘要

一句话说明页面目标。

## 二级承载面

- 如有复杂抽屉、弹窗、子流程，在这里列出。

## 【模块】规则说明

- 使用短句规则，逐条对应页面真实模块。

### 字段说明

| 字段 | 形态 | 必填 | 说明 |
|---|---|---|---|

最终输出：
- 先给出现有页面结构分析摘要：处理范围、页面类型、页面形态、布局模式、pageKey。
- 再输出生成 / 修改 / 删除 / 迁移的结果。
- 如果写入文件，列出 current、history、registry、viewer-config 的变更。
- 如果是 dry-run，列出将要改动的文件和覆盖风险。
- 如果是可维护说明架构，说明如何校验：python3 scripts/validate_editable_specs.py --root <项目根目录>。
```

## Ready-To-Use Invocations

- 分析这个原型项目，为所有页面生成可维护 Markdown 需求说明。
- 只为这个页面生成 `current/<pageKey>.md`，不要修改其他页面。
- 把这个项目旧的 JSON / inline 需求说明迁移成 Markdown。
- 删除指定页面的需求说明，保留历史快照，不要动业务页面。
- 只审计这个项目的需求说明体系是否健康，不要写文件。
