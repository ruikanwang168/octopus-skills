---
name: prototype-generator
description: >-
  Process-control skill for AI-assisted product prototype generation from
  requirement documents. Diagnoses input, plans pages and interactions, produces
  review/index artifacts, generates prototypes page-by-page, and runs
  completeness checks. Use when generating multi-page prototypes from PRD,
  specs, user stories, or requirement docs in Cursor, Codex, or Claude Code.
  Works standalone, and automatically enters prototype-starter compatible mode
  when the target directory contains DESIGN.md, design-system/, shared/, and
  scripts/new-feature.cjs.
---

# prototype-generator

## Purpose

`prototype-generator` is a process-control skill for AI-assisted product prototype generation.

Its final goal is to generate a complete, runnable or previewable product prototype from a requirement document, while preventing missing pages, sub-pages, dialogs, drawers, routes, and deep interactions.

This skill must work with or without `prototype-starter`. Do not require the user to initialize a starter workspace first. If a starter workspace is detected, use it as an enhanced generation environment; otherwise continue in standalone mode.

This skill does not ask the AI to generate all prototype pages at once. Instead, it controls the complete generation process through:

- Input diagnosis
- Function catalog extraction
- Page list and page relationship planning
- Human review document
- Executable prototype index
- Page-by-page generation
- Task status tracking
- Generated file recording
- Route and interaction verification
- Final completeness check

## Workspace Detection

Before generating prototype files, inspect the target directory.

Treat the target as a `prototype-starter` workspace only when it contains the starter signals below:

```text
DESIGN.md or design.md
design-system/
shared/
scripts/new-feature.cjs
```

If these files do not exist, continue in standalone mode. Do not stop and ask the user to run `prototype-starter`.

### Standalone Mode

Use standalone mode when no starter workspace is detected. In this mode:

1. Diagnose the requirement input.
2. Generate `prototype-index-review.md`.
3. Generate confirmed `prototype-index.md`.
4. Generate prototype files page by page.
5. Maintain `prototype-generation-log.md`.
6. Run `prototype-completeness-check.md`.
7. Keep the result runnable or previewable using the selected or inferred stack.

### Prototype-Starter Compatible Mode

Use starter-compatible mode when a starter workspace is detected. In this mode, this skill remains responsible for page coverage and task control, while starter assets remain responsible for product fidelity and project structure.

Additional rules:

1. Read root `DESIGN.md` or `design.md` as product design constraints.
2. Read `design-system/fidelity-guardrails.json` when present.
3. Read `design-system/shared-registry.json` when present.
4. Generate `feature-manifest.json` from confirmed, unblocked tasks in `prototype-index.md`.
5. Prefer `node scripts/new-feature.cjs --manifest <feature-manifest.json>` to create page and scenario skeletons.
6. Generated pages must reuse starter shared CSS/JS assets.
7. Generated pages must preserve starter metadata such as `data-page-key`, `data-page-kind`, `data-parent-page-key`, `data-surface`, `data-design-source-sha`, and `data-design-contract-version`.
8. Run `node scripts/check-prototype-compliance.cjs` when available.
9. In the final completeness check, verify both requirement coverage and starter compatibility.

Starter-compatible mode must not create pages, dialogs, drawers, side panels, confirmations, routes, or registry entries outside the confirmed `prototype-index.md`. If a missing surface is discovered, add it to the index as `Needs Confirmation` before generating it.

## Final Goal

The final output of this skill is a complete product prototype.

The review document, prototype index, task table, generation log, and completeness check are intermediate control artifacts. They exist to ensure that the final prototype does not miss required pages, sub-pages, dialogs, drawers, states, routes, or core interactions.

Depending on the user's technical stack and project context, the final prototype may include:

- React / Vue / HTML page files
- Layout components
- Route configuration
- Page components
- Dialogs and drawers
- Mock data
- Navigation interactions
- Table and form interactions
- Basic empty, loading, success, and error states
- A runnable or previewable prototype project

## Core Principle

Do not only control the input. Control the output process.

The AI must:

1. Diagnose the input document before planning.
2. Extract or infer function modules.
3. Extract or infer pages, sub-pages, dialogs, drawers, and interactions.
4. Mark inferred pages and uncertain interactions explicitly.
5. Generate a human review document before coding.
6. Generate an executable `prototype-index.md` after human review.
7. Generate the prototype page by page.
8. Update task status and generated files after each task.
9. Return to the index before continuing.
10. Run a final completeness check before declaring the prototype complete.

## When to Use

Use this skill when:

- The user provides a product specification, PRD, functional requirement, user story, requirement research note, pre-sales solution, or other requirement document.
- The user wants an AI coding agent to generate a product prototype.
- The prototype contains multiple modules, pages, sub-pages, dialogs, drawers, or complex flows.
- The user wants to avoid missing pages or hidden interactions.
- The AI should not generate everything in one shot.
- The user needs a controlled, inspectable, page-by-page prototype generation process.

## Supported Inputs

This skill accepts any document that contains enough information to plan and generate a product prototype.

Supported input documents include, but are not limited to:

- Product specification
- PRD
- Functional requirements document
- User stories
- Business requirements document
- Requirement research notes
- Pre-sales solution document
- Business process document
- Page description document
- Existing prototype notes
- Research meeting notes
- Development requirement document

The input document does not need to follow a fixed format. However, it should contain or allow the AI to infer:

- Product or business background
- User roles
- Function modules
- Page or function entry points
- Business workflows
- Page relationships
- Core interactions
- Data objects
- Page components
- Generation scope
- Technical stack
- Design guidelines

## Optional Inputs

The user may also provide:

- `DESIGN.md` or other design system documents
- Existing project directory structure
- Existing prototype source code
- Screenshots of current or reference pages
- Technical stack requirements
- UI component library requirements
- Generation scope constraints
- Existing route configuration
- Existing page files
- Existing `prototype-index.md` or `prototype-index-review.md`

## Default Output Files

Unless the user requests otherwise, generate or maintain the following files:

```text
prototype-index-review.md
prototype-index.md
prototype-generation-log.md
prototype-completeness-check.md
```

Optional supporting files:

```text
prototype-input-diagnosis.md
prototype-page-map.md
page-task-execution.md
feature-manifest.json
```

The final delivery output should be the generated prototype project or generated prototype files.

## Execution Modes

The skill supports the following execution modes:

| Mode | Description |
|---|---|
| `interactive` | Default mode. Confirm key checkpoints with the user. |
| `auto` | Automatically generate index and pages when assumptions are low-risk. |
| `review-first` | Only generate review document and index. Do not generate prototype pages. |
| `strict` | Stop when key information is missing. Do not infer major content. |
| `draft` | Generate a hypothesis-based prototype draft and mark uncertain items clearly. |

Default mode:

```text
interactive
```

## Input Diagnosis Rules

Before generating any page index or prototype code, diagnose the input document.

The diagnosis should determine:

1. What type of document the user provided.
2. Whether the input contains enough information to plan prototype generation.
3. Which information is explicitly stated.
4. Which information must be inferred.
5. Which information is missing and requires confirmation.
6. Whether the skill should continue automatically or pause for human review.

### Input Maturity Levels

| Level | Description | Default handling |
|---|---|---|
| L0 | Information is severely insufficient. Only an idea or one-line description is available. | Generate missing information questions and optional hypothesis draft. |
| L1 | Function description exists, but pages, flows, and interactions are unclear. | Generate a draft index with many confirmation items. |
| L2 | Function modules and some page or interaction clues exist. | Generate initial review document and mark inferred items. |
| L3 | Page, workflow, interaction, and field information are mostly complete. | Generate review document and executable index. |
| L4 | Requirements, design guidelines, technical stack, and project structure are available. | Generate an execution-ready index and prototype tasks. |

### Required Diagnosis Output

Output the diagnosis in this structure:

```markdown
# Input Diagnosis

## 1. Document Type

- Detected document type:
- Reason:

## 2. Input Maturity Level

- Level:
- Explanation:

## 3. Information Completeness

| Information Item | Status | Notes |
|---|---|---|
| Product / business background | Complete / Partial / Missing |  |
| User roles | Complete / Partial / Missing |  |
| Function modules | Complete / Partial / Missing |  |
| Page clues | Complete / Partial / Missing |  |
| Business workflow | Complete / Partial / Missing |  |
| Page relationships | Complete / Partial / Missing |  |
| Core interactions | Complete / Partial / Missing |  |
| Data objects | Complete / Partial / Missing |  |
| Fields | Complete / Partial / Missing |  |
| Generation scope | Complete / Partial / Missing |  |
| Technical stack | Complete / Partial / Missing |  |
| Design guidelines | Complete / Partial / Missing |  |
| Existing project structure | Complete / Partial / Missing |  |

## 4. Explicitly Extracted Information

- ...

## 5. Inferred Information

- ...

## 6. Missing or Uncertain Information

- ...

## 7. Processing Strategy

- Explicitly stated pages will be included directly.
- Pages inferred from operations will be included and marked as `Inferred`.
- Common product-pattern pages will be included only when useful and marked as `Needs Confirmation`.
- Missing fields or unclear interactions will be marked as `Needs Input`.
- Do not silently ignore potential pages, sub-pages, dialogs, drawers, or deep interactions.
```

## Extraction and Inference Rules

### Rule 1: Extract explicit pages first

If the document explicitly mentions a page, include it directly.

Examples:

- “项目列表页” → include Project List Page
- “客户详情页” → include Customer Detail Page
- “成员管理弹窗” → include Member Management Dialog

### Rule 2: Infer pages from operations

If the document mentions an operation, infer the likely page or interaction.

| Operation clue | Likely page / interaction |
|---|---|
| Query / search / browse | List page |
| Add / create / new | Create page or create dialog |
| Edit / modify | Edit page or edit dialog |
| View / detail | Detail page |
| Delete / remove | Delete confirmation dialog |
| Import | Import dialog or import page |
| Export | Export action and export confirmation / result |
| Approve / reject | Approval dialog or approval detail page |
| Configure / settings | Configuration page |
| Assign / distribute | Assignment dialog or drawer |
| Bind / link / associate | Association dialog or selection page |
| Upload | Upload dialog or upload area |
| Preview | Preview page or preview dialog |
| Analyze / detect / check | Result page or task detail page |
| Publish / submit | Submit confirmation and result feedback |
| Enable / disable | Status change confirmation |
| Copy / clone | Copy confirmation or create-from-existing page |

### Rule 3: Infer sub-pages and deep interactions

For each list page, check whether it needs:

- Search area
- Filter area
- Table
- Row actions
- Batch actions
- Detail page
- Create page
- Edit page
- Delete confirmation dialog
- Import / export actions
- Empty state
- Loading state
- Error state

For each form page, check whether it needs:

- Form fields
- Validation rules
- Submit action
- Save draft action
- Cancel action
- Back navigation
- Success feedback
- Error feedback

For each detail page, check whether it needs:

- Basic information card
- Tabs
- Related records
- Timeline / operation log
- Edit entry
- Delete entry
- Back navigation

For each dialog or drawer, check whether it needs:

- Trigger action
- Title
- Main content
- Confirm action
- Cancel action
- Validation
- Success feedback
- Error feedback

### Rule 4: Mark assumptions clearly

Never treat inferred pages as confirmed requirements.

Use the following source values:

| Source | Meaning |
|---|---|
| `Explicit` | The page or interaction is clearly stated in the input document. |
| `Inferred from operation` | The page or interaction is inferred from a described operation. |
| `Inferred from product pattern` | The page or interaction is inferred from common product design patterns. |
| `Needs Confirmation` | The page or interaction may be needed, but the input document does not provide enough evidence. |
| `Needs Input` | The page or interaction cannot be reliably planned without more information. |

## Human-in-the-loop Rules

This skill should not blindly continue when the input is incomplete or when important assumptions are made.

The skill must pause and request human review in the following cases:

1. The input maturity level is L0, L1, or L2.
2. The generated prototype index contains many inferred pages.
3. The generated prototype index contains pages marked as `Needs Confirmation`.
4. The generation scope is unclear.
5. Page relationships are ambiguous.
6. Core interactions are missing or inferred.
7. The final completeness check finds missing pages or missing interactions.

The skill may continue automatically when:

1. The input maturity level is L3 or L4.
2. The page task is clearly defined.
3. The current task has no unresolved assumptions.
4. The current task only updates task status or performs routine checks.

Default rule:

> Confirm direction and boundaries with the human. Let AI execute clear tasks automatically.

## Review Document Rule

Before generating prototype pages, the skill must generate a `prototype-index-review.md` document for human review.

The review document should include:

- Input diagnosis result
- Function catalog
- Page list
- Page relationships
- Inferred pages
- Items needing confirmation
- Missing information
- User modification area
- Confirmation conclusion

The skill must not treat inferred pages or uncertain interactions as confirmed requirements unless the user confirms them.

After the user modifies or confirms the review document, the skill should generate or update `prototype-index.md` as the execution index for page-by-page prototype generation.

In starter-compatible mode, generate `feature-manifest.json` after `prototype-index.md` is confirmed. Do not include tasks with `Needs Confirmation` or `Needs Input` in the manifest unless the user explicitly selects draft or hypothesis generation.

## Workflow

### Step 1: Diagnose input

Read the input document and generate an input diagnosis.

Do not generate prototype code at this stage.

### Step 2: Extract function catalog

Extract all function modules from the input document.

If modules are not explicit, infer them from business processes and operations.

### Step 3: Generate page list

For each function module, identify:

- Main pages
- List pages
- Create pages
- Edit pages
- Detail pages
- Dialogs
- Drawers
- Secondary pages
- Configuration pages
- Result pages
- Empty states
- Error states

### Step 4: Generate page relationships

Identify:

- Entry page
- Previous page
- Trigger operation
- Target page
- Return path
- Success path
- Failure path
- Cancel path

Generate a Mermaid page relationship diagram when useful.

### Step 5: Generate human review document

Generate `prototype-index-review.md`.

The user should be able to modify the review document directly.

### Step 6: Generate executable prototype index

After human confirmation or modification, generate `prototype-index.md`.

The index is the source of truth for page-by-page prototype generation.

In starter-compatible mode, also generate `feature-manifest.json` from confirmed tasks so starter scripts can create the project skeleton without losing page coverage.

### Step 7: Generate prototype page by page

After `prototype-index.md` is confirmed, generate the prototype page by page.

For each task in the index:

1. Read the task.
2. Set task status to `In Progress`.
3. Generate the corresponding page, component, route, mock data, or interaction.
4. Ensure the generated page is connected to existing navigation or routes.
5. Record generated files.
6. Update task status.
7. Run a local consistency check for the task.
8. Continue with the next task only after the current task is completed or blocked.

The AI must not skip tasks silently.

In starter-compatible mode, create page/scenario skeletons through `node scripts/new-feature.cjs --manifest <feature-manifest.json>` before filling in page content whenever that script is available.

## Feature Manifest Rules

`feature-manifest.json` is the handoff file from requirement planning to starter-compatible project generation. Generate it only after `prototype-index.md` has been confirmed or updated from the user's review.

In starter-compatible mode:

1. Include only tasks that are confirmed and not blocked by `Needs Confirmation` or `Needs Input`.
2. Preserve `iterationSlug`, `featureName`, `updatedAt`, `iterationName`, `sourceRequirement`, and `sourceIndex`.
3. Convert normal pages to `pages[]` entries with `title`, `path`, `pageKey`, and `surface: "page"`.
4. Convert drawers, modals, side panels, confirmations, import wizards, and other independent surfaces to `scenarios[]` under their parent page.
5. Preserve `parentPageKey` for every scenario.
6. Include `sourceTaskIds` so completeness checks can trace manifest entries back to index tasks.
7. Include `designPatternRefs` when a task maps to a root `DESIGN.md` pattern or `design-system/shared-registry.json` entry.
8. Do not put uncertain or inferred-but-unconfirmed tasks into the manifest unless the user explicitly selected `draft` mode.

Minimal starter-compatible manifest:

```json
{
  "iterationSlug": "2026-01-order-upgrade",
  "featureSlug": "2026-01-order-upgrade",
  "featureName": "订单流程升级",
  "updatedAt": "2026-06-17",
  "iterationName": "V1",
  "sourceRequirement": "requirements.md",
  "sourceIndex": "prototype-index.md",
  "workspaceMode": "prototype-starter-compatible",
  "pages": [
    {
      "title": "订单列表",
      "path": "order-list",
      "pageKey": "order-list",
      "surface": "page",
      "sourceTaskIds": ["T001"],
      "designPatternRefs": ["list-page"],
      "scenarios": [
        {
          "title": "新建订单",
          "pageKey": "order-create-drawer",
          "surface": "drawer",
          "parentPageKey": "order-list",
          "sourceTaskIds": ["T002"],
          "designPatternRefs": ["drawer-form"]
        }
      ]
    }
  ]
}
```

### Step 8: Maintain generation log

After each page generation task, update `prototype-generation-log.md`.

The log should include:

- Task ID
- Page name
- Action taken
- Files created
- Files modified
- Status change
- Issues found
- Next task

### Step 9: Run final completeness check

Compare:

- Input requirement document
- `prototype-index-review.md`
- `prototype-index.md`
- `feature-manifest.json` when present
- Generated prototype files
- Routes and navigation
- Component usage
- Starter compliance output when in starter-compatible mode

Output `prototype-completeness-check.md`.

### Step 10: Finalize prototype delivery

The prototype can be considered complete only after:

1. All confirmed tasks are completed.
2. No required page is missing.
3. No required route is missing.
4. No required core interaction is missing.
5. Completeness check passes.
6. The project can be run or previewed according to the selected technical stack.

## Prototype Index Fields

`prototype-index.md` should include the following fields:

| Field | Description |
|---|---|
| Task ID | Unique task ID, such as T001 |
| Function Module | Business function module |
| Page Name | Page or interaction to generate |
| Page Type | Home / List / Create / Edit / Detail / Dialog / Drawer / Secondary Page / Result Page |
| Iteration Slug | Iteration or feature folder slug, such as 2026-01-order-upgrade |
| Page Key | Stable page identifier for requirement/spec tooling |
| Surface | page / drawer / modal / side-panel / confirm |
| Parent Page Key | Parent page for scenario surfaces |
| Source Section | Which section of the input document the task comes from |
| Source Type | Explicit / Inferred from operation / Inferred from product pattern / Needs Confirmation |
| Previous Page | Where the user enters this page from |
| Trigger Operation | Which operation opens this page or interaction |
| Next Page | Where the user goes after this page |
| Core Components | Table, form, filter, button, dialog, tabs, cards, etc. |
| Key Fields | Important fields if available |
| Required Route | Whether the task needs a route |
| Suggested File Path | Suggested implementation file path |
| Design Pattern Refs | Relevant DESIGN.md, starter shared-registry, or UI pattern references |
| Manifest Entry | Whether this task should be emitted to feature-manifest.json |
| Starter Compatible | Whether this task must use starter shared assets and metadata |
| Status | Not Started / In Progress / Completed / Needs Confirmation / Needs Input / Needs Fix |
| Check Result | Missing, uncertain, or completed check result |
| Generated Files | Files generated for this task |
| Notes | Additional notes |

## Status Values

| Status | Meaning |
|---|---|
| `Not Started` | The task has not been generated. |
| `In Progress` | The task is currently being generated. |
| `Completed` | The task has been generated and checked. |
| `Needs Confirmation` | The task requires human confirmation before generation. |
| `Needs Input` | The task lacks necessary information. |
| `Needs Fix` | The task has been generated but requires fixes. |
| `Skipped` | The task is intentionally not generated. |

## Prototype Generation Rules

When generating prototype code:

1. Never generate 20 pages in one step.
2. Generate only one page or one small module per task.
3. Always read the current `prototype-index.md` before generation.
4. Always update the task status after generation.
5. Always record generated or modified files.
6. Do not create pages that are not in the index unless the user explicitly approves.
7. If a missing page is discovered during generation, add it as a new task and mark it as `Needs Confirmation`.
8. If a generated page reveals a missing interaction, add it to the check result.
9. If a page depends on an uncertain field or rule, use a clear placeholder and mark it in the task notes.
10. Ensure routes and navigation are consistent with page relationships.
11. Prefer reusable layout and components when multiple pages share patterns.
12. Keep the prototype runnable or previewable after each completed task whenever possible.

## File Generation Rules

For each page task, consider whether to generate or update:

- Page file
- Route configuration
- Navigation menu
- Layout file
- Shared component
- Mock data file
- Type definition
- Dialog / drawer component
- Style file
- README or run instruction

Do not generate unnecessary files.

## Task Completion Criteria

A page task can be marked as `Completed` only when:

1. The page or interaction is implemented.
2. The page has an entry route or trigger if required.
3. Required navigation is connected.
4. Required components are present.
5. Basic interaction behavior exists.
6. Generated files are recorded.
7. No blocking `Needs Input` issue remains.

## Final Acceptance Criteria

The prototype can be considered complete only when:

1. Every confirmed task in `prototype-index.md` is marked as `Completed` or intentionally `Skipped`.
2. Every generated page has a corresponding route or entry.
3. Every explicit page from the input document exists in the prototype.
4. Every confirmed inferred page exists in the prototype.
5. Every list page has expected actions.
6. Every create/edit page has form submission and cancel behavior.
7. Every delete action has a confirmation interaction.
8. Every detail page has return navigation.
9. No unresolved `Needs Confirmation`, `Needs Input`, or `Needs Fix` tasks remain.
10. `prototype-completeness-check.md` confirms that no required page or core interaction is missing.
11. The prototype project can be run or previewed based on the selected technical stack.

## Completeness Check Rules

The final completeness check must verify:

1. Whether all function modules from the input document are covered.
2. Whether all explicit pages from the input document are generated.
3. Whether inferred pages were confirmed or intentionally skipped.
4. Whether each list page has expected row actions and batch actions.
5. Whether each create/edit form has submit, cancel, validation, and feedback behavior.
6. Whether each delete operation has confirmation.
7. Whether each detail page has navigation and related operations.
8. Whether all page relationships are implemented.
9. Whether routes exist for generated pages.
10. Whether generated files match the index.
11. Whether the prototype contains pages not registered in the index.
12. Whether unresolved `Needs Confirmation`, `Needs Input`, or `Needs Fix` tasks remain.
13. Whether the prototype can be run or previewed.

## Default Response Behavior

When invoked with a requirement document, the skill should usually start with:

1. Input diagnosis
2. Function catalog
3. Page list
4. Page relationship map
5. `prototype-index-review.md`

Do not jump directly into writing prototype code unless:

1. The user explicitly asks to generate code now, and
2. The page index has already been confirmed, or
3. The selected execution mode is `auto` or `draft`.

## Recommended First User-facing Output

After analyzing the input document, output:

```markdown
I have completed the input diagnosis and generated the prototype index review document.

Please review the following before we continue:

1. Function modules
2. Page list
3. Page relationships
4. Inferred pages
5. Items needing confirmation
6. Missing information

After you confirm or modify the review document, I will generate `prototype-index.md` as the execution index and then generate the prototype page by page.
```
