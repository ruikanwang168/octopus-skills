---
name: prototype-spec-annotator
description: 独立维护已有 HTML / Vue / React 原型项目的页面级需求说明资产：分析现有页面、发现页面与稳定 pageKey、生成或更新 Markdown-first 说明、维护 registry/history、可选接入说明展示层、删除/显隐/迁移/校验说明资产。只要用户提到给现有原型补需求说明、生成/修改/删除/隐藏/展示页面说明、把旧 inline 或 JSON 说明迁移为 Markdown、批量维护多页面说明、校验说明体系，必须使用本 skill。适用于不了解任何外部应用背景、只提供本地原型项目或页面文件的用户。
---

# Prototype Spec Annotator

## Purpose

把已经完成的原型代码升级为“产品页面 + 可维护需求说明资产”的交付物。

默认产物不是一次性静态说明块，而是每页一个 Markdown 说明文件：

```text
prototype-specs/ 或 src/page-specs/
  current/
    <pageKey>.md
  assets/
    <pageKey>/
      paste-<timestamp>.png
  history/
    <pageKey>/
      <timestamp>.before-overwrite.md
      <timestamp>.before-delete.md
  registry.json
  viewer-config.json
```

本 skill 是独立本地工作流。不要要求用户了解、安装或运行额外应用；用户只需要提供目标原型项目、页面文件或处理范围。所有生成、迁移、审计和可选展示接线都围绕目标项目与本 skill 自带脚本完成。

## Hard Rules

- 先分析已有页面代码，再写需求说明；页面代码是事实来源，不要凭空写 PRD。
- 多页面、长期维护、手动编辑、单页重生成、覆盖确认场景默认使用 Markdown-first 可维护架构。
- `current/*.md` 是默认主协议；`current/*.json` 只能作为兼容、迁移或导出格式。
- `pageKey` 必须稳定显式，并且等于 `current/<pageKey>.md` 文件名。
- 已有说明不能静默覆盖；覆盖、删除、手动保存前先写入 `history/<pageKey>/` 快照。
- `overwriteProtected: true` 或 `lastManualEditedAt` 非空时，默认必须提示覆盖风险。
- 说明内容必须对应页面真实模块、字段、状态、按钮和二级承载面。
- 修改范围必须收敛在用户指定项目、页面或文件内；不要改目标范围外的业务页面、脚本或仓库文件。
- 清理说明时只移除说明资产、说明 wrapper、说明标记和说明接线，不删除业务页面主体。
- HTML / React / Vue 新接入默认必须使用同一套 dual-view：`产品页面 / 需求说明` 可拖动切换器、`.proto-spec-*` 文档阅读器样式、`编辑 / Markdown / 预览 / 保存 / 取消` 工具栏和 `/__prototype-specs/specs/<pageKey>` 保存 API。
- `产品页面 / 需求说明` 切换器在 HTML / React / Vue 中都必须支持按住任意区域拖动：默认顶部居中，移动超过约 5px 才进入拖动，未拖动时按钮点击仍正常切换，刷新后恢复默认位置且不持久化拖动坐标。
- 编辑态的 `预览` 只能渲染当前未保存草稿；`保存` 才能写回 `current/<pageKey>.md` 并创建 `.before-manual-save.md` 历史快照。三类项目的按钮语义、状态文案和视觉样式必须一致。
- 编辑态 Markdown 文本框必须支持粘贴剪贴板图片：图片落盘到 `<spec-root>/assets/<pageKey>/`，正文插入 `![粘贴图片](../assets/<pageKey>/<filename>)`，并通过 `/__prototype-specs/assets/<pageKey>` 资产 API 读写；禁止把图片以内联 base64 写入 Markdown。
- 旧 inline / document-flow / 外部静态 viewer 只能作为 legacy 迁移输入；默认集成前必须清理 `initSpecViewer(...)`、`initProtoSpecViewer(...)`、`assets/js/spec-viewer.js`、`assets/js/proto-spec-viewer.js`、`assets/css/proto-spec.css`、`proto-spec-divider`、`proto-spec-badge`、inline `PageSpecDocInline` 等旧接线，不能与 dual-view 共存。
- 如果只做审计或 dry-run，不写文件，只输出发现、风险和建议操作。

## Task Router

先把用户请求归到一个模式，再读取对应参考文件：

- `create`：从现有原型生成 Markdown 需求说明并接入展示层。少量页面由执行该 skill 的智能体写正文并用脚本写入/校验，随后执行集成；全量批处理执行 `scripts/run_proto_spec_workflow.py --operation create --integrate` 一步完成生成和展示接线。默认产物是「页面 + 可编辑需求说明」的双视图交付物；只有用户明确只要离线 Markdown 文件时才跳过集成。按需读 `references/markdown-spec-format.md`、`references/spec-writing-rules.md`、`references/page-types.md`、`references/15-dimension-scan.md`、`references/framework-integration.md`。
- `update`：修改已有 Markdown 说明。少量页面由执行该 skill 的智能体直接更新正文并保留历史；批量更新可执行 `scripts/run_proto_spec_workflow.py --operation update`。按需读 `references/operation-modes.md`、`references/markdown-spec-format.md`、`references/15-dimension-scan.md`。
- `delete`：删除指定说明并保留历史。优先执行 `scripts/run_proto_spec_workflow.py --operation delete`，并按需读 `references/operation-modes.md`、`references/cleanup-mode.md`。
- `display`：只调整显隐、默认展开或页面/说明展示方式。优先执行 `scripts/run_proto_spec_workflow.py --operation display`，并按需读 `references/operation-modes.md`、`references/visibility-mode.md`。
- `migrate`：把旧 inline / JSON / 大对象说明迁移为 Markdown。读 `references/migration-mode.md`、`references/markdown-spec-format.md`。
- `audit`：只检查说明体系是否健康。优先执行 `scripts/run_proto_spec_workflow.py --operation audit` 或 `scripts/validate_editable_specs.py`，并按需读 `references/validation.md`、`references/quality-checklist.md`。
- `integrate`：把 Markdown 说明接到 React / Vue / HTML 预览中。优先执行 `scripts/run_proto_spec_workflow.py --operation integrate`，并按需读 `references/framework-integration.md`、`references/layout-integration-rules.md`。

范围不清楚时，先保守处理用户点名的页面或文件；只有用户明确要求全量时，才扫描整个项目。

## Model Usage

默认由执行该 skill 的智能体及其当前模型负责高质量内容判断与说明写作。不要要求用户额外配置模型才能使用本 skill。

- 对少量页面、需要准确表达业务规则、需要结合用户补充上下文的任务：执行该 skill 的智能体先分析页面代码并直接生成或修改 Markdown 正文，再用脚本初始化、写入、接线和校验。
- 对全量批处理、结构化扫描、历史快照、registry 维护、展示层接线、迁移、删除、显隐和审计：优先使用 `scripts/run_proto_spec_workflow.py` 或专项脚本。
- runner 是本地进程，不会自动继承执行环境中的当前模型。只有用户明确需要无人值守批量生成、或要求脚本自己调用模型时，才使用 `--model-base-url --model-api-key --model` 或 `PROTO_SPEC_MODEL_*` 环境变量。
- 未配置 runner 模型时，runner 只生成 `local-rule-draft` 基础草稿；执行该 skill 的智能体必须继续读取页面代码和 `current/*.md`，按 `Writing Rules` 和相关 reference 审阅、补全或重写 Markdown 正文。只有用户明确说“仅草稿 / 不要 AI 补全 / dry-run 占位”时，才允许传 `--draft-only` 并停在规则草稿。

## Default Workflow

1. 确认处理范围、操作模式和是否允许写文件。
2. 读取 `references/input-contract.md`，补齐最小输入。
3. 分析目标原型代码，识别框架、页面、稳定 `pageKey`、页面类型、页面形态、布局模式和二级承载面。
4. 用 `references/15-dimension-scan.md` 做按需覆盖扫描；只写页面可见、可直接推断或用户明确补充的维度。
5. 选择生成策略：
   - 少量页面或高质量说明：执行该 skill 的智能体用当前模型写 Markdown 正文，再用脚本完成写入、registry/history 和校验。完成后继续执行 step 10 接入展示层（除非用户明确只要离线 Markdown 文件）。
   - 全量批处理或结构化任务：执行独立 runner 并追加 `--integrate`，一步完成生成和展示接线（除非用户明确只要离线文件）。
6. 常用 runner 命令：
   - 新增/重生成：`python3 scripts/run_proto_spec_workflow.py --root <项目根目录> --operation create --scope all`
   - 指定页面：追加 `--scope selected --page-key <pageKey>` 或 `--file <相对路径>`
   - 同时接入展示层：追加 `--integrate --viewer-mode dual-view --visibility-mode manual-toggle`
   - 覆盖已有说明：只有用户确认后追加 `--force`
   - 仅保留本地规则草稿：只有用户明确要求草稿时追加 `--draft-only`
   - 只预览：追加 `--dry-run --json`
7. 如果 runner 不适合当前任务，再使用专项脚本：
   - 初始化空说明空间：`python3 scripts/init_spec_system.py --root <项目根目录>`
   - 迁移旧说明：`python3 scripts/migrate_to_markdown_specs.py --root <项目根目录>`
   - 清理旧 inline 说明：`python3 scripts/clear_specs.py --root <项目根目录>`
8. 如果 runner 输出 `aiReviewRequired: true`、`aiReviewPages` 或 `sourceType: "local-rule-draft"`，不要结束任务；继续分析对应页面源码并补全这些 Markdown 正文，补全后把 frontmatter 改为 `sourceType: "ai-reviewed"`、`aiReviewRequired: false`、`aiReviewStatus: "completed"`。
9. 如果已有说明，先写历史快照，再覆盖；如果用户未确认覆盖，停止在建议状态。
10. 接入展示层（默认必须执行）。这是本 skill 的核心交付物 —— 「产品页面 + 可编辑需求说明」双视图。只有用户明确说「只生成 Markdown 文件」「不需要页面展示」「离线说明即可」「不接入页面」时，才跳过此步。
    - 判断依据：用户请求中出现「可编辑」「页面上」「展示」「切换」「查看说明」「需求说明」「双视图」等词时，集成是强制步骤，不得跳过。
    - 按 `references/framework-integration.md` 选择 React / Vue / HTML 的接线方式；三类项目统一使用 `dual-view`，写入前清理旧 inline viewer。
    - 展示层统一规格：`产品页面 / 需求说明` 可拖动切换器、`.proto-spec-*` 文档阅读器样式、`编辑 / Markdown / 预览 / 保存 / 取消` 工具栏、`/__prototype-specs/specs/<pageKey>` 保存 API。
    - 切换器拖动规格必须三端一致：默认顶部居中；在切换条任意区域按住并拖动，移动超过约 5px 才视为拖动；拖动结束后的 click 事件不得触发视图切换；刷新后回到默认位置。
    - 编辑态 `预览` 只能渲染当前未保存草稿；`保存` 写入 `current/<pageKey>.md` 并生成 `.before-manual-save.md` 历史快照。
    - 编辑态粘贴图片时，HTML / React / Vue 都必须把图片保存到 `<spec-root>/assets/<pageKey>/`，插入相对 Markdown 图片引用，并在预览渲染时把该引用解析到 `/__prototype-specs/assets/<pageKey>/<filename>`。
11. 结束前运行校验：
   - `python3 scripts/validate_editable_specs.py --root <项目根目录>`
   - 如果目标项目有构建命令，再运行项目自己的 build / typecheck。
12. 如果接入了展示层，必须启动本地 server 或目标项目 dev server，实测一次 `PUT /__prototype-specs/specs/<pageKey>` 保存 API，确认会写入 `current/<pageKey>.md` 且生成 `.before-manual-save.md` 历史快照。
13. 汇报改动文件、历史快照、校验结果和未处理风险。

## Runner Contract

`scripts/run_proto_spec_workflow.py` 是本 skill 的默认执行入口。它必须保持自包含：

- 只读取本 skill 自带脚本和目标原型项目文件。
- 不 import 任何外部产品的 TypeScript、React、Electron 或产品源码。
- 不要求目标项目安装额外应用依赖。
- 默认使用本地规则生成基础说明；runner 作为本地进程，不能自动访问执行环境中的当前模型。
- 本地规则生成的内容必须标记为 `sourceType: "local-rule-draft"`、`generationMode: "local-rule"`、`aiReviewRequired: true`、`aiReviewStatus: "pending"`，并在 report 中输出 `aiReviewRequired` 与 `aiReviewPages`。
- `--draft-only` 只表示用户明确接受未审阅草稿；不要在默认工作流中使用。
- 只有无人值守批处理或用户明确要求脚本直接调用模型时，才提供 `--model-base-url --model-api-key --model` 或对应环境变量 `PROTO_SPEC_MODEL_BASE_URL`、`PROTO_SPEC_MODEL_API_KEY`、`PROTO_SPEC_MODEL`，调用 OpenAI-compatible Chat Completions 生成更完整说明。
- React / Vue 集成只在找到明确入口和路由锚点时自动 patch；同时写入 `scripts/proto-spec-vite-plugin.mjs` 并 patch `vite.config.*`，提供同源保存 API；否则只写入 viewer 文件并报告跳过原因。
- HTML 集成会写入 `proto-spec-server.mjs`，用于静态预览、本地保存 API、GET 读取说明 API，并在返回 HTML 时注入当前 Markdown 的 `application/json` 兜底数据，避免浏览器或部署环境拦截 `.md` 静态资源导致说明不可见。
- 当 `viewerMode` 为 `dual-view` 时，集成前必须移除旧 inline viewer、旧外部静态 viewer 资产和接线；校验时发现 dual-view 与 legacy viewer marker 共存应报错。
- 保存 API 路径为 `/__prototype-specs/specs/<pageKey>`。
- 图片资产 API 路径为 `/__prototype-specs/assets/<pageKey>` 和 `/__prototype-specs/assets/<pageKey>/<filename>`；只支持 `png`、`jpeg`、`webp`、`gif`，单图大小上限 10MB，资产保存到 `<spec-root>/assets/<pageKey>/`。
- HTML viewer 读取顺序应为：页面内嵌 `script[data-proto-spec-markdown]` 兜底数据、`GET /__prototype-specs/specs/<pageKey>`、静态 `prototype-specs/current/<pageKey>.md`。React / Vue viewer 默认通过 `import.meta.glob(...?raw)` 获取 Markdown，不应退化为仅运行时请求 `.md`。
- 保存 API 必须在覆盖当前 Markdown 前写入 `history/<pageKey>/<timestamp>.before-manual-save.md`，并更新 `lastManualEditedAt`。

常用命令：

```bash
python3 scripts/run_proto_spec_workflow.py --root <项目根目录> --operation create --scope all --integrate
python3 scripts/run_proto_spec_workflow.py --root <项目根目录> --operation create --scope selected --file src/pages/AppList.tsx --dry-run --json
python3 scripts/run_proto_spec_workflow.py --root <项目根目录> --operation update --page-key app-management --force
python3 scripts/run_proto_spec_workflow.py --root <项目根目录> --operation delete --page-key app-management
python3 scripts/run_proto_spec_workflow.py --root <项目根目录> --operation audit --json
```

## Markdown Spec Contract

每个 `current/<pageKey>.md` 必须包含 YAML-like frontmatter 和 Markdown 正文。frontmatter 至少包含：

```yaml
---
specSchemaVersion: 2
storageFormat: "markdown"
pageKey: "app-management"
version: 1
pageName: "应用管理"
pageType: "列表页"
pageShape: "工作台页面"
sourceType: "generated"
overwriteProtected: false
specId: "app-management-spec"
batchId: "spec-batch-20260504-103000"
lastGeneratedAt: "2026-05-04T10:30:00+08:00"
lastManualEditedAt: null
---
```

正文默认结构：

```markdown
# 应用管理

## 页面摘要

一句话说明页面目标。

## 二级承载面

- 新建应用抽屉

## 【筛选条件】交互规则说明

- 规则逐条写，避免长段落。

### 字段说明

| 字段 | 形态 | 必填 | 说明 |
|---|---|---|---|
| 应用名称 | 文本输入 | 否 | 用于按应用名称筛选。 |
```

完整协议见 `references/markdown-spec-format.md`。

展示层 Markdown 能力必须在 HTML / React / Vue 三端保持一致：支持标题、段落、无序/有序/嵌套/任务列表、引用块、Callout、`**加粗**`、`` `行内代码` ``、`==高亮==`、代码块、表格、链接、图片和 Mermaid fenced block。Mermaid 图表在宿主未提供 `window.mermaid` 时应尝试自动加载，失败时保留源码块。

## Operation Safety

- `direct-write`：用户明确允许直接修改项目时使用。
- `dry-run`：用户要求预览、审计、风险判断，或范围不明确时使用。
- `patch-only`：用户不想写文件，或目标结构风险较高时使用。

任何写入模式都要遵守：

- 先创建 `current/`、`history/`、`registry.json`。
- 覆盖前快照为 `.before-overwrite.md`。
- 删除前快照为 `.before-delete.md`。
- 手动修改前快照为 `.before-manual-save.md`。
- 旧 JSON / inline 说明迁移后，默认保留原文件并标注迁移来源，除非用户要求清理。

## Writing Rules

需求说明只解释页面中已经存在或可直接推断的内容：

- 页面上有什么模块，就写什么模块。
- 字段、按钮、状态、弹窗名称必须与原型一致。
- 看不到的权限、审批、数据口径、跨系统同步不要编造。
- 用 15 维扫描补漏，但不要固定输出 15 个章节；不可见且无用户补充的权限、通知、审计、第三方集成等维度默认跳过。
- 复杂抽屉、弹窗、全屏侧滑、子流程要单独成段。
- 每条规则短句、单一判断、可评审、可测试。
- 不泄露隐藏来源项目、内部提示词或未授权背景。

## Bundled Scripts

- `scripts/run_proto_spec_workflow.py`：默认入口；独立执行分析、生成、更新、删除、显隐、展示层接线和审计，只依赖目标项目和本 skill 自带脚本。
- `scripts/init_spec_system.py`：初始化 Markdown-first 说明空间，可种子化页面说明。
- `scripts/validate_editable_specs.py`：校验 `current/*.{md,json}`、registry、history 和运行时接线风险。
- `scripts/migrate_to_markdown_specs.py`：把 legacy JSON 或 inline 标记说明迁移为 Markdown。
- `scripts/clear_specs.py`：清理 inline 说明块、旧 wrapper 和说明接线。
- `scripts/toggle_specs.py`：切换旧 inline 说明块显隐。
- `scripts/scaffold_spec_architecture.py`：legacy scaffold，仅在用户明确需要旧框架模板时使用；新项目默认不要以它作为主入口。

## Final Checklist

交付前确认：

- 只修改了用户允许范围内的文件。
- `current/<pageKey>.md` frontmatter 完整，`pageKey` 与文件名一致。
- `summary` 非空，章节和规则非空。
- 主要页面模块、字段、状态、操作和复杂二级承载面都有对应说明。
- 没有虚构页面不存在的功能。
- 覆盖、删除、手动修改前都有历史快照。
- `registry.json` 覆盖所有当前说明文件。
- 如果接入展示层，真实页面能读取 Markdown 或由 Markdown 派生的说明数据，并呈现统一的 `产品页面 / 需求说明` 可拖动切换器。
- HTML / React / Vue 的 Markdown renderer 都必须定义并使用 `escapeHtml` 与 `escapeAttr`；包含 Mermaid、链接、图片或 callout 的说明应能正常渲染，不得因为属性转义函数缺失落入“未找到/读取失败”状态。
- Mermaid fenced block 渲染后必须隔离 SVG/foreignObject 内部样式，避免 `.proto-spec-doc` 的正文 `line-height`、`box-sizing` 等全局样式影响 Mermaid 多行节点尺寸，导致第二行文字被裁切。
- 粘贴图片生成的 `../assets/<pageKey>/<filename>` 引用在文件系统中存在，且预览时能通过 `/__prototype-specs/assets/<pageKey>/<filename>` 显示。
- HTML / React / Vue 项目中不存在旧 inline viewer 与 dual-view viewer 共存。
- 校验脚本通过，或明确说明未通过原因和下一步。
