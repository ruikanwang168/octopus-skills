# Operation Modes

## Mode Selection

Route the user request before editing files.

For deterministic file operations, use the bundled runner:

```bash
python3 scripts/run_proto_spec_workflow.py --root <project> --operation <mode>
```

The runner is self-contained. It must not import source files from unrelated tools, products, or applications.

Use the executing agent's current model for content quality. The runner is for deterministic file operations, batch scaffolding, history/registry maintenance, integration, and validation. It cannot automatically access the execution environment's current model; configure runner model flags only for unattended script-side generation.

| Mode | User intent | Default output |
|---|---|---|
| `create` | Generate specs for existing prototype pages | `current/<pageKey>.md` |
| `update` | Modify existing specs | Updated Markdown + history snapshot |
| `delete` | Remove specs | History snapshot + removed current file |
| `display` | Change visibility or viewer mode | Updated `viewer-config.json` or inline markers |
| `migrate` | Convert legacy inline / JSON specs to Markdown | Markdown specs + registry |
| `audit` | Inspect health without changes | Findings and recommended commands |
| `integrate` | Wire specs into runtime preview | Minimal loader/viewer patch |

## Write Modes

- `direct-write`: write files when the user clearly allowed it.
- `dry-run`: print planned changes and risks without writing.
- `patch-only`: provide patch snippets or generated Markdown without applying them.

When scope or overwrite intent is unclear, choose `dry-run` or ask one blocking question.

## Create

Preferred command:

```bash
python3 scripts/run_proto_spec_workflow.py --root <project> --operation create --scope all
```

1. Identify target pages and stable `pageKey`s.
2. Initialize the spec workspace if missing.
3. Generate one Markdown file per page.
4. Add or update registry entries.
5. Validate.

If a current file already exists, switch to update/overwrite flow.

## Update

Use this when the user asks to revise, polish, regenerate, or locally adjust a page spec.

Preferred command:

```bash
python3 scripts/run_proto_spec_workflow.py --root <project> --operation update --page-key <pageKey>
```

Before writing:

- Read `current/<pageKey>.md`.
- If `overwriteProtected: true`, do not overwrite unless the user explicitly confirms.
- If `lastManualEditedAt` is not null, warn that manual edits exist.
- Snapshot the current file to `history/<pageKey>/`.

Update only the requested page or sections. Do not reformat unrelated pages.

## Delete

Preferred command:

```bash
python3 scripts/run_proto_spec_workflow.py --root <project> --operation delete --page-key <pageKey>
```

Before deleting:

- Snapshot `current/<pageKey>.md` to `.before-delete.md`.
- Remove `current/<pageKey>.md`.
- Remove or mark the registry entry.
- If a runtime integration was generated only for this page, remove the page mapping but keep shared viewer code if other specs remain.

Deletion should not remove business page code.

## Display

Use display mode when the user wants:

- default hidden / default expanded
- manual toggle
- dual-view vs inline-bottom
- only show/hide without changing text

For Markdown-first projects, update `viewer-config.json`.

Default to `dual-view` for HTML, React, and Vue. Use `inline-bottom` only for explicitly requested legacy document-flow output. If switching an existing project to `dual-view`, remove old inline viewer assets and calls before validating.

Preferred command:

```bash
python3 scripts/run_proto_spec_workflow.py --root <project> --operation display --viewer-mode dual-view --visibility-mode manual-toggle
```

For legacy inline pages, use `data-spec-visible`, `hidden`, and `scripts/toggle_specs.py`.

## Migrate

Migration should preserve content first, then clean up old forms only if requested.

Supported migrations:

- `current/*.json` to `current/*.md`
- inline `PROTO_SPEC` / `data-role="page-spec"` blocks to Markdown
- legacy `pageSpecs.ts` content to per-page Markdown when structurally parseable

After migration, run validation and report any old inline blocks that remain.

## Audit

Audit mode never writes files. It checks:

- current spec files parse
- pageKey and filename match
- registry coverage
- history directories exist
- summaries and rules are non-empty
- legacy inline specs or JSON files remain
- runtime code appears to read current specs

Use either command for machine-readable output:

```bash
python3 scripts/run_proto_spec_workflow.py --root <project> --operation audit --json
python3 scripts/validate_editable_specs.py --root <project> --json
```

## Integrate

Integrate only after Markdown specs exist.

Preferred command:

```bash
python3 scripts/run_proto_spec_workflow.py --root <project> --operation integrate --scope all
```

Choose the smallest safe integration:

- React/Vue route-aware shell for multi-page apps.
- Inline-bottom only for normal document-flow pages.
- HTML runtime injection only for static HTML projects.

Do not put the full main spec in Drawer, Dialog, Sheet, Popover, or a fixed overlay.
