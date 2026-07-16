#!/usr/bin/env python3
"""Validate Markdown-first prototype spec workspaces.

The validator supports the current Markdown protocol and legacy JSON files.
It is intentionally self-contained so the skill can be used outside any app.
"""

from __future__ import annotations

import argparse
import json
import re
import sys
from dataclasses import dataclass, field
from pathlib import Path
from typing import Iterable


SPEC_SCHEMA_VERSION = 2
SUMMARY_HEADING = "页面摘要"
SECONDARY_HEADING = "二级承载面"
FIELD_TABLE_HEADING = "字段说明"
CODE_EXTENSIONS = {".js", ".jsx", ".ts", ".tsx", ".vue", ".html", ".htm", ".mjs", ".cjs"}
IGNORE_DIRS = {
    ".git",
    ".next",
    ".nuxt",
    ".turbo",
    "build",
    "coverage",
    "dist",
    "history",
    "node_modules",
    "out",
    "release",
    "tmp",
}
SPEC_ROOT_CANDIDATES = (
    "src/page-specs",
    "page-specs",
    "src/prototype-specs",
    "prototype-specs",
)
INLINE_SPEC_PATTERNS = (
    re.compile(r"PROTO_SPEC:(BEGIN|END)"),
    re.compile(r'data-role\s*=\s*["\']page-spec["\']', re.I),
    re.compile(r'data-spec-origin\s*=\s*["\']prototype-spec-annotator["\']', re.I),
    re.compile(r"\bproto-spec-doc\b", re.I),
    re.compile(r"\binitSpecViewer\s*\(", re.I),
    re.compile(r"\binitProtoSpecViewer\s*\(", re.I),
    re.compile(r"assets/js/spec-viewer\.js", re.I),
    re.compile(r"assets/js/proto-spec-viewer\.js", re.I),
    re.compile(r"\bproto-spec-(?:divider|badge|content|btn|btn-edit|btn-save|btn-toggle)\b", re.I),
)
CURRENT_HTML_VIEWER_MARKERS = (
    "proto-spec-annotator-viewer:start",
    "data-proto-spec-annotator-viewer",
)
GENERATED_VIEWER_PATH_PARTS = (
    "components/proto-spec/",
    "components\\proto-spec\\",
)
RUNTIME_SOURCE_MARKERS = (
    "current/*.md",
    "current/*.json",
    "import.meta.glob",
    "/api/page-specs",
    "/api/prototype-specs",
    "prototype-specs/current",
    "page-specs/current",
    "PageSpecDoc",
    "PageSpecRouteShell",
)
PAGE_KEY_DERIVATION_PATTERNS = (
    re.compile(r"pageKey\s*[:=].{0,220}(pathname|location\.pathname).{0,220}replace\(", re.S),
    re.compile(r"usePageSpec\(\s*(?:location\.)?pathname", re.S),
    re.compile(r"pageKey\s*[:=].{0,220}(label|title|name).{0,220}(toLowerCase\(\)|replace\()", re.S),
)
LOCAL_STORAGE_PATTERN = re.compile(r"\blocalStorage\b")
MONOLITHIC_RULE_EDITOR_PATTERN = re.compile(r"rules\.join\(\s*['\"]\\n['\"]\s*\)|rules\.split\(\s*['\"]\\n['\"]\s*\)")
MARKDOWN_IMAGE_PATTERN = re.compile(r"!\[[^\]]*\]\(([^)\s]+)(?:\s+\"[^\"]*\")?\)")
EXTERNAL_IMAGE_PATTERN = re.compile(r"^(?:https?:|data:|blob:|/)", re.I)


@dataclass
class ValidationReport:
    errors: list[str] = field(default_factory=list)
    warnings: list[str] = field(default_factory=list)
    infos: list[str] = field(default_factory=list)

    def extend(self, other: "ValidationReport") -> None:
        self.errors.extend(other.errors)
        self.warnings.extend(other.warnings)
        self.infos.extend(other.infos)

    def as_dict(self) -> dict[str, list[str]]:
        return {"errors": self.errors, "warnings": self.warnings, "infos": self.infos}


@dataclass
class ParsedMarkdownSpec:
    path: Path
    frontmatter: dict[str, object]
    body: str
    page_key: str
    summary: str
    sections: list[tuple[str, list[str]]]


def parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser(description="Validate Markdown-first prototype spec files.")
    parser.add_argument("--root", default=".", help="Project root. Defaults to current directory.")
    parser.add_argument("--page-key", action="append", default=[], help="Restrict validation to a page key. Repeatable.")
    parser.add_argument("--json", dest="json_output", action="store_true", help="Emit JSON report.")
    parser.add_argument("--strict", action="store_true", help="Treat warnings as failures.")
    return parser.parse_args()


def iter_code_files(root: Path) -> Iterable[Path]:
    for path in root.rglob("*"):
        try:
            relative_parts = path.relative_to(root).parts
        except ValueError:
            continue
        if any(part in IGNORE_DIRS for part in relative_parts):
            continue
        if path.is_file() and path.suffix.lower() in CODE_EXTENSIONS:
            yield path


def read_text(path: Path) -> str | None:
    try:
        return path.read_text(encoding="utf-8")
    except (UnicodeDecodeError, OSError):
        return None


def read_json(path: Path) -> dict | None:
    try:
        payload = json.loads(path.read_text(encoding="utf-8"))
    except (OSError, json.JSONDecodeError):
        return None
    return payload if isinstance(payload, dict) else None


def find_spec_roots(root: Path) -> list[Path]:
    return [root / candidate for candidate in SPEC_ROOT_CANDIDATES if (root / candidate / "current").is_dir()]


def parse_frontmatter_value(raw: str) -> object:
    value = raw.strip()
    if value in {"null", "~"}:
        return None
    if value == "true":
        return True
    if value == "false":
        return False
    if re.fullmatch(r"-?\d+", value):
        try:
            return int(value)
        except ValueError:
            return value
    if re.fullmatch(r"-?\d+\.\d+", value):
        try:
            return float(value)
        except ValueError:
            return value
    if (value.startswith('"') and value.endswith('"')) or (value.startswith("'") and value.endswith("'")):
        try:
            return json.loads(value)
        except json.JSONDecodeError:
            return value[1:-1]
    return value


def parse_frontmatter(raw: str) -> tuple[dict[str, object], str]:
    normalized = raw.replace("\ufeff", "", 1)
    if not normalized.startswith("---\n"):
        return {}, normalized
    end = normalized.find("\n---", 4)
    if end == -1:
        return {}, normalized
    frontmatter_text = normalized[4:end]
    body = normalized[end + 4 :].lstrip("\r\n")
    parsed: dict[str, object] = {}
    for line in frontmatter_text.splitlines():
        if not line.strip() or line.strip().startswith("#"):
            continue
        if ":" not in line:
            continue
        key, value = line.split(":", 1)
        parsed[key.strip()] = parse_frontmatter_value(value)
    return parsed, body


def heading_content(body: str, heading: str) -> str:
    pattern = re.compile(rf"^##\s+{re.escape(heading)}\s*$", re.M)
    match = pattern.search(body)
    if not match:
        return ""
    start = match.end()
    next_heading = re.search(r"^##\s+", body[start:], re.M)
    end = start + next_heading.start() if next_heading else len(body)
    return body[start:end].strip()


def strip_markdown(value: str) -> str:
    value = re.sub(r"^#+\s*", "", value.strip())
    value = re.sub(r"[*_`>#-]", "", value)
    return re.sub(r"\s+", " ", value).strip()


def parse_markdown_spec(path: Path) -> ParsedMarkdownSpec | None:
    raw = read_text(path)
    if raw is None:
        return None
    frontmatter, body = parse_frontmatter(raw)
    page_key = str(frontmatter.get("pageKey") or path.stem)
    summary = strip_markdown(heading_content(body, SUMMARY_HEADING))
    sections = parse_rule_sections(body)
    return ParsedMarkdownSpec(path=path, frontmatter=frontmatter, body=body, page_key=page_key, summary=summary, sections=sections)


def validate_markdown_images(parsed: ParsedMarkdownSpec) -> ValidationReport:
    report = ValidationReport()
    for match in MARKDOWN_IMAGE_PATTERN.finditer(parsed.body):
        src = match.group(1).strip()
        if not src or EXTERNAL_IMAGE_PATTERN.search(src):
            continue
        image_path = (parsed.path.parent / src).resolve()
        if not image_path.is_file():
            report.errors.append(f"{parsed.path}: image asset not found: {src}.")
    return report


def parse_rule_sections(body: str) -> list[tuple[str, list[str]]]:
    headings = list(re.finditer(r"^##\s+(.+?)\s*$", body, re.M))
    sections: list[tuple[str, list[str]]] = []
    for index, match in enumerate(headings):
        title = match.group(1).strip()
        if title in {SUMMARY_HEADING, SECONDARY_HEADING}:
            continue
        start = match.end()
        end = headings[index + 1].start() if index + 1 < len(headings) else len(body)
        content = body[start:end]
        rules = [
            item.group(1).strip()
            for item in re.finditer(r"^\s*(?:[-*+]\s+(?:\[[ xX]\]\s+)?|\d+[.)]\s+)(.+?)\s*$", content, re.M)
            if item.group(1).strip() and not item.group(1).strip().startswith("---")
        ]
        sections.append((title, rules))
    return sections


def validate_markdown_spec(path: Path) -> tuple[ValidationReport, str | None]:
    report = ValidationReport()
    parsed = parse_markdown_spec(path)
    if parsed is None:
        report.errors.append(f"{path}: cannot read Markdown spec.")
        return report, None

    frontmatter = parsed.frontmatter
    if not frontmatter:
        report.errors.append(f"{path}: missing frontmatter block.")
    if frontmatter.get("specSchemaVersion") != SPEC_SCHEMA_VERSION:
        report.warnings.append(f"{path}: specSchemaVersion should be {SPEC_SCHEMA_VERSION}.")
    if frontmatter.get("storageFormat") != "markdown":
        report.errors.append(f'{path}: storageFormat must be "markdown".')
    if parsed.page_key != path.stem:
        report.errors.append(f"{path}: pageKey '{parsed.page_key}' must match filename '{path.stem}'.")

    for key in ("pageName", "pageType", "pageShape", "sourceType", "specId", "batchId"):
        value = frontmatter.get(key)
        if not isinstance(value, str) or not value.strip():
            report.errors.append(f"{path}: frontmatter.{key} must be a non-empty string.")

    version = frontmatter.get("version")
    if not isinstance(version, int) or version < 1:
        report.errors.append(f"{path}: frontmatter.version must be a positive integer.")
    if not isinstance(frontmatter.get("overwriteProtected"), bool):
        report.errors.append(f"{path}: frontmatter.overwriteProtected must be a boolean.")

    if not parsed.summary:
        report.errors.append(f"{path}: ## {SUMMARY_HEADING} must contain non-empty text.")
    if not parsed.sections:
        report.errors.append(f"{path}: no rule sections found beyond summary/secondary surfaces.")
    for title, rules in parsed.sections:
        if not title.strip():
            report.errors.append(f"{path}: a rule section has an empty title.")
        if not rules:
            report.errors.append(f"{path}: section '{title}' has no bullet rules.")

    if "待补充" in parsed.body:
        report.warnings.append(f"{path}: contains placeholder text '待补充'.")
    if f"### {FIELD_TABLE_HEADING}" in parsed.body and "| 字段 | 形态 | 必填 | 说明 |" not in parsed.body:
        report.warnings.append(f"{path}: field table heading exists but expected table header was not found.")
    report.extend(validate_markdown_images(parsed))

    return report, parsed.page_key


def validate_json_spec(path: Path) -> tuple[ValidationReport, str | None]:
    report = ValidationReport()
    try:
        payload = json.loads(path.read_text(encoding="utf-8"))
    except (json.JSONDecodeError, OSError) as error:
        report.errors.append(f"{path}: invalid JSON: {error}")
        return report, None
    if not isinstance(payload, dict):
        report.errors.append(f"{path}: top-level JSON must be an object.")
        return report, None

    page_key = payload.get("pageKey")
    if not isinstance(page_key, str) or not page_key:
        page_key = path.stem
        report.warnings.append(f"{path}: missing pageKey; using filename for compatibility.")
    if page_key != path.stem:
        report.errors.append(f"{path}: pageKey '{page_key}' must match filename '{path.stem}'.")

    summary = payload.get("summary")
    if not isinstance(summary, str) or not summary.strip():
        report.errors.append(f"{path}: summary must be a non-empty string.")
    sections = payload.get("sections")
    if not isinstance(sections, list) or not sections:
        report.errors.append(f"{path}: sections must be a non-empty array.")
    else:
        for index, section in enumerate(sections):
            if not isinstance(section, dict):
                report.errors.append(f"{path}: sections[{index}] must be an object.")
                continue
            title = section.get("title")
            if not isinstance(title, str) or not title.strip():
                report.errors.append(f"{path}: sections[{index}].title must be non-empty.")
            rules = section.get("rules")
            if not isinstance(rules, list) or not any(isinstance(rule, str) and rule.strip() for rule in rules):
                report.errors.append(f"{path}: sections[{index}].rules must contain at least one non-empty rule.")

    report.warnings.append(f"{path}: legacy JSON spec detected; migrate to current/{path.stem}.md when possible.")
    return report, page_key


def load_registry(spec_root: Path) -> dict | None:
    registry_path = spec_root / "registry.json"
    try:
        payload = json.loads(registry_path.read_text(encoding="utf-8"))
    except (json.JSONDecodeError, OSError):
        return None
    return payload if isinstance(payload, dict) else None


def validate_registry(spec_root: Path, current_page_keys: set[str]) -> ValidationReport:
    report = ValidationReport()
    registry_path = spec_root / "registry.json"
    registry = load_registry(spec_root)
    if registry is None:
        report.errors.append(f"{registry_path}: missing or invalid registry.json.")
        return report

    pages = registry.get("pages")
    if not isinstance(pages, list):
        report.errors.append(f"{registry_path}: pages must be an array.")
        return report

    registry_keys = {
        entry.get("pageKey")
        for entry in pages
        if isinstance(entry, dict) and isinstance(entry.get("pageKey"), str)
    }
    missing = sorted(current_page_keys - registry_keys)
    extra = sorted(registry_keys - current_page_keys)
    if missing:
        report.errors.append(f"{registry_path}: missing current specs in registry: {', '.join(missing)}.")
    if extra:
        report.warnings.append(f"{registry_path}: registry has no matching current spec for: {', '.join(extra)}.")
    if registry.get("storageFormat") not in {None, "markdown"}:
        report.warnings.append(f'{registry_path}: storageFormat should be "markdown".')
    return report


def validate_history_dirs(spec_root: Path, current_page_keys: set[str]) -> ValidationReport:
    report = ValidationReport()
    history_root = spec_root / "history"
    if not history_root.is_dir():
        report.warnings.append(f"{history_root}: history directory is missing.")
        return report
    for page_key in sorted(current_page_keys):
        if not (history_root / page_key).is_dir():
            report.warnings.append(f"{history_root / page_key}: history directory is missing for current spec.")
    return report


def validate_spec_root(spec_root: Path, page_keys: set[str]) -> tuple[ValidationReport, set[str]]:
    report = ValidationReport()
    current_dir = spec_root / "current"
    current_keys: set[str] = set()
    md_files = sorted(current_dir.glob("*.md"))
    json_files = sorted(current_dir.glob("*.json"))
    files = md_files + json_files
    if not files:
        report.errors.append(f"{current_dir}: no current spec files found.")
        return report, current_keys

    md_keys = {path.stem for path in md_files}
    for path in files:
        if page_keys and path.stem not in page_keys:
            continue
        if path.suffix == ".md":
            item_report, page_key = validate_markdown_spec(path)
        else:
            item_report, page_key = validate_json_spec(path)
            if path.stem in md_keys:
                item_report.warnings.append(f"{path}: legacy JSON exists beside Markdown; remove after migration if no longer needed.")
        report.extend(item_report)
        if page_key:
            current_keys.add(page_key)

    if page_keys:
        missing_requested = sorted(page_keys - current_keys)
        if missing_requested:
            report.errors.append(f"{current_dir}: requested page keys not found: {', '.join(missing_requested)}.")

    report.extend(validate_registry(spec_root, current_keys))
    report.extend(validate_history_dirs(spec_root, current_keys))
    return report, current_keys


def viewer_mode_requires_dual_consistency(root: Path) -> bool:
    for spec_root in find_spec_roots(root):
        config = read_json(spec_root / "viewer-config.json") or {}
        if config.get("viewerMode") in {None, "dual-view"}:
            return True
    return False


def scan_code_risks(root: Path) -> ValidationReport:
    report = ValidationReport()
    saw_runtime_marker = False
    inline_hits: list[str] = []
    derivation_hits: list[str] = []
    local_storage_hits: list[str] = []
    monolithic_editor_hits: list[str] = []
    missing_escape_attr_hits: list[str] = []
    stale_html_server_hits: list[str] = []
    missing_mermaid_isolation_hits: list[str] = []

    for path in iter_code_files(root):
        text = read_text(path)
        if text is None:
            continue
        rel = str(path.relative_to(root))
        if any(marker in text for marker in RUNTIME_SOURCE_MARKERS):
            saw_runtime_marker = True
        has_current_html_viewer = any(marker in text for marker in CURRENT_HTML_VIEWER_MARKERS)
        is_generated_react_viewer = any(part in rel for part in GENERATED_VIEWER_PATH_PARTS)
        has_legacy_inline_marker = any(
            pattern.search(text)
            for pattern in INLINE_SPEC_PATTERNS
            if not (
                pattern.pattern == r"\bproto-spec-doc\b"
                and (has_current_html_viewer or is_generated_react_viewer)
            )
        )
        if has_legacy_inline_marker:
            inline_hits.append(rel)
        if any(pattern.search(text) for pattern in PAGE_KEY_DERIVATION_PATTERNS):
            derivation_hits.append(rel)
        if LOCAL_STORAGE_PATTERN.search(text):
            local_storage_hits.append(rel)
        if MONOLITHIC_RULE_EDITOR_PATTERN.search(text):
            monolithic_editor_hits.append(rel)
        if ("escapeAttr(" in text or "data-mermaid=" in text) and "function escapeAttr" not in text:
            missing_escape_attr_hits.append(rel)
        if path.name == "proto-spec-server.mjs" and "/__prototype-specs/specs/" in text and "handleSpecRead" not in text:
            stale_html_server_hits.append(rel)
        if ".proto-spec-mermaid svg" in text and ("foreignObject" not in text or "line-height:1.2" not in text):
            missing_mermaid_isolation_hits.append(rel)

    if not saw_runtime_marker:
        report.warnings.append("No runtime marker found for reading current specs; this is fine for Markdown-only delivery, but not for integrated preview.")
    if inline_hits:
        message = "Legacy inline spec markers remain in: " + ", ".join(sorted(set(inline_hits))[:12])
        if viewer_mode_requires_dual_consistency(root):
            report.errors.append(message + ". dual-view projects must remove old inline viewers before integration.")
        else:
            report.warnings.append(message)
    if derivation_hits:
        report.warnings.append("Potential unstable pageKey derivation found in: " + ", ".join(sorted(set(derivation_hits))[:12]))
    if local_storage_hits:
        report.warnings.append("localStorage usage found; ensure it is not the only persistence layer: " + ", ".join(sorted(set(local_storage_hits))[:12]))
    if monolithic_editor_hits:
        report.warnings.append("Rules may be edited via join/split textareas instead of structured rule editing: " + ", ".join(sorted(set(monolithic_editor_hits))[:12]))
    if missing_escape_attr_hits:
        report.errors.append("Viewer renderer references HTML attributes but is missing escapeAttr(): " + ", ".join(sorted(set(missing_escape_attr_hits))[:12]))
    if stale_html_server_hits:
        report.warnings.append("HTML proto-spec server lacks GET/read fallback for Markdown specs: " + ", ".join(sorted(set(stale_html_server_hits))[:12]))
    if missing_mermaid_isolation_hits:
        report.warnings.append("Viewer CSS may let document typography clip multi-line Mermaid labels; add Mermaid foreignObject style isolation: " + ", ".join(sorted(set(missing_mermaid_isolation_hits))[:12]))
    return report


def main() -> int:
    args = parse_args()
    root = Path(args.root).resolve()
    page_keys = {key.strip() for key in args.page_key if key.strip()}
    report = ValidationReport()
    spec_roots = find_spec_roots(root)

    if not spec_roots:
        report.errors.append(f"{root}: no supported spec root found. Expected one of: {', '.join(SPEC_ROOT_CANDIDATES)}.")
    else:
        for spec_root in spec_roots:
            spec_report, current_keys = validate_spec_root(spec_root, page_keys)
            report.extend(spec_report)
            report.infos.append(f"{spec_root}: validated {len(current_keys)} current spec(s).")

    report.extend(scan_code_risks(root))

    if args.json_output:
        print(json.dumps(report.as_dict(), ensure_ascii=False, indent=2))
    else:
        for label, items in (("ERROR", report.errors), ("WARN", report.warnings), ("INFO", report.infos)):
            for item in items:
                print(f"{label}: {item}")
        if not report.errors and (not args.strict or not report.warnings):
            print("Validation passed.")

    if report.errors or (args.strict and report.warnings):
        return 1
    return 0


if __name__ == "__main__":
    sys.exit(main())
