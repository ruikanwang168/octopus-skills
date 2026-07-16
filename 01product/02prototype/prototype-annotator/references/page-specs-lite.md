# Page Specs Lite

当用户希望 `prototype-annotator` 同时维护“每页长期需求说明文档”时启用本模式。

## 目标边界

`Page Specs Lite` 是 `prototype-annotator` 自有的轻量页面说明资产，不是 `prototype-spec-annotator` 的 `prototype-specs/current/*.md` 或 `src/page-specs/current/*.md`。

- JSON 继续负责可视化标注层：selector、surface、显隐、编号、编辑回写和标注卡片。
- Markdown 负责完整页面说明：页面摘要、核心内容、二级承载面、模块规则、状态异常和待确认问题。
- `P` 页面级说明标注直接指向并渲染整篇 Markdown，是 `spec-owned` 引用，不再维护摘要版正文。
- 元素级标注是 `annotation-owned`，首次生成可以参考 Markdown 页面说明，后续新增、编辑、删除只维护 `annotations.json`。
- 外部 PRD、产品说明书、用户故事、业务信息和旧 page specs 只作为生成证据来源。

## 目录结构

```text
prototype-annotator/
  annotations.json
  specs/
    current/
      <pageKey>.md
    history/
      <pageKey>/
        latest.before-overwrite.md
    registry.json
```

默认历史策略是每页只保留最近一次覆盖前快照。需要更多快照时给 `generate_page_specs.py` 传 `--history-limit 5`。

## Markdown 协议

每个 `current/<pageKey>.md` 使用轻量 frontmatter：

```md
---
specSchemaVersion: 1
storageFormat: "markdown"
pageKey: "P01"
version: 1
pageName: "应用管理"
pageType: "列表页"
pageShape: "桌面端页面"
path: "index.html"
route: "/index.html"
sourceType: "generated"
overwriteProtected: false
lastGeneratedAt: "2026-07-07T00:00:00Z"
lastManualEditedAt: null
---
```

frontmatter 是页面说明的存储元数据，只在编辑模式、源码文件或调试场景中保留；运行时预览、页面级 `P` 标注卡片和导出阅读视图不应把 `specSchemaVersion`、`pageKey`、`lastGeneratedAt` 等 frontmatter 字段渲染为正文。

正文推荐结构：

```md
# 页面名称

## 页面摘要

## 核心内容

## 二级承载面

## 【筛选条件】交互规则说明

## 【结果区】显示规则说明

## 【功能操作】交互规则说明

## 业务流程

## 状态与异常

## 待确认
```

章节按页面真实内容裁剪，不强制输出所有模块。必须保留 `页面摘要` 和 `待确认`。

## Markdown 能力

页面说明和元素级标注共用运行时 Markdown 渲染链路，支持：

- `#` 到 `######` 标题层级。
- `**加粗**`、`*斜体*`、`==高亮==`、行内代码。
- 代码块和 `mermaid` 代码块。
- 表格、图片、引用、有序列表和无序列表。

图片引用仅支持 `/prototype-annotator/assets/...`、`./prototype-annotator/assets/...`、兼容旧路径的 `.prototype-annotations/assets/...`，以及安全的 HTTP(S) URL。浏览器内粘贴图片时，写入 API 会保存到 `prototype-annotator/assets/` 并插入 `/prototype-annotator/assets/...`。

## 工作流

```bash
python3 scripts/generate_page_specs.py <prototype_path> --docs <PRD.md>
python3 scripts/sync_page_specs_to_annotations.py <prototype_path>
python3 scripts/validate_page_specs.py <prototype_path>
```

完整标注工作流中，建议先生成页面说明，再把页面说明作为元素级标注首次生成证据：

```bash
python3 scripts/scan_prototype.py <prototype_path>
python3 scripts/build_product_context.py <prototype_path> --docs <PRD.md>
python3 scripts/generate_page_specs.py <prototype_path> --docs <PRD.md>
python3 scripts/build_annotation_candidates.py <prototype_path> --docs <PRD.md>
python3 scripts/generate_annotations_draft.py <prototype_path> --audience product-review
python3 scripts/sync_page_specs_to_annotations.py <prototype_path>
python3 scripts/sync_deploy_assets.py <prototype_path>       # React/Vue/Vite 项目需要同步 public/specs
python3 scripts/validate_page_specs.py <prototype_path>
python3 scripts/validate_annotations.py <prototype_path> --strict-quality
```

## 覆盖保护

- 覆盖已有 spec 前，默认写入 `history/<pageKey>/latest.before-overwrite.md`。
- `overwriteProtected: true` 或 `lastManualEditedAt` 非空时，默认跳过覆盖。
- 用户明确确认覆盖后，才使用 `--force`。
- `--history-limit 0` 表示不写快照；仅在临时草稿或外部 Git 已可靠覆盖时使用。

## P 标注同步规则

`sync_page_specs_to_annotations.py` 会为每页创建或更新一条页面级 `P` 标注：

```json
{
  "annotationType": "P",
  "dimension": "Page overview",
  "source": {
    "type": "page-spec",
    "ref": "prototype-annotator/specs/current/P01.md"
  },
  "specRef": "prototype-annotator/specs/current/P01.md",
  "contentSource": {
    "type": "markdown-file",
    "ref": "prototype-annotator/specs/current/P01.md",
    "format": "markdown"
  },
  "maintenancePolicy": "spec-owned"
}
```

同步脚本只创建或更新 `P` 标注的引用字段，不写 `contentMarkdown` 正文。人工创建或手动 selector 的 `P` 标注默认不覆盖，除非传 `--force`。

页面级 `P` 标注是页面说明入口，不是普通元素标注。运行时页面徽标显示 `P`，侧栏在“页面说明”分组中展示 `[P]`，导出报告显示 `P`；它不占用元素标注的数字序号。元素级标注和 surface 内部标注按当前页面或当前打开二级界面上下文连续显示 `1, 2, 3...`。

元素级标注可保留下面的证据字段，表示首次生成参考了页面说明：

```json
{
  "source": {
    "type": "page-spec",
    "ref": "prototype-annotator/specs/current/P01.md#【功能操作】交互规则说明"
  },
  "maintenancePolicy": "annotation-owned"
}
```

这类元素级标注后续与 Markdown 脱钩。只有用户显式要求“根据最新 Markdown 重新生成标注”时才重新生成，并应保护人工标注和人工 selector。

## 浏览器内编辑

- 静态 HTML 使用 `scripts/serve_annotation_review.py` 打开时，`P` 编辑器保存到 `prototype-annotator/specs/current/*.md`，并记录 `history.jsonl`。
- React/Vue/Vite 项目接入 `prototypeAnnotatorWritePlugin()` 后，`P` 编辑器保存源码目录下的 `prototype-annotator/specs/current/*.md`，并同步 `public/prototype-annotator/specs/current/*.md`。
- 普通静态服务或未接入 Vite 写入插件时，`P` 编辑器只能把修改暂存在浏览器 `localStorage`，界面必须明确提示未写入项目文件。
- 图片粘贴统一写入 `prototype-annotator/assets/`，Markdown 内引用 `/prototype-annotator/assets/...`。

## 校验重点

`validate_page_specs.py` 会检查：

- `page-map.json` 中每个 `pageKey` 是否有 `current/<pageKey>.md`。
- frontmatter 的 `pageKey` 是否与文件名一致。
- `registry.json` 是否覆盖当前说明文件。
- `annotations.json` 是否有对应页面级 `P` 标注并引用 spec。
- `P` 标注是否使用 `contentSource.type = "markdown-file"` 和 `maintenancePolicy = "spec-owned"`。
- React/Vue/Vite 发布路径下的 `public/prototype-annotator/specs/` 是否存在并与源文件同步。
