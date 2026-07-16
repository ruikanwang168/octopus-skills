# Cross-Framework Spec Storage Mode

This reference is retained for backward compatibility. The default storage mode is now Markdown-first. For new work, prefer:

- `markdown-spec-format.md`
- `operation-modes.md`
- `framework-integration.md`
- `validation.md`

## Current Default

Use per-page Markdown files as the source of truth:

```text
src/page-specs/ 或 prototype-specs/
  current/
    <pageKey>.md
  history/
    <pageKey>/
      <timestamp>.before-overwrite.md
  registry.json
  viewer-config.json
```

JSON files are legacy compatibility inputs. They may be migrated, exported, or consumed by a generated runtime adapter, but do not make `current/*.json` the default source for new projects.

## Framework-Agnostic Rules

- `pageKey` must be stable and must match `current/<pageKey>.md`.
- `registry.json` indexes pages; it does not store full spec content.
- Runtime code may read raw Markdown, a generated manifest derived from Markdown, or a local page-spec API.
- Manual edits must write back to project files or be clearly documented as browser-only fallback.
- Full specs should not be hidden inside Drawer/Dialog/Sheet/Popover overlays.
- Fixed-shell/workspace apps should use a dual-view shell: product page and spec page are mutually exclusive.
- Normal document-flow pages may use inline-bottom display.

## Lifecycle

### Full Generation

1. Discover pages and explicit `pageKey`s.
2. Initialize the spec root.
3. Generate `current/<pageKey>.md` for each page.
4. Add pages to `registry.json`.
5. Validate Markdown specs.

If a current file exists, switch to overwrite confirmation.

### Single-Page Regeneration

1. Locate `current/<pageKey>.md`.
2. If missing, generate normally.
3. If present, check `overwriteProtected` and `lastManualEditedAt`.
4. Ask for confirmation when overwrite risk exists.
5. Snapshot the old file to `history/<pageKey>/`.
6. Write the new Markdown file.

### Manual Save

1. Snapshot the current file to `.before-manual-save.md`.
2. Increment `version`.
3. Set `sourceType: "manual"` or `"mixed"`.
4. Set `lastManualEditedAt`.
5. Save `current/<pageKey>.md`.

### Delete

1. Snapshot the current file to `.before-delete.md`.
2. Remove `current/<pageKey>.md`.
3. Remove or mark the registry entry.
4. Remove page-specific runtime mapping if needed.

## Validation

Run:

```bash
python3 scripts/validate_editable_specs.py --root <target-project>
```

The validator supports Markdown and legacy JSON, but Markdown is the expected passing path for new projects.
