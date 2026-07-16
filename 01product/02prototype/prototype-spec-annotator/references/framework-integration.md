# Framework Integration

## Goal

Expose Markdown specs inside the prototype without turning the spec into a business feature or overlay.

Integration is the default deliverable. The expected output is a "product page + editable spec" dual-view. Only skip integration when the user explicitly requests offline Markdown files only (e.g., "只生成 Markdown", "不需要页面展示", "离线说明即可", "不接入页面"). When intent is unclear, integrate.

Preferred command:

```bash
python3 scripts/run_proto_spec_workflow.py --root <project> --operation integrate --scope all
```

For generation plus integration in one pass:

```bash
python3 scripts/run_proto_spec_workflow.py --root <project> --operation create --scope all --integrate
```

The runner is independent and self-contained. Do not copy or import source files from unrelated tools, products, or applications at runtime.

## General Rules

- Specs must be visually and structurally separate from the product page.
- HTML / React / Vue integrations should use the same default `dual-view`: product page and spec page are mutually exclusive.
- The `产品页面 / 需求说明` switcher must be draggable in HTML, React, and Vue. Default placement is fixed top-center. Pressing anywhere on the switcher and moving more than about 5px enters drag mode; a drag must suppress the following click so view switching only happens when the user clicked without dragging. Do not persist the dragged coordinates; refresh returns to the default position.
- Use `inline-bottom` only when the user explicitly asks for legacy document-flow output or a migration-compatible read-only view.
- Do not place the full spec in Drawer, Dialog, Sheet, Popover, Tooltip, or a floating overlay.
- Runtime adapters may convert Markdown to JSON internally, but Markdown remains the source of truth.
- Before writing dual-view, remove old inline viewers such as `initSpecViewer(...)`, `assets/js/spec-viewer.js`, `proto-spec-divider`, `proto-spec-badge`, `PageSpecDocInline`, and old `data-role="page-spec"` blocks.
- If an integration cannot be done safely, output a patch-only recommendation.

## React

Recommended files for a multi-page Vite/React prototype:

```text
src/page-specs/current/*.md
src/page-specs/registry.json
src/components/proto-spec/PageSpecDoc.tsx
src/components/proto-spec/PageSpecRouteShell.tsx
src/components/proto-spec/proto-spec.css
```

Minimum behavior:

- route map resolves explicit routes to stable `pageKey`s.
- spec loader reads `current/<pageKey>.md` or a generated manifest derived from Markdown.
- shell renders segmented controls: `产品页面` and `需求说明`.
- segmented controls are draggable from any point on the switcher, keep normal click switching when movement stays within the drag threshold, and reset to top-center after refresh.
- viewer renders headings, unordered/ordered/nested/task lists, blockquotes, callouts, highlights, tables, images, code blocks, and Mermaid fences without breaking layout.
- edit controls use the shared `.proto-spec-*` CSS and expose the same `编辑 / Markdown / 预览 / 保存 / 取消` flow as HTML and Vue. `预览` renders the current draft only; `保存` persists through `/__prototype-specs/specs/<pageKey>`.
- Markdown editor paste supports clipboard images by saving them through `/__prototype-specs/assets/<pageKey>`, inserting `../assets/<pageKey>/<filename>`, and rendering that path through `/__prototype-specs/assets/<pageKey>/<filename>`.

Avoid:

- deriving `pageKey` from `location.pathname.replace(...)`
- appending `<PageSpecDoc />` directly under a shared `<Outlet />`
- putting the full spec into a drawer
- leaving old inline `PageSpecDocInline` or `proto-spec-divider` sections in the same route

## Vue

Recommended files:

```text
src/page-specs/current/*.md
src/page-specs/registry.json
src/components/proto-spec/PageSpecDoc.vue
src/components/proto-spec/PageSpecRouteShell.vue
src/components/proto-spec/proto-spec.css
```

Patch around `router-view` / `RouterView` only when the target App component has a clear anchor. If no safe anchor exists, output patch-only guidance.

Minimum behavior is the same as React: shared switcher labels, shared `.proto-spec-*` document-reader styles, Markdown rendering for headings, lists, task lists, blockquotes, callouts, highlights, tables, images, code blocks, Mermaid fences, current-draft preview, clipboard image paste through `/__prototype-specs/assets/<pageKey>`, and persistent save through `/__prototype-specs/specs/<pageKey>` when running the Vite dev server with the generated plugin.

The Vue switcher must use the same drag threshold and click-suppression behavior as React and HTML.

Remove old inline Vue spec components before wrapping `router-view`; dual-view and inline-bottom must not coexist in the same page.

## Static HTML

Use `prototype-specs/current/*.md` and one of these display approaches:

- Generate a separate spec viewer page that reads Markdown files.
- Inject a small dual-view runtime into selected HTML files.
- Add an external link from the prototype page to the Markdown spec.

For static HTML, the runner writes `proto-spec-server.mjs` when integrating. Use `node proto-spec-server.mjs --port 8080` from the prototype project root for static preview and local save API. The server must support both `GET /__prototype-specs/specs/<pageKey>` for reading Markdown and `PUT/POST/PATCH /__prototype-specs/specs/<pageKey>` for saving Markdown. It must also support `POST /__prototype-specs/assets/<pageKey>` for clipboard image paste and `GET /__prototype-specs/assets/<pageKey>/<filename>` for rendering saved images. When serving an HTML page with the dual-view runtime, it should also inject a nearby `<script type="application/json" data-proto-spec-markdown="<pageKey>">...</script>` fallback so the viewer can still render if the browser or deployment blocks direct `.md` static-resource reads. Do not claim persistent editing if the page is opened directly from `file://` or only uses memory/localStorage.

The HTML injected viewer should match the React/Vue viewer labels and visual classes: `产品页面`, `需求说明`, `.proto-spec-switcher`, `.proto-spec-doc`, and `编辑 / Markdown / 预览 / 保存 / 取消`. Its Markdown renderer must support the same headings, lists, task lists, blockquotes, callouts, highlights, tables, images, code blocks, and Mermaid behavior as React/Vue. The HTML renderer must define both `escapeHtml` and `escapeAttr`; Mermaid, links, images, and callout classes all need attribute escaping and must not throw at render time. The shared `.proto-spec-*` CSS must isolate Mermaid SVG/foreignObject internals from document typography rules such as `line-height` and `box-sizing`, otherwise multi-line Mermaid node labels can be clipped. Its switcher must support the same draggable top-center reset behavior as React/Vue. Its preview mode must render the unsaved draft, not the last saved Markdown. Its editor must support clipboard image paste with the same asset directory and API contract as React/Vue.

The runner should remove old static viewer files and calls (`assets/js/spec-viewer.js`, `initSpecViewer(...)`, embedded `/* Proto Spec Viewer */` styles) before injecting the new dual-view runtime.

## Runtime Loader Options

Choose the smallest option that fits the project:

1. `fetch("/prototype-specs/current/<pageKey>.md")`
2. `import.meta.glob("./current/*.md", { as: "raw" })`
3. generated manifest file from Markdown
4. local dev API for save/edit workflows

For HTML dual-view, prefer an embedded JSON Markdown fallback first, then same-origin `GET /__prototype-specs/specs/<pageKey>`, then static `.md` fetches. For React/Vue, prefer `import.meta.glob(...?raw)` so specs are bundled with the app and not dependent on runtime `.md` fetches. If the target build tool cannot import raw Markdown, prefer `fetch` in dev/static preview or generate a manifest during scaffolding.
