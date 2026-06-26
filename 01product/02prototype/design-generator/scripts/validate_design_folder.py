#!/usr/bin/env python3
"""
校验生成的设计系统文件夹。

支持格式：
  - ai-design-system-v3（默认）：10 章 DESIGN.md + DESIGN_GAPS.md
  - stitch-alpha：stitch-alpha 语料格式
  - legacy：旧编号章节格式
"""

from __future__ import annotations

import argparse
import html
import json
import re
import sys
from pathlib import Path
from typing import Any

from front_matter_schema import (
    is_unified_schema,
    normalize_design_data,
    parse_simple_yaml as parse_simple_yaml_fallback,
)


SUPPORTED_MARKDOWN_FILES = ("DESIGN.md", "design.md")
REQUIRED_FILES_LEGACY = ("preview.html", "preview-dark.html", "example.html")
REQUIRED_FILES_V3 = ("preview.html", "preview-dark.html", "example.html", "DESIGN_GAPS.md")
REQUIRED_NORMALIZED_KEYS = (
    "version",
    "name",
    "description",
    "colors",
    "typography",
    "spacing",
    "rounded",
    "components",
)
OPTIONAL_NORMALIZED_KEYS = (
    "language",
    "shadows",
    "motion",
    "patterns",
    "evidence",
    "runtime",
    "componentMappings",
    "pagePatterns",
    "prototypeRules",
)
# 规范化 v3 数据中可能出现的历史 / 投影字段。
RECOMMENDED_V3_KEYS = (
    "productType",
    "interfaceArchetype",
    "density",
    "framework",
    "componentLibraries",
    "designPurpose",
    "recommendedTokens",
    "legacyTokens",
    "layoutRules",
    "componentRecipes",
    "pageTemplates",
    "aiGenerationRules",
    "forbiddenRules",
    "selfCheck",
    "knownLimits",
    "unresolvedItems",
    "conflicts",
    "assumptions",
    "confidence",
)
REQUIRED_UNIFIED_KEYS = (
    # ── 身份信息 ──
    "version",
    "language",
    "name",
    "summary",
    # ── 产品上下文 ──
    "product",
    "technology",
    "runtime",
    # ── 可执行设计系统 ──
    "tokens",
    "layout",
    "components",
    "pageTemplates",
    "generationRules",
    # ── 证据与缺口台账（见 references/output-contract.md） ──
    "evidence",
    "briefConsultation",
    "legacyTokens",
    "openQuestions",
    "knownLimits",
    "assumptions",
)
# 这些台账字段允许为空 list/dict：字段必须存在，但没有可记录内容也是合法状态。
ALLOW_EMPTY_UNIFIED_KEYS = frozenset(
    {"legacyTokens", "openQuestions", "knownLimits", "assumptions"}
)

# ── V3（ai-design-system-v3）10 章章节 ──
REQUIRED_V3_SECTIONS = (
    "Usage Guide",
    "Design System Overview",
    "Design Principles & Interface Language",
    "Foundation Tokens",
    "Component System & Usage Rules",
    "Layout System & Page Shell",
    "Page Templates",
    "Interaction States & Responsive Rules",
    "AI Generation Rules, Forbidden Patterns & Self-Check",
    "Known Limits & Evidence Summary",
)
V3_SECTION_ALIASES = {
    "Usage Guide": ("usage guide", "使用说明"),
    "Design System Overview": (
        "design system overview",
        "product & interface profile",
        "product and interface profile",
        "设计系统总览",
        "设计系统概览",
        "产品与界面画像",
        "产品和界面画像",
    ),
    "Design Principles & Interface Language": (
        "design principles & interface language",
        "design principles and interface language",
        "design principles",
        "设计原则与界面语言",
        "设计原则和界面语言",
        "设计原则",
    ),
    "Foundation Tokens": ("foundation tokens", "design tokens", "基础设计令牌", "基础令牌", "设计令牌"),
    "Component System & Usage Rules": (
        "component system & usage rules",
        "component system and usage rules",
        "component system",
        "组件系统与使用规则",
        "组件系统和使用规则",
        "组件系统",
    ),
    "Layout System & Page Shell": (
        "layout system & page shell",
        "layout system and page shell",
        "layout & app shell",
        "layout and app shell",
        "布局系统与页面骨架",
        "布局系统和页面骨架",
        "布局与应用壳",
        "布局和应用壳",
    ),
    "Page Templates": ("page templates", "页面模板"),
    "Interaction States & Responsive Rules": (
        "interaction states & responsive rules",
        "interaction states and responsive rules",
        "交互状态与响应式规则",
        "交互状态和响应式规则",
    ),
    "AI Generation Rules, Forbidden Patterns & Self-Check": (
        "ai generation rules, forbidden patterns & self-check",
        "ai generation rules, forbidden patterns and self-check",
        "ai generation rules forbidden patterns & self-check",
        "AI 生成规则、禁止事项与自检清单",
        "AI 生成规则 禁止事项与自检清单",
        "AI 生成规则、禁止事项和自检清单",
        "原型生成规则与自检",
        "原型生成规则和自检",
        "prototype generation rules & self-check",
        "prototype generation rules and self-check",
        "ai 生成规则",
    ),
    "Known Limits & Evidence Summary": (
        "known limits & evidence summary",
        "known limits and evidence summary",
        "evidence, limits & default decisions",
        "evidence limits & default decisions",
        "evidence limits and default decisions",
        "已知限制与来源摘要",
        "已知限制和来源摘要",
        "证据、限制与默认决策",
        "证据、限制和默认决策",
    ),
}

# ── DESIGN_GAPS.md section requirements ──
REQUIRED_GAPS_SECTIONS = (
    "总体置信度摘要",
    "高优先级待确认项",
    "中优先级待确认项",
    "低优先级待确认项",
    "设计冲突清单",
    "未覆盖",
    "人工确认记录",
)
GAPS_SECTION_ALIASES = {
    "总体置信度摘要": ("总体置信度摘要", "overall confidence summary", "confidence summary"),
    "高优先级待确认项": ("高优先级待确认项", "high priority", "high-priority"),
    "中优先级待确认项": ("中优先级待确认项", "medium priority", "medium-priority"),
    "低优先级待确认项": ("低优先级待确认项", "low priority", "low-priority"),
    "设计冲突清单": ("设计冲突清单", "design conflict", "conflict list", "设计冲突"),
    "未覆盖": ("未覆盖", "未观察", "uncovered", "unobserved"),
    "人工确认记录": ("人工确认记录", "manual confirmation", "confirmation record"),
}

LEGACY_SECTION_NUMBERS = tuple(str(index) for index in range(1, 10))
PREFERRED_PREVIEW_MARKERS = (
    "id=\"style-overview\"",
    "id=\"colors\"",
    "id=\"typography\"",
    "id=\"layout-grid\"",
    "id=\"icons\"",
    "id=\"spacing\"",
    "id=\"radius\"",
    "id=\"elevation\"",
    "id=\"buttons\"",
    "id=\"inputs\"",
    "id=\"data-display\"",
    "id=\"tags\"",
    "id=\"pagination\"",
    "id=\"tabs\"",
    "id=\"dialogs\"",
    "id=\"cards\"",
    "id=\"template-pages\"",
)
PREVIEW_REQUIRED_MARKERS = (
    "data-preview-source=\"design-md\"",
    "id=\"style-overview\"",
    "id=\"colors\"",
    "id=\"buttons\"",
    "id=\"template-pages\"",
)
EXAMPLE_REQUIRED_MARKERS = (
    "data-example-source=\"design-md\"",
    "data-example-archetype=",
    "data-example-pattern=",
    "data-example-pattern-source=",
)
STITCH_ALPHA_REQUIRED_FILES = ("preview.html", "preview-dark.html")
REQUIRED_STITCH_ALPHA_KEYS = (
    "version",
    "name",
    "description",
    "colors",
    "typography",
    "rounded",
    "spacing",
    "components",
)
OPTIONAL_STITCH_ALPHA_KEYS = ("format", "shadows", "language")
REQUIRED_STITCH_ALPHA_SECTIONS = (
    "Overview",
    "Colors",
    "Typography",
    "Components",
)
RECOMMENDED_STITCH_ALPHA_SECTIONS = (
    "Layout",
    "Elevation",
    "Shapes",
    "Do's and Don'ts",
    "Responsive Behavior",
    "Iteration Guide",
    "Known Gaps",
)
STITCH_ALPHA_PREVIEW_REQUIRED_MARKERS = (
    ":root",
    "id=\"colors\"",
    "id=\"typography\"",
    "id=\"components\"",
)
STITCH_ALPHA_COMPONENT_ANCHORS = (
    "id=\"components\"",
    "id=\"buttons\"",
    "id=\"cards\"",
    "id=\"forms\"",
    "id=\"badges\"",
    "id=\"inputs\"",
    "id=\"navigation\"",
    "id=\"nav\"",
)
STITCH_ALPHA_PREVIEW_RECOMMENDED_MARKERS = (
    "id=\"responsive\"",
    "id=\"spacing\"",
    "id=\"radius\"",
    "id=\"elevation\"",
)
PLACEHOLDER_MARKERS = (
    "todo",
    "must_replace",
    "{{project_name}}",
    "{{project_slug}}",
    "replace with",
    "replace this",
    "replace these",
    "replace all placeholder copy",
)
TITLE_PATTERNS = (
    r"^#\s+Design System:",
    r"^#\s+设计系统[:：]",
)
TOKEN_REF_RE = re.compile(r"\{([a-zA-Z0-9_-]+)\.([a-zA-Z0-9_.-]+)\}")
HEX_COLOR_RE = re.compile(r"#(?:[0-9a-fA-F]{3}|[0-9a-fA-F]{6}|[0-9a-fA-F]{8})\b")
# recommendedTokens.color key -> colors key candidates (see references/front-matter-dedup-rules.md)
RECOMMENDED_TO_COLORS: dict[str, tuple[str, ...]] = {
    "primary": ("primary", "brand", "accent"),
    "topbar": ("shell-topbar", "top-nav-bg", "topbar", "top-nav"),
    "sidebar": ("shell-sidebar", "sidebar"),
    "canvas": ("canvas",),
    "text": ("ink", "text-primary", "text", "body"),
    "placeholder": ("ink-muted", "text-muted", "placeholder"),
    "border": ("hairline", "border", "stroke"),
}
LAYOUT_DIMENSION_SLOTS: tuple[tuple[str, tuple[str, ...], tuple[str, ...]], ...] = (
    (
        "topbar height",
        ("topbarHeight", "topbar_height"),
        (
            "appShell.topbar.height",
            "appShell.topNav.height",
            "appShell.top-nav.height",
        ),
    ),
    (
        "sidebar width",
        ("sidebarWidth", "sidebar_width"),
        ("appShell.sidebar.width", "appShell.sidebar.expandedWidth"),
    ),
    (
        "sidebar collapsed width",
        ("sidebarCollapsedWidth", "sidebar_collapsed_width"),
        ("appShell.sidebar.collapsedWidth",),
    ),
)
EVIDENCE_MODES = {"source+screenshot", "source-only", "screenshot-only", "url", "brief"}
GENERIC_PREVIEW_TERMS = (
    "customer_order",
    "table management",
    "data platform",
    "asset management",
    "governance",
    "ops",
    "数据治理",
    "数据同步",
    "标签工厂",
    "元数据管理",
    "客户同步任务",
    "订单实时采集",
    "资产标准校验",
    "数据管道示例",
    "T-2024-001",
    "ODS_CASE_AR",
    "TDM_MODEL",
    "DW_ETL_FLOW",
    "ARCHIVE_2024",
    "MySQL 8.0",
)
ZH_PLACEHOLDER_TERMS = (
    "design system typography sample",
    "primary action",
    "secondary action",
    "disabled action",
    "field label",
    "prototype example",
    "filter",
    "tree table",
    "standard list",
    "tree master detail",
    "dashboard overview",
    "save",
    "success",
    "10 / page",
)

# 表示第 10 章不自洽的模式：只引用 DESIGN_GAPS.md。
GAPS_ONLY_PATTERNS = (
    r"详见\s*DESIGN_GAPS",
    r"详见\s*`DESIGN_GAPS\.md`",
    r"参见\s*DESIGN_GAPS",
    r"请查看\s*DESIGN_GAPS",
    r"see\s+DESIGN_GAPS",
    r"refer to\s+DESIGN_GAPS",
)


def load_yaml(text: str) -> dict[str, Any]:
    try:
        import yaml  # type: ignore
    except Exception:
        return parse_simple_yaml(text)

    data = yaml.safe_load(text) or {}
    if not isinstance(data, dict):
        return {}
    return data


def parse_scalar(value: str) -> Any:
    value = value.strip()
    if not value:
        return {}
    if (value.startswith('"') and value.endswith('"')) or (
        value.startswith("'") and value.endswith("'")
    ):
        return value[1:-1]
    if value.startswith("[") and value.endswith("]"):
        inner = value[1:-1].strip()
        if not inner:
            return []
        return [parse_scalar(item.strip()) for item in inner.split(",")]
    if value in {"[]", "{}"}:
        return [] if value == "[]" else {}
    if value.lower() in {"true", "false"}:
        return value.lower() == "true"
    if re.fullmatch(r"-?\d+", value):
        try:
            return int(value)
        except ValueError:
            return value
    return value


def parse_simple_yaml(text: str) -> dict[str, Any]:
    """解析生成的 DESIGN.md 使用的 YAML 子集。"""
    return parse_simple_yaml_fallback(text)


def extract_front_matter(content: str) -> tuple[dict[str, Any] | None, str]:
    if not content.startswith("---\n"):
        return None, content
    # 查找独立成行的 closing ---，不能把 YAML 注释或正文字符串里的 --- 当成结束符。
    idx = content.find("\n", 4)  # 跳过开头的 "---\n"
    while idx != -1:
        nl = content.find("\n", idx + 1)
        line = content[idx : nl if nl != -1 else len(content)].strip()
        if line == "---":
            front_matter = content[4:idx]
            body = content[nl + 1 :] if nl != -1 else ""
            return normalize_design_data(load_yaml(front_matter)), body
        idx = nl
    return None, content


def raw_front_matter_text(content: str) -> str:
    if not content.startswith("---\n"):
        return ""
    idx = content.find("\n", 4)
    while idx != -1:
        nl = content.find("\n", idx + 1)
        line = content[idx : nl if nl != -1 else len(content)].strip()
        if line == "---":
            return content[4:idx]
        idx = nl
    return ""


def has_unquoted_hash_value(line: str) -> bool:
    """检测 YAML 标量值中会被解析成注释的未加引号 #。"""
    if ":" not in line or line.lstrip().startswith("#"):
        return False
    in_single = False
    in_double = False
    for index, char in enumerate(line):
        if char == "'" and not in_double:
            in_single = not in_single
        elif char == '"' and not in_single:
            in_double = not in_double
        elif char == "#" and not in_single and not in_double:
            before = line[:index]
            after = line[index + 1 :]
            if ":" not in before:
                return False
            value_prefix = before.split(":", 1)[1]
            if value_prefix.strip() and re.match(r"[0-9a-zA-Z]", after.strip()):
                return True
    return False


def unquoted_hash_lines(front_matter_text: str) -> list[int]:
    return [
        index
        for index, line in enumerate(front_matter_text.splitlines(), 1)
        if has_unquoted_hash_value(line)
    ]


def has_placeholder(content: str) -> bool:
    lowered = content.lower()
    return any(marker in lowered for marker in PLACEHOLDER_MARKERS)


def resolve_design_md(
    design_dir: Path,
    requested_name: str,
    errors: list[str],
) -> Path | None:
    exact_entries = {
        entry.name: entry for entry in design_dir.iterdir() if entry.is_file()
    }

    if requested_name != "auto":
        path = exact_entries.get(requested_name)
        if path is None:
            errors.append(f"缺少必需文件：{requested_name}")
            return None
        other = "design.md" if requested_name == "DESIGN.md" else "DESIGN.md"
        if other in exact_entries:
            errors.append("DESIGN.md 和 design.md 同时存在。请只保留一个 Markdown 单一事实源文件。")
        return path

    present = [name for name in SUPPORTED_MARKDOWN_FILES if name in exact_entries]
    if not present:
        errors.append("缺少必需 Markdown 设计文件：DESIGN.md 或 design.md")
        return None
    if len(present) > 1:
        errors.append("DESIGN.md 和 design.md 同时存在。请只保留一个 Markdown 单一事实源文件。")
        return None
    return exact_entries[present[0]]


def validate_mapping_key(
    data: dict[str, Any],
    key: str,
    errors: list[str],
    warnings: list[str],
) -> None:
    value = data.get(key)
    if value is None:
        return
    if not isinstance(value, dict):
        errors.append(f"Front matter 字段 '{key}' 必须是映射。")
        return
    if not value:
        warnings.append(f"Front matter 字段 '{key}' 为空。")


def collect_token_refs(value: Any) -> list[tuple[str, str]]:
    refs: list[tuple[str, str]] = []
    if isinstance(value, str):
        refs.extend(TOKEN_REF_RE.findall(value))
    elif isinstance(value, dict):
        for child in value.values():
            refs.extend(collect_token_refs(child))
    elif isinstance(value, list):
        for child in value:
            refs.extend(collect_token_refs(child))
    return refs


def has_cjk(text: str) -> bool:
    return bool(re.search(r"[一-鿿]", text))


def canon_section_title(title: str, aliases: dict[str, tuple[str, ...]] | None = None) -> str:
    cleaned = re.sub(r"\s+", " ", title.strip())
    lowered = cleaned.lower()
    alias_table = aliases if aliases is not None else V3_SECTION_ALIASES
    for canonical, alias_list in alias_table.items():
        if lowered == canonical.lower() or any(alias == lowered for alias in alias_list):
            return canonical
        if canonical.lower() in lowered:
            return canonical
        if any(alias in lowered for alias in alias_list if has_cjk(alias)):
            return canonical
    return cleaned


def cjk_ratio(text: str) -> float:
    content = re.sub(r"`[^`]*`", "", text)
    letters = re.findall(r"[A-Za-z一-鿿]", content)
    if not letters:
        return 0.0
    cjk = [char for char in letters if has_cjk(char)]
    return len(cjk) / len(letters)


def visible_html_text(html_text: str) -> str:
    """返回生成 HTML 页面中的规范化可见文本。"""
    without_nonvisible = re.sub(
        r"<(?:style|script)\b[^>]*>.*?</(?:style|script)>",
        " ",
        html_text,
        flags=re.I | re.S,
    )
    without_tags = re.sub(r"<[^>]+>", " ", without_nonvisible)
    return re.sub(r"\s+", " ", without_tags).strip().lower()


def collect_text(value: Any) -> str:
    if isinstance(value, dict):
        return " ".join(
            part for key, child in value.items() for part in (str(key), collect_text(child)) if part
        )
    if isinstance(value, list):
        return " ".join(collect_text(item) for item in value)
    if value is None:
        return ""
    return str(value)


def iter_items(value: Any) -> list[tuple[str, Any]]:
    if isinstance(value, dict):
        return [(str(key), item) for key, item in value.items()]
    if isinstance(value, list):
        return [(str(index + 1), item) for index, item in enumerate(value)]
    if value in (None, "", [], {}):
        return []
    return [("item", value)]


def validate_unified_front_matter(
    front_matter: dict[str, Any],
    errors: list[str],
    warnings: list[str],
) -> None:
    """校验统一可执行设计 front matter 契约。"""
    if not is_unified_schema(front_matter):
        return

    for key in REQUIRED_UNIFIED_KEYS:
        if key not in front_matter:
            errors.append(f"统一 front matter 缺少必需字段：{key}")
            continue
        if key in ALLOW_EMPTY_UNIFIED_KEYS:
            continue
        value = front_matter.get(key)
        if value in (None, {}, [], ""):
            errors.append(f"统一 front matter 缺少必需字段或字段值：{key}")

    blocked_values = ("unknown", "unavailable", "unverified", "todo", "must_replace")
    blocked_paths: list[str] = []

    def walk(value: Any, path: str) -> None:
        if isinstance(value, dict):
            for child_key, child in value.items():
                walk(child, f"{path}.{child_key}" if path else str(child_key))
            return
        if isinstance(value, list):
            for index, child in enumerate(value):
                walk(child, f"{path}[{index}]")
            return
        if isinstance(value, str):
            lowered = value.strip().lower()
            if lowered in blocked_values or any(marker in lowered for marker in ("must_replace", "{{")):
                blocked_paths.append(path)

    for root in ("product", "technology", "tokens", "layout", "components", "pageTemplates", "generationRules"):
        walk(front_matter.get(root), root)

    if blocked_paths:
        errors.append(
            "统一 front matter 包含不可执行占位符或 unknown 值："
            + ", ".join(blocked_paths[:8])
            + (", ..." if len(blocked_paths) > 8 else "")
        )

    evidence_text = collect_text(front_matter.get("evidence")).lower()
    if any(term in evidence_text for term in ("recommended-default", "inferred")):
        decisions = mapping(mapping(front_matter, "evidence"), "decisions")
        decisions_text = collect_text(mapping(front_matter, "evidence").get("decisions")).lower()
        if "rationale" not in decisions_text and not decisions:
            warnings.append(
                "统一 front matter 使用了 inferred/recommended 决策；evidence.decisions 应包含原型安全默认值的理由。"
            )

    for key, item in iter_items(front_matter.get("openQuestions")):
        text = collect_text(item).lower()
        compact = re.sub(r"\s+", "", text)
        has_decision_or_fallback = (
            "currentdecision" in compact
            or "fallbackrule" in compact
            or "current decision" in text
            or "fallback rule" in text
            or "当前" in text
            or "兜底" in text
            or "默认处理" in text
            or "回退" in text
        )
        if not has_decision_or_fallback:
            warnings.append(
                f"openQuestions.{key} 应包含 currentDecision 或 fallbackRule，避免阻塞下游原型生成。"
            )


def mapping(value: Any, key: str) -> dict[str, Any]:
    if not isinstance(value, dict):
        return {}
    child = value.get(key, {})
    return child if isinstance(child, dict) else {}


def first_text(*values: Any) -> str:
    for value in values:
        if value is None:
            continue
        text = str(value).strip()
        if text:
            return text
    return ""


def slugify(text: str) -> str:
    text = re.sub(r"[\s_]+", "-", str(text or "").strip().lower())
    text = re.sub(r"[^a-z0-9\-]+", "-", text)
    text = re.sub(r"-{2,}", "-", text).strip("-")
    return text or "template"


def page_template_keys(front_matter: dict[str, Any]) -> set[str]:
    raw = front_matter.get("pageTemplates")
    items: list[Any]
    if isinstance(raw, list):
        items = raw
    elif isinstance(raw, dict):
        items = list(raw.values())
    else:
        items = []
    keys: set[str] = set()
    for item in items:
        if not isinstance(item, dict):
            continue
        key = first_text(item.get("key"), item.get("id"))
        raw_name = first_text(item.get("name"), item.get("title"))
        if raw_name:
            keys.add(str(raw_name))
        if not key:
            key = slugify(raw_name)
        if key:
            keys.add(str(key))
    return keys


def page_template_has_representative(front_matter: dict[str, Any]) -> bool:
    raw = front_matter.get("pageTemplates")
    items: list[Any]
    if isinstance(raw, list):
        items = raw
    elif isinstance(raw, dict):
        items = list(raw.values())
    else:
        items = []
    for item in items:
        if not isinstance(item, dict):
            continue
        sections_value = item.get("sections", item.get("structure"))
        if isinstance(sections_value, list) and sections_value:
            return True
        if isinstance(sections_value, str) and sections_value.strip():
            return True
    return False


def guess_archetype(text: str) -> str:
    text = str(text or "").strip().lower()
    if text.startswith("custom:"):
        return text
    if any(term in text for term in ("content-resource-portal", "资源门户", "资源库", "数字资源", "文化内容", "档案", "专题展", "媒体资料库", "资源展示", "素材库")):
        return "content-resource-portal"
    if any(term in text for term in ("brand-portfolio", "作品集", "个人品牌", "creator", "portfolio", "brand-site", "brand site", "personal brand")):
        return "brand-portfolio"
    if any(term in text for term in ("marketing-site", "landing", "pricing", "cta", "营销", "落地页", "官网")):
        return "marketing-site"
    if any(term in text for term in ("mobile-app", "mobile app", "移动端", "tabbar", "ios", "android")):
        return "mobile-app"
    if any(term in text for term in ("data-screen", "大屏", "全屏", "指挥", "告警", "实时状态")):
        return "data-screen"
    if any(term in text for term in ("aigc-workbench", "aigc", "prompt", "提示词", "参数面板", "结果预览", "任务历史", "ai 生成")):
        return "aigc-workbench"
    if any(term in text for term in ("chat-agent", "copilot", "对话", "聊天", "assistant", "客服", "知识问答")):
        return "chat-agent"
    if any(term in text for term in ("docs-portal", "documentation", "开发者中心", "api 文档", "文档站", "docs")):
        return "docs-portal"
    if any(term in text for term in ("map-geospatial", "地图", "图层", "点位", "空间分析", "gis", "geospatial")):
        return "map-geospatial"
    if any(term in text for term in ("file-asset-manager", "素材管理", "文件库", "上传", "版本管理", "asset manager")):
        return "file-asset-manager"
    if any(term in text for term in ("settings-admin", "设置中心", "账号", "组织", "权限", "计费", "billing")):
        return "settings-admin"
    if any(term in text for term in ("enterprise-admin", "后台", "管理", "crud", "审批", "配置", "表管理")):
        return "enterprise-admin"
    if any(term in text for term in ("analytics-dashboard", "dashboard", "analytics", "metric", "chart", "仪表盘", "指标", "趋势")):
        return "analytics-dashboard"
    return ""

def front_matter_archetype(front_matter: dict[str, Any] | None) -> str:
    if not isinstance(front_matter, dict):
        return ""
    explicit = " ".join(
        str(front_matter.get(key, "")).strip().lower()
        for key in ("productType", "interfaceArchetype", "description")
    )
    if any(
        term in explicit
        for term in (
            "brand-editorial",
            "brand editorial",
            "brand-site",
            "brand site",
            "portfolio",
            "creator",
            "个人品牌",
            "作品集",
            "创作者",
            "落地页",
        )
    ):
        return "brand-portfolio"
    if any(term in explicit for term in ("marketing-site", "marketing", "landing")):
        return "marketing"
    if any(term in explicit for term in ("enterprise-admin", "enterprise admin", "admin")):
        return "enterprise-admin"
    if any(term in explicit for term in ("dashboard", "analytics")):
        return "dashboard"
    return ""


def css_custom_property_value(raw_content: str, name: str) -> str:
    match = re.search(rf"{re.escape(name)}\s*:\s*([^;\"']+)", raw_content, re.I)
    return match.group(1).strip() if match else ""


def css_length_value(value: Any, fallback: str = "") -> str:
    text = str(value or "").strip()
    if not text:
        return fallback
    resolved = text
    if re.fullmatch(r"-?\d+(?:\.\d+)?", resolved):
        return "0" if float(resolved) == 0 else f"{resolved}px"
    return resolved


def resolve_front_matter_refs(front_matter: dict[str, Any], value: Any) -> str:
    text = str(value or "").strip()
    if not text:
        return ""

    def repl(match: re.Match[str]) -> str:
        namespace, token_name = match.groups()
        current: Any = front_matter.get(namespace)
        for part in token_name.split("."):
            if isinstance(current, dict) and part in current:
                current = current[part]
            else:
                return match.group(0)
        return str(current)

    return TOKEN_REF_RE.sub(repl, text)


def expected_shell_tokens(front_matter: dict[str, Any] | None) -> dict[str, str]:
    if not isinstance(front_matter, dict):
        return {}
    colors = mapping(front_matter, "colors")
    layout_rules = mapping(front_matter, "layoutRules")
    layout_root = mapping(front_matter, "layout")
    app_shell = mapping(layout_rules, "appShell") or mapping(layout_root, "appShell")
    topbar = (
        mapping(app_shell, "topbar")
        or mapping(app_shell, "topBar")
        or mapping(app_shell, "topNav")
    )
    sidebar = mapping(app_shell, "sidebar")
    tags_view = mapping(app_shell, "tagsBar") or mapping(app_shell, "tags") or mapping(app_shell, "tagsView")
    result = {
        "topbar_bg": first_text(
            topbar.get("background"),
            topbar.get("backgroundColor"),
            colors.get("top-nav-bg"),
            colors.get("shellTopbar"),
        ),
        "topbar_height": css_length_value(first_text(topbar.get("height"))),
        "sidebar_width": css_length_value(first_text(sidebar.get("expandedWidth"), sidebar.get("width"))),
        "sidebar_bg": first_text(sidebar.get("background"), sidebar.get("backgroundColor"), colors.get("shellSidebar")),
        "tags_height": css_length_value(first_text(tags_view.get("height"))),
        "tags_bg": first_text(tags_view.get("background"), tags_view.get("backgroundColor")),
    }
    return {key: resolve_front_matter_refs(front_matter, value) for key, value in result.items()}


def evidence_mode(front_matter: dict[str, Any] | None) -> str:
    if not isinstance(front_matter, dict):
        return ""
    evidence = front_matter.get("evidence") if isinstance(front_matter.get("evidence"), dict) else {}
    runtime = front_matter.get("runtime") if isinstance(front_matter.get("runtime"), dict) else {}
    mode = ""
    if isinstance(evidence, dict):
        mode = str(evidence.get("mode", "")).strip().lower()
    if not mode and isinstance(runtime, dict):
        mode = str(runtime.get("evidenceMode", "")).strip().lower()
    return mode


def is_extraction_backed(front_matter: dict[str, Any] | None) -> bool:
    return evidence_mode(front_matter) in {"url", "source-only", "source+screenshot"}


def normalize_literal(value: Any) -> str:
    """规范化颜色/数字字面量，用于重复检测。"""
    if value is None:
        return ""
    text = str(value).strip().lower()
    text = re.sub(r"\s+", "", text)
    if text.endswith("px"):
        try:
            number = float(text[:-2])
            if number.is_integer():
                return str(int(number))
            return str(number)
        except ValueError:
            return text
    return text


def nested_get(data: dict[str, Any], dotted_path: str) -> Any:
    current: Any = data
    for part in dotted_path.split("."):
        if not isinstance(current, dict) or part not in current:
            return None
        current = current[part]
    return current


def first_color_key(colors: dict[str, Any], candidates: tuple[str, ...]) -> str | None:
    for key in candidates:
        if key in colors:
            return key
    return None


def collect_hex_literals(value: Any) -> set[str]:
    found: set[str] = set()
    if isinstance(value, str):
        found.update(match.group(0).lower() for match in HEX_COLOR_RE.finditer(value))
    elif isinstance(value, dict):
        for child in value.values():
            found.update(collect_hex_literals(child))
    elif isinstance(value, list):
        for child in value:
            found.update(collect_hex_literals(child))
    return found


def typography_font_family_values(typography: dict[str, Any]) -> list[str]:
    stacks: list[str] = []
    for role in typography.values():
        if not isinstance(role, dict):
            continue
        family = role.get("fontFamily")
        if isinstance(family, str) and family.strip():
            stacks.append(family.strip())
    return stacks


def validate_front_matter_dedup(
    front_matter: dict[str, Any] | None,
    errors: list[str],
    warnings: list[str],
) -> None:
    """检测 v2/v3 front matter 块之间的重复字面量（见 references/front-matter-dedup-rules.md）。"""
    if not isinstance(front_matter, dict):
        return

    colors = mapping(front_matter, "colors")
    rec = mapping(front_matter, "recommendedTokens")
    rec_colors = mapping(rec, "color")
    if colors and rec_colors:
        for rec_key, color_candidates in RECOMMENDED_TO_COLORS.items():
            if rec_key not in rec_colors:
                continue
            rec_value = rec_colors[rec_key]
            rec_norm = normalize_literal(rec_value)
            if not rec_norm or TOKEN_REF_RE.search(str(rec_value)):
                continue
            color_key = first_color_key(colors, color_candidates)
            if not color_key:
                continue
            color_value = colors[color_key]
            color_norm = normalize_literal(color_value)
            if not color_norm or TOKEN_REF_RE.search(str(color_value)):
                continue
            if rec_norm == color_norm:
                warnings.append(
                    "[dedup-colors-recommended] recommendedTokens.color."
                    f"{rec_key} duplicates colors.{color_key} ({rec_value!r}); "
                    "omit the recommendedTokens entry or use a {colors.*} reference."
                )
            else:
                errors.append(
                    "[dedup-conflicting-literals] recommendedTokens.color."
                    f"{rec_key} ({rec_value!r}) conflicts with colors.{color_key} ({color_value!r})."
                )

    rec_layout = mapping(rec, "layout")
    layout_rules = mapping(front_matter, "layoutRules")
    if rec_layout and layout_rules:
        for label, rec_keys, layout_paths in LAYOUT_DIMENSION_SLOTS:
            rec_value = first_text(*(rec_layout.get(key) for key in rec_keys))
            layout_value = first_text(
                *(nested_get(layout_rules, path) for path in layout_paths)
            )
            rec_norm = normalize_literal(rec_value)
            layout_norm = normalize_literal(layout_value)
            if not rec_norm or not layout_norm:
                continue
            if rec_norm == layout_norm:
                warnings.append(
                    f"[dedup-layout-dimensions] {label} ({rec_value!r}) is duplicated in "
                    "recommendedTokens.layout and layoutRules.appShell; keep one authoritative value."
                )
            elif rec_norm != layout_norm:
                errors.append(
                    f"[dedup-conflicting-literals] {label}: recommendedTokens.layout "
                    f"({rec_value!r}) conflicts with layoutRules ({layout_value!r})."
                )

    product_type = slugify(str(front_matter.get("productType", "")))
    interface_archetype = slugify(str(front_matter.get("interfaceArchetype", "")))
    if product_type and interface_archetype and product_type == interface_archetype:
        warnings.append(
            "[dedup-archetype-labels] productType and interfaceArchetype normalize to the same "
            f"value ({product_type!r}); use a descriptive interfaceArchetype string."
        )

    page_patterns = front_matter.get("pagePatterns")
    page_templates = front_matter.get("pageTemplates")
    if isinstance(page_patterns, dict) and page_patterns and isinstance(page_templates, list) and page_templates:
        warnings.append(
            "[dedup-page-patterns] Both pagePatterns and pageTemplates are populated; "
            "prefer pageTemplates as the authoritative page skeleton and trim pagePatterns to refs/evidence."
        )

    prototype_rules = collect_text(front_matter.get("prototypeRules")).strip()
    ai_rules = collect_text(front_matter.get("aiGenerationRules")).strip()
    if len(prototype_rules) > 40 and len(ai_rules) > 40:
        warnings.append(
            "[dedup-generation-rules] prototypeRules and aiGenerationRules both carry long rule text; "
            "merge into aiGenerationRules and keep prototypeRules as a one-line v2 summary if needed."
        )

    evidence = mapping(front_matter, "evidence")
    conflict_channels = 0
    conflict_blob = " ".join(
        [
            collect_text(evidence.get("knownConflicts")),
            collect_text(front_matter.get("conflicts")),
            collect_text(front_matter.get("unresolvedItems")),
            collect_text(front_matter.get("legacyTokens")),
        ]
    ).lower()
    topbar_markers = ("#001d66", "#002766", "topbar", "顶栏")
    if any(marker in conflict_blob for marker in topbar_markers):
        if evidence.get("knownConflicts"):
            conflict_channels += 1
        if front_matter.get("conflicts"):
            conflict_channels += 1
        if front_matter.get("unresolvedItems"):
            conflict_channels += 1
        legacy_notes = collect_text(front_matter.get("legacyTokens")).lower()
        if any(marker in legacy_notes for marker in topbar_markers):
            conflict_channels += 1
        if conflict_channels >= 3:
            warnings.append(
                "[dedup-conflict-channels] The topbar color conflict is recorded in "
                f"{conflict_channels} front matter channels; consolidate detail under unresolvedItems."
            )

    evidence_conf = normalize_literal(evidence.get("confidence"))
    confidence = mapping(front_matter, "confidence")
    overall_conf = normalize_literal(confidence.get("overall"))
    if evidence_conf and overall_conf and evidence_conf != overall_conf:
        warnings.append(
            f"[dedup-confidence-mismatch] evidence.confidence ({evidence.get('confidence')!r}) "
            f"differs from confidence.overall ({confidence.get('overall')!r}); keep dimensional confidence only."
        )

    components = mapping(front_matter, "components")
    component_recipes = mapping(front_matter, "componentRecipes")
    if components and component_recipes:
        component_hex = collect_hex_literals(components)
        recipe_hex = collect_hex_literals(component_recipes)
        shared_hex = sorted(component_hex & recipe_hex)
        if shared_hex:
            warnings.append(
                "[dedup-component-color-literals] Hex values appear in both components and "
                f"componentRecipes ({', '.join(shared_hex[:4])}); prefer token refs in components."
            )

    typography = mapping(front_matter, "typography")
    font_stacks = typography_font_family_values(typography)
    if len(font_stacks) >= 3 and len(set(font_stacks)) == 1 and len(font_stacks[0]) > 40:
        warnings.append(
            "[dedup-typography-font-stack] typography roles repeat the same fontFamily string; "
            "use a YAML anchor or a shared fontFamilyDefault key."
        )


def validate_shell_front_matter_consistency(
    front_matter: dict[str, Any] | None,
    warnings: list[str],
) -> None:
    if not isinstance(front_matter, dict):
        return
    evidence = mapping(front_matter, "evidence")
    runtime = mapping(front_matter, "runtime")
    layout_state = mapping(runtime, "layoutState")
    expected = expected_shell_tokens(front_matter)

    evidence_mode = str(evidence.get("mode", "")).strip().lower()
    if evidence_mode in {"source+screenshot", "source-only"}:
        approximate_shell_keys = []
        for key, value in layout_state.items():
            key_text = str(key).lower()
            value_text = str(value)
            if not any(term in key_text for term in ("sidebar", "top", "tag", "tab", "width", "height")):
                continue
            if "~" in value_text or "约" in value_text or "approx" in value_text.lower():
                approximate_shell_keys.append(str(key))
        if approximate_shell_keys:
            warnings.append(
                "runtime.layoutState keeps approximate shell dimensions in a source-backed output "
                f"({', '.join(approximate_shell_keys[:4])}); prefer exact source/computed-style values."
            )

    runtime_shell = str(layout_state.get("shell", ""))
    tags_bg = expected.get("tags_bg", "")
    if runtime_shell and tags_bg:
        match = re.search(r"(?:标签页|页签|tags?|tabs?)[^#]{0,28}(#[0-9a-fA-F]{3,8})", runtime_shell)
        if match and match.group(1).lower() != tags_bg.lower():
            warnings.append(
                "runtime.layoutState.shell describes a tags/tab background that disagrees with "
                f"layoutRules.appShell.tagsView.backgroundColor ({match.group(1)} vs {tags_bg})."
            )


def validate_token_refs(data: dict[str, Any], errors: list[str]) -> None:
    ref_source = data if is_unified_schema(data) else data.get("components", {})
    for namespace, token_name in collect_token_refs(ref_source):
        namespace_data = data.get(namespace)
        if not isinstance(namespace_data, dict):
            errors.append(
                f"Component references undefined token namespace: {{{namespace}.{token_name}}}"
            )
            continue
        current: Any = namespace_data
        for part in token_name.split("."):
            if not isinstance(current, dict) or part not in current:
                errors.append(f"Component references undefined token: {{{namespace}.{token_name}}}")
                break
            current = current[part]


def has_token_role(tokens: dict[str, Any], *terms: str) -> bool:
    for key, value in tokens.items():
        key_text = str(key).lower()
        role_text = ""
        if isinstance(value, dict):
            role_text = " ".join(
                str(value.get(role_key, "")).lower()
                for role_key in ("role", "usage", "description")
            )
            if has_token_role(value, *terms):
                return True
        if any(term in key_text or term in role_text for term in terms):
            return True
    return False


def has_flat_token_alias(tokens: dict[str, Any], *names: str) -> bool:
    """仅当一级 token alias 存在时返回 true。

    渲染器支持嵌套分组，但 DESIGN.md 应暴露扁平语义 alias 层，
    让下游 AI 工具不必了解本技能的分组约定即可使用文件。
    """
    for name in names:
        if name in tokens:
            return True
    return False


def validate_evidence_awareness(
    front_matter: dict[str, Any],
    body: str,
    errors: list[str],
    warnings: list[str],
) -> None:
    evidence = front_matter.get("evidence")
    mode = ""
    sources: Any = None

    if isinstance(evidence, dict):
        mode = str(evidence.get("mode", "")).strip().lower()
        if mode and mode not in EVIDENCE_MODES:
            warnings.append("evidence.mode 应为以下值之一：" + ", ".join(sorted(EVIDENCE_MODES)) + "。")
        if not evidence.get("confidence"):
            warnings.append("evidence 应包含 confidence 值。")
        sources = evidence.get("sources")
        if mode != "brief" and not isinstance(sources, dict):
            warnings.append("非 brief 证据模式下，evidence.sources 应列出源码文件、截图或 URL。")
    else:
        warnings.append(
            "新的 Design.md 产物应包含 evidence mode 和 confidence，便于下游判断原型保真度。"
        )

    runtime = front_matter.get("runtime")
    if mode in {"source+screenshot", "url"} and not isinstance(runtime, dict):
        warnings.append("source+screenshot 或 URL 派生产物应在 runtime 中记录 active theme/layout state。")

    component_mappings = front_matter.get("componentMappings")
    components = front_matter.get("components")
    has_components = isinstance(components, dict) and bool(components)
    if (
        mode in {"source+screenshot", "source-only", "url"}
        and not has_components
        and not isinstance(component_mappings, dict)
    ):
        warnings.append(
            "源码派生产物应在 components 下记录源码到原型的组件映射。"
        )

    page_patterns = front_matter.get("pagePatterns")
    patterns = front_matter.get("patterns")
    page_templates = front_matter.get("pageTemplates")
    has_page_patterns = isinstance(page_patterns, dict) and bool(page_patterns)
    has_patterns = isinstance(patterns, dict) and bool(patterns)
    has_page_templates = (
        isinstance(page_templates, list) and bool(page_templates)
        or isinstance(page_templates, dict) and bool(page_templates)
    )
    if mode in {"source+screenshot", "source-only", "url"} and not (
        has_page_templates or has_page_patterns or has_patterns
    ):
        warnings.append("源码派生产物应包含可复用 pageTemplates。")

    body_lower = body.lower()
    confidence = front_matter.get("confidence", {})
    confidence_map = confidence if isinstance(confidence, dict) else {}
    confidence_tokens = str(confidence_map.get("tokens", "")).strip().lower()
    confidence_components = str(confidence_map.get("components", "")).strip().lower()
    confidence_page_templates = str(confidence_map.get("pageTemplates", "")).strip().lower()
    assumptions_text = collect_text(front_matter.get("assumptions")).strip()
    known_limits_text = collect_text(front_matter.get("knownLimits")).strip()
    evidence_text = collect_text(evidence).strip() if isinstance(evidence, dict) else ""
    combined_evidence_text = " ".join(
        part for part in (evidence_text, assumptions_text, known_limits_text) if part
    ).lower()
    if mode in {"source-only", "source+screenshot", "url"}:
        says_no_screenshot = any(
            term in combined_evidence_text or term in body_lower
            for term in ("未使用浏览器截图", "未使用截图", "未验证截图", "without screenshot", "no screenshot")
        )
        if says_no_screenshot and front_matter.get("unobservedScreenshots") is False:
            warnings.append(
                "unobservedScreenshots=false 与“未观察截图”的说明冲突；请使用 screenshotsObserved=false 或 unobservedScreenshots=true。"
            )

    if mode == "brief":
        if not assumptions_text:
            warnings.append("brief 模式产物必须包含 assumptions，用于解释合成设计决策。")
        if isinstance(sources, dict) and not sources.get("inferredFrom") and not assumptions_text:
            warnings.append("brief 模式的 evidence.sources 应包含 inferredFrom 条目或 assumptions。")
        consultation = front_matter.get("briefConsultation")
        if not isinstance(consultation, dict):
            errors.append(
                "brief 模式 DESIGN.md 必须包含带确认状态的 briefConsultation。"
            )
        else:
            status = str(consultation.get("status", "")).strip().lower()
            approved_by = str(consultation.get("approvedBy", "")).strip()
            proposal_summary = str(consultation.get("proposalSummary", "")).strip()
            skip_reason = str(consultation.get("skipReason", "")).strip()
            allowed_statuses = {"approved", "skipped", "not-required"}
            allowed_approvers = {
                "user",
                "explicit-brief",
                "non-interactive",
                "batch-generation",
                "ci",
                "automation",
                "unattended",
                "previous-design",
                "not-applicable",
            }
            explicit_noninteractive_terms = (
                "non-interactive",
                "noninteractive",
                "batch",
                "batch-generation",
                "ci",
                "unattended",
                "headless",
                "automation",
                "automated",
                "no-question",
                "no questions",
                "without asking",
                "skip confirmation",
                "skip-confirmation",
                "do not ask",
                "don't ask",
                "just generate",
                "directly generate",
                "用户明确要求不确认",
                "用户明确要求跳过确认",
                "用户明确要求直接生成",
                "用户明确要求不要询问",
                "用户明确要求无需确认",
                "不询问",
                "不要问",
                "无需确认",
                "跳过确认",
                "直接生成",
                "非交互",
                "批量生成",
                "自动化",
                "无人值守",
            )
            invalid_skip_reason_terms = (
                "product definition",
                "prd",
                "requirements document",
                "requirement document",
                "workflow description",
                "navigation list",
                "layout sketch",
                "user provided a document",
                "user supplied a document",
                "user asked to generate",
                "asked to generate",
                "generate a design system",
                "inferred from",
                "derived from",
                "category conventions",
                "产品定义",
                "需求文档",
                "产品需求",
                "流程描述",
                "导航",
                "布局草图",
                "用户提供文档",
                "用户直接请求",
                "请求生成",
                "生成完整设计系统",
                "根据文档生成",
                "根据产品定义",
                "方向由",
                "推导",
                "品类惯例",
            )
            explicit_visual_terms = (
                "visual direction",
                "visual tone",
                "brand",
                "brand color",
                "primary color",
                "color",
                "palette",
                "typography",
                "font",
                "typeface",
                "density",
                "radius",
                "rounded",
                "shadow",
                "motion",
                "animation",
                "reference product",
                "style reference",
                "风格",
                "视觉方向",
                "视觉气质",
                "品牌",
                "品牌色",
                "主色",
                "颜色",
                "配色",
                "字体",
                "字重",
                "字号",
                "密度",
                "圆角",
                "阴影",
                "动效",
                "参考产品",
                "参考品牌",
            )
            if status not in allowed_statuses:
                errors.append(
                    "briefConsultation.status 必须是 approved、skipped 或 not-required。"
                )
            if not proposal_summary:
                errors.append("brief 模式必须提供 briefConsultation.proposalSummary。")
            if not approved_by:
                errors.append("brief 模式必须提供 briefConsultation.approvedBy。")
            elif approved_by not in allowed_approvers:
                warnings.append(
                    "briefConsultation.approvedBy 建议为以下值之一："
                    + ", ".join(sorted(allowed_approvers))
                    + "."
                )
            if status == "skipped" and not skip_reason:
                errors.append("status 为 skipped 时必须提供 briefConsultation.skipReason。")
            if status == "skipped":
                has_noninteractive_evidence = any(
                    term in skip_reason.lower() for term in explicit_noninteractive_terms
                )
                has_invalid_skip_reason = any(
                    term in skip_reason.lower() for term in invalid_skip_reason_terms
                )
                if not has_noninteractive_evidence:
                    errors.append(
                        "briefConsultation.status=skipped 要求 skipReason 中包含明确的非交互、批量、CI、无人值守、无需提问或用户要求跳过确认的证据。"
                    )
                if has_invalid_skip_reason:
                    errors.append(
                        "briefConsultation.skipReason 不能仅依赖用户提供产品/PRD/需求文档、要求生成，或 Agent 从流程/布局/品类惯例推断方向。"
                    )
            if status == "approved" and approved_by != "user":
                warnings.append("briefConsultation.status=approved 时建议使用 approvedBy=user。")
            if status == "not-required" and approved_by not in {"explicit-brief", "previous-design"}:
                warnings.append(
                    "briefConsultation.status=not-required 通常应使用 approvedBy=explicit-brief 或 previous-design。"
                )
            if status == "not-required" and approved_by == "explicit-brief":
                has_visual_evidence = any(
                    term in combined_evidence_text
                    for term in explicit_visual_terms
                )
                if not has_visual_evidence:
                    errors.append(
                        "briefConsultation.status=not-required 且 approvedBy=explicit-brief 时，必须有明确视觉方向证据，例如颜色、字体、密度、圆角、动效、品牌、风格或参考产品约束。"
                    )
            if status == "skipped" and approved_by not in {"non-interactive", "batch-generation", "ci", "automation", "unattended"}:
                warnings.append(
                    "briefConsultation.status=skipped 通常应使用 approvedBy=non-interactive、batch-generation、ci、automation 或 unattended。"
                )
        high_dims = [
            name
            for name, value in (
                ("confidence.tokens", confidence_tokens),
                ("confidence.components", confidence_components),
                ("confidence.pageTemplates", confidence_page_templates),
            )
            if value == "high"
        ]
        explicit_brief_evidence = any(
            term in combined_evidence_text
            for term in (
                "用户提供",
                "explicit",
                "provided",
                "given",
                "页面规范",
                "素材 url",
                "asset url",
                "颜色",
                "typography",
                "layout",
                "component",
                "组件",
                "动效",
            )
        )
        if high_dims and not explicit_brief_evidence:
            warnings.append(
                "brief 模式产物没有明确品牌或实现证据时，不应把合成设计维度标为 high confidence："
                + ", ".join(high_dims)
                + "."
            )

    if mode == "screenshot-only":
        if confidence_tokens == "high":
            warnings.append("screenshot-only 产物不能把 confidence.tokens 标为 high。")
        approximation_text = " ".join(
            [
                body_lower,
                collect_text(front_matter.get("colors")).lower(),
                collect_text(front_matter.get("typography")).lower(),
                collect_text(front_matter.get("spacing")).lower(),
                collect_text(front_matter.get("rounded")).lower(),
                assumptions_text.lower(),
                known_limits_text.lower(),
            ]
        )
        if not any(term in approximation_text for term in ("approx", "approximate", "inferred", "近似", "估算", "推断")):
            warnings.append("screenshot-only 产物应明确将 token 值标为 approximate 或 inferred。")

    typography_text = collect_text(front_matter.get("typography")).lower()
    if "inter" in typography_text and "inter" not in combined_evidence_text:
        warnings.append("Typography 无证据或明确假设就使用 Inter；请补充依据或替换。")

    if mode not in {"", "brief"}:
        generic_color_values = {"#2563eb", "#1d4ed8", "#111827", "#6b7280", "#f8fafc", "#eef2f7"}
        color_text = collect_text(front_matter.get("colors")).lower()
        leaked_colors = sorted(value for value in generic_color_values if value in color_text)
        if leaked_colors and not any(value in combined_evidence_text for value in leaked_colors):
            warnings.append(
                "Design.md 似乎保留了无证据的脚手架/默认颜色值："
                + ", ".join(leaked_colors[:4])
                + "."
            )

    primary_conflict_terms = (
        ("dark sidebar", "white sidebar"),
        ("dark side bar", "white side bar"),
        ("light sidebar", "dark sidebar"),
    )
    for first, second in primary_conflict_terms:
        if first in body_lower and second in body_lower:
            warnings.append(
                f"发现可能冲突的主主题描述：'{first}' 与 '{second}'。请把备选项放入 DESIGN_GAPS.md。"
            )
            break


def validate_v3_design_md(path: Path, errors: list[str], warnings: list[str]) -> None:
    """校验 ai-design-system-v3 格式（10 章）的 DESIGN.md。"""
    content = path.read_text(encoding="utf-8")
    if has_placeholder(content):
        errors.append(f"{path.name} 仍包含占位文本。")

    hash_lines = unquoted_hash_lines(raw_front_matter_text(content))
    if hash_lines:
        errors.append(
            f"{path.name} YAML front matter 在以下行包含未加引号的 # 值："
            + ", ".join(str(line) for line in hash_lines[:6])
            + "。提到 hex 颜色的 prose 字段需要加引号，否则 YAML 会把 # 后内容当作注释。"
        )

    front_matter, body = extract_front_matter(content)
    if front_matter is None:
        errors.append(f"{path.name} 必须以 Design.md YAML front matter 开头。")
        return

    unified = is_unified_schema(front_matter)
    validate_unified_front_matter(front_matter, errors, warnings)

    # 检查渲染器和校验辅助函数使用的规范化字段。
    for key in REQUIRED_NORMALIZED_KEYS:
        if key not in front_matter:
            errors.append(f"{path.name} front matter 缺少必需字段：{key}")

    for key in REQUIRED_NORMALIZED_KEYS + OPTIONAL_NORMALIZED_KEYS:
        if key in ("version", "name", "description", "language"):
            continue
        validate_mapping_key(front_matter, key, errors, warnings)

    version = str(front_matter.get("version", "")).strip()
    if unified:
        if version not in {"1", "1.0"}:
            warnings.append(f"{path.name} uses version '{version}'. Expected 1 for unified executable output.")
    elif version not in {"2.0", "2", "alpha"}:
        warnings.append(f"{path.name} uses version '{version}'. Expected 2.0 for older output.")

    description = str(front_matter.get("summary") or front_matter.get("description", "")).strip()
    # 80 字符阈值只是“密集可执行摘要”的粗略代理。
    # 中文信息密度约为 ASCII 的 3 倍，所以不能用同一阈值误报中文摘要。
    # 这里按语言 / CJK 比例选择阈值。
    if cjk_ratio(description) >= 0.5:
        min_summary_length = 40
    else:
        min_summary_length = 80
    if len(description) < min_summary_length:
        warnings.append(f"{path.name} summary/description is short; expected a dense executable design-system summary.")

    language = str(front_matter.get("language", "")).strip().lower()
    if language.startswith("zh") and cjk_ratio(description + "\n" + body) < 0.18:
        warnings.append(
            f"{path.name} declares language '{front_matter.get('language')}' but human-facing prose appears mostly non-Chinese."
        )

    # ── v3-specific checks ──

    if not unified:
        # 检查旧版推荐字段
        for key in RECOMMENDED_V3_KEYS:
            if key not in front_matter:
                warnings.append(f"{path.name} front matter missing recommended key: {key}")

        # 检查 recommendedTokens 与 legacyTokens
        rec_tokens = front_matter.get("recommendedTokens", {})
        leg_tokens = front_matter.get("legacyTokens", {})
        if isinstance(rec_tokens, dict) and not rec_tokens:
            warnings.append(f"{path.name} recommendedTokens is empty; should list recommended token values for new pages.")
        if isinstance(leg_tokens, dict) and isinstance(rec_tokens, dict) and rec_tokens and not leg_tokens:
            # 不一定是错误，产品可能没有 legacy tokens。
            pass

    # 检查置信度
    confidence = front_matter.get("confidence", {})
    if isinstance(confidence, dict):
        if not confidence.get("overall"):
            warnings.append(f"{path.name} confidence.overall is missing.")
        if confidence.get("darkMode") in (None, "") and "darkMode" not in confidence:
            warnings.append(f"{path.name} confidence should include darkMode dimension.")
        if confidence.get("mobile") in (None, "") and "mobile" not in confidence:
            warnings.append(f"{path.name} confidence should include mobile dimension.")

    # ── core validations ──
    colors = front_matter.get("colors", {})
    if isinstance(colors, dict):
        if not has_token_role(colors, "primary", "brand", "accent"):
            warnings.append("colors should include a primary/brand/accent role.")
        if not has_token_role(colors, "ink", "text-primary", "text", "body"):
            warnings.append("colors should include an ink/text role.")
        if not has_token_role(colors, "canvas", "surface", "background"):
            warnings.append("colors should include a canvas/surface role.")
        if not has_token_role(colors, "hairline", "border", "stroke"):
            warnings.append("colors should include a hairline/border role.")
        flat_alias_groups = {
            "primary": ("primary", "brand", "accent"),
            "ink": ("ink", "text-primary", "text", "textStrong"),
            "canvas": ("canvas", "surface-canvas"),
            "surface": ("surface-1", "surface", "surface-card"),
            "hairline": ("hairline", "border", "stroke"),
        }
        missing_aliases = [
            label for label, aliases in flat_alias_groups.items()
            if not has_flat_token_alias(colors, *aliases)
        ]
        if missing_aliases:
            warnings.append(
                "colors should expose flat semantic aliases for downstream AI use: "
                + ", ".join(missing_aliases)
                + ". Nested groups may remain as supplemental detail."
            )

    typography = front_matter.get("typography", {})
    if isinstance(typography, dict):
        type_keys = set(typography)
        if not any("display" in key or "heading" in key for key in type_keys):
            warnings.append("typography should include display or heading roles.")
        if not any("body" in key for key in type_keys):
            warnings.append("typography should include a body role.")
        if not any("button" in key or "caption" in key for key in type_keys):
            warnings.append("typography should include button or caption roles.")

    components = front_matter.get("components", {})
    if isinstance(components, dict):
        archetype = front_matter_archetype(front_matter)
        component_names = " ".join(components.keys()).lower()
        if "button" not in component_names:
            warnings.append("components should include button variants.")
        if archetype != "brand-portfolio" and not any(term in component_names for term in ("card", "surface", "panel")):
            warnings.append("components should include card/surface/panel recipes.")
        if archetype != "brand-portfolio" and not any(term in component_names for term in ("input", "field", "form")):
            warnings.append("components should include input/form recipes when relevant.")

    validate_token_refs(front_matter, errors)
    if not unified:
        validate_front_matter_dedup(front_matter, errors, warnings)
    validate_evidence_awareness(front_matter, body, errors, warnings)

    if re.search(r"(图片|image|asset|url)[^。\n]{0,80}(见|see)\s*(原始|original)?\s*(规范|spec|prompt)", body, re.I):
        warnings.append(
            f"{path.name} refers to external/original specs for required assets. "
            "Preserve exact asset URLs/paths in DESIGN.md so downstream tools can reproduce the UI."
        )

    # ── Check 10 chapters ──
    present_sections = {
        canon_section_title(section, V3_SECTION_ALIASES)
        for section in re.findall(r"^##\s+(?:\d+\.\s*)?(.+?)\s*$", body, re.MULTILINE)
    }
    missing_sections = [
        section for section in REQUIRED_V3_SECTIONS if section not in present_sections
    ]
    if missing_sections:
        errors.append(
            f"{path.name} is missing ai-design-system-v3 chapters: " + ", ".join(missing_sections)
        )

    # ── Check Chapter 10 is self-contained ──
    body_lower = body.lower()
    chapter_10_match = re.search(
        r"^##\s+(?:\d+\.\s*)?(?:"
        r"known limits & evidence summary"
        r"|known limits and evidence summary"
        r"|evidence, limits & default decisions"
        r"|evidence limits & default decisions"
        r"|evidence limits and default decisions"
        r"|已知限制与来源摘要"
        r"|已知限制和来源摘要"
        r"|证据、限制与默认决策"
        r"|证据、限制和默认决策"
        r")\s*$",
        body,
        re.MULTILINE | re.IGNORECASE,
    )
    if chapter_10_match:
        # 获取第 10 章内容（从当前标题到下一个 ## 或文件末尾）
        ch10_start = chapter_10_match.end()
        next_heading = re.search(r"^##\s+", body[ch10_start:], re.MULTILINE)
        ch10_end = ch10_start + next_heading.start() if next_heading else len(body)
        ch10_content = body[ch10_start:ch10_end]

        # 检查第 10 章是否只引用 DESIGN_GAPS.md
        stripped = re.sub(r"\s+", "", ch10_content)
        for pattern in GAPS_ONLY_PATTERNS:
            if re.search(pattern, ch10_content):
                # 确认这是否是唯一内容
                if len(stripped) < 200:
                    errors.append(
                        f"{path.name} Chapter 10 (Known Limits) appears to only reference DESIGN_GAPS.md. "
                        "Chapter 10 must provide self-contained default decisions and handling rules."
                    )
                else:
                    warnings.append(
                        f"{path.name} Chapter 10 references DESIGN_GAPS.md — ensure it also provides "
                        "self-contained default decisions."
                    )
                break

        # 检查第 10 章必需小节
        ch10_lower = ch10_content.lower()
        has_source_summary = any(term in ch10_lower for term in ("来源摘要", "evidence summary", "10.1"))
        has_default_decisions = any(term in ch10_lower for term in ("默认决策", "default decision", "10.2"))
        has_unconfirmed = any(term in ch10_lower for term in ("未确认", "unconfirmed", "default handling", "默认处理", "10.3"))
        if not has_source_summary:
            warnings.append(f"{path.name} Chapter 10 should include evidence summary subsection (10.1).")
        if not has_default_decisions:
            warnings.append(f"{path.name} Chapter 10 should include current default decisions subsection (10.2).")
        if not has_unconfirmed:
            warnings.append(f"{path.name} Chapter 10 should include unconfirmed capabilities subsection (10.3).")

    # ── Check Chapter 9 subsections ──
    chapter_9_match = re.search(
        r"^##\s+(?:\d+\.\s*)?(?:"
        r"ai generation rules, forbidden patterns & self-check"
        r"|ai generation rules, forbidden patterns and self-check"
        r"|ai generation rules forbidden patterns & self-check"
        r"|prototype generation rules & self-check"
        r"|prototype generation rules and self-check"
        r"|AI 生成规则、禁止事项与自检清单"
        r"|AI 生成规则 禁止事项与自检清单"
        r"|AI 生成规则、禁止事项和自检清单"
        r"|原型生成规则与自检"
        r"|原型生成规则和自检"
        r")\s*$",
        body,
        re.MULTILINE | re.IGNORECASE,
    )
    if chapter_9_match:
        ch9_start = chapter_9_match.end()
        next_heading = re.search(r"^##\s+", body[ch9_start:], re.MULTILINE)
        ch9_end = ch9_start + next_heading.start() if next_heading else len(body)
        ch9_content = body[ch9_start:ch9_end]

        ch9_sub_terms = [
            ("AI 生成规则", "ai generation rules", "9.1"),
            ("禁止事项", "forbidden patterns", "forbidden rules", "9.2"),
            ("自检清单", "self-check", "self check", "9.3"),
        ]
        for terms in ch9_sub_terms:
            found = any(t.lower() in ch9_content.lower() for t in terms)
            if not found:
                warnings.append(
                    f"{path.name} Chapter 9 should include subsection for: {terms[0]}"
                )

    # ── Check Chapter 4 has legacy token subsection (4.8) ──
    chapter_4_match = re.search(
        r"^##\s+(?:\d+\.\s*)?(?:foundation tokens|基础设计令牌|基础令牌|设计令牌)\s*$",
        body,
        re.MULTILINE | re.IGNORECASE,
    )
    if chapter_4_match:
        ch4_start = chapter_4_match.end()
        next_heading = re.search(r"^##\s+", body[ch4_start:], re.MULTILINE)
        ch4_end = ch4_start + next_heading.start() if next_heading else len(body)
        ch4_content = body[ch4_start:ch4_end]

        legacy_terms = ("legacy token", "冲突 token", "legacy 颜色", "历史变量", "旧变量", "4.8")
        has_legacy = any(t.lower() in ch4_content.lower() for t in legacy_terms)
        if not has_legacy:
            warnings.append(
                f"{path.name} Chapter 4 should include legacy token / conflict token subsection (4.8) "
                "to distinguish deprecated values from recommended tokens."
            )


def body_has_high_impact_items(body: str) -> bool:
    """仅当第 10.4 章列出真实高影响项时返回 true。"""
    match = re.search(r"^###\s+10\.4\s+.*?(?:高影响|high impact).*?$", body, re.I | re.M)
    if not match:
        return False
    tail = body[match.end():]
    next_heading = re.search(r"^#{1,3}\s+", tail, re.M)
    section = tail[: next_heading.start()] if next_heading else tail
    compact = re.sub(r"\s+", "", section).lower()
    if not compact:
        return False
    no_item_terms = (
        "当前没有",
        "暂无",
        "无高影响",
        "无阻塞",
        "none",
        "nohigh-impact",
        "nohighimpact",
    )
    if any(term in compact for term in no_item_terms):
        return False
    for line in section.splitlines():
        stripped = line.strip()
        if not stripped or stripped.startswith("|---") or stripped.startswith("| ID"):
            continue
        if re.match(r"^[-*]\s+\S", stripped) or re.match(r"^\d+\.\s+\S", stripped):
            return True
        if stripped.startswith("|") and stripped.endswith("|"):
            cells = [cell.strip() for cell in stripped.strip("|").split("|")]
            if len(cells) >= 2 and not all(cell in {"", "—", "-"} for cell in cells):
                return True
    return False


def validate_gaps_md(
    path: Path,
    errors: list[str],
    warnings: list[str],
    front_matter: dict[str, Any] | None = None,
    design_body: str = "",
) -> None:
    """Validate DESIGN_GAPS.md structure."""
    if not path.exists():
        errors.append("缺少必需文件：DESIGN_GAPS.md")
        return

    content = path.read_text(encoding="utf-8")
    if has_placeholder(content):
        errors.append(f"{path.name} still contains placeholder text.")

    # 检查标题
    if "DESIGN_GAPS.md" not in content and "设计待确认项与冲突清单" not in content:
        warnings.append(f"{path.name} should use title 'DESIGN_GAPS.md｜设计待确认项与冲突清单'.")

    # 检查必需章节
    present_sections = {
        canon_section_title(section, GAPS_SECTION_ALIASES)
        for section in re.findall(r"^##\s+(?:\d+\.\s*)?(.+?)\s*$", content, re.MULTILINE)
    }
    missing = [s for s in REQUIRED_GAPS_SECTIONS if s not in present_sections]
    if missing:
        errors.append(
            f"{path.name} is missing required sections: " + ", ".join(missing)
        )

    # 校验优先级章节（第 2-4 章）中的 gap 类型标签。
    # 生成文件会使用 generate_gaps_doc.py 中 GAP_TYPES 的中文标签。
    # 同时接受中文标准标签和英文类型标识，覆盖 Agent 编写或人工编辑的 DESIGN_GAPS.md。
    _VALID_GAP_TYPE_LABELS = frozenset({
        "未确认", "估算", "冲突", "推断", "推荐默认", "历史遗留", "未覆盖 / 暂不支持",
        "unconfirmed", "approximate", "conflict", "inferred", "recommended-default",
        "legacy", "unsupported",
    })
    _type_col_errors: list[str] = []
    for sec in re.split(r"^##\s+", content, flags=re.MULTILINE):
        if not sec.strip().startswith(("2.", "3.", "4.", "高优先", "中优先", "低优先")):
            continue
        rows = re.findall(r"^\|(.+)\|[ \t]*$", sec, re.MULTILINE)
        if len(rows) < 2:
            continue
        header_cells = [c.strip() for c in rows[0].split("|")]
        try:
            type_col = next(i for i, h in enumerate(header_cells) if "类型" in h or h.lower() in ("type", "gap type"))
        except StopIteration:
            continue
        for row in rows[2:]:  # skip header and separator
            cells = [c.strip() for c in row.split("|")]
            if type_col >= len(cells):
                continue
            cell_val = cells[type_col].strip()
            if cell_val and cell_val != "—" and cell_val not in _VALID_GAP_TYPE_LABELS:
                _type_col_errors.append(cell_val)
    if _type_col_errors:
        warnings.append(
            f"{path.name} contains unrecognised gap type values: "
            + ", ".join(dict.fromkeys(_type_col_errors))
            + ". Expected: 未确认/估算/冲突/推断/推荐默认/未覆盖/历史遗留/暂不支持."
        )

    # 检查文件不是空壳，并包含最小有效内容
    if len(content) < 500:
        warnings.append(f"{path.name} is very short; ensure it contains meaningful gap analysis.")

    if front_matter:
        high_signal_text = " ".join(
            [
                collect_text(front_matter.get("knownLimits", {})),
                collect_text(front_matter.get("unresolvedItems", {})),
            ]
        )
        has_structured_high_signal = any(
            term in high_signal_text
            for term in ("highImpactPending", "高影响待确认项:", "高影响待确认：")
        )
        has_high_signal = has_structured_high_signal or body_has_high_impact_items(design_body)
        if has_high_signal and "无高优先级待确认项" in content:
            errors.append(
                f"{path.name} says there are no high-priority gaps, but DESIGN.md contains high-impact pending items."
            )

    # ── 检查第 2/3/4 章表格行至少有 4 个非空单元格 ──
    # 查找高/中/低优先级 gap 章节中的表格行
    sections_content = re.split(r"^##\s+", content, flags=re.MULTILINE)
    for sec in sections_content:
        if sec.strip().startswith(("2.", "3.", "4.", "高优先", "中优先", "低优先")):
            table_rows = re.findall(r"^\|(?!.*?---).*?\|.*$", sec, re.MULTILINE)
            for row in table_rows:
                cells = [c.strip() for c in row.split("|") if c.strip()]
                non_empty = sum(1 for c in cells if c not in ("", "-", "—"))
                if non_empty < 4:
                    # 这是填充列过少的内容行。
                    # 仅在至少有 2 个单元格时提示，避免误报表头行。
                    if len(cells) >= 3 and len(cells) != non_empty:
                        warnings.append(
                            f"{path.name} has a gap table row with only {non_empty}/{len(cells)} columns filled. "
                            f"Row content: {row.strip()[:80]}"
                        )
                        break  # avoid spam


def validate_stitch_alpha_design_md(path: Path, errors: list[str], warnings: list[str]) -> None:
    content = path.read_text(encoding="utf-8")
    if has_placeholder(content):
        errors.append(f"{path.name} still contains placeholder text.")

    front_matter, body = extract_front_matter(content)
    if front_matter is None:
        errors.append(f"{path.name} must start with stitch-alpha YAML front matter.")
        return

    for key in REQUIRED_STITCH_ALPHA_KEYS:
        if key not in front_matter:
            errors.append(f"{path.name} front matter missing required key: {key}")

    for key in REQUIRED_STITCH_ALPHA_KEYS + OPTIONAL_STITCH_ALPHA_KEYS:
        if key in ("version", "name", "description", "language", "format"):
            continue
        validate_mapping_key(front_matter, key, errors, warnings)

    extra_v2_keys = [
        key for key in ("evidence", "runtime", "componentMappings", "pagePatterns", "prototypeRules", "patterns", "motion")
        if key in front_matter
    ]
    if extra_v2_keys:
        warnings.append(
            f"{path.name} front matter includes unified/v3 keys not used in stitch-alpha: "
            + ", ".join(extra_v2_keys)
            + ". Consider switching to --format ai-design-system-v3 if these are intentional."
        )

    version = str(front_matter.get("version", "")).strip().lower()
    if version not in {"alpha", }:
        warnings.append(
            f"{path.name} uses version '{front_matter.get('version')}'. stitch-alpha corpus convention is 'alpha'."
        )

    description = str(front_matter.get("description", "")).strip()
    if len(description) < 80:
        warnings.append(f"{path.name} description is short; stitch-alpha expects a dense one-paragraph summary.")

    language = str(front_matter.get("language", "")).strip().lower()
    if language.startswith("zh") and cjk_ratio(description + "\n" + body) < 0.18:
        warnings.append(
            f"{path.name} declares language '{front_matter.get('language')}' but human-facing prose appears mostly non-Chinese."
        )

    colors = front_matter.get("colors", {})
    if isinstance(colors, dict):
        if not has_token_role(colors, "primary", "brand", "accent"):
            warnings.append("colors should include a primary/brand/accent role.")
        if not has_token_role(colors, "ink", "text-primary", "text", "body"):
            warnings.append("colors should include an ink/text role.")
        if not has_token_role(colors, "canvas", "surface", "background"):
            warnings.append("colors should include a canvas/surface role.")
        if not has_token_role(colors, "hairline", "border", "stroke"):
            warnings.append("colors should include a hairline/border role.")

    typography = front_matter.get("typography", {})
    if isinstance(typography, dict):
        type_keys = set(typography)
        if not any("display" in key or "heading" in key or "title" in key for key in type_keys):
            warnings.append("typography should include display/heading/title roles.")
        if not any("body" in key for key in type_keys):
            warnings.append("typography should include a body role.")
        if not any("button" in key or "caption" in key or "label" in key for key in type_keys):
            warnings.append("typography should include button/caption/label roles.")

    components = front_matter.get("components", {})
    if isinstance(components, dict):
        archetype = front_matter_archetype(front_matter)
        component_names = " ".join(components.keys()).lower()
        if "button" not in component_names:
            warnings.append("components should include button variants.")
        if archetype != "brand-portfolio" and not any(term in component_names for term in ("card", "surface", "panel")):
            warnings.append("components should include card/surface/panel recipes.")

    present_sections = {
        canon_section_title(section)
        for section in re.findall(r"^##\s+(?:\d+\.\s*)?(.+?)\s*$", body, re.MULTILINE)
    }
    missing_required_sections = [
        section for section in REQUIRED_STITCH_ALPHA_SECTIONS if section not in present_sections
    ]
    if missing_required_sections:
        errors.append(
            f"{path.name} is missing required stitch-alpha sections: "
            + ", ".join(missing_required_sections)
        )
    missing_recommended_sections = [
        section for section in RECOMMENDED_STITCH_ALPHA_SECTIONS if section not in present_sections
    ]
    if missing_recommended_sections:
        warnings.append(
            f"{path.name} is missing recommended stitch-alpha sections: "
            + ", ".join(missing_recommended_sections)
        )


def validate_legacy_design_md(path: Path, errors: list[str], warnings: list[str]) -> None:
    content = path.read_text(encoding="utf-8")

    if has_placeholder(content):
        errors.append(f"{path.name} still contains placeholder text.")

    if not any(re.search(pattern, content, re.MULTILINE) for pattern in TITLE_PATTERNS):
        warnings.append(
            f"{path.name} 应以 '# Design System: <Product Name>' 或本地化等价标题开头。"
        )

    section_numbers = set(re.findall(r"^##\s+(\d+)\.", content, re.MULTILINE))
    missing_numbers = [
        number for number in LEGACY_SECTION_NUMBERS if number not in section_numbers
    ]
    if missing_numbers:
        errors.append(
            f"{path.name} is missing legacy numbered sections: " + ", ".join(missing_numbers)
        )


def detect_format(path: Path) -> str:
    """Detect format of a DESIGN.md file.

    Priority: v3 signals > stitch-alpha > legacy.
    """
    content = path.read_text(encoding="utf-8")
    front_matter, body = extract_front_matter(content)
    if not front_matter:
        return "legacy"

    # 优先检查 v3 信号
    v3_signals = ("productType", "recommendedTokens", "legacyTokens", "aiGenerationRules",
                  "forbiddenRules", "selfCheck", "knownLimits", "designPurpose")
    v3_count = sum(1 for key in v3_signals if key in front_matter)
    if v3_count >= 3:
        return "ai-design-system-v3"

    # 检查正文中的 v3 风格章节
    v3_section_count = sum(
        1 for section in re.findall(r"^##\s+(?:\d+\.\s*)?(.+?)\s*$", body, re.MULTILINE)
        if canon_section_title(section, V3_SECTION_ALIASES) in REQUIRED_V3_SECTIONS
    )
    if v3_section_count >= 7:
        return "ai-design-system-v3"

    # 检查 stitch-alpha 信号
    stitch_signals = ("format",)
    if any(key in front_matter for key in stitch_signals):
        declared = str(front_matter.get("format", "")).strip().lower()
        if declared in {"stitch-alpha", "alpha"}:
            return "stitch-alpha"

    declared = str(front_matter.get("format", "")).strip().lower()
    if declared in {"v3", "ai-design-system-v3"}:
        return "ai-design-system-v3"
    return "legacy"


def find_unresolved_render_tokens(raw_content: str) -> list[str]:
    return sorted(set(re.findall(r"\{(?:colors|typography|spacing|rounded|shadows)\.[^}]+\}", raw_content)))


def find_python_object_leaks(raw_content: str) -> list[str]:
    samples = []
    if re.search(r"\{'[^']+':", raw_content):
        samples.append("dict-literal")
    for pattern, label in (
        (r"[:\[(,]\s*True\b", "True"),
        (r"[:\[(,]\s*False\b", "False"),
        (r"\bTrue\s*[,)\]]", "True"),
        (r"\bFalse\s*[,)\]]", "False"),
    ):
        if re.search(pattern, raw_content) and label not in samples:
            samples.append(label)
    return samples


def has_unescaped_quotes_in_style_attr(raw_content: str) -> bool:
    return bool(re.search(r'style="[^">]*:\s*"[^">]*"', raw_content, re.I))


def validate_preview(
    path: Path,
    errors: list[str],
    warnings: list[str],
    front_matter: dict[str, Any] | None = None,
    design_body: str = "",
) -> None:
    raw_content = path.read_text(encoding="utf-8")
    comparable_raw_content = html.unescape(raw_content)
    content = raw_content.lower()
    visible_text = visible_html_text(raw_content)

    if "<html" not in content:
        errors.append(f"{path.name} is missing an <html> tag.")
    if ":root" not in content:
        errors.append(f"{path.name} is missing a :root token block.")
    if has_placeholder(content):
        errors.append(f"{path.name} still contains placeholder text.")

    unresolved_tokens = find_unresolved_render_tokens(raw_content)
    if unresolved_tokens:
        errors.append(
            f"{path.name} still contains unresolved token placeholders: "
            + ", ".join(unresolved_tokens[:3])
        )

    object_leaks = find_python_object_leaks(raw_content)
    for leak in find_python_object_leaks(comparable_raw_content):
        if leak not in object_leaks:
            object_leaks.append(leak)
    if re.search(r"(?:font-size|line-height|letter-spacing|font-weight)\s*:\s*\{['\"]", comparable_raw_content, re.I):
        object_leaks.append("dict-literal-css")
    if object_leaks:
        errors.append(
            f"{path.name} leaks raw Python-style objects or booleans into the UI: "
            + ", ".join(object_leaks[:3])
        )
    if has_unescaped_quotes_in_style_attr(raw_content):
        errors.append(f"{path.name} contains unescaped quotes inside a style attribute.")

    if re.search(r"width\s*:\s*-?\d+(?:\.\d+)?(?:px|rem|em|%)\s+-?\d", raw_content, re.I):
        errors.append(f"{path.name} contains invalid width styles derived from multi-value spacing tokens.")
    invalid_custom_values = re.findall(
        r"--[a-z0-9_-]+\s*:\s*[^;\n]*(?:\d(?:px|rem|em|vh|vw|%)\s*/\s*\d|\d(?:px|rem|em|vh|vw|%)-\d)[^;\n]*;",
        raw_content,
        flags=re.I,
    )
    if invalid_custom_values:
        errors.append(
            f"{path.name} contains prose-style responsive token values in executable CSS variables: "
            + ", ".join(value.strip() for value in invalid_custom_values[:3])
        )
    no_unit_css = re.findall(
        r"(?<!-)\b(font-size|width|height|min-width|min-height|max-width|max-height|border-radius|gap)\s*:\s*(-?(?!0(?:\.0+)?\b)\d+(?:\.\d+)?)\s*(?=[;\"}])",
        raw_content,
        flags=re.I,
    )
    no_unit_custom = re.findall(
        r"(--spec-(?:topbar|sidebar-width|tags))\s*:\s*(-?(?!0(?:\.0+)?\b)\d+(?:\.\d+)?)\s*;",
        raw_content,
        flags=re.I,
    )
    if no_unit_css or no_unit_custom:
        examples = [f"{prop}: {value}" for prop, value in (no_unit_css + no_unit_custom)[:5]]
        errors.append(
            f"{path.name} contains CSS length values without units: " + ", ".join(examples)
        )

    missing_required = [marker for marker in PREVIEW_REQUIRED_MARKERS if marker not in content]
    if missing_required:
        errors.append(
            f"{path.name} is missing required Design.md preview markers: "
            + ", ".join(missing_required)
        )

    if path.name == "preview-dark.html" and "data-dark-strategy=" not in content:
        errors.append(f"{path.name} must declare a dark strategy.")

    marker_hits = sum(1 for marker in PREFERRED_PREVIEW_MARKERS if marker in content)
    if marker_hits < 8:
        warnings.append(
            f"{path.name} exposes only {marker_hits} preferred preview sections; add more token catalog sections."
        )

    if front_matter:
        colors = front_matter.get("colors", {})
        if isinstance(colors, dict):
            important = [
                key
                for key in colors
                if any(term in key.lower() for term in ("primary", "brand", "ink", "canvas"))
            ][:4]
            missing_tokens = [key for key in important if key.lower() not in content]
            if missing_tokens:
                warnings.append(
                    f"{path.name} does not visibly expose key color token names: "
                    + ", ".join(missing_tokens)
                )
        components = front_matter.get("components", {})
        if isinstance(components, dict):
            component_names = " ".join(components.keys()).lower()
            if "button" in component_names and "button" not in content:
                warnings.append(f"{path.name} should display button component recipes.")
            if any(term in component_names for term in ("input", "field", "form")) and "form" not in content:
                warnings.append(f"{path.name} should display form/input component recipes.")
            if any(term in component_names for term in ("card", "surface", "panel")) and not any(
                term in content for term in ("card", "surface", "panel")
            ):
                warnings.append(f"{path.name} should display card/surface component recipes.")
        language = str(front_matter.get("language", "")).lower()
        typography = front_matter.get("typography", {})
        if isinstance(typography, dict):
            body_type = typography.get("body") if isinstance(typography.get("body"), dict) else {}
            expected_font = first_text(
                typography.get("baseFontFamily"),
                typography.get("fontFamily"),
                body_type.get("fontFamily") if isinstance(body_type, dict) else "",
            )
            actual_font = css_custom_property_value(raw_content, "--font-sans")
            expected_head = expected_font.split(",", 1)[0].strip().strip('"').strip("'")
            if expected_head and actual_font and expected_head.lower() not in actual_font.lower():
                errors.append(
                    f"{path.name} uses --font-sans '{actual_font}' but DESIGN.md typography expects '{expected_font}'."
                )
        source_text = collect_text(front_matter).lower() + " " + design_body.lower()
        lower_raw = raw_content.lower()
        if re.search(r"--spec-sidebar\s*:\s*#20222a\b", lower_raw):
            errors.append(f"{path.name} uses legacy dark sidebar #20222a in the representative shell.")
        if re.search(r"--(?:brand|color-primary)\s*:\s*#409eff\b", lower_raw):
            errors.append(f"{path.name} uses legacy Element default #409EFF as an active preview brand token.")
        leaked_generic = [term for term in GENERIC_PREVIEW_TERMS if term in content and term not in source_text]
        if leaked_generic:
            mode = ""
            evidence = front_matter.get("evidence") if isinstance(front_matter.get("evidence"), dict) else {}
            runtime = front_matter.get("runtime") if isinstance(front_matter.get("runtime"), dict) else {}
            if isinstance(evidence, dict):
                mode = str(evidence.get("mode", "")).strip().lower()
            if not mode and isinstance(runtime, dict):
                mode = str(runtime.get("evidenceMode", "")).strip().lower()
            message = (
                f"{path.name} may still rely on generic specimen copy instead of source terms: "
                + ", ".join(leaked_generic[:3])
            )
            if is_extraction_backed(front_matter):
                errors.append(message)
            else:
                warnings.append(message)
        renderer_component_defaults = (
            "35% / 65% / 80%",
            "480px / 640px",
            "Total 128",
            "共 128 条",
        )
        leaked_component_defaults = [
            term for term in renderer_component_defaults if term in visible_text and term.lower() not in source_text
        ]
        if leaked_component_defaults:
            message = (
                f"{path.name} appears to expose renderer-side component defaults instead of documented specs: "
                + ", ".join(leaked_component_defaults[:4])
            )
            if is_extraction_backed(front_matter):
                errors.append(message)
            else:
                warnings.append(message)
        if is_extraction_backed(front_matter):
            has_documented_layout = any(
                bool(mapping(front_matter.get(parent), "appShell"))
                for parent in ("layout", "layoutRules")
            )
            if has_documented_layout and 'data-layout-source="design-md"' not in raw_content:
                errors.append(
                    f"{path.name} layout/grid preview is not marked as source-backed. "
                    "URL/source mode must render from DESIGN.md layout.appShell/pageTemplates instead of generic admin fallback."
                )
        archetype = front_matter_archetype(front_matter)
        structure_notes = " ".join(
            [
                collect_text(front_matter.get("layoutRules", {})),
                collect_text(front_matter.get("pageTemplates", {})),
                collect_text(front_matter.get("pagePatterns", {})),
                collect_text(front_matter.get("patterns", {})),
                collect_text(front_matter.get("forbiddenRules", {})),
            ]
        ).lower()
        no_persistent_shell = any(
            term in structure_notes
            for term in (
                "no persistent app shell",
                "no app shell",
                "no sidebar",
                "无侧栏",
                "无持久",
            )
        )
        if no_persistent_shell and any(term in visible_text.lower() for term in ("sidebar", "侧栏")):
            errors.append(
                f"{path.name} renders sidebar/app-shell layout chrome even though DESIGN.md forbids a persistent app shell."
            )
        no_footer = any(term in structure_notes for term in ("no footer", "do not add a footer", "无页脚", "不要添加页脚"))
        if no_footer and "footer" in visible_text.lower():
            errors.append(f"{path.name} renders a footer even though DESIGN.md forbids one.")
        if archetype == "brand-portfolio":
            portfolio_forbidden = (
                "data entry components",
                "data display components",
                "pagination components",
                "dialogs / drawers",
                "input fields, textareas",
                "tables, lists",
                "primary, secondary, ghost, text, danger",
                "ods_",
                "tdm_",
                "dw_etl",
                "sample value",
                "search keyword",
            )
            leaked_portfolio_terms = [
                term
                for term in portfolio_forbidden
                if term in content and term not in source_text
            ]
            if leaked_portfolio_terms:
                errors.append(
                    f"{path.name} leaks generic admin/UI-kit sections into a brand-portfolio preview: "
                    + ", ".join(leaked_portfolio_terms[:4])
                )
            if any(term in source_text for term in ("contactbutton", "liveprojectbutton", "contact me", "live project")):
                if not any(term in content for term in ("contactbutton", "liveprojectbutton", "contact me", "live project")):
                    errors.append(
                        f"{path.name} does not expose the documented portfolio CTA components."
                    )
            if "#1862ff" in content and "#1862ff" not in source_text:
                errors.append(f"{path.name} uses generic blue #1862FF that is not part of the portfolio brief.")
        if language.startswith("zh"):
            if cjk_ratio(raw_content) < 0.05:
                warnings.append(f"{path.name} appears under-localized for a Chinese design system output.")
            leaked_placeholders = [
                term
                for term in ZH_PLACEHOLDER_TERMS
                if term in visible_text and term not in source_text
            ]
            if leaked_placeholders:
                errors.append(
                    f"{path.name} still contains English placeholder UI copy: "
                    + ", ".join(leaked_placeholders[:3])
                )
        if front_matter_archetype(front_matter) == "enterprise-admin":
            if re.search(r"<aside[^>]+class=[\"'][^\"']*\bspec-rail\b", raw_content, re.I):
                errors.append(
                    f"{path.name} renders the generic 72px spec-rail layout for an enterprise app shell. "
                    "Use the documented single sidebar + tagsBar layout instead."
                )
        if path.name == "preview-dark.html":
            match = re.search(r'data-dark-strategy="([^"]+)"', raw_content, re.I)
            strategy = match.group(1).strip().lower() if match else ""
            confidence = front_matter.get("confidence", {}) if isinstance(front_matter, dict) else {}
            dark_confidence = ""
            if isinstance(confidence, dict):
                dark_confidence = str(confidence.get("darkMode", "")).strip().lower()
            dark_notes = " ".join(
                [
                    collect_text(front_matter.get("runtime", {})),
                    collect_text(front_matter.get("evidence", {})),
                    collect_text(front_matter.get("knownLimits", {})),
                    collect_text(front_matter.get("confidence", {})),
                    design_body,
                ]
            ).lower()
            unavailable_terms = (
                "dark mode not confirmed",
                "dark mode unavailable",
                "dark mode unsupported",
                "dark mode unconfirmed",
                "no dark mode",
                "unsupported dark",
                "do not generate dark",
                "未确认暗色",
                "暗色模式未确认",
                "未支持暗色",
                "不支持暗色",
                "暗色模式 不支持",
                "暗色模式：不支持",
                "不生成暗色",
                "不生成暗色页面",
                "没有暗色",
                "未观察到暗色",
            )
            dark_is_unavailable = dark_confidence in {
                "none",
                "unknown",
                "unsupported",
                "unavailable",
                "unconfirmed",
                "low",
            } or any(term in dark_notes for term in unavailable_terms)
            if strategy == "real dark mode" and dark_is_unavailable:
                warnings.append(
                    "preview-dark.html claims Real Dark Mode, but runtime notes, confidence, or known limits indicate dark mode is unavailable or unconfirmed."
                )
            if strategy in {"dark inspection view", "dark strategy unavailable"} and "inspection" not in content and "检查视图" not in content:
                warnings.append("preview-dark.html should visibly explain when it is not a confirmed runtime dark mode.")

    expected_shell = expected_shell_tokens(front_matter)
    if path.name in {"preview.html", "preview-dark.html"}:
        expected_topbar_bg = expected_shell.get("topbar_bg", "")
        expected_topbar_height = expected_shell.get("topbar_height", "")
        expected_sidebar_width = expected_shell.get("sidebar_width", "")
        expected_sidebar_bg = expected_shell.get("sidebar_bg", "")
        expected_tags_height = expected_shell.get("tags_height", "")
        actual_topbar_bg = css_custom_property_value(raw_content, "--spec-topbar-bg")
        actual_topbar_height = css_custom_property_value(raw_content, "--spec-topbar")
        actual_sidebar_width = css_custom_property_value(raw_content, "--spec-sidebar-width")
        actual_sidebar_bg = css_custom_property_value(raw_content, "--spec-sidebar")
        actual_tags_height = css_custom_property_value(raw_content, "--spec-tags")
        if expected_topbar_bg and actual_topbar_bg and actual_topbar_bg.lower() != expected_topbar_bg.lower():
            warnings.append(
                f"{path.name} specimen topbar background ({actual_topbar_bg}) does not match DESIGN.md shell color ({expected_topbar_bg})."
            )
        if expected_topbar_bg and not actual_topbar_bg:
            warnings.append(
                f"{path.name} specimen does not expose --spec-topbar-bg even though DESIGN.md defines a shell topbar background."
            )
        if expected_topbar_height and actual_topbar_height and actual_topbar_height != expected_topbar_height:
            warnings.append(
                f"{path.name} specimen topbar height ({actual_topbar_height}) does not match DESIGN.md shell height ({expected_topbar_height})."
            )
        if expected_sidebar_width and actual_sidebar_width and actual_sidebar_width != expected_sidebar_width:
            warnings.append(
                f"{path.name} specimen sidebar width ({actual_sidebar_width}) does not match DESIGN.md shell width ({expected_sidebar_width})."
            )
        if expected_sidebar_bg and actual_sidebar_bg and actual_sidebar_bg.lower() != expected_sidebar_bg.lower():
            errors.append(
                f"{path.name} specimen sidebar background ({actual_sidebar_bg}) does not match DESIGN.md shell background ({expected_sidebar_bg})."
            )
        if expected_tags_height and actual_tags_height and actual_tags_height != expected_tags_height:
            errors.append(
                f"{path.name} specimen tags height ({actual_tags_height}) does not match DESIGN.md shell height ({expected_tags_height})."
            )
        if expected_tags_height and expected_tags_height != "0" and not re.search(r"<[^>]+class=[\"'][^\"']*\bspec-tags\b", raw_content, re.I):
            errors.append(
                f"{path.name} does not render a .spec-tags element even though DESIGN.md defines a tagsBar height ({expected_tags_height})."
            )

    # ── New: :root must not contain generic kit defaults outside .kit-mirror ──
    _generic_colors = {"#2563eb", "#ea2261", "#16a34a", "#b66c00", "#dc2626"}
    _found_generic = []
    for gc in _generic_colors:
        if gc in raw_content:
            # 确认颜色出现在 .kit-mirror 块之外
            lines = raw_content.split("\n")
            in_kit = False
            for lineno, line in enumerate(lines, 1):
                if ".kit-mirror" in line or "kit-mirror" in line.lower():
                    in_kit = not in_kit
                if gc in line and not in_kit:
                    _found_generic.append(f"{gc} at line {lineno}")
    if _found_generic:
        errors.append(
            f"{path.name} contains generic kit-default colors outside .kit-mirror scope: "
            + "; ".join(_found_generic[:3])
        )

    # ── New: colors populated but "No color tokens documented." visible ──
    if front_matter and "colors" in front_matter and isinstance(front_matter.get("colors"), dict):
        has_any_color = bool(
            front_matter["colors"]
        )  # non-empty
        if has_any_color and "no color tokens" in raw_content.lower():
            errors.append(
                f"{path.name} shows 'No color tokens documented.' even though DESIGN.md "
                "front matter contains color definitions."
            )

    # ── New: Style-overview primary color should match front matter ──
    if front_matter:
        colors = front_matter.get("colors", {})
        primary_candidates = []
        if isinstance(colors, dict):
            for group_name in ("primary", "brand", "accent"):
                v = colors.get(group_name)
                if isinstance(v, str):
                    primary_candidates.append(v)
                elif isinstance(v, dict) and "value" in v:
                    primary_candidates.append(str(v["value"]))
            for _, group in colors.items():
                if isinstance(group, dict) and not any(isinstance(x, dict) for x in group.values()):
                    for cand in ("primary", "brand", "accent"):
                        if cand in group:
                            cv = group[cand]
                            if isinstance(cv, str) and cv not in primary_candidates:
                                primary_candidates.append(cv)
                            elif isinstance(cv, dict) and cv.get("value") not in primary_candidates:
                                primary_candidates.append(str(cv.get("value", "")))
        if primary_candidates:
            primary_val = primary_candidates[0]
            if primary_val not in raw_content and primary_val not in content:
                warnings.append(
                    f"{path.name} style-overview may not reflect the DESIGN.md primary color "
                    f"({primary_val}). Check that the '主色' card shows the correct brand color."
                )

    # ── New (preview-dark only): --type-*-color must not contain rgba(0,0,0, ──
    if "dark" in path.name.lower():
        type_color_matches = re.findall(
            r"--type-\S+-color:\s*rgba\(\s*0\s*,\s*0\s*,\s*0\s*",
            raw_content,
            re.I,
        )
        if type_color_matches:
            errors.append(
                f"{path.name} contains light-mode typography colors (rgba(0,0,0,…)) "
                f"in {len(type_color_matches)} --type-*-color tokens — must use dark inverses."
            )


def validate_preview_stitch_alpha(
    path: Path,
    errors: list[str],
    warnings: list[str],
    front_matter: dict[str, Any] | None = None,
    design_body: str = "",
) -> None:
    raw_content = path.read_text(encoding="utf-8")
    comparable_raw_content = html.unescape(raw_content)
    content = raw_content.lower()

    if "<html" not in content:
        errors.append(f"{path.name} is missing an <html> tag.")
    if ":root" not in content:
        errors.append(f"{path.name} is missing a :root token block.")
    if has_placeholder(content):
        errors.append(f"{path.name} still contains placeholder text.")

    scrubbed = re.sub(r"`[^`]*`", "", raw_content)
    scrubbed = re.sub(r"<(code|pre)\b[^>]*>.*?</\1>", "", scrubbed, flags=re.DOTALL | re.IGNORECASE)
    scrubbed = re.sub(r"^\s*\*\s+.*$", "", scrubbed, flags=re.MULTILINE)
    unresolved_tokens = find_unresolved_render_tokens(scrubbed)
    if unresolved_tokens:
        warnings.append(
            f"{path.name} contains unresolved token placeholders outside backticks/code blocks: "
            + ", ".join(unresolved_tokens[:3])
        )

    object_leaks = find_python_object_leaks(raw_content)
    for leak in find_python_object_leaks(comparable_raw_content):
        if leak not in object_leaks:
            object_leaks.append(leak)
    if object_leaks:
        errors.append(
            f"{path.name} leaks raw Python-style objects or booleans into the UI: "
            + ", ".join(object_leaks[:3])
        )
    if has_unescaped_quotes_in_style_attr(raw_content):
        errors.append(f"{path.name} contains unescaped quotes inside a style attribute.")
    if "当前 DESIGN.md 的页面结构信息不足" in raw_content or "neutral-section" in raw_content:
        errors.append(f"{path.name} contains neutral fallback sections; repair pageTemplates/section renderers and rerender.")

    missing_required = [
        marker for marker in STITCH_ALPHA_PREVIEW_REQUIRED_MARKERS if marker not in content
    ]
    if missing_required:
        errors.append(
            f"{path.name} is missing required stitch-alpha preview markers: "
            + ", ".join(missing_required)
        )

    if not any(anchor in content for anchor in STITCH_ALPHA_COMPONENT_ANCHORS):
        errors.append(
            f"{path.name} must include a components anchor — either id=\"components\" or a granular id=\"buttons\"/\"cards\"/\"forms\"/etc."
        )

    missing_recommended = [
        marker for marker in STITCH_ALPHA_PREVIEW_RECOMMENDED_MARKERS if marker not in content
    ]
    if missing_recommended:
        warnings.append(
            f"{path.name} is missing recommended stitch-alpha preview anchors: "
            + ", ".join(missing_recommended)
        )

    if front_matter:
        colors = front_matter.get("colors", {})
        if isinstance(colors, dict):
            primary_keys = [
                key for key in colors
                if any(term in key.lower() for term in ("primary", "brand", "ink", "canvas"))
            ][:3]
            for key in primary_keys:
                value = colors[key]
                hex_value = ""
                if isinstance(value, str):
                    hex_value = value.strip().strip('"').strip("'").lower()
                elif isinstance(value, dict):
                    hex_value = str(value.get("value", "")).strip().lower()
                if hex_value and hex_value.startswith("#") and hex_value not in content:
                    warnings.append(
                        f"{path.name} does not visibly inject color token '{key}' ({hex_value})."
                    )

    if path.name == "preview-dark.html":
        if "data-dark-strategy=" not in content:
            warnings.append(f"{path.name} omits data-dark-strategy; reference dark previews use this attribute.")


def validate_example(
    path: Path,
    errors: list[str],
    warnings: list[str],
    front_matter: dict[str, Any] | None = None,
) -> None:
    raw_content = path.read_text(encoding="utf-8")
    comparable_raw_content = html.unescape(raw_content)
    content = raw_content.lower()
    visible_text = visible_html_text(raw_content)

    if "<html" not in content:
        errors.append(f"{path.name} is missing an <html> tag.")
    if has_placeholder(content):
        errors.append(f"{path.name} still contains placeholder text.")

    unresolved_tokens = find_unresolved_render_tokens(raw_content)
    if unresolved_tokens:
        errors.append(
            f"{path.name} still contains unresolved token placeholders: "
            + ", ".join(unresolved_tokens[:3])
        )

    object_leaks = find_python_object_leaks(raw_content)
    for leak in find_python_object_leaks(comparable_raw_content):
        if leak not in object_leaks:
            object_leaks.append(leak)
    if object_leaks:
        errors.append(
            f"{path.name} leaks raw Python-style objects or booleans into the UI: "
            + ", ".join(object_leaks[:3])
        )
    if has_unescaped_quotes_in_style_attr(raw_content):
        errors.append(f"{path.name} contains unescaped quotes inside a style attribute.")
    if "当前 DESIGN.md 的页面结构信息不足" in raw_content or "neutral-section" in raw_content:
        errors.append(f"{path.name} contains neutral fallback sections; repair pageTemplates/section renderers and rerender.")

    missing_required = [marker for marker in EXAMPLE_REQUIRED_MARKERS if marker not in content]
    if missing_required:
        errors.append(
            f"{path.name} is missing required Design.md example markers: "
            + ", ".join(missing_required)
        )

    html_tag = re.search(r"<html\b[^>]*>", raw_content, re.I)
    html_tag_text = html_tag.group(0) if html_tag else ""
    example_archetype_match = re.search(r'data-example-archetype\s*=\s*"([^"]+)"', html_tag_text, re.I)
    example_pattern_match = re.search(r'data-example-pattern\s*=\s*"([^"]+)"', html_tag_text, re.I)
    example_pattern_source_match = re.search(r'data-example-pattern-source\s*=\s*"([^"]+)"', html_tag_text, re.I)
    example_archetype = example_archetype_match.group(1).strip() if example_archetype_match else ""
    example_pattern = example_pattern_match.group(1).strip() if example_pattern_match else ""
    example_pattern_source = example_pattern_source_match.group(1).strip() if example_pattern_source_match else ""

    if not example_archetype:
        errors.append(f"{path.name} must declare data-example-archetype on the <html> root element.")
    if not example_pattern:
        errors.append(f"{path.name} must declare data-example-pattern on the <html> root element.")
    if not example_pattern_source:
        errors.append(f"{path.name} must declare data-example-pattern-source on the <html> root element.")
    if example_pattern in {"fallback-archetype", "fallback-neutral"} or example_pattern_source in {"fallback-archetype", "fallback-neutral"}:
        errors.append(f"{path.name} still uses legacy hardcoded fallback example templates.")
    if str(example_pattern_source).startswith("fallback-insufficient-design-md") or str(example_pattern_source).startswith("agent-required"):
        errors.append(
            f"{path.name} is still diagnostic or lacks a representative page from DESIGN.md; generate it with an agent from pageTemplates/pagePatterns/component structure."
        )

    scenario: dict[str, Any] | None = None
    generation_input: dict[str, Any] | None = None
    scenario_match = re.search(
        r'<script\b(?=[^>]*\bid=["\']example-scenario["\'])(?=[^>]*\btype=["\']application/json["\'])[^>]*>(.*?)</script>',
        raw_content,
        re.I | re.S,
    )
    if scenario_match:
        try:
            parsed = json.loads(html.unescape(scenario_match.group(1)).strip())
            if isinstance(parsed, dict):
                scenario = parsed
            else:
                errors.append(f"{path.name} example-scenario JSON must be an object.")
        except Exception as exc:
            errors.append(f"{path.name} contains invalid example-scenario JSON: {exc}")

    generation_input_match = re.search(
        r'<script\b(?=[^>]*\bid=["\']example-generation-input["\'])(?=[^>]*\btype=["\']application/json["\'])[^>]*>(.*?)</script>',
        raw_content,
        re.I | re.S,
    )
    if not generation_input_match:
        errors.append(f"{path.name} must embed <script type=\"application/json\" id=\"example-generation-input\">.")
    else:
        try:
            parsed = json.loads(html.unescape(generation_input_match.group(1)).strip())
            if isinstance(parsed, dict):
                generation_input = parsed
            else:
                errors.append(f"{path.name} example-generation-input JSON must be an object.")
        except Exception as exc:
            errors.append(f"{path.name} contains invalid example-generation-input JSON: {exc}")

    if generation_input:
        user_request = str(generation_input.get("userRequest", "")).strip()
        if not user_request:
            errors.append(f"{path.name} example-generation-input.userRequest is required.")
        elif user_request not in visible_text and user_request.lower() not in visible_text.lower():
            errors.append(f"{path.name} must visibly render example-generation-input.userRequest.")
        if not str(generation_input.get("source", "")).strip():
            warnings.append(f"{path.name} example-generation-input.source should describe whether the request was explicit or inferred from DESIGN.md.")
        if str(generation_input.get("source", "")).strip().lower() == "diagnostic":
            errors.append(f"{path.name} example-generation-input.source is diagnostic; generate a real example from DESIGN.md.")
        selected_template = str(generation_input.get("selectedPageTemplate", "")).strip()
        if front_matter and selected_template:
            template_keys = page_template_keys(front_matter)
            if selected_template not in template_keys:
                errors.append(
                    f"{path.name} example-generation-input.selectedPageTemplate ({selected_template}) does not match any DESIGN.md pageTemplates key/name."
                )
        expected_patterns = generation_input.get("expectedPatterns")
        required_capabilities = generation_input.get("requiredCapabilities")
        if expected_patterns is not None and not isinstance(expected_patterns, list):
            warnings.append(f"{path.name} example-generation-input.expectedPatterns should be a list.")
        if required_capabilities is not None and not isinstance(required_capabilities, list):
            warnings.append(f"{path.name} example-generation-input.requiredCapabilities should be a list.")

    if scenario:
        scenario_page = str(scenario.get("pageName", "")).strip()
        if not scenario_page:
            errors.append(f"{path.name} example-scenario.pageName is required.")
        elif scenario_page not in visible_text and scenario_page.lower() not in visible_text.lower():
            errors.append(f"{path.name} must visibly render example-scenario.pageName ({scenario_page}).")
        scenario_sections = scenario.get("sections", [])
        if not isinstance(scenario_sections, list) or not scenario_sections:
            errors.append(f"{path.name} example-scenario.sections must contain at least one section.")
        else:
            missing_sections: list[str] = []
            for section in scenario_sections[:4]:
                if not isinstance(section, dict):
                    continue
                title = str(section.get("title", "")).strip()
                section_type = str(section.get("type", "")).strip()
                if title and title not in visible_text:
                    missing_sections.append(title)
                elif section_type and f'data-section-type="{section_type.lower()}"' not in content:
                    missing_sections.append(section_type)
            if missing_sections:
                errors.append(
                    f"{path.name} must visibly render the main example-scenario.sections: "
                    + ", ".join(missing_sections[:4])
                )
        scenario_source = scenario.get("source", {})
        if isinstance(scenario_source, dict):
            scenario_template = str(scenario_source.get("template", "")).strip()
            scenario_template_source = str(scenario_source.get("templateSource", "")).strip()
            if scenario_template and example_pattern and scenario_template != example_pattern:
                warnings.append(
                    f"{path.name} data-example-pattern ({example_pattern}) differs from example-scenario.source.template ({scenario_template})."
                )
            if scenario_template_source and example_pattern_source and scenario_template_source != example_pattern_source:
                warnings.append(
                    f"{path.name} data-example-pattern-source ({example_pattern_source}) differs from example-scenario.source.templateSource ({scenario_template_source})."
                )
            if scenario_template in {"fallback-archetype", "fallback-neutral"} or scenario_template_source in {"fallback-archetype", "fallback-neutral"}:
                errors.append(f"{path.name} example-scenario.source still references legacy hardcoded fallback templates.")
            if scenario_template_source.startswith("fallback-insufficient-design-md"):
                errors.append(
                    f"{path.name} example-scenario.source.templateSource indicates DESIGN.md lacks enough page structure."
                )
        else:
            errors.append(f"{path.name} example-scenario.source must be an object.")

    if scenario and generation_input:
        scenario_input = scenario.get("generationInput", {})
        if isinstance(scenario_input, dict):
            scenario_request = str(scenario_input.get("userRequest", "")).strip()
            input_request = str(generation_input.get("userRequest", "")).strip()
            if scenario_request and input_request and scenario_request != input_request:
                errors.append(f"{path.name} example-scenario.generationInput must match example-generation-input.")
        else:
            errors.append(f"{path.name} example-scenario.generationInput must be an object.")

    if not any(
        term in content
        for term in (
            "table",
            "form",
            "dashboard",
            "sidebar",
            "toolbar",
            "nav",
            "panel",
            "card",
            "list",
        )
    ):
        warnings.append(f"{path.name} should demonstrate a representative screen pattern, not only generic text.")

    if front_matter:
        language = str(front_matter.get("language", "")).lower()
        source_text = collect_text(front_matter).lower()
        if language.startswith("zh"):
            leaked_generic_nav = [
                term
                for term in ("List Page", "Dashboard Page", "Drawer Config", "Dialog Form")
                if term in visible_text and term.lower() not in source_text
            ]
            if leaked_generic_nav:
                errors.append(
                    f"{path.name} contains generic English page names in a Chinese design system: "
                    + ", ".join(leaked_generic_nav[:4])
                )
        archetype = guess_archetype(" ".join(str(front_matter.get(key, "")) for key in ("productType", "interfaceArchetype", "description")))
        template_archetypes = []
        raw_templates = front_matter.get("pageTemplates")
        template_items: list[Any]
        if isinstance(raw_templates, list):
            template_items = raw_templates
        elif isinstance(raw_templates, dict):
            template_items = list(raw_templates.values())
        else:
            template_items = []
        for item in template_items:
            if isinstance(item, dict):
                template_archetypes.append(str(item.get("archetype", "")).strip())
        primary_template_archetype = guess_archetype(" ".join(template_archetypes))
        if primary_template_archetype:
            archetype = primary_template_archetype

        # 诊断状态已经通过专用 example-pattern-source 标记
        # / userRequest / data-example-source errors above; skip archetype mismatch
        # noise so users don't get duplicate errors for the same root cause.
        is_diagnostic_example = (
            example_archetype == "diagnostic"
            or example_pattern == "diagnostic"
            or str(example_pattern_source).startswith("agent-required")
            or str(example_pattern_source).startswith("fallback-insufficient-design-md")
        )
        if (
            not is_diagnostic_example
            and example_archetype
            and archetype
            and example_archetype != archetype
            and not str(archetype).startswith("custom:")
        ):
            explicit_product_type = str(front_matter.get("productType", "")).strip().lower()
            if explicit_product_type and guess_archetype(explicit_product_type) and guess_archetype(explicit_product_type) != example_archetype:
                errors.append(
                    f"{path.name} data-example-archetype ({example_archetype}) conflicts with DESIGN.md productType ({explicit_product_type})."
                )
            else:
                warnings.append(
                    f"{path.name} data-example-archetype ({example_archetype}) may not match DESIGN.md interfaceArchetype/pageTemplates ({archetype})."
                )

        template_keys = page_template_keys(front_matter)
        page_patterns = front_matter.get("pagePatterns", {})
        pattern_keys = {str(key) for key in page_patterns.keys()} if isinstance(page_patterns, dict) else set()
        if example_pattern and example_pattern not in {"fallback-archetype", "fallback-neutral"}:
            if template_keys and example_pattern not in template_keys and example_pattern not in pattern_keys:
                warnings.append(
                    f"{path.name} data-example-pattern ({example_pattern}) does not match any pageTemplates/pagePatterns key in DESIGN.md."
                )
        if page_template_has_representative(front_matter):
            if example_pattern in {"fallback-archetype", "fallback-neutral"} or example_pattern_source.startswith("fallback-insufficient-design-md"):
                errors.append(
                    f"{path.name} fell back even though DESIGN.md defines usable pageTemplates; enrich/repair pageTemplates and rerender."
                )
            elif template_keys and example_pattern and example_pattern not in template_keys and example_pattern_source == "pageTemplates":
                warnings.append(
                    f"{path.name} declares pageTemplates as the example source but pattern={example_pattern} is not a pageTemplates key."
                )
            if scenario and isinstance(scenario.get("source"), dict):
                scenario_template = str(scenario["source"].get("template", "")).strip()
                scenario_template_source = str(scenario["source"].get("templateSource", "")).strip()
                if not scenario_template or scenario_template in {"inferred", "inferred/fallback", "fallback-neutral", "fallback-archetype"} or scenario_template_source.startswith("fallback-insufficient-design-md"):
                    errors.append(
                        f"{path.name} example-scenario.source.template must identify the DESIGN.md structure used to generate the example."
                    )
                elif template_keys and scenario_template_source == "pageTemplates" and scenario_template not in template_keys:
                    errors.append(
                        f"{path.name} example-scenario.source.template ({scenario_template}) does not match any DESIGN.md pageTemplates key."
                    )
        else:
            if template_items:
                warnings.append(
                    "DESIGN.md includes pageTemplates but none have usable sections/structure; example.html may fall back to pagePatterns or a neutral specimen."
                )

        if scenario:
            scenario_archetype = str(scenario.get("archetype", "")).strip()
            if scenario_archetype and example_archetype and scenario_archetype != example_archetype:
                errors.append(
                    f"{path.name} data-example-archetype ({example_archetype}) must match example-scenario.archetype ({scenario_archetype})."
                )

        evidence = mapping(front_matter, "evidence")
        evidence_mode = str(evidence.get("mode", "")).strip().lower()
        if evidence_mode == "brief":
            raw_templates_for_evidence = front_matter.get("pageTemplates")
            items_for_evidence: list[Any]
            if isinstance(raw_templates_for_evidence, list):
                items_for_evidence = raw_templates_for_evidence
            elif isinstance(raw_templates_for_evidence, dict):
                items_for_evidence = list(raw_templates_for_evidence.values())
            else:
                items_for_evidence = []
            bad_evidence = []
            for item in items_for_evidence:
                if not isinstance(item, dict):
                    continue
                evidence_value = str(item.get("evidence", "")).strip().lower()
                if evidence_value in {"observed", "source-derived", "url-observed"}:
                    bad_evidence.append(first_text(item.get("name"), item.get("title"), item.get("key")))
            if bad_evidence:
                errors.append(
                    "brief-mode DESIGN.md must not mark inferred templates as observed/source-derived; offending pageTemplates: "
                    + ", ".join([s for s in bad_evidence if s][:4])
                )

        patterns = front_matter.get("patterns", {})
        has_patterns = (
            isinstance(page_patterns, dict)
            and bool(page_patterns)
            or isinstance(patterns, dict)
            and bool(patterns)
        )
        if has_patterns and not any(
            term in content
            for term in ("pattern", "table", "tree", "dashboard", "editor", "form", "management", "shell")
        ):
            warnings.append(f"{path.name} should visibly reflect documented page patterns.")
        runtime = front_matter.get("runtime", {})
        runtime_text = collect_text(runtime).lower()
        if "tags-bar" in runtime_text and "class=\"tags\"" not in content:
            warnings.append(f"{path.name} omits a tags/tab bar even though runtime shell documents one.")
        if "sidebar" in runtime_text and "sidebar" not in content:
            warnings.append(f"{path.name} should preserve the documented sidebar shell.")
        if "top-bar" in runtime_text and "topbar" not in content:
            warnings.append(f"{path.name} should preserve the documented top bar shell.")
        source_terms = {
            str(key).lower()
            for source in (page_patterns, patterns)
            if isinstance(source, dict)
            for key in source.keys()
        }
        if archetype != "brand-portfolio" and source_terms and not any(term.replace("_", "-") in content or term.replace("-", " ") in content for term in list(source_terms)[:4]):
            warnings.append(f"{path.name} may still lean on generic page copy instead of documented source pattern terms.")

        expected_shell = expected_shell_tokens(front_matter)
        shell_checks = (
            ("--topbar-bg", expected_shell.get("topbar_bg", ""), "topbar background"),
            ("--topbar-height", expected_shell.get("topbar_height", ""), "topbar height"),
            ("--sidebar-width", expected_shell.get("sidebar_width", ""), "sidebar width"),
            ("--tags-height", expected_shell.get("tags_height", ""), "tags height"),
        )
        for css_name, expected_value, label in shell_checks:
            if not expected_value:
                continue
            actual_value = css_custom_property_value(raw_content, css_name)
            normalized_expected = (
                f"{expected_value}px"
                if re.fullmatch(r"-?\d+(?:\.\d+)?", expected_value.strip())
                else expected_value
            )
            if actual_value and actual_value.lower() != normalized_expected.lower():
                warnings.append(
                    f"{path.name} {label} ({actual_value}) does not match DESIGN.md shell rule ({expected_value})."
                )

    invalid_class_attrs = re.findall(r'(?<![\w-])class="[^"]*\.[^"]*"', raw_content, re.I)
    if invalid_class_attrs:
        errors.append(
            f"{path.name} contains selector syntax inside class attributes. "
            "Move raw selectors to data-source-class and keep class names legal: "
            + ", ".join(invalid_class_attrs[:3])
        )

    # ── New: Check for illegal HTML nesting (<p> contains block elements) ──
    illegal_p_nesting = re.findall(r"<p[^>]*>[^<]*<(h[1-6]|p|div|ul|ol|table|section)\b", raw_content, re.I)
    if illegal_p_nesting:
        errors.append(
            f"{path.name} 存在 {len(illegal_p_nesting)} 处非法 HTML 嵌套："
            f"<p> 内包含块级元素（例如 {', '.join('<' + t for t in set(illegal_p_nesting[:3]))}）"
        )


def main() -> int:
    parser = argparse.ArgumentParser(description="校验生成的设计系统文件夹。")
    parser.add_argument("design_dir", help="设计系统文件夹路径")
    parser.add_argument(
        "--markdown-name",
        choices=("auto", "DESIGN.md", "design.md"),
        default="auto",
        help="期望的 Markdown 设计文件名。默认自动检测。",
    )
    parser.add_argument(
        "--format",
        choices=("auto", "ai-design-system-v3", "v3", "stitch-alpha", "legacy"),
        default="auto",
        help=(
            "期望的 Markdown 格式。"
            "'ai-design-system-v3'（或别名 'v3'）是 10 章格式。"
            "默认自动检测。"
        ),
    )
    args = parser.parse_args()

    design_dir = Path(args.design_dir).resolve()
    errors: list[str] = []
    warnings: list[str] = []

    if not design_dir.exists():
        print(f"[错误] 未找到 DESIGN 文件夹：{design_dir}", file=sys.stderr)
        return 1
    if not design_dir.is_dir():
        print(f"[错误] 路径不是目录：{design_dir}", file=sys.stderr)
        return 1

    design_md_path = resolve_design_md(design_dir, args.markdown_name, errors)

    if args.format == "auto":
        detected = detect_format(design_md_path) if design_md_path is not None else "ai-design-system-v3"
    elif args.format in ("ai-design-system-v3", "v3"):
        detected = "ai-design-system-v3"
    else:
        detected = args.format

    if detected == "stitch-alpha":
        expected_files = STITCH_ALPHA_REQUIRED_FILES
    elif detected == "ai-design-system-v3":
        expected_files = REQUIRED_FILES_V3
    else:
        expected_files = REQUIRED_FILES_LEGACY

    for file_name in expected_files:
        file_path = design_dir / file_name
        if not file_path.exists():
            errors.append(f"缺少必需文件：{file_name}")

    front_matter: dict[str, Any] | None = None
    if not errors and design_md_path is not None:
        if detected == "stitch-alpha":
            validate_stitch_alpha_design_md(design_md_path, errors, warnings)
            front_matter, design_body = extract_front_matter(design_md_path.read_text(encoding="utf-8"))
            validate_preview_stitch_alpha(
                design_dir / "preview.html", errors, warnings, front_matter, design_body
            )
            validate_preview_stitch_alpha(
                design_dir / "preview-dark.html", errors, warnings, front_matter, design_body
            )
        elif detected == "ai-design-system-v3":
            validate_v3_design_md(design_md_path, errors, warnings)
            front_matter, design_body = extract_front_matter(design_md_path.read_text(encoding="utf-8"))
            validate_shell_front_matter_consistency(front_matter, warnings)
            validate_gaps_md(design_dir / "DESIGN_GAPS.md", errors, warnings, front_matter, design_body)
            validate_preview(design_dir / "preview.html", errors, warnings, front_matter, design_body)
            validate_preview(design_dir / "preview-dark.html", errors, warnings, front_matter, design_body)
            validate_example(design_dir / "example.html", errors, warnings, front_matter)
        else:
            validate_legacy_design_md(design_md_path, errors, warnings)
            validate_preview(design_dir / "preview.html", errors, warnings, None, "")
            validate_preview(design_dir / "preview-dark.html", errors, warnings, None, "")
            validate_example(design_dir / "example.html", errors, warnings, None)

    if errors:
        print("[失败] DESIGN 文件夹校验未通过。")
        for error in errors:
            print(f" - 错误：{error}")
        for warning in warnings:
            print(f" - 警告：{warning}")
        return 1

    print("[完成] DESIGN 文件夹校验通过。")
    for warning in warnings:
        print(f" - 警告：{warning}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
