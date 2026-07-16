#!/usr/bin/env python3
"""Validate Prototype Annotator Page Specs Lite assets."""

from __future__ import annotations

import argparse
import filecmp
import re
from pathlib import Path

from page_specs import (
    annotation_root,
    default_annotations,
    default_page_map,
    default_spec_root,
    markdown_sections,
    parse_frontmatter,
    read_json,
    relative_to_root,
    registry_path,
    spec_files,
    spec_path_for,
)


REQUIRED_SECTIONS = ("页面摘要", "待确认")
USEFUL_SECTIONS = ("核心内容", "业务流程", "功能操作", "结果区", "筛选条件", "状态与异常")
DEPLOY_PUBLIC_FRAMEWORK_DEPS = {"react", "vue", "vite"}


def normalize(value: str) -> str:
    return re.sub(r"\s+", " ", value or "").strip()


def page_map_pages(page_map: dict) -> dict[str, dict]:
    return {
        str(page.get("pageKey")): page
        for page in page_map.get("pages", []) or []
        if page.get("pageKey")
    }


def has_section(sections: dict[str, str], name: str) -> bool:
    return any(key == name or name in key for key in sections)


def page_level_p_annotations(data: dict) -> dict[str, dict]:
    result: dict[str, dict] = {}
    for ann in data.get("annotations", []) or []:
        page_key = str(ann.get("pageKey") or "")
        if str(ann.get("annotationType") or "") == "P" and not str(ann.get("surfaceId") or "").strip():
            result[page_key] = ann
    return result


def validate_spec_file(path: Path, expected_page_key: str, page_map: dict[str, dict]) -> tuple[list[str], list[str]]:
    errors: list[str] = []
    warnings: list[str] = []
    markdown = path.read_text(encoding="utf-8")
    frontmatter, body = parse_frontmatter(markdown)
    page_key = str(frontmatter.get("pageKey") or "")
    if not frontmatter:
        errors.append(f"{path.name}: missing frontmatter")
    if page_key != expected_page_key:
        errors.append(f"{path.name}: frontmatter pageKey {page_key or '<missing>'} does not match filename {expected_page_key}")
    if expected_page_key not in page_map:
        errors.append(f"{path.name}: pageKey {expected_page_key} is not present in page-map.json")
    if not normalize(str(frontmatter.get("pageName") or "")):
        errors.append(f"{path.name}: missing pageName")
    if str(frontmatter.get("storageFormat") or "") != "markdown":
        warnings.append(f"{path.name}: storageFormat should be markdown")
    if not re.search(r"^#\s+.+", body, re.M):
        errors.append(f"{path.name}: missing # page title")
    sections = markdown_sections(markdown)
    for section in REQUIRED_SECTIONS:
        if not has_section(sections, section):
            errors.append(f"{path.name}: missing required section {section}")
    if not any(has_section(sections, section) for section in USEFUL_SECTIONS):
        warnings.append(f"{path.name}: no useful detail section found ({' / '.join(USEFUL_SECTIONS)})")
    if "prototype-specs/current" in markdown or "src/page-specs/current" in markdown:
        warnings.append(f"{path.name}: references external page spec paths; prefer prototype-annotator/specs/current as the owned source")
    return errors, warnings


def validate_registry(spec_root: Path, spec_page_keys: set[str], page_map_keys: set[str]) -> tuple[list[str], list[str]]:
    errors: list[str] = []
    warnings: list[str] = []
    path = registry_path(spec_root)
    if not path.exists():
        errors.append(f"Missing registry: {path}")
        return errors, warnings
    registry = read_json(path)
    if registry.get("mode") != "page-specs-lite":
        warnings.append("registry.json mode should be page-specs-lite")
    registered = {str(page.get("pageKey")) for page in registry.get("pages", []) or [] if page.get("pageKey")}
    missing = sorted(spec_page_keys - registered)
    extra = sorted(registered - page_map_keys)
    if missing:
        errors.append("registry.json does not include spec page(s): " + ", ".join(missing))
    if extra:
        warnings.append("registry.json includes page(s) not in page-map.json: " + ", ".join(extra))
    return errors, warnings


def validate_annotation_links(root: Path, spec_root: Path, annotations_path: Path, spec_page_keys: set[str]) -> tuple[list[str], list[str]]:
    errors: list[str] = []
    warnings: list[str] = []
    if not annotations_path.exists():
        warnings.append(f"annotations.json not found, skipped annotation link check: {annotations_path}")
        return errors, warnings
    data = read_json(annotations_path)
    page_overviews = page_level_p_annotations(data)
    for page_key in sorted(spec_page_keys):
        ann = page_overviews.get(page_key)
        if not ann:
            errors.append(f"{page_key}: missing annotationType=P page overview linked to page spec")
            continue
        expected = relative_to_root(spec_path_for(spec_root, page_key), root)
        spec_ref = str(ann.get("specRef") or "")
        content_source = ann.get("contentSource") if isinstance(ann.get("contentSource"), dict) else {}
        content_ref = str(content_source.get("ref") or "")
        content_type = str(content_source.get("type") or "")
        maintenance_policy = str(ann.get("maintenancePolicy") or "")
        source = ann.get("source") if isinstance(ann.get("source"), dict) else {}
        source_ref = str(source.get("ref") or "")
        source_type = str(source.get("type") or "")
        if source_type != "page-spec":
            errors.append(f"{ann.get('id')}: source.type should be page-spec")
        if content_type != "markdown-file":
            errors.append(f"{ann.get('id')}: contentSource.type should be markdown-file")
        if maintenance_policy != "spec-owned":
            errors.append(f"{ann.get('id')}: maintenancePolicy should be spec-owned")
        if expected not in spec_ref and expected not in source_ref and expected not in content_ref:
            errors.append(f"{ann.get('id')}: does not reference {expected}")
    return errors, warnings


def framework_needs_public_specs(root: Path) -> bool:
    package_json = root / "package.json"
    if not package_json.exists():
        return False
    try:
        data = read_json(package_json)
    except Exception:
        return False
    deps = {}
    deps.update(data.get("dependencies") or {})
    deps.update(data.get("devDependencies") or {})
    return bool(DEPLOY_PUBLIC_FRAMEWORK_DEPS & set(deps))


def validate_public_specs(root: Path, spec_root: Path, spec_page_keys: set[str]) -> tuple[list[str], list[str]]:
    errors: list[str] = []
    warnings: list[str] = []
    if not framework_needs_public_specs(root):
        return errors, warnings
    public_current = root / "public" / "prototype-annotator" / "specs" / "current"
    for page_key in sorted(spec_page_keys):
        source = spec_path_for(spec_root, page_key)
        public_copy = public_current / f"{page_key}.md"
        if not public_copy.exists():
            errors.append(f"{page_key}: missing deploy spec copy: {public_copy}")
        elif not filecmp.cmp(source, public_copy, shallow=False):
            errors.append(f"{page_key}: deploy spec copy is stale: {public_copy}")
    return errors, warnings


def main() -> int:
    parser = argparse.ArgumentParser(description="Validate Prototype Annotator Page Specs Lite files.")
    parser.add_argument("prototype_path", help="HTML file, static directory, or project root")
    parser.add_argument("--spec-root", help="Specs root. Defaults to prototype-annotator/specs")
    parser.add_argument("--page-map", help="Path to page-map.json")
    parser.add_argument("--annotations", help="Path to annotations.json")
    parser.add_argument("--skip-annotation-link-check", action="store_true", help="Only validate Markdown specs and registry")
    args = parser.parse_args()

    target = Path(args.prototype_path).resolve()
    if not target.exists():
        parser.error(f"Path does not exist: {target}")
    root = annotation_root(target)
    spec_root = Path(args.spec_root).resolve() if args.spec_root else default_spec_root(target)
    files = spec_files(spec_root)
    if not files:
        parser.error(f"No page specs found under {spec_root / 'current'}")
    page_map_path = Path(args.page_map).resolve() if args.page_map else default_page_map(target)
    if not page_map_path.exists():
        parser.error(f"Page map does not exist: {page_map_path}")
    page_map = page_map_pages(read_json(page_map_path))
    errors: list[str] = []
    warnings: list[str] = []
    spec_keys = {path.stem for path in files}
    missing_specs = sorted(set(page_map) - spec_keys)
    if missing_specs:
        errors.append("Missing page spec(s): " + ", ".join(missing_specs))
    for path in files:
        file_errors, file_warnings = validate_spec_file(path, path.stem, page_map)
        errors.extend(file_errors)
        warnings.extend(file_warnings)
    registry_errors, registry_warnings = validate_registry(spec_root, spec_keys, set(page_map))
    errors.extend(registry_errors)
    warnings.extend(registry_warnings)
    public_errors, public_warnings = validate_public_specs(root, spec_root, spec_keys)
    errors.extend(public_errors)
    warnings.extend(public_warnings)
    if not args.skip_annotation_link_check:
        annotations_path = Path(args.annotations).resolve() if args.annotations else default_annotations(target)
        link_errors, link_warnings = validate_annotation_links(root, spec_root, annotations_path, spec_keys)
        errors.extend(link_errors)
        warnings.extend(link_warnings)

    for warning in warnings:
        print(f"WARNING: {warning}")
    if errors:
        for error in errors:
            print(f"ERROR: {error}")
        return 1
    print(f"Page specs validation passed. Specs: {len(files)}; warnings: {len(warnings)}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
