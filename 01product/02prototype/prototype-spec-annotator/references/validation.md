# Validation

## Validation Goals

A valid Markdown-first spec system proves four things:

1. Current spec files parse.
2. The specs contain usable content.
3. Registry and history match the current files.
4. Any claimed runtime integration can actually read the spec source.

## Command

```bash
python3 scripts/validate_editable_specs.py --root <project>
```

Useful options:

```bash
python3 scripts/validate_editable_specs.py --root <project> --json
python3 scripts/validate_editable_specs.py --root <project> --strict
python3 scripts/validate_editable_specs.py --root <project> --page-key app-management
```

## Required Checks

- `current/*.md` frontmatter exists.
- `specSchemaVersion` is present.
- `storageFormat` is `markdown`.
- `pageKey` matches the filename.
- `version` is a positive integer.
- `pageName`, `pageType`, `pageShape` are non-empty.
- `summary` is non-empty.
- At least one `##` rule section exists beyond `页面摘要` and `二级承载面`.
- Every rule section has at least one non-empty bullet rule.
- Field tables, if present, have the expected columns.
- `registry.json` includes every current spec.
- `history/<pageKey>/` exists for every current spec.

## Warnings

Warn, but do not always fail, when:

- legacy `current/*.json` remains beside Markdown
- inline `PROTO_SPEC` blocks remain
- old `pageSpecs.ts` objects remain
- runtime code uses `localStorage` but no file/API persistence is visible
- runtime code derives `pageKey` from pathname or label text
- no runtime integration is visible but the user requested integrated preview
- specs contain too many "待补充" placeholders

## Content Quality Review

Use the quality checklist after structural validation:

- Does every major visible module have a corresponding section?
- Do rules mention fields/buttons/statuses that do not exist?
- Are empty, loading, failure, disabled, and permission/no-access states covered when visible or directly implied?
- Are complex drawers/modals/nested panels covered as secondary surfaces?
- Are sensitive source names or hidden background details absent?

## Failure Handling

If validation fails:

- Do not call the task complete.
- Fix the spec files or registry if the change is in scope.
- If the target runtime integration is unsafe or out of scope, downgrade to Markdown-only delivery and state the limitation.

