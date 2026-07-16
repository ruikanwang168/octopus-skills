#!/usr/bin/env python3
"""Initialize a Markdown-first prototype spec workspace.

The workspace is self-contained inside the target project and does not depend
on unrelated application source code.
"""

from __future__ import annotations

import argparse
import json
import shutil
from datetime import datetime
from pathlib import Path


SPEC_SCHEMA_VERSION = 2


def parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser(
        description="Initialize Markdown-first page-spec storage and sync helper scripts."
    )
    parser.add_argument("--root", required=True, help="Target project root directory.")
    parser.add_argument(
        "--source-scripts",
        help="Optional source directory containing this skill's scripts. Defaults to current script directory.",
    )
    parser.add_argument(
        "--skip-copy-scripts",
        action="store_true",
        help="Do not sync helper scripts into <root>/scripts.",
    )
    parser.add_argument(
        "--seed-page",
        action="append",
        default=[],
        metavar="PAGE_KEY[:PAGE_NAME[:SOURCE_FILE[:ROUTE]]]",
        help="Create a starter current spec Markdown file. Repeatable.",
    )
    parser.add_argument(
        "--legacy-json",
        action="store_true",
        help="Seed legacy current/*.json files instead of Markdown. Use only for old projects.",
    )
    return parser.parse_args()


def now_iso() -> str:
    return datetime.now().astimezone().isoformat(timespec="seconds")


def batch_id() -> str:
    return "spec-batch-" + datetime.now().astimezone().strftime("%Y%m%d-%H%M%S")


def detect_spec_dir(root: Path) -> Path:
    if (root / "src").exists():
        return root / "src" / "page-specs"
    return root / "prototype-specs"


def ensure_dir(path: Path) -> None:
    path.mkdir(parents=True, exist_ok=True)


def parse_seed_pages(raw_pages: list[str]) -> list[dict[str, str]]:
    parsed: list[dict[str, str]] = []
    for raw in raw_pages:
        parts = [part.strip() for part in raw.split(":")]
        if not parts or not parts[0]:
            continue
        page_key = parts[0]
        page_name = parts[1] if len(parts) > 1 and parts[1] else titleize(page_key)
        source_file = parts[2] if len(parts) > 2 else ""
        route_hint = parts[3] if len(parts) > 3 else ""
        parsed.append(
            {
                "pageKey": page_key,
                "pageName": page_name,
                "sourceFile": source_file,
                "routeHint": route_hint,
            }
        )
    return parsed


def titleize(page_key: str) -> str:
    return page_key.replace("-", " ").replace("_", " ").title()


def load_json(path: Path, fallback: dict) -> dict:
    if not path.exists():
        return fallback
    try:
        payload = json.loads(path.read_text(encoding="utf-8"))
    except (json.JSONDecodeError, OSError):
        return fallback
    return payload if isinstance(payload, dict) else fallback


def write_json(path: Path, payload: dict) -> None:
    ensure_dir(path.parent)
    path.write_text(json.dumps(payload, ensure_ascii=False, indent=2) + "\n", encoding="utf-8")


def sync_scripts(source_dir: Path, dest_dir: Path) -> list[Path]:
    copied: list[Path] = []
    if source_dir.resolve() == dest_dir.resolve():
        return copied
    ensure_dir(dest_dir)
    for script in sorted(source_dir.glob("*.py")):
        target = dest_dir / script.name
        shutil.copy2(script, target)
        copied.append(target)
    return copied


def write_registry(registry_file: Path, seed_pages: list[dict[str, str]]) -> None:
    payload = load_json(
        registry_file,
        {
            "specSchemaVersion": SPEC_SCHEMA_VERSION,
            "storageFormat": "markdown",
            "pages": [],
            "lastUpdated": "",
        },
    )
    pages = payload.get("pages")
    if not isinstance(pages, list):
        pages = []

    by_key: dict[str, dict] = {}
    for entry in pages:
        if isinstance(entry, dict) and isinstance(entry.get("pageKey"), str):
            by_key[entry["pageKey"]] = entry

    for page in seed_pages:
        existing = by_key.get(page["pageKey"], {})
        by_key[page["pageKey"]] = {
            **existing,
            "pageKey": page["pageKey"],
            "pageName": page["pageName"],
            **({"sourceFile": page["sourceFile"]} if page["sourceFile"] else {}),
            **({"routeHint": page["routeHint"]} if page["routeHint"] else {}),
        }

    payload["specSchemaVersion"] = SPEC_SCHEMA_VERSION
    payload["storageFormat"] = "markdown"
    payload["pages"] = sorted(by_key.values(), key=lambda item: item.get("pageKey", ""))
    payload["lastUpdated"] = now_iso()
    write_json(registry_file, payload)


def write_viewer_config(viewer_config_file: Path) -> None:
    existing = load_json(viewer_config_file, {})
    payload = {
        "specSchemaVersion": SPEC_SCHEMA_VERSION,
        "visibilityMode": existing.get("visibilityMode") or "manual-toggle",
        "viewerMode": existing.get("viewerMode") or "dual-view",
        "htmlSaveMode": existing.get("htmlSaveMode") or "file-service",
        "updatedAt": now_iso(),
    }
    write_json(viewer_config_file, payload)


def make_seed_payload(page: dict[str, str]) -> dict:
    now = now_iso()
    return {
        "specSchemaVersion": SPEC_SCHEMA_VERSION,
        "storageFormat": "markdown",
        "pageKey": page["pageKey"],
        "version": 1,
        "pageName": page["pageName"],
        "pageType": "待确认",
        "pageShape": "待确认",
        "summary": f"待根据真实页面内容补充 {page['pageName']} 的页面说明。",
        "secondarySurfaces": [],
        "sections": [
            {
                "id": "overview",
                "title": "【页面总览】规则说明",
                "rules": ["待根据真实页面结构补充模块说明。"],
                "fields": [],
            }
        ],
        "meta": {
            "sourceType": "generated",
            "lastGeneratedAt": now,
            "lastManualEditedAt": None,
            "overwriteProtected": False,
            "specId": f"{page['pageKey']}-spec",
            "batchId": batch_id(),
        },
    }


def scalar(value: object) -> str:
    if value is None:
        return "null"
    if isinstance(value, bool):
        return "true" if value else "false"
    if isinstance(value, (int, float)):
        return str(value)
    return json.dumps(str(value), ensure_ascii=False)


def spec_to_markdown(spec: dict) -> str:
    meta = spec.get("meta") if isinstance(spec.get("meta"), dict) else {}
    frontmatter = {
        "specSchemaVersion": spec.get("specSchemaVersion", SPEC_SCHEMA_VERSION),
        "storageFormat": "markdown",
        "pageKey": spec.get("pageKey", ""),
        "version": spec.get("version", 1),
        "pageName": spec.get("pageName", ""),
        "pageType": spec.get("pageType", "待确认"),
        "pageShape": spec.get("pageShape", "待确认"),
        "sourceType": meta.get("sourceType", "generated"),
        "overwriteProtected": meta.get("overwriteProtected", False),
        "specId": meta.get("specId", f"{spec.get('pageKey', '')}-spec"),
        "batchId": meta.get("batchId", batch_id()),
        "lastGeneratedAt": meta.get("lastGeneratedAt"),
        "lastManualEditedAt": meta.get("lastManualEditedAt"),
    }
    lines = ["---"]
    lines.extend(f"{key}: {scalar(value)}" for key, value in frontmatter.items())
    lines.extend(["---", "", f"# {spec.get('pageName') or spec.get('pageKey')}", "", "## 页面摘要", ""])
    lines.extend([str(spec.get("summary") or "暂无页面摘要。"), ""])

    secondary = spec.get("secondarySurfaces")
    if isinstance(secondary, list) and secondary:
        lines.extend(["## 二级承载面", ""])
        lines.extend(f"- {item}" for item in secondary if str(item).strip())
        lines.append("")

    sections = spec.get("sections") if isinstance(spec.get("sections"), list) else []
    for section in sections:
        if not isinstance(section, dict):
            continue
        lines.extend([f"## {section.get('title') or '【未命名】规则说明'}", ""])
        rules = section.get("rules") if isinstance(section.get("rules"), list) else []
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
                    "| {name} | {kind} | {required} | {desc} |".format(
                        name=escape_cell(field.get("name", "")),
                        kind=escape_cell(field.get("type") or field.get("value") or ""),
                        required="是" if field.get("required") else "否",
                        desc=escape_cell(field.get("description") or field.get("value") or ""),
                    )
                )
            lines.append("")

    return "\n".join(lines).rstrip() + "\n"


def escape_cell(value: object) -> str:
    return str(value).replace("|", "\\|").replace("\n", " ").strip()


def seed_current_specs(current_dir: Path, history_dir: Path, seed_pages: list[dict[str, str]], legacy_json: bool) -> list[Path]:
    created: list[Path] = []
    for page in seed_pages:
        ensure_dir(history_dir / page["pageKey"])
        payload = make_seed_payload(page)
        suffix = "json" if legacy_json else "md"
        target = current_dir / f"{page['pageKey']}.{suffix}"
        if target.exists():
            continue
        if legacy_json:
            target.write_text(json.dumps(payload, ensure_ascii=False, indent=2) + "\n", encoding="utf-8")
        else:
            target.write_text(spec_to_markdown(payload), encoding="utf-8")
        created.append(target)
    return created


def init_project(target_root: Path, source_scripts: Path, copy_scripts: bool, seed_pages: list[dict[str, str]], legacy_json: bool) -> None:
    spec_dir = detect_spec_dir(target_root)
    current_dir = spec_dir / "current"
    history_dir = spec_dir / "history"
    scripts_dest = target_root / "scripts"

    for path in (current_dir, history_dir):
        ensure_dir(path)
        print(f"Ensured directory: {path}")
    if copy_scripts:
        ensure_dir(scripts_dest)
        print(f"Ensured directory: {scripts_dest}")

    for page in seed_pages:
        ensure_dir(history_dir / page["pageKey"])

    write_registry(spec_dir / "registry.json", seed_pages)
    print(f"Ensured registry: {spec_dir / 'registry.json'}")
    write_viewer_config(spec_dir / "viewer-config.json")
    print(f"Ensured viewer config: {spec_dir / 'viewer-config.json'}")

    seeded_files = seed_current_specs(current_dir, history_dir, seed_pages, legacy_json)
    for path in seeded_files:
        print(f"Created starter spec: {path}")

    if copy_scripts:
        copied = sync_scripts(source_scripts, scripts_dest)
        if copied:
            for path in copied:
                print(f"Synced script: {path}")
        else:
            print("Scripts already in place; no sync needed.")

    print("\nInitialization complete.")
    print(f"- Spec root: {spec_dir}")
    print(f"- Current files: {current_dir}")
    print(f"- History files: {history_dir}")
    print(f"- Default format: {'legacy JSON' if legacy_json else 'Markdown'}")
    print("- Next step: create or migrate current/<pageKey>.md files, then run validate_editable_specs.py.")


def main() -> None:
    args = parse_args()
    target_root = Path(args.root).resolve()
    source_scripts = Path(args.source_scripts).resolve() if args.source_scripts else Path(__file__).resolve().parent
    seed_pages = parse_seed_pages(args.seed_page)
    init_project(
        target_root=target_root,
        source_scripts=source_scripts,
        copy_scripts=not args.skip_copy_scripts,
        seed_pages=seed_pages,
        legacy_json=args.legacy_json,
    )


if __name__ == "__main__":
    main()
