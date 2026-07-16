#!/usr/bin/env python3
"""Toggle visibility of spec sections added by prototype-spec-annotator.

This script is intended for inline/DOM-mounted spec blocks whose root nodes carry
the standard proto-spec attributes. It updates `data-spec-visible` and the
HTML/JSX `hidden` attribute in-place.
"""

from __future__ import annotations

import argparse
import re
import sys
from pathlib import Path

from clear_specs import (
    HTML_SECTION_OPEN,
    TARGET_ATTR_PATTERNS,
    dedupe_paths,
    iter_candidate_files,
    meta_matches_selectors,
    resolve_files,
    tidy_whitespace,
    attrs_match_selectors,
)


HIDDEN_ATTR = re.compile(r"\shidden(?:\s*=\s*(?:\"hidden\"|'hidden'))?", re.I)
MARKER_COMMENT_PATTERNS = [
    re.compile(r"<!--\s*PROTO_SPEC:(?P<kind>BEGIN|END)(?P<meta>.*?)-->"),
    re.compile(r"\{/\*\s*PROTO_SPEC:(?P<kind>BEGIN|END)(?P<meta>.*?)\*/\}"),
    re.compile(r"/\*\s*PROTO_SPEC:(?P<kind>BEGIN|END)(?P<meta>.*?)\*/"),
]


def parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser(description="Toggle visibility of prototype-spec-annotator spec sections.")
    parser.add_argument("--root", default=".", help="Project root used for relative file paths. Defaults to current directory.")
    parser.add_argument("--all", action="store_true", help="Toggle all supported spec blocks under --root.")
    parser.add_argument("--files", nargs="*", default=[], help="Toggle specs only in the specified files.")
    parser.add_argument("--page-ids", nargs="*", default=[], help="Toggle specs only for the given page ids.")
    parser.add_argument("--spec-ids", nargs="*", default=[], help="Toggle specs only for the given unique spec ids.")
    parser.add_argument("--batch-id", help="Toggle specs only for the given batch id.")
    parser.add_argument("--show", action="store_true", help="Show matching specs.")
    parser.add_argument("--hide", action="store_true", help="Hide matching specs.")
    parser.add_argument("--dry-run", action="store_true", help="Preview changes without writing files.")
    args = parser.parse_args()
    if args.show == args.hide:
        parser.error("Specify exactly one of --show or --hide.")
    if not args.all and not args.files and not args.page_ids and not args.spec_ids and not args.batch_id:
        parser.error("Specify --all, --files, --page-ids, --spec-ids, or --batch-id.")
    return args


def replace_or_add_attr(attrs: str, name: str, value: str) -> str:
    pattern = re.compile(rf'(\s{name}\s*=\s*["\'])([^"\']*)(["\'])', re.I)
    if pattern.search(attrs):
        return pattern.sub(rf'\1{value}\3', attrs, count=1)
    return f'{attrs} {name}="{value}"'


def set_hidden_attr(attrs: str, visible: bool) -> str:
    attrs = HIDDEN_ATTR.sub("", attrs)
    if visible:
        return attrs
    return f"{attrs} hidden"


def set_meta_flag(meta: str, key: str, value: str) -> str:
    pattern = re.compile(rf"({key}\s*=\s*)([^\s]+)")
    if pattern.search(meta):
        return pattern.sub(rf"\1{value}", meta, count=1)
    return f"{meta} {key}={value}"


def toggle_marker_visibility(
    text: str,
    page_ids: set[str],
    spec_ids: set[str],
    batch_id: str | None,
    visible: bool,
) -> tuple[str, int]:
    changed = 0

    def make_repl(wrapper: str):
        def repl(match: re.Match[str]) -> str:
            nonlocal changed
            meta = match.group("meta")
            if not meta_matches_selectors(meta, page_ids, spec_ids, batch_id):
                return match.group(0)
            new_meta = set_meta_flag(meta, "visible", "true" if visible else "false")
            changed += 1
            kind = match.group("kind")
            if wrapper == "html":
                return f"<!-- PROTO_SPEC:{kind}{new_meta} -->"
            if wrapper == "jsx":
                return f"{{/* PROTO_SPEC:{kind}{new_meta} */}}"
            return f"/* PROTO_SPEC:{kind}{new_meta} */"

        return repl

    text = MARKER_COMMENT_PATTERNS[0].sub(make_repl("html"), text)
    text = MARKER_COMMENT_PATTERNS[1].sub(make_repl("jsx"), text)
    text = MARKER_COMMENT_PATTERNS[2].sub(make_repl("block"), text)
    return text, changed


def toggle_markup_blocks(
    text: str,
    page_ids: set[str],
    spec_ids: set[str],
    batch_id: str | None,
    targeted_by_file: bool,
    visible: bool,
) -> tuple[str, int]:
    changed = 0

    def repl(match: re.Match[str]) -> str:
        nonlocal changed
        tag = match.group("tag")
        attrs = match.group("attrs")
        if not any(pattern.search(attrs) for pattern in TARGET_ATTR_PATTERNS):
            return match.group(0)
        if not attrs_match_selectors(attrs, page_ids, spec_ids, batch_id, targeted_by_file):
            return match.group(0)
        new_attrs = replace_or_add_attr(attrs, "data-spec-visible", "true" if visible else "false")
        new_attrs = set_hidden_attr(new_attrs, visible)
        changed += 1
        return f"<{tag}{new_attrs}>"

    return HTML_SECTION_OPEN.sub(repl, text), changed


def main() -> int:
    args = parse_args()
    root = Path(args.root).resolve()
    page_ids = {page.strip() for page in args.page_ids if page.strip()}
    spec_ids = {spec.strip() for spec in args.spec_ids if spec.strip()}
    targets = resolve_files(root, args.files, args.all, list(page_ids))
    targets = dedupe_paths(targets)
    if not targets:
        print("No matching files.")
        return 0

    changed_files = 0
    changed_blocks = 0

    for path in targets:
        if path.suffix.lower() not in {".html", ".htm", ".vue", ".jsx", ".tsx", ".js", ".ts"}:
            continue
        try:
            text = path.read_text(encoding="utf-8")
        except UnicodeDecodeError:
            print(f"SKIP binary/non-utf8: {path}")
            continue

        targeted_by_file = bool(args.all or args.files)
        updated, marker_count = toggle_marker_visibility(
            text,
            page_ids,
            spec_ids,
            args.batch_id,
            args.show,
        )
        updated, block_count = toggle_markup_blocks(
            updated,
            page_ids,
            spec_ids,
            args.batch_id,
            targeted_by_file,
            args.show,
        )
        total_count = marker_count + block_count
        if total_count == 0:
            continue

        updated = tidy_whitespace(updated)
        changed_files += 1
        changed_blocks += total_count
        rel = path.relative_to(root) if path.is_relative_to(root) else path
        print(f"{rel}: toggled={total_count} visible={'true' if args.show else 'false'}")
        if not args.dry_run:
            path.write_text(updated, encoding="utf-8")

    if args.dry_run:
        print(f"dry_run changed_files={changed_files} toggled_blocks={changed_blocks}")
    else:
        print(f"changed_files={changed_files} toggled_blocks={changed_blocks}")
    return 0


if __name__ == "__main__":
    sys.exit(main())
