# Markdown Spec Format

## Goal

Use Markdown as the default long-lived source of truth for prototype page requirements. JSON may be imported, exported, or used by a runtime adapter, but the skill's default write target is `current/<pageKey>.md`.

## Directory Layout

Use `src/page-specs/` when the target project has a `src/` directory. Use `prototype-specs/` for plain HTML folders or non-standard projects.

```text
<spec-root>/
  current/
    <pageKey>.md
  assets/
    <pageKey>/
      paste-<timestamp>.png
  history/
    <pageKey>/
      <timestamp>.before-overwrite.md
      <timestamp>.before-delete.md
      <timestamp>.before-manual-save.md
  registry.json
  viewer-config.json
```

Rules:

- `current/` contains exactly one current file per page.
- `history/` stores snapshots only; runtime display must not read from history by default.
- `assets/<pageKey>/` stores images pasted or referenced by that page's Markdown spec.
- `registry.json` lists every current page that should be managed.
- `viewer-config.json` stores display preferences, not page content.

## Frontmatter

Every Markdown spec begins with a YAML-like frontmatter block.

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

Required keys:

- `specSchemaVersion`: current default is `2`.
- `storageFormat`: must be `"markdown"`.
- `pageKey`: stable page id; must match the filename.
- `version`: positive integer.
- `pageName`: readable page name.
- `pageType`: list/detail/form/tool or localized equivalent.
- `pageShape`: desktop/mobile/workspace/big-screen/aigc or localized equivalent.
- `sourceType`: `generated`, `manual`, `mixed`, `local-rule-draft`, or `ai-reviewed`.
- `overwriteProtected`: boolean.
- `specId`: stable single-page spec id.
- `batchId`: generation or migration batch id.
- `lastGeneratedAt`: ISO timestamp or null.
- `lastManualEditedAt`: ISO timestamp or null.

Optional keys:

- `contentHash`
- `sourceFile`
- `routeHint`
- `generationMode`: `model`, `local-rule`, or `manual`.
- `aiReviewRequired`: boolean; must be `true` for local-rule drafts unless `--draft-only` was explicitly requested.
- `aiReviewStatus`: `pending`, `completed`, or `skipped-draft-only`.
- `migrationSource`
- `reviewStatus`
- `owner`

When `sourceType` is `local-rule-draft`, the current AI coding agent must read the page source and rewrite or complete the Markdown body before final delivery. After review, set `sourceType: "ai-reviewed"`, `aiReviewRequired: false`, and `aiReviewStatus: "completed"`.

## Body Structure

Use this structure unless the user provides a stronger format.

```markdown
# 页面名称

## 页面摘要

一句话说明页面目标。

## 二级承载面

- 新建应用抽屉
- 高级筛选弹窗

## 【筛选条件】交互规则说明

- 筛选条件变化后，用户点击查询才刷新结果列表。
- 点击重置后恢复默认筛选条件，并清空用户输入的关键字。

### 字段说明

| 字段 | 形态 | 必填 | 说明 |
|---|---|---|---|
| 应用名称 | 文本输入 | 否 | 用于按应用名称模糊筛选。 |
```

Body rules:

- Use `#` only for the page title.
- Use `## 页面摘要` exactly for the summary section.
- Use `## 二级承载面` when drawers, modals, tabs, nested panels, or child flows exist.
- Use `## 【模块】规则说明` for sections.
- Use bullet lists or ordered lists for rules. Use ordered lists when describing user steps, state transitions, or processing sequences.
- Use `### 字段说明` and a table for fields.
- Keep each rule short and testable.

## Viewer Markdown Support

The generated HTML, React, and Vue viewers must support the same Markdown subset:

- Headings from `#` to `####`.
- Paragraphs and line breaks.
- Unordered lists, ordered lists, nested lists, and task lists.
- Blockquotes and callouts using `> [!NOTE]`, `> [!TIP]`, `> [!IMPORTANT]`, `> [!WARNING]`, `> [!CAUTION]`, `> [!TODO]`, `> [!INFO]`, or `> [!RISK]`.
- Inline `**bold**`, `` `code` ``, and `==highlight==`.
- Fenced code blocks.
- Pipe tables.
- Links and images.
- Mermaid fenced blocks. The viewer should render Mermaid diagrams when Mermaid is already present, and should attempt to load Mermaid automatically when it is missing. If rendering fails, the source code block remains visible.

Avoid raw HTML in Markdown specs. The runtime viewer escapes HTML content for safety.

## Image Assets

Use relative Markdown image paths for local spec assets:

```markdown
![粘贴图片](../assets/app-management/paste-20260618T153012Z.png)
```

Rules:

- Store page-local images under `<spec-root>/assets/<pageKey>/`.
- From `current/<pageKey>.md`, reference those images as `../assets/<pageKey>/<filename>`.
- The editable viewer may create these files by handling clipboard paste in the Markdown editor.
- Runtime previews should resolve `../assets/<pageKey>/<filename>` to `/__prototype-specs/assets/<pageKey>/<filename>` when served by the generated local server or Vite plugin.
- Do not inline pasted images as base64 in Markdown.
- `validate_editable_specs.py` should fail when a local Markdown image path does not exist.

## PageKey Rules

Create a stable key from an explicit route, page file stem, or user-provided id. Do not derive keys from mutable UI labels.

Good:

- `app-management`
- `quality-object-config`
- `portal-home`

Bad:

- `pathname.replace(...)`
- `label.toLowerCase()`
- `应用管理页面`
- `admin--admin-users`

## History Rules

Before overwriting `current/<pageKey>.md`, copy the current file into:

```text
history/<pageKey>/<timestamp>.before-overwrite.md
```

Before deleting:

```text
history/<pageKey>/<timestamp>.before-delete.md
```

Before saving a manual edit:

```text
history/<pageKey>/<timestamp>.before-manual-save.md
```

Use local time with timezone when writing frontmatter timestamps. Use filesystem-safe UTC-ish filenames by replacing `:` and `.` with `-`.

## Registry

Minimum `registry.json`:

```json
{
  "specSchemaVersion": 2,
  "storageFormat": "markdown",
  "pages": [
    {
      "pageKey": "app-management",
      "pageName": "应用管理",
      "sourceFile": "src/pages/AppManagement.tsx",
      "routeHint": "/apps"
    }
  ],
  "lastUpdated": "2026-05-04T10:30:00+08:00"
}
```

The registry should not duplicate full spec content. It is an index for discovery and validation.

## Viewer Config

Minimum `viewer-config.json`:

```json
{
  "specSchemaVersion": 2,
  "visibilityMode": "manual-toggle",
  "viewerMode": "dual-view",
  "htmlSaveMode": "file-service",
  "updatedAt": "2026-05-04T10:30:00+08:00"
}
```

Accepted `viewerMode` values:

- `dual-view`: product page and spec view are mutually exclusive.
- `inline-bottom`: legacy only; spec renders below the prototype in normal document flow when the user explicitly asks for that mode.

Do not allow `dual-view` and legacy inline viewer markers to coexist in the same project. Remove `initSpecViewer(...)`, `assets/js/spec-viewer.js`, `proto-spec-divider`, `proto-spec-badge`, `PageSpecDocInline`, and old `data-role="page-spec"` blocks before validating a dual-view integration.

Accepted `visibilityMode` values:

- `default-expanded`
- `default-hidden`
- `manual-toggle`
