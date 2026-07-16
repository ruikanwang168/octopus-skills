#!/usr/bin/env python3
"""Shared helpers for Prototype Annotator Page Specs Lite."""

from __future__ import annotations

import json
import re
import shutil
from datetime import datetime, timezone
from pathlib import Path
from typing import Iterable


ANNOTATION_DIR_NAME = "prototype-annotator"
LEGACY_ANNOTATION_DIR_NAME = ".prototype-annotations"
SPECS_DIR_NAME = "specs"
CURRENT_DIR_NAME = "current"
HISTORY_DIR_NAME = "history"
REGISTRY_FILE_NAME = "registry.json"

DOC_NAME_RE = re.compile(
    r"prd|产品|需求|用户故事|业务|说明|交互|原型|spec|requirement|story|brief",
    re.I,
)


def now_iso() -> str:
    return datetime.now(timezone.utc).replace(microsecond=0).isoformat().replace("+00:00", "Z")


def safe_timestamp() -> str:
    return datetime.now(timezone.utc).strftime("%Y%m%d-%H%M%S")


def annotation_root(target: Path) -> Path:
    return target.parent if target.is_file() else target


def annotator_dir(target: Path) -> Path:
    return annotation_root(target) / ANNOTATION_DIR_NAME


def default_spec_root(target: Path) -> Path:
    return annotator_dir(target) / SPECS_DIR_NAME


def current_dir(spec_root: Path) -> Path:
    return spec_root / CURRENT_DIR_NAME


def history_dir(spec_root: Path, page_key: str) -> Path:
    return spec_root / HISTORY_DIR_NAME / page_key


def registry_path(spec_root: Path) -> Path:
    return spec_root / REGISTRY_FILE_NAME


def spec_path_for(spec_root: Path, page_key: str) -> Path:
    return current_dir(spec_root) / f"{page_key}.md"


def default_page_map(target: Path) -> Path:
    preferred = annotator_dir(target) / "page-map.json"
    if preferred.exists():
        return preferred
    legacy = annotation_root(target) / LEGACY_ANNOTATION_DIR_NAME / "page-map.json"
    if legacy.exists():
        return legacy
    return preferred


def default_annotations(target: Path) -> Path:
    preferred = annotator_dir(target) / "annotations.json"
    if preferred.exists():
        return preferred
    legacy = annotation_root(target) / LEGACY_ANNOTATION_DIR_NAME / "annotations.json"
    if legacy.exists():
        return legacy
    return preferred


def default_candidates(target: Path) -> Path:
    preferred = annotator_dir(target) / "annotation-candidates.json"
    if preferred.exists():
        return preferred
    legacy = annotation_root(target) / LEGACY_ANNOTATION_DIR_NAME / "annotation-candidates.json"
    if legacy.exists():
        return legacy
    return preferred


def default_product_context(target: Path) -> Path:
    preferred = annotator_dir(target) / "product-context.json"
    if preferred.exists():
        return preferred
    legacy = annotation_root(target) / LEGACY_ANNOTATION_DIR_NAME / "product-context.json"
    if legacy.exists():
        return legacy
    return preferred


def read_json(path: Path, default: dict | None = None) -> dict:
    try:
        return json.loads(path.read_text(encoding="utf-8"))
    except (OSError, json.JSONDecodeError):
        return {} if default is None else default


def write_json(path: Path, payload: dict) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    temp = path.with_suffix(path.suffix + ".tmp")
    temp.write_text(json.dumps(payload, ensure_ascii=False, indent=2) + "\n", encoding="utf-8")
    temp.replace(path)


def normalize(value: str) -> str:
    return re.sub(r"\s+", " ", value or "").strip()


def strip_quotes(value: str) -> str:
    value = value.strip()
    if len(value) >= 2 and value[0] == value[-1] and value[0] in {"'", '"'}:
        return value[1:-1]
    return value


def parse_frontmatter(markdown: str) -> tuple[dict, str]:
    if not markdown.startswith("---\n"):
        return {}, markdown
    end = markdown.find("\n---", 4)
    if end < 0:
        return {}, markdown
    raw = markdown[4:end]
    body = markdown[end + len("\n---") :].lstrip("\n")
    frontmatter: dict[str, object] = {}
    for line in raw.splitlines():
        if not line.strip() or ":" not in line:
            continue
        key, value = line.split(":", 1)
        key = key.strip()
        raw_value = value.strip()
        lowered = raw_value.lower()
        if lowered == "null":
            frontmatter[key] = None
        elif lowered == "true":
            frontmatter[key] = True
        elif lowered == "false":
            frontmatter[key] = False
        elif re.fullmatch(r"-?\d+", raw_value):
            frontmatter[key] = int(raw_value)
        else:
            frontmatter[key] = strip_quotes(raw_value)
    return frontmatter, body


def format_frontmatter(data: dict) -> str:
    lines = ["---"]
    for key, value in data.items():
        if value is None:
            rendered = "null"
        elif isinstance(value, bool):
            rendered = "true" if value else "false"
        elif isinstance(value, int):
            rendered = str(value)
        else:
            escaped = str(value).replace("\\", "\\\\").replace('"', '\\"')
            rendered = f'"{escaped}"'
        lines.append(f"{key}: {rendered}")
    lines.append("---")
    return "\n".join(lines) + "\n\n"


def markdown_sections(markdown: str) -> dict[str, str]:
    _, body = parse_frontmatter(markdown)
    sections: dict[str, list[str]] = {}
    current = ""
    for line in body.splitlines():
        match = re.match(r"^(#{2,4})\s+(.+?)\s*$", line)
        if match:
            current = normalize(match.group(2))
            sections.setdefault(current, [])
            continue
        if current:
            sections.setdefault(current, []).append(line)
    return {key: "\n".join(lines).strip() for key, lines in sections.items()}


def is_protected_spec(markdown: str) -> bool:
    frontmatter, _ = parse_frontmatter(markdown)
    if frontmatter.get("overwriteProtected") is True:
        return True
    last_manual = frontmatter.get("lastManualEditedAt")
    return bool(last_manual not in {None, "", "null"})


def snapshot_before_overwrite(path: Path, spec_root: Path, page_key: str, keep_history: int) -> Path | None:
    if keep_history <= 0 or not path.exists():
        return None
    target_dir = history_dir(spec_root, page_key)
    target_dir.mkdir(parents=True, exist_ok=True)
    if keep_history == 1:
        snapshot = target_dir / "latest.before-overwrite.md"
    else:
        snapshot = target_dir / f"{safe_timestamp()}.before-overwrite.md"
    shutil.copy2(path, snapshot)
    prune_history(target_dir, keep_history)
    return snapshot


def prune_history(target_dir: Path, keep_history: int) -> None:
    if keep_history <= 1:
        return
    snapshots = sorted(
        target_dir.glob("*.before-overwrite.md"),
        key=lambda item: item.stat().st_mtime,
        reverse=True,
    )
    for stale in snapshots[keep_history:]:
        stale.unlink(missing_ok=True)


def discover_doc_paths(root: Path, explicit: Iterable[str]) -> list[Path]:
    paths: list[Path] = []
    for item in explicit:
        path = Path(item).resolve()
        if path.is_file():
            paths.append(path)
        elif path.is_dir():
            paths.extend(sorted(path.rglob("*.md")))
            paths.extend(sorted(path.rglob("*.txt")))
    if not paths:
        for candidate in sorted(root.rglob("*")):
            if not candidate.is_file() or candidate.suffix.lower() not in {".md", ".txt"}:
                continue
            try:
                relative_parts = candidate.relative_to(root).parts
            except ValueError:
                relative_parts = candidate.parts
            if any(part in {"node_modules", "dist", "build", ANNOTATION_DIR_NAME, LEGACY_ANNOTATION_DIR_NAME} for part in relative_parts):
                continue
            if DOC_NAME_RE.search(candidate.name):
                paths.append(candidate)
        if not paths and (root / "README.md").exists():
            paths.append(root / "README.md")
    unique: list[Path] = []
    seen: set[Path] = set()
    for path in paths:
        if path in seen:
            continue
        seen.add(path)
        unique.append(path)
    return unique[:12]


def load_docs(paths: Iterable[Path], limit_per_doc: int = 30000) -> list[dict]:
    docs: list[dict] = []
    for path in paths:
        try:
            text = path.read_text(encoding="utf-8", errors="ignore")[:limit_per_doc]
        except OSError:
            continue
        if text.strip():
            docs.append({"path": str(path), "text": text})
    return docs


def relative_to_root(path: Path, root: Path) -> str:
    try:
        return path.relative_to(root).as_posix()
    except ValueError:
        return path.as_posix()


def registry_page_entry(page: dict, spec_file: Path, project_root: Path, source_type: str, generated_at: str) -> dict:
    page_key = str(page.get("pageKey") or spec_file.stem)
    return {
        "pageKey": page_key,
        "pageName": str(page.get("title") or page.get("pageName") or page_key),
        "path": str(page.get("path") or ""),
        "route": str(page.get("route") or ""),
        "specPath": relative_to_root(spec_file, project_root),
        "sourceType": source_type,
        "lastGeneratedAt": generated_at,
    }


def write_registry(spec_root: Path, pages: list[dict], project_root: Path, source_type: str) -> None:
    generated_at = now_iso()
    registry = {
        "specSchemaVersion": 1,
        "storageFormat": "markdown",
        "mode": "page-specs-lite",
        "historyPolicy": "latest-before-overwrite",
        "pages": [
            registry_page_entry(page, spec_path_for(spec_root, str(page.get("pageKey"))), project_root, source_type, generated_at)
            for page in pages
            if page.get("pageKey")
        ],
        "lastUpdated": generated_at,
    }
    write_json(registry_path(spec_root), registry)


def spec_files(spec_root: Path) -> list[Path]:
    folder = current_dir(spec_root)
    if not folder.exists():
        return []
    return sorted(folder.glob("*.md"))
