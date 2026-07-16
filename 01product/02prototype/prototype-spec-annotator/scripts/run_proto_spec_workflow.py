#!/usr/bin/env python3
"""Run the Prototype Spec Annotator workflow.

Analyze an existing prototype project, create Markdown-first page specs, keep
registry/history files, optionally wire a lightweight viewer, and validate.
The runner is intentionally self-contained and uses only the Python standard
library.
"""

from __future__ import annotations

import argparse
import json
import os
import re
import shutil
import sys
import urllib.error
import urllib.request
from dataclasses import asdict, dataclass, field
from datetime import datetime
from pathlib import Path
from typing import Iterable


SPEC_SCHEMA_VERSION = 2
SUMMARY_HEADING = "页面摘要"
SECONDARY_SURFACES_HEADING = "二级承载面"
FIELD_TABLE_HEADING = "字段说明"

IGNORED_DIRS = {
    ".git",
    ".edgeone",
    ".idea",
    ".next",
    ".nuxt",
    ".turbo",
    ".vite",
    "build",
    "coverage",
    "dist",
    "dist-electron",
    "history",
    "node_modules",
    "out",
    "prototype-specs",
    "release",
    "src/page-specs",
}
PAGE_DIR_MARKERS = ("src/pages", "src/views", "pages", "views", "src/routes")
PAGE_KEY_DIR_MARKERS = (
    *PAGE_DIR_MARKERS,
    "src/components",
    "components",
    "src/screens",
    "screens",
    "src/features",
    "features",
)
REACT_APP_ENTRY_FILES = ("src/App.tsx", "src/App.jsx", "App.tsx", "App.jsx")
VUE_APP_ENTRY_FILES = ("src/App.vue", "App.vue")
VITE_CONFIG_FILES = ("vite.config.ts", "vite.config.js", "vite.config.mts", "vite.config.mjs")
LOCAL_SOURCE_EXTENSIONS = (".tsx", ".jsx", ".ts", ".js", ".vue")
TEXT_EXTENSIONS = {".html", ".htm", ".vue", ".jsx", ".tsx", ".js", ".ts", ".css", ".scss"}

NON_PAGE_COMPONENT_NAME_PATTERN = re.compile(
    r"(Shell|Layout|Provider|Router|Route|Outlet|Header|Footer|Sidebar|Sidecar|Navigation|Menu|Toolbar|Topbar|Navbar|MetricCard|Card)$",
    re.I,
)
NON_PAGE_SOURCE_PATTERN = re.compile(
    r"(^|/)(main|index|vite-env|types|utils|helpers|constants|config|store|hooks)\.(tsx|jsx|ts|js|d\.ts)$",
    re.I,
)
FIXED_SHELL_PATTERN = re.compile(r"h-screen|min-h-0|overflow-hidden|overflow-y-auto|fixed sidebar|layout-shell|proto-page-shell|drawer|sheet", re.I)
MOBILE_PATTERN = re.compile(r"mobile|iphone|android|tabbar|bottom-nav|safe-area", re.I)
BIG_SCREEN_PATTERN = re.compile(r"big-screen|dashboard|chart|graph|monitor|screen|datav|地图|看板|图表|监控|大屏|mapbox|leaflet|amap", re.I)
AIGC_PATTERN = re.compile(r"prompt|chat|assistant|generate|workflow|conversation|生成中|生成结果", re.I)
LIST_PATTERN = re.compile(r"table|thead|tbody|pagination|filter|search|columns|list|查询|筛选", re.I)
FORM_PATTERN = re.compile(r"form|input|textarea|select|checkbox|radio|submit|保存|提交", re.I)
TOOL_PATTERN = re.compile(r"upload|generate|process|result|run|execute|prompt|chat", re.I)


@dataclass
class ProjectPage:
    pageKey: str
    pageName: str
    relativePath: str
    routeHint: str
    extension: str
    pageType: str
    pageShape: str
    layoutMode: str
    detectedElements: list[str] = field(default_factory=list)


@dataclass
class ProjectAnalysis:
    rootPath: str
    framework: str
    specRoot: str
    viewerConfigPath: str
    pages: list[ProjectPage]
    commands: dict[str, str | None]
    editableSpecRecommended: bool
    defaultViewerMode: str
    summary: list[str]


@dataclass
class WorkflowReport:
    operation: str
    dryRun: bool
    analysis: dict | None = None
    aiReviewRequired: bool = False
    aiReviewPages: list[str] = field(default_factory=list)
    localRuleDraftPages: list[str] = field(default_factory=list)
    changedFiles: list[str] = field(default_factory=list)
    skipped: list[str] = field(default_factory=list)
    warnings: list[str] = field(default_factory=list)
    errors: list[str] = field(default_factory=list)


def parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser(description="Analyze a prototype project and maintain Markdown page specs.")
    parser.add_argument("--root", required=True, help="Target prototype project root.")
    parser.add_argument(
        "--operation",
        choices=("create", "update", "delete", "display", "integrate", "audit"),
        default="create",
        help="Workflow operation. create/update generate Markdown specs; integrate only wires the viewer.",
    )
    parser.add_argument("--scope", choices=("all", "selected"), default="all")
    parser.add_argument("--page-key", action="append", default=[], help="Restrict to a stable pageKey. Repeatable.")
    parser.add_argument("--file", action="append", default=[], help="Restrict to a source file relative to root. Repeatable.")
    parser.add_argument("--force", action="store_true", help="Overwrite existing specs after history snapshot.")
    parser.add_argument("--dry-run", action="store_true", help="Print planned changes without writing files.")
    parser.add_argument("--json", dest="json_output", action="store_true", help="Emit a JSON report.")
    parser.add_argument("--integrate", action="store_true", help="Also wire a runtime viewer after create/update.")
    parser.add_argument("--visibility-mode", choices=("default-expanded", "default-hidden", "manual-toggle"), default="manual-toggle")
    parser.add_argument("--viewer-mode", choices=("dual-view", "inline-bottom"), default="dual-view")
    parser.add_argument("--html-save-mode", choices=("file-service", "browser-cache", "manual-json"), default="file-service")
    parser.add_argument("--model-base-url", default=os.environ.get("PROTO_SPEC_MODEL_BASE_URL", ""))
    parser.add_argument("--model-api-key", default=os.environ.get("PROTO_SPEC_MODEL_API_KEY", ""))
    parser.add_argument("--model", default=os.environ.get("PROTO_SPEC_MODEL", ""))
    parser.add_argument("--draft-only", action="store_true", help="Allow stopping after local-rule draft generation when no runner model is configured. Use only when the user explicitly asks for draft output.")
    return parser.parse_args()


def now_iso() -> str:
    return datetime.now().astimezone().isoformat(timespec="seconds")


def batch_id() -> str:
    return "spec-batch-" + datetime.now().astimezone().strftime("%Y%m%d-%H%M%S")


def stamp() -> str:
    return datetime.now().astimezone().isoformat(timespec="seconds").replace(":", "-")


def normalize_path(value: str) -> str:
    return value.replace("\\", "/").strip("/")


def read_text(path: Path) -> str | None:
    try:
        return path.read_text(encoding="utf-8")
    except (OSError, UnicodeDecodeError):
        return None


def write_text(path: Path, content: str, dry_run: bool, report: WorkflowReport) -> None:
    if dry_run:
        report.changedFiles.append(str(path))
        return
    path.parent.mkdir(parents=True, exist_ok=True)
    previous = read_text(path)
    if previous == content:
        return
    path.write_text(content, encoding="utf-8")
    report.changedFiles.append(str(path))


def ensure_dir(path: Path, dry_run: bool, report: WorkflowReport) -> None:
    if dry_run:
        report.changedFiles.append(str(path))
        return
    if path.is_dir():
        return
    path.mkdir(parents=True, exist_ok=True)
    report.changedFiles.append(str(path))


def read_json(path: Path) -> dict | None:
    try:
        payload = json.loads(path.read_text(encoding="utf-8"))
    except (OSError, json.JSONDecodeError):
        return None
    return payload if isinstance(payload, dict) else None


def write_json(path: Path, payload: dict, dry_run: bool, report: WorkflowReport) -> None:
    write_text(path, json.dumps(payload, ensure_ascii=False, indent=2) + "\n", dry_run, report)


def list_project_files(root: Path) -> list[str]:
    files: list[str] = []
    for path in root.rglob("*"):
        try:
            relative = path.relative_to(root)
        except ValueError:
            continue
        if any(part in IGNORED_DIRS for part in relative.parts):
            continue
        if path.is_file():
            files.append(normalize_path(str(relative)))
    return sorted(files)


def read_package_json(root: Path) -> dict | None:
    return read_json(root / "package.json")


def detect_framework(package_json: dict | None, files: list[str]) -> str:
    deps = {}
    if package_json:
        deps.update(package_json.get("dependencies") or {})
        deps.update(package_json.get("devDependencies") or {})
    if "react" in deps or any(path.endswith((".tsx", ".jsx")) for path in files):
        return "react"
    if "vue" in deps or any(path.endswith(".vue") for path in files):
        return "vue"
    if any(path.endswith((".html", ".htm")) for path in files):
        return "html"
    return "unknown"


def detect_package_manager(root: Path) -> str:
    if (root / "pnpm-lock.yaml").exists():
        return "pnpm"
    if (root / "yarn.lock").exists():
        return "yarn"
    if (root / "bun.lockb").exists() or (root / "bun.lock").exists():
        return "bun"
    return "npm"


def package_manager_command(package_manager: str, script_name: str) -> str:
    if package_manager == "yarn":
        return f"yarn {script_name}"
    if package_manager == "pnpm":
        return f"pnpm {script_name}"
    if package_manager == "bun":
        return f"bun run {script_name}"
    return f"npm run {script_name}"


def detect_commands(root: Path, package_json: dict | None) -> dict[str, str | None]:
    manager = detect_package_manager(root)
    scripts = package_json.get("scripts") if package_json else {}
    scripts = scripts if isinstance(scripts, dict) else {}
    dev_name = "dev" if "dev" in scripts else "start" if "start" in scripts else "serve" if "serve" in scripts else ""
    return {
        "packageManager": manager,
        "installCommand": "yarn" if manager == "yarn" else f"{manager} install",
        "devCommand": package_manager_command(manager, dev_name) if dev_name else None,
        "buildCommand": package_manager_command(manager, "build") if "build" in scripts else None,
    }


def detect_spec_root(root: Path, framework: str) -> Path:
    return root / "prototype-specs" if framework == "html" else root / "src" / "page-specs"


def analyze_project(root: Path, selected_files: list[str]) -> ProjectAnalysis:
    package_json = read_package_json(root)
    files = list_project_files(root)
    framework = detect_framework(package_json, files)
    page_key_hints = read_existing_page_key_hints(root, framework)
    pages = discover_pages(root, framework, files, selected_files, page_key_hints)
    commands = detect_commands(root, package_json)
    spec_root = detect_spec_root(root, framework)
    summary = [
        f"识别框架：{framework if framework != 'unknown' else 'unknown/html-compatible'}",
        f"候选页面数：{len(pages)}",
        f"说明根目录：{spec_root}",
        commands["devCommand"] and f"检测到预览命令：{commands['devCommand']}" or "未检测到可自动启动的预览命令",
    ]
    return ProjectAnalysis(
        rootPath=str(root),
        framework=framework,
        specRoot=str(spec_root),
        viewerConfigPath=str(spec_root / "viewer-config.json"),
        pages=pages,
        commands=commands,
        editableSpecRecommended=len(pages) > 1,
        defaultViewerMode="dual-view",
        summary=summary,
    )


def read_existing_page_key_hints(root: Path, framework: str) -> dict[str, str]:
    spec_root = detect_spec_root(root, framework)
    hints: dict[str, str] = {}
    registry = read_json(spec_root / "registry.json") or {}
    pages = registry.get("pages") if isinstance(registry, dict) else []
    if isinstance(pages, list):
        for item in pages:
            if not isinstance(item, dict):
                continue
            source_file = normalize_path(str(item.get("sourceFile") or ""))
            page_key = str(item.get("pageKey") or "").strip()
            if source_file and page_key:
                hints[source_file] = page_key
    current_dir = spec_root / "current"
    if current_dir.is_dir():
        for spec_file in sorted(current_dir.glob("*.md")):
            raw = read_text(spec_file) or ""
            frontmatter, _body = parse_frontmatter(raw)
            source_file = normalize_path(str(frontmatter.get("sourceFile") or frontmatter.get("relativePath") or ""))
            page_key = str(frontmatter.get("pageKey") or spec_file.stem).strip()
            if source_file and page_key:
                hints.setdefault(source_file, page_key)
    return hints


def discover_pages(root: Path, framework: str, files: list[str], selected_files: list[str], page_key_hints: dict[str, str] | None = None) -> list[ProjectPage]:
    if selected_files:
        candidates = [normalize_path(path) for path in selected_files]
    else:
        candidates = filter_page_candidates(root, framework, files)
    if not candidates and framework in {"html", "unknown"}:
        candidates = [path for path in files if path.endswith((".html", ".htm"))]

    file_set = set(files)
    if framework == "react":
        route_hints = infer_react_route_hints(root, file_set)
    elif framework == "vue":
        route_hints = infer_vue_route_hints(root, file_set)
    else:
        route_hints = {}
    pages: list[ProjectPage] = []
    seen: set[str] = set()
    for relative_path in sorted(candidates):
        if relative_path not in file_set:
            continue
        primary = read_text(root / relative_path)
        if not primary:
            continue
        source = read_page_source_context(root, relative_path, primary, file_set)
        page_key = (page_key_hints or {}).get(relative_path) or create_stable_page_key(relative_path)
        if page_key in seen:
            continue
        seen.add(page_key)
        page_shape = detect_page_shape(relative_path, source)
        page_type = detect_page_type(source, page_shape)
        pages.append(
            ProjectPage(
                pageKey=page_key,
                pageName=detect_page_name(relative_path, primary, source),
                relativePath=relative_path,
                routeHint=relative_path if framework == "html" else route_hints.get(relative_path, infer_route_hint(relative_path)),
                extension=Path(relative_path).suffix,
                pageType=page_type,
                pageShape=page_shape,
                layoutMode="fixed-shell" if FIXED_SHELL_PATTERN.search(source) else "document-flow",
                detectedElements=infer_detected_elements(source),
            )
        )
    return pages


def filter_page_candidates(root: Path, framework: str, files: list[str]) -> list[str]:
    expected = {
        "react": (".tsx", ".jsx"),
        "vue": (".vue",),
        "html": (".html", ".htm"),
        "unknown": (".html", ".htm", ".vue", ".tsx", ".jsx"),
    }.get(framework, (".html", ".htm"))
    page_dir_matches = [
        path
        for path in files
        if any(path.startswith(marker + "/") for marker in PAGE_DIR_MARKERS) and path.endswith(expected)
    ]
    if page_dir_matches:
        return page_dir_matches
    if framework == "react":
        app_candidates = discover_react_app_screen_candidates(root, files)
        if app_candidates:
            return app_candidates
        component_pages = discover_likely_component_pages(root, files, expected)
        if component_pages:
            return component_pages
    return [
        path
        for path in files
        if path.endswith(expected)
        and "/shared/" not in path.lower()
        and "/lib/" not in path.lower()
        and "/utils/" not in path.lower()
        and not NON_PAGE_SOURCE_PATTERN.search(path)
    ]


def discover_react_app_screen_candidates(root: Path, files: list[str]) -> list[str]:
    file_set = set(files)
    discovered: set[str] = set()
    for app_file in REACT_APP_ENTRY_FILES:
        if app_file not in file_set:
            continue
        source = read_text(root / app_file) or ""
        imports = parse_local_component_imports(source)
        used = set(re.findall(r"<([A-Z][A-Za-z0-9_]*)\b", source))
        for component_name, import_source in imports.items():
            if component_name not in used or NON_PAGE_COMPONENT_NAME_PATTERN.search(component_name):
                continue
            resolved = resolve_imported_source_file(app_file, import_source, file_set)
            if not resolved:
                continue
            component_source = read_text(root / resolved) or ""
            if looks_like_page_component(component_name, resolved, component_source):
                discovered.add(resolved)
    return sorted(discovered)


def discover_likely_component_pages(root: Path, files: list[str], expected_extensions: tuple[str, ...]) -> list[str]:
    pages: list[str] = []
    for relative_path in files:
        if not relative_path.startswith("src/components/") or not relative_path.endswith(expected_extensions):
            continue
        component_name = Path(relative_path).stem
        if NON_PAGE_COMPONENT_NAME_PATTERN.search(component_name) or NON_PAGE_SOURCE_PATTERN.search(relative_path):
            continue
        source = read_text(root / relative_path) or ""
        if looks_like_page_component(component_name, relative_path, source):
            pages.append(relative_path)
    return sorted(pages)


def parse_local_component_imports(source: str) -> dict[str, str]:
    imports: dict[str, str] = {}
    pattern = re.compile(
        r"import\s+(?:type\s+)?(?:(?P<default>[A-Z][A-Za-z0-9_]*)\s*,?\s*)?(?:\{\s*(?P<named>[^}]+)\s*\})?\s+from\s+[\"'](?P<source>[^\"']+)[\"']"
    )
    for match in pattern.finditer(source):
        import_source = (match.group("source") or "").strip()
        if not (import_source.startswith(".") or import_source.startswith("@/")):
            continue
        default_name = match.group("default")
        if default_name:
            imports[default_name] = import_source
        named = match.group("named") or ""
        for raw_part in named.split(","):
            part = raw_part.strip()
            alias = re.match(r"(?P<name>[A-Z][A-Za-z0-9_]*)(?:\s+as\s+(?P<alias>[A-Z][A-Za-z0-9_]*))?$", part)
            if alias:
                imports[alias.group("alias") or alias.group("name")] = import_source
    return imports


def resolve_imported_source_file(importer_file: str, import_source: str, file_set: set[str]) -> str | None:
    importer_dir = str(Path(importer_file).parent).replace("\\", "/")
    if importer_dir == ".":
        importer_dir = ""
    if import_source.startswith("@/"):
        base = "src/" + import_source[2:]
    elif import_source.startswith("."):
        base = normalize_path(str(Path(importer_dir, import_source)))
    else:
        return None
    candidates = []
    if Path(base).suffix in LOCAL_SOURCE_EXTENSIONS:
        candidates.append(base)
    candidates.extend(base + ext for ext in LOCAL_SOURCE_EXTENSIONS)
    candidates.extend(base + "/index" + ext for ext in LOCAL_SOURCE_EXTENSIONS)
    return next((candidate for candidate in candidates if candidate in file_set), None)


def looks_like_page_component(component_name: str, relative_path: str, source: str) -> bool:
    if NON_PAGE_COMPONENT_NAME_PATTERN.search(component_name) or NON_PAGE_SOURCE_PATTERN.search(relative_path):
        return False
    visible_texts = extract_visible_texts(source)
    detected = infer_detected_elements(source)
    has_page_structure = re.search(
        r"<(main|section|article|header|form|table)\b|className=[\"'`][^\"'`]*(h-screen|min-h-screen|grid|flex|space-y|overflow-y-auto|page|screen|dashboard|bento)",
        source,
        re.I,
    )
    has_stateful_surface = re.search(r"useState|tabs?|activeTab|modal|drawer|dialog|filter|search|chart|knowledge|todo|agent", source, re.I)
    return len(source) > 260 and len(visible_texts) >= 2 and bool(has_page_structure or has_stateful_surface or len(detected) >= 2)


def infer_react_route_hints(root: Path, file_set: set[str]) -> dict[str, str]:
    route_hints: dict[str, str] = {}
    for app_file in REACT_APP_ENTRY_FILES:
        if app_file not in file_set:
            continue
        source = read_text(root / app_file) or ""
        component_imports = {
            name: resolved
            for name, import_source in parse_local_component_imports(source).items()
            if (resolved := resolve_imported_source_file(app_file, import_source, file_set))
        }
        route_stack: list[str] = []
        for tag in collect_route_tags(source):
            if tag["closing"]:
                if route_stack:
                    route_stack.pop()
                continue
            parent = route_stack[-1] if route_stack else ""
            route_path = extract_route_path(tag["source"])
            is_index = "index" in tag["source"]
            full_path = normalize_route_pattern(parent or "/") if is_index else combine_route_paths(parent, route_path) if route_path else parent
            component_name = extract_route_element_component(tag["source"])
            component_file = component_imports.get(component_name or "")
            if component_file and full_path and full_path not in {"*", "/*"}:
                route_hints.setdefault(component_file, normalize_route_pattern(full_path))
            if not tag["selfClosing"]:
                route_stack.append(full_path)
    return route_hints


def infer_vue_route_hints(root: Path, file_set: set[str]) -> dict[str, str]:
    route_hints: dict[str, str] = {}
    router_files = [
        path
        for path in file_set
        if path.startswith("src/router/") and path.endswith((".js", ".ts"))
    ]
    for router_file in sorted(router_files):
        source = read_text(root / router_file) or ""
        route_blocks = split_vue_route_blocks(source)
        search_units = route_blocks if route_blocks else [source]
        for block in search_units:
            path_match = re.search(r"path\s*:\s*[\"'](?P<path>[^\"']+)[\"']", block)
            import_match = re.search(
                r"component\s*:\s*(?:\(\)\s*=>\s*)?import\(\s*[\"'](?P<import>[^\"']+\.vue)[\"']\s*\)",
                block,
            )
            if not path_match or not import_match:
                continue
            resolved = resolve_imported_source_file(router_file, import_match.group("import"), file_set)
            route_path = path_match.group("path")
            if resolved and route_path and route_path not in {"*", "/:pathMatch(.*)*"}:
                route_hints.setdefault(resolved, normalize_route_pattern(route_path))
    return route_hints


def split_vue_route_blocks(source: str) -> list[str]:
    blocks: list[str] = []
    current: list[str] = []
    depth = 0
    for line in source.splitlines(keepends=True):
        stripped = line.strip()
        if not current and stripped == "{":
            current.append(line)
            depth = 1
            continue
        if not current:
            continue
        current.append(line)
        depth += line.count("{") - line.count("}")
        if depth <= 0:
            blocks.append("".join(current))
            current = []
            depth = 0
    return blocks


def collect_route_tags(source: str) -> list[dict[str, str | bool]]:
    tags: list[dict[str, str | bool]] = []
    for line in source.splitlines():
        stripped = line.strip()
        if "</Route>" in stripped:
            tags.append({"source": "</Route>", "closing": True, "selfClosing": False})
            continue
        if "<Route" not in stripped:
            continue
        start = stripped.find("<Route")
        tag = stripped[start:]
        tags.append({"source": tag, "closing": False, "selfClosing": tag.rstrip().endswith("/>")})
    return tags


def extract_route_path(route_tag: str) -> str | None:
    match = re.search(r"\bpath\s*=\s*(?:\"([^\"]+)\"|'([^']+)')", route_tag)
    return match.group(1) or match.group(2) if match else None


def extract_route_element_component(route_tag: str) -> str | None:
    match = re.search(r"\belement\s*=\s*\{\s*<\s*([A-Z][A-Za-z0-9_]*)\b", route_tag)
    return match.group(1) if match else None


def combine_route_paths(parent_path: str, child_path: str) -> str:
    if child_path == "*":
        return normalize_route_pattern(parent_path) + "/*" if parent_path else "*"
    if child_path.startswith("/"):
        return normalize_route_pattern(child_path)
    parent = normalize_route_pattern(parent_path or "/")
    return normalize_route_pattern(("" if parent == "/" else parent) + "/" + child_path)


def normalize_route_pattern(value: str) -> str:
    value = value.strip()
    if not value or value == "/":
        return "/"
    if value == "*":
        return "*"
    return "/" + value.strip("/")


def humanize_name(raw: str) -> str:
    value = re.sub(r"([a-z0-9])([A-Z])", r"\1 \2", raw)
    value = value.replace("-", " ").replace("_", " ")
    return " ".join(part[:1].upper() + part[1:] for part in value.split()) or raw


def detect_page_name(relative_path: str, primary: str, source: str) -> str:
    init_layout_match = re.search(r"initLayout\(\s*[\"'][^\"']+[\"']\s*,\s*[\"']([^\"']{2,40})[\"']\s*\)", source)
    if init_layout_match:
        return clean_page_name(init_layout_match.group(1))
    title_match = re.search(r"<title[^>]*>([^<]{2,80})</title>", primary, re.I)
    if title_match:
        return clean_page_name(title_match.group(1))
    heading_match = re.search(r"<h1[^>]*>([^<]{2,60})</h1>", primary, re.I)
    if heading_match:
        return clean_page_name(heading_match.group(1))
    return humanize_name(Path(relative_path).stem)


def clean_page_name(value: str) -> str:
    value = re.sub(r"\s*[-|｜]\s*MDM Pro\s*$", "", value.strip(), flags=re.I)
    return value or "页面"


def create_stable_page_key(relative_path: str) -> str:
    normalized = normalize_path(relative_path)
    marker = next((entry for entry in PAGE_KEY_DIR_MARKERS if normalized.startswith(entry + "/")), "")
    narrowed = normalized[len(marker) + 1 :] if marker else normalized
    parsed = Path(narrowed)
    dir_part = "" if str(parsed.parent) == "." else normalize_path(str(parsed.parent))
    stem = "" if parsed.stem == "index" else parsed.stem
    key_parts = [*dir_part.split("/"), stem] if dir_part else [stem]
    joined = "-".join(part for part in key_parts if part)
    key = re.sub(r"([a-z0-9])([A-Z])", r"\1-\2", joined)
    key = re.sub(r"[^a-zA-Z0-9-]+", "-", key)
    key = re.sub(r"-{2,}", "-", key).strip("-").lower()
    if key:
        return key
    import hashlib

    return "page-" + hashlib.sha1(relative_path.encode("utf-8")).hexdigest()[:8]


def infer_route_hint(relative_path: str) -> str:
    normalized = normalize_path(relative_path)
    marker = next((entry for entry in PAGE_KEY_DIR_MARKERS if normalized.startswith(entry + "/")), "")
    narrowed = normalized[len(marker) + 1 :] if marker else normalized
    without_ext = re.sub(r"\.[^.]+$", "", narrowed)
    parts = [
        re.sub(r"_+", "-", re.sub(r"([a-z0-9])([A-Z])", r"\1-\2", part)).lower()
        for part in without_ext.split("/")
        if part and part != "index"
    ]
    return "/" + "/".join(parts) if parts else "/"


def detect_page_shape(relative_path: str, content: str) -> str:
    sample = relative_path + "\n" + content
    if MOBILE_PATTERN.search(sample):
        return "mobile"
    if BIG_SCREEN_PATTERN.search(sample):
        return "big-screen"
    if AIGC_PATTERN.search(sample):
        return "aigc"
    if FIXED_SHELL_PATTERN.search(sample):
        return "workspace"
    return "desktop"


def detect_page_type(content: str, page_shape: str) -> str:
    if page_shape == "aigc":
        return "tool"
    if FORM_PATTERN.search(content) and not LIST_PATTERN.search(content):
        return "form"
    if LIST_PATTERN.search(content):
        return "list"
    if TOOL_PATTERN.search(content):
        return "tool"
    return "detail"


def infer_detected_elements(content: str) -> list[str]:
    hints: list[str] = []
    checks = [
        (r"button|btn|点击|操作", "按钮/操作区"),
        (r"table|thead|tbody|columns|pagination", "表格/结果区"),
        (r"filter|search|查询|筛选", "筛选区"),
        (r"dialog|drawer|modal|弹窗|抽屉", "弹窗/抽屉"),
        (r"tabs|tab-pane|分栏|标签", "标签/分栏"),
        (r"form|input|select|textarea", "表单字段"),
        (r"chart|graph|echarts|地图|图表|看板|趋势|mapbox|leaflet|amap", "图表/可视化"),
        (r"chat|prompt|assistant|result|generate", "生成链路"),
    ]
    for pattern, label in checks:
        if re.search(pattern, content, re.I):
            hints.append(label)
    return list(dict.fromkeys(hints))


def read_page_source_context(root: Path, relative_path: str, primary: str, file_set: set[str]) -> str:
    snippets = [f"// FILE: {relative_path}\n{primary}"]
    linked: list[str] = []
    for import_source in re.findall(r"from\s+[\"']([^\"']+)[\"']|import\s*\(\s*[\"']([^\"']+)[\"']\s*\)", primary):
        raw = next((part for part in import_source if part), "")
        resolved = resolve_imported_source_file(relative_path, raw, file_set)
        if resolved and resolved != relative_path:
            linked.append(resolved)
    for html_ref in re.findall(r"(?:src|href)\s*=\s*[\"']([^\"']+\.(?:js|css|ts|tsx|jsx|vue))[\"']", primary, re.I):
        candidate = normalize_path(str(Path(Path(relative_path).parent, html_ref)))
        if candidate in file_set:
            linked.append(candidate)
    for linked_file in sorted(dict.fromkeys(linked))[:8]:
        text = read_text(root / linked_file)
        if text:
            snippets.append(f"\n// LINKED FILE: {linked_file}\n{text[:6000]}")
    return "\n".join(snippets)


def extract_visible_texts(source: str) -> list[str]:
    source = remove_generated_viewer_blocks(source)
    source = re.sub(r"<head\b[\s\S]*?</head>", " ", source, flags=re.I)
    source = re.sub(r"<script\b[^>]*\bsrc\s*=\s*[\"'][^\"']+[\"'][^>]*></script>", " ", source, flags=re.I)
    source = re.sub(r"<link\b[^>]*>", " ", source, flags=re.I)
    source = re.sub(r"<!--[\s\S]*?-->", " ", source)
    matches = re.findall(r">([^<>{}\n]{2,48})<|[\"'`]([\u4e00-\u9fa5A-Za-z0-9][^\"'`\n]{1,40})[\"'`]", source)
    items: list[str] = []
    for left, right in matches:
        from_markup_text = bool(left)
        value = (left or right).strip()
        if not is_visible_text_hint(value, from_markup_text):
            continue
        value = re.sub(r"\s+", " ", value)
        if value not in items:
            items.append(value)
    return items[:60]


def remove_generated_viewer_blocks(source: str) -> str:
    return re.sub(
        r"<!--\s*proto-spec-annotator-viewer:start\s*-->[\s\S]*?<!--\s*proto-spec-annotator-viewer:end\s*-->",
        " ",
        source,
        flags=re.I,
    )


def is_visible_text_hint(value: str, from_markup_text: bool = False) -> bool:
    if not value or re.search(r"[{}<>]", value):
        return False
    normalized = re.sub(r"\s+", " ", value).strip()
    lower = normalized.lower()
    if not normalized.strip("`'\".,;:，。；：、()（）[]【】"):
        return False
    if lower in {
        "en",
        "utf-8",
        "viewport",
        "module",
        "text/javascript",
        "text/css",
        "stylesheet",
        "anonymous",
        "true",
        "false",
        "null",
        "domcontentloaded",
        "style",
        "button",
        "product",
        "spec",
    }:
        return False
    if any(token in lower for token in ("http://", "https://", "cdn.", "width=device-width", "initial-scale", ".js", ".css", "charset=", "viewport")):
        return False
    if not from_markup_text and not re.search(r"[\u4e00-\u9fa5]", normalized):
        return False
    if re.search(r"\b[a-zA-Z_$][\w$]*\s*\(", normalized):
        return False
    if re.search(r"\b(oninput|onclick|onchange|class|classname|id|data-lucide)\b", normalized, re.I):
        return False
    if " " in normalized and not re.search(r"[\u4e00-\u9fa5]", normalized):
        tokens = normalized.split()
        if len(tokens) >= 2 and all(re.fullmatch(r"[a-z0-9_:/.-]+", token, re.I) for token in tokens):
            return False
    if re.fullmatch(r"[#.]?[a-z0-9_-]{1,3}", lower):
        return False
    if re.fullmatch(r"#[0-9a-f]{3,8}", lower):
        return False
    if re.fullmatch(r"[a-z]+[-:][a-z0-9_.:-]+", lower) and not re.search(r"[\u4e00-\u9fa5]", normalized):
        return False
    return True


def extract_structure_hints(source: str) -> list[str]:
    checks = [
        (LIST_PATTERN, "存在表格、列表或结果区"),
        (re.compile(r"dialog|drawer|modal|sheet|弹窗|抽屉", re.I), "存在弹窗或抽屉"),
        (FORM_PATTERN, "存在表单输入"),
        (re.compile(r"tabs|tab-pane|segmented|el-tabs|标签", re.I), "存在标签/分栏切换"),
        (AIGC_PATTERN, "存在生成链路与结果反馈"),
        (BIG_SCREEN_PATTERN, "存在图表或可视化"),
    ]
    return [label for pattern, label in checks if pattern.search(source)]


def infer_secondary_surfaces(source: str) -> list[str]:
    surfaces: list[str] = []
    patterns = [
        (r"(?:title|label|header)\s*[:=]\s*[\"'`]([^\"'`]{2,30})(?:弹窗|抽屉|面板)?[\"'`]", ""),
        (r"(新建|编辑|详情|配置|导入|导出|高级筛选|列设置|选择器|预览|确认删除)[^<\n\"'`]{0,10}(弹窗|抽屉|面板|Drawer|Dialog|Modal)", ""),
        (r"(Drawer|Dialog|Modal|Sheet|Popover)[^A-Za-z0-9]{0,16}([\u4e00-\u9fa5A-Za-z0-9]{2,24})", ""),
    ]
    for pattern, _label in patterns:
        for match in re.finditer(pattern, source, re.I):
            values = [part for part in match.groups() if part]
            title = "".join(values).strip()
            title = re.sub(r"\s+", "", title)
            if not is_secondary_surface_hint(title):
                continue
            if 2 <= len(title) <= 32 and title not in surfaces:
                surfaces.append(title)
    return surfaces[:8]


def is_secondary_surface_hint(value: str) -> bool:
    lower = value.lower()
    if lower in {"modaloverlay", "drawercontainer", "tablecontainer", "toastcontainer", "maincontent"}:
        return False
    if not re.search(r"[\u4e00-\u9fa5]", value) and re.fullmatch(r"[a-z0-9_-]+", lower):
        return False
    return True


def extract_field_hints(source: str) -> list[dict]:
    fields: list[dict] = []
    patterns = [
        r"(?:label|placeholder|aria-label)\s*=\s*[\"']([^\"']{2,30})[\"']",
        r"<label[^>]*>([^<]{2,30})</label>",
        r"el-form-item[^>]*label\s*=\s*[\"']([^\"']{2,30})[\"']",
    ]
    for pattern in patterns:
        for match in re.finditer(pattern, source, re.I):
            name = re.sub(r"\s+", " ", match.group(1)).strip()
            if not name or any(item["name"] == name for item in fields):
                continue
            fields.append({"id": slugify(name) or f"field-{len(fields) + 1}", "name": name, "type": infer_field_type(name), "description": f"用于录入或筛选{name}。", "required": False})
            if len(fields) >= 20:
                return fields
    return fields


def infer_field_type(name: str) -> str:
    if re.search(r"时间|日期|Date|Time", name, re.I):
        return "日期"
    if re.search(r"状态|类型|分类|级别", name):
        return "下拉选择"
    if re.search(r"数量|金额|比例|阈值|分数", name):
        return "数字输入"
    return "文本输入"


def slugify(value: str) -> str:
    slug = re.sub(r"[^A-Za-z0-9\u4e00-\u9fa5]+", "-", value.lower()).strip("-")
    return slug or ""


def localize_page_type(page_type: str) -> str:
    return {"list": "列表页", "form": "表单页", "tool": "工具页", "detail": "详情页"}.get(page_type, "页面")


def localize_page_shape(page_shape: str) -> str:
    return {
        "mobile": "移动端页面",
        "workspace": "工作台页面",
        "big-screen": "大屏页面",
        "aigc": "AIGC 页面",
        "desktop": "桌面端页面",
    }.get(page_shape, "桌面端页面")


def default_sections_for(page: ProjectPage) -> list[dict]:
    if page.pageType == "list":
        return [
            {"id": "filters", "title": "【筛选条件】交互规则说明", "rules": ["筛选条件需说明默认值、重置逻辑和查询触发方式。"], "fields": []},
            {"id": "results", "title": "【结果区】显示规则说明", "rules": ["结果区需说明列表展示、排序、分页、空状态和失败反馈。"], "fields": []},
            {"id": "actions", "title": "【功能操作】交互规则说明", "rules": ["操作区需说明主操作、单条操作、批量操作和风险操作边界。"], "fields": []},
        ]
    if page.pageType == "form":
        return [
            {"id": "visibility", "title": "【显示隐藏】规则说明", "rules": ["说明表单打开方式、关闭路径和默认展示状态。"], "fields": []},
            {"id": "fields", "title": "【字段输入规则】说明", "rules": ["字段规则需覆盖默认值、校验时机、错误提示和联动关系。"], "fields": []},
            {"id": "submit", "title": "【提交规则】说明", "rules": ["提交规则需覆盖取消、保存、正式提交、成功反馈和失败提示。"], "fields": []},
        ]
    if page.pageType == "tool":
        return [
            {"id": "overview", "title": "【功能说明】规则说明", "rules": ["说明页面适用范围、前置条件和输出目标。"], "fields": []},
            {"id": "input", "title": "【输入或校验规则】说明", "rules": ["输入区需说明参数限制、校验提示和默认状态。"], "fields": []},
            {"id": "state", "title": "【状态说明】规则说明", "rules": ["状态说明需覆盖处理中、成功、失败和重试路径。"], "fields": []},
        ]
    return [
        {"id": "visibility", "title": "【显示隐藏】规则说明", "rules": ["说明页面打开方式、默认标签和主要展示状态。"], "fields": []},
        {"id": "info", "title": "【基础信息】显示规则说明", "rules": ["基础信息需说明关键字段、摘要信息和展示优先级。"], "fields": []},
        {"id": "actions", "title": "【功能操作】交互规则说明", "rules": ["操作说明需覆盖主操作、更多操作和风险提示。"], "fields": []},
    ]


def build_heuristic_summary(page: ProjectPage, visible_texts: list[str]) -> str:
    headline = next((item for item in visible_texts if re.search(r"[\u4e00-\u9fa5]", item) and len(item) >= 2), None)
    if not headline:
        headline = next((item for item in visible_texts if len(item) >= 4), page.pageName)
    if page.pageType == "list":
        return f"围绕 {headline} 提供筛选、结果查看与操作执行，并覆盖空状态、失败反馈和批量处理规则。"
    if page.pageType == "form":
        return f"围绕 {headline} 提供字段录入、校验、保存与提交链路，并明确默认值、联动规则和失败提示。"
    if page.pageType == "tool":
        return f"围绕 {headline} 提供输入、处理、结果反馈和重试链路，并覆盖生成态与异常恢复。"
    return f"围绕 {headline} 展示核心信息、状态与主操作，并明确显示优先级、切换路径和风险操作边界。"


def build_heuristic_spec(page: ProjectPage, source: str, current_batch_id: str) -> dict:
    visible_texts = extract_visible_texts(source)
    structure_hints = extract_structure_hints(source)
    sections = default_sections_for(page)
    fields = extract_field_hints(source)
    if fields:
        target_index = 1 if len(sections) > 1 else 0
        sections[target_index]["fields"] = fields
    context_rules: list[str] = []
    if visible_texts:
        context_rules.append("页面中出现的关键文案包括 " + "、".join(visible_texts[:8]) + "，需求说明应逐项对应这些可见模块。")
    if structure_hints:
        context_rules.append("页面结构特征包括 " + "、".join(structure_hints) + "，规则需覆盖对应承载区和状态。")
    if page.pageShape == "workspace":
        context_rules.append("工作台页面默认采用产品页面与需求说明互斥双视图，避免在同一可视区堆叠。")
    if page.pageShape == "mobile":
        context_rules.append("移动端页面需补充返回路径、底部固定操作和弱网/空状态提示。")
    if page.pageShape == "aigc":
        context_rules.append("AIGC 页面需覆盖输入限制、生成中状态、停止/重试入口和结果后续动作。")
    if context_rules:
        sections[0]["rules"] = list(dict.fromkeys([*sections[0]["rules"], *context_rules]))
    secondary_surfaces = infer_secondary_surfaces(source)
    for surface in secondary_surfaces:
        sections.append(
            {
                "id": slugify(surface) or f"secondary-{len(sections) + 1}",
                "title": f"【{surface}】交互规则说明",
                "rules": [f"{surface} 作为二级承载面时，需要说明打开入口、关闭方式、提交/确认行为和异常反馈。"],
                "fields": [],
            }
        )
    now = now_iso()
    return {
        "specSchemaVersion": SPEC_SCHEMA_VERSION,
        "storageFormat": "markdown",
        "pageKey": page.pageKey,
        "version": 1,
        "pageName": page.pageName,
        "pageType": localize_page_type(page.pageType),
        "pageShape": localize_page_shape(page.pageShape),
        "summary": build_heuristic_summary(page, visible_texts),
        "secondarySurfaces": secondary_surfaces,
        "sections": sections[:8],
        "meta": {
            "sourceType": "generated",
            "lastGeneratedAt": now,
            "lastManualEditedAt": None,
            "overwriteProtected": False,
            "specId": f"{page.pageKey}-spec",
            "batchId": current_batch_id,
        },
    }


def model_configured(args: argparse.Namespace) -> bool:
    return bool(args.model_base_url.strip() and args.model_api_key.strip() and args.model.strip())


def build_model_prompt(analysis: ProjectAnalysis, page: ProjectPage, source: str, args: argparse.Namespace, limit: int) -> str:
    visible_texts = extract_visible_texts(source)[:24]
    structure_hints = extract_structure_hints(source)
    secondary = infer_secondary_surfaces(source)
    template = {
        "pageKey": page.pageKey,
        "version": 1,
        "pageName": page.pageName,
        "pageType": "列表页/详情页/表单页/工具页",
        "pageShape": "桌面端页面/移动端页面/工作台页面/大屏页面/AIGC 页面",
        "summary": "一句话总结页面目标",
        "secondarySurfaces": ["如有需要可列出复杂弹窗/抽屉/二级面板"],
        "sections": [
            {
                "id": "section-id",
                "title": "【模块】规则说明",
                "rules": ["规则1", "规则2"],
                "fields": [{"id": "field-id", "name": "字段名", "type": "文本输入", "description": "字段说明", "required": False}],
            }
        ],
    }
    return "\n".join(
        [
            "你是一个负责给现有原型页面补充页面内需求说明的产品需求生成器。",
            "严格遵守：只能基于页面真实元素和可直接推断的信息写需求说明；输出合法 JSON 对象；不要输出 Markdown 或代码块。",
            "标题使用【模块】规则说明 / 【模块】交互规则说明 / 【模块】显示规则说明。",
            "每条规则短句、单一判断，适合产品/设计/研发评审。",
            "若页面包含弹窗、抽屉、标签页、图表、上传、风险操作、生成态，必须覆盖对应规则。",
            "fields 只输出 id、name、type、description、required。",
            "sections 最多 8 个，每个 section 最多 8 条 rules，fields 总数最多 20 个。",
            "最终回答第一个字符必须是 {，最后一个字符必须是 }。",
            "",
            "JSON 结构：",
            json.dumps(template, ensure_ascii=False, indent=2),
            "",
            "项目上下文：",
            f"- 框架：{analysis.framework}",
            f"- 当前操作：{args.operation}",
            f"- 页面文件：{page.relativePath}",
            f"- 页面类型推断：{page.pageType}",
            f"- 页面形态推断：{page.pageShape}",
            f"- 布局推断：{page.layoutMode}",
            "- 识别到的页面元素：" + ("、".join(page.detectedElements) if page.detectedElements else "待确认"),
            "- 页面中提取到的可见文本：" + (" | ".join(visible_texts) if visible_texts else "较少，请优先根据结构判断"),
            "- 结构特征：" + ("、".join(structure_hints) if structure_hints else "待确认"),
            "- 二级承载面清单：" + ("、".join(secondary) if secondary else "未识别到复杂承载面"),
            "",
            "页面源码节选：",
            source[:limit],
        ]
    )


def call_model(args: argparse.Namespace, prompt: str) -> str:
    url = args.model_base_url.rstrip("/") + "/chat/completions"
    body = {
        "model": args.model,
        "temperature": 0.2,
        "max_tokens": 6000,
        "stream": False,
        "response_format": {"type": "json_object"},
        "messages": [
            {"role": "system", "content": "你输出的最终结果必须是一个合法 JSON 对象。不要输出解释、Markdown 或代码块。"},
            {"role": "user", "content": prompt},
        ],
    }
    request = urllib.request.Request(
        url,
        data=json.dumps(body).encode("utf-8"),
        headers={"Content-Type": "application/json", "Authorization": f"Bearer {args.model_api_key}"},
        method="POST",
    )
    with urllib.request.urlopen(request, timeout=60) as response:
        payload = json.loads(response.read().decode("utf-8"))
    content = payload.get("choices", [{}])[0].get("message", {}).get("content", "")
    if isinstance(content, list):
        content = "".join(item.get("text", "") for item in content if isinstance(item, dict))
    if not isinstance(content, str) or not content.strip():
        raise ValueError("模型响应为空。")
    return content


def extract_json_object(raw: str) -> dict:
    text = raw.strip()
    try:
        payload = json.loads(text)
    except json.JSONDecodeError:
        match = re.search(r"\{[\s\S]*\}", text)
        if not match:
            raise
        payload = json.loads(match.group(0))
    if not isinstance(payload, dict):
        raise ValueError("模型输出不是 JSON 对象。")
    return payload


def normalize_model_spec(payload: dict, page: ProjectPage, fallback: dict, current_batch_id: str) -> dict:
    sections = payload.get("sections") if isinstance(payload.get("sections"), list) else fallback["sections"]
    normalized_sections: list[dict] = []
    for index, section in enumerate(sections[:8]):
        section = section if isinstance(section, dict) else {}
        fields = section.get("fields") if isinstance(section.get("fields"), list) else []
        normalized_sections.append(
            {
                "id": str(section.get("id") or f"section-{index + 1}"),
                "title": str(section.get("title") or f"【章节 {index + 1}】规则说明"),
                "rules": [str(rule).strip() for rule in section.get("rules", []) if str(rule).strip()] or ["待补充页面规则。"],
                "fields": [
                    {
                        "id": str(field.get("id") or f"field-{field_index + 1}"),
                        "name": str(field.get("name") or f"字段 {field_index + 1}"),
                        "type": str(field.get("type") or ""),
                        "description": str(field.get("description") or field.get("value") or ""),
                        "required": bool(field.get("required")),
                    }
                    for field_index, field in enumerate(fields[:20])
                    if isinstance(field, dict)
                ],
            }
        )
    now = now_iso()
    return {
        **fallback,
        **payload,
        "specSchemaVersion": SPEC_SCHEMA_VERSION,
        "storageFormat": "markdown",
        "pageKey": page.pageKey,
        "pageName": str(payload.get("pageName") or page.pageName),
        "pageType": str(payload.get("pageType") or fallback["pageType"]),
        "pageShape": str(payload.get("pageShape") or fallback["pageShape"]),
        "summary": str(payload.get("summary") or fallback["summary"]),
        "secondarySurfaces": [str(item) for item in payload.get("secondarySurfaces", []) if str(item).strip()]
        if isinstance(payload.get("secondarySurfaces"), list)
        else fallback.get("secondarySurfaces", []),
        "sections": normalized_sections,
        "meta": {
            "sourceType": "generated",
            "lastGeneratedAt": now,
            "lastManualEditedAt": None,
            "overwriteProtected": False,
            "specId": f"{page.pageKey}-spec",
            "batchId": current_batch_id,
        },
    }


def build_page_spec(analysis: ProjectAnalysis, page: ProjectPage, source: str, args: argparse.Namespace, current_batch_id: str, report: WorkflowReport) -> dict:
    fallback = build_heuristic_spec(page, source, current_batch_id)
    if not model_configured(args):
        mark_local_rule_draft(fallback, args, report, page.pageKey, "未配置 runner 模型参数")
        return fallback
    last_error: Exception | None = None
    for limit in (9000, 5000, 2500):
        try:
            raw = call_model(args, build_model_prompt(analysis, page, source, args, limit))
            return normalize_model_spec(extract_json_object(raw), page, fallback, current_batch_id)
        except (urllib.error.URLError, urllib.error.HTTPError, ValueError, json.JSONDecodeError) as error:
            last_error = error
            report.warnings.append(f"{page.pageKey}: 模型生成在 {limit} 字符上下文失败，准备降级或重试：{error}")
    mark_local_rule_draft(fallback, args, report, page.pageKey, f"模型不可用，最后错误：{last_error}")
    return fallback


def mark_local_rule_draft(spec: dict, args: argparse.Namespace, report: WorkflowReport, page_key: str, reason: str) -> None:
    meta = spec.setdefault("meta", {})
    if isinstance(meta, dict):
        meta["sourceType"] = "local-rule-draft"
        meta["generationMode"] = "local-rule"
        meta["aiReviewRequired"] = not args.draft_only
        meta["aiReviewStatus"] = "pending" if not args.draft_only else "skipped-draft-only"
    if page_key not in report.localRuleDraftPages:
        report.localRuleDraftPages.append(page_key)
    if args.draft_only:
        report.warnings.append(f"{page_key}: {reason}，已按 --draft-only 保留本地规则基础草稿；正文未经过 AI 审阅补全。")
        return
    report.aiReviewRequired = True
    if page_key not in report.aiReviewPages:
        report.aiReviewPages.append(page_key)
    report.warnings.append(f"{page_key}: {reason}，已使用本地规则生成基础草稿；当前 AI 编程工具必须继续审阅页面代码并补全 current/{page_key}.md，除非用户明确只要草稿。")


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
    if "generationMode" in meta:
        frontmatter["generationMode"] = meta.get("generationMode")
    if "aiReviewRequired" in meta:
        frontmatter["aiReviewRequired"] = meta.get("aiReviewRequired")
    if "aiReviewStatus" in meta:
        frontmatter["aiReviewStatus"] = meta.get("aiReviewStatus")
    lines = ["---"]
    lines.extend(f"{key}: {scalar(value)}" for key, value in frontmatter.items())
    lines.extend(["---", "", f"# {spec.get('pageName') or spec.get('pageKey')}", "", f"## {SUMMARY_HEADING}", ""])
    lines.extend([str(spec.get("summary") or "暂无页面摘要。"), ""])
    secondary = spec.get("secondarySurfaces")
    if isinstance(secondary, list) and secondary:
        lines.extend([f"## {SECONDARY_SURFACES_HEADING}", ""])
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
            lines.extend([f"### {FIELD_TABLE_HEADING}", "", "| 字段 | 形态 | 必填 | 说明 |", "|---|---|---|---|"])
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


def parse_frontmatter(raw: str) -> tuple[dict[str, object], str]:
    if not raw.startswith("---\n"):
        return {}, raw
    end = raw.find("\n---", 4)
    if end == -1:
        return {}, raw
    frontmatter: dict[str, object] = {}
    for line in raw[4:end].splitlines():
        if ":" not in line:
            continue
        key, value = line.split(":", 1)
        frontmatter[key.strip()] = parse_frontmatter_value(value.strip())
    return frontmatter, raw[end + 4 :].lstrip("\r\n")


def parse_frontmatter_value(raw: str) -> object:
    if raw in {"null", "~"}:
        return None
    if raw == "true":
        return True
    if raw == "false":
        return False
    if re.fullmatch(r"-?\d+", raw):
        return int(raw)
    if re.fullmatch(r"-?\d+\.\d+", raw):
        return float(raw)
    if (raw.startswith('"') and raw.endswith('"')) or (raw.startswith("'") and raw.endswith("'")):
        try:
            return json.loads(raw)
        except json.JSONDecodeError:
            return raw[1:-1]
    return raw


def save_spec(spec_root: Path, page: ProjectPage, spec: dict, force: bool, dry_run: bool, report: WorkflowReport) -> bool:
    current_dir = spec_root / "current"
    history_dir = spec_root / "history" / page.pageKey
    target = current_dir / f"{page.pageKey}.md"
    existing_raw = read_text(target)
    existing_frontmatter, existing_body = parse_frontmatter(existing_raw or "")
    ensure_dir(history_dir, dry_run, report)
    if existing_raw:
        if existing_frontmatter.get("overwriteProtected") is True and not force:
            report.skipped.append(f"{page.pageKey}: overwriteProtected=true，未覆盖。")
            return False
        if existing_frontmatter.get("lastManualEditedAt") not in {None, "null", ""} and not force:
            report.skipped.append(f"{page.pageKey}: 存在 lastManualEditedAt，未覆盖；使用 --force 才会写历史快照后覆盖。")
            return False
        if not force:
            report.skipped.append(f"{page.pageKey}: current spec already exists；使用 --force 才会写历史快照后覆盖。")
            return False
        if not dry_run:
            (history_dir / f"{stamp()}.before-overwrite.md").write_text(existing_raw, encoding="utf-8")
            report.changedFiles.append(str(history_dir))
        spec["version"] = max(int(spec.get("version") or 1), int(existing_frontmatter.get("version") or 1) + 1)
    markdown = spec_to_markdown(spec)
    if existing_body and parse_frontmatter(markdown)[1].strip() == existing_body.strip():
        return True
    write_text(target, markdown, dry_run, report)
    return True


def update_registry(spec_root: Path, pages: Iterable[ProjectPage], dry_run: bool, report: WorkflowReport, remove_keys: set[str] | None = None) -> None:
    registry_path = spec_root / "registry.json"
    payload = read_json(registry_path) or {"specSchemaVersion": SPEC_SCHEMA_VERSION, "storageFormat": "markdown", "pages": [], "lastUpdated": ""}
    existing_pages = payload.get("pages") if isinstance(payload.get("pages"), list) else []
    by_key = {
        entry.get("pageKey"): entry
        for entry in existing_pages
        if isinstance(entry, dict) and isinstance(entry.get("pageKey"), str)
    }
    for page in pages:
        by_key[page.pageKey] = {
            **(by_key.get(page.pageKey) or {}),
            "pageKey": page.pageKey,
            "pageName": page.pageName,
            "sourceFile": page.relativePath,
            "routeHint": page.routeHint,
        }
    if remove_keys:
        for key in remove_keys:
            by_key.pop(key, None)
    payload["specSchemaVersion"] = SPEC_SCHEMA_VERSION
    payload["storageFormat"] = "markdown"
    payload["pages"] = sorted(by_key.values(), key=lambda item: item.get("pageKey", ""))
    payload["lastUpdated"] = now_iso()
    write_json(registry_path, payload, dry_run, report)


def prune_stale_current_specs(
    spec_root: Path,
    active_page_keys: set[str],
    dry_run: bool,
    report: WorkflowReport,
) -> set[str]:
    current_dir = spec_root / "current"
    if not current_dir.is_dir():
        return set()

    stale_keys: set[str] = set()
    for target in sorted([*current_dir.glob("*.md"), *current_dir.glob("*.json")]):
        if target.stem in active_page_keys:
            continue
        stale_keys.add(target.stem)
        if dry_run:
            report.changedFiles.append(str(target))
            continue

        existing_raw = read_text(target) or ""
        history_dir = spec_root / "history" / target.stem
        history_dir.mkdir(parents=True, exist_ok=True)
        snapshot_suffix = ".md" if target.suffix == ".md" else ".json"
        (history_dir / f"{stamp()}.before-delete{snapshot_suffix}").write_text(existing_raw, encoding="utf-8")
        target.unlink()
        report.changedFiles.append(str(history_dir))
        report.changedFiles.append(str(target))

    if stale_keys:
        report.warnings.append("Removed stale current specs not matching discovered pages: " + ", ".join(sorted(stale_keys)))
    return stale_keys


def write_viewer_config(spec_root: Path, args: argparse.Namespace, dry_run: bool, report: WorkflowReport) -> None:
    payload = read_json(spec_root / "viewer-config.json") or {}
    payload.update(
        {
            "specSchemaVersion": SPEC_SCHEMA_VERSION,
            "visibilityMode": args.visibility_mode,
            "viewerMode": args.viewer_mode,
            "htmlSaveMode": args.html_save_mode,
            "updatedAt": now_iso(),
        }
    )
    write_json(spec_root / "viewer-config.json", payload, dry_run, report)


def delete_specs(spec_root: Path, pages: list[ProjectPage], args: argparse.Namespace, report: WorkflowReport) -> None:
    removed: set[str] = set()
    for page in pages:
        history_dir = spec_root / "history" / page.pageKey
        deleted_any = False
        for suffix in (".md", ".json"):
            target = spec_root / "current" / f"{page.pageKey}{suffix}"
            existing_raw = read_text(target)
            if existing_raw and not args.dry_run:
                history_dir.mkdir(parents=True, exist_ok=True)
                snapshot_suffix = ".md" if suffix == ".md" else ".json"
                (history_dir / f"{stamp()}.before-delete{snapshot_suffix}").write_text(existing_raw, encoding="utf-8")
                report.changedFiles.append(str(history_dir))
            if target.exists():
                deleted_any = True
                if args.dry_run:
                    report.changedFiles.append(str(target))
                else:
                    target.unlink()
                    report.changedFiles.append(str(target))
        if deleted_any:
            removed.add(page.pageKey)
        else:
            report.skipped.append(f"{page.pageKey}: no current spec found.")
    update_registry(spec_root, [], args.dry_run, report, remove_keys=removed)


def select_pages(analysis: ProjectAnalysis, args: argparse.Namespace) -> list[ProjectPage]:
    page_keys = {key.strip() for key in args.page_key if key.strip()}
    file_filters = {normalize_path(path) for path in args.file}
    pages = analysis.pages
    if page_keys:
        pages = [page for page in pages if page.pageKey in page_keys]
    if file_filters:
        pages = [page for page in pages if page.relativePath in file_filters]
    if args.scope == "selected" and not page_keys and not file_filters:
        return []
    return pages


def generate_specs(root: Path, analysis: ProjectAnalysis, pages: list[ProjectPage], args: argparse.Namespace, report: WorkflowReport) -> None:
    spec_root = Path(analysis.specRoot)
    current_batch_id = batch_id()
    if not args.dry_run:
        (spec_root / "current").mkdir(parents=True, exist_ok=True)
        (spec_root / "history").mkdir(parents=True, exist_ok=True)
    saved_pages: list[ProjectPage] = []
    file_set = set(list_project_files(root))
    for page in pages:
        primary = read_text(root / page.relativePath) or ""
        source = read_page_source_context(root, page.relativePath, primary, file_set)
        spec = build_page_spec(analysis, page, source, args, current_batch_id, report)
        if save_spec(spec_root, page, spec, args.force, args.dry_run, report):
            saved_pages.append(page)
    stale_keys: set[str] = set()
    if args.scope == "all" and args.force:
        stale_keys = prune_stale_current_specs(spec_root, {page.pageKey for page in pages}, args.dry_run, report)
    if saved_pages or stale_keys:
        update_registry(spec_root, saved_pages, args.dry_run, report, remove_keys=stale_keys)
    write_viewer_config(spec_root, args, args.dry_run, report)


def integrate_viewer(root: Path, analysis: ProjectAnalysis, pages: list[ProjectPage], args: argparse.Namespace, report: WorkflowReport) -> None:
    if args.viewer_mode == "dual-view":
        cleanup_legacy_inline_viewer(root, analysis.framework, args.dry_run, report)
    if analysis.framework == "html":
        integrate_html_viewer(root, pages, args, report)
        return
    if analysis.framework == "react":
        integrate_react_viewer(root, pages, args, report)
        return
    if analysis.framework == "vue":
        integrate_vue_viewer(root, pages, args, report)
        return
    report.warnings.append("未稳定识别框架，跳过自动展示层接线。")


HTML_VIEWER_MARKER = "data-proto-spec-annotator-viewer"
LEGACY_HTML_VIEWER_ASSETS = (
    "assets/css/proto-spec.css",
    "assets/js/proto-spec-viewer.js",
    "assets/js/spec-viewer.js",
    "assets/page-spec-shell.js",
    "assets/page-spec-render.js",
)
LEGACY_SCRIPT_TAG_PATTERN = re.compile(
    r"\n?[ \t]*<script\b[^>]*\bsrc\s*=\s*[\"'][^\"']*(?:assets/js/(?:proto-spec-viewer|spec-viewer)\.js|assets/page-spec-(?:shell|render)\.js)[^\"']*[\"'][^>]*>\s*</script>[ \t]*",
    re.I,
)
LEGACY_STYLESHEET_TAG_PATTERN = re.compile(
    r"\n?[ \t]*<link\b[^>]*\bhref\s*=\s*[\"'][^\"']*assets/css/proto-spec\.css[^\"']*[\"'][^>]*>[ \t]*",
    re.I,
)
LEGACY_INIT_SPEC_VIEWER_PATTERN = re.compile(
    r"\n?[ \t]*(?:setTimeout\(\s*\(\)\s*=>\s*)?init(?:Proto)?SpecViewer\(\s*[\"'][^\"']+[\"']\s*\)\s*(?:,\s*\d+\s*\))?\s*;?[ \t]*",
    re.I,
)
LEGACY_PROTO_SPEC_STYLE_PATTERN = re.compile(
    r"\n?[ \t]*/\*\s*Proto Spec Viewer\s*\*/[\s\S]*?(?=\n[ \t]*(?:/\*|</style>))",
    re.I,
)
LEGACY_INLINE_CLASS_PATTERN = re.compile(
    r"\bproto-spec-(?:divider|badge|page-name|header|header-left|header-right|btn|btn-edit|btn-save|btn-toggle|content|preview|editor|loading|error|status|status-ok|status-err|h[1-4]|p|ul|li|table|th|td|code)\b"
)


def cleanup_legacy_inline_viewer(root: Path, framework: str, dry_run: bool, report: WorkflowReport) -> None:
    """Remove old inline/document-flow viewers before writing the unified dual-view shell."""
    removed_files: list[Path] = []
    for relative in LEGACY_HTML_VIEWER_ASSETS:
        target = root / relative
        if not target.exists():
            continue
        if dry_run:
            report.changedFiles.append(str(target))
        else:
            target.unlink()
            report.changedFiles.append(str(target))
        removed_files.append(target)

    for path in iter_legacy_viewer_candidate_files(root):
        source = read_text(path)
        if source is None:
            continue
        next_source = remove_legacy_inline_viewer_source(source)
        if next_source == source:
            continue
        write_text(path, next_source, dry_run, report)

    if removed_files:
        report.warnings.append("Removed legacy inline spec viewer assets before dual-view integration: " + ", ".join(str(path.relative_to(root)) for path in removed_files))


def iter_legacy_viewer_candidate_files(root: Path) -> Iterable[Path]:
    extensions = {".html", ".htm", ".vue", ".jsx", ".tsx", ".js", ".ts"}
    for path in root.rglob("*"):
        try:
            relative = path.relative_to(root)
        except ValueError:
            continue
        if any(part in IGNORED_DIRS for part in relative.parts):
            continue
        if path.is_file() and path.suffix.lower() in extensions:
            yield path


def remove_legacy_inline_viewer_source(source: str) -> str:
    next_source = remove_html_viewer(source)
    next_source = LEGACY_SCRIPT_TAG_PATTERN.sub("", next_source)
    next_source = LEGACY_STYLESHEET_TAG_PATTERN.sub("", next_source)
    next_source = LEGACY_INIT_SPEC_VIEWER_PATTERN.sub("", next_source)
    next_source = LEGACY_PROTO_SPEC_STYLE_PATTERN.sub("", next_source)
    next_source = remove_legacy_inline_spec_blocks(next_source)
    return collapse_excess_blank_lines(next_source)


def remove_legacy_inline_spec_blocks(source: str) -> str:
    output: list[str] = []
    index = 0
    removed_any = False
    for match in re.finditer(r"<(?P<tag>section|div|article)\b(?P<attrs>[^>]*)>", source, re.I):
        attrs = match.group("attrs")
        if not (
            re.search(r'data-role\s*=\s*["\']page-spec["\']', attrs, re.I)
            or re.search(r'data-spec-origin\s*=\s*["\']prototype-spec-annotator["\']', attrs, re.I)
            or re.search(r'class\s*=\s*["\'][^"\']*\bproto-spec-doc\b[^"\']*["\']', attrs, re.I)
        ):
            continue
        close_end = find_matching_html_close(source, match.end(), match.group("tag"))
        if close_end is None:
            continue
        output.append(source[index : match.start()])
        index = close_end
        removed_any = True
    if not removed_any:
        return source
    output.append(source[index:])
    return "".join(output)


def find_matching_html_close(source: str, start: int, tag: str) -> int | None:
    pattern = re.compile(rf"</?{re.escape(tag)}\b[^>]*>", re.I)
    depth = 1
    for match in pattern.finditer(source, start):
        if match.group(0).startswith("</"):
            depth -= 1
            if depth == 0:
                return match.end()
        else:
            depth += 1
    return None


def collapse_excess_blank_lines(source: str) -> str:
    return re.sub(r"\n{3,}", "\n\n", source)


def integrate_html_viewer(root: Path, pages: list[ProjectPage], args: argparse.Namespace, report: WorkflowReport) -> None:
    write_text(root / "proto-spec-server.mjs", html_local_server_source(), args.dry_run, report)
    for page in pages:
        path = root / page.relativePath
        source = read_text(path)
        if source is None or path.suffix.lower() not in {".html", ".htm"}:
            continue
        next_source = inject_html_viewer(source, page.pageKey, args.viewer_mode)
        write_text(path, next_source, args.dry_run, report)


def inject_html_viewer(source: str, page_key: str, viewer_mode: str) -> str:
    cleaned = remove_html_viewer(source)
    payload = html_viewer_runtime(page_key, viewer_mode)
    if re.search(r"</body\s*>", cleaned, re.I):
        return re.sub(r"</body\s*>", lambda _match: payload + "\n</body>", cleaned, count=1, flags=re.I)
    return cleaned + "\n" + payload + "\n"


def remove_html_viewer(source: str) -> str:
    pattern = re.compile(r"\n?<!-- proto-spec-annotator-viewer:start -->[\s\S]*?<!-- proto-spec-annotator-viewer:end -->\n?", re.I)
    return pattern.sub("\n", source)


def html_viewer_runtime(page_key: str, viewer_mode: str) -> str:
    page_key_literal = json.dumps(page_key, ensure_ascii=False)
    viewer_mode_literal = json.dumps(viewer_mode, ensure_ascii=False)
    css_literal = json.dumps(proto_spec_css(), ensure_ascii=False)
    return """<!-- proto-spec-annotator-viewer:start -->
<div data-proto-spec-annotator-viewer></div>
<script>
(function () {{
  const mount = document.currentScript.previousElementSibling;
  const pageKey = __PAGE_KEY__;
  const viewerMode = __VIEWER_MODE__ || "dual-view";
  const script = document.currentScript;
  const style = document.createElement("style");
  style.textContent = __PROTO_SPEC_CSS__;
  document.head.appendChild(style);
  const switcher = document.createElement("div");
  switcher.className = "proto-spec-switcher";
  switcher.innerHTML = '<button type="button" data-view="product" class="is-active">产品页面</button><button type="button" data-view="spec">需求说明</button>';
  document.body.appendChild(switcher);
  const productNodes = Array.from(document.body.children).filter(function (node) {{
    return node !== switcher && node !== mount && node !== script && node.tagName !== "SCRIPT";
  }});
  const specPanel = document.createElement("main");
  specPanel.className = "proto-spec-doc";
  specPanel.hidden = true;
  specPanel.innerHTML = '<div class="proto-spec-doc__inner"><h1>需求说明</h1><p>正在加载...</p></div>';
  document.body.appendChild(specPanel);
  let frontmatterText = "";
  let bodyMarkdown = "";
  let draft = "";
  let editing = false;
  let editorMode = "write";
  let status = "";
  function splitFrontmatter(markdown) {{
    if (!markdown.startsWith("---\\n")) return {{ frontmatterText: "", body: markdown.trim() }};
    const end = markdown.indexOf("\\n---", 4);
    if (end === -1) return {{ frontmatterText: "", body: markdown.trim() }};
    return {{
      frontmatterText: markdown.slice(4, end),
      body: markdown.slice(end + 4).replace(/^\\s*\\n/, "").trim()
    }};
  }}
  function composeMarkdown() {{
    return frontmatterText ? "---\\n" + frontmatterText + "\\n---\\n\\n" + draft.trim() + "\\n" : draft.trim() + "\\n";
  }}
  function renderMarkdown(markdown) {{
    const lines = markdown.replace(/\\r\\n/g, "\\n").split("\\n");
    const out = [];
    let paragraph = [];
    function flushParagraph() {{
      if (!paragraph.length) return;
      out.push("<p>" + paragraph.map(renderInline).join("<br>") + "</p>");
      paragraph = [];
    }}
    for (let index = 0; index < lines.length; index += 1) {{
      const line = lines[index];
      const trimmed = line.trim();
      const fence = trimmed.match(/^```\\s*([A-Za-z0-9_-]*)\\s*$/);
      if (fence) {{
        flushParagraph();
        const lang = (fence[1] || "").toLowerCase();
        const code = [];
        index += 1;
        while (index < lines.length && !lines[index].trim().startsWith("```")) {{
          code.push(lines[index]);
          index += 1;
        }}
        const codeText = code.join("\\n");
        out.push(lang === "mermaid"
          ? '<figure class="proto-spec-mermaid" data-mermaid="' + escapeAttr(codeText) + '"><figcaption>Mermaid</figcaption><pre><code>' + escapeHtml(codeText) + "</code></pre></figure>"
          : '<pre><code>' + escapeHtml(codeText) + "</code></pre>");
        continue;
      }}
      if (!trimmed) {{
        flushParagraph();
        continue;
      }}
      const heading = trimmed.match(/^(#{1,4})\\s+(.+)$/);
      if (heading) {{
        flushParagraph();
        out.push("<h" + heading[1].length + ">" + renderInline(heading[2]) + "</h" + heading[1].length + ">");
        continue;
      }}
      if (isQuoteStart(trimmed)) {{
        flushParagraph();
        const quote = renderQuoteBlock(lines, index);
        out.push(quote.html);
        index = quote.index - 1;
        continue;
      }}
      if (isTableStart(lines, index)) {{
        flushParagraph();
        const headers = parseTableRow(lines[index]);
        index += 2;
        const rows = [];
        while (index < lines.length && lines[index].trim().startsWith("|")) {{
          rows.push(parseTableRow(lines[index]));
          index += 1;
        }}
        index -= 1;
        out.push(renderTable(headers, rows));
        continue;
      }}
      if (parseListItem(line)) {{
        flushParagraph();
        const list = renderListBlock(lines, index);
        out.push(list.html);
        index = list.index - 1;
        continue;
      }}
      paragraph.push(line);
    }}
    flushParagraph();
    return out.join("");
  }}
  function isQuoteStart(trimmed) {{
    return /^>\\s?/.test(trimmed);
  }}
  function renderQuoteBlock(lines, start) {{
    const quoteLines = [];
    let index = start;
    while (index < lines.length) {{
      const line = lines[index] || "";
      if (!line.trim()) {{
        quoteLines.push("");
        index += 1;
        continue;
      }}
      const quote = line.match(/^\\s*>\\s?(.*)$/);
      if (!quote) break;
      quoteLines.push(quote[1] || "");
      index += 1;
    }}
    const callout = quoteLines[0]?.match(/^\\[!(NOTE|TIP|IMPORTANT|WARNING|CAUTION|TODO|INFO|RISK)\\]\\s*(.*)$/i);
    if (callout) {{
      const type = callout[1].toLowerCase();
      const title = callout[2] || calloutLabel(type);
      const body = quoteLines.slice(1).join("\\n").trim();
      return {{
        html: '<blockquote class="proto-spec-callout proto-spec-callout--' + escapeAttr(type) + '"><p class="proto-spec-callout__title">' + renderInline(title) + "</p>" + (body ? renderMarkdown(body) : "") + "</blockquote>",
        index
      }};
    }}
    return {{ html: "<blockquote>" + renderMarkdown(quoteLines.join("\\n").trim()) + "</blockquote>", index }};
  }}
  function calloutLabel(type) {{
    return {{ note: "说明", tip: "建议", important: "重要", warning: "警告", caution: "注意", todo: "待办", info: "信息", risk: "风险" }}[type] || "说明";
  }}
  function parseListItem(line) {{
    const match = String(line || "").match(/^(\\s*)([-*+]|\\d+[.)])\\s+(?:\\[( |x|X)\\]\\s+)?(.+)$/);
    if (!match) return null;
    return {{
      indent: match[1].replace(/\\t/g, "    ").length,
      ordered: /^\\d/.test(match[2]),
      task: match[3] !== undefined,
      checked: /x/i.test(match[3] || ""),
      text: match[4]
    }};
  }}
  function renderListBlock(lines, start) {{
    const first = parseListItem(lines[start]);
    if (!first) return {{ html: "", index: start + 1 }};
    const tag = first.ordered ? "ol" : "ul";
    const items = [];
    let index = start;
    while (index < lines.length) {{
      const item = parseListItem(lines[index]);
      if (!item || item.indent !== first.indent || item.ordered !== first.ordered) break;
      let content = (item.task ? renderTaskCheckbox(item.checked) : "") + renderInline(item.text);
      index += 1;
      while (index < lines.length) {{
        const next = parseListItem(lines[index]);
        const raw = lines[index] || "";
        if (!raw.trim()) {{
          index += 1;
          continue;
        }}
        if (next && next.indent > first.indent) {{
          const nested = renderListBlock(lines, index);
          content += nested.html;
          index = nested.index;
          continue;
        }}
        if (next && next.indent <= first.indent) break;
        const continuationIndent = raw.match(/^\\s*/)[0].replace(/\\t/g, "    ").length;
        if (continuationIndent > first.indent) {{
          content += "<br>" + renderInline(raw.trim());
          index += 1;
          continue;
        }}
        break;
      }}
      items.push("<li>" + content + "</li>");
    }}
    return {{ html: "<" + tag + ">" + items.join("") + "</" + tag + ">", index }};
  }}
  function renderTaskCheckbox(checked) {{
    return '<input class="proto-spec-task-checkbox" type="checkbox" disabled' + (checked ? " checked" : "") + ' aria-label="' + (checked ? "已完成" : "未完成") + '">';
  }}
  function isTableStart(lines, index) {{
    return Boolean(lines[index] && lines[index + 1] && lines[index].trim().startsWith("|") && lines[index + 1].trim().startsWith("|") && parseTableRow(lines[index + 1]).every(function (cell) {{ return /^:?-{{3,}}:?$/.test(cell); }}));
  }}
  function parseTableRow(line) {{
    return line.trim().replace(/^\\||\\|$/g, "").split("|").map(function (cell) {{ return cell.trim(); }});
  }}
  function renderTable(headers, rows) {{
    return "<table><thead><tr>" + headers.map(function (cell) {{ return "<th>" + renderInline(cell) + "</th>"; }}).join("") + "</tr></thead><tbody>" + rows.map(function (row) {{ return "<tr>" + headers.map(function (_header, index) {{ return "<td>" + renderInline(row[index] || "") + "</td>"; }}).join("") + "</tr>"; }}).join("") + "</tbody></table>";
  }}
  function renderInline(value) {{
    let output = "";
    let cursor = 0;
    const pattern = /!\\[([^\\]]*)\\]\\(([^)\\s]+)(?:\\s+"([^"]*)")?\\)|\\[([^\\]]+)\\]\\(([^)\\s]+)\\)|`([^`]+)`|\\*\\*([^*]+)\\*\\*|==([^=]+)==/g;
    let match;
    while ((match = pattern.exec(value)) !== null) {{
      output += escapeHtml(value.slice(cursor, match.index));
      if (match[1] !== undefined) output += '<img src="' + escapeAttr(resolveImageSrc(match[2])) + '" alt="' + escapeAttr(match[1]) + '"' + (match[3] ? ' title="' + escapeAttr(match[3]) + '"' : "") + ">";
      else if (match[4] !== undefined) output += '<a href="' + escapeAttr(match[5]) + '" target="_blank" rel="noreferrer">' + escapeHtml(match[4]) + "</a>";
      else if (match[6] !== undefined) output += "<code>" + escapeHtml(match[6]) + "</code>";
      else if (match[7] !== undefined) output += "<strong>" + escapeHtml(match[7]) + "</strong>";
      else if (match[8] !== undefined) output += "<mark>" + escapeHtml(match[8]) + "</mark>";
      cursor = match.index + match[0].length;
    }}
    return output + escapeHtml(value.slice(cursor));
  }}
  function loadMermaid() {{
    if (window.mermaid && typeof window.mermaid.render === "function") {{
      initializeMermaid(window.mermaid);
      return Promise.resolve(window.mermaid);
    }}
    if (window.__protoSpecMermaidPromise) return window.__protoSpecMermaidPromise;
    window.__protoSpecMermaidPromise = new Promise(function (resolve, reject) {{
      const existing = document.querySelector("script[data-proto-spec-mermaid]");
      if (existing) {{
        existing.addEventListener("load", function () {{
          if (window.mermaid && typeof window.mermaid.render === "function") {{
            initializeMermaid(window.mermaid);
            resolve(window.mermaid);
          }} else {{
            reject(new Error("Mermaid failed to initialize."));
          }}
        }}, {{ once: true }});
        existing.addEventListener("error", reject, {{ once: true }});
        return;
      }}
      const script = document.createElement("script");
      script.src = "https://cdn.jsdelivr.net/npm/mermaid@10/dist/mermaid.min.js";
      script.async = true;
      script.dataset.protoSpecMermaid = "true";
      script.onload = function () {{
        if (window.mermaid && typeof window.mermaid.render === "function") {{
          initializeMermaid(window.mermaid);
          resolve(window.mermaid);
        }} else {{
          reject(new Error("Mermaid failed to initialize."));
        }}
      }};
      script.onerror = reject;
      document.head.appendChild(script);
    }});
    return window.__protoSpecMermaidPromise;
  }}
  function initializeMermaid(mermaid) {{
    if (window.__protoSpecMermaidInitialized) return;
    if (typeof mermaid.initialize === "function") mermaid.initialize({{ startOnLoad: false, securityLevel: "strict" }});
    window.__protoSpecMermaidInitialized = true;
  }}
  function renderMermaidDiagrams() {{
    const nodes = Array.from(specPanel.querySelectorAll(".proto-spec-mermaid[data-mermaid]:not([data-rendered])"));
    if (!nodes.length) return;
    nodes.forEach(function (node) {{ node.setAttribute("data-rendered", "loading"); }});
    loadMermaid().then(function (mermaid) {{
      nodes.forEach(function (node, index) {{
      const code = node.getAttribute("data-mermaid") || "";
      mermaid.render("proto-spec-mermaid-" + pageKey + "-" + index + "-" + Date.now(), code).then(function (result) {{
        node.setAttribute("data-rendered", "true");
        node.innerHTML = result.svg || node.innerHTML;
      }}).catch(function () {{
        node.setAttribute("data-rendered", "failed");
      }});
      }});
    }}).catch(function () {{
      nodes.forEach(function (node) {{ node.setAttribute("data-rendered", "failed"); }});
    }});
  }}
  function resolveImageSrc(src) {{
    const value = String(src || "");
    if (/^(?:https?:|data:|blob:|\\/)/i.test(value)) return value;
    const assetPrefix = "../assets/" + pageKey + "/";
    if (value.startsWith(assetPrefix)) {{
      return "/__prototype-specs/assets/" + encodeURIComponent(pageKey) + "/" + value.slice(assetPrefix.length).split("/").map(encodeURIComponent).join("/");
    }}
    return value;
  }}
  function pastedImageFiles(event) {{
    const items = Array.from(event.clipboardData?.items || []);
    return items
      .filter(function (item) {{ return item.kind === "file" && /^image\\/(png|jpe?g|webp|gif)$/i.test(item.type || ""); }})
      .map(function (item) {{ return item.getAsFile(); }})
      .filter(Boolean);
  }}
  async function uploadImageAsset(file) {{
    const res = await fetch("/__prototype-specs/assets/" + encodeURIComponent(pageKey), {{
      method: "POST",
      headers: {{
        "Content-Type": file.type || "application/octet-stream",
        "X-Proto-Spec-Filename": encodeURIComponent(file.name || "")
      }},
      body: file
    }});
    if (!res.ok) throw new Error(await res.text());
    return res.json();
  }}
  function insertAtSelection(editor, markdownItems) {{
    const start = Number.isFinite(editor.selectionStart) ? editor.selectionStart : editor.value.length;
    const end = Number.isFinite(editor.selectionEnd) ? editor.selectionEnd : start;
    const before = editor.value.slice(0, start);
    const after = editor.value.slice(end);
    const prefix = before && !before.endsWith("\\n") ? "\\n" : "";
    const suffix = after && !after.startsWith("\\n") ? "\\n" : "";
    const insertion = prefix + markdownItems.join("\\n") + suffix;
    editor.value = before + insertion + after;
    draft = editor.value;
  }}
  async function handleEditorPaste(event) {{
    const editor = event.target?.closest?.(".proto-spec-doc__editor");
    if (!editor) return;
    const files = pastedImageFiles(event);
    if (!files.length) return;
    event.preventDefault();
    try {{
      const markdownItems = [];
      for (const file of files) {{
        const payload = await uploadImageAsset(file);
        markdownItems.push(payload.markdown || ("![粘贴图片](" + payload.path + ")"));
      }}
      insertAtSelection(editor, markdownItems);
      status = "图片已插入，保存后生效";
    }} catch (error) {{
      status = "图片上传失败：请使用 node proto-spec-server.mjs 启动本地预览。";
    }}
    renderSpec();
  }}
  function renderSpec() {{
    const displayStatus = status || (editing && draft !== bodyMarkdown ? "未保存" : "");
    const toolbar = editing
      ? '<div class="proto-spec-doc__toolbar"><div class="proto-spec-doc__mode-toggle" role="group" aria-label="编辑模式"><button type="button" data-action="write" class="' + (editorMode === "write" ? "is-active" : "") + '">Markdown</button><button type="button" data-action="preview" class="' + (editorMode === "preview" ? "is-active" : "") + '">预览</button></div><button type="button" class="proto-spec-doc__button proto-spec-doc__button--primary" data-action="save">保存</button><button type="button" class="proto-spec-doc__button" data-action="cancel">取消</button>' + (displayStatus ? '<span class="proto-spec-doc__status">' + escapeHtml(displayStatus) + '</span>' : "") + '</div>'
      : '<div class="proto-spec-doc__toolbar"><button type="button" class="proto-spec-doc__button" data-action="edit">编辑</button>' + (displayStatus ? '<span class="proto-spec-doc__status">' + escapeHtml(displayStatus) + '</span>' : "") + '</div>';
    const content = editing && editorMode === "write"
      ? '<textarea class="proto-spec-doc__editor"></textarea>'
      : '<article class="proto-spec-doc__content">' + renderMarkdown(editing ? draft : bodyMarkdown) + '</article>';
    specPanel.innerHTML = '<div class="proto-spec-doc__inner">' + toolbar + content + '</div>';
    const editor = specPanel.querySelector(".proto-spec-doc__editor");
    if (editor) editor.value = draft;
    if (!editing) renderMermaidDiagrams();
  }}
  function escapeHtml(value) {{
    return String(value).replace(/[&<>]/g, function (ch) {{ return {{ "&": "&amp;", "<": "&lt;", ">": "&gt;" }}[ch]; }});
  }}
  function escapeAttr(value) {{
    return escapeHtml(value).replace(/"/g, "&quot;");
  }}
  function embeddedSpecMarkdown() {{
    const nodes = Array.from(document.querySelectorAll("script[data-proto-spec-markdown]"));
    const node = nodes.find(function (item) {{ return item.getAttribute("data-proto-spec-markdown") === pageKey; }});
    if (!node) return "";
    try {{
      return JSON.parse(node.textContent || "\\"\\\"");
    }} catch (error) {{
      return node.textContent || "";
    }}
  }}
  async function fetchFirstText(urls) {{
    const embedded = embeddedSpecMarkdown();
    if (embedded) return embedded;
    let lastError = null;
    for (const url of urls) {{
      try {{
        const res = await fetch(url, {{ cache: "no-store" }});
        if (res.ok) return res.text();
        lastError = new Error(url + " returned " + res.status);
      }} catch (error) {{
        lastError = error;
      }}
    }}
    throw lastError || new Error("spec not found");
  }}
  async function saveSpec() {{
    const editor = specPanel.querySelector(".proto-spec-doc__editor");
    if (editor) draft = editor.value;
    status = "保存中...";
    renderSpec();
    try {{
      const res = await fetch("/__prototype-specs/specs/" + encodeURIComponent(pageKey), {{
        method: "PUT",
        headers: {{ "Content-Type": "application/json" }},
        body: JSON.stringify({{ markdown: composeMarkdown() }})
      }});
      if (!res.ok) throw new Error(await res.text());
      bodyMarkdown = draft;
      editing = false;
      editorMode = "write";
      status = "已保存";
    }} catch (error) {{
      status = "保存失败：请使用 node proto-spec-server.mjs 启动本地预览。";
    }}
    renderSpec();
  }}
  fetchFirstText([
    "/__prototype-specs/specs/" + encodeURIComponent(pageKey),
    "/prototype-specs/current/" + encodeURIComponent(pageKey) + ".md",
    "../prototype-specs/current/" + encodeURIComponent(pageKey) + ".md"
  ]).then(function (markdown) {{
    const parsed = splitFrontmatter(markdown);
    frontmatterText = parsed.frontmatterText;
    bodyMarkdown = parsed.body;
    draft = bodyMarkdown;
    renderSpec();
  }}).catch(function (error) {{
    specPanel.setAttribute("data-spec-error", error && (error.stack || error.message || String(error)) || "unknown");
    specPanel.innerHTML = '<div class="proto-spec-doc__inner"><h1>需求说明</h1><p>读取需求说明失败。请确认已从项目根目录启动本地服务，或检查 prototype-specs/current/' + pageKey + '.md。</p></div>';
  }});
  specPanel.addEventListener("click", function (event) {{
    const button = event.target.closest("button[data-action]");
    if (!button) return;
    if (button.dataset.action === "edit") {{
      editing = true;
      editorMode = "write";
      status = "";
      renderSpec();
    }}
    if (button.dataset.action === "write" || button.dataset.action === "preview") {{
      const editor = specPanel.querySelector(".proto-spec-doc__editor");
      if (editor) draft = editor.value;
      editorMode = button.dataset.action === "preview" ? "preview" : "write";
      status = "";
      renderSpec();
    }}
    if (button.dataset.action === "cancel") {{
      editing = false;
      editorMode = "write";
      draft = bodyMarkdown;
      status = "";
      renderSpec();
    }}
    if (button.dataset.action === "save") saveSpec();
  }});
  specPanel.addEventListener("paste", function (event) {{
    handleEditorPaste(event);
  }});
  function setView(view) {{
    const showSpec = view === "spec";
    specPanel.hidden = !showSpec;
    if (viewerMode === "dual-view") productNodes.forEach(function (node) {{ node.hidden = showSpec; }});
    switcher.querySelectorAll("button").forEach(function (button) {{ button.classList.toggle("is-active", button.dataset.view === view); }});
  }}
  function clampSwitcherPosition(left, top) {{
    const rect = switcher.getBoundingClientRect();
    const margin = 8;
    return {{
      left: Math.min(Math.max(left, margin), Math.max(margin, window.innerWidth - rect.width - margin)),
      top: Math.min(Math.max(top, margin), Math.max(margin, window.innerHeight - rect.height - margin))
    }};
  }}
  let suppressClick = false;
  function enableSwitcherDrag() {{
    let drag = null;
    switcher.addEventListener("pointerdown", function (event) {{
      if (event.button !== 0) return;
      const rect = switcher.getBoundingClientRect();
      drag = {{
        pointerId: event.pointerId,
        startX: event.clientX,
        startY: event.clientY,
        left: rect.left,
        top: rect.top,
        moved: false
      }};
      switcher.setPointerCapture?.(event.pointerId);
    }});
    switcher.addEventListener("pointermove", function (event) {{
      if (!drag || event.pointerId !== drag.pointerId) return;
      const dx = event.clientX - drag.startX;
      const dy = event.clientY - drag.startY;
      if (!drag.moved && Math.hypot(dx, dy) <= 5) return;
      drag.moved = true;
      const next = clampSwitcherPosition(drag.left + dx, drag.top + dy);
      switcher.classList.add("is-dragging");
      switcher.style.left = next.left + "px";
      switcher.style.top = next.top + "px";
      switcher.style.transform = "none";
      event.preventDefault();
    }});
    function finishDrag(event) {{
      if (!drag || event.pointerId !== drag.pointerId) return;
      suppressClick = drag.moved && event.type === "pointerup";
      switcher.classList.remove("is-dragging");
      if (switcher.hasPointerCapture?.(event.pointerId)) switcher.releasePointerCapture(event.pointerId);
      drag = null;
    }}
    switcher.addEventListener("pointerup", finishDrag);
    switcher.addEventListener("pointercancel", finishDrag);
  }}
  enableSwitcherDrag();
  switcher.addEventListener("click", function (event) {{
    if (suppressClick) {{
      suppressClick = false;
      event.preventDefault();
      event.stopPropagation();
      return;
    }}
    const source = event.target instanceof Element ? event.target : switcher;
    const button = source.closest("button[data-view]")
      || document.elementFromPoint(event.clientX, event.clientY)?.closest("button[data-view]");
    if (button) setView(button.dataset.view);
  }});
}})();
</script>
<!-- proto-spec-annotator-viewer:end -->""".replace("{{", "{").replace("}}", "}").replace("__PAGE_KEY__", page_key_literal).replace("__VIEWER_MODE__", viewer_mode_literal).replace("__PROTO_SPEC_CSS__", css_literal)


def html_local_server_source() -> str:
    return """#!/usr/bin/env node
import { createServer } from "node:http";
import { promises as fs } from "node:fs";
import path from "node:path";

const root = process.cwd();
const port = Number(process.env.PORT || readArg("--port") || 8080);
const specApiPrefix = "/__prototype-specs/specs/";
const assetApiPrefix = "/__prototype-specs/assets/";
const maxAssetBytes = 10 * 1024 * 1024;
const imageTypes = new Map([
  ["image/png", "png"],
  ["image/jpeg", "jpg"],
  ["image/webp", "webp"],
  ["image/gif", "gif"],
]);

createServer(async (req, res) => {
  try {
    const url = new URL(req.url || "/", "http://localhost");
    if (url.pathname.startsWith(specApiPrefix)) {
      await handleSpecRequest(req, res, decodeURIComponent(url.pathname.slice(specApiPrefix.length)));
      return;
    }
    if (url.pathname.startsWith(assetApiPrefix)) {
      await handleAssetRequest(req, res, decodeURIComponent(url.pathname.slice(assetApiPrefix.length)));
      return;
    }
    const pathname = url.pathname === "/" ? "/index.html" : url.pathname;
    const file = path.resolve(root, "." + decodeURIComponent(pathname));
    if (!(file === root || file.startsWith(root + path.sep))) throw Object.assign(new Error("Forbidden"), { status: 403 });
    const stat = await fs.stat(file).catch(() => null);
    if (!stat?.isFile()) throw Object.assign(new Error("Not found"), { status: 404 });
    res.writeHead(200, { "Content-Type": contentType(file) });
    res.end(await readResponseFile(file));
  } catch (error) {
    res.writeHead(error.status || 500, { "Content-Type": "text/plain; charset=utf-8" });
    res.end(error.message || "Internal server error");
  }
}).listen(port, "127.0.0.1", () => {
  console.log(`ProtoSpec local server: http://127.0.0.1:${port}`);
});

function readArg(name) {
  const index = process.argv.indexOf(name);
  return index >= 0 ? process.argv[index + 1] : "";
}

async function handleSpecRequest(req, res, pageKey) {
  if ((req.method || "") === "OPTIONS") {
    res.writeHead(204, allowHeaders());
    res.end();
    return;
  }
  if ((req.method || "") === "GET") {
    await handleSpecRead(res, pageKey);
    return;
  }
  if (!["PUT", "POST", "PATCH"].includes(req.method || "")) {
    res.writeHead(405, { ...allowHeaders(), "Content-Type": "application/json; charset=utf-8" });
    res.end(JSON.stringify({ error: "Method not allowed" }));
    return;
  }
  const chunks = [];
  for await (const chunk of req) chunks.push(Buffer.isBuffer(chunk) ? chunk : Buffer.from(chunk));
  const payload = parsePayload(Buffer.concat(chunks).toString("utf-8"));
  const markdown = typeof payload === "string" ? payload : payload.markdown;
  if (!markdown || typeof markdown !== "string") throw Object.assign(new Error("markdown is required"), { status: 400 });
  await writeManualSpec(pageKey, markdown);
  res.writeHead(200, { ...allowHeaders(), "Content-Type": "application/json; charset=utf-8" });
  res.end(JSON.stringify({ ok: true, pageKey }));
}

async function handleSpecRead(res, pageKey) {
  const safeKey = safePageKey(pageKey);
  const currentFile = path.join(root, "prototype-specs", "current", safeKey + ".md");
  const markdown = await fs.readFile(currentFile, "utf-8").catch(() => "");
  if (!markdown) {
    res.writeHead(404, { ...allowHeaders(), "Content-Type": "text/plain; charset=utf-8" });
    res.end(`Spec not found: ${safeKey}`);
    return;
  }
  res.writeHead(200, { ...allowHeaders(), "Content-Type": "text/markdown; charset=utf-8" });
  res.end(markdown);
}

async function handleAssetRequest(req, res, assetPath) {
  if ((req.method || "") === "OPTIONS") {
    res.writeHead(204, allowHeaders());
    res.end();
    return;
  }
  const parts = assetPath.split("/").filter(Boolean);
  const safeKey = safePageKey(parts[0] || "");
  if ((req.method || "") === "GET") {
    const assetName = safeAssetName(parts[1] || "");
    if (!assetName) throw Object.assign(new Error("Asset not found"), { status: 404 });
    const assetFile = path.join(root, "prototype-specs", "assets", safeKey, assetName);
    const content = await fs.readFile(assetFile).catch(() => null);
    if (!content) throw Object.assign(new Error("Asset not found"), { status: 404 });
    res.writeHead(200, { ...allowHeaders(), "Content-Type": contentType(assetFile) });
    res.end(content);
    return;
  }
  if ((req.method || "") !== "POST") {
    res.writeHead(405, { ...allowHeaders(), "Content-Type": "application/json; charset=utf-8" });
    res.end(JSON.stringify({ error: "Method not allowed" }));
    return;
  }
  const mime = String(req.headers["content-type"] || "").split(";")[0].toLowerCase();
  const ext = imageTypes.get(mime);
  if (!ext) throw Object.assign(new Error("Only png, jpeg, webp, and gif images are supported"), { status: 415 });
  const body = await readRequestBody(req, maxAssetBytes);
  if (!body.length) throw Object.assign(new Error("Image body is required"), { status: 400 });
  const assetDir = path.join(root, "prototype-specs", "assets", safeKey);
  const filename = "paste-" + assetTimestamp() + "." + ext;
  await fs.mkdir(assetDir, { recursive: true });
  await fs.writeFile(path.join(assetDir, filename), body);
  const markdownPath = `../assets/${safeKey}/${filename}`;
  const urlPath = `/__prototype-specs/assets/${encodeURIComponent(safeKey)}/${encodeURIComponent(filename)}`;
  res.writeHead(200, { ...allowHeaders(), "Content-Type": "application/json; charset=utf-8" });
  res.end(JSON.stringify({ ok: true, pageKey: safeKey, path: markdownPath, url: urlPath, markdown: `![粘贴图片](${markdownPath})` }));
}

function allowHeaders() {
  return {
    "Access-Control-Allow-Origin": "*",
    "Access-Control-Allow-Methods": "GET,PUT,POST,PATCH,OPTIONS",
    "Access-Control-Allow-Headers": "Content-Type,X-Proto-Spec-Filename",
  };
}

async function readRequestBody(req, maxBytes) {
  const chunks = [];
  let total = 0;
  for await (const chunk of req) {
    const buffer = Buffer.isBuffer(chunk) ? chunk : Buffer.from(chunk);
    total += buffer.length;
    if (total > maxBytes) throw Object.assign(new Error("Image exceeds 10MB limit"), { status: 413 });
    chunks.push(buffer);
  }
  return Buffer.concat(chunks);
}

function parsePayload(raw) {
  if (!raw) return {};
  try { return JSON.parse(raw); } catch { return raw; }
}

async function readResponseFile(file) {
  const content = await fs.readFile(file);
  if (!file.endsWith(".html")) return content;
  return Buffer.from(await injectSpecFallback(file, content.toString("utf-8")), "utf-8");
}

async function injectSpecFallback(file, html) {
  if (!html.includes("data-proto-spec-annotator-viewer")) return html;
  const match = html.match(/const pageKey = "([^"]+)";/);
  if (!match) return html;
  const pageKey = safePageKey(match[1]);
  const markdown = await fs.readFile(path.join(root, "prototype-specs", "current", pageKey + ".md"), "utf-8").catch(() => "");
  if (!markdown) return html;
  const script = '<script type="application/json" data-proto-spec-markdown="' + pageKey + '">' + escapeScriptJson(JSON.stringify(markdown)) + "</script>\\n";
  return html.replace("<!-- proto-spec-annotator-viewer:start -->", script + "<!-- proto-spec-annotator-viewer:start -->");
}

function escapeScriptJson(value) {
  return value.replace(/</g, "\\\\u003c");
}

async function writeManualSpec(pageKey, markdown) {
  const safeKey = safePageKey(pageKey);
  const currentDir = path.join(root, "prototype-specs", "current");
  const historyDir = path.join(root, "prototype-specs", "history", safeKey);
  const currentFile = path.join(currentDir, safeKey + ".md");
  await fs.mkdir(currentDir, { recursive: true });
  const previous = await fs.readFile(currentFile, "utf-8").catch(() => "");
  if (previous) {
    await fs.mkdir(historyDir, { recursive: true });
    await fs.writeFile(path.join(historyDir, timestamp() + ".before-manual-save.md"), previous, "utf-8");
  }
  await fs.writeFile(currentFile, markManualEdit(markdown), "utf-8");
}

function markManualEdit(markdown) {
  const now = new Date().toISOString();
  if (!markdown.startsWith("---\\n")) return markdown;
  const end = markdown.indexOf("\\n---", 4);
  if (end === -1) return markdown;
  const frontmatter = upsertLine(upsertLine(markdown.slice(4, end), "lastManualEditedAt", JSON.stringify(now)), "sourceType", "\\"manual-edited\\"");
  return "---\\n" + frontmatter.trimEnd() + "\\n---" + markdown.slice(end + 4);
}

function upsertLine(frontmatter, key, value) {
  const pattern = new RegExp("^" + key + ":.*$", "m");
  return pattern.test(frontmatter) ? frontmatter.replace(pattern, key + ": " + value) : frontmatter.trimEnd() + "\\n" + key + ": " + value + "\\n";
}

function safePageKey(value) {
  return String(value || "").replace(/[^A-Za-z0-9_-]/g, "-") || "page-spec";
}

function safeAssetName(value) {
  return path.basename(String(value || "")).replace(/[^A-Za-z0-9._-]/g, "-").replace(/^\\.+/, "");
}

function contentType(file) {
  if (file.endsWith(".html")) return "text/html; charset=utf-8";
  if (file.endsWith(".js") || file.endsWith(".mjs")) return "text/javascript; charset=utf-8";
  if (file.endsWith(".css")) return "text/css; charset=utf-8";
  if (file.endsWith(".md")) return "text/markdown; charset=utf-8";
  if (file.endsWith(".png")) return "image/png";
  if (file.endsWith(".jpg") || file.endsWith(".jpeg")) return "image/jpeg";
  if (file.endsWith(".webp")) return "image/webp";
  if (file.endsWith(".gif")) return "image/gif";
  return "application/octet-stream";
}

function assetTimestamp() {
  return new Date().toISOString().replace(/[-:]/g, "").replace(".", "-");
}

function timestamp() {
  return new Date().toISOString().replace(/[-:]/g, "").replace(/\\.\\d+Z$/, "Z");
}
"""


def integrate_react_viewer(root: Path, pages: list[ProjectPage], args: argparse.Namespace, report: WorkflowReport) -> None:
    write_text(root / "src/page-specs/index.ts", shared_page_specs_index_source(), args.dry_run, report)
    write_text(root / "src/page-specs/route-map.ts", route_map_source(pages), args.dry_run, report)
    write_text(root / "src/components/proto-spec/PageSpecDoc.tsx", react_doc_source(), args.dry_run, report)
    write_text(root / "src/components/proto-spec/PageSpecRouteShell.tsx", react_shell_source(), args.dry_run, report)
    write_text(root / "src/components/proto-spec/proto-spec.css", proto_spec_css(), args.dry_run, report)
    write_text(root / "scripts/proto-spec-vite-plugin.mjs", vite_save_plugin_source("src/page-specs"), args.dry_run, report)
    patch_vite_config(root, "src/page-specs", args, report)
    app_file = next((candidate for candidate in REACT_APP_ENTRY_FILES if (root / candidate).exists()), "")
    if not app_file:
        report.warnings.append("未找到 React App 入口；已写入 viewer 文件但未自动接入。")
        return
    source = read_text(root / app_file) or ""
    patched = patch_react_app_source(source, app_file)
    if patched == source:
        if "<PageSpecRouteShell" in source:
            return
        report.warnings.append(f"{app_file}: 未找到 BrowserRouter 或 Routes 锚点；已跳过自动接入。")
        return
    write_text(root / app_file, patched, args.dry_run, report)


def patch_react_app_source(source: str, app_file: str) -> str:
    if "<PageSpecRouteShell" in source:
        return source
    import_path = relative_import_path(app_file, "src/components/proto-spec/PageSpecRouteShell")
    next_source = insert_import(source, f'import {{ PageSpecRouteShell }} from "{import_path}";')
    match = re.search(r"<BrowserRouter\b[^>]*>", next_source)
    close = next_source.rfind("</BrowserRouter>")
    if match and close >= 0:
        return next_source[: match.end()] + "\n      <PageSpecRouteShell>" + next_source[match.end() : close] + "\n      </PageSpecRouteShell>\n    " + next_source[close:]
    match = re.search(r"<Routes\b[^>]*>", next_source)
    close = next_source.rfind("</Routes>")
    if match and close >= 0:
        block = next_source[match.start() : close + len("</Routes>")]
        return next_source[: match.start()] + "<PageSpecRouteShell>\n      " + block + "\n    </PageSpecRouteShell>" + next_source[close + len("</Routes>") :]
    return source


def insert_import(source: str, statement: str) -> str:
    if statement in source:
        return source
    matches = list(re.finditer(r"^import[\s\S]*?;\s*$", source, re.M))
    if not matches:
        return statement + "\n" + source
    index = matches[-1].end()
    return source[:index] + "\n" + statement + source[index:]


def relative_import_path(importer_file: str, target_file: str) -> str:
    importer_dir = Path(importer_file).parent
    relative = os.path.relpath(target_file, "." if str(importer_dir) == "." else str(importer_dir)).replace("\\", "/")
    return relative if relative.startswith(".") else "./" + relative


def patch_vite_config(root: Path, spec_root_relative: str, args: argparse.Namespace, report: WorkflowReport) -> None:
    config_file = next((candidate for candidate in VITE_CONFIG_FILES if (root / candidate).exists()), "")
    if not config_file:
        report.warnings.append("未找到 Vite 配置文件；编辑保存 API 已生成插件但未自动接入。")
        return
    source = read_text(root / config_file) or ""
    patched = patch_vite_config_source(source, config_file, spec_root_relative)
    if patched == source:
        if "protoSpecPlugin" in source:
            return
        report.warnings.append(f"{config_file}: 未找到 plugins 数组；编辑保存 API 插件未自动接入。")
        return
    write_text(root / config_file, patched, args.dry_run, report)


def patch_vite_config_source(source: str, config_file: str, spec_root_relative: str) -> str:
    next_source = insert_import(source, f'import protoSpecPlugin from "{relative_import_path(config_file, "scripts/proto-spec-vite-plugin.mjs")}";')
    if "protoSpecPlugin(" in next_source:
        return next_source
    plugin_call = f'protoSpecPlugin({{ specRoot: "{spec_root_relative}" }}), '
    return re.sub(r"plugins\s*:\s*\[", lambda match: match.group(0) + plugin_call, next_source, count=1)


def vite_save_plugin_source(default_spec_root: str) -> str:
    return f"""import {{ promises as fs }} from "node:fs";
import path from "node:path";

export default function protoSpecPlugin(options = {{}}) {{
  const specRoot = options.specRoot || "{default_spec_root}";
  const maxAssetBytes = 10 * 1024 * 1024;
  const imageTypes = new Map([
    ["image/png", "png"],
    ["image/jpeg", "jpg"],
    ["image/webp", "webp"],
    ["image/gif", "gif"],
  ]);
  return {{
    name: "prototype-spec-annotator-save-api",
    configureServer(server) {{
      server.middlewares.use(async (req, res, next) => {{
        try {{
          const url = new URL(req.url || "/", "http://localhost");
          const specPrefix = "/__prototype-specs/specs/";
          const assetPrefix = "/__prototype-specs/assets/";
          if (url.pathname.startsWith(assetPrefix)) {{
            await handleAssetRequest(server.config.root || process.cwd(), specRoot, req, res, decodeURIComponent(url.pathname.slice(assetPrefix.length)), imageTypes, maxAssetBytes);
            return;
          }}
          if (!url.pathname.startsWith(specPrefix)) return next();
          if (req.method === "OPTIONS") {{
            res.writeHead(204, allowHeaders());
            res.end();
            return;
          }}
          if (!["PUT", "POST", "PATCH"].includes(req.method || "")) {{
            res.writeHead(405, {{ ...allowHeaders(), "Content-Type": "application/json; charset=utf-8" }});
            res.end(JSON.stringify({{ error: "Method not allowed" }}));
            return;
          }}
          const pageKey = decodeURIComponent(url.pathname.slice(specPrefix.length));
          const payload = await readJsonBody(req);
          const markdown = typeof payload === "string" ? payload : payload?.markdown;
          if (!markdown || typeof markdown !== "string") throw Object.assign(new Error("markdown is required"), {{ status: 400 }});
          await writeManualSpec(server.config.root || process.cwd(), specRoot, pageKey, markdown);
          res.writeHead(200, {{ ...allowHeaders(), "Content-Type": "application/json; charset=utf-8" }});
          res.end(JSON.stringify({{ ok: true, pageKey: safePageKey(pageKey) }}));
        }} catch (error) {{
          res.writeHead(error.status || 500, {{ ...allowHeaders(), "Content-Type": "application/json; charset=utf-8" }});
          res.end(JSON.stringify({{ error: error.message || "Internal server error" }}));
        }}
      }});
    }},
  }};
}}

function allowHeaders() {{
  return {{
    "Access-Control-Allow-Origin": "*",
    "Access-Control-Allow-Methods": "GET,PUT,POST,PATCH,OPTIONS",
    "Access-Control-Allow-Headers": "Content-Type,X-Proto-Spec-Filename",
  }};
}}

async function readJsonBody(req) {{
  const chunks = [];
  for await (const chunk of req) chunks.push(Buffer.isBuffer(chunk) ? chunk : Buffer.from(chunk));
  const raw = Buffer.concat(chunks).toString("utf-8");
  if (!raw) return {{}};
  try {{ return JSON.parse(raw); }} catch {{ return raw; }}
}}

async function handleAssetRequest(root, specRoot, req, res, assetPath, imageTypes, maxAssetBytes) {{
  if (req.method === "OPTIONS") {{
    res.writeHead(204, allowHeaders());
    res.end();
    return;
  }}
  const parts = assetPath.split("/").filter(Boolean);
  const safeKey = safePageKey(parts[0] || "");
  if (req.method === "GET") {{
    const assetName = safeAssetName(parts[1] || "");
    if (!assetName) throw Object.assign(new Error("Asset not found"), {{ status: 404 }});
    const assetFile = path.resolve(root, specRoot, "assets", safeKey, assetName);
    const content = await fs.readFile(assetFile).catch(() => null);
    if (!content) throw Object.assign(new Error("Asset not found"), {{ status: 404 }});
    res.writeHead(200, {{ ...allowHeaders(), "Content-Type": imageContentType(assetName) }});
    res.end(content);
    return;
  }}
  if (req.method !== "POST") {{
    res.writeHead(405, {{ ...allowHeaders(), "Content-Type": "application/json; charset=utf-8" }});
    res.end(JSON.stringify({{ error: "Method not allowed" }}));
    return;
  }}
  const mime = String(req.headers["content-type"] || "").split(";")[0].toLowerCase();
  const ext = imageTypes.get(mime);
  if (!ext) throw Object.assign(new Error("Only png, jpeg, webp, and gif images are supported"), {{ status: 415 }});
  const body = await readRawBody(req, maxAssetBytes);
  if (!body.length) throw Object.assign(new Error("Image body is required"), {{ status: 400 }});
  const assetDir = path.resolve(root, specRoot, "assets", safeKey);
  const filename = "paste-" + assetTimestamp() + "." + ext;
  await fs.mkdir(assetDir, {{ recursive: true }});
  await fs.writeFile(path.join(assetDir, filename), body);
  const markdownPath = `../assets/${{safeKey}}/${{filename}}`;
  const urlPath = `/__prototype-specs/assets/${{encodeURIComponent(safeKey)}}/${{encodeURIComponent(filename)}}`;
  res.writeHead(200, {{ ...allowHeaders(), "Content-Type": "application/json; charset=utf-8" }});
  res.end(JSON.stringify({{ ok: true, pageKey: safeKey, path: markdownPath, url: urlPath, markdown: `![粘贴图片](${{markdownPath}})` }}));
}}

async function readRawBody(req, maxBytes) {{
  const chunks = [];
  let total = 0;
  for await (const chunk of req) {{
    const buffer = Buffer.isBuffer(chunk) ? chunk : Buffer.from(chunk);
    total += buffer.length;
    if (total > maxBytes) throw Object.assign(new Error("Image exceeds 10MB limit"), {{ status: 413 }});
    chunks.push(buffer);
  }}
  return Buffer.concat(chunks);
}}

async function writeManualSpec(root, specRoot, pageKey, markdown) {{
  const safeKey = safePageKey(pageKey);
  const currentDir = path.resolve(root, specRoot, "current");
  const historyDir = path.resolve(root, specRoot, "history", safeKey);
  const currentFile = path.join(currentDir, safeKey + ".md");
  await fs.mkdir(currentDir, {{ recursive: true }});
  const previous = await fs.readFile(currentFile, "utf-8").catch(() => "");
  if (previous) {{
    await fs.mkdir(historyDir, {{ recursive: true }});
    await fs.writeFile(path.join(historyDir, timestamp() + ".before-manual-save.md"), previous, "utf-8");
  }}
  await fs.writeFile(currentFile, markManualEdit(markdown), "utf-8");
}}

function markManualEdit(markdown) {{
  const now = new Date().toISOString();
  if (!markdown.startsWith("---\\n")) return markdown;
  const end = markdown.indexOf("\\n---", 4);
  if (end === -1) return markdown;
  const frontmatter = upsertLine(upsertLine(markdown.slice(4, end), "lastManualEditedAt", JSON.stringify(now)), "sourceType", "\\"manual-edited\\"");
  return "---\\n" + frontmatter.trimEnd() + "\\n---" + markdown.slice(end + 4);
}}

function upsertLine(frontmatter, key, value) {{
  const pattern = new RegExp("^" + key + ":.*$", "m");
  return pattern.test(frontmatter) ? frontmatter.replace(pattern, key + ": " + value) : frontmatter.trimEnd() + "\\n" + key + ": " + value + "\\n";
}}

function safePageKey(value) {{
  return String(value || "").replace(/[^A-Za-z0-9_-]/g, "-") || "page-spec";
}}

function safeAssetName(value) {{
  return path.basename(String(value || "")).replace(/[^A-Za-z0-9._-]/g, "-").replace(/^\\.+/, "");
}}

function imageContentType(file) {{
  if (file.endsWith(".png")) return "image/png";
  if (file.endsWith(".jpg") || file.endsWith(".jpeg")) return "image/jpeg";
  if (file.endsWith(".webp")) return "image/webp";
  if (file.endsWith(".gif")) return "image/gif";
  return "application/octet-stream";
}}

function assetTimestamp() {{
  return new Date().toISOString().replace(/[-:]/g, "").replace(".", "-");
}}

function timestamp() {{
  return new Date().toISOString().replace(/[-:]/g, "").replace(/\\.\\d+Z$/, "Z");
}}
"""


def integrate_vue_viewer(root: Path, pages: list[ProjectPage], args: argparse.Namespace, report: WorkflowReport) -> None:
    write_text(root / "src/page-specs/index.ts", shared_page_specs_index_source(), args.dry_run, report)
    write_text(root / "src/page-specs/route-map.ts", route_map_source(pages), args.dry_run, report)
    write_text(root / "src/components/proto-spec/PageSpecDoc.vue", vue_doc_source(), args.dry_run, report)
    write_text(root / "src/components/proto-spec/PageSpecRouteShell.vue", vue_shell_source(), args.dry_run, report)
    write_text(root / "src/components/proto-spec/proto-spec.css", proto_spec_css(), args.dry_run, report)
    write_text(root / "scripts/proto-spec-vite-plugin.mjs", vite_save_plugin_source("src/page-specs"), args.dry_run, report)
    patch_vite_config(root, "src/page-specs", args, report)
    app_file = next((candidate for candidate in VUE_APP_ENTRY_FILES if (root / candidate).exists()), "")
    if not app_file:
        report.warnings.append("未找到 Vue App 入口；已写入 viewer 文件但未自动接入。")
        return
    source = read_text(root / app_file) or ""
    patched = patch_vue_app_source(source, app_file)
    if patched == source:
        if "<PageSpecRouteShell" in source:
            return
        report.warnings.append(f"{app_file}: 未找到 router-view / RouterView 锚点；已跳过自动接入。")
        return
    write_text(root / app_file, patched, args.dry_run, report)


def patch_vue_app_source(source: str, app_file: str) -> str:
    source = harmonize_vue_script_setup_language(source)
    if "<PageSpecRouteShell" in source:
        return source
    import_path = relative_import_path(app_file, "src/components/proto-spec/PageSpecRouteShell.vue")
    next_source = insert_vue_import(source, f'import PageSpecRouteShell from "{import_path}";')
    match = re.search(r"<(?:router-view|RouterView)\b[^>]*/>|<(router-view|RouterView)\b[^>]*>[\s\S]*?</(?:router-view|RouterView)>", next_source, re.I)
    if not match:
        return source
    return next_source[: match.start()] + "<PageSpecRouteShell>\n    " + match.group(0) + "\n  </PageSpecRouteShell>" + next_source[match.end() :]


def insert_vue_import(source: str, statement: str) -> str:
    source = harmonize_vue_script_setup_language(source)
    if statement in source:
        return source
    setup_match = re.search(r"<script\b[^>]*\bsetup\b[^>]*>", source, re.I)
    if setup_match:
        return source[: setup_match.end()] + "\n" + statement + source[setup_match.end() :]
    return f"{vue_setup_script_open_tag(source)}\n{statement}\n</script>\n\n" + source


def vue_script_lang(attrs: str) -> str | None:
    match = re.search(r"\blang\s*=\s*[\"']([^\"']+)[\"']", attrs, re.I)
    return match.group(1) if match else None


def vue_setup_script_open_tag(source: str) -> str:
    normal_match = re.search(r"<script\b(?![^>]*\bsetup\b)(?P<attrs>[^>]*)>", source, re.I)
    normal_lang = vue_script_lang(normal_match.group("attrs")) if normal_match else "ts"
    return f'<script setup lang="{normal_lang}">' if normal_lang else "<script setup>"


def harmonize_vue_script_setup_language(source: str) -> str:
    setup_match = re.search(r"<script\b(?P<attrs>[^>]*)\bsetup\b(?P<attrs_after>[^>]*)>", source, re.I)
    normal_match = re.search(r"<script\b(?![^>]*\bsetup\b)(?P<attrs>[^>]*)>", source, re.I)
    if not setup_match or not normal_match:
        return source
    setup_attrs = f"{setup_match.group('attrs')} {setup_match.group('attrs_after')}"
    setup_lang = vue_script_lang(setup_attrs)
    normal_lang = vue_script_lang(normal_match.group("attrs"))
    if setup_lang == normal_lang:
        return source
    if normal_lang:
        replacement = re.sub(r"\s+lang\s*=\s*[\"'][^\"']+[\"']", "", setup_match.group(0), flags=re.I)
        replacement = replacement[:-1] + f' lang="{normal_lang}">'
    else:
        replacement = re.sub(r"\s+lang\s*=\s*[\"'][^\"']+[\"']", "", setup_match.group(0), flags=re.I)
    return source[: setup_match.start()] + replacement + source[setup_match.end() :]


def route_map_source(pages: list[ProjectPage]) -> str:
    entries = "\n".join(f'  {{ pattern: "{normalize_route_pattern(page.routeHint or "/" + page.pageKey)}", pageKey: "{page.pageKey}" }},' for page in pages)
    return "export const PAGE_SPEC_ROUTE_MAP = [\n" + entries + "\n];\n"


def shared_page_specs_index_source() -> str:
    return """export interface PageSpec {
  pageKey: string;
  version: number;
  pageName: string;
  pageType: string;
  pageShape: string;
  summary: string;
  markdown?: string;
  frontmatterText?: string;
  rawMarkdown?: string;
  storageFormat?: "markdown" | "json";
  meta?: Record<string, unknown>;
}

const markdownModules = import.meta.glob("./current/*.md", { query: "?raw", eager: true, import: "default" }) as Record<string, string>;
const viewerConfigModules = import.meta.glob("./viewer-config.json", { eager: true, import: "default" }) as Record<string, Record<string, unknown>>;

export const pageSpecs: Record<string, PageSpec> = Object.fromEntries(
  Object.entries(markdownModules).map(([modulePath, markdown]) => {
    const pageKey = modulePath.replace(/^\\.\\/current\\//, "").replace(/\\.md$/, "");
    return [pageKey, parseMarkdownSpec(markdown, pageKey)];
  })
);

export function getPageSpec(pageKey: string): PageSpec | null {
  return pageSpecs[pageKey] ?? null;
}

export function getViewerConfig(): Record<string, unknown> {
  return Object.values(viewerConfigModules)[0] ?? { visibilityMode: "manual-toggle", viewerMode: "dual-view" };
}

function parseMarkdownSpec(rawMarkdown: string, fallbackPageKey: string): PageSpec {
  const { frontmatter, frontmatterText, body } = splitFrontmatter(rawMarkdown);
  return {
    pageKey: String(frontmatter.pageKey || fallbackPageKey),
    version: Number(frontmatter.version || 1),
    pageName: String(frontmatter.pageName || firstHeading(body) || fallbackPageKey),
    pageType: String(frontmatter.pageType || "页面"),
    pageShape: String(frontmatter.pageShape || "桌面端页面"),
    summary: extractSummary(body),
    markdown: body,
    frontmatterText,
    rawMarkdown,
    storageFormat: "markdown",
    meta: frontmatter,
  };
}

function splitFrontmatter(rawMarkdown: string): { frontmatter: Record<string, unknown>; frontmatterText: string; body: string } {
  if (!rawMarkdown.startsWith("---\\n")) return { frontmatter: {}, frontmatterText: "", body: rawMarkdown.trim() };
  const end = rawMarkdown.indexOf("\\n---", 4);
  if (end === -1) return { frontmatter: {}, frontmatterText: "", body: rawMarkdown.trim() };
  const frontmatterText = rawMarkdown.slice(4, end);
  const frontmatter = Object.fromEntries(frontmatterText.split(/\\r?\\n/).map((line) => {
    const index = line.indexOf(":");
    if (index === -1) return null;
    return [line.slice(0, index).trim(), parseFrontmatterValue(line.slice(index + 1).trim())];
  }).filter(Boolean) as Array<[string, unknown]>);
  return { frontmatter, frontmatterText, body: rawMarkdown.slice(end + 4).replace(/^\\s*\\n/, "").trim() };
}

function parseFrontmatterValue(value: string): unknown {
  if (value === "true") return true;
  if (value === "false") return false;
  if (value === "null") return null;
  if (/^-?\\d+(\\.\\d+)?$/.test(value)) return Number(value);
  if ((value.startsWith('"') && value.endsWith('"')) || (value.startsWith("'") && value.endsWith("'"))) {
    try { return JSON.parse(value); } catch { return value.slice(1, -1); }
  }
  return value;
}

function firstHeading(markdown: string): string | null {
  return markdown.match(/^#\\s+(.+)$/m)?.[1]?.trim() || null;
}

function extractSummary(markdown: string): string {
  return (markdown.match(/^##\\s+页面摘要\\s*$([\\s\\S]*?)(?=^##\\s+|$)/m)?.[1] ?? "").replace(/^\\s*(?:[-*+]|\\d+[.)])\\s+/gm, "").trim();
}
"""


def react_doc_source() -> str:
    return """import { useEffect, useMemo, useState } from "react";
import type { ClipboardEvent } from "react";
import type { PageSpec } from "../../page-specs";
import "./proto-spec.css";

export function PageSpecDoc({ spec }: { spec: PageSpec }) {
  const [editing, setEditing] = useState(false);
  const [editorMode, setEditorMode] = useState<"write" | "preview">("write");
  const [draft, setDraft] = useState(spec.markdown || "");
  const [savedMarkdown, setSavedMarkdown] = useState(spec.markdown || "");
  const [status, setStatus] = useState("");
  useEffect(() => {
    setEditing(false);
    setEditorMode("write");
    setDraft(spec.markdown || "");
    setSavedMarkdown(spec.markdown || "");
    setStatus("");
  }, [spec.pageKey, spec.markdown]);
  const html = useMemo(() => renderMarkdown(editing && editorMode === "preview" ? draft : savedMarkdown, spec.pageKey), [draft, editing, editorMode, savedMarkdown, spec.pageKey]);
  const displayStatus = status || (editing && draft !== savedMarkdown ? "未保存" : "");
  useEffect(() => {
    if (!editing || editorMode === "preview") renderMermaidDiagrams();
  }, [editing, editorMode, html]);
  async function handlePaste(event: ClipboardEvent<HTMLTextAreaElement>) {
    const files = pastedImageFiles(event.clipboardData);
    if (!files.length) return;
    event.preventDefault();
    const editor = event.currentTarget;
    setStatus("正在上传图片...");
    try {
      const markdownItems: string[] = [];
      for (const file of files) {
        const payload = await uploadImageAsset(spec.pageKey, file);
        markdownItems.push(payload.markdown || `![粘贴图片](${payload.path})`);
      }
      setDraft(insertAtSelection(editor.value, editor.selectionStart, editor.selectionEnd, markdownItems));
      setStatus("图片已插入，保存后生效");
    } catch {
      setStatus("图片上传失败：请确认正在使用已接入 protoSpecPlugin 的 Vite 开发服务。");
    }
  }
  async function save() {
    setStatus("保存中...");
    try {
      const res = await fetch(`/__prototype-specs/specs/${encodeURIComponent(spec.pageKey)}`, {
        method: "PUT",
        headers: { "Content-Type": "application/json" },
        body: JSON.stringify({ ...spec, markdown: composeMarkdownSpec(spec, draft) }),
      });
      if (!res.ok) throw new Error(await res.text());
      setSavedMarkdown(draft);
      setEditing(false);
      setEditorMode("write");
      setStatus("已保存");
    } catch (error) {
      setStatus("保存失败：请确认正在使用已接入 protoSpecPlugin 的 Vite 开发服务。");
    }
  }
  return <main className="proto-spec-doc"><div className="proto-spec-doc__inner">
    <header><p className="proto-spec-doc__eyebrow">PAGE SPEC</p><h1>{spec.pageName}</h1><p>{spec.summary}</p></header>
    <div className="proto-spec-doc__toolbar">{!editing ? <button type="button" className="proto-spec-doc__button" onClick={() => { setEditing(true); setEditorMode("write"); setStatus(""); }}>编辑</button> : <><div className="proto-spec-doc__mode-toggle" role="group" aria-label="编辑模式"><button type="button" className={editorMode === "write" ? "is-active" : ""} onClick={() => setEditorMode("write")}>Markdown</button><button type="button" className={editorMode === "preview" ? "is-active" : ""} onClick={() => setEditorMode("preview")}>预览</button></div><button type="button" className="proto-spec-doc__button proto-spec-doc__button--primary" onClick={save}>保存</button><button type="button" className="proto-spec-doc__button" onClick={() => { setDraft(savedMarkdown); setEditing(false); setEditorMode("write"); setStatus(""); }}>取消</button></>}{displayStatus && <span className="proto-spec-doc__status">{displayStatus}</span>}</div>
    {editing && editorMode === "write" ? <textarea className="proto-spec-doc__editor" value={draft} onChange={(event) => setDraft(event.target.value)} onPaste={handlePaste} /> : <article className="proto-spec-doc__content" dangerouslySetInnerHTML={{ __html: html }} />}
  </div></main>;
}

function composeMarkdownSpec(spec: PageSpec, body: string): string {
  return spec.frontmatterText ? `---\\n${spec.frontmatterText}\\n---\\n\\n${body.trim()}\\n` : body.trim() + "\\n";
}

function pastedImageFiles(data: DataTransfer): File[] {
  return Array.from(data.items)
    .filter((item) => item.kind === "file" && /^image\\/(png|jpe?g|webp|gif)$/i.test(item.type || ""))
    .map((item) => item.getAsFile())
    .filter((file): file is File => Boolean(file));
}

async function uploadImageAsset(pageKey: string, file: File): Promise<{ path: string; markdown: string }> {
  const res = await fetch(`/__prototype-specs/assets/${encodeURIComponent(pageKey)}`, {
    method: "POST",
    headers: {
      "Content-Type": file.type || "application/octet-stream",
      "X-Proto-Spec-Filename": encodeURIComponent(file.name || ""),
    },
    body: file,
  });
  if (!res.ok) throw new Error(await res.text());
  return res.json();
}

function insertAtSelection(value: string, selectionStart: number, selectionEnd: number, markdownItems: string[]): string {
  const start = Number.isFinite(selectionStart) ? selectionStart : value.length;
  const end = Number.isFinite(selectionEnd) ? selectionEnd : start;
  const before = value.slice(0, start);
  const after = value.slice(end);
  const prefix = before && !before.endsWith("\\n") ? "\\n" : "";
  const suffix = after && !after.startsWith("\\n") ? "\\n" : "";
  return before + prefix + markdownItems.join("\\n") + suffix + after;
}

function renderMarkdown(markdown: string, pageKey = ""): string {
  const lines = markdown.replace(/\\r\\n/g, "\\n").split("\\n");
  const out: string[] = [];
  let paragraph: string[] = [];
  function flushParagraph() {
    if (!paragraph.length) return;
    out.push("<p>" + paragraph.map((item) => renderInline(item, pageKey)).join("<br>") + "</p>");
    paragraph = [];
  }
  for (let index = 0; index < lines.length; index += 1) {
    const line = lines[index] || "";
    const trimmed = line.trim();
    const fence = trimmed.match(/^```\\s*([A-Za-z0-9_-]*)\\s*$/);
    if (fence) {
      flushParagraph();
      const lang = (fence[1] || "").toLowerCase();
      const code: string[] = [];
      index += 1;
      while (index < lines.length && !String(lines[index]).trim().startsWith("```")) {
        code.push(lines[index] || "");
        index += 1;
      }
      const codeText = code.join("\\n");
      out.push(lang === "mermaid"
        ? `<figure class="proto-spec-mermaid" data-mermaid="${escapeAttr(codeText)}"><figcaption>Mermaid</figcaption><pre><code>${escapeHtml(codeText)}</code></pre></figure>`
        : `<pre><code>${escapeHtml(codeText)}</code></pre>`);
      continue;
    }
    if (!trimmed) {
      flushParagraph();
      continue;
    }
    const heading = trimmed.match(/^(#{1,4})\\s+(.+)$/);
    if (heading) {
      flushParagraph();
      out.push(`<h${heading[1].length}>${renderInline(heading[2], pageKey)}</h${heading[1].length}>`);
      continue;
    }
    if (isQuoteStart(trimmed)) {
      flushParagraph();
      const quote = renderQuoteBlock(lines, index, pageKey);
      out.push(quote.html);
      index = quote.index - 1;
      continue;
    }
    if (isTableStart(lines, index)) {
      flushParagraph();
      const headers = parseTableRow(lines[index] || "");
      index += 2;
      const rows: string[][] = [];
      while (index < lines.length && String(lines[index]).trim().startsWith("|")) {
        rows.push(parseTableRow(lines[index] || ""));
        index += 1;
      }
      index -= 1;
      out.push(renderTable(headers, rows, pageKey));
      continue;
    }
    if (parseListItem(line)) {
      flushParagraph();
      const list = renderListBlock(lines, index, pageKey);
      out.push(list.html);
      index = list.index - 1;
      continue;
    }
    paragraph.push(line);
  }
  flushParagraph();
  return out.join("");
}

function isQuoteStart(trimmed: string): boolean {
  return /^>\\s?/.test(trimmed);
}

function renderQuoteBlock(lines: string[], start: number, pageKey = ""): { html: string; index: number } {
  const quoteLines: string[] = [];
  let index = start;
  while (index < lines.length) {
    const line = lines[index] || "";
    if (!line.trim()) {
      quoteLines.push("");
      index += 1;
      continue;
    }
    const quote = line.match(/^\\s*>\\s?(.*)$/);
    if (!quote) break;
    quoteLines.push(quote[1] || "");
    index += 1;
  }
  const callout = quoteLines[0]?.match(/^\\[!(NOTE|TIP|IMPORTANT|WARNING|CAUTION|TODO|INFO|RISK)\\]\\s*(.*)$/i);
  if (callout) {
    const type = callout[1].toLowerCase();
    const title = callout[2] || calloutLabel(type);
    const body = quoteLines.slice(1).join("\\n").trim();
    return {
      html: `<blockquote class="proto-spec-callout proto-spec-callout--${escapeAttr(type)}"><p class="proto-spec-callout__title">${renderInline(title, pageKey)}</p>${body ? renderMarkdown(body, pageKey) : ""}</blockquote>`,
      index,
    };
  }
  return { html: `<blockquote>${renderMarkdown(quoteLines.join("\\n").trim(), pageKey)}</blockquote>`, index };
}

function calloutLabel(type: string): string {
  return ({ note: "说明", tip: "建议", important: "重要", warning: "警告", caution: "注意", todo: "待办", info: "信息", risk: "风险" } as Record<string, string>)[type] || "说明";
}

type ListItem = { indent: number; ordered: boolean; task: boolean; checked: boolean; text: string };

function parseListItem(line: string): ListItem | null {
  const match = String(line || "").match(/^(\\s*)([-*+]|\\d+[.)])\\s+(?:\\[( |x|X)\\]\\s+)?(.+)$/);
  if (!match) return null;
  return {
    indent: match[1].replace(/\\t/g, "    ").length,
    ordered: /^\\d/.test(match[2]),
    task: match[3] !== undefined,
    checked: /x/i.test(match[3] || ""),
    text: match[4],
  };
}

function renderListBlock(lines: string[], start: number, pageKey = ""): { html: string; index: number } {
  const first = parseListItem(lines[start] || "");
  if (!first) return { html: "", index: start + 1 };
  const tag = first.ordered ? "ol" : "ul";
  const items: string[] = [];
  let index = start;
  while (index < lines.length) {
    const item = parseListItem(lines[index] || "");
    if (!item || item.indent !== first.indent || item.ordered !== first.ordered) break;
    let content = (item.task ? renderTaskCheckbox(item.checked) : "") + renderInline(item.text, pageKey);
    index += 1;
    while (index < lines.length) {
      const next = parseListItem(lines[index] || "");
      const raw = lines[index] || "";
      if (!raw.trim()) {
        index += 1;
        continue;
      }
      if (next && next.indent > first.indent) {
        const nested = renderListBlock(lines, index, pageKey);
        content += nested.html;
        index = nested.index;
        continue;
      }
      if (next && next.indent <= first.indent) break;
      const continuationIndent = (raw.match(/^\\s*/)?.[0] || "").replace(/\\t/g, "    ").length;
      if (continuationIndent > first.indent) {
        content += "<br>" + renderInline(raw.trim(), pageKey);
        index += 1;
        continue;
      }
      break;
    }
    items.push(`<li>${content}</li>`);
  }
  return { html: `<${tag}>${items.join("")}</${tag}>`, index };
}

function renderTaskCheckbox(checked: boolean): string {
  return `<input class="proto-spec-task-checkbox" type="checkbox" disabled${checked ? " checked" : ""} aria-label="${checked ? "已完成" : "未完成"}">`;
}

function isTableStart(lines: string[], index: number): boolean {
  return Boolean(lines[index]?.trim().startsWith("|") && lines[index + 1]?.trim().startsWith("|") && parseTableRow(lines[index + 1] || "").every((cell) => /^:?-{3,}:?$/.test(cell)));
}

function parseTableRow(line: string): string[] {
  return line.trim().replace(/^\\||\\|$/g, "").split("|").map((cell) => cell.trim());
}

function renderTable(headers: string[], rows: string[][], pageKey = ""): string {
  return "<table><thead><tr>" + headers.map((cell) => `<th>${renderInline(cell, pageKey)}</th>`).join("") + "</tr></thead><tbody>" + rows.map((row) => "<tr>" + headers.map((_header, index) => `<td>${renderInline(row[index] || "", pageKey)}</td>`).join("") + "</tr>").join("") + "</tbody></table>";
}

function resolveImageSrc(src: string, pageKey: string): string {
  if (/^(?:https?:|data:|blob:|\\/)/i.test(src)) return src;
  const assetPrefix = `../assets/${pageKey}/`;
  if (pageKey && src.startsWith(assetPrefix)) {
    return `/__prototype-specs/assets/${encodeURIComponent(pageKey)}/${src.slice(assetPrefix.length).split("/").map(encodeURIComponent).join("/")}`;
  }
  return src;
}

function renderInline(value: string, pageKey = ""): string {
  let output = "";
  let cursor = 0;
  const pattern = /!\\[([^\\]]*)\\]\\(([^)\\s]+)(?:\\s+"([^"]*)")?\\)|\\[([^\\]]+)\\]\\(([^)\\s]+)\\)|`([^`]+)`|\\*\\*([^*]+)\\*\\*|==([^=]+)==/g;
  let match: RegExpExecArray | null;
  while ((match = pattern.exec(value)) !== null) {
    output += escapeHtml(value.slice(cursor, match.index));
    if (match[1] !== undefined) output += `<img src="${escapeAttr(resolveImageSrc(match[2], pageKey))}" alt="${escapeAttr(match[1])}"${match[3] ? ` title="${escapeAttr(match[3])}"` : ""}>`;
    else if (match[4] !== undefined) output += `<a href="${escapeAttr(match[5])}" target="_blank" rel="noreferrer">${escapeHtml(match[4])}</a>`;
    else if (match[6] !== undefined) output += `<code>${escapeHtml(match[6])}</code>`;
    else if (match[7] !== undefined) output += `<strong>${escapeHtml(match[7])}</strong>`;
    else if (match[8] !== undefined) output += `<mark>${escapeHtml(match[8])}</mark>`;
    cursor = match.index + match[0].length;
  }
  return output + escapeHtml(value.slice(cursor));
}

type MermaidApi = { initialize?: (options: Record<string, unknown>) => void; render: (id: string, code: string) => Promise<{ svg?: string }> };
type ProtoSpecWindow = Window & typeof globalThis & { mermaid?: MermaidApi; __protoSpecMermaidPromise?: Promise<MermaidApi>; __protoSpecMermaidInitialized?: boolean };

function loadMermaid(): Promise<MermaidApi> {
  const protoWindow = window as ProtoSpecWindow;
  if (protoWindow.mermaid?.render) {
    initializeMermaid(protoWindow.mermaid);
    return Promise.resolve(protoWindow.mermaid);
  }
  if (protoWindow.__protoSpecMermaidPromise) return protoWindow.__protoSpecMermaidPromise;
  protoWindow.__protoSpecMermaidPromise = new Promise((resolve, reject) => {
    const existing = document.querySelector<HTMLScriptElement>("script[data-proto-spec-mermaid]");
    if (existing) {
      existing.addEventListener("load", () => {
        if (protoWindow.mermaid?.render) {
          initializeMermaid(protoWindow.mermaid);
          resolve(protoWindow.mermaid);
        } else {
          reject(new Error("Mermaid failed to initialize."));
        }
      }, { once: true });
      existing.addEventListener("error", reject, { once: true });
      return;
    }
    const script = document.createElement("script");
    script.src = "https://cdn.jsdelivr.net/npm/mermaid@10/dist/mermaid.min.js";
    script.async = true;
    script.dataset.protoSpecMermaid = "true";
    script.onload = () => {
      if (protoWindow.mermaid?.render) {
        initializeMermaid(protoWindow.mermaid);
        resolve(protoWindow.mermaid);
      } else {
        reject(new Error("Mermaid failed to initialize."));
      }
    };
    script.onerror = reject;
    document.head.appendChild(script);
  });
  return protoWindow.__protoSpecMermaidPromise;
}

function initializeMermaid(mermaid: MermaidApi): void {
  const protoWindow = window as ProtoSpecWindow;
  if (protoWindow.__protoSpecMermaidInitialized) return;
  if (mermaid.initialize) mermaid.initialize({ startOnLoad: false, securityLevel: "strict" });
  protoWindow.__protoSpecMermaidInitialized = true;
}

function renderMermaidDiagrams(): void {
  const nodes = Array.from(document.querySelectorAll<HTMLElement>(".proto-spec-mermaid[data-mermaid]:not([data-rendered])"));
  if (!nodes.length) return;
  nodes.forEach((node) => { node.dataset.rendered = "loading"; });
  void loadMermaid().then((mermaid) => {
    nodes.forEach((node, index) => {
      const code = node.dataset.mermaid || "";
      void mermaid.render(`proto-spec-mermaid-${index}-${Date.now()}`, code).then((result) => {
        node.dataset.rendered = "true";
        if (result.svg) node.innerHTML = result.svg;
      }).catch(() => {
        node.dataset.rendered = "failed";
      });
    });
  }).catch(() => {
    nodes.forEach((node) => { node.dataset.rendered = "failed"; });
  });
}

function escapeHtml(value: string): string {
  return value.replace(/[&<>]/g, (ch) => ({ "&": "&amp;", "<": "&lt;", ">": "&gt;" }[ch] || ch));
}

function escapeAttr(value: string): string {
  return escapeHtml(value).replace(/"/g, "&quot;");
}
"""


def react_shell_source() -> str:
    return """import { useMemo, useRef, useState } from "react";
import type { MouseEvent, PointerEvent } from "react";
import { useLocation } from "react-router-dom";
import { getPageSpec, getViewerConfig } from "../../page-specs";
import { PAGE_SPEC_ROUTE_MAP } from "../../page-specs/route-map";
import { PageSpecDoc } from "./PageSpecDoc";
import "./proto-spec.css";

export function PageSpecRouteShell({ children }: { children: React.ReactNode }) {
  const location = useLocation();
  const [view, setView] = useState<"product" | "spec">("product");
  const pageKey = useMemo(() => resolvePageKey(location.pathname), [location.pathname]);
  const spec = pageKey ? getPageSpec(pageKey) : null;
  const config = getViewerConfig();
  const dual = config.viewerMode !== "inline-bottom";
  if (!spec) return <>{children}</>;
  return <div className="proto-spec-route-shell">
    <DraggableSpecSwitcher view={view} onViewChange={setView} />
    {(!dual || view === "product") && children}
    {(!dual || view === "spec") && <PageSpecDoc spec={spec} />}
  </div>;
}

function DraggableSpecSwitcher({ view, onViewChange }: { view: "product" | "spec"; onViewChange: (view: "product" | "spec") => void }) {
  const dragRef = useRef<{ pointerId: number; startX: number; startY: number; left: number; top: number; moved: boolean } | null>(null);
  const suppressClickRef = useRef(false);
  const [dragging, setDragging] = useState(false);
  const [position, setPosition] = useState<{ left: number; top: number } | null>(null);
  function clampPosition(element: HTMLElement, left: number, top: number): { left: number; top: number } {
    const rect = element.getBoundingClientRect();
    const margin = 8;
    return {
      left: Math.min(Math.max(left, margin), Math.max(margin, window.innerWidth - rect.width - margin)),
      top: Math.min(Math.max(top, margin), Math.max(margin, window.innerHeight - rect.height - margin)),
    };
  }
  function startDrag(event: PointerEvent<HTMLDivElement>) {
    if (event.button !== 0) return;
    const rect = event.currentTarget.getBoundingClientRect();
    dragRef.current = { pointerId: event.pointerId, startX: event.clientX, startY: event.clientY, left: rect.left, top: rect.top, moved: false };
    event.currentTarget.setPointerCapture(event.pointerId);
  }
  function moveDrag(event: PointerEvent<HTMLDivElement>) {
    const drag = dragRef.current;
    if (!drag || event.pointerId !== drag.pointerId) return;
    const dx = event.clientX - drag.startX;
    const dy = event.clientY - drag.startY;
    if (!drag.moved && Math.hypot(dx, dy) <= 5) return;
    drag.moved = true;
    setDragging(true);
    setPosition(clampPosition(event.currentTarget, drag.left + dx, drag.top + dy));
    event.preventDefault();
  }
  function finishDrag(event: PointerEvent<HTMLDivElement>) {
    const drag = dragRef.current;
    if (!drag || event.pointerId !== drag.pointerId) return;
    suppressClickRef.current = drag.moved && event.type === "pointerup";
    dragRef.current = null;
    setDragging(false);
    if (event.currentTarget.hasPointerCapture(event.pointerId)) event.currentTarget.releasePointerCapture(event.pointerId);
  }
  function handleSwitcherClick(event: MouseEvent<HTMLDivElement>) {
    if (suppressClickRef.current) {
      suppressClickRef.current = false;
      event.preventDefault();
      event.stopPropagation();
      return;
    }
    const source = event.target instanceof Element ? event.target : null;
    const button = source?.closest<HTMLButtonElement>("button[data-view]")
      || document.elementFromPoint(event.clientX, event.clientY)?.closest<HTMLButtonElement>("button[data-view]");
    if (!button) return;
    onViewChange(button.dataset.view === "spec" ? "spec" : "product");
  }
  return <div
    className={"proto-spec-switcher" + (dragging ? " is-dragging" : "")}
    style={position ? { left: position.left, top: position.top, transform: "none" } : undefined}
    onPointerDown={startDrag}
    onPointerMove={moveDrag}
    onPointerUp={finishDrag}
    onPointerCancel={finishDrag}
    onClick={handleSwitcherClick}
  >
    <button type="button" data-view="product" className={view === "product" ? "is-active" : ""}>产品页面</button>
    <button type="button" data-view="spec" className={view === "spec" ? "is-active" : ""}>需求说明</button>
  </div>;
}

function resolvePageKey(pathname: string): string | null {
  const normalized = "/" + pathname.replace(/^\\/+|\\/+$/g, "");
  for (const entry of PAGE_SPEC_ROUTE_MAP) {
    if (routeMatches(entry.pattern, normalized)) return entry.pageKey;
  }
  return null;
}

function routeMatches(pattern: string, pathname: string): boolean {
  if (pattern === pathname || pattern === "/*") return true;
  const patternParts = pattern.replace(/^\\/+|\\/+$/g, "").split("/").filter(Boolean);
  const pathParts = pathname.replace(/^\\/+|\\/+$/g, "").split("/").filter(Boolean);
  if (patternParts.length !== pathParts.length) return false;
  return patternParts.every((part, index) => part.startsWith(":") || part === pathParts[index]);
}
"""


def vue_doc_source() -> str:
    return """<script setup lang="ts">
import { computed, nextTick, ref, watch } from "vue";
import type { PageSpec } from "../../page-specs";
import "./proto-spec.css";
const props = defineProps<{ spec: PageSpec }>();
const editing = ref(false);
const editorMode = ref<"write" | "preview">("write");
const draft = ref(props.spec.markdown || "");
const savedMarkdown = ref(props.spec.markdown || "");
const status = ref("");
watch(() => props.spec.pageKey, () => {
  editing.value = false;
  editorMode.value = "write";
  draft.value = props.spec.markdown || "";
  savedMarkdown.value = props.spec.markdown || "";
  status.value = "";
});
const html = computed(() => renderMarkdown(editing.value && editorMode.value === "preview" ? draft.value : savedMarkdown.value));
const displayStatus = computed(() => status.value || (editing.value && draft.value !== savedMarkdown.value ? "未保存" : ""));
watch(html, () => {
  if (!editing.value || editorMode.value === "preview") void nextTick(renderMermaidDiagrams);
}, { immediate: true });
async function save() {
  status.value = "保存中...";
  try {
    const res = await fetch(`/__prototype-specs/specs/${encodeURIComponent(props.spec.pageKey)}`, { method: "PUT", headers: { "Content-Type": "application/json" }, body: JSON.stringify({ ...props.spec, markdown: composeMarkdownSpec(props.spec, draft.value) }) });
    if (!res.ok) throw new Error(await res.text());
    savedMarkdown.value = draft.value;
    editing.value = false;
    editorMode.value = "write";
    status.value = "已保存";
  } catch {
    status.value = "保存失败：请确认正在使用已接入 protoSpecPlugin 的 Vite 开发服务。";
  }
}
function composeMarkdownSpec(spec: PageSpec, body: string): string {
  return spec.frontmatterText ? `---\\n${spec.frontmatterText}\\n---\\n\\n${body.trim()}\\n` : body.trim() + "\\n";
}
async function handlePaste(event: ClipboardEvent) {
  const files = pastedImageFiles(event.clipboardData);
  if (!files.length) return;
  event.preventDefault();
  const editor = event.currentTarget as HTMLTextAreaElement;
  status.value = "正在上传图片...";
  try {
    const markdownItems: string[] = [];
    for (const file of files) {
      const payload = await uploadImageAsset(props.spec.pageKey, file);
      markdownItems.push(payload.markdown || `![粘贴图片](${payload.path})`);
    }
    draft.value = insertAtSelection(editor.value, editor.selectionStart, editor.selectionEnd, markdownItems);
    status.value = "图片已插入，保存后生效";
  } catch {
    status.value = "图片上传失败：请确认正在使用已接入 protoSpecPlugin 的 Vite 开发服务。";
  }
}
function pastedImageFiles(data: DataTransfer | null): File[] {
  return Array.from(data?.items || [])
    .filter((item) => item.kind === "file" && /^image\\/(png|jpe?g|webp|gif)$/i.test(item.type || ""))
    .map((item) => item.getAsFile())
    .filter((file): file is File => Boolean(file));
}
async function uploadImageAsset(pageKey: string, file: File): Promise<{ path: string; markdown: string }> {
  const res = await fetch(`/__prototype-specs/assets/${encodeURIComponent(pageKey)}`, {
    method: "POST",
    headers: {
      "Content-Type": file.type || "application/octet-stream",
      "X-Proto-Spec-Filename": encodeURIComponent(file.name || ""),
    },
    body: file,
  });
  if (!res.ok) throw new Error(await res.text());
  return res.json();
}
function insertAtSelection(value: string, selectionStart: number, selectionEnd: number, markdownItems: string[]): string {
  const start = Number.isFinite(selectionStart) ? selectionStart : value.length;
  const end = Number.isFinite(selectionEnd) ? selectionEnd : start;
  const before = value.slice(0, start);
  const after = value.slice(end);
  const prefix = before && !before.endsWith("\\n") ? "\\n" : "";
  const suffix = after && !after.startsWith("\\n") ? "\\n" : "";
  return before + prefix + markdownItems.join("\\n") + suffix + after;
}
function renderMarkdown(markdown: string): string {
  const lines = markdown.replace(/\\r\\n/g, "\\n").split("\\n");
  const out: string[] = [];
  let paragraph: string[] = [];
  function flushParagraph() {
    if (!paragraph.length) return;
    out.push("<p>" + paragraph.map(renderInline).join("<br>") + "</p>");
    paragraph = [];
  }
  for (let index = 0; index < lines.length; index += 1) {
    const line = lines[index] || "";
    const trimmed = line.trim();
    const fence = trimmed.match(/^```\\s*([A-Za-z0-9_-]*)\\s*$/);
    if (fence) {
      flushParagraph();
      const lang = (fence[1] || "").toLowerCase();
      const code: string[] = [];
      index += 1;
      while (index < lines.length && !String(lines[index]).trim().startsWith("```")) {
        code.push(lines[index] || "");
        index += 1;
      }
      const codeText = code.join("\\n");
      out.push(lang === "mermaid"
        ? `<figure class="proto-spec-mermaid" data-mermaid="${escapeAttr(codeText)}"><figcaption>Mermaid</figcaption><pre><code>${escapeHtml(codeText)}</code></pre></figure>`
        : `<pre><code>${escapeHtml(codeText)}</code></pre>`);
      continue;
    }
    if (!trimmed) {
      flushParagraph();
      continue;
    }
    const heading = trimmed.match(/^(#{1,4})\\s+(.+)$/);
    if (heading) {
      flushParagraph();
      out.push(`<h${heading[1].length}>${renderInline(heading[2])}</h${heading[1].length}>`);
      continue;
    }
    if (isQuoteStart(trimmed)) {
      flushParagraph();
      const quote = renderQuoteBlock(lines, index);
      out.push(quote.html);
      index = quote.index - 1;
      continue;
    }
    if (isTableStart(lines, index)) {
      flushParagraph();
      const headers = parseTableRow(lines[index] || "");
      index += 2;
      const rows: string[][] = [];
      while (index < lines.length && String(lines[index]).trim().startsWith("|")) {
        rows.push(parseTableRow(lines[index] || ""));
        index += 1;
      }
      index -= 1;
      out.push(renderTable(headers, rows));
      continue;
    }
    if (parseListItem(line)) {
      flushParagraph();
      const list = renderListBlock(lines, index);
      out.push(list.html);
      index = list.index - 1;
      continue;
    }
    paragraph.push(line);
  }
  flushParagraph();
  return out.join("");
}

function isQuoteStart(trimmed: string): boolean {
  return /^>\\s?/.test(trimmed);
}

function renderQuoteBlock(lines: string[], start: number): { html: string; index: number } {
  const quoteLines: string[] = [];
  let index = start;
  while (index < lines.length) {
    const line = lines[index] || "";
    if (!line.trim()) {
      quoteLines.push("");
      index += 1;
      continue;
    }
    const quote = line.match(/^\\s*>\\s?(.*)$/);
    if (!quote) break;
    quoteLines.push(quote[1] || "");
    index += 1;
  }
  const callout = quoteLines[0]?.match(/^\\[!(NOTE|TIP|IMPORTANT|WARNING|CAUTION|TODO|INFO|RISK)\\]\\s*(.*)$/i);
  if (callout) {
    const type = callout[1].toLowerCase();
    const title = callout[2] || calloutLabel(type);
    const body = quoteLines.slice(1).join("\\n").trim();
    return {
      html: `<blockquote class="proto-spec-callout proto-spec-callout--${escapeAttr(type)}"><p class="proto-spec-callout__title">${renderInline(title)}</p>${body ? renderMarkdown(body) : ""}</blockquote>`,
      index,
    };
  }
  return { html: `<blockquote>${renderMarkdown(quoteLines.join("\\n").trim())}</blockquote>`, index };
}

function calloutLabel(type: string): string {
  return ({ note: "说明", tip: "建议", important: "重要", warning: "警告", caution: "注意", todo: "待办", info: "信息", risk: "风险" } as Record<string, string>)[type] || "说明";
}

type ListItem = { indent: number; ordered: boolean; task: boolean; checked: boolean; text: string };

function parseListItem(line: string): ListItem | null {
  const match = String(line || "").match(/^(\\s*)([-*+]|\\d+[.)])\\s+(?:\\[( |x|X)\\]\\s+)?(.+)$/);
  if (!match) return null;
  return {
    indent: match[1].replace(/\\t/g, "    ").length,
    ordered: /^\\d/.test(match[2]),
    task: match[3] !== undefined,
    checked: /x/i.test(match[3] || ""),
    text: match[4],
  };
}

function renderListBlock(lines: string[], start: number): { html: string; index: number } {
  const first = parseListItem(lines[start] || "");
  if (!first) return { html: "", index: start + 1 };
  const tag = first.ordered ? "ol" : "ul";
  const items: string[] = [];
  let index = start;
  while (index < lines.length) {
    const item = parseListItem(lines[index] || "");
    if (!item || item.indent !== first.indent || item.ordered !== first.ordered) break;
    let content = (item.task ? renderTaskCheckbox(item.checked) : "") + renderInline(item.text);
    index += 1;
    while (index < lines.length) {
      const next = parseListItem(lines[index] || "");
      const raw = lines[index] || "";
      if (!raw.trim()) {
        index += 1;
        continue;
      }
      if (next && next.indent > first.indent) {
        const nested = renderListBlock(lines, index);
        content += nested.html;
        index = nested.index;
        continue;
      }
      if (next && next.indent <= first.indent) break;
      const continuationIndent = (raw.match(/^\\s*/)?.[0] || "").replace(/\\t/g, "    ").length;
      if (continuationIndent > first.indent) {
        content += "<br>" + renderInline(raw.trim());
        index += 1;
        continue;
      }
      break;
    }
    items.push(`<li>${content}</li>`);
  }
  return { html: `<${tag}>${items.join("")}</${tag}>`, index };
}

function renderTaskCheckbox(checked: boolean): string {
  return `<input class="proto-spec-task-checkbox" type="checkbox" disabled${checked ? " checked" : ""} aria-label="${checked ? "已完成" : "未完成"}">`;
}

function isTableStart(lines: string[], index: number): boolean {
  return Boolean(lines[index]?.trim().startsWith("|") && lines[index + 1]?.trim().startsWith("|") && parseTableRow(lines[index + 1] || "").every((cell) => /^:?-{3,}:?$/.test(cell)));
}

function parseTableRow(line: string): string[] {
  return line.trim().replace(/^\\||\\|$/g, "").split("|").map((cell) => cell.trim());
}

function renderTable(headers: string[], rows: string[][]): string {
  return "<table><thead><tr>" + headers.map((cell) => `<th>${renderInline(cell)}</th>`).join("") + "</tr></thead><tbody>" + rows.map((row) => "<tr>" + headers.map((_header, index) => `<td>${renderInline(row[index] || "")}</td>`).join("") + "</tr>").join("") + "</tbody></table>";
}

function resolveImageSrc(src: string): string {
  if (/^(?:https?:|data:|blob:|\\/)/i.test(src)) return src;
  const pageKey = props.spec.pageKey;
  const assetPrefix = `../assets/${pageKey}/`;
  if (src.startsWith(assetPrefix)) {
    return `/__prototype-specs/assets/${encodeURIComponent(pageKey)}/${src.slice(assetPrefix.length).split("/").map(encodeURIComponent).join("/")}`;
  }
  return src;
}
function renderInline(value: string): string {
  let output = "";
  let cursor = 0;
  const pattern = /!\\[([^\\]]*)\\]\\(([^)\\s]+)(?:\\s+"([^"]*)")?\\)|\\[([^\\]]+)\\]\\(([^)\\s]+)\\)|`([^`]+)`|\\*\\*([^*]+)\\*\\*|==([^=]+)==/g;
  let match: RegExpExecArray | null;
  while ((match = pattern.exec(value)) !== null) {
    output += escapeHtml(value.slice(cursor, match.index));
    if (match[1] !== undefined) output += `<img src="${escapeAttr(resolveImageSrc(match[2]))}" alt="${escapeAttr(match[1])}"${match[3] ? ` title="${escapeAttr(match[3])}"` : ""}>`;
    else if (match[4] !== undefined) output += `<a href="${escapeAttr(match[5])}" target="_blank" rel="noreferrer">${escapeHtml(match[4])}</a>`;
    else if (match[6] !== undefined) output += `<code>${escapeHtml(match[6])}</code>`;
    else if (match[7] !== undefined) output += `<strong>${escapeHtml(match[7])}</strong>`;
    else if (match[8] !== undefined) output += `<mark>${escapeHtml(match[8])}</mark>`;
    cursor = match.index + match[0].length;
  }
  return output + escapeHtml(value.slice(cursor));
}

type MermaidApi = { initialize?: (options: Record<string, unknown>) => void; render: (id: string, code: string) => Promise<{ svg?: string }> };
type ProtoSpecWindow = Window & typeof globalThis & { mermaid?: MermaidApi; __protoSpecMermaidPromise?: Promise<MermaidApi>; __protoSpecMermaidInitialized?: boolean };

function loadMermaid(): Promise<MermaidApi> {
  const protoWindow = window as ProtoSpecWindow;
  if (protoWindow.mermaid?.render) {
    initializeMermaid(protoWindow.mermaid);
    return Promise.resolve(protoWindow.mermaid);
  }
  if (protoWindow.__protoSpecMermaidPromise) return protoWindow.__protoSpecMermaidPromise;
  protoWindow.__protoSpecMermaidPromise = new Promise((resolve, reject) => {
    const existing = document.querySelector<HTMLScriptElement>("script[data-proto-spec-mermaid]");
    if (existing) {
      existing.addEventListener("load", () => {
        if (protoWindow.mermaid?.render) {
          initializeMermaid(protoWindow.mermaid);
          resolve(protoWindow.mermaid);
        } else {
          reject(new Error("Mermaid failed to initialize."));
        }
      }, { once: true });
      existing.addEventListener("error", reject, { once: true });
      return;
    }
    const script = document.createElement("script");
    script.src = "https://cdn.jsdelivr.net/npm/mermaid@10/dist/mermaid.min.js";
    script.async = true;
    script.dataset.protoSpecMermaid = "true";
    script.onload = () => {
      if (protoWindow.mermaid?.render) {
        initializeMermaid(protoWindow.mermaid);
        resolve(protoWindow.mermaid);
      } else {
        reject(new Error("Mermaid failed to initialize."));
      }
    };
    script.onerror = reject;
    document.head.appendChild(script);
  });
  return protoWindow.__protoSpecMermaidPromise;
}

function initializeMermaid(mermaid: MermaidApi): void {
  const protoWindow = window as ProtoSpecWindow;
  if (protoWindow.__protoSpecMermaidInitialized) return;
  if (mermaid.initialize) mermaid.initialize({ startOnLoad: false, securityLevel: "strict" });
  protoWindow.__protoSpecMermaidInitialized = true;
}

function renderMermaidDiagrams(): void {
  const nodes = Array.from(document.querySelectorAll<HTMLElement>(".proto-spec-mermaid[data-mermaid]:not([data-rendered])"));
  if (!nodes.length) return;
  nodes.forEach((node) => { node.dataset.rendered = "loading"; });
  void loadMermaid().then((mermaid) => {
    nodes.forEach((node, index) => {
      const code = node.dataset.mermaid || "";
      void mermaid.render(`proto-spec-mermaid-${index}-${Date.now()}`, code).then((result) => {
        node.dataset.rendered = "true";
        if (result.svg) node.innerHTML = result.svg;
      }).catch(() => {
        node.dataset.rendered = "failed";
      });
    });
  }).catch(() => {
    nodes.forEach((node) => { node.dataset.rendered = "failed"; });
  });
}

function escapeHtml(value: string): string {
  return value.replace(/[&<>]/g, (ch) => ({ "&": "&amp;", "<": "&lt;", ">": "&gt;" }[ch] || ch));
}

function escapeAttr(value: string): string {
  return escapeHtml(value).replace(/"/g, "&quot;");
}
</script>
<template>
  <main class="proto-spec-doc"><div class="proto-spec-doc__inner">
    <header><p class="proto-spec-doc__eyebrow">PAGE SPEC</p><h1>{{ spec.pageName }}</h1><p>{{ spec.summary }}</p></header>
    <div class="proto-spec-doc__toolbar">
      <button v-if="!editing" type="button" class="proto-spec-doc__button" @click="editing = true; editorMode = 'write'; status = ''">编辑</button>
      <template v-else>
        <div class="proto-spec-doc__mode-toggle" role="group" aria-label="编辑模式">
          <button type="button" :class="{ 'is-active': editorMode === 'write' }" @click="editorMode = 'write'">Markdown</button>
          <button type="button" :class="{ 'is-active': editorMode === 'preview' }" @click="editorMode = 'preview'">预览</button>
        </div>
        <button type="button" class="proto-spec-doc__button proto-spec-doc__button--primary" @click="save">保存</button>
        <button type="button" class="proto-spec-doc__button" @click="draft = savedMarkdown; editing = false; editorMode = 'write'; status = ''">取消</button>
      </template>
      <span v-if="displayStatus" class="proto-spec-doc__status">{{ displayStatus }}</span>
    </div>
    <textarea v-if="editing && editorMode === 'write'" class="proto-spec-doc__editor" v-model="draft" @paste="handlePaste" />
    <article v-else class="proto-spec-doc__content" v-html="html" />
  </div></main>
</template>
"""


def vue_shell_source() -> str:
    return """<script setup lang="ts">
import { computed, ref } from "vue";
import { useRoute } from "vue-router";
import { getPageSpec, getViewerConfig } from "../../page-specs";
import { PAGE_SPEC_ROUTE_MAP } from "../../page-specs/route-map";
import PageSpecDoc from "./PageSpecDoc.vue";
import "./proto-spec.css";
const route = useRoute();
const view = ref<"product" | "spec">("product");
const dragging = ref(false);
const suppressClick = ref(false);
const dragState = ref<{ pointerId: number; startX: number; startY: number; left: number; top: number; moved: boolean } | null>(null);
const switcherPosition = ref<{ left: number; top: number } | null>(null);
const pageKey = computed(() => resolvePageKey(route.path));
const spec = computed(() => pageKey.value ? getPageSpec(pageKey.value) : null);
const dual = computed(() => getViewerConfig().viewerMode !== "inline-bottom");
const switcherStyle = computed(() => switcherPosition.value ? { left: `${switcherPosition.value.left}px`, top: `${switcherPosition.value.top}px`, transform: "none" } : undefined);
function clampSwitcherPosition(element: HTMLElement, left: number, top: number): { left: number; top: number } {
  const rect = element.getBoundingClientRect();
  const margin = 8;
  return {
    left: Math.min(Math.max(left, margin), Math.max(margin, window.innerWidth - rect.width - margin)),
    top: Math.min(Math.max(top, margin), Math.max(margin, window.innerHeight - rect.height - margin)),
  };
}
function startSwitcherDrag(event: PointerEvent) {
  if (event.button !== 0) return;
  const element = event.currentTarget as HTMLElement;
  const rect = element.getBoundingClientRect();
  dragState.value = { pointerId: event.pointerId, startX: event.clientX, startY: event.clientY, left: rect.left, top: rect.top, moved: false };
  element.setPointerCapture(event.pointerId);
}
function moveSwitcherDrag(event: PointerEvent) {
  const drag = dragState.value;
  if (!drag || event.pointerId !== drag.pointerId) return;
  const dx = event.clientX - drag.startX;
  const dy = event.clientY - drag.startY;
  if (!drag.moved && Math.hypot(dx, dy) <= 5) return;
  drag.moved = true;
  dragging.value = true;
  switcherPosition.value = clampSwitcherPosition(event.currentTarget as HTMLElement, drag.left + dx, drag.top + dy);
  event.preventDefault();
}
function finishSwitcherDrag(event: PointerEvent) {
  const drag = dragState.value;
  if (!drag || event.pointerId !== drag.pointerId) return;
  suppressClick.value = drag.moved && event.type === "pointerup";
  dragging.value = false;
  dragState.value = null;
  const element = event.currentTarget as HTMLElement;
  if (element.hasPointerCapture(event.pointerId)) element.releasePointerCapture(event.pointerId);
}
function handleSwitcherClick(event: MouseEvent) {
  if (suppressClick.value) {
    suppressClick.value = false;
    event.preventDefault();
    event.stopPropagation();
    return;
  }
  const source = event.target instanceof Element ? event.target : null;
  const button = source?.closest<HTMLButtonElement>("button[data-view]")
    || document.elementFromPoint(event.clientX, event.clientY)?.closest<HTMLButtonElement>("button[data-view]");
  if (!button) return;
  view.value = button.dataset.view === "spec" ? "spec" : "product";
}
function resolvePageKey(pathname: string): string | null {
  const normalized = "/" + pathname.replace(/^\\/+|\\/+$/g, "");
  for (const entry of PAGE_SPEC_ROUTE_MAP) if (routeMatches(entry.pattern, normalized)) return entry.pageKey;
  return null;
}

function routeMatches(pattern: string, pathname: string): boolean {
  if (pattern === pathname || pattern === "/*") return true;
  const patternParts = pattern.replace(/^\\/+|\\/+$/g, "").split("/").filter(Boolean);
  const pathParts = pathname.replace(/^\\/+|\\/+$/g, "").split("/").filter(Boolean);
  if (patternParts.length !== pathParts.length) return false;
  return patternParts.every((part, index) => part.startsWith(":") || part === pathParts[index]);
}
</script>
<template>
  <div class="proto-spec-route-shell">
    <template v-if="spec">
      <div
        class="proto-spec-switcher"
        :class="{ 'is-dragging': dragging }"
        :style="switcherStyle"
        @pointerdown="startSwitcherDrag"
        @pointermove="moveSwitcherDrag"
        @pointerup="finishSwitcherDrag"
        @pointercancel="finishSwitcherDrag"
        @click="handleSwitcherClick"
      ><button type="button" data-view="product" :class="{ 'is-active': view === 'product' }">产品页面</button><button type="button" data-view="spec" :class="{ 'is-active': view === 'spec' }">需求说明</button></div>
      <slot v-if="!dual || view === 'product'" />
      <PageSpecDoc v-if="!dual || view === 'spec'" :spec="spec" />
    </template>
    <slot v-else />
  </div>
</template>
"""


def proto_spec_css() -> str:
    return "".join(
        [
            ".proto-spec-switcher,.proto-spec-doc{--proto-spec-bg:#f5f7fa;--proto-spec-surface:#fff;--proto-spec-muted:#647083;--proto-spec-text:#1f2933;--proto-spec-border:#d8dee8;--proto-spec-soft:#eef2f6;--proto-spec-accent:#e65f3f;--proto-spec-accent-dark:#bd452d;--proto-spec-focus:#2563eb;box-sizing:border-box}",
            ".proto-spec-route-shell{min-height:100%}",
            ".proto-spec-switcher{position:fixed;top:16px;left:50%;z-index:2147483000;display:inline-flex;transform:translateX(-50%);gap:2px;border:1px solid var(--proto-spec-border);border-radius:8px;background:rgba(255,255,255,.96);padding:3px;box-shadow:0 10px 24px rgba(15,23,42,.12);backdrop-filter:blur(10px);cursor:grab;touch-action:none;user-select:none}",
            ".proto-spec-switcher.is-dragging,.proto-spec-switcher.is-dragging button{cursor:grabbing}",
            ".proto-spec-switcher button,.proto-spec-doc__toolbar button{-webkit-appearance:none;appearance:none;display:inline-flex;align-items:center;justify-content:center;gap:6px;margin:0;text-align:center;text-decoration:none;text-indent:0;text-shadow:none;text-transform:none;white-space:nowrap;-webkit-text-fill-color:currentColor;opacity:1;filter:none}",
            ".proto-spec-switcher button::before,.proto-spec-switcher button::after,.proto-spec-doc__toolbar button::before,.proto-spec-doc__toolbar button::after{content:none!important;display:none!important}",
            ".proto-spec-switcher button{min-width:88px;min-height:36px;border:0;border-radius:6px;background:transparent;color:var(--proto-spec-muted);cursor:pointer;font:700 13px/1.2 Inter,ui-sans-serif,system-ui,sans-serif;letter-spacing:0;padding:9px 13px}",
            ".proto-spec-switcher button:hover{background:var(--proto-spec-soft);color:var(--proto-spec-accent-dark);-webkit-text-fill-color:currentColor}",
            ".proto-spec-switcher button.is-active{background:var(--proto-spec-accent);color:#fff;-webkit-text-fill-color:#fff}",
            ".proto-spec-doc{min-height:100vh;background:var(--proto-spec-bg);color:var(--proto-spec-text);padding:88px 24px 56px;font:14px/1.75 Inter,ui-sans-serif,system-ui,sans-serif}",
            ".proto-spec-doc *{box-sizing:border-box}",
            ".proto-spec-doc__inner{width:min(1040px,100%);margin:0 auto}",
            ".proto-spec-doc header{border-bottom:1px solid var(--proto-spec-border);margin:0 0 18px;padding:0 0 22px}",
            ".proto-spec-doc__eyebrow{color:var(--proto-spec-muted);font-size:12px;font-weight:800;letter-spacing:0;margin:0 0 8px;text-transform:uppercase}",
            ".proto-spec-doc h1{color:var(--proto-spec-text);font-size:30px;font-weight:800;line-height:1.2;margin:0 0 10px}",
            ".proto-spec-doc header p:not(.proto-spec-doc__eyebrow){color:var(--proto-spec-muted);font-size:15px;line-height:1.7;max-width:78ch;margin:0}",
            ".proto-spec-doc h2{border-top:1px solid var(--proto-spec-border);color:var(--proto-spec-text);font-size:20px;font-weight:800;line-height:1.35;margin:28px 0 12px;padding-top:24px}",
            ".proto-spec-doc h2:first-child{border-top:0;margin-top:0;padding-top:0}",
            ".proto-spec-doc h3{color:var(--proto-spec-text);font-size:16px;font-weight:800;line-height:1.45;margin:22px 0 8px}",
            ".proto-spec-doc h4{color:var(--proto-spec-muted);font-size:14px;font-weight:800;line-height:1.45;margin:18px 0 6px}",
            ".proto-spec-doc p{margin:0 0 12px}",
            ".proto-spec-doc a{color:var(--proto-spec-accent-dark);text-decoration:none}",
            ".proto-spec-doc a:hover{text-decoration:underline}",
            ".proto-spec-doc ul,.proto-spec-doc ol{margin:0 0 14px 22px;padding:0}",
            ".proto-spec-doc ul ul,.proto-spec-doc ul ol,.proto-spec-doc ol ul,.proto-spec-doc ol ol{margin-top:6px;margin-bottom:6px}",
            ".proto-spec-doc li{margin:5px 0}",
            ".proto-spec-doc li::marker{color:var(--proto-spec-accent)}",
            ".proto-spec-task-checkbox{width:15px;height:15px;margin:0 7px 0 0;vertical-align:-2px;accent-color:var(--proto-spec-accent)}",
            ".proto-spec-doc code{border-radius:5px;background:var(--proto-spec-soft);color:var(--proto-spec-text);font:13px/1.5 ui-monospace,SFMono-Regular,Menlo,monospace;padding:2px 5px}",
            ".proto-spec-doc mark{border-radius:4px;background:#fff2b8;color:var(--proto-spec-text);padding:1px 4px}",
            ".proto-spec-doc pre{overflow:auto;border:1px solid var(--proto-spec-border);border-radius:8px;background:#f8fafc;color:var(--proto-spec-text);margin:14px 0;padding:14px}",
            ".proto-spec-doc pre code{background:transparent;padding:0}",
            ".proto-spec-doc blockquote{border-left:4px solid var(--proto-spec-accent);color:var(--proto-spec-muted);margin:16px 0;padding:2px 0 2px 14px}",
            ".proto-spec-callout{border:1px solid var(--proto-spec-border)!important;border-left:4px solid var(--proto-spec-accent)!important;border-radius:8px;background:#fffaf7;color:var(--proto-spec-text)!important;padding:12px 14px!important}",
            ".proto-spec-callout__title{color:var(--proto-spec-accent-dark);font-weight:800;margin:0 0 6px!important}",
            ".proto-spec-doc img{display:block;max-width:100%;height:auto;border:1px solid var(--proto-spec-border);border-radius:8px;background:#fff;margin:14px 0}",
            ".proto-spec-doc__toolbar{position:sticky;top:66px;z-index:2;display:flex;align-items:center;gap:8px;flex-wrap:wrap;margin:0 0 16px;padding:10px 0;background:var(--proto-spec-bg)}",
            ".proto-spec-doc__button,.proto-spec-doc__toolbar button{min-height:38px;border:1px solid var(--proto-spec-border);border-radius:6px;background:var(--proto-spec-surface);color:var(--proto-spec-text);cursor:pointer;font:800 13px/1.2 Inter,ui-sans-serif,system-ui,sans-serif;letter-spacing:0;padding:9px 12px}",
            ".proto-spec-doc__button:hover,.proto-spec-doc__button:active,.proto-spec-doc__toolbar button:hover,.proto-spec-doc__toolbar button:active{border-color:var(--proto-spec-accent);color:var(--proto-spec-accent-dark);-webkit-text-fill-color:currentColor}",
            ".proto-spec-doc__button--primary{border-color:var(--proto-spec-accent);background:var(--proto-spec-accent);color:#fff;-webkit-text-fill-color:#fff}",
            ".proto-spec-doc__button--primary:hover,.proto-spec-doc__button--primary:active,.proto-spec-doc__button--primary:focus{background:var(--proto-spec-accent-dark);color:#fff;-webkit-text-fill-color:#fff}",
            ".proto-spec-doc__toolbar button.proto-spec-doc__button--primary,.proto-spec-doc__toolbar button.proto-spec-doc__button--primary:hover,.proto-spec-doc__toolbar button.proto-spec-doc__button--primary:active,.proto-spec-doc__toolbar button.proto-spec-doc__button--primary:focus{background:var(--proto-spec-accent)!important;border-color:var(--proto-spec-accent)!important;color:#fff!important;-webkit-text-fill-color:#fff!important;font-size:13px!important;line-height:1.2!important;text-indent:0!important;text-shadow:none!important;visibility:visible!important;opacity:1!important;overflow:visible!important}",
            ".proto-spec-doc__toolbar button.proto-spec-doc__button--primary:hover,.proto-spec-doc__toolbar button.proto-spec-doc__button--primary:active,.proto-spec-doc__toolbar button.proto-spec-doc__button--primary:focus{background:var(--proto-spec-accent-dark)!important}",
            ".proto-spec-doc__mode-toggle{display:inline-flex;gap:2px;border:1px solid var(--proto-spec-border);border-radius:8px;background:var(--proto-spec-soft);padding:3px}",
            ".proto-spec-doc__mode-toggle button{min-height:32px;border:0;background:transparent;color:var(--proto-spec-muted);padding:7px 11px}",
            ".proto-spec-doc__mode-toggle button.is-active{background:var(--proto-spec-surface);box-shadow:0 1px 2px rgba(15,23,42,.08);color:var(--proto-spec-text);-webkit-text-fill-color:currentColor}",
            ".proto-spec-doc__status{color:var(--proto-spec-muted);font-size:13px;font-weight:700}",
            ".proto-spec-doc__content{background:var(--proto-spec-surface);border:1px solid var(--proto-spec-border);border-radius:8px;box-shadow:0 14px 30px rgba(15,23,42,.06);display:block;margin-top:0;padding:30px 34px}",
            ".proto-spec-doc__content>*{max-width:78ch}",
            ".proto-spec-doc__content table{border-collapse:collapse;width:100%;max-width:100%;background:white;margin:16px 0}",
            ".proto-spec-doc__content th,.proto-spec-doc__content td{border:1px solid var(--proto-spec-border);padding:9px 11px;text-align:left;vertical-align:top}",
            ".proto-spec-doc__content th{background:var(--proto-spec-soft);font-weight:800}",
            ".proto-spec-mermaid{border:1px solid var(--proto-spec-border);border-radius:8px;background:#fff;margin:16px 0;padding:14px;max-width:100%}",
            ".proto-spec-mermaid[data-rendered='loading']::after{content:'正在渲染 Mermaid 图表...';display:block;color:var(--proto-spec-muted);font-size:12px;font-weight:700;margin-top:8px}",
            ".proto-spec-mermaid[data-rendered='failed']::after{content:'Mermaid 图表渲染失败，已保留源码。';display:block;color:var(--proto-spec-accent-dark);font-size:12px;font-weight:700;margin-top:8px}",
            ".proto-spec-mermaid figcaption{color:var(--proto-spec-muted);font-size:12px;font-weight:800;letter-spacing:0;margin:0 0 8px;text-transform:uppercase}",
            ".proto-spec-mermaid svg{display:block;max-width:100%;height:auto;margin:0 auto;overflow:visible}",
            ".proto-spec-mermaid foreignObject,.proto-spec-mermaid foreignObject *{box-sizing:content-box;line-height:1.2!important}",
            ".proto-spec-doc__editor{box-sizing:border-box;width:100%;min-height:64vh;border:1px solid var(--proto-spec-border);border-radius:8px;background:var(--proto-spec-surface);box-shadow:0 14px 30px rgba(15,23,42,.06);color:var(--proto-spec-text);font:14px/1.65 ui-monospace,SFMono-Regular,Menlo,monospace;padding:22px;resize:vertical}",
            ".proto-spec-doc__editor:focus,.proto-spec-doc button:focus-visible,.proto-spec-switcher button:focus-visible{outline:2px solid var(--proto-spec-focus);outline-offset:2px}",
            "@media (max-width:720px){.proto-spec-switcher{top:10px}.proto-spec-switcher button{min-width:auto;padding:8px 10px}.proto-spec-doc{padding:74px 14px 32px}.proto-spec-doc h1{font-size:24px}.proto-spec-doc__toolbar{top:54px}.proto-spec-doc__content{padding:22px 18px}.proto-spec-doc__content>*{max-width:100%}.proto-spec-doc__editor{min-height:58vh;padding:16px}}",
        ]
    )


def audit(analysis: ProjectAnalysis, pages: list[ProjectPage], report: WorkflowReport) -> None:
    spec_root = Path(analysis.specRoot)
    current = spec_root / "current"
    if not current.is_dir():
        report.errors.append(f"{current}: current spec directory does not exist.")
        return
    current_keys = {path.stem for path in current.glob("*.md")}
    expected_keys = {page.pageKey for page in pages}
    missing = sorted(expected_keys - current_keys)
    if missing:
        report.warnings.append("Missing specs for pages: " + ", ".join(missing))
    for path in sorted(current.glob("*.md")):
        raw = read_text(path) or ""
        frontmatter, body = parse_frontmatter(raw)
        if frontmatter.get("pageKey") != path.stem:
            report.errors.append(f"{path}: pageKey must match filename.")
        if frontmatter.get("storageFormat") != "markdown":
            report.errors.append(f'{path}: storageFormat must be "markdown".')
        if f"## {SUMMARY_HEADING}" not in body:
            report.errors.append(f"{path}: missing ## {SUMMARY_HEADING}.")
        if not re.search(r"^##\s+.+", body, re.M):
            report.errors.append(f"{path}: no rule sections found.")


def sync_helper_scripts(root: Path, dry_run: bool, report: WorkflowReport) -> None:
    source_dir = Path(__file__).resolve().parent
    target_dir = root / "scripts"
    if source_dir == target_dir:
        return
    for script in source_dir.glob("*.py"):
        target = target_dir / script.name
        if dry_run:
            report.changedFiles.append(str(target))
            continue
        target_dir.mkdir(parents=True, exist_ok=True)
        if not target.exists() or read_text(script) != read_text(target):
            shutil.copy2(script, target)
            report.changedFiles.append(str(target))


def main() -> int:
    args = parse_args()
    root = Path(args.root).resolve()
    report = WorkflowReport(operation=args.operation, dryRun=args.dry_run)
    if not root.is_dir():
        report.errors.append(f"{root}: project root does not exist or is not a directory.")
        return finish(report, args)

    analysis = analyze_project(root, args.file)
    pages = select_pages(analysis, args)
    report.analysis = {
        **asdict(analysis),
        "pages": [asdict(page) for page in pages],
    }
    if not pages and args.operation not in {"audit"}:
        report.errors.append("No target pages found. Use --scope all, --file, or --page-key with a discovered page.")
        return finish(report, args)

    if args.operation == "audit":
        audit(analysis, pages or analysis.pages, report)
        return finish(report, args)

    spec_root = Path(analysis.specRoot)
    if args.operation in {"create", "update"}:
        sync_helper_scripts(root, args.dry_run, report)
        generate_specs(root, analysis, pages, args, report)
        if args.integrate:
            integrate_viewer(root, analysis, pages, args, report)
    elif args.operation == "delete":
        delete_specs(spec_root, pages, args, report)
    elif args.operation == "display":
        write_viewer_config(spec_root, args, args.dry_run, report)
        if args.integrate:
            integrate_viewer(root, analysis, pages, args, report)
    elif args.operation == "integrate":
        integrate_viewer(root, analysis, pages, args, report)

    return finish(report, args)


def finish(report: WorkflowReport, args: argparse.Namespace) -> int:
    unique_changed = []
    for path in report.changedFiles:
        if path not in unique_changed:
            unique_changed.append(path)
    report.changedFiles = unique_changed
    if args.json_output:
        print(json.dumps(asdict(report), ensure_ascii=False, indent=2))
    else:
        print(f"Operation: {report.operation} ({'dry-run' if report.dryRun else 'write'})")
        for label, items in (("ERROR", report.errors), ("WARN", report.warnings), ("SKIP", report.skipped), ("CHANGED", report.changedFiles)):
            for item in items:
                print(f"{label}: {item}")
        if report.aiReviewRequired:
            print("NEXT: 本地规则只生成了基础草稿。请继续读取对应页面代码和 current/*.md，由当前 AI 编程工具补全 Markdown 正文，然后重新运行 validate_editable_specs.py。")
        if not report.errors:
            print("Workflow completed.")
    return 1 if report.errors else 0


if __name__ == "__main__":
    sys.exit(main())
