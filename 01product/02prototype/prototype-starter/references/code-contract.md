# DESIGN.md to Prototype Project Contract

Use this reference when customizing the starter's product-fidelity output, including React or Vue framework prototypes.

## Authoritative Inputs

- `initialization.productMode` and `initialization.confirmationStatus`: select evidence policy and prove the document is approved for initialization.
- `tokens`: generate CSS variables in `shared/css/tokens.css`.
- `layout.contractVersion: 2` and `layout.profiles`: normalize product-form-neutral region trees, exact viewports and breakpoint behavior into `layout-model.json`, then generate only declared regions in `shared/css/product-shell.css`.
- Legacy `layout.appShell`: normalize explicit facts into `legacy-app-shell`; missing viewports or ambiguous absent regions remain blocking.
- `components`: generate reusable product component classes in `shared/css/product-components.css`.
- `pageTemplates`: generate product page pattern classes, template choices, and `AGENTS.md` page-type guidance.
- `copywriting`: preserve in the design contract; when present, generate AGENTS guidance and data-driven warning checks for message copy, dialog/form guidance, and punctuation rules.
- `legacyTokens`: preserve in the design contract; when present, derive legacy raw-value warnings from explicit `value` entries.
- `generationRules.noSource`: generate static HTML prototype shell and component rules from these entries.
- `generationRules.selfCheck`: include in generated `AGENTS.md` and compliance output.
- `technology` / `runtime`: preserve as design and source-stack context, and use them for product fidelity. Never infer the prototype output framework from these fields; use HTML by default unless the user explicitly requests `--framework react` or `--framework vue`.
- `layout.*.classNames` and `components.*.source`: generate product-specific DOM/CSS classes from these fields whenever present. Do not replace explicit product names such as `avue-*`, `basic-container`, `top-search`, or `title_new` with generic `proto-*` equivalents. These examples are product fingerprints, not global starter requirements.

The `DESIGN.md` Markdown body is authoritative when it documents shell diagrams, DOM hierarchy, calibrated behavior, source class names or anti-patterns. Read it during the first shared-system pass or when compact context conflicts; normal domain work uses `authoring-context.json`.

## Ownership Model

The default workflow is hybrid:

- Python owns deterministic scaffolding, design extraction, hashes, registries, checks, and migration safety.
- The model owns product interpretation and authors `shared/`, representative templates, and framework shell from the relevant compact domain context. It reads the complete DESIGN only for first authoring or conflict resolution.
- Generated product assets are runnable seeds, not accepted final output.
- `--deterministic-shared` keeps the legacy generator-owned behavior for tests or explicitly requested deterministic output.

In LLM mode, refreshes do not overwrite existing authored product assets. A rendered-design change marks authoring `pending-layout-review`; finalization requires the preview manifest and fresh layout/screenshot evidence.

## Generated Project Responsibilities

- `DESIGN.md`: human-readable source design system.
- `design-system/design-readiness.json`: successful readiness report. Failed readiness never creates the output project.
- `design-system/layout-model.json`: normalized v2 profiles, viewports, region trees, template bindings and pending-authoring state shared by every downstream stage.
- `design-system/authoring-context.json`: compact model-facing design domains; each authoring pass reads only the selected domain.
- `design-system/contexts/layout/<profile>.json`: one profile, its templates, referenced components and referenced tokens; this is the default model context for v2 authoring.
- `design-system/design-contract.json`: contract v4 machine extract with source hash, aggregate rendered hash, and `runtimeHashes` for tokens, shell, components, patterns, and rules. Legacy top-level mirrors remain for compatibility.
- `design-system/design-change-plan.json`: previous/current domain diff with affected page keys, shared refs, and required reconciliation actions.
- `design-system/evidence-sources.json`: persistent product evidence provenance, viewport, dimensions, DPR, and file hashes.
- `design-system/design-gaps.json`: persistent evidence-backed design-gap lifecycle ledger.
- `design-system/context-index.json`: compact task router. Future agents select design-system, new-feature, incremental, or verification context without loading every design artifact.
- `design-system/check-rules.json`: derived compliance rules generated only from fields that exist in the front matter.
- `design-system/fidelity-guardrails.json`: concise guardrail for future work, including source hash, product class fingerprints, required page metadata, shared CSS/JS, copywriting rules, legacy token warnings, and the blocking compliance command.
- `design-system/fidelity-reviews.json`: persistent review ledger keyed by product page/component path. Each approval records source/runtime hashes, page hash, shared and feature-local runtime hash, reviewed viewports, screenshot evidence hashes, reviewer, and timestamp.
- `design-system/authoring-brief.md`: project-local instructions for model-authored shared assets.
- `design-system/authoring-status.json`: pending/ready state tied to the current design source hash.
- `design-system/layout-contract.json`: v2 profile-indexed region selectors, DOM/visible count ranges including zero, containment/order, geometry, breakpoints, scroll owners and forbidden developer controls.
- `design-system/preview-manifest.json`: representative page, exact viewports, screenshot paths and bound page/runtime hashes.
- `design-system/layout-audit.html`: developer-only same-origin iframe audit harness outside product pages.
- `design-system/shared-registry.json`: reusable component, pattern, and interaction inventory with owning files and feature consumers.
- `AGENTS.md`: concise execution rules for future agents working inside the prototype project.
- `shared/css/product-*.css`: reusable product design-system layer for direct-browser HTML pages.
- `shared/js/product-icons.js`: offline local SVG icon renderer for `data-icon` elements. Generated product pages should not rely on external icon CDNs.
- `shared/js/product-shell.js`: reusable product shell interactions such as sidebar toggle, filter expansion, toast, drawer stack, and confirmation surfaces.
- `templates/*`: source templates used by `scripts/new-feature.cjs`.
- `scripts/check-prototype-compliance.cjs`: structural and design-contract checks.
- `scripts/record-fidelity-review.cjs`: records the selected profile's dynamic viewport evidence; incremental reviews also require matching baseline screenshots and a visual diff report.
- `scripts/prepare-layout-audit.cjs`: refreshes representative page and shared/runtime hashes before browser inspection.
- `scripts/finalize-design-system.cjs`: requires `--manifest`, then binds passing generic region/breakpoint reports and every declared viewport screenshot to current page/runtime hashes.
- `scripts/compare-prototype-screenshots.py`: dependency-free PNG decoder and pixel comparator. It measures only pixels outside declared change masks and emits the required incremental visual diff report.
- `scripts/manage-shared-registry.cjs`: lists or upserts promoted shared assets.
- `scripts/manage-evidence-sources.cjs`: registers and verifies screenshot/URL/source evidence.
- `scripts/manage-design-gaps.cjs`: enforces gap classifications, transitions, shared linkage, and verification.
- React/Vue projects: Vite project files under `package.json`, `vite.config.js`, `src/main.jsx|main.js`, `src/App.jsx|App.vue`, `src/prototype-registry.js`, and `src/features/*`.

## CSS Variable Naming

Use stable semantic names:

```css
--color-primary
--color-text
--font-family-base
--font-body-size
--space-lg
--radius-sm
--shadow-card
--motion-base
```

Map token references such as `{tokens.colors.primary}` to `var(--color-primary)`.

## Feature Folder Rules

HTML projects use first-level feature folders.

Every feature iteration should be a first-level folder:

```text
02-workbench-upgrade/
├── index.html
├── workbench-home.html
├── task-reminder.html
└── assets/
    ├── prototype.css
    └── prototype.js
```

Feature pages should import the shared layer with paths relative to the feature folder:

```html
<link rel="stylesheet" href="../shared/css/tokens.css">
<link rel="stylesheet" href="../shared/css/product-shell.css">
<link rel="stylesheet" href="../shared/css/product-components.css">
<link rel="stylesheet" href="../shared/css/product-patterns.css">
<link rel="stylesheet" href="../shared/css/prototype-meta.css">
<link rel="stylesheet" href="./assets/prototype.css">
<script src="../shared/js/product-icons.js"></script>
<script src="../shared/js/product-shell.js"></script>
```

Generated list pages should expose generic roles such as `data-prototype-role="search-region"` and `data-prototype-role="list-region"`. Compliance uses these roles plus design-derived product fingerprints, so the starter stays generic while still enforcing high-fidelity product structure.

Every generated product page should also expose the design source anchor:

```html
data-design-source-sha="<DESIGN.md sha256>"
data-design-runtime-sha="<rendered design sha256>"
data-design-contract-version="3"
```

The source hash is traceability metadata. The rendered-design hash covers visual/runtime fields and body guidance. A source-only change may warn without invalidating a page when the rendered-design hash is unchanged; a rendered-design change blocks stale pages.

If `layout`, `components`, `pageTemplates`, `generationRules`, or the Markdown body define concrete class names, `check-rules.json` records them under `productFidelity.classFingerprints`. Product pages must preserve at least one relevant product fingerprint so later work cannot silently fall back to a generic prototype shell.

`productFidelity.roleRequirements` strengthens this check by requiring the correct classes for each structural role. HTML pages must contain the configured project shell and page roles. React/Vue projects validate project shell roles in `App.jsx`/`App.vue` and page roles in each feature component.

After inspecting every viewport declared by the page's layout profile, record approval and run the release gate:

```bash
node scripts/record-fidelity-review.cjs 02-feature/page.html \
  --viewport mobile,fidelity-evidence/current-mobile.png,390,844
node scripts/check-prototype-compliance.cjs --release
```

The release gate invalidates approval when the page/component, rendered design, shared CSS/JS, feature-local assets, framework shell, or screenshot evidence changes.

The root `index.html` is the prototype library entry and must link to each feature folder `index.html`.

## Independent Feature Scenarios

When a drawer, modal, side panel, confirmation dialog, import wizard, or batch-operation surface carries an independent business goal, generate it as a feature scenario instead of leaving it only as an implicit interaction inside the parent page.

Use `scripts/new-feature.cjs --manifest feature-manifest.json` for these cases. Each scenario should define:

- `title`: visible Chinese title.
- `pageKey`: stable identifier used by `prototype-spec-annotator` for `prototype-specs/current/<pageKey>.md`.
- `surface`: one of `drawer`, `modal`, `side-panel`, or `confirm`.
- `parentPageKey`: optional in the manifest; defaults to the parent page `pageKey`.

Generated HTML pages expose:

```html
data-page-key="user-new-drawer"
data-page-kind="scenario"
data-parent-page-key="user-list"
data-surface="drawer"
```

## Requirement Gate and Placeholder Pages

Page and scenario descriptors use the same requirement gate. Confirmed new pages are generated as non-releasable scaffolds only when both conditions are true:

- `requirementStatus` is exactly `confirmed`.
- `description` contains a concrete requirement.

All other descriptors, including legacy `--pages "页面名:文件名"`, generate an accessible placeholder. A placeholder preserves `pageKey`, `kind`, `surface`, and `parentPageKey`, adds `data-requirement-status="needs-input"` and `data-generation-mode="placeholder"`, and contains no inferred business controls or mock data. React/Vue registry entries persist `requirementStatus` and `generationMode` as well.

Normal compliance lists placeholders as warnings and skips business-page structure, product fingerprint, and fidelity-review checks for them. Release compliance fails if any placeholder exists; there is no bypass flag.

Release compliance also fails while a confirmed page remains `data-generation-mode="scaffold"`. After real business authoring it must become `authored`.

## Incremental Baseline Contract

Use manifest `mode: "incremental"` only for upgrades with an approved local page/component baseline. Each confirmed page requires `baseline.path`, declared `changes`, a non-empty `preserve` list, and `allowedFiles`.

The feature generator copies the baseline page/component and local supporting assets rather than using a generic template. It writes `incremental-contract.json` with baseline and prepared hashes. Release checks require the target to change, reject changes outside `allowedFiles`, verify the source baseline remains unchanged, and require baseline/current evidence for the profile's declared viewports plus an approving visual diff report.

Generate the report with `scripts/compare-prototype-screenshots.py`. Masks must cover only the declared change regions; the script rejects screenshots with mismatched dimensions, masks covering the entire image, or excess pixel differences outside masks.

## Reconstruction Contract

Use manifest `mode: "reconstruction"` when product screenshots, URLs, recordings, or source evidence exist without an approved local prototype baseline. Register evidence first, reference its IDs from each page, author `reconstruction-scaffold` into `reconstruction-authored`, and record reference/current evidence for every `claim: fidelity` viewport plus a comparison report generated with `--mode reconstruction`.

Pages and reviews may declare `designDomains` and `sharedRefs`. Contract v4 computes `data-design-profile-sha` from those domain hashes. Legacy pages without these fields depend on all design domains.

HTML projects flatten scenarios into standalone files, such as `user-new-drawer.html`, while preserving the parent page context and opening the declared surface by default. React/Vue projects flatten scenarios into registry page entries and direct hash routes, such as `#/feature/02-user-management/user-new-drawer`.

React/Vue projects use `src/features/NN-feature-name/` instead. `scripts/new-feature.cjs` creates page components and updates `src/prototype-registry.js`:

```text
src/features/02-workbench-upgrade/
├── WorkbenchHome.jsx|WorkbenchHome.vue
└── TaskReminder.jsx|TaskReminder.vue
```

The root `index.html` is the Vite entry and should not be edited into a static feature library. The app shell reads from `src/prototype-registry.js`.

## Refresh Rules

Use `--plan-only` before refreshing to preview managed file changes. Use `--backup-managed` with `--force` when refreshing an existing project to copy overwritten managed files into `.prototype-starter-backups/`.

Refreshing from a changed `DESIGN.md` overwrites deterministic governance files such as:

- `DESIGN.md`
- `AGENTS.md`
- `design-system/design-contract.json`
- `design-system/design-readiness.json`
- `design-system/authoring-context.json`
- `design-system/layout-contract.json`
- `design-system/check-rules.json`
- `design-system/context-index.json`
- `design-system/fidelity-guardrails.json`
- `design-system/fidelity-reviews.json`
- `scripts/extract-design-contract.py`
- `scripts/new-feature.cjs`
- `scripts/check-prototype-compliance.cjs`
- `scripts/compare-prototype-screenshots.py`
- `package.json`, `vite.config.js`, and `src/main.jsx|main.js` for React/Vue projects

Default LLM mode protects existing `shared/css/*`, `shared/js/*`, `templates/*`, representative preview pages, `src/App.jsx|App.vue`, and `src/styles.css`. The model reconciles them deliberately and re-runs prepare, browser audit, screenshots and manifest finalization. Legacy ready state migrates to `pending-layout-review`. `--deterministic-shared` restores generator ownership for shared seed files but does not bypass layout evidence.

Refreshing must not overwrite existing numbered feature folders, HTML root `index.html`, or React/Vue `src/prototype-registry.js` unless the user explicitly asks for a migration or reset.
