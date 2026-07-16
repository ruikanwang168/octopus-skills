# Framework Skeleton Selection

> Legacy note: these skeletons predate the Markdown-first protocol. For new projects, first create `current/<pageKey>.md` specs and read `framework-integration.md`; use these skeletons only when the user explicitly asks for old inline/framework scaffolding or when migrating an existing skeleton.

在开始写代码前，先从这里选定唯一输出骨架。新项目和默认集成应优先读 `framework-integration.md` 并使用统一 `dual-view`，本文件只用于识别 legacy skeleton 或处理用户明确要求的非默认输出。

不要先改代码、再回头解释结构。顺序必须是：

1. 判断框架
2. 判断展示模式
3. 选定一个骨架
4. 按骨架落目录、组件、挂载点和 `pageKey`

如果只是需要先把说明系统支持层和示例接线落到项目里，可以直接运行：

```bash
python3 scripts/scaffold_spec_architecture.py --root <project> --framework react --layout fixed-shell --page-key market --route-path /market
```

这个脚本只生成支持层、示例接线文件和 HTML 资产，不会自动改真实业务页。

## 1. 判断框架

- React：存在 `.tsx/.jsx`、`react-router-dom`、函数组件、`import.meta.glob`
- Vue：存在 `.vue`、`vue-router`、`<template>` / `<script setup>`
- HTML：独立 `.html` 页面、无 SPA 框架，或仅用原生 JS / jQuery / Axure 导出结构

## 2. 判断展示模式

- 固定视口壳层：
  - 有 `h-screen`、`min-h-0`、`overflow-hidden`
  - 有侧栏、顶栏、`Outlet`
  - 页面内容滚动发生在内部容器
- 正常文档流：
  - `main/article/section` 自然向下撑开
  - 页面末尾追加内容不会被裁切
  - 没有整页级内部滚动壳层

## 3. 选择矩阵

- React + 固定视口壳层：
  读 [skeleton-react-fixed-shell-editable.md](skeleton-react-fixed-shell-editable.md)
- React + 正常文档流 legacy：
  读 [skeleton-react-document-flow-inline.md](skeleton-react-document-flow-inline.md)
- Vue + 固定视口壳层：
  读 [skeleton-vue-fixed-shell-editable.md](skeleton-vue-fixed-shell-editable.md)
- Vue + 正常文档流 legacy：
  读 [skeleton-vue-document-flow-inline.md](skeleton-vue-document-flow-inline.md)
- HTML + 固定视口壳层：
  读 [skeleton-html-fixed-shell-toggle.md](skeleton-html-fixed-shell-toggle.md)
- HTML + 正常文档流 legacy：
  读 [skeleton-html-document-flow-inline.md](skeleton-html-document-flow-inline.md)

如果需要先按骨架生成支持层，再手动接业务页，优先运行 `scripts/scaffold_spec_architecture.py`，参数与这里选出的框架和布局保持一致。

## 4. 选型规则

- 一次任务只能选一个主骨架，不要混用两套挂载方式。
- 默认集成必须选 `dual-view`；`inline-bottom` 只能在用户明确要求 legacy 文档流或只读迁移输出时使用。
- **强制要求**：对于多页面项目，必须优先选定 `Editable` 相关的骨架，并运行 `scripts/init_spec_system.py` 初始化。
- 如果项目要求后续持续维护说明，React / Vue 默认保留 `current/history` 数据层，即使展示模式是正常文档流，也不要退化成只写静态 HTML 块。
- 纯 HTML 项目默认使用 runner 写入的 `proto-spec-server.mjs` 提供本地预览和保存 API；只有用户明确要求 `file://` 直开或无法启动本地服务时，才降级为只读 inline / toggle 说明，并明确标注不可持久编辑。
- 切换到 `dual-view` 前必须清理旧 inline viewer：`initSpecViewer(...)`、`assets/js/spec-viewer.js`、`proto-spec-divider`、`proto-spec-badge`、`PageSpecDocInline`、旧 `data-role="page-spec"` 区块。

## 5. 直接失败的情况

命中以下任一情况，说明没有正确使用骨架：

- 在共享 `Layout` / `Outlet` 里直接挂 `<PageSpecDoc />`
- 主说明藏在 `Drawer` / `Sheet` / `Dialog` / `Popover`
- `pageKey` 从 `pathname.replace(...)`、导航文案、标题文本临时推导
- 目录结构和挂载方式一半像 fixed-shell，一半像 document-flow
- `viewer-config.json` 是 `dual-view`，但页面仍加载旧 inline viewer
- 代码已经写完，仍然说不清“本次到底按哪个骨架实现”

## 6. 如果没有骨架适配

如果项目明显不属于以上六类：

- 不要临场发明新的默认架构
- 先输出补丁建议或插入片段
- 同时说明缺失的是哪一类骨架
- 后续再为这类项目单独补参考骨架
