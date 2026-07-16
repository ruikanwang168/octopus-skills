#!/usr/bin/env python3
"""Clear spec sections added by prototype-spec-annotator.

Supports deterministic marker-based cleanup and a conservative set of
legacy heuristics for the two patterns already seen in testing:

- inline HTML/template sections such as data-role="page-spec",
  class/className containing proto-spec-doc, or data-module="spec-section"
- React wrapper usage such as withPageSpec("PageKey", Component)
- JS helper functions such as renderXxxSpecSection()
"""

from __future__ import annotations

import argparse
import re
import sys
from dataclasses import dataclass
from pathlib import Path
from typing import Iterable


TEXT_EXTENSIONS = {".html", ".htm", ".vue", ".jsx", ".tsx", ".js", ".ts"}
MARKUP_EXTENSIONS = {".html", ".htm", ".vue", ".jsx", ".tsx"}
IGNORE_DIRS = {
    ".git",
    ".next",
    ".nuxt",
    ".turbo",
    "build",
    "coverage",
    "dist",
    "node_modules",
    "out",
    "tmp",
}

MARKER_PATTERNS = [
    re.compile(
        r"<!--\s*proto-spec-annotator-viewer:start(?P<meta>.*?)-->\s*(?P<body>.*?)\s*<!--\s*proto-spec-annotator-viewer:end(?P<meta2>.*?)-->",
        re.S | re.I,
    ),
    re.compile(
        r"<!--\s*PROTO_SPEC:BEGIN(?P<meta>.*?)-->\s*(?P<body>.*?)\s*<!--\s*PROTO_SPEC:END(?P<meta2>.*?)-->",
        re.S,
    ),
    re.compile(
        r"\{/\*\s*PROTO_SPEC:BEGIN(?P<meta>.*?)\*/\}\s*(?P<body>.*?)\s*\{/\*\s*PROTO_SPEC:END(?P<meta2>.*?)\*/\}",
        re.S,
    ),
    re.compile(
        r"/\*\s*PROTO_SPEC:BEGIN(?P<meta>.*?)\*/\s*(?P<body>.*?)\s*/\*\s*PROTO_SPEC:END(?P<meta2>.*?)\*/",
        re.S,
    ),
]

WITH_PAGE_SPEC_EXPORT = re.compile(
    r"export\s+default\s+withPageSpec\(\s*([\"'])(?P<page>.+?)\1\s*,\s*(?P<component>[A-Za-z_][A-Za-z0-9_]*)\s*\)\s*;"
)
WITH_PAGE_SPEC_IMPORT = re.compile(
    r"^.*withPageSpec.*(?:\r?\n)?", re.M
)
PAGE_SPEC_DOC_IMPORT = re.compile(
    r"^.*PageSpecDoc.*(?:\r?\n)?", re.M
)
PAGE_SPEC_DOC_TAG = re.compile(r"[ \t]*<PageSpecDoc\b[^>]*/>[ \t]*(?:\r?\n)?")
PAGE_SPECS_IMPORT = re.compile(
    r'^import\s*\{\s*pageSpecs\s*,\s*type\s+PageSpecKey\s*\}\s*from\s*(?P<quote>["\'])(?P<source>[^"\']*pageSpecs)\1;\s*(?:\r?\n)?',
    re.M,
)
PAGE_SPEC_TYPE_IMPORT = re.compile(
    r'^import\s+type\s+\{\s*PageSpec\s*\}\s*from\s*["\'][^"\']*pageSpecs["\'];\s*(?:\r?\n)?',
    re.M,
)
PAGE_SPECS_EXPORT_BLOCK = re.compile(
    r"export const pageSpecs = \{[\s\S]*?\n\}\s+as\s+const\s+satisfies\s+Record<string,\s*PageSpec>;\n\nexport type PageSpecKey = keyof typeof pageSpecs;\n?",
    re.M,
)

LEGACY_HELPER_FUNCTION = re.compile(
    r"""
    (?P<full>
        function\s+(?P<name>[A-Za-z_][A-Za-z0-9_]*SpecSection)\s*\([^)]*\)\s*\{
        [\s\S]*?
        \}
    )
    """,
    re.X,
)

SPEC_SECTION_CALL = r"""
    (?:
        \n?[ \t]*\$\{\s*__NAME__\(\)\s*\}[ \t]*\n?
        |
        \n?[ \t]*__NAME__\(\)\s*;?[ \t]*\n?
    )
"""

HTML_SECTION_OPEN = re.compile(r"<(?P<tag>section|div|article)\b(?P<attrs>[^>]*)>", re.I)
TARGET_ATTR_PATTERNS = [
    re.compile(r'data-role\s*=\s*["\']page-spec["\']', re.I),
    re.compile(r'data-module\s*=\s*["\']spec-section["\']', re.I),
    re.compile(r'data-spec-origin\s*=\s*["\']prototype-spec-annotator["\']', re.I),
    re.compile(r'class(?:Name)?\s*=\s*["\'][^"\']*\bproto-spec-doc\b[^"\']*["\']', re.I),
]
DATA_SPEC_PAGE = re.compile(r'data-spec-page\s*=\s*["\']([^"\']+)["\']', re.I)
DATA_SPEC_ID = re.compile(r'data-spec-id\s*=\s*["\']([^"\']+)["\']', re.I)
DATA_SPEC_BATCH = re.compile(r'data-spec-batch\s*=\s*["\']([^"\']+)["\']', re.I)


@dataclass
class CleanupResult:
    text: str
    changed: bool
    removed_blocks: int
    notes: list[str]


def parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser(description="Clear spec sections added by prototype-spec-annotator.")
    parser.add_argument("--root", default=".", help="Project root used for relative file paths. Defaults to current directory.")
    parser.add_argument("--all", action="store_true", help="Clear specs from all supported files under --root.")
    parser.add_argument("--files", nargs="*", default=[], help="Clear specs from the specified files.")
    parser.add_argument("--page-ids", nargs="*", default=[], help="Clear specs only for the given page ids or page file stems.")
    parser.add_argument("--spec-ids", nargs="*", default=[], help="Clear specs only for the given unique spec ids.")
    parser.add_argument("--batch-id", help="Clear specs only for the given batch id.")
    parser.add_argument("--dry-run", action="store_true", help="Preview changes without writing files.")
    args = parser.parse_args()
    if not args.all and not args.files and not args.page_ids and not args.spec_ids and not args.batch_id:
        parser.error("Specify --all, --files, --page-ids, --spec-ids, or --batch-id.")
    return args


def resolve_files(root: Path, files: list[str], clear_all: bool, page_ids: list[str]) -> list[Path]:
    if files:
        resolved = []
        for item in files:
            path = Path(item)
            if not path.is_absolute():
                path = root / path
            if path.is_file():
                resolved.append(path.resolve())
            elif path.is_dir():
                resolved.extend(iter_candidate_files(path.resolve()))
            else:
                print(f"WARN missing target: {item}", file=sys.stderr)
        return dedupe_paths(resolved)

    candidates = list(iter_candidate_files(root.resolve()))
    if clear_all:
        return candidates

    return candidates


def iter_candidate_files(root: Path) -> Iterable[Path]:
    for path in root.rglob("*"):
        relative_parts = path.relative_to(root).parts
        if any(part in IGNORE_DIRS for part in relative_parts):
            continue
        if path.is_file() and path.suffix.lower() in TEXT_EXTENSIONS:
            yield path


def dedupe_paths(paths: Iterable[Path]) -> list[Path]:
    seen: set[Path] = set()
    ordered: list[Path] = []
    for path in paths:
        real = path.resolve()
        if real not in seen:
            seen.add(real)
            ordered.append(real)
    return ordered


def file_matches_page_ids(path: Path, page_ids: set[str]) -> bool:
    if not page_ids:
        return True
    stem = path.stem
    name = path.name
    relative = str(path)
    return any(page in {stem, name} or page in relative for page in page_ids)


def has_selectors(page_ids: set[str], spec_ids: set[str], batch_id: str | None) -> bool:
    return bool(page_ids or spec_ids or batch_id)


def match_meta_value(meta: str, key: str) -> str | None:
    match = re.search(rf"{key}\s*=\s*([^\s]+)", meta)
    if not match:
        return None
    return match.group(1).strip("\"' ")


def meta_matches_selectors(meta: str, page_ids: set[str], spec_ids: set[str], batch_id: str | None) -> bool:
    if not has_selectors(page_ids, spec_ids, batch_id):
        return True
    page_value = match_meta_value(meta, "page")
    spec_value = match_meta_value(meta, "id")
    batch_value = match_meta_value(meta, "batch")
    if page_ids and page_value in page_ids:
        return True
    if spec_ids and spec_value in spec_ids:
        return True
    if batch_id and batch_value == batch_id:
        return True
    return False


def cleanup_text(
    text: str,
    path: Path,
    page_ids: set[str],
    spec_ids: set[str],
    batch_id: str | None,
    targeted_by_file: bool,
    clear_all: bool,
) -> CleanupResult:
    removed_blocks = 0
    notes: list[str] = []
    original = text

    if clear_all and is_page_spec_doc_component(path, text):
        stubbed = page_spec_doc_stub(path)
        return CleanupResult(
            text=stubbed,
            changed=stubbed != original,
            removed_blocks=1,
            notes=["page_spec_doc_component=stubbed"],
        )

    if clear_all and is_page_spec_route_shell_component(path, text):
        stubbed = page_spec_route_shell_stub(path)
        return CleanupResult(
            text=stubbed,
            changed=stubbed != original,
            removed_blocks=1,
            notes=["page_spec_route_shell=stubbed"],
        )

    if clear_all and is_page_specs_data_module(path, text):
        cleared = clear_page_specs_data(text)
        return CleanupResult(
            text=cleared,
            changed=cleared != original,
            removed_blocks=1,
            notes=["page_specs_data=cleared"],
        )

    text, removed = remove_marker_blocks(text, page_ids, spec_ids, batch_id)
    if removed:
        removed_blocks += removed
        notes.append(f"marker_blocks={removed}")

    text, removed = remove_with_page_spec_exports(text, page_ids)
    matched_export = removed > 0
    if removed:
        removed_blocks += removed
        notes.append(f"with_page_spec_exports={removed}")

    if path.suffix.lower() in {".js", ".ts", ".jsx", ".tsx"}:
        text, helper_names = remove_legacy_helper_functions(text, page_ids, targeted_by_file, path)
        if helper_names:
            removed_blocks += len(helper_names)
            notes.append(f"legacy_helpers={','.join(helper_names)}")
            text = remove_helper_invocations(text, helper_names)

        text, removed = remove_page_spec_doc_usages(text, targeted_by_file, matched_export)
        if removed:
            removed_blocks += removed
            notes.append(f"page_spec_doc_tags={removed}")

        text = cleanup_import_lines(text)

    if path.suffix.lower() in MARKUP_EXTENSIONS:
        text, removed = remove_markup_spec_blocks(text, page_ids, spec_ids, batch_id, targeted_by_file)
        if removed:
            removed_blocks += removed
            notes.append(f"markup_blocks={removed}")

    if text != original:
        text = tidy_whitespace(text)
    return CleanupResult(text=text, changed=text != original, removed_blocks=removed_blocks, notes=notes)


def is_page_spec_doc_component(path: Path, text: str) -> bool:
    return path.name.startswith("PageSpecDoc.") and "proto-spec-doc" in text


def is_page_spec_route_shell_component(path: Path, text: str) -> bool:
    return path.name.startswith("PageSpecRouteShell.") and (
        "proto-spec-route-shell" in text or "PageSpecDoc" in text
    )


def page_spec_doc_stub(path: Path) -> str:
    if path.suffix.lower() == ".vue":
        return "<template></template>\n"
    return "export function PageSpecDoc() {\n  return null;\n}\n"


def page_spec_route_shell_stub(path: Path) -> str:
    if path.suffix.lower() == ".vue":
        return "<template><slot /></template>\n"
    return 'import type { ReactNode } from "react";\n\nexport function PageSpecRouteShell({ children }: { children: ReactNode }) {\n  return <>{children}</>;\n}\n'


def is_page_specs_data_module(path: Path, text: str) -> bool:
    return path.name == "pageSpecs.ts" and "export const pageSpecs = {" in text


def clear_page_specs_data(text: str) -> str:
    replacement = "export const pageSpecs = {} as const;\n\nexport type PageSpecKey = keyof typeof pageSpecs;\n"
    updated = PAGE_SPECS_EXPORT_BLOCK.sub(replacement, text)
    return tidy_whitespace(updated)


def remove_marker_blocks(text: str, page_ids: set[str], spec_ids: set[str], batch_id: str | None) -> tuple[str, int]:
    total_removed = 0
    for pattern in MARKER_PATTERNS:
        changed = True
        while changed:
            changed = False

            def repl(match: re.Match[str]) -> str:
                nonlocal changed, total_removed
                meta = f"{match.group('meta')} {match.group('meta2')}"
                if meta_matches_selectors(meta, page_ids, spec_ids, batch_id):
                    changed = True
                    total_removed += 1
                    return ""
                return match.group(0)

            text = pattern.sub(repl, text)
    return text, total_removed


def remove_with_page_spec_exports(text: str, page_ids: set[str]) -> tuple[str, int]:
    removed = 0

    def repl(match: re.Match[str]) -> str:
        nonlocal removed
        page = match.group("page")
        component = match.group("component")
        if page_ids and page not in page_ids:
            return match.group(0)
        removed += 1
        return f"export default {component};"

    return WITH_PAGE_SPEC_EXPORT.sub(repl, text), removed


def remove_legacy_helper_functions(
    text: str,
    page_ids: set[str],
    targeted_by_file: bool,
    path: Path,
) -> tuple[str, list[str]]:
    helper_names: list[str] = []

    def repl(match: re.Match[str]) -> str:
        full = match.group("full")
        name = match.group("name")
        if page_ids and not targeted_by_file and not any(page in full for page in page_ids):
            return full
        if not any(token in full for token in ('data-module="spec-section"', 'data-role="page-spec"', "proto-spec-doc")):
            return full
        helper_names.append(name)
        return ""

    text = LEGACY_HELPER_FUNCTION.sub(repl, text)
    return text, helper_names


def remove_helper_invocations(text: str, helper_names: list[str]) -> str:
    for name in helper_names:
        pattern = re.compile(SPEC_SECTION_CALL.replace("__NAME__", re.escape(name)), re.X)
        text = pattern.sub("\n", text)
    return text


def remove_page_spec_doc_usages(text: str, targeted_by_file: bool, matched_export: bool) -> tuple[str, int]:
    if not targeted_by_file and not matched_export:
        return text, 0
    count = len(PAGE_SPEC_DOC_TAG.findall(text))
    if not count:
        return text, 0
    return PAGE_SPEC_DOC_TAG.sub("\n", text), count


def cleanup_import_lines(text: str) -> str:
    if "withPageSpec(" not in text:
        text = WITH_PAGE_SPEC_IMPORT.sub("", text)
    if "pageSpecs[" not in text:
        text = PAGE_SPECS_IMPORT.sub(r'import type { PageSpecKey } from "\g<source>";\n', text)
    text_without_doc_import = PAGE_SPEC_DOC_IMPORT.sub("", text)
    if "<PageSpecDoc" not in text_without_doc_import and "PageSpecDoc(" not in text_without_doc_import and "PageSpecDoc." not in text_without_doc_import:
        text = PAGE_SPEC_DOC_IMPORT.sub("", text)
    if "PageSpec " not in text and "PageSpec<" not in text and "PageSpec[" not in text and "PageSpec;" not in text and "PageSpec =" not in text:
        text = PAGE_SPEC_TYPE_IMPORT.sub("", text)
    return text


def attrs_match_selectors(
    attrs: str,
    page_ids: set[str],
    spec_ids: set[str],
    batch_id: str | None,
    targeted_by_file: bool,
) -> bool:
    if not has_selectors(page_ids, spec_ids, batch_id):
        return targeted_by_file or True

    page_match = DATA_SPEC_PAGE.search(attrs)
    spec_match = DATA_SPEC_ID.search(attrs)
    batch_match = DATA_SPEC_BATCH.search(attrs)
    if page_ids and page_match and page_match.group(1) in page_ids:
        return True
    if spec_ids and spec_match and spec_match.group(1) in spec_ids:
        return True
    if batch_id and batch_match and batch_match.group(1) == batch_id:
        return True
    return False


def remove_markup_spec_blocks(
    text: str,
    page_ids: set[str],
    spec_ids: set[str],
    batch_id: str | None,
    targeted_by_file: bool,
) -> tuple[str, int]:
    removed = 0
    cursor = 0
    parts: list[str] = []

    while True:
        match = HTML_SECTION_OPEN.search(text, cursor)
        if not match:
            parts.append(text[cursor:])
            break

        tag = match.group("tag")
        attrs = match.group("attrs")
        if not any(pattern.search(attrs) for pattern in TARGET_ATTR_PATTERNS):
            parts.append(text[cursor:match.end()])
            cursor = match.end()
            continue

        if not attrs_match_selectors(attrs, page_ids, spec_ids, batch_id, targeted_by_file):
            parts.append(text[cursor:match.end()])
            cursor = match.end()
            continue

        end = find_matching_tag_end(text, match.start(), tag)
        if end is None:
            parts.append(text[cursor:match.end()])
            cursor = match.end()
            continue

        parts.append(text[cursor:trim_left_boundary(text, match.start())])
        cursor = trim_right_boundary(text, end)
        removed += 1

    return "".join(parts), removed


def find_matching_tag_end(text: str, start: int, tag: str) -> int | None:
    open_match = HTML_SECTION_OPEN.match(text, start)
    if not open_match:
        return None
    cursor = open_match.end()
    depth = 1
    token_re = re.compile(rf"<(/?){tag}\b[^>]*?>", re.I)
    while True:
        token = token_re.search(text, cursor)
        if not token:
            return None
        raw = token.group(0)
        closing = token.group(1) == "/"
        self_closing = raw.rstrip().endswith("/>")
        if closing:
            depth -= 1
            if depth == 0:
                return token.end()
        elif not self_closing:
            depth += 1
        cursor = token.end()


def trim_left_boundary(text: str, start: int) -> int:
    while start > 0 and text[start - 1] in " \t":
        start -= 1
    if start > 0 and text[start - 1] == "\n":
        start -= 1
        if start > 0 and text[start - 1] == "\r":
            start -= 1
    return start


def trim_right_boundary(text: str, end: int) -> int:
    length = len(text)
    while end < length and text[end] in " \t":
        end += 1
    if end < length and text[end] == "\r":
        end += 1
    if end < length and text[end] == "\n":
        end += 1
    return end


def tidy_whitespace(text: str) -> str:
    text = re.sub(r"\n{3,}", "\n\n", text)
    text = re.sub(r"[ \t]+\n", "\n", text)
    return text


def main() -> int:
    args = parse_args()
    root = Path(args.root).resolve()
    page_ids = {page.strip() for page in args.page_ids if page.strip()}
    spec_ids = {spec.strip() for spec in args.spec_ids if spec.strip()}
    targets = resolve_files(root, args.files, args.all, list(page_ids))
    if not targets:
        print("No matching files.")
        return 0

    changed_files = 0
    total_removed = 0

    for path in targets:
        try:
            text = path.read_text(encoding="utf-8")
        except UnicodeDecodeError:
            print(f"SKIP binary/non-utf8: {path}")
            continue

        targeted_by_file = bool(args.all or args.files or file_matches_page_ids(path, page_ids))
        result = cleanup_text(text, path, page_ids, spec_ids, args.batch_id, targeted_by_file, args.all)
        if not result.changed:
            continue

        changed_files += 1
        total_removed += result.removed_blocks
        rel = path.relative_to(root) if path.is_relative_to(root) else path
        print(f"{rel}: removed={result.removed_blocks} details={' '.join(result.notes)}")
        if not args.dry_run:
            path.write_text(result.text, encoding="utf-8")

    if args.dry_run:
        print(f"dry_run changed_files={changed_files} removed_blocks={total_removed}")
    else:
        print(f"changed_files={changed_files} removed_blocks={total_removed}")
    return 0


if __name__ == "__main__":
    sys.exit(main())
