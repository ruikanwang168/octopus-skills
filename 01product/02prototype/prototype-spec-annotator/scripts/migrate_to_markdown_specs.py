#!/usr/bin/env python3
"""Migrate legacy prototype specs to Markdown-first current specs.

Supported inputs:
- current/*.json legacy specs
- inline PROTO_SPEC marker blocks in HTML/Vue/JSX/TSX files

The script preserves source files. It writes Markdown specs and registry entries
only, and snapshots an existing Markdown spec before overwriting it.
"""

from __future__ import annotations

import argparse
import html
import json
import re
import sys
from datetime import datetime
from pathlib import Path
from typing import Iterable


SPEC_SCHEMA_VERSION = 2
SPEC_ROOT_CANDIDATES = ("src/page-specs", "page-specs", "src/prototype-specs", "prototype-specs")
TEXT_EXTENSIONS = {".html", ".htm", ".vue", ".jsx", ".tsx", ".js", ".ts"}
IGNORE_DIRS = {".git", ".next", ".nuxt", "build", "coverage", "dist", "history", "node_modules", "out", "release"}
MARKER_BLOCKS = (
    re.compile(r"<!--\s*PROTO_SPEC:BEGIN(?P<meta>.*?)-->(?P<body>[\s\S]*?)<!--\s*PROTO_SPEC:END(?P<meta2>.*?)-->", re.S),
    re.compile(r"\{/\*\s*PROTO_SPEC:BEGIN(?P<meta>.*?)\*/\}(?P<body>[\s\S]*?)\{/\*\s*PROTO_SPEC:END(?P<meta2>.*?)\*/\}", re.S),
    re.compile(r"/\*\s*PROTO_SPEC:BEGIN(?P<meta>.*?)\*/(?P<body>[\s\S]*?)/\*\s*PROTO_SPEC:END(?P<meta2>.*?)\*/", re.S),
)
DATA_SPEC_PAGE = re.compile(r'data-spec-page\s*=\s*["\']([^"\']+)["\']', re.I)
DATA_SPEC_ID = re.compile(r'data-spec-id\s*=\s*["\']([^"\']+)["\']', re.I)


def parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser(description="Migrate legacy page specs to Markdown-first files.")
    parser.add_argument("--root", default=".", help="Project root. Defaults to current directory.")
    parser.add_argument("--dry-run", action="store_true", help="Preview changes without writing files.")
    parser.add_argument("--force", action="store_true", help="Overwrite existing Markdown specs after snapshotting them.")
    parser.add_argument("--json-only", action="store_true", help="Migrate only legacy current/*.json files.")
    parser.add_argument("--inline-only", action="store_true", help="Migrate only inline marked spec blocks.")
    parser.add_argument("--spec-root", help="Explicit spec root relative to project root.")
    return parser.parse_args()


def now_iso() -> str:
    return datetime.now().astimezone().isoformat(timespec="seconds")


def stamp() -> str:
    return datetime.now().astimezone().isoformat(timespec="seconds").replace(":", "-")


def batch_id() -> str:
    return "spec-migration-" + datetime.now().astimezone().strftime("%Y%m%d-%H%M%S")


def detect_spec_root(root: Path, explicit: str | None = None) -> Path:
    if explicit:
        return (root / explicit).resolve()
    for candidate in SPEC_ROOT_CANDIDATES:
        path = root / candidate
        if (path / "current").is_dir() or path.is_dir():
            return path
    if (root / "src").exists():
        return root / "src" / "page-specs"
    return root / "prototype-specs"


def ensure_dir(path: Path, dry_run: bool) -> None:
    if not dry_run:
        path.mkdir(parents=True, exist_ok=True)


def scalar(value: object) -> str:
    if value is None:
        return "null"
    if isinstance(value, bool):
        return "true" if value else "false"
    if isinstance(value, (int, float)):
        return str(value)
    return json.dumps(str(value), ensure_ascii=False)


def escape_cell(value: object) -> str:
    return str(value).replace("|", "\\|").replace("\n", " ").strip()


def normalize_page_key(value: str) -> str:
    key = value.strip().replace("\\", "/").split("/")[-1]
    key = re.sub(r"\.[A-Za-z0-9]+$", "", key)
    key = re.sub(r"[^A-Za-z0-9\u4e00-\u9fa5_-]+", "-", key)
    key = re.sub(r"-+", "-", key).strip("-_")
    return key or "page-spec"


def titleize(page_key: str) -> str:
    return page_key.replace("-", " ").replace("_", " ").title()


def json_spec_to_markdown(spec: dict, migration_source: str | None = None) -> tuple[str, str, str]:
    page_key = normalize_page_key(str(spec.get("pageKey") or "page-spec"))
    page_name = str(spec.get("pageName") or titleize(page_key))
    meta = spec.get("meta") if isinstance(spec.get("meta"), dict) else {}
    frontmatter = {
        "specSchemaVersion": SPEC_SCHEMA_VERSION,
        "storageFormat": "markdown",
        "pageKey": page_key,
        "version": int(spec.get("version") or 1),
        "pageName": page_name,
        "pageType": spec.get("pageType") or "待确认",
        "pageShape": spec.get("pageShape") or "待确认",
        "sourceType": meta.get("sourceType") or "mixed",
        "overwriteProtected": bool(meta.get("overwriteProtected")),
        "specId": meta.get("specId") or f"{page_key}-spec",
        "batchId": meta.get("batchId") or batch_id(),
        "lastGeneratedAt": meta.get("lastGeneratedAt"),
        "lastManualEditedAt": meta.get("lastManualEditedAt") or now_iso(),
    }
    if migration_source:
        frontmatter["migrationSource"] = migration_source

    lines = ["---"]
    lines.extend(f"{key}: {scalar(value)}" for key, value in frontmatter.items())
    lines.extend(["---", "", f"# {page_name}", "", "## 页面摘要", ""])
    lines.extend([str(spec.get("summary") or f"从旧说明迁移而来，需复核 {page_name} 的页面目标。"), ""])

    secondary = spec.get("secondarySurfaces")
    if isinstance(secondary, list) and secondary:
        lines.extend(["## 二级承载面", ""])
        lines.extend(f"- {item}" for item in secondary if str(item).strip())
        lines.append("")

    sections = spec.get("sections") if isinstance(spec.get("sections"), list) else []
    if not sections:
        sections = [{"title": "【页面说明】规则说明", "rules": ["从旧说明迁移而来，需根据真实页面补充可评审规则。"]}]
    for section in sections:
        if not isinstance(section, dict):
            continue
        lines.extend([f"## {section.get('title') or '【页面说明】规则说明'}", ""])
        rules = section.get("rules") if isinstance(section.get("rules"), list) else []
        if not rules:
            rules = ["从旧说明迁移而来，需补充具体规则。"]
        for rule in rules:
            if str(rule).strip():
                lines.append(f"- {str(rule).strip()}")
        lines.append("")
        fields = section.get("fields") if isinstance(section.get("fields"), list) else []
        if fields:
            lines.extend(["### 字段说明", "", "| 字段 | 形态 | 必填 | 说明 |", "|---|---|---|---|"])
            for field in fields:
                if not isinstance(field, dict):
                    continue
                lines.append(
                    f"| {escape_cell(field.get('name', ''))} | {escape_cell(field.get('type') or field.get('value') or '')} | {'是' if field.get('required') else '否'} | {escape_cell(field.get('description') or field.get('value') or '')} |"
                )
            lines.append("")
    return page_key, page_name, "\n".join(lines).rstrip() + "\n"


def plain_text_from_html(raw: str) -> str:
    text = re.sub(r"<script[\s\S]*?</script>", " ", raw, flags=re.I)
    text = re.sub(r"<style[\s\S]*?</style>", " ", text, flags=re.I)
    text = re.sub(r"<[^>]+>", " ", text)
    text = html.unescape(text)
    text = re.sub(r"\s+", " ", text).strip()
    return text


def inline_block_to_markdown(page_key: str, page_name: str, block_text: str, source: str) -> tuple[str, str, str]:
    plain = plain_text_from_html(block_text)
    sentences = [part.strip(" ;；。") for part in re.split(r"[。；;\n]", plain) if part.strip()]
    rules = sentences[:12] or ["从旧页面内说明迁移而来，需人工复核。"]
    spec = {
        "pageKey": page_key,
        "pageName": page_name,
        "version": 1,
        "pageType": "待确认",
        "pageShape": "待确认",
        "summary": f"{page_name} 的需求说明从旧页面内说明迁移而来，需结合真实页面复核。",
        "sections": [{"title": "【页面说明】规则说明", "rules": rules}],
        "meta": {
            "sourceType": "mixed",
            "lastGeneratedAt": None,
            "lastManualEditedAt": now_iso(),
            "overwriteProtected": False,
            "specId": f"{page_key}-spec",
            "batchId": batch_id(),
        },
    }
    return json_spec_to_markdown(spec, source)


def write_markdown(spec_root: Path, page_key: str, markdown: str, dry_run: bool, force: bool) -> str:
    current_dir = spec_root / "current"
    history_dir = spec_root / "history" / page_key
    target = current_dir / f"{page_key}.md"
    if target.exists() and not force:
        return f"SKIP existing {target} (use --force to overwrite with snapshot)"
    if dry_run:
        return f"WOULD write {target}"
    ensure_dir(current_dir, dry_run=False)
    ensure_dir(history_dir, dry_run=False)
    if target.exists():
        snapshot = history_dir / f"{stamp()}.before-migration-overwrite.md"
        snapshot.write_text(target.read_text(encoding="utf-8"), encoding="utf-8")
    target.write_text(markdown, encoding="utf-8")
    return f"WROTE {target}"


def update_registry(spec_root: Path, pages: list[tuple[str, str]], dry_run: bool) -> str:
    registry_path = spec_root / "registry.json"
    payload = {"specSchemaVersion": SPEC_SCHEMA_VERSION, "storageFormat": "markdown", "pages": [], "lastUpdated": ""}
    if registry_path.exists():
        try:
            existing = json.loads(registry_path.read_text(encoding="utf-8"))
            if isinstance(existing, dict):
                payload.update(existing)
        except json.JSONDecodeError:
            pass
    existing_pages = payload.get("pages") if isinstance(payload.get("pages"), list) else []
    by_key = {
        entry.get("pageKey"): entry
        for entry in existing_pages
        if isinstance(entry, dict) and isinstance(entry.get("pageKey"), str)
    }
    for page_key, page_name in pages:
        by_key[page_key] = {**by_key.get(page_key, {}), "pageKey": page_key, "pageName": page_name}
    payload["specSchemaVersion"] = SPEC_SCHEMA_VERSION
    payload["storageFormat"] = "markdown"
    payload["pages"] = sorted(by_key.values(), key=lambda item: item.get("pageKey", ""))
    payload["lastUpdated"] = now_iso()
    if dry_run:
        return f"WOULD update {registry_path}"
    ensure_dir(registry_path.parent, dry_run=False)
    registry_path.write_text(json.dumps(payload, ensure_ascii=False, indent=2) + "\n", encoding="utf-8")
    return f"UPDATED {registry_path}"


def iter_candidate_files(root: Path) -> Iterable[Path]:
    for path in root.rglob("*"):
        try:
            parts = path.relative_to(root).parts
        except ValueError:
            continue
        if any(part in IGNORE_DIRS for part in parts):
            continue
        if path.is_file() and path.suffix.lower() in TEXT_EXTENSIONS:
            yield path


def migrate_json(spec_root: Path, dry_run: bool, force: bool) -> list[tuple[str, str, str]]:
    migrated: list[tuple[str, str, str]] = []
    current_dir = spec_root / "current"
    for path in sorted(current_dir.glob("*.json")):
        try:
            payload = json.loads(path.read_text(encoding="utf-8"))
        except (json.JSONDecodeError, OSError) as error:
            migrated.append((path.stem, titleize(path.stem), f"SKIP invalid JSON {path}: {error}"))
            continue
        if not isinstance(payload, dict):
            migrated.append((path.stem, titleize(path.stem), f"SKIP non-object JSON {path}"))
            continue
        page_key, page_name, markdown = json_spec_to_markdown(payload, str(path))
        status = write_markdown(spec_root, page_key, markdown, dry_run, force)
        migrated.append((page_key, page_name, status))
    return migrated


def meta_value(meta: str, key: str) -> str | None:
    match = re.search(rf"{key}\s*=\s*([^\s]+)", meta)
    if not match:
        return None
    return match.group(1).strip("\"' ")


def migrate_inline(root: Path, spec_root: Path, dry_run: bool, force: bool) -> list[tuple[str, str, str]]:
    migrated: list[tuple[str, str, str]] = []
    seen: set[str] = set()
    for path in iter_candidate_files(root):
        raw = path.read_text(encoding="utf-8", errors="ignore")
        for pattern in MARKER_BLOCKS:
            for match in pattern.finditer(raw):
                meta = match.group("meta") or ""
                body = match.group("body") or ""
                page_key = meta_value(meta, "page") or meta_value(meta, "pageKey")
                if not page_key:
                    page_match = DATA_SPEC_PAGE.search(body)
                    page_key = page_match.group(1) if page_match else path.stem
                page_key = normalize_page_key(page_key)
                if page_key in seen:
                    continue
                seen.add(page_key)
                page_name = titleize(page_key)
                _id_match = DATA_SPEC_ID.search(body)
                _, _, markdown = inline_block_to_markdown(page_key, page_name, body, str(path))
                status = write_markdown(spec_root, page_key, markdown, dry_run, force)
                migrated.append((page_key, page_name, status))
    return migrated


def main() -> int:
    args = parse_args()
    if args.json_only and args.inline_only:
        print("ERROR: choose only one of --json-only or --inline-only", file=sys.stderr)
        return 2

    root = Path(args.root).resolve()
    spec_root = detect_spec_root(root, args.spec_root)
    all_pages: list[tuple[str, str]] = []

    if not args.inline_only:
        for page_key, page_name, status in migrate_json(spec_root, args.dry_run, args.force):
            print(status)
            if status.startswith(("WROTE", "WOULD")):
                all_pages.append((page_key, page_name))

    if not args.json_only:
        for page_key, page_name, status in migrate_inline(root, spec_root, args.dry_run, args.force):
            print(status)
            if status.startswith(("WROTE", "WOULD")):
                all_pages.append((page_key, page_name))

    if all_pages:
        print(update_registry(spec_root, all_pages, args.dry_run))
    else:
        print("No migratable specs found.")

    if args.dry_run:
        print("Dry run complete; no files were written.")
    return 0


if __name__ == "__main__":
    sys.exit(main())
