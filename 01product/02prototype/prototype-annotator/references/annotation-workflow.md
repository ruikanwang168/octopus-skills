# Annotation Generation Workflow

Use this workflow when creating annotations from a prototype and optional PRD.

## 目录

- [Inputs](#inputs)
- [Step 1: Scan Prototype](#step-1-scan-prototype)
- [Step 2: Extract PRD Signals](#step-2-extract-prd-signals)
- [Step 3: Generate Page Specs Lite When Needed](#step-3-generate-page-specs-lite-when-needed)
- [Step 4: Build Evidence Candidates](#step-4-build-evidence-candidates)
- [Step 5: Match Evidence to Elements](#step-5-match-evidence-to-elements)
- [Step 6: Select Annotation Coverage](#step-6-select-annotation-coverage)
- [Step 7: Write Markdown-First Content](#step-7-write-markdown-first-content)
- [Step 8: Preserve Manual Edits](#step-8-preserve-manual-edits)
- [Step 9: Validate](#step-9-validate)
- [Step 10: Export Reports](#step-10-export-reports)

## Inputs

- Prototype source: HTML file, static directory, React/Vue app, or exported prototype.
- Product docs: PRD, product spec, upstream page-level spec documents, meeting notes, README, or issue list.
- Product profile: optional `product-profile.json` with product type, forms, users, and enabled annotation types.
- Existing annotations: `prototype-annotator/annotations.json`, if present. Legacy `.prototype-annotations/annotations.json` is accepted during migration.

## Step 1: Scan Prototype

Run for static HTML:

```bash
python3 scripts/scan_prototype.py <prototype_path>
```

Run for React/Vue/Vite after starting the dev server:

```bash
node scripts/scan_rendered_routes.mjs <project_root> --base-url http://localhost:5173
```

Inspect `prototype-annotator/page-map.json` for:

- Page keys and paths.
- Buttons, links, inputs, forms, tables, dialogs, tabs, cards, status indicators.
- Candidate selectors and fallback text.
- Missing stable identifiers.

If the prototype is a React/Vue source project, read `references/prototype-adapters.md` and use rendered route scanning. Do not treat a static SPA `index.html` scan as coverage. Any core route with an empty `elements[]` list is a scan failure unless the rendered page is genuinely empty.

## Step 2: Extract PRD Signals

From PRD or product spec, extract:

- Page responsibilities and entry/exit.
- Main actions and secondary actions.
- Form fields and validation rules.
- State values and transition conditions.
- Permission differences by role.
- Data objects, API expectations, and table columns.
- Empty/loading/error/disabled states.
- Business flow and Mermaid diagrams.
- Open questions and assumptions.

Prefer explicit PRD facts. Mark inferred content clearly.

Also identify the product shape before choosing annotation priorities. Read `references/product-type-strategy.md` and `references/annotation-type-taxonomy.md` when the task spans B端 / enterprise, C端, SaaS, AI / Agent, data / BI, content, community, or tooling products.

If a `product-profile.json` exists, pass it when generating annotations:

```bash
python3 scripts/generate_annotations_draft.py <prototype_path> --product-profile <product-profile.json>
```

If the project already contains `prototype-specs/current/*.md` or `src/page-specs/current/*.md`, also read `references/spec-to-annotation-mapping.md` and treat those Markdown files as page-level evidence. External page specs are not annotations by themselves; use them to decide which element-level explanations are worth creating. Do not create or update those external page spec Markdown files in this workflow.

## Step 3: Generate Page Specs Lite When Needed

Skip this step unless the user explicitly wants long-lived per-page Markdown requirements owned by `prototype-annotator`.

When enabled, generate page specs before building annotation candidates:

```bash
python3 scripts/generate_page_specs.py <prototype_path> --docs <PRD.md>
```

This creates `prototype-annotator/specs/current/<pageKey>.md`. Page-level `P` annotations will later point to these files with:

```json
{
  "annotationType": "P",
  "specRef": "prototype-annotator/specs/current/P01.md",
  "contentSource": {
    "type": "markdown-file",
    "ref": "prototype-annotator/specs/current/P01.md",
    "format": "markdown"
  },
  "maintenancePolicy": "spec-owned"
}
```

Do not copy the Markdown body into `annotations.json`.

## Step 4: Build Evidence Candidates

Read `references/annotation-evidence-scan.md` before writing annotations. Generate or inspect `prototype-annotator/annotation-candidates.json` for:

- Selected elements and their evidence.
- Skipped elements and the skip reason.
- Candidate priority, kind, dimension, and source.
- Candidate `annotationType`, derived from `dimension` and `kind`.
- Missing stable selectors that should be fixed before handoff.

Only promote a candidate into an annotation when it explains business meaning, implementation-critical behavior, state, validation, permission, flow, data, or AI/automation behavior.

When `prototype-annotator/specs/current/*.md` exists, `build_annotation_candidates.py` reads those files as page-spec evidence. Element-level candidates and generated annotations may keep `source.type: "page-spec"` / `source.ref`, but that evidence link does not create ongoing synchronization with the Markdown file.

If selected candidates use fragile selectors, generate an anchor plan:

```bash
python3 scripts/suggest_data_ann_anchors.py <prototype_path>
```

Review `prototype-annotator/data-ann-plan.json` before changing source. The
plan recommends `data-ann` values and replacement selectors but does not edit
application code.

## Step 5: Match Evidence to Elements

For each scanned page:

1. Match page title, route, heading, nav label, and visible structure.
2. Match actions by button/link text and surrounding section.
3. Match form rules by label, placeholder, field name, and submit action.
4. Match table operations by column headers and row action text.
5. Match flows by route links, step labels, modal triggers, and CTA copy.

If an element cannot be matched, skip it unless it is critical to the user journey.

## Step 6: Select Annotation Coverage

Do not select annotations by fixed count. Every page should have one page-level overview annotation for reader orientation; additional annotations are only selected when they explain non-obvious rules. Treat any numeric limit as a ceiling, not a quota: low-value pages may only have the overview, simple pages usually need 3-5 annotations, and dense core pages may need 4-8.

For each page, first select one `Page overview` candidate, preferably anchored to the page `h1`. Without Page Specs Lite it should explain the page responsibility, main content, and reading focus. With Page Specs Lite, the final `P` annotation is `spec-owned` and displays the full Markdown spec instead of a summarized `contentMarkdown`.

After that, select an additional candidate only when it explains something that is not obvious from the visible UI:

- A primary CTA with non-trivial state, validation, permission, or downstream data change.
- A form/input/upload/filter/table interaction with rules the UI does not fully express.
- A state, exception, empty/loading/no-permission condition, or status transition.
- A risky or permission-sensitive operation such as delete, disable, reject, approve, publish, or role change.
- An AI/automation behavior, generation state, model/prompt boundary, retry, export, or confidence rule.
- A metric, chart, calculation, or data relationship that needs implementation context.

Repeated row actions should normally be folded into one annotation for the table operation. Avoid annotating every visible UI element, common navigation, ordinary headings, and self-explanatory buttons. Also skip cross-page chrome such as app branding, global header search, user profile entry, return-to-frontstage links, and side navigation unless the user specifically asks to document the shell itself.

## Step 7: Write Markdown-First Content

Each annotation should answer:

- Where does this page/module come from?
- What does this element mean in the product?
- What happens when the user interacts with it?
- What field rules, states, validations, permissions, risks, or dependencies matter?
- What downstream flow or data change occurs?
- How should exceptions be handled?
- What is still uncertain?

Use `references/rich-content-guide.md` for tables, highlights, and Mermaid.

New element-level annotations should include both the implementation-oriented fields and the product-semantic field:

```json
{
  "annotationType": "A",
  "kind": "interaction",
  "dimension": "Primary action",
  "topics": ["interaction", "flow"]
}
```

Do not replace `kind`, `dimension`, or `topics` with `annotationType`; older runtime and quality checks still rely on those fields.

When writing from local-rule candidates without PRD or page specs, include a `待确认` section or clear text such as `根据原型结构推断`. Do not turn inferred permissions, backend storage, notifications, audit logs, or integrations into facts.

If Page Specs Lite is enabled:

- `P` annotations use `contentSource/specRef` and `maintenancePolicy: "spec-owned"`.
- Element-level annotations keep `contentMarkdown` and `maintenancePolicy: "annotation-owned"`.
- Editing a `P` card updates `prototype-annotator/specs/current/*.md`; editing an element card updates only `annotations.json`.

## Step 8: Preserve Manual Edits

When updating an existing `annotations.json`:

- Keep existing `id` values.
- Do not overwrite `createdBy: "manual"` annotations unless the user asks.
- Preserve manually changed `target.selector`.
- Preserve annotations with `review.status: "approved"` unless the user asks for regeneration.
- Merge AI improvements into element-level `contentMarkdown` only when the target is the same and the meaning is compatible.
- Preserve `P` annotation `specRef/contentSource` when Page Specs Lite is enabled; update the Markdown file itself for page-level content changes.
- Append new annotations with the next sequence number for the page.

## Step 9: Validate

Run:

```bash
python3 scripts/validate_annotations.py <prototype_path>
```

Fix:

- Duplicate ids.
- Missing page keys.
- Empty title or body.
- Missing `contentMarkdown` on non-P annotations.
- Missing readable Markdown source on spec-owned `P` annotations.
- Selector syntax errors.
- Selectors that match no elements.

Before handoff, run the stricter quality gate:

```bash
python3 scripts/validate_annotations.py <prototype_path> --strict-quality
```

Fix semantic duplicates, repeated table row actions, and count-filling annotations before treating the result as final.

For研发交付, set `productProfile.annotationMode` to `dev-handoff`, read `references/dev-handoff-standard.md`, promote all selected candidates, then run:

```bash
python3 scripts/validate_annotations.py <prototype_path> --strict-quality --dev-handoff --fail-on-pending-review
python3 scripts/audit_annotation_coverage.py <prototype_path>
```

`productProfile` checks are project-level. For example, an AI product should include `AI` plus `HITL` or `FALLBACK` somewhere in the full annotations file, but not every page needs every AI-related type.

When Page Specs Lite is enabled, also run:

```bash
python3 scripts/sync_page_specs_to_annotations.py <prototype_path>
python3 scripts/sync_deploy_assets.py <prototype_path>       # React/Vue/Vite 项目需要同步 public/specs
python3 scripts/validate_page_specs.py <prototype_path>
```

## Step 10: Export Reports

Run:

```bash
python3 scripts/render_annotation_report.py <prototype_path>
```

This creates `annotation-report.md` and `annotation-checklist.md`. The checklist now auto-checks page coverage, product-shape coverage, and dev-handoff gaps when `annotation-candidates.json` is present.
