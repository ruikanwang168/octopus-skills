# Migration Mode

## Goal

Convert older prototype-spec-annotator outputs into Markdown-first spec assets without losing content or damaging the prototype.

## Supported Sources

1. Legacy JSON:

```text
src/page-specs/current/*.json
prototype-specs/current/*.json
```

2. Inline marked blocks:

```html
<!-- PROTO_SPEC:BEGIN page=app-management id=app-management-spec -->
...
<!-- PROTO_SPEC:END -->
```

3. DOM attributes:

```html
<section data-role="page-spec" data-spec-page="app-management">
```

4. Legacy shared component data:

```ts
export const pageSpecs = { ... }
```

Only migrate source forms you can parse safely. If parsing is uncertain, preserve the original and output a manual migration note.

## Default Migration Flow

1. Run a dry scan:

```bash
python3 scripts/migrate_to_markdown_specs.py --root <project> --dry-run
```

2. Review detected sources and target `pageKey`s.
3. Execute migration:

```bash
python3 scripts/migrate_to_markdown_specs.py --root <project>
```

4. Validate:

```bash
python3 scripts/validate_editable_specs.py --root <project>
```

5. Clean legacy inline blocks only when the user asks:

```bash
python3 scripts/clear_specs.py --root <project> --all --dry-run
```

## Migration Rules

- Preserve original source files unless the user asks to clean them.
- Never overwrite an existing Markdown spec without creating a history snapshot.
- JSON fields map to Markdown frontmatter and body.
- Inline blocks map to a Markdown body with conservative section titles if structure is unclear.
- Add `migrationSource` to frontmatter when possible.
- Set `sourceType: "mixed"` for migrated content.
- Set `lastGeneratedAt: null` and `lastManualEditedAt` to the migration timestamp when the source was edited or unknown.

## JSON Mapping

Map:

- `pageKey` -> frontmatter `pageKey`
- `version` -> frontmatter `version`
- `pageName` -> frontmatter `pageName`
- `pageType` -> frontmatter `pageType`
- `pageShape` -> frontmatter `pageShape`
- `summary` -> `## 页面摘要`
- `secondarySurfaces` -> `## 二级承载面`
- `sections[].title` -> `## <title>`
- `sections[].rules[]` -> bullet list
- `sections[].fields[]` -> `### 字段说明` table
- `meta.*` -> matching frontmatter keys

## Inline Mapping

If the inline block contains recognizable headings, preserve them.

If not, create:

```markdown
# <pageName>

## 页面摘要

从旧页面内说明迁移而来，需人工复核。

## 【页面说明】规则说明

- <plain text extracted from the old block>
```

Keep migrated text concise. Remove duplicated button labels, decorative headings, and generated wrapper text where safe.

## Cleanup After Migration

Only clean old inline blocks after Markdown validation passes. Prefer dry-run first.

Do not remove:

- business UI elements
- actual page drawers or dialogs
- app routing
- source files that merely import the business page

