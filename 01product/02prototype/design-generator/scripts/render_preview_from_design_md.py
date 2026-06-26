#!/usr/bin/env python3
"""
从 DESIGN.md 渲染 preview.html 和 preview-dark.html。

预览文件是 Markdown 单一事实源的可视化校验面板，用于展示 token 组、
组件配方、交互状态覆盖、布局模式、Agent 指南和已知缺口。
最终 example.html 默认由 Agent 编写；本脚本仅保留 legacy --render-example
模式，用于兼容较早生成的包。
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
    normalize_design_data,
    parse_simple_yaml as parse_simple_yaml_fallback,
)


SUPPORTED_MARKDOWN_FILES = ("DESIGN.md", "design.md")
GENERIC_COLOR_FALLBACKS = {
    "#2563eb",
    "#1d4ed8",
    "#ffffff",
    "#111827",
    "#172033",
    "#667085",
    "#6b7280",
    "#f8fafc",
    "#eef2f7",
    "#f3f5f8",
    "#f5f5f5",
    "#f5f7fb",
    "#f5f7fa",
    "#f6f9fc",
    "#e8f1ff",
    "#d7dee8",
    "#d9dee8",
    "#e3e8ee",
    "#1862ff",
    "#1450cc",
}
GENERIC_FONT_FALLBACK = 'system-ui, -apple-system, BlinkMacSystemFont, "Segoe UI", sans-serif'
SECTION_RE = re.compile(r"^##\s+(?:\d+\.\s*)?(.+?)\s*$", re.MULTILINE)
TOKEN_REF_RE = re.compile(r"#?\{([a-zA-Z0-9_.-]+)\}")
CSS_LENGTH_KEYS = {
    "font-size",
    "width",
    "height",
    "min-width",
    "min-height",
    "max-width",
    "max-height",
    "border-radius",
    "gap",
    "row-gap",
    "column-gap",
}
SECTION_ALIASES = {
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
        "prototype generation rules & self-check",
        "prototype generation rules and self-check",
        "AI 生成规则、禁止事项与自检清单",
        "AI 生成规则 禁止事项与自检清单",
        "原型生成规则与自检",
        "原型生成规则和自检",
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
STITCH_ALPHA_SECTION_ALIASES = {
    "Overview": ("overview", "概览"),
    "Colors": ("colors", "color palette", "颜色"),
    "Typography": ("typography", "字体"),
    "Layout": ("layout", "布局"),
    "Elevation": ("elevation", "elevation & depth", "depth & elevation", "shadows", "elevation and depth"),
    "Shapes": ("shapes", "radius", "rounded"),
    "Components": ("components", "组件"),
    "Do's and Don'ts": ("do's and don'ts", "dos and don'ts", "do / don't", "dos & donts", "应该/避免"),
    "Responsive Behavior": ("responsive behavior", "responsive", "响应式"),
    "Iteration Guide": ("iteration guide", "迭代指南"),
    "Design Constraints": ("design constraints", "设计约束", "known gaps", "已知缺口", "已知不足"),
}
LABELS = {
    "en": {
        "preview": "Preview",
        "preview_aria": "Preview sections",
        "preview_catalog": "Design System Preview",
        "overview": "Design Style Overview",
        "colors": "Colors",
        "typography": "Typography",
        "scale": "Scale",
        "components": "Components",
        "states": "States",
        "patterns": "Template Pages",
        "guide": "Guide",
        "gaps": "Gaps",
        "style_overview": "Design Style Overview",
        "style_overview_copy": "Quick understanding of the overall design style, main colors, fonts, page density, component system, and typical page types.",
        "product_name": "Product Name",
        "style_summary": "Style Summary",
        "main_color": "Main Color",
        "font_family": "Font Family",
        "page_density": "Page Density",
        "component_system": "Component System",
        "product_type": "Product Type",
        "typical_pages": "Typical Pages",
        "ui_specs": "Basic Design Tokens / UI Specifications",
        "ui_specs_copy": "Core design tokens including colors, typography, layout, icons, spacing, radius, and shadows.",
        "layout_grid": "Layout / Grid",
        "layout_grid_copy": "Page framework, grid rules, and responsive behavior.",
        "icons": "Icons",
        "icons_copy": "Icon style, default size, common sizes, and usage scenarios.",
        "token_overview": "Token Overview",
        "token_copy": "Counts, evidence, and runtime signals for quickly judging how complete this system is.",
        "color_roles": "Color Specifications",
        "color_copy": "Semantic color swatches with role labels and usage scenarios. Shows primary, hover, active states, backgrounds, text colors, borders, and semantic colors.",
        "type_scale": "Typography Specifications",
        "type_copy": "Text roles with font size, weight, line height, color, and usage scenarios. Not just font names, but text role definitions.",
        "spacing": "Spacing",
        "spacing_copy": "Core spacing tokens and their usage scenarios.",
        "radius": "Border Radius",
        "radius_copy": "Common radius values and applicable scenarios.",
        "elevation": "Shadows / Elevation",
        "elevation_copy": "Shadow styles for cards, dialogs, dropdowns, and other elevated surfaces.",
        "component_specs": "Component Examples / Component Specifications",
        "component_specs_copy": "Visual samples with sizes, states, colors, and usage scenarios. Components should match the target product's real component system.",
        "component_recipes": "Component Specifications",
        "component_copy": "Visual samples first, implementation tokens second. Shows sizes, states, and usage scenarios.",
        "component_mapping": "Component Mapping",
        "buttons": "Button Components",
        "buttons_copy": "Primary, secondary, ghost, text, danger, disabled buttons with states and sizing rules.",
        "inputs": "Data Entry Components",
        "inputs_copy": "Input fields, textareas, selects, date pickers, checkboxes, radios, switches, upload components, and search boxes.",
        "data_display": "Data Display Components",
        "data_display_copy": "Tables, lists, status tags, action columns, empty states, and loading states.",
        "tags": "Tag Components",
        "tags_copy": "Default, success, warning, error, info, selected, and disabled tags.",
        "pagination": "Pagination Components",
        "pagination_copy": "Previous, next, current page, page numbers, total count, page size selector, and jump to page.",
        "tabs": "Tabs / Top Navigation",
        "tabs_copy": "Default, active, hover, disabled tabs, and top tab navigation.",
        "dialogs": "Dialogs / Drawers",
        "dialogs_copy": "Dialog titles, content areas, form content, footer action buttons, masks, drawer titles, drawer detail layouts, and drawer footer actions.",
        "cards": "Card Components",
        "cards_copy": "Info cards, action cards, metric cards, special cards, and card grids.",
        "state_title": "Interaction States",
        "state_copy": "Coverage matrix based on component names and recipe properties, not silent invention.",
        "template_pages": "Real Pages / Template Page Examples",
        "template_pages_copy": "Representative page examples based on product type. Shows how tokens and components combine into real pages.",
        "template_summary_nav": "Template Summary",
        "template_examples_nav": "Rendered Examples",
        "layout_title": "Layout Patterns",
        "layout_copy": "A source-matched specimen appears before the raw pattern recipes so readers can understand the page grammar visually.",
        "specimen_note": "Representative layout specimen generated from documented page patterns and component mappings.",
        "enterprise_pages": "Enterprise Backend / Admin System Pages",
        "enterprise_pages_copy": "Standard table management, tree-table, list pages, search + list, form pages, card pages, dialogs, drawers, and overview pages.",
        "marketing_pages": "Marketing Site / Landing Pages",
        "marketing_pages_copy": "Top navigation, hero section, CTA section, feature cards, user cases, FAQ section, and footer.",
        "mobile_pages": "Mobile App Pages",
        "mobile_pages_copy": "Mobile home, list pages, detail pages, form pages, bottom navigation, mobile dialogs, and mobile buttons.",
        "dashboard_pages": "Data Dashboard Pages",
        "dashboard_pages_copy": "Dashboard overview, metric cards, trend charts, map/spatial displays, alert lists, monitoring task lists, and data update time.",
        "form_title": "Form Controls Sample",
        "form_copy": "Baseline form controls rendered with the extracted surface, border, radius, and type rules.",
        "action_title": "Action Sample",
        "action_copy": "Primary, secondary, and disabled actions shown as quick affordance checks.",
        "agent_title": "Agent Prompt Guide Snapshot",
        "agent_copy": "The highest-value downstream generation rules extracted from the markdown source of truth.",
        "quality_title": "Quality Checklist / Design Constraints",
        "quality_copy": "Validation prompts and documented constraints grouped at the end for review.",
        "collapse_hint": "▸ expand (design-system reference)",
        "checklist": "Checklist",
        "known_gaps": "Design Constraints",
        "implementation_tokens": "Implementation tokens",
        "not_documented": "Not documented",
        "documented": "Documented",
        "mentioned_only": "Mentioned only",
        "runtime_missing": "runtime state not documented",
        "no_component_mapping": "No component mappings documented.",
        "dark_evidence": "Dark mode evidence",
        "dark_missing": "dark mode not confirmed",
        "inspection_note": "Inspection view uses the same brand system but not a confirmed dark runtime.",
        "gap_summary": "Coverage notes",
        "usage_note": "Usage Note",
        "usage_note_copy": "This page is for previewing design specifications and page examples. For AI coding tools to generate pages, please use DESIGN.md in the same directory.",
    },
    "zh": {
        "preview": "预览目录",
        "preview_aria": "预览章节",
        "preview_catalog": "设计系统预览",
        "overview": "设计风格概览",
        "colors": "颜色",
        "typography": "字体",
        "scale": "尺度",
        "components": "组件",
        "states": "状态",
        "patterns": "模板页面",
        "guide": "指南",
        "gaps": "缺口",
        "style_overview": "设计风格概览",
        "style_overview_copy": "快速理解产品整体设计风格、主色、字体、页面密度、组件体系和典型页面类型。",
        "product_name": "产品名称",
        "style_summary": "风格摘要",
        "main_color": "主色",
        "font_family": "字体",
        "page_density": "页面密度",
        "component_system": "组件体系",
        "product_type": "产品类型",
        "typical_pages": "典型页面",
        "ui_specs": "基础设计令牌 / UI 规范",
        "ui_specs_copy": "核心设计令牌，包括颜色、字体、布局、图标、间距、圆角和阴影。",
        "layout_grid": "布局 / 栅格",
        "layout_grid_copy": "页面框架、栅格规则和响应式行为。",
        "icons": "图标",
        "icons_copy": "图标风格、默认尺寸、常用尺寸和使用场景。",
        "token_overview": "设计令牌总览",
        "token_copy": "快速查看证据、运行态、令牌数量、组件数量和页面模式完整度。",
        "color_roles": "颜色规范",
        "color_copy": "语义颜色色块，包含角色标签和使用场景。展示主色、hover、active 状态、背景色、文字色、边框色和语义色。",
        "type_scale": "字体规范",
        "type_copy": "文字角色，包含字号、字重、行高、颜色和使用场景。不只是字体名称，而是文字角色定义。",
        "spacing": "间距",
        "spacing_copy": "核心间距令牌及其使用场景。",
        "radius": "圆角",
        "radius_copy": "常用圆角值及适用场景。",
        "elevation": "阴影 / 层级",
        "elevation_copy": "卡片、弹窗、下拉菜单等悬浮表面的阴影样式。",
        "component_specs": "组件样例 / 组件规范",
        "component_specs_copy": "视觉样例，包含尺寸、状态、颜色和使用场景。组件应贴近目标产品的真实组件体系。",
        "component_recipes": "组件规范",
        "component_copy": "先看视觉样例，再展开实现令牌。展示尺寸、状态和使用场景。",
        "component_mapping": "组件映射",
        "buttons": "按钮组件",
        "buttons_copy": "主按钮、次按钮、幽灵按钮、文字按钮、危险按钮、禁用按钮，包含状态和尺寸规则。",
        "inputs": "数据录入组件",
        "inputs_copy": "输入框、文本域、下拉选择、日期选择、复选框、单选框、开关、上传组件和搜索框。",
        "data_display": "数据展示组件",
        "data_display_copy": "表格、列表、状态标签、操作列、空状态和加载状态。",
        "tags": "标签组件",
        "tags_copy": "默认、成功、警告、错误、信息、选中和禁用标签。",
        "pagination": "分页组件",
        "pagination_copy": "上一页、下一页、当前页、页码、总数、每页条数选择和跳页输入。",
        "tabs": "Tabs / 顶部切换",
        "tabs_copy": "默认、active、hover、禁用 tab，以及顶部标签导航。",
        "dialogs": "弹窗 / 抽屉",
        "dialogs_copy": "弹窗标题、内容区、表单内容、底部操作按钮、遮罩层、抽屉标题、抽屉详情布局和抽屉底部操作区。",
        "cards": "卡片组件",
        "cards_copy": "信息卡片、操作卡片、指标卡片、特殊卡片和卡片网格。",
        "state_title": "交互状态",
        "state_copy": "基于组件名称和配方属性判断状态覆盖，不凭空补齐未记录状态。",
        "template_pages": "真实页面 / 模板页面样例",
        "template_pages_copy": "根据产品类型展示代表性页面样例。展示令牌和组件如何组合成真实页面。",
        "template_summary_nav": "模板摘要",
        "template_examples_nav": "页面样例",
        "layout_title": "布局模式",
        "layout_copy": "先展示贴近源项目的页面样例，再列出原始布局配方，便于理解页面语法。",
        "specimen_note": "以下页面样例由已记录的页面模式和组件映射生成，用于快速理解真实页面结构。",
        "enterprise_pages": "企业后台 / 管理系统页面",
        "enterprise_pages_copy": "标准表格管理页、树表联动页、列表页、搜索+列表页、表单页、卡片页、弹窗、抽屉和概览页。",
        "marketing_pages": "营销官网 / 落地页",
        "marketing_pages_copy": "顶部导航、Hero 区、CTA 区、功能卡片、用户案例、FAQ 区和 Footer。",
        "mobile_pages": "移动端应用页面",
        "mobile_pages_copy": "移动端首页、列表页、详情页、表单页、底部导航、移动端弹窗和移动端按钮。",
        "dashboard_pages": "数据大屏页面",
        "dashboard_pages_copy": "大屏总览、指标卡片、趋势图表、地图/空间展示、告警列表、监测任务列表和数据更新时间。",
        "form_title": "表单控件样例",
        "form_copy": "用提取到的表面、边框、圆角和字体规则渲染基础表单控件。",
        "action_title": "操作按钮样例",
        "action_copy": "展示主按钮、次按钮和禁用按钮，用于快速检查操作样式。",
        "agent_title": "Agent 提示词指南摘录",
        "agent_copy": "从 Markdown 源文档中摘取最关键的后续页面生成规则。",
        "quality_title": "质量清单 / 设计约束",
        "quality_copy": "集中展示验收项和已确认的约束条件，方便维护者复核。",
        "collapse_hint": "▸ 展开（设计系统参考文档）",
        "checklist": "质量清单",
        "known_gaps": "设计约束",
        "implementation_tokens": "实现令牌",
        "not_documented": "未记录",
        "documented": "已记录",
        "mentioned_only": "仅文本提及",
        "runtime_missing": "未记录运行态",
        "no_component_mapping": "未记录组件映射。",
        "usage_note": "使用说明",
        "usage_note_copy": "本页面用于预览设计规范和页面样例。用于 AI 编程工具生成页面时，请使用同目录下的 DESIGN.md。",
        "dark_evidence": "暗色模式依据",
        "dark_missing": "暗色模式未确认",
        "inspection_note": "检查视图沿用同一套品牌语言，但不代表已确认真实暗色运行态。",
        "gap_summary": "覆盖提示",
    },
}


def preview_section_schema(labels: dict[str, str], data: dict[str, Any] | None = None) -> tuple[dict[str, Any], ...]:
    """预览导航和锚点 section 的单一事实源。"""
    archetype = infer_archetype(data or {}) if data else ""
    if archetype == "brand-portfolio":
        component_children = (
            {"id": "buttons", "label": labels["buttons"]},
            {"id": "cards", "label": labels["cards"]},
        )
    elif archetype in {"media-content", "content-resource-portal"}:
        component_children = (
            {"id": "buttons", "label": "频道 Tab / 顶部导航"},
            {"id": "cards", "label": "文章卡片 / 信息流"},
            {"id": "right-rail", "label": "快捷入口 / 右侧挂件"},
        )
    else:
        component_children = (
            {"id": "buttons", "label": labels["buttons"]},
            {"id": "inputs", "label": labels["inputs"]},
            {"id": "data-display", "label": labels["data_display"]},
            {"id": "tags", "label": labels["tags"]},
            {"id": "pagination", "label": labels["pagination"]},
            {"id": "tabs", "label": labels["tabs"]},
            {"id": "dialogs", "label": labels["dialogs"]},
            {"id": "cards", "label": labels["cards"]},
        )
    return (
        {
            "id": "style-overview",
            "label": labels["style_overview"],
            "children": (),
        },
        {
            "id": "ui-specs",
            "label": labels["ui_specs"],
            "children": (
                {"id": "colors", "label": labels["colors"]},
                {"id": "typography", "label": labels["typography"]},
                {"id": "layout-grid", "label": labels["layout_grid"]},
                {"id": "icons", "label": labels["icons"]},
                {"id": "spacing", "label": labels["spacing"]},
                {"id": "radius", "label": labels["radius"]},
                {"id": "elevation", "label": labels["elevation"]},
            ),
        },
        {
            "id": "component-specs",
            "label": labels["component_specs"],
            "children": component_children,
        },
        {
            "id": "template-pages",
            "label": labels["template_pages"],
            "children": (
                {"id": "template-summary", "label": labels["template_summary_nav"]},
                {"id": "template-examples", "label": labels["template_examples_nav"]},
            ),
        },
    )


def preview_top_nav(section_schema: tuple[dict[str, Any], ...]) -> str:
    """渲染预览顶部导航。"""
    return "".join(
        f'<a href="#{html.escape(str(section["id"]))}">{html.escape(str(section["label"]))}</a>'
        for section in section_schema
    )


def preview_sidebar_toc(section_schema: tuple[dict[str, Any], ...]) -> str:
    """根据共享 schema 渲染分组侧边目录。"""
    groups: list[str] = []
    for section in section_schema:
        section_id = html.escape(str(section["id"]))
        section_label = html.escape(str(section["label"]))
        child_links = "".join(
            (
                '<a class="toc-child" '
                f'href="#{html.escape(str(child["id"]))}">{html.escape(str(child["label"]))}</a>'
            )
            for child in section.get("children", ())
        )
        child_block = f'<div class="toc-children">{child_links}</div>' if child_links else ""
        groups.append(
            '<div class="toc-group">'
            f'<a class="toc-parent" href="#{section_id}">{section_label}</a>'
            f"{child_block}"
            "</div>"
        )
    return "".join(groups)


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
    """解析生成的 DESIGN.md 使用的 YAML 子集。

    该兜底解析器刻意支持嵌套映射和列表，这样在没有 PyYAML 时，
    渲染器仍可消费 pageTemplates。
    """
    return parse_simple_yaml_fallback(text)


def extract_design_doc(content: str) -> tuple[dict[str, Any], str]:
    if not content.startswith("---\n"):
        raise ValueError("设计 Markdown 必须以 YAML front matter 开头。")
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
    raise ValueError("设计 Markdown 的 front matter 未闭合。")


def has_cjk(text: str) -> bool:
    return bool(re.search(r"[\u4e00-\u9fff]", text))


def detect_language(data: dict[str, Any], body: str = "") -> str:
    explicit = str(data.get("language", "")).lower()
    if explicit.startswith("zh") or explicit in {"cn", "chinese", "中文"}:
        return "zh"
    if explicit.startswith("en"):
        return "en"
    sample = " ".join([str(data.get("name", "")), str(data.get("description", "")), body[:2000]])
    return "zh" if has_cjk(sample) else "en"


def canon_section_title(title: str, aliases: dict[str, tuple[str, ...]] | None = None) -> str:
    cleaned = re.sub(r"\s+", " ", title.strip())
    lowered = cleaned.lower()
    alias_table = aliases if aliases is not None else SECTION_ALIASES
    for canonical, alias_list in alias_table.items():
        if lowered == canonical.lower() or any(alias == lowered for alias in alias_list):
            return canonical
        if canonical.lower() in lowered:
            return canonical
        if any(alias in lowered for alias in alias_list if has_cjk(alias)):
            return canonical
    return cleaned


def extract_sections(body: str, aliases: dict[str, tuple[str, ...]] | None = None) -> dict[str, str]:
    matches = list(SECTION_RE.finditer(body))
    sections: dict[str, str] = {}
    for index, match in enumerate(matches):
        title = match.group(1).strip()
        start = match.end()
        end = matches[index + 1].start() if index + 1 < len(matches) else len(body)
        content = body[start:end].strip()
        sections[title] = content
        sections.setdefault(canon_section_title(title, aliases), content)
    return sections


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


def mentions_any(text: str, terms: tuple[str, ...]) -> bool:
    lowered = text.lower()
    return any(term in lowered for term in terms)


def humanize_identifier(value: str) -> str:
    text = re.sub(r"([a-z0-9])([A-Z])", r"\1 \2", str(value))
    text = re.sub(r"[_./-]+", " ", text)
    text = re.sub(r"\s+", " ", text).strip()
    if not text:
        return ""
    if text.upper() == text and any(ch.isalpha() for ch in text):
        return text
    return text.title()


def localize_term(term: str, lang: str) -> str:
    normalized = re.sub(r"\s+", " ", term).strip()
    if lang != "zh" or not normalized:
        return normalized
    glossary = {
        "App Shell": "应用框架",
        "Table Management": "表管理",
        "Tree Table": "树表页",
        "Tree Table Management": "树形表管理",
        "Button": "按钮",
        "Table": "表格",
        "Workspace": "工作台",
        "Quality Review": "质量检查",
        "System Overview": "系统总览",
        "List Page": "列表页",
        "Detail Page": "详情页",
        "Form Page": "表单页",
        "Dashboard Page": "概览页",
        "Drawer Config": "配置抽屉",
        "Dialog Form": "弹窗表单",
        "Design Asset": "设计资产",
        "Component Mapping": "组件映射",
        "Create": "新建",
        "Import": "导入",
        "Search": "查询",
        "Filter": "筛选",
        "Online": "在线",
        "Active": "在线",
        "Success": "成功",
        "Error": "错误",
        "Warning": "警告",
        "Failed": "失败",
        "Pending": "待处理",
        "Draft": "草稿",
        "View": "查看",
        "Edit": "编辑",
        "Detail": "详情",
    }
    return glossary.get(normalized, normalized)


def unique_terms(candidates: list[str], limit: int) -> list[str]:
    seen: set[str] = set()
    selected: list[str] = []
    for candidate in candidates:
        normalized = re.sub(r"\s+", " ", candidate).strip()
        if not normalized:
            continue
        key = normalized.casefold()
        if key in seen:
            continue
        seen.add(key)
        selected.append(normalized)
        if len(selected) >= limit:
            break
    return selected


def extract_product_terms(data: dict[str, Any], lang: str = "en") -> dict[str, list[str]]:
    page_patterns = mapping(data, "pagePatterns")
    patterns = mapping(data, "patterns")
    component_mappings = mapping(data, "componentMappings")
    components = mapping(data, "components")
    page_templates_raw = data.get("pageTemplates")
    sources = [page_patterns, patterns, component_mappings, components]
    pattern_terms: list[str] = []
    component_terms: list[str] = []
    action_terms: list[str] = []
    status_terms: list[str] = []
    for source in sources:
        for key, value in source.items():
            readable = humanize_identifier(str(key))
            if readable:
                pattern_terms.append(localize_term(readable, lang))
            if isinstance(value, dict):
                nested_text = collect_text(value)
                action_terms.extend(
                    localize_term(humanize_identifier(match), lang)
                    for match in re.findall(
                        r"\b(create|new|search|filter|reset|import|export|save|submit|publish|sync|deploy|edit|detail|view|approve)\b",
                        nested_text,
                        flags=re.I,
                    )
                )
                status_terms.extend(
                    localize_term(humanize_identifier(match), lang)
                    for match in re.findall(
                        r"\b(online|active|draft|disabled|pending|error|warning|success|failed|archived)\b",
                        nested_text,
                        flags=re.I,
                    )
                )
        if source is component_mappings:
            component_terms.extend(localize_term(humanize_identifier(str(key)), lang) for key in source.keys())
    template_items: list[Any]
    if isinstance(page_templates_raw, list):
        template_items = page_templates_raw
    elif isinstance(page_templates_raw, dict):
        template_items = list(page_templates_raw.values())
    else:
        template_items = []
    for item in template_items:
        if isinstance(item, dict):
            term = ""
            for candidate in (item.get("title"), item.get("name"), item.get("key"), item.get("id")):
                if candidate is not None and str(candidate).strip():
                    term = str(candidate).strip()
                    break
            if term:
                pattern_terms.append(localize_term(humanize_identifier(term), lang))
    component_terms.extend(localize_term(humanize_identifier(str(key)), lang) for key in components.keys())
    return {
        "patterns": unique_terms(pattern_terms, 10),
        "components": unique_terms(component_terms, 12),
        "actions": unique_terms(action_terms, 8),
        "statuses": unique_terms(status_terms, 8),
    }


def strongest_page_pattern(data: dict[str, Any]) -> tuple[str, dict[str, Any]]:
    page_patterns = mapping(data, "pagePatterns")
    patterns = mapping(data, "patterns")
    for source in (page_patterns, patterns):
        for key, value in source.items():
            if not isinstance(value, dict):
                continue
            evidence = collect_text(value.get("evidence", "")).lower()
            if "source-confirmed" in evidence or "observed" in evidence:
                return str(key), value
    for source in (page_patterns, patterns):
        for key, value in source.items():
            if isinstance(value, dict):
                return str(key), value
    return "", {}


def page_pattern_title(pattern_key: str, pattern_value: dict[str, Any], lang: str) -> str:
    key = pattern_key.lower()
    applies_when = collect_text(pattern_value.get("appliesWhen", "")).strip()
    localized_defaults = {
        "table-management": "数据管理页" if lang == "zh" else "Table Management",
        "tree-table": "树表联动页" if lang == "zh" else "Tree Table Workspace",
        "tree-table-split": "树表联动页" if lang == "zh" else "Tree Table Workspace",
        "form-create-edit": "新建 / 编辑页" if lang == "zh" else "Create / Edit Form",
        "dashboard-overview": "概览页" if lang == "zh" else "Dashboard Overview",
        "stepped-form": "分步配置页" if lang == "zh" else "Stepped Form",
    }
    for known_key, title in localized_defaults.items():
        if known_key in key:
            return applies_when or title
    return applies_when or localize_term(humanize_identifier(pattern_key), lang) or (
        "代表页面" if lang == "zh" else "Representative Page"
    )


def _first_string(*values: Any) -> str:
    for value in values:
        if value is None:
            continue
        text = str(value).strip()
        if text:
            return text
    return ""


def shell_metrics(data: dict[str, Any]) -> dict[str, Any]:
    runtime = mapping(data, "runtime")
    layout_state = mapping(runtime, "layoutState")
    runtime_shell = runtime.get("shell", "")
    layout_rules = mapping(data, "layoutRules")
    layout_root = mapping(data, "layout")
    app_shell = mapping(layout_rules, "appShell") or mapping(layout_root, "appShell")
    top_nav_rules = mapping(app_shell, "topbar") or mapping(app_shell, "topBar") or mapping(app_shell, "topNav")
    sidebar_rules = mapping(app_shell, "sidebar")
    tags_rules = (
        mapping(app_shell, "tagsBar")
        or mapping(app_shell, "tags")
        or mapping(app_shell, "tagsView")
    )
    shell_text = " ".join(
        [
            collect_text(layout_state.get("shell", "")),
            collect_text(runtime_shell),
            collect_text(app_shell),
        ]
    )
    metrics = {
        "topbar": "56px",
        "sidebar": "92px",
        "sidebar_collapsed": "92px",
        "tags": "0px",
        "has_tags": False,
        "shell_text": shell_text,
    }
    structured_topbar = _first_string(
        top_nav_rules.get("height"),
        layout_state.get("topNavHeight"),
        layout_state.get("topbarHeight"),
    )
    structured_sidebar = _first_string(
        sidebar_rules.get("expandedWidth"),
        sidebar_rules.get("width"),
        layout_state.get("sidebarExpandedWidth"),
        layout_state.get("sidebarWidth"),
    )
    structured_sidebar_collapsed = _first_string(
        sidebar_rules.get("collapsedWidth"),
        layout_state.get("sidebarCollapsedWidth"),
    )
    structured_tags = _first_string(
        tags_rules.get("height"),
        layout_state.get("tagsHeight"),
        layout_state.get("tagsViewHeight"),
    )
    if structured_topbar:
        metrics["topbar"] = first_css_length(structured_topbar, str(metrics["topbar"]))
    if structured_sidebar:
        metrics["sidebar"] = first_css_length(structured_sidebar, str(metrics["sidebar"]))
    if structured_sidebar_collapsed:
        metrics["sidebar_collapsed"] = first_css_length(structured_sidebar_collapsed, str(metrics["sidebar_collapsed"]))
    if structured_tags:
        metrics["tags"] = first_css_length(structured_tags, str(metrics["tags"]))
        metrics["has_tags"] = True
    topbar_match = re.search(r"top-?bar\((\d+px)\)", shell_text, flags=re.I)
    sidebar_match = re.search(r"sidebar\((\d+px)", shell_text, flags=re.I)
    collapsed_match = re.search(r"collapsible to (\d+px)", shell_text, flags=re.I)
    tags_match = re.search(r"tags?-bar\((\d+px)\)", shell_text, flags=re.I)
    generic_topbar_match = re.search(r"(?:topHeight|topbar|top bar|header|顶栏|顶部)[^\d]{0,24}(\d+px)", shell_text, flags=re.I)
    generic_sidebar_match = re.search(r"(?:sidebarWidth|sidebar|side bar|侧边栏|侧栏)[^\d]{0,24}(\d+px)", shell_text, flags=re.I)
    generic_collapsed_match = re.search(r"(?:collapsed|collapse|折叠)[^\d]{0,24}(\d+px)", shell_text, flags=re.I)
    generic_tags_match = re.search(r"(?:tags|tabs|标签页|页签)[^\d]{0,24}(\d+px)", shell_text, flags=re.I)
    if not structured_topbar and topbar_match:
        metrics["topbar"] = topbar_match.group(1)
    elif not structured_topbar and generic_topbar_match:
        metrics["topbar"] = generic_topbar_match.group(1)
    if not structured_sidebar and sidebar_match:
        metrics["sidebar"] = sidebar_match.group(1)
    elif not structured_sidebar and generic_sidebar_match:
        metrics["sidebar"] = generic_sidebar_match.group(1)
    if not structured_sidebar_collapsed and collapsed_match:
        metrics["sidebar_collapsed"] = collapsed_match.group(1)
    elif not structured_sidebar_collapsed and generic_collapsed_match:
        metrics["sidebar_collapsed"] = generic_collapsed_match.group(1)
    if not structured_tags and tags_match:
        metrics["tags"] = tags_match.group(1)
        metrics["has_tags"] = True
    elif not structured_tags and generic_tags_match:
        metrics["tags"] = generic_tags_match.group(1)
        metrics["has_tags"] = True
    return metrics


def _shell_spec_vars(data: dict[str, Any], dark: bool) -> dict[str, str]:
    """Build the ``--spec-*`` shell variables for the :root block.

    Mirrors ``validate_design_folder.expected_shell_tokens``. Returning an
    empty string for a slot tells the caller to skip emitting the CSS line
    instead of writing an empty value.
    """
    metrics = shell_metrics(data)
    layout_rules = mapping(data, "layoutRules")
    app_shell = mapping(layout_rules, "appShell")
    topbar = (
        mapping(app_shell, "topbar")
        or mapping(app_shell, "topBar")
        or mapping(app_shell, "topNav")
    )
    sidebar = mapping(app_shell, "sidebar")
    tags = mapping(app_shell, "tagsBar") or mapping(app_shell, "tags") or mapping(app_shell, "tagsView")

    topbar_bg = _example_lookup(
        data,
        "layoutRules.appShell.topbar.background",
        "layoutRules.appShell.topBar.background",
        "layoutRules.appShell.topNav.background",
        "tokens.colors.shellTopbar",
        "colors.shellTopbar",
    )
    if not topbar_bg:
        topbar_bg = _first_string(
            topbar.get("background"),
            topbar.get("backgroundColor"),
        )
    if not topbar_bg:
        topbar_bg = resolve_color_nested(
            data,
            "shellTopbar",
            "shell-topbar",
            "top-nav-bg",
            "topbar-bg",
            "top-header-bg",
            "nav-bg",
            fallback="",
        )

    sidebar_bg = _first_string(
        sidebar.get("background"),
        sidebar.get("backgroundColor"),
        _example_lookup(data, "tokens.colors.shellSidebar", "colors.shellSidebar"),
    )
    sidebar_text = _first_string(
        sidebar.get("textColor"),
        sidebar.get("color"),
        _example_lookup(data, "tokens.colors.shellSidebarText", "colors.shellSidebarText"),
    )
    sidebar_active_bg = _first_string(
        sidebar.get("activeBackground"),
        sidebar.get("activeBg"),
        _example_lookup(data, "tokens.colors.shellSidebarActiveBg", "colors.shellSidebarActiveBg"),
    )
    tags_bg = _first_string(
        tags.get("background"),
        tags.get("backgroundColor"),
        _example_lookup(data, "tokens.colors.shellTagsBar", "colors.shellTagsBar"),
    )

    return {
        "spec-topbar-bg": resolve_all_refs(topbar_bg, data) if topbar_bg else "",
        "spec-topbar": first_css_length(str(metrics.get("topbar", "") or ""), ""),
        "spec-sidebar-width": first_css_length(str(metrics.get("sidebar", "") or ""), ""),
        "spec-sidebar": resolve_all_refs(sidebar_bg, data) if sidebar_bg else "",
        "spec-sidebar-text": resolve_all_refs(sidebar_text, data) if sidebar_text else "",
        "spec-sidebar-active-bg": resolve_all_refs(sidebar_active_bg, data) if sidebar_active_bg else "",
        "spec-tags": first_css_length(str(metrics.get("tags", "") or ""), ""),
        "spec-tags-bg": resolve_all_refs(tags_bg, data) if tags_bg else "",
    }


def should_render_full_kit_examples(data: dict[str, Any]) -> bool:
    evidence_mode = str(mapping(data, "evidence").get("mode", "")).lower()
    archetype = infer_archetype(data)
    if archetype == "brand-portfolio":
        return False
    source_text = collect_text(data).lower()
    forbidden_terms = (
        "do not add generic saas",
        "no generic saas",
        "no app shell",
        "do not generate admin",
        "不要添加通用",
        "禁止通用",
        "无后台",
        "不要后台",
    )
    if any(term in source_text for term in forbidden_terms):
        return False
    if archetype == "marketing":
        return True
    if evidence_mode in {"brief", "screenshot-only"}:
        return True
    return False


def padded_terms(values: list[str], fallback: list[str], size: int) -> list[str]:
    selected: list[str] = []
    seen: set[str] = set()
    for item in values:
        normalized = re.sub(r"\s+", " ", str(item)).strip()
        if not normalized:
            continue
        key = normalized.casefold()
        if key in seen:
            continue
        seen.add(key)
        selected.append(normalized)
        if len(selected) >= size:
            return selected
    for item in fallback:
        if len(selected) >= size:
            break
        normalized = re.sub(r"\s+", " ", str(item)).strip()
        if not normalized:
            continue
        key = normalized.casefold()
        if key in seen:
            continue
        seen.add(key)
        selected.append(normalized)
    while len(selected) < size:
        selected.append(fallback[-1])
    return selected


def non_generic_terms(values: list[str]) -> list[str]:
    generic = {
        "button",
        "buttons",
        "table",
        "tables",
        "form",
        "forms",
        "input",
        "inputs",
        "select",
        "dialog",
        "drawer",
        "tag",
        "pagination",
        "card",
        "code editor",
        "editor",
        "page shell",
        "section rhythm",
        "app shell",
        "shell",
    }
    return [value for value in values if value.strip().lower() not in generic]


def render_kit_section(data: dict[str, Any], lang: str) -> str:
    if infer_archetype(data) == "brand-portfolio":
        title = "作品集专用校验" if lang == "zh" else "Portfolio-Specific Validation"
        copy = (
            "此规范是品牌/作品集落地页，不渲染后台、数据录入、表格、分页、弹窗等通用产品组件。组件预览仅覆盖文档中明确存在的 ContactButton、LiveProjectButton、项目卡片和页面区块。"
            if lang == "zh"
            else "This is a brand/portfolio landing page. Admin, data-entry, table, pagination, and dialog kit examples are intentionally omitted. The preview only covers documented components such as ContactButton, LiveProjectButton, project cards, and landing sections."
        )
        return f"""
    <section id="kit-mirror" class="source-only-kit">
      <h2>{title}</h2>
      <p class="section-copy">{copy}</p>
    </section>
    """
    if should_render_full_kit_examples(data):
        return kit_mirror_examples_html(data, lang)

    # 对源码派生项目，收起补充校验样例
    title = "补充校验样例" if lang == "zh" else "Supplemental Validation Examples"
    copy = (
        "通用 kit 示例保留为补充校验项；此类 source-derived 项目应以源项目页面样例为主。"
        if lang == "zh"
        else "通用 kit 样例只作为补充检查；源码派生系统应主要通过源产品匹配样例判断。"
    )
    hint = "▸ 展开查看通用 kit 示例" if lang == "zh" else "▸ Expand to view generic kit examples"

    return f"""
    <div class="kit-mirror">
    <section id="kit-mirror">
      <details class="collapsed-section">
        <summary>
          <h2 style="display:inline;font-size:15px;font-weight:600;">{title}</h2>
          <span class="collapse-hint">{hint}</span>
        </summary>
        <div style="margin-top:16px;">
          <p class="section-copy">{copy}</p>
          <p class="muted">{'如需完整 kit-mirror 9-pattern 校验，可在 marketing / brief / screenshot-only 场景下启用。' if lang == 'zh' else 'Enable the full kit-mirror 9-pattern gallery for marketing, brief, or screenshot-only outputs when generic coverage is more valuable.'}</p>
        </div>
      </details>
    </section>
    </div>
    """


def preview_gap_notes(data: dict[str, Any], sections: dict[str, str], lang: str) -> list[str]:
    notes: list[str] = []
    page_patterns = mapping(data, "pagePatterns")
    patterns = mapping(data, "patterns")
    shadows = mapping(data, "shadows")
    motion = mapping(data, "motion")
    runtime = mapping(data, "runtime")
    dark_info = resolve_dark_evidence(data, sections)
    if not page_patterns and not patterns:
        notes.append("缺少页面模式，样例可能更多依赖 archetype 推断。" if lang == "zh" else "No page patterns documented, so the specimen falls back more heavily to archetype inference.")
    if not shadows:
        notes.append("未记录阴影令牌。" if lang == "zh" else "Shadow tokens are not documented.")
    if not motion:
        notes.append("未记录动效令牌。" if lang == "zh" else "Motion tokens are not documented.")
    if not runtime:
        notes.append("未记录运行态主题或布局状态。" if lang == "zh" else "Runtime theme/layout state is not documented.")
    if dark_info["strategy"] != "Real Dark Mode":
        notes.append(
            "暗色页为检查视图或未确认状态，请勿将其视为真实暗色实现。" if lang == "zh" else "Dark preview is an inspection view or unavailable state, not a confirmed production dark runtime."
        )
    return notes[:4]


def resolve_dark_evidence(data: dict[str, Any], sections: dict[str, str]) -> dict[str, str]:
    runtime = mapping(data, "runtime")
    runtime_theme = mapping(runtime, "theme")
    evidence = mapping(data, "evidence")
    known_limits = mapping(data, "knownLimits")
    confidence = mapping(data, "confidence")
    colors = mapping(data, "colors")
    known_gaps_text = " ".join(
        [sections.get("Known Gaps", ""), sections.get("Known Limits & Evidence Summary", ""),
         sections.get("Quality Checklist", ""), sections.get("AI Generation Rules, Forbidden Patterns & Self-Check", ""),
         collect_text(runtime), collect_text(evidence), collect_text(known_limits), collect_text(confidence)]
    ).lower()
    observed_text = " ".join([collect_text(runtime), collect_text(evidence), " ".join(sections.values())]).lower()
    dark_color_keys = [str(key) for key in colors.keys() if any(term in str(key).lower() for term in ("dark", "inverse", "night"))]
    dark_confidence = str(confidence.get("darkMode", "")).strip().lower()
    theme_mode = str(
        runtime_theme.get("mode", "")
        or runtime_theme.get("themeMode", "")
        or runtime_theme.get("name", "")
    ).strip().lower()
    dark_strategy_value = str(runtime_theme.get("darkStrategy", "")).strip().lower()
    if dark_strategy_value in {"real-dark-mode", "real dark mode", "production-dark", "production dark"}:
        return {
            "strategy": "Real Dark Mode",
            "reason": "runtime.theme.darkStrategy identifies a confirmed production dark runtime.",
        }
    if dark_strategy_value in {"dark-inspection-view", "dark inspection view", "inspection"}:
        return {
            "strategy": "Dark Inspection View",
            "reason": "runtime.theme.darkStrategy marks the dark file as an inspection view.",
        }
    if dark_strategy_value in {"unavailable", "dark-strategy-unavailable", "dark strategy unavailable"}:
        return {
            "strategy": "Dark Strategy Unavailable",
            "reason": "runtime.theme.darkStrategy marks dark mode as unavailable.",
        }
    if theme_mode == "dark-only":
        return {
            "strategy": "Real Dark Mode",
            "reason": "runtime.theme.mode identifies dark as the only production theme.",
        }
    if theme_mode == "light-only":
        return {
            "strategy": "Dark Strategy Unavailable",
            "reason": "runtime.theme.mode identifies light as the only production theme.",
        }
    if theme_mode in {"supports-both", "both", "light-dark", "light/dark"}:
        return {
            "strategy": "Real Dark Mode",
            "reason": "runtime.theme.mode indicates both light and dark production themes are supported.",
        }
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
    observed_terms = (
        "real dark",
        "dark theme",
        "dark-themed",
        "dark mode observed",
        "dark mode enabled",
        "theme: dark",
        "theme dark",
        "supports dark mode",
        "observed dark",
        "dark runtime",
        "真实暗色",
        "暗色模式已观察",
        "已观察到暗色",
        "支持暗色模式",
        "主题为暗色",
    )
    if is_single_dark_theme(data):
        return {
            "strategy": "Real Dark Mode",
            "reason": "Runtime notes indicate a dark-only production system.",
        }
    if dark_confidence in {"none", "unknown", "unsupported", "unavailable", "unconfirmed", "low"}:
        return {
            "strategy": "Dark Strategy Unavailable",
            "reason": "confidence.darkMode indicates dark mode is unavailable or unconfirmed.",
        }
    if mentions_any(known_gaps_text, unavailable_terms):
        return {
            "strategy": "Dark Strategy Unavailable",
            "reason": "Known gaps or runtime notes explicitly say dark mode is unavailable or unconfirmed.",
        }
    if dark_color_keys or mentions_any(observed_text, observed_terms):
        return {
            "strategy": "Real Dark Mode",
            "reason": "Source evidence or token structure indicates an observed dark mode.",
        }
    return {
        "strategy": "Dark Inspection View",
        "reason": "No confirmed dark runtime was observed, so the preview uses a brand-consistent inspection palette.",
    }


def resolve_design_md(design_dir: Path, requested_name: str) -> Path:
    exact_entries = {
        entry.name: entry for entry in design_dir.iterdir() if entry.is_file()
    }

    if requested_name != "auto":
        path = exact_entries.get(requested_name)
        if path is None:
            raise FileNotFoundError(f"缺少必需文件：{requested_name}")
        other = "design.md" if requested_name == "DESIGN.md" else "DESIGN.md"
        if other in exact_entries:
            raise ValueError("DESIGN.md 和 design.md 同时存在。请只保留一个 Markdown 单一事实源文件。")
        return path

    present = [name for name in SUPPORTED_MARKDOWN_FILES if name in exact_entries]
    if not present:
        raise FileNotFoundError("缺少 DESIGN.md 或 design.md")
    if len(present) > 1:
        raise ValueError("DESIGN.md 和 design.md 同时存在。请只保留一个。")
    return exact_entries[present[0]]


def css_var_name(namespace: str, key: str) -> str:
    normalized = re.sub(r"[^a-zA-Z0-9_-]+", "-", key).strip("-").lower()
    return f"--{namespace}-{normalized}"


def first_css_length(value: str, fallback: str) -> str:
    """Return a usable CSS length from descriptive responsive token strings."""
    text = str(value or "").strip()
    if not text:
        return fallback
    if re.fullmatch(r"-?\d+(?:\.\d+)?", text):
        return "0" if float(text) == 0 else f"{text}px"
    if "/" not in text and re.fullmatch(r"(?:-?\d+(?:\.\d+)?(?:px|rem|em|vh|vw|%)|0|clamp\([^)]+\)|9999px)", text):
        return text
    match = re.search(r"-?\d+(?:\.\d+)?(?:px|rem|em|vh|vw|%)", text)
    return match.group(0) if match else fallback


def _example_css_length(value: Any, fallback: str) -> str:
    return first_css_length(str(value or ""), fallback)


def css_scalar(value: Any, *, css_key: str = "") -> str:
    """Normalize scalar token values for executable CSS contexts."""
    if value is None:
        return ""
    text = str(value).strip()
    if not text:
        return ""
    if css_key in CSS_LENGTH_KEYS and re.fullmatch(r"-?\d+(?:\.\d+)?", text):
        return "0" if float(text) == 0 else f"{text}px"
    return text


def _example_lookup(data: dict[str, Any], *paths: str) -> str:
    for path in paths:
        current: Any = data
        for part in path.split("."):
            if isinstance(current, dict) and part in current:
                current = current[part]
            else:
                current = None
                break
        if current not in (None, "", [], {}):
            return str(current)
    return ""


def is_safe_custom_property_value(value: str) -> bool:
    """Filter prose-only token values out of generated CSS variables."""
    text = str(value or "").strip()
    if not text or "\n" in text:
        return False
    lowered = text.lower()
    if " per breakpoint" in lowered or "mobile/" in lowered or "horizontal" in lowered:
        return False
    if re.search(r"\d(?:px|rem|em|vh|vw|%)\s*/\s*\d", text):
        return False
    if re.search(r"\d(?:px|rem|em|vh|vw|%)-\d", text):
        return False
    return True


def is_single_dark_theme(data: dict[str, Any]) -> bool:
    runtime_text = collect_text(mapping(data, "runtime")).lower()
    known_text = collect_text(mapping(data, "knownLimits")).lower()
    description = str(data.get("description", "")).lower()
    blob = " ".join([runtime_text, known_text, description])
    return any(
        term in blob
        for term in (
            "dark-only",
            "dark only",
            "dark theme",
            "dark-themed",
            "dark-portfolio",
            "暗色唯一",
            "仅有暗色",
            "暗色单主题",
        )
    )


_RGBA_BLACK_RE = re.compile(r"rgba?\(\s*0\s*,\s*0\s*,\s*0\s*(?:,\s*([0-9.]+)\s*)?\)", re.I)


def _invert_text_color_for_dark(value: str) -> str:
    """Flip light-mode text colors to dark-mode equivalents.

    Typography token colors are often authored as rgba(0,0,0,alpha). On a dark
    canvas those are unreadable, so we mirror them to rgba(255,255,255,alpha)
    while preserving the alpha channel. Hex #000/#111 style near-blacks get the
    same treatment. Non-matching values pass through unchanged so brand hex
    tokens (#003EB3 etc.) are not touched.
    """
    if not value:
        return value
    v = value.strip()
    m = _RGBA_BLACK_RE.search(v)
    if m:
        alpha = m.group(1) if m.group(1) else "1"
        return _RGBA_BLACK_RE.sub(f"rgba(255, 255, 255, {alpha})", v)
    low = v.lower()
    if low in ("#000", "#000000"):
        return "rgba(255, 255, 255, 0.9)"
    if low in ("#111", "#111111", "#1a1a1a", "#222", "#222222"):
        return "rgba(255, 255, 255, 0.85)"
    return v


def flatten(prefix: str, value: Any) -> list[tuple[str, str]]:
    rows: list[tuple[str, str]] = []
    if isinstance(value, dict):
        for key, child in value.items():
            child_prefix = f"{prefix}-{key}" if prefix else str(key)
            rows.extend(flatten(child_prefix, child))
    else:
        rows.append((prefix, str(value)))
    return rows


def mapping(data: dict[str, Any], key: str) -> dict[str, Any]:
    value = data.get(key)
    return value if isinstance(value, dict) else {}


def token_value(value: Any) -> str:
    if isinstance(value, dict):
        nested = value.get("value")
        if nested is not None:
            return str(nested) if not isinstance(nested, (dict, list, tuple)) else responsive_token_value(nested)
        return responsive_token_value(value)
    if isinstance(value, bool):
        return str(value).lower()
    if value is None or isinstance(value, (list, tuple)):
        return ""
    return str(value)


def is_css_length_like(value: str) -> bool:
    return bool(
        re.fullmatch(
            r"-?\d+(?:\.\d+)?(?:px|rem|em|vh|vw|%|ch|ex|vmin|vmax|svh|lvh|dvh)?",
            value.strip(),
            flags=re.I,
        )
    )


def responsive_token_value(value: Any, *, css_key: str = "") -> str:
    """Return an executable CSS scalar for token values that may be breakpoint maps."""
    if isinstance(value, dict):
        nested = value.get("value")
        if nested is not None and not isinstance(nested, (dict, list, tuple)):
            return css_scalar(nested, css_key=css_key)
        ordered_keys = (
            "base",
            "default",
            "mobile",
            "xs",
            "sm",
            "md",
            "lg",
            "xl",
            "2xl",
            "desktop",
        )
        pairs: list[tuple[str, str]] = []
        for key in ordered_keys:
            child = value.get(key)
            if child is not None and not isinstance(child, (dict, list, tuple)):
                pairs.append((key, str(child)))
        if pairs:
            if css_key == "font-size":
                low = css_scalar(pairs[0][1], css_key=css_key)
                mid = css_scalar(next((item for key, item in pairs if key in {"sm", "md", "desktop"}), pairs[min(1, len(pairs) - 1)][1]), css_key=css_key)
                high = css_scalar(next((item for key, item in reversed(pairs) if key in {"lg", "xl", "2xl", "desktop"}), pairs[-1][1]), css_key=css_key)
                if all(is_css_length_like(item) for item in (low, mid, high)):
                    return f"clamp({low}, {mid}, {high})"
            return css_scalar(pairs[0][1], css_key=css_key)
        if isinstance(nested, dict):
            return responsive_token_value(nested, css_key=css_key)
        return ""
    if isinstance(value, (list, tuple)):
        for item in value:
            normalized = responsive_token_value(item, css_key=css_key)
            if normalized:
                return normalized
        return ""
    if isinstance(value, bool):
        return str(value).lower()
    if value is None:
        return ""
    return css_scalar(value, css_key=css_key)


def resolve_refs(text: str, data: dict[str, Any]) -> str:
    """Resolve {group.token} / {tokens.colors.primary} references."""
    if not text or "{" not in text:
        return text

    def _replace(match: re.Match) -> str:
        ref_path = match.group(1)
        parts = [part for part in ref_path.split(".") if part]
        if len(parts) < 2:
            return match.group(0)
        current: Any = data
        value: Any = None
        for part in parts:
            if not isinstance(current, dict):
                value = None
                break
            if part in current:
                value = current[part]
                current = value
                continue
            lowered = part.lower()
            matched = False
            for key, val in current.items():
                if str(key).lower() == lowered:
                    value = val
                    current = val
                    matched = True
                    break
            if not matched:
                value = None
                break
        if value is not None:
            resolved = token_value(value)
            if resolved:
                return resolved
            # 对没有 `value` 键的 dict token（例如 typography），
            # 返回最有用属性的紧凑摘要。
            if isinstance(value, dict):
                compact = compact_value(value, data)
                if compact:
                    return compact
        return match.group(0)

    return TOKEN_REF_RE.sub(_replace, text)


def resolve_all_refs(text: str, data: dict[str, Any], max_passes: int = 4) -> str:
    """Resolve nested token references without looping forever on missing tokens."""
    current = text
    for _ in range(max_passes):
        resolved = resolve_refs(current, data)
        if resolved == current:
            break
        current = resolved
    return current


def token_role(value: Any) -> str:
    if isinstance(value, dict):
        role = value.get("role") or value.get("description") or value.get("usage")
        return str(role) if role is not None else ""
    return ""


def token(data: dict[str, Any], group: str, *names: str, fallback: str) -> str:
    source = mapping(data, group)
    for name in names:
        value = token_value(source.get(name))
        if value:
            return value
    lowered_names = [name.lower() for name in names]
    for key, value in source.items():
        lowered_key = str(key).lower()
        if any(name in lowered_key for name in lowered_names):
            normalized = token_value(value)
            if normalized:
                return normalized
    return fallback


def resolve_color_nested(data: dict[str, Any], *names: str, fallback: str) -> str:
    """Like token(data, 'colors', *names, fallback=...) but also walks nested groups.

    Handles both flat color dicts (colors.primary → "#xxx") and nested ones
    (colors.primary-colors.primary → {value: "#xxx", role: "…"}).
    """
    colors = mapping(data, "colors")
    # 先尝试扁平查找
    for name in names:
        v = token_value(colors.get(name))
        if v:
            return v
    # 再遍历嵌套分组
    for _, group in colors.items():
        if isinstance(group, dict):
            # 检查精确名称键
            for name in names:
                v = token_value(group.get(name))
                if v:
                    return v
            # 检查模糊名称匹配
            for k, gv in group.items():
                lowered_k = str(k).lower()
                if any(n.lower() in lowered_k for n in names):
                    v = token_value(gv)
                    if v:
                        return v
    return fallback


def first_typography(data: dict[str, Any], *name_parts: str) -> dict[str, Any]:
    typography = mapping(data, "typography")
    base_family = str(
        typography.get("baseFontFamily")
        or typography.get("fontFamily")
        or typography.get("font-family")
        or ""
    ).strip()

    def with_base_family(value: dict[str, Any]) -> dict[str, Any]:
        result = dict(value)
        if base_family and not any(key in result for key in ("fontFamily", "font-family")):
            result["fontFamily"] = base_family
        return result

    for key, value in typography.items():
        if all(part in key for part in name_parts) and isinstance(value, dict):
            return with_base_family(value)
    for value in typography.values():
        if isinstance(value, dict):
            return with_base_family(value)
    return {"fontFamily": base_family} if base_family else {}


def style_from_type(type_token: dict[str, Any], data: dict[str, Any] | None = None) -> str:
    pairs = []
    mapping_keys = {
        "fontFamily": "font-family",
        "fontSize": "font-size",
        "fontWeight": "font-weight",
        "lineHeight": "line-height",
        "letterSpacing": "letter-spacing",
    }
    for key, css_key in mapping_keys.items():
        if key in type_token:
            css_value = responsive_token_value(type_token[key], css_key=css_key)
            if css_value:
                if data is not None:
                    css_value = resolve_refs(css_value, data)
                pairs.append(f"{css_key}: {css_value}")
    return "; ".join(pairs)


def attr_escape(value: Any) -> str:
    """Escape values inserted into HTML attributes."""
    return html.escape(str(value), quote=True)


def style_attr(value: Any) -> str:
    """Escape a CSS declaration list before putting it in a style attribute."""
    return attr_escape(value)


def inline_markdown(text: str) -> str:
    safe = html.escape(text)
    safe = re.sub(r"`([^`]+)`", r"<code>\1</code>", safe)
    safe = re.sub(r"\*\*([^*]+)\*\*", r"<strong>\1</strong>", safe)
    safe = re.sub(r"\*([^*]+)\*", r"<em>\1</em>", safe)
    return safe


def markdown_excerpt(markdown: str, empty: str = "Not documented") -> str:
    """Convert markdown body text to safe inline-HTML fragments.

    Block-level elements (headings, lists, blockquotes) are kept as blocks.
    Adjacent paragraph lines are merged into a single <p> to avoid nested-<p> bugs.
    """
    BLOCK_TAGS = {"h4", "ul", "blockquote", "ol"}
    blocks: list[str] = []
    para_buf: list[str] = []
    list_buf: list[str] = []

    def _flush_para() -> None:
        if para_buf:
            blocks.append(f"<p>{' '.join(para_buf)}</p>")
            para_buf.clear()

    def _flush_list() -> None:
        if list_buf:
            blocks.append(f"<ul>{''.join(list_buf)}</ul>")
            list_buf.clear()

    for raw in markdown.splitlines():
        stripped = raw.strip()
        if not stripped:
            _flush_para()
            _flush_list()
            continue
        if stripped.startswith("```"):
            _flush_para()
            _flush_list()
            continue
        if stripped.startswith("###"):
            _flush_para()
            _flush_list()
            blocks.append(f"<h4>{inline_markdown(stripped.lstrip('#').strip())}</h4>")
        elif stripped.startswith("- [ ] ") or stripped.startswith("- [x] "):
            _flush_para()
            checked = "checked" if stripped.startswith("- [x] ") else ""
            label = stripped[6:].strip()
            list_buf.append(f"<li><span class=\"check {checked}\"></span>{inline_markdown(label)}</li>")
        elif stripped.startswith("- "):
            _flush_para()
            list_buf.append(f"<li>{inline_markdown(stripped[2:].strip())}</li>")
        elif stripped.startswith(">"):
            _flush_para()
            _flush_list()
            blocks.append(f"<blockquote>{inline_markdown(stripped.lstrip('>').strip())}</blockquote>")
        elif re.match(r"^\d+\.\s+", stripped):
            _flush_para()
            _flush_list()
            blocks.append(f"<p>{inline_markdown(stripped)}</p>")
        else:
            _flush_list()
            para_buf.append(inline_markdown(stripped))
        if len(blocks) + (1 if para_buf else 0) + (1 if list_buf else 0) >= 12:
            break
    _flush_para()
    _flush_list()
    if not blocks:
        return f"<p class=\"muted\">{empty}</p>"
    return "\n".join(blocks)


def color_group(name: str) -> str:
    lowered = name.lower()
    if any(term in lowered for term in ("success", "warning", "error", "danger", "info")):
        return "Semantic"
    if any(term in lowered for term in ("ink", "text", "muted", "body", "caption")):
        return "Text"
    if any(term in lowered for term in ("canvas", "surface", "bg", "background")):
        return "Surface"
    if any(term in lowered for term in ("hairline", "border", "stroke", "rule")):
        return "Border"
    if any(term in lowered for term in ("primary", "brand", "accent", "link")):
        return "Brand"
    return "Accent / Data"


def _flatten_color_leaves(colors: dict[str, Any]) -> list[tuple[str, str, str]]:
    """Return (name, value, role) triples from flat *or* nested color groups.

    Handles shapes like:
      colors:
        primary: "#003EB3"                     # flat scalar
        brand:   { value: "#003EB3", role: "x" }  # flat dict
        primary-colors:                        # nested group
          primary: { value: "#003EB3", role: "x" }
          primary-hover: "#0958d9"
    """
    out: list[tuple[str, str, str]] = []
    for name, value in colors.items():
        # flat scalar
        if isinstance(value, str):
            out.append((str(name), value, ""))
            continue
        if isinstance(value, dict):
            # leaf dict (has "value")
            if "value" in value and not any(
                isinstance(v, dict) for v in value.values()
            ):
                v = token_value(value)
                if v:
                    out.append((str(name), v, token_role(value)))
                continue
            # nested group → recurse one level
            for leaf_name, leaf_value in value.items():
                nested_name = f"{name}.{leaf_name}"
                if isinstance(leaf_value, str):
                    out.append((nested_name, leaf_value, ""))
                elif isinstance(leaf_value, dict):
                    v = token_value(leaf_value)
                    if v:
                        out.append((nested_name, v, token_role(leaf_value)))
    return out


def grouped_swatches(colors: dict[str, Any]) -> str:
    groups = ["Brand", "Text", "Surface", "Border", "Semantic", "Accent / Data"]
    grouped: dict[str, list[tuple[str, str, str]]] = {group: [] for group in groups}
    for name, value, role in _flatten_color_leaves(colors):
        grouped[color_group(name)].append((name, value, role))

    blocks = []
    for group in groups:
        rows = []
        for name, value, role in grouped[group]:
            safe_name = html.escape(name)
            safe_value = html.escape(value)
            role_html = f"<span>{html.escape(role)}</span>" if role else ""
            rows.append(
                f"""
                <article class="swatch">
                  <div class="swatch-color" style="background:{safe_value}"></div>
                  <div class="swatch-body">
                    <strong>{safe_name}</strong>
                    <code>{safe_value}</code>
                    {role_html}
                  </div>
                </article>"""
            )
        if rows:
            blocks.append(
                f"""
                <div class="token-group">
                  <h3>{html.escape(group)}</h3>
                  <div class="grid colors">{"".join(rows)}</div>
                </div>"""
            )
    return "\n".join(blocks) or "<p class=\"muted\">No color tokens documented.</p>"


def typography_samples(data: dict[str, Any], lang: str = "en") -> str:
    typography = mapping(data, "typography")
    samples = product_sample_copy(data, lang)
    entries: list[dict[str, str]] = []
    for raw_name, value in typography.items():
        if not isinstance(value, dict):
            continue
        name = str(raw_name)
        entries.append(
            {
                "name": name,
                "style": style_from_type(value, data),
                "style_escaped": style_attr(style_from_type(value, data)),
                "meta": " / ".join(
                    responsive_token_value(value.get(key), css_key={
                        "fontSize": "font-size",
                        "fontFamily": "font-family",
                        "fontWeight": "font-weight",
                        "lineHeight": "line-height",
                        "letterSpacing": "letter-spacing",
                    }.get(key, ""))
                    or "n/a"
                    for key in ("fontSize", "fontWeight", "lineHeight", "letterSpacing")
                ),
                "sample": typography_role_sample(name, lang, samples),
                "usage": typography_role_usage(name, lang),
                "group": typography_role_group(name, lang),
                "signature": typography_signature(value),
            }
        )

    if not entries:
        return "<p class=\"muted\">No typography tokens documented.</p>"

    preferred_order = ("page-title", "section-title", "body", "dense-body", "caption", "micro", "button")
    ordered = sorted(
        entries,
        key=lambda entry: (
            preferred_order.index(entry["name"]) if entry["name"] in preferred_order else len(preferred_order),
            entry["name"],
        ),
    )
    overview_entries = ordered[:5]
    matrix_rows = "".join(
        f"""
        <div class="type-matrix-row">
          <strong>{html.escape(entry['name'])}</strong>
          <span class="type-group-chip">{html.escape(entry['group'])}</span>
          <div class="type-sample-cell" style="{entry['style_escaped']}">{html.escape(entry['sample'])}</div>
          <code>{html.escape(entry['meta'])}</code>
          <span>{html.escape(entry['usage'])}</span>
        </div>"""
        for entry in ordered
    )
    ladder_rows = "".join(
        f"""
        <div class="type-ladder-row">
          <span>{html.escape(entry['usage'])}</span>
          <strong style="{entry['style_escaped']}">{html.escape(entry['sample'])}</strong>
          <code>{html.escape(entry['name'])}</code>
        </div>"""
        for entry in overview_entries
    )
    same_style_note = typography_semantic_overlap_note(ordered, lang)
    z = lang == "zh"
    samples = product_sample_copy(data, lang)
    return f"""
    <div class="type-showcase">
      <article class="surface-card type-ladder">
        <div class="type-card-title">
          <strong>{'字体层级总览' if z else 'Typography Ladder'}</strong>
          <span>{'先看层级差异，再看参数。' if z else 'Read hierarchy first, then inspect values.'}</span>
        </div>
        <div class="type-ladder-list">{ladder_rows}</div>
      </article>
      <article class="surface-card type-context-demo">
        <div class="type-card-title">
          <strong>{'产品语境小样' if z else 'Product Context Sample'}</strong>
          <span>{'把标题、正文、辅助文字和按钮放回真实页面。' if z else 'Put titles, body, metadata, and actions back into context.'}</span>
        </div>
        <div class="type-context-shell">
          <div class="type-context-head">
            <strong>{html.escape(samples['title'])}</strong>
            <button>{html.escape(samples['action'])}</button>
          </div>
          <div class="type-context-panel">
            <strong>{html.escape(samples['section'])}</strong>
            <p>{html.escape(samples['body'])}</p>
            <span>{html.escape(samples['meta'])}</span>
          </div>
        </div>
      </article>
    </div>
    {same_style_note}
    <div class="type-matrix">
      <div class="type-matrix-head">
        <strong>{'角色' if z else 'Role'}</strong>
        <strong>{'分组' if z else 'Group'}</strong>
        <strong>{'样例' if z else 'Sample'}</strong>
        <strong>{'规格' if z else 'Specs'}</strong>
        <strong>{'使用场景' if z else 'Usage'}</strong>
      </div>
      {matrix_rows}
    </div>
    """


def typography_role_group(name: str, lang: str) -> str:
    lowered = name.lower()
    z = lang == "zh"
    if "button" in lowered or "label" in lowered:
        return "交互文本" if z else "Interaction"
    if "body" in lowered or "caption" in lowered or "micro" in lowered or "helper" in lowered:
        return "内容阅读" if z else "Reading"
    return "页面结构" if z else "Structure"


def _label_values(value: Any) -> list[str]:
    labels: list[str] = []
    if isinstance(value, dict):
        for key, child in value.items():
            if str(key).lower() in {"label", "text", "title"} and isinstance(child, str) and child.strip():
                labels.append(child.strip())
            labels.extend(_label_values(child))
    elif isinstance(value, list):
        for item in value:
            labels.extend(_label_values(item))
    return labels


def product_sample_copy(data: dict[str, Any], lang: str) -> dict[str, str]:
    z = lang == "zh"
    title = str(data.get("name", "")).strip() or ("页面标题" if z else "Page Title")
    page_templates = page_template_items(data)
    page_patterns = mapping(data, "pagePatterns")
    template_names = [
        str(item.get("name") or item.get("title") or item.get("id") or "").strip()
        for item in page_templates
        if str(item.get("name") or item.get("title") or item.get("id") or "").strip()
    ] or list(page_patterns.keys())
    section = localize_term(humanize_identifier(str(template_names[0])), lang) if template_names else ("核心内容" if z else "Core Section")
    labels = _label_values(mapping(data, "components")) + _label_values(mapping(data, "componentRecipes"))
    action = next((label for label in labels if 1 <= len(label) <= 32), "")
    if not action:
        action_terms = extract_product_terms(data, lang).get("actions", [])
        action = action_terms[0] if action_terms else ("查看详情" if z else "View Details")
    description = str(data.get("description", "")).strip()
    if description:
        sentence = re.split(r"(?<=[.!?。！？])\s+", description)[0].strip()
        body = sentence[:150]
    else:
        body = "使用当前设计系统中的真实页面内容和组件语义。" if z else "Use real page content and component semantics from this design system."
    return {
        "title": title,
        "section": section,
        "body": body,
        "action": action,
        "meta": "最近更新" if z else "Recently updated",
    }


def typography_role_sample(name: str, lang: str, samples: dict[str, str]) -> str:
    lowered = name.lower()
    z = lang == "zh"
    if "button" in lowered:
        return samples["action"]
    if "dense-body" in lowered or "caption" in lowered or "micro" in lowered or "helper" in lowered:
        return samples["meta"]
    if "body" in lowered:
        return samples["body"]
    if "section" in lowered:
        return samples["section"]
    if "page" in lowered or "display" in lowered or "heading" in lowered or "title" in lowered:
        return samples["title"]
    return "设计系统文字样例" if z else "Design system type sample"


def typography_role_usage(name: str, lang: str) -> str:
    lowered = name.lower()
    z = lang == "zh"
    if "button" in lowered:
        return "按钮与关键操作" if z else "Buttons and key actions"
    if "dense-body" in lowered or "caption" in lowered or "micro" in lowered or "helper" in lowered:
        return "辅助信息与元数据" if z else "Metadata and helper text"
    if "body" in lowered:
        return "正文、表格、说明段落" if z else "Body copy, tables, supporting text"
    if "section" in lowered:
        return "模块标题与区块切分" if z else "Section headings and grouping"
    if "page" in lowered or "display" in lowered or "heading" in lowered or "title" in lowered:
        return "页面主标题" if z else "Primary page headings"
    return "系统内通用文本" if z else "General product text"


def typography_signature(value: dict[str, Any]) -> str:
    return "|".join(
        str(value.get(key, ""))
        for key in ("fontFamily", "fontSize", "fontWeight", "lineHeight", "letterSpacing")
    )


def typography_semantic_overlap_note(entries: list[dict[str, str]], lang: str) -> str:
    by_signature: dict[str, list[str]] = {}
    for entry in entries:
        by_signature.setdefault(entry["signature"], []).append(entry["name"])
    duplicated = [names for names in by_signature.values() if len(names) > 1]
    if not duplicated:
        return ""
    z = lang == "zh"
    names = " / ".join(html.escape("、".join(group)) for group in duplicated[:2])
    copy = (
        f"{names} 当前共享同一组视觉值，但承担不同语义层级；保留独立 token 有助于后续页面结构稳定。"
        if z
        else f"{names} currently share the same visual values, but they describe different semantic levels; keeping separate tokens protects page hierarchy."
    )
    return f'<div class="type-semantic-note"><strong>{"同值异义说明" if z else "Semantic Note"}</strong><span>{copy}</span></div>'


def scale_rows(group: dict[str, Any], label: str) -> str:
    rows = []
    for name, value in group.items():
        safe_value_raw = token_value(value)
        if not safe_value_raw:
            continue
        safe_name = html.escape(str(name))
        safe_value = html.escape(safe_value_raw)
        visual = ""
        if label == "Spacing":
            if re.fullmatch(r"-?\d+(?:\.\d+)?(?:px|rem|em|%)", safe_value_raw.strip()):
                visual = f"<span class=\"measure\" style=\"width:{safe_value}\"></span>"
        elif label == "Radius":
            radius_value = html.escape(first_css_length(safe_value_raw, "8px"))
            visual = f"<span class=\"radius-demo\" style=\"border-radius:{radius_value}\"></span>"
        elif label == "Elevation":
            visual = f"<span class=\"shadow-demo\" style=\"box-shadow:{safe_value}\"></span>"
        rows.append(
            f"<article class=\"scale-row\"><strong>{safe_name}</strong><code>{safe_value}</code>{visual}</article>"
        )
    return "\n".join(rows) or f"<p class=\"muted\">No {label.lower()} tokens documented.</p>"


def _token_usage(kind: str, name: str, lang: str) -> str:
    z = lang == "zh"
    lowered = name.lower()
    if kind == "spacing":
        if lowered in {"xxs", "2xs"}:
            return "图标与文字、极密集微间距" if z else "Icon/text micro spacing"
        if lowered in {"xs", "sm"}:
            return "表单控件、按钮组、紧邻元素" if z else "Controls, button groups, adjacent items"
        if lowered in {"md", "lg"}:
            return "卡片内边距、分组之间" if z else "Panel padding and group gaps"
        if lowered in {"xl", "xxl"}:
            return "页面区块、模块纵向节奏" if z else "Section rhythm and page spacing"
        if lowered == "section":
            return "弹窗与顶栏壳层的大块内边距" if z else "Dialog body and shell padding"
        if lowered == "formitem":
            return "表单项纵向间距" if z else "Vertical gap between form items"
        if lowered == "contentmargin":
            return "主内容区相对壳层的外圈留白" if z else "Outer margin around main content canvas"
        return "通用间距尺度" if z else "General spacing scale"
    if kind == "radius":
        if "pill" in lowered:
            return "标签、胶囊态控件" if z else "Tags and pill controls"
        if lowered in {"xs", "sm"}:
            return "按钮、输入框、轻控件" if z else "Buttons, inputs, compact controls"
        return "卡片、面板、弹窗容器" if z else "Cards, panels, dialog shells"
    if kind == "shadow":
        if lowered in {"none", "flat"}:
            return "平面容器，依赖边框分层" if z else "Flat surfaces separated by borders"
        if "shell" in lowered:
            return "顶栏、页签、应用壳层" if z else "Top bars, tabs, shell chrome"
        if "panel" in lowered or "surface" in lowered:
            return "轻浮层或局部强调面板" if z else "Subtle raised panels"
        return "弹窗、下拉、强悬浮层" if z else "Dialogs, dropdowns, higher elevation"
    return "—"


def spacing_preview_bar_width(css_length: str) -> str | None:
    """Return spacing token length at 1:1 screen pixels (no preview scaling)."""
    normalized = first_css_length(str(css_length or "").strip(), "")
    if not normalized or not is_css_length_like(normalized):
        return None
    return normalized


def spacing_token_usage(value: Any, name: str, lang: str) -> str:
    if isinstance(value, dict):
        custom = value.get("usage") or value.get("description")
        if custom:
            return str(custom).strip()
    return _token_usage("spacing", str(name), lang)


def spacing_spec(group: dict[str, Any], lang: str) -> str:
    rows = []
    bars = []
    for name, value in group.items():
        raw = token_value(value)
        if not raw:
            continue
        safe_name = html.escape(str(name))
        css_len = first_css_length(str(raw).strip(), "")
        safe_value = html.escape(css_len or str(raw).strip())
        usage = html.escape(spacing_token_usage(value, str(name), lang))
        preview_width = spacing_preview_bar_width(css_len or str(raw))
        if preview_width:
            escaped_width = html.escape(preview_width)
            bar = (
                f'<div class="spacing-gap-demo" title="{safe_value}">'
                f'<span class="spacing-block" aria-hidden="true"></span>'
                f'<span class="spacing-gap" style="width:{escaped_width};" aria-hidden="true"></span>'
                f'<span class="spacing-block" aria-hidden="true"></span>'
                f"</div>"
            )
        else:
            bar = '<span class="measure-rich text">—</span>'
        rows.append(
            f"""
            <article class="scale-card">
              <div class="scale-meta"><strong>{safe_name}</strong><code>{safe_value}</code></div>
              <div class="scale-visual spacing-true-scale">{bar}</div>
              <p>{usage}</p>
            </article>"""
        )
        bars.append(f"<span>{safe_name} · {safe_value}</span>")
    if not rows:
        return "<p class=\"muted\">No spacing tokens documented.</p>"
    joined = "".join(rows)
    chips = "".join(f"<span class=\"mini-pill\">{item}</span>" for item in bars[:6])
    return f"""
    <div class="section-note">{'间距示意按 1:1 屏幕像素：中间透明区域宽度即令牌数值（8px 在屏幕上仅为 8 个 CSS 像素）。' if lang == 'zh' else 'Spacing previews use 1:1 screen pixels: the middle gap width equals the token value.'}</div>
    <div class="scale-gallery">{joined}</div>
    <div class="usage-strip">
      <strong>{'典型组合' if lang == 'zh' else 'Typical combinations'}</strong>
      <div>{chips}</div>
      <p>{'按钮组、表单区、内容面板与页面段落应分别使用不同节奏，避免全页只有一种留白。' if lang == 'zh' else 'Button groups, form areas, panels, and sections should use distinct rhythm instead of one repeated gap everywhere.'}</p>
    </div>
    """


def radius_spec(group: dict[str, Any], lang: str) -> str:
    cards = []
    for name, value in group.items():
        raw = token_value(value)
        if not raw:
            continue
        safe_name = html.escape(str(name))
        safe_value = html.escape(raw)
        css_radius = html.escape(first_css_length(raw, "8px"))
        usage = html.escape(_token_usage("radius", str(name), lang))
        cards.append(
            f"""
            <article class="radius-card-demo">
              <div class="radius-shape" style="border-radius:{css_radius};"></div>
              <div class="scale-meta"><strong>{safe_name}</strong><code>{safe_value}</code></div>
              <p>{usage}</p>
            </article>"""
        )
    if not cards:
        return "<p class=\"muted\">No radius tokens documented.</p>"
    return f"""
    <div class="section-note">{'圆角要直接对应组件族，而不是只记住数值。' if lang == 'zh' else 'Radius values should map to component families, not stay as abstract numbers.'}</div>
    <div class="radius-gallery">{''.join(cards)}</div>
    """


def elevation_spec(group: dict[str, Any], lang: str) -> str:
    cards = []
    for name, value in group.items():
        raw = token_value(value)
        if not raw:
            continue
        safe_name = html.escape(str(name))
        safe_value = html.escape(raw)
        usage = html.escape(_token_usage("shadow", str(name), lang))
        cards.append(
            f"""
            <article class="elevation-card-demo">
              <div class="floating-surface" style="box-shadow:{safe_value};"></div>
              <div class="scale-meta"><strong>{safe_name}</strong><code>{safe_value}</code></div>
              <p>{usage}</p>
            </article>"""
        )
    if not cards:
        return "<p class=\"muted\">No elevation tokens documented.</p>"
    return f"""
    <div class="section-note">{'本区块用于判断“什么该浮起来，什么只需边框”。' if lang == 'zh' else 'Use this section to decide what truly needs elevation and what should stay flat.'}</div>
    <div class="elevation-gallery">{''.join(cards)}</div>
    """


def component_category(name: str) -> str:
    lowered = name.lower()
    if "button" in lowered or "cta" in lowered:
        return "Buttons"
    if any(term in lowered for term in ("input", "field", "form", "select", "textarea")):
        return "Inputs & Forms"
    if any(term in lowered for term in ("switch", "radio", "checkbox")):
        return "Selection Controls"
    if any(term in lowered for term in ("card", "surface", "panel", "tile")):
        return "Cards & Surfaces"
    if any(term in lowered for term in ("table", "row", "list")):
        return "Tables / Lists"
    if any(term in lowered for term in ("nav", "tab", "breadcrumb", "sidebar", "topbar", "header", "footer", "pagination", "tree")):
        return "Navigation"
    if any(term in lowered for term in ("badge", "tag", "alert", "toast", "status", "message")):
        return "Feedback"
    if any(term in lowered for term in ("modal", "drawer", "overlay", "dialog", "tooltip", "popover", "dropdown")):
        return "Overlays"
    if "editor" in lowered or "code" in lowered:
        return "Editors"
    return "Other"


def recipe_details(value: dict[str, Any], data: dict[str, Any]) -> str:
    rows = []
    for key, child in value.items():
        if isinstance(child, dict) and "value" not in child:
            continue
        if isinstance(child, list):
            child_value = ", ".join(str(item) for item in child)
        else:
            child_value = token_value(child)
        if child_value:
            resolved = resolve_refs(child_value, data)
            rows.append(f"<dt>{html.escape(str(key))}</dt><dd>{html.escape(resolved)}</dd>")
    return f"<dl>{''.join(rows)}</dl>" if rows else "<p class=\"muted\">No recipe properties.</p>"


def _resolve_prop(value: dict[str, Any], key: str, data: dict[str, Any]) -> str:
    """Resolve a single recipe property value through token references."""
    raw = token_value(value.get(key, ""))
    return resolve_refs(raw, data) if raw else ""


def _recipe_style(value: dict[str, Any], data: dict[str, Any]) -> str:
    """Build inline CSS from recipe token values so visual samples match the text."""
    css_map = {
        "backgroundColor": "background-color",
        "background": "background",
        "textColor": "color",
        "borderColor": "border-color",
        "border": "border",
        "borderStyle": "border-style",
        "borderRadius": "border-radius",
        "rounded": "border-radius",
        "fontSize": "font-size",
        "fontWeight": "font-weight",
        "lineHeight": "line-height",
        "height": "height",
        "minHeight": "min-height",
        "width": "width",
        "minWidth": "min-width",
        "padding": "padding",
        "shadow": "box-shadow",
        "boxShadow": "box-shadow",
        "maxWidth": "max-width",
    }
    alias_map = {
        "headerBg": "backgroundColor",
        "headerBackground": "backgroundColor",
        "hoverBg": "backgroundColor",
        "hoverBackground": "backgroundColor",
        "activeBg": "backgroundColor",
        "activeBackground": "backgroundColor",
        "headerTextColor": "textColor",
        "activeTextColor": "textColor",
    }
    parts = []
    for prop, css_prop in css_map.items():
        v = _resolve_prop(value, prop, data)
        if not v and prop in alias_map:
            v = _resolve_prop(value, alias_map[prop], data)
        if v:
            parts.append(f"{css_prop}:{v}")
    return ";".join(parts)


def _s(*fragments: str) -> str:
    """Merge CSS fragments, filtering empties. Use this to combine _recipe_style output with
    category-specific overrides so token values always reach the rendered element."""
    return ";".join(f for f in fragments if f)


def normalize_component_key(value: str) -> str:
    return re.sub(r"[^a-z0-9\u4e00-\u9fff]+", "", str(value or "").lower())


def component_example_mapping(data: dict[str, Any], *aliases: str) -> dict[str, Any]:
    """Return source-authored component examples, if DESIGN.md provides them."""
    components = mapping(data, "components")
    wanted = {normalize_component_key(alias) for alias in aliases if alias}
    for key, value in components.items():
        if not isinstance(value, dict):
            continue
        normalized = normalize_component_key(str(key))
        if normalized not in wanted and not any(alias in normalized or normalized in alias for alias in wanted):
            continue
        for example_key in ("examples", "sampleContent", "sampleData", "samples"):
            example_value = value.get(example_key)
            if isinstance(example_value, dict):
                return example_value
        return {}
    return {}


def component_example_text(examples: dict[str, Any], *keys: str) -> str:
    for key in keys:
        value = examples.get(key)
        if isinstance(value, str) and value.strip():
            return value.strip()
        if isinstance(value, (int, float)):
            return str(value)
    return ""


def first_page_sample_with(data: dict[str, Any], *keys: str) -> dict[str, Any]:
    for template in page_template_items(data):
        sample = sample_mapping(template)
        if any(sample.get(key) not in (None, "", [], {}) for key in keys):
            return sample
    return {}


def source_input_examples(data: dict[str, Any]) -> tuple[dict[str, Any], str]:
    examples = component_example_mapping(data, "input", "inputs", "form", "forms", "search", "textarea", "select")
    if examples:
        return examples, "source-example"
    sample = first_page_sample_with(data, "searchFields", "filters", "fields", "columns", "tableColumns")
    fields = first_sample_list(sample, "searchFields", "filters", "fields", "columns", "tableColumns")
    if fields:
        first = sample_field_label(fields[0], "")
        second = sample_field_label(fields[1], "") if len(fields) > 1 else ""
        return {"placeholder": first, "searchPlaceholder": second or first, "value": ""}, "page-sample-derived"
    return {}, "neutral-state"


def source_card_examples(data: dict[str, Any]) -> tuple[list[Any], str]:
    examples = component_example_mapping(data, "card", "cards", "metric", "metrics")
    for key in ("cards", "items", "examples"):
        value = examples.get(key)
        if isinstance(value, list) and value:
            return value, "source-example"
    if examples:
        return [examples], "source-example"
    sample = first_page_sample_with(data, "cards", "services", "resources", "metrics", "stats")
    cards = first_sample_list(sample, "cards", "services", "resources", "metrics", "stats")
    if cards:
        return cards, "page-sample-derived"
    return [], "neutral-state"


def source_table_examples(data: dict[str, Any], lang: str) -> tuple[list[str], list[Any], str]:
    z = lang == "zh"
    examples = component_example_mapping(data, "table", "tables", "list", "lists", "dataDisplay")
    columns = [str(item) for item in first_sample_list(examples, "columns", "tableColumns", "headers")]
    rows = first_sample_list(examples, "rows", "tableRows", "items")
    if columns or rows:
        return columns, rows, "source-example"
    sample = first_page_sample_with(data, "columns", "tableColumns", "headers", "rows", "tableRows", "items")
    columns = [str(item) for item in first_sample_list(sample, "columns", "tableColumns", "headers")]
    rows = first_sample_list(sample, "rows", "tableRows", "items")
    if columns or rows:
        return columns, rows, "page-sample-derived"
    return [("列" if z else "Column"), ("列" if z else "Column"), ("操作" if z else "Action")], [], "neutral-state"


def skeleton_bar(width: str = "70%") -> str:
    return f'<span aria-hidden="true" style="display:block;width:{width};height:10px;border-radius:999px;background:var(--bg-elevated);"></span>'


def neutral_state_note(lang: str) -> str:
    return (
        "未提供组件样例；以下仅展示已记录 token 与布局骨架，未记录的组件规格不会由预览器补成默认值。"
        if lang == "zh"
        else "No component examples are provided; this panel shows documented tokens and layout skeletons only. Missing component specs are not filled by renderer defaults."
    )


def component_recipe_mapping(data: dict[str, Any], *aliases: str) -> dict[str, Any]:
    """Return the documented component recipe for aliases such as button/input.

    This intentionally reads only DESIGN.md front matter. It does not create
    component defaults, because preview output must not look more certain than
    the underlying design specification.
    """
    components = mapping(data, "components")
    wanted = {normalize_component_key(alias) for alias in aliases if alias}
    for key, value in components.items():
        if not isinstance(value, dict):
            continue
        normalized = normalize_component_key(str(key))
        if normalized in wanted or any(alias in normalized or normalized in alias for alias in wanted):
            return value
    return {}


def component_recipe_value(data: dict[str, Any], aliases: tuple[str, ...], *keys: str) -> str:
    recipe = component_recipe_mapping(data, *aliases)
    if not recipe:
        return ""
    wanted = {normalize_component_key(key) for key in keys if key}

    def walk(value: Any, path: tuple[str, ...] = ()) -> str:
        if isinstance(value, dict):
            for key, child in value.items():
                normalized = normalize_component_key(str(key))
                if normalized in wanted:
                    candidate = token_value(child)
                    if candidate:
                        return resolve_all_refs(candidate, data)
                # examples 是内容样例，不是组件规格。
                if normalized in {"examples", "samplecontent", "sampledata", "samples"}:
                    continue
                found = walk(child, path + (str(key),))
                if found:
                    return found
        return ""

    return walk(recipe)


def token_spec_value(data: dict[str, Any], group: str, *names: str) -> str:
    value = token(data, group, *names, fallback="")
    return resolve_all_refs(value, data) if value else ""


def documented_spec_value(
    data: dict[str, Any],
    aliases: tuple[str, ...],
    component_keys: tuple[str, ...],
    token_group: str = "",
    token_keys: tuple[str, ...] = (),
) -> tuple[str, str]:
    component_value = component_recipe_value(data, aliases, *component_keys)
    if component_value:
        return component_value, "component"
    if token_group and token_keys:
        token_value_result = token_spec_value(data, token_group, *token_keys)
        if token_value_result:
            return token_value_result, "token"
    return "", "not-documented"


def spec_value_markup(value: str, source: str, lang: str) -> str:
    if value:
        return f'<span data-spec-source="{html.escape(source)}">{html.escape(value)}</span>'
    missing = "未记录" if lang == "zh" else "Not documented"
    return f'<span data-spec-source="not-documented" class="muted">{missing}</span>'


def component_visual(name: str, value: dict[str, Any], category: str, lang: str, data: dict[str, Any]) -> str:
    """Return an HTML visual sample for a component recipe.

    INVARIANT: every returned element that represents the component MUST include
    `style` (the output of _recipe_style) as an inline style attribute so the
    visual sample reflects the documented token values rather than CSS-class
    defaults.  Use _s() to merge `style` with any category-specific inline CSS.
    """
    lowered = name.lower()
    style = _recipe_style(value, data)

    if category == "Buttons":
        bg = token_value(value.get("backgroundColor", value.get("background", "")))
        text_color = token_value(value.get("textColor", ""))
        is_transparent = "transparent" in bg.lower() or not bg
        is_filled = bg and not is_transparent
        is_gradient = "gradient" in bg.lower() or "linear" in bg.lower()
        is_danger = "danger" in lowered or "error" in lowered or "delete" in lowered or (
            text_color and any(c in text_color.lower() for c in ("#ff4d4f", "#c62828", "#dc2626", "#ef4444", "rgb(255,"))
        )
        is_primary = not is_danger and (
            "primary" in lowered or "gradient" in lowered or (is_filled and not any(t in lowered for t in ("default", "text", "dashed", "plain", "ghost", "link")))
        )
        btn_class = "gradient-fill" if is_gradient else (
            "primary-fill" if (is_filled and is_primary) else
            "danger-fill" if (is_filled and is_danger) else
            "default-fill" if is_filled else "default"
        )
        hover = "悬停" if lang == "zh" else "Hover"
        disabled = "禁用" if lang == "zh" else "Disabled"
        return f"<div class=\"sample-line\"><button class=\"sample-button {btn_class}\" style=\"{style}\">{html.escape(name)}</button><button class=\"sample-button ghost\">{hover}</button><button class=\"sample-button disabled\">{disabled}</button></div>"

    if category == "Inputs & Forms":
        examples, source = source_input_examples(data)
        value_label = component_example_text(examples, "value", "inputValue", "defaultValue")
        placeholder = component_example_text(examples, "placeholder", "label", "name")
        if "textarea" in lowered:
            rows_attr = ' rows="2"'
            textarea_value = component_example_text(examples, "textarea", "textareaValue", "description", "body")
            return f"<div class=\"sample-form\" data-example-source=\"{source}\"><label>{html.escape(name)}</label><textarea{rows_attr} style=\"{_s('width:100%', style)}\" placeholder=\"{html.escape(placeholder)}\">{html.escape(textarea_value)}</textarea></div>"
        if "select" in lowered:
            options = first_sample_list(examples, "options", "items")
            selected = str(options[0]) if options else ("Selected" if lang != "zh" else "已选")
            return f"<div class=\"sample-form\" data-example-source=\"{source}\"><label>{html.escape(name)}</label><select style=\"{style}\"><option>{html.escape(selected)}</option></select></div>"
        return f"<div class=\"sample-form\" data-example-source=\"{source}\"><label>{html.escape(name)}</label><input value=\"{html.escape(value_label)}\" placeholder=\"{html.escape(placeholder)}\" style=\"{style}\" /></div>"

    if category == "Selection Controls":
        bg = _resolve_prop(value, "backgroundColor", data)
        border = _resolve_prop(value, "borderColor", data) or bg
        checked = "已选" if lang == "zh" else "✓"
        unchecked = "未选" if lang == "zh" else "○"
        if "switch" in lowered:
            switch_style = _s(f"display:inline-block;width:36px;height:20px;border-radius:10px;background:{bg};vertical-align:middle", style)
            return f"<div class=\"sample-line\"><span style=\"{switch_style}\"></span> <span style=\"font-size:12px;\">{html.escape(name)} {checked} / {unchecked}</span></div>"
        if "radio" in lowered:
            dot_style = _s(f"display:inline-block;width:14px;height:14px;border-radius:50%;border:2px solid {border};background:radial-gradient(circle,{bg} 40%,transparent 42%);vertical-align:middle", style)
            return f"<div class=\"sample-line\"><span style=\"{dot_style}\"></span> <span style=\"font-size:12px;\">{html.escape(name)} {checked} </span><span style=\"opacity:.4;font-size:12px;\">{unchecked}</span></div>"
        # checkbox
        box_style = _s(f"display:inline-block;width:14px;height:14px;border-radius:2px;border:2px solid {border};background:{bg};vertical-align:middle", style)
        return f"<div class=\"sample-line\"><span style=\"{box_style}\"></span> <span style=\"font-size:12px;\">{html.escape(name)} {checked} </span><span style=\"opacity:.4;font-size:12px;\">{unchecked}</span></div>"

    if category == "Tables / Lists":
        header_bg = (
            _resolve_prop(value, "headerBackground", data)
            or _resolve_prop(value, "headerBg", data)
            or _resolve_prop(value, "backgroundColor", data)
        )
        header_color = _resolve_prop(value, "headerTextColor", data) or _resolve_prop(value, "textColor", data)
        columns, rows, source = source_table_examples(data, lang)
        name_col = columns[0] if columns else ("列" if lang == "zh" else "Column")
        status_col = columns[1] if len(columns) > 1 else ("列" if lang == "zh" else "Column")
        action_col = columns[2] if len(columns) > 2 else ("操作" if lang == "zh" else "Action")
        head_style = _s(f"background:{header_bg}" if header_bg else "", f"color:{header_color}" if header_color else "", style)
        if rows:
            def row_cells(row: Any) -> list[str]:
                if isinstance(row, dict):
                    values = [str(row.get(column, "")) for column in columns[:3]]
                elif isinstance(row, list):
                    values = [str(item) for item in row[:3]]
                else:
                    values = [str(row)]
                while len(values) < 3:
                    values.append("")
                return values[:3]
            body = "".join(
                "<div>" + "".join(f"<span>{html.escape(cell)}</span>" for cell in row_cells(row)) + "</div>"
                for row in rows[:2]
            )
        else:
            body = (
                f"<div><span>{skeleton_bar('72%')}</span><span>{skeleton_bar('46%')}</span><span>{skeleton_bar('34%')}</span></div>"
                f"<div><span>{skeleton_bar('56%')}</span><span>{skeleton_bar('40%')}</span><span>{skeleton_bar('30%')}</span></div>"
            )
        return f"""<div class="mini-table" data-example-source="{source}"><div class="mini-head" style="{head_style}"><span>{html.escape(name_col)}</span><span>{html.escape(status_col)}</span><span>{html.escape(action_col)}</span></div>{body}</div>"""

    if category == "Navigation":
        # topbar / header 组件
        if "topbar" in lowered or "header" in lowered:
            product_name = str(data.get("name", "")) or ("产品名称" if lang == "zh" else "Product Name")
            nav1 = "数据源" if lang == "zh" else "Data"
            nav2 = "任务管理" if lang == "zh" else "Tasks"
            nav3 = "系统设置" if lang == "zh" else "Settings"
            help_text = "帮助" if lang == "zh" else "Help"
            user_text = "用户名" if lang == "zh" else "User"
            topbar_style = _s("display:flex;align-items:center;gap:20px;padding:0 16px;", style)
            return f"""<div style="{topbar_style}">
              <strong>{html.escape(product_name)}</strong>
              <span>{nav1}</span>
              <span>{nav2}</span>
              <span>{nav3}</span>
              <div style="margin-left:auto;display:flex;gap:12px;">
                <span>{help_text}</span>
                <span>{user_text}</span>
              </div>
            </div>"""

        # sidebar / sidebar-item 组件
        if "sidebar" in lowered:
            item1 = "数据源管理" if lang == "zh" else "Data Sources"
            item2 = "任务管理" if lang == "zh" else "Task Management"
            item3 = "系统设置" if lang == "zh" else "System Settings"
            is_active = "active" in lowered
            active_bg = _resolve_prop(value, "activeBg", data) or _resolve_prop(value, "activeBackground", data)
            active_color = _resolve_prop(value, "activeColor", data) or _resolve_prop(value, "activeTextColor", data)
            active_style = _s(
                f"background:{active_bg}" if active_bg else "",
                f"color:{active_color}" if active_color else "",
                "padding:7px 8px;border-radius:4px;"
            )
            sidebar_style = _s("padding:16px 12px;display:grid;gap:8px;", style)
            return f"""<div style="{sidebar_style}">
              <span style="{active_style if is_active else 'padding:7px 8px;'}">{item1}</span>
              <span style="padding:7px 8px;">{item2}</span>
              <span style="padding:7px 8px;">{item3}</span>
            </div>"""

        if "pagination" in lowered:
            total = (
                component_recipe_value(data, ("pagination", "pager"), "total", "totalCount", "summary")
                or ("未记录总数" if lang == "zh" else "Total not documented")
            )
            active_color = (
                _resolve_prop(value, "activeColor", data)
                or _resolve_prop(value, "activeTextColor", data)
                or _resolve_prop(value, "textColor", data)
            )
            active_bg = _resolve_prop(value, "activeBg", data) or active_color
            page_tag_style = _s(
                f"background:{active_bg};color:#fff;border-color:{active_color or active_bg}",
                style,
            )
            page_size = "10 条/页" if lang == "zh" else "10 / page"
            return f"<div class=\"sample-line\"><span style=\"{style}\">{total}</span><span class=\"tag\" style=\"{page_tag_style}\">1</span><span class=\"tag\" style=\"{style}\">2</span><span class=\"tag\" style=\"{style}\">3</span><span class=\"tag\" style=\"{style}\">{page_size}</span></div>"
        if "tree" in lowered:
            parent = "数据资产" if lang == "zh" else "Data Assets"
            child = "表管理" if lang == "zh" else "Table Management"
            hover_bg = (
                _resolve_prop(value, "hoverBackground", data)
                or _resolve_prop(value, "hoverBg", data)
                or _resolve_prop(value, "focusBackground", data)
                or _resolve_prop(value, "activeBg", data)
            )
            tree_style = _s(f"background:{hover_bg}" if hover_bg else "", style)
            return f"<div class=\"sample-surface\" style=\"{tree_style}\"><strong>{parent}</strong><span class=\"tag success\">{child}</span><span>{'字段详情' if lang == 'zh' else 'Field Details'}</span></div>"
        active = "当前" if lang == "zh" else "Active"
        more = "更多" if lang == "zh" else "More"
        active_color = (
            _resolve_prop(value, "activeColor", data)
            or _resolve_prop(value, "activeTextColor", data)
            or _resolve_prop(value, "textColor", data)
        )
        active_bg = _resolve_prop(value, "activeBg", data)
        active_border = _resolve_prop(value, "activeBorderColor", data) or active_color
        active_style = _s(
            f"color:{active_color}" if active_color else "",
            f"background:{active_bg}" if active_bg else "",
            f"border-color:{active_border}" if active_border else "",
            style,
        )
        return f"<div class=\"sample-nav\"><span class=\"active\" style=\"{active_style}\">{active}</span><span style=\"{style}\">{html.escape(name)}</span><span style=\"{style}\">{more}</span></div>"

    if category == "Feedback":
        if "message" in lowered:
            icon = "Success" if "success" in lowered else ("Warning" if "warning" in lowered else "Error")
            cls = "ok" if "success" in lowered else ("partial" if "warning" in lowered else "tag danger")
            msg_bg = _resolve_prop(value, "backgroundColor", data)
            msg_border = _resolve_prop(value, "borderColor", data)
            msg_color = _resolve_prop(value, "textColor", data)
            msg_style = _s(f"background:{msg_bg};border-left:4px solid {msg_border};color:{msg_color}" if msg_bg else "", style)
            msg_text = {"message-success": "保存成功，已同步组件配置", "message-warning": "存在未发布变更，请先检查", "message-error": "发布失败，请检查字段映射"}
            text = msg_text.get(name.lower(), msg_text.get("message-success", ""))
            return f"<div class=\"sample-drawer\" style=\"{msg_style}\"><strong class=\"{cls}\">{icon}</strong><span>{text}</span></div>"
        # 标签 / 徽标 / 标记：使用基于 token 的行内样式渲染
        tag_style = _s("display:inline-block", style)
        success = "成功" if lang == "zh" else "Success"
        error = "错误" if lang == "zh" else "Error"
        return f"<div class=\"sample-line\"><span style=\"{tag_style}\">{html.escape(name)}</span><span style=\"{tag_style}\">{success}</span><span style=\"{tag_style}\">{error}</span></div>"

    if category == "Overlays":
        bg = _resolve_prop(value, "backgroundColor", data) or _resolve_prop(value, "background", data)
        text_c = _resolve_prop(value, "textColor", data)
        ov_style = _s(f"background:{bg};color:{text_c}" if bg else "", style)
        if "tooltip" in lowered:
            tip = "深色提示信息" if lang == "zh" else "Tooltip content"
            return f"<div class=\"sample-drawer\" style=\"{ov_style}\"><strong>{html.escape(name)}</strong><span style=\"font-size:12px;\">{tip}</span></div>"
        if "popover" in lowered:
            title = "更多操作" if lang == "zh" else "More Actions"
            return f"<div class=\"sample-drawer\" style=\"{_s(ov_style, 'padding:12px')}\"><strong>{title}</strong><span>{'查看详情' if lang == 'zh' else 'View Details'}</span><span>{'复制链接' if lang == 'zh' else 'Copy Link'}</span></div>"
        if "dropdown" in lowered:
            dd_color = _resolve_prop(value, "textColor", data)
            return f"<div class=\"sample-drawer\" style=\"{ov_style}\"><strong style=\"color:{dd_color};\">{'下拉菜单' if lang == 'zh' else 'Dropdown Menu'}</strong><span style=\"color:{dd_color};\">{'新建视图' if lang == 'zh' else 'Create View'}</span><span>{'复制配置' if lang == 'zh' else 'Duplicate Config'}</span></div>"
        confirm = "确认" if lang == "zh" else "Confirm"
        return f"<div class=\"sample-drawer\" style=\"{ov_style}\"><strong>{html.escape(name)}</strong><div></div><div></div><button class=\"sample-button primary\">{confirm}</button></div>"

    if category == "Editors":
        code_title = "代码编辑器" if lang == "zh" else "Code Editor"
        code_line = "const columns = mapTokens(tokens);"
        return f"<div class=\"sample-surface\"><strong>{code_title}</strong><code style=\"{style}\">{html.escape(code_line)}</code><code>return buildPreview(layout);</code></div>"

    surface = "表面样例" if lang == "zh" else "Surface sample"
    block = "内容区块" if lang == "zh" else "Content block"
    return f"<div class=\"sample-surface\" style=\"{style}\"><span>{surface}</span><strong>{block}</strong></div>"


def component_recipes(data: dict[str, Any], lang: str = "en") -> str:
    components = mapping(data, "components")
    labels = LABELS[lang]
    groups: dict[str, list[tuple[str, dict[str, Any]]]] = {}
    for name, value in components.items():
        if isinstance(value, dict):
            groups.setdefault(component_category(name), []).append((name, value))

    blocks = []
    for group in (
        "Buttons",
        "Inputs & Forms",
        "Selection Controls",
        "Cards & Surfaces",
        "Navigation",
        "Tables / Lists",
        "Feedback",
        "Overlays",
        "Editors",
        "Other",
    ):
        recipes = groups.get(group, [])
        if not recipes:
            continue
        cards = []
        for name, value in recipes:
            category = component_category(name)
            cards.append(
                f"""
                <article class="component-card">
                  <strong>{html.escape(name)}</strong>
                  {component_visual(name, value, category, lang, data)}
                  <details>
                    <summary>{labels["implementation_tokens"]}</summary>
                    {recipe_details(value, data)}
                  </details>
                </article>"""
            )
        blocks.append(
            f"""
            <div class="token-group">
              <h3>{html.escape(group)}</h3>
              <div class="grid components">{"".join(cards)}</div>
            </div>"""
        )
    return "\n".join(blocks) or f"<p class=\"muted\">{labels['not_documented']}</p>"


def state_matrix(data: dict[str, Any], sections: dict[str, str], lang: str = "en") -> str:
    components = mapping(data, "components")
    labels = LABELS[lang]
    component_text = " ".join(
        [str(name).lower() for name in components.keys()]
        + [str(key).lower() for value in components.values() if isinstance(value, dict) for key in value.keys()]
        + [collect_text(value).lower() for value in components.values()]
    )
    prose_text = " ".join(
        sections.get(name, "").lower()
        for name in ("Interaction & States", "Interaction States & Responsive Rules",
                     "Component System", "Component System & Usage Rules",
                     "Visual Patterns", "Page Templates",
                     "Known Gaps", "Known Limits & Evidence Summary")
    )
    states = ("default", "hover", "focus", "active", "selected", "disabled", "error", "loading", "empty")
    rows = []
    for state in states:
        if state == "default" or state in component_text:
            state_class = "ok"
            status = labels["documented"]
        elif state in prose_text:
            state_class = "partial"
            status = labels["mentioned_only"]
        else:
            state_class = "missing"
            status = labels["not_documented"]
        rows.append(
            f"""
            <tr>
              <th>{html.escape(state)}</th>
              <td class="{state_class}">{status}</td>
            </tr>"""
        )
    return f"<table class=\"state-table\"><tbody>{''.join(rows)}</tbody></table>"


def infer_archetype(data: dict[str, Any]) -> str:
    explicit_type = str(data.get("productType", "")).strip().lower()
    explicit_archetype = str(data.get("interfaceArchetype", "")).strip().lower()
    explicit = " ".join(part for part in (explicit_type, explicit_archetype) if part)
    if explicit:
        if any(
            term in explicit
            for term in (
                "content portal",
                "resource portal",
                "digital resource",
                "resource library",
                "content library",
                "文化内容",
                "资源门户",
                "数字资源",
                "资源展示",
                "资源库",
                "专题展",
            )
        ):
            return "content-resource-portal"
        if any(
            term in explicit
            for term in (
                "brand-editorial",
                "brand editorial",
                "brand-site",
                "brand site",
                "portfolio",
                "creator",
                "personal brand",
                "个人品牌",
                "作品集",
                "创作者",
                "落地页",
            )
        ):
            return "brand-portfolio"
        if any(term in explicit for term in ("enterprise-admin", "enterprise admin", "admin")):
            return "enterprise-admin"
        if any(term in explicit for term in ("product-dashboard", "dashboard", "analytics")):
            return "product-dashboard"
        if any(
            term in explicit
            for term in (
                "media-content",
                "media content",
                "news",
                "content portal",
                "content community",
                "媒体内容",
                "资讯门户",
                "内容社区",
                "媒体资讯",
                "新闻",
                "视频",
                "播客",
                "内容流",
                "文章流",
            )
        ):
            return "media-content"
        if any(term in explicit for term in ("marketing-site", "marketing", "landing")):
            return "marketing"
        if any(term in explicit for term in ("mobile-app", "mobile")):
            return "mobile"
        if any(term in explicit for term in ("editor-workbench", "editor", "workbench")):
            return "editor-workbench"
        if any(term in explicit for term in ("developer-tool", "documentation", "docs")):
            return "documentation"
    haystack = " ".join(
        [
            str(data.get("description", "")),
            " ".join(mapping(data, "pagePatterns").keys()),
            " ".join(mapping(data, "patterns").keys()),
            " ".join(mapping(data, "componentMappings").keys()),
        ]
    ).lower()
    component_keys = " ".join(mapping(data, "components").keys()).lower()
    if any(term in haystack for term in ("marketplace", "listing", "property", "travel", "hotel", "vacation")):
        return "marketplace"
    if any(
        term in haystack
        for term in (
            "resource-library",
            "resource detail",
            "resource-card",
            "content portal",
            "digital resource",
            "资源库",
            "资源详情",
            "资源卡片",
            "专题展",
            "剧种",
            "戏曲",
        )
    ):
        return "content-resource-portal"
    if any(term in haystack for term in ("productivity", "consumer", "notes", "workspace", "document", "wiki")):
        return "consumer"
    if any(term in haystack for term in ("editor", "workbench", "canvas")):
        return "editor-workbench"
    if any(term in haystack for term in ("docs", "documentation", "api")):
        return "documentation"
    if any(term in haystack for term in ("enterprise", "admin", "crud", "table-management", "drawer")):
        return "enterprise-admin"
    if any(term in haystack for term in ("dashboard", "analytics", "metric", "chart")):
        return "product-dashboard"
    if any(
        term in haystack
        for term in (
            "media-content",
            "content portal",
            "content community",
            "媒体",
            "资讯",
            "内容流",
            "文章流",
            "文章列表",
            "post-list",
            "postlist",
        )
    ):
        return "media-content"
    if any(
        term in haystack
        for term in (
            "portfolio",
            "creator",
            "brand-editorial",
            "brand editorial",
            "personal brand",
            "作品集",
            "创作者",
            "个人品牌",
        )
    ):
        return "brand-portfolio"
    if any(term in haystack for term in ("marketing", "landing", "pricing", "hero")):
        return "marketing"
    # 从 front matter 组件 key 推断：property-card 和 search-bar 指向 marketplace
    if "property-card" in component_keys or "search-bar" in component_keys:
        return "marketplace"
    return "product-dashboard"


def page_template_items(data: dict[str, Any]) -> list[dict[str, Any]]:
    raw = data.get("pageTemplates")
    if isinstance(raw, list):
        return [item for item in raw if isinstance(item, dict)]
    if isinstance(raw, dict):
        return [item for item in raw.values() if isinstance(item, dict)]
    return []


def choose_page_template(data: dict[str, Any], *preferred: str) -> dict[str, Any]:
    items = page_template_items(data)
    preferred_lc = tuple(item.lower() for item in preferred)
    for item in items:
        haystack = " ".join(
            str(item.get(key, ""))
            for key in ("id", "key", "name", "title", "archetype", "purpose")
        ).lower()
        if any(term in haystack for term in preferred_lc):
            return item
    for item in items:
        if str(item.get("priority", "")).lower() == "primary":
            return item
    return items[0] if items else {}


def sample_list(value: Any) -> list[Any]:
    if isinstance(value, list):
        return value
    if value in (None, "", {}, []):
        return []
    return [value]


def sample_field_label(field: Any, fallback: str) -> str:
    if isinstance(field, dict):
        return str(field.get("label") or field.get("name") or fallback)
    text = str(field or "").strip()
    return text or fallback


def evidence_mode(data: dict[str, Any]) -> str:
    evidence = data.get("evidence") if isinstance(data.get("evidence"), dict) else {}
    runtime = data.get("runtime") if isinstance(data.get("runtime"), dict) else {}
    return str(
        evidence.get("mode")
        or runtime.get("evidenceMode")
        or runtime.get("mode")
        or ""
    ).strip().lower()


def is_extraction_backed(data: dict[str, Any]) -> bool:
    return evidence_mode(data) in {"url", "source-only", "source+screenshot"}


def sample_mapping(template: dict[str, Any]) -> dict[str, Any]:
    for key in ("sampleContent", "sampleData", "samples"):
        value = template.get(key)
        if isinstance(value, dict):
            return value
    return {}


def template_structure_items(template: dict[str, Any]) -> list[Any]:
    for key in ("sections", "structure", "blocks", "children"):
        value = template.get(key)
        if isinstance(value, list) and value:
            return value
        if isinstance(value, dict) and value:
            return list(value.values())
    return []


def sample_has_renderable_content(sample: dict[str, Any]) -> bool:
    if not sample:
        return False
    renderable_keys = {
        "columns",
        "tableColumns",
        "headers",
        "rows",
        "tableRows",
        "items",
        "treeNodes",
        "tree",
        "categories",
        "cards",
        "services",
        "resources",
        "tabs",
        "searchFields",
        "filters",
        "primaryAction",
        "action",
        "headline",
        "heroTitle",
        "title",
        "body",
        "description",
        "articles",
        "quickNav",
        "metrics",
        "stats",
        "nav",
        "navigation",
    }
    return any(sample.get(key) not in (None, "", [], {}) for key in renderable_keys)


def page_template_renderable(template: dict[str, Any]) -> bool:
    return bool(template_structure_items(template)) and sample_has_renderable_content(sample_mapping(template))


def renderable_page_templates(data: dict[str, Any]) -> list[dict[str, Any]]:
    return [template for template in page_template_items(data) if page_template_renderable(template)]


def choose_renderable_page_template(data: dict[str, Any], *preferred: str) -> dict[str, Any]:
    items = renderable_page_templates(data)
    preferred_lc = tuple(item.lower() for item in preferred)
    for item in items:
        haystack = " ".join(
            str(item.get(key, ""))
            for key in ("id", "key", "name", "title", "archetype", "purpose")
        ).lower()
        if any(term in haystack for term in preferred_lc):
            return item
    for item in items:
        if str(item.get("priority", "")).lower() == "primary":
            return item
    return items[0] if items else {}


def enterprise_template_renderable(template: dict[str, Any]) -> bool:
    return page_template_renderable(template)


def enterprise_renderable_templates(data: dict[str, Any]) -> list[dict[str, Any]]:
    return renderable_page_templates(data)


def choose_enterprise_renderable_template(data: dict[str, Any], *preferred: str) -> dict[str, Any]:
    return choose_renderable_page_template(data, *preferred)


def sample_strings(value: Any) -> list[str]:
    if isinstance(value, dict):
        return [item for child in value.values() for item in sample_strings(child)]
    if isinstance(value, list):
        items: list[str] = []
        for child in value:
            items.extend(sample_strings(child))
        return items
    text = str(value or "").strip()
    return [text] if text else []


def first_sample_list(sample: dict[str, Any], *keys: str) -> list[Any]:
    for key in keys:
        value = sample.get(key)
        if isinstance(value, list) and value:
            return value
    return []


def first_sample_string(sample: dict[str, Any], *keys: str) -> str:
    for key in keys:
        value = sample.get(key)
        if isinstance(value, str) and value.strip():
            return value.strip()
        if isinstance(value, (int, float)):
            return str(value)
    return ""


def page_template_title(data: dict[str, Any], template: dict[str, Any], sample: dict[str, Any], lang: str) -> str:
    z = lang == "zh"
    return (
        first_sample_string(sample, "title", "pageTitle", "headline", "heroTitle")
        or str(template.get("name") or template.get("title") or template.get("id") or template.get("key") or "").strip()
        or str(data.get("name") or ("页面模板" if z else "Page Template")).strip()
    )


def render_template_diagnostic(
    data: dict[str, Any],
    lang: str,
    heading: str,
    copy: str,
    fallback: list[tuple[str, str]],
) -> str:
    z = lang == "zh"
    reason = (
        "DESIGN.md 缺少可渲染的 pageTemplates：需要 sections/structure 以及 sampleContent/sampleData。已禁用通用页面样例。"
        if z
        else "DESIGN.md does not provide renderable pageTemplates: sections/structure plus sampleContent/sampleData are required. Generic page fallback is disabled."
    )
    return f"""
    <section>
      <div class="section-head"><div><h3 style="margin:0;">{html.escape(heading)}</h3><p>{html.escape(copy)}</p></div></div>
      {template_summary_cards(data, lang, fallback)}

      <div id="template-examples" class="toc-anchor"></div>
      <div class="section-note diagnostic-panel" data-template-source="insufficient-design-md">
        {html.escape(reason)}
      </div>
    </section>
    """


def render_source_template_specimen(
    data: dict[str, Any],
    template: dict[str, Any],
    lang: str,
    archetype: str,
) -> str:
    z = lang == "zh"
    sample = sample_mapping(template)
    primary = resolve_color_nested(data, "primary", "brand", "brand-primary", fallback="var(--brand)")
    surface = resolve_color_nested(data, "surface", "surface-card", "surface-1", fallback="#ffffff")
    canvas = resolve_color_nested(data, "canvas", "surface-canvas", fallback="#f0f2f5")
    border = resolve_color_nested(data, "border", "border-default", "hairline", fallback="#d9d9d9")
    muted = resolve_color_nested(data, "textMuted", "text-muted", "ink-muted", fallback="rgba(0,0,0,0.45)")
    text = resolve_color_nested(data, "text", "text-primary", "ink", fallback="rgba(0,0,0,0.65)")
    page_title = page_template_title(data, template, sample, lang)
    page_copy = first_sample_string(sample, "description", "body", "summary", "subtitle")
    primary_action = first_sample_string(sample, "primaryAction", "action", "cta")
    sections = [
        sample_field_label(section, f"Section {index + 1}" if not z else f"区块 {index + 1}")
        for index, section in enumerate(template_structure_items(template)[:6])
    ]
    tabs = [str(item) for item in first_sample_list(sample, "tabs", "nav", "navigation")]
    cards = first_sample_list(sample, "cards", "services", "resources", "quickCards")
    articles = first_sample_list(sample, "articles", "posts", "items")
    rows = first_sample_list(sample, "rows", "tableRows")
    columns = [str(item) for item in first_sample_list(sample, "columns", "tableColumns", "headers")]
    metrics = first_sample_list(sample, "metrics", "stats", "kpis")
    fields = first_sample_list(sample, "fields", "searchFields", "filters")

    if not columns and rows and isinstance(rows[0], dict):
        columns = [str(key) for key in rows[0].keys()]

    section_chips = "".join(f"<span>{html.escape(str(item))}</span>" for item in sections)
    tab_html = "".join(f'<span class="{("active" if index == 0 else "")}">{html.escape(str(tab))}</span>' for index, tab in enumerate(tabs[:6]))
    action_html = f'<button class="primary">{html.escape(primary_action)}</button>' if primary_action else ""

    def render_card_item(item: Any) -> str:
        if isinstance(item, dict):
            title = str(item.get("title") or item.get("name") or item.get("label") or "")
            desc = str(item.get("description") or item.get("desc") or item.get("summary") or "")
            action = str(item.get("action") or item.get("cta") or "")
        else:
            title, desc, action = str(item), "", ""
        action_html = f'<a href="#">{html.escape(action)}</a>' if action else ""
        return f"<article><strong>{html.escape(title)}</strong><p>{html.escape(desc)}</p>{action_html}</article>"

    def render_table_row(row: Any) -> str:
        if isinstance(row, dict):
            values = [str(row.get(column, "")) for column in columns]
        elif isinstance(row, list):
            values = [str(item) for item in row]
        else:
            values = [str(row)]
        if not columns:
            return ""
        while len(values) < len(columns):
            values.append("")
        return "<tr>" + "".join(f"<td>{html.escape(value)}</td>" for value in values[: len(columns)]) + "</tr>"

    if cards:
        body_html = '<div class="source-card-grid">' + "".join(render_card_item(item) for item in cards[:6]) + "</div>"
    elif articles:
        body_html = '<div class="source-card-grid">' + "".join(render_card_item(item) for item in articles[:6]) + "</div>"
    elif metrics:
        body_html = '<div class="source-card-grid">' + "".join(render_card_item(item) for item in metrics[:6]) + "</div>"
    elif rows and columns:
        header_html = "".join(f"<th>{html.escape(column)}</th>" for column in columns[:6])
        row_html = "".join(render_table_row(row) for row in rows[:6])
        body_html = f"""
        <div class="spec-panel new_table">
          <table class="spec-table">
            <thead><tr>{header_html}</tr></thead>
            <tbody>{row_html}</tbody>
          </table>
        </div>"""
    elif fields:
        body_html = '<div class="source-card-grid">' + "".join(render_card_item(item) for item in fields[:6]) + "</div>"
    else:
        values = [
            (str(key), compact_value(value, data) or str(value))
            for key, value in sample.items()
            if value not in (None, "", [], {}) and key not in {"title", "pageTitle", "headline", "heroTitle"}
        ][:6]
        body_html = '<div class="source-card-grid">' + "".join(
            f"<article><strong>{html.escape(key)}</strong><p>{html.escape(value)}</p></article>"
            for key, value in values
        ) + "</div>"

    return f"""
      <div class="specimen source-matched {html.escape(archetype)}" style="--spec-primary:{html.escape(primary)};--spec-surface:{html.escape(surface)};--spec-canvas:{html.escape(canvas)};--spec-border:{html.escape(border)};--spec-text:{html.escape(text)};--spec-muted:{html.escape(muted)};">
        <main class="source-main" style="background:var(--spec-canvas);">
          <div class="source-toolbar">
            <strong>{html.escape(page_title)}</strong>
            {action_html}
          </div>
          {f'<p style="margin:0 0 12px;color:var(--spec-muted);">{html.escape(page_copy)}</p>' if page_copy else ''}
          {f'<div class="source-tabs">{tab_html}</div>' if tab_html else ''}
          {f'<div class="chip-row" style="margin-bottom:12px;">{section_chips}</div>' if section_chips else ''}
          {body_html}
        </main>
      </div>"""


def render_source_template_page_section(
    data: dict[str, Any],
    lang: str,
    archetype: str,
    heading: str,
    copy: str,
    fallback: list[tuple[str, str]],
    *preferred: str,
) -> str:
    template = choose_renderable_page_template(data, *preferred)
    if not template:
        return render_template_diagnostic(data, lang, heading, copy, fallback)

    z = lang == "zh"
    sample = sample_mapping(template)
    title = page_template_title(data, template, sample, lang)
    source_copy = (
        "以下样例严格由 DESIGN.md.pageTemplates 与 sampleContent 生成；缺少样例内容时不会套用内置通用页面。"
        if z
        else "The specimen below is generated strictly from DESIGN.md pageTemplates and sampleContent; missing sample content does not trigger built-in generic pages."
    )
    return f"""
    <section>
      <div class="section-head"><div><h3 style="margin:0;">{html.escape(heading)}</h3><p>{html.escape(source_copy or copy)}</p></div></div>
      {template_summary_cards(data, lang, fallback)}

      <div id="template-examples" class="toc-anchor"></div>
      <h4 style="margin-top:16px;">{html.escape(title)}</h4>
      {render_source_template_specimen(data, template, lang, archetype)}
    </section>
    """


def extraction_sidebar_items(data: dict[str, Any], templates: list[dict[str, Any]], lang: str) -> list[str]:
    z = lang == "zh"
    sidebar_text = collect_text(mapping(data, "components").get("sidebarMenu", ""))
    match = re.search(r"(?:菜单按|menu\s+uses?)\s*([^。.;]+?)(?:分组|group|$)", sidebar_text, re.I)
    if match:
        raw_terms = re.split(r"[、,，/]+", match.group(1))
        terms = [term.strip() for term in raw_terms if 1 <= len(term.strip()) <= 12]
        if terms:
            return terms[:10]
    names = [
        str(item.get("name") or item.get("title") or item.get("id") or "").strip()
        for item in templates
        if isinstance(item, dict)
    ]
    return [name for name in names if name][:8] or (["首页"] if z else ["Home"])


def source_backed_enterprise_specimen(data: dict[str, Any], lang: str = "en") -> str:
    """Render an enterprise specimen only from pageTemplates and sampleContent."""
    z = lang == "zh"
    templates = page_template_items(data)
    template = choose_enterprise_renderable_template(data, "tree-table", "tree", "table", "list", "management", "管理")
    sample = sample_mapping(template)
    template_text = collect_text(template).lower()

    shell = shell_metrics(data)
    primary = resolve_color_nested(data, "primary", "brand", "brand-primary", fallback="var(--brand)")
    topbar_bg = resolve_all_refs(
        _example_lookup(data, "layout.appShell.topbar.background", "tokens.colors.shellTopbar", "colors.shellTopbar")
        or resolve_color_nested(data, "shellTopbar", "shell-topbar", "topbar-bg", fallback="#ffffff"),
        data,
    )
    sidebar_bg = resolve_all_refs(
        _example_lookup(data, "layout.appShell.sidebar.background", "tokens.colors.shellSidebar", "colors.shellSidebar")
        or resolve_color_nested(data, "shellSidebar", "sidebar", "surface", fallback="#ffffff"),
        data,
    )
    sidebar_active_bg = resolve_all_refs(
        _example_lookup(data, "layout.appShell.sidebar.activeBackground", "tokens.colors.activeSurface", "colors.activeSurface")
        or resolve_color_nested(data, "activeSurface", "shellSidebarActiveBg", "sidebar-active-bg", fallback="#e6f4ff"),
        data,
    )
    surface = resolve_color_nested(data, "surface", "surface-card", "surface-1", fallback="#ffffff")
    canvas = resolve_color_nested(data, "canvas", "surface-canvas", fallback="#f0f2f5")
    border = resolve_color_nested(data, "border", "border-default", "hairline", fallback="#d9d9d9")
    table_header_bg = resolve_color_nested(data, "surfaceMuted", "table-header-bg", "surface-table-header", fallback="#f5f5f5")
    table_header_color = resolve_color_nested(data, "textStrong", "table-header-color", fallback="rgba(0,0,0,0.85)")
    text = resolve_color_nested(data, "text", "text-primary", "ink", fallback="rgba(0,0,0,0.65)")
    muted = resolve_color_nested(data, "textMuted", "text-muted", "ink-muted", fallback="rgba(0,0,0,0.45)")
    product_name = humanize_identifier(str(data.get("name", ""))) or ("产品" if z else "Product")
    page_title = str(sample.get("title") or sample.get("pageTitle") or template.get("name") or template.get("id") or product_name)
    menu_items = extraction_sidebar_items(data, templates, lang)
    active_menu = page_title if page_title in menu_items else (menu_items[-1] if menu_items else page_title)

    columns = [str(item) for item in first_sample_list(sample, "columns", "tableColumns", "headers")]
    rows = first_sample_list(sample, "rows", "tableRows", "items")
    tree_nodes = [str(item) for item in first_sample_list(sample, "treeNodes", "tree", "categories")]
    cards = first_sample_list(sample, "cards", "services", "resources")
    tabs = [str(item) for item in first_sample_list(sample, "tabs")]

    if not columns and rows and isinstance(rows[0], dict):
        columns = [str(key) for key in rows[0].keys()]
    if not columns:
        columns = [("名称" if z else "Name"), ("类型" if z else "Type"), ("操作" if z else "Actions")]
    if not rows:
        candidate_values = [value for value in sample_strings(sample) if value not in {page_title}][: max(3, len(columns))]
        rows = [candidate_values[: len(columns)]] if candidate_values else []

    def render_row(row: Any) -> str:
        if isinstance(row, dict):
            values = [str(row.get(column, "")) for column in columns]
        elif isinstance(row, list):
            values = [str(item) for item in row]
        else:
            values = [str(row)]
        while len(values) < len(columns):
            values.append("")
        cells = []
        for index, value in enumerate(values[: len(columns)]):
            col = columns[index]
            cls = "link" if index == 0 or "名称" in col or "name" in col.lower() else ""
            text_html = f'<a href="#">{html.escape(value)}</a>' if cls and value else html.escape(value)
            cells.append(f"<td>{text_html}</td>")
        return "<tr>" + "".join(cells) + "</tr>"

    def render_cards() -> str:
        if not cards:
            return ""
        card_html = []
        for card in cards[:6]:
            if isinstance(card, dict):
                title = str(card.get("title") or card.get("name") or "")
                desc = str(card.get("description") or card.get("desc") or "")
                action = str(card.get("action") or "")
            else:
                title, desc, action = str(card), "", ""
            card_html.append(
                f'<article class="source-card"><strong>{html.escape(title)}</strong><p>{html.escape(desc)}</p><a href="#">{html.escape(action)}</a></article>'
            )
        return '<div class="source-card-grid">' + "".join(card_html) + "</div>"

    has_cards = bool(cards) and ("card" in template_text or "卡片" in template_text or "service" in template_text)
    has_tree_table = bool(tree_nodes) or "tree" in template_text or "左树" in template_text
    has_tabs = bool(tabs) or "tabs" in template_text or "标签" in template_text
    header_html = "".join(f"<th>{html.escape(column)}</th>" for column in columns)
    row_html = "".join(render_row(row) for row in rows[:6])
    if not row_html:
        row_html = f'<tr><td colspan="{len(columns)}">{html.escape("样例数据由 pageTemplates.sampleContent 提供" if z else "Sample rows come from pageTemplates.sampleContent")}</td></tr>'
    tree_html = "".join(f'<span class="{"active" if index == 0 else ""}">{html.escape(node)}</span>' for index, node in enumerate(tree_nodes[:12]))
    tabs_html = "".join(f'<span class="{"active" if index == 0 else ""}">{html.escape(tab)}</span>' for index, tab in enumerate(tabs[:5]))
    toolbar_action = str(sample.get("primaryAction") or sample.get("action") or ("新建" if z else "Create"))
    toolbar_filter = str(sample.get("filterPlaceholder") or ("请输入名称" if z else "Enter name"))

    if has_cards:
        main_html = f"""
              <div class="source-toolbar"><strong>{html.escape(page_title)}</strong><button class="primary">{html.escape(toolbar_action)}</button><input value="" placeholder="{html.escape(toolbar_filter)}" /></div>
              {render_cards()}
        """
    else:
        main_html = f"""
              {'<div class="source-tabs">' + tabs_html + '</div>' if has_tabs else ''}
              <div class="source-toolbar"><strong>{html.escape(page_title)}</strong><button class="primary">{html.escape(toolbar_action)}</button><input value="" placeholder="{html.escape(toolbar_filter)}" /></div>
              <div class="spec-panel new_table">
                <table class="spec-table">
                  <thead><tr>{header_html}</tr></thead>
                  <tbody>{row_html}</tbody>
                </table>
                <div class="spec-pagination">{html.escape('共 ' + str(max(len(rows), 1)) + ' 条' if z else 'Total ' + str(max(len(rows), 1)))} <b>1</b></div>
              </div>
        """

    body_html = f"""
            <main class="spec-main source-main">
              {main_html}
            </main>
    """
    if has_tree_table:
        body_html = f"""
            <main class="spec-main source-main source-split">
              <aside class="source-tree">
                <div class="source-search">{html.escape('输入目录名称' if z else 'Search folder')}</div>
                {tree_html}
              </aside>
              <section class="source-content">{main_html}</section>
            </main>
        """

    return f"""
      <div class="specimen enterprise-admin source-matched" style="--spec-primary:{html.escape(primary)};--spec-topbar-bg:{html.escape(topbar_bg)};--spec-surface:{html.escape(surface)};--spec-canvas:{html.escape(canvas)};--spec-border:{html.escape(border)};--spec-sidebar:{html.escape(sidebar_bg)};--spec-sidebar-text:{html.escape(text)};--spec-sidebar-active-bg:{html.escape(sidebar_active_bg)};--spec-tags-bg:{html.escape(surface)};--spec-table-header-bg:{html.escape(table_header_bg)};--spec-table-header-color:{html.escape(table_header_color)};--spec-text:{html.escape(text)};--spec-muted:{html.escape(muted)};--spec-topbar:{html.escape(shell['topbar'])};--spec-sidebar-width:{html.escape(shell['sidebar'])};--spec-tags:0px">
        <div class="source-shell">
          <aside class="spec-sidebar-menu source-sidebar">
            <strong class="source-logo">{html.escape(product_name)}</strong>
            {''.join(f'<span class="{"active" if item == active_menu else ""}">{html.escape(item)}</span>' for item in menu_items)}
          </aside>
          <div class="spec-workspace">
            <div class="spec-topbar source-topbar"><span></span><span>{html.escape(product_name)}</span></div>
            {body_html}
          </div>
        </div>
      </div>"""


def enterprise_admin_specimen(data: dict[str, Any], lang: str = "en") -> str:
    """Render the source-matched enterprise shell + primary list template."""
    z = lang == "zh"
    if enterprise_renderable_templates(data):
        return source_backed_enterprise_specimen(data, lang)
    reason = (
        "DESIGN.md 缺少可渲染的企业后台 pageTemplates：需要 sections/structure 以及 sampleContent/sampleData。已禁用通用后台样例。"
        if z
        else "DESIGN.md does not provide renderable enterprise pageTemplates: sections/structure plus sampleContent/sampleData are required. Generic admin fallback is disabled."
    )
    return f"""
      <div class="section-note diagnostic-panel" data-template-source="insufficient-design-md">
        {html.escape(reason)}
      </div>"""


def representative_specimen(data: dict[str, Any], _sections: dict[str, str], lang: str = "en") -> str:
    archetype = infer_archetype(data)
    if archetype in {"brand-portfolio", "marketing"}:
        template = choose_renderable_page_template(data, "hero", "portfolio", "marketing", "brand", "landing", "作品", "品牌")
        if template:
            return render_source_template_specimen(data, template, lang, archetype)
        reason = (
            "DESIGN.md 缺少可渲染的品牌 / 营销 pageTemplates；已禁用内置通用品牌样例。"
            if lang == "zh"
            else "DESIGN.md does not provide renderable brand/marketing pageTemplates; built-in generic brand specimen is disabled."
        )
        return f"""
      <div class="section-note diagnostic-panel" data-template-source="insufficient-design-md">
        {html.escape(reason)}
      </div>"""
    if archetype == "enterprise-admin":
        return enterprise_admin_specimen(data, lang)
    terms = extract_product_terms(data, lang)
    pattern_names = terms["patterns"]
    component_names = terms["components"]
    pattern_key, pattern_value = strongest_page_pattern(data)
    shell = shell_metrics(data)
    primary = resolve_color_nested(data, "primary", "brand", "brand-primary", fallback="#2563eb")
    topbar_bg = _example_lookup(
        data,
        "layoutRules.appShell.topbar.background",
        "layoutRules.appShell.topBar.background",
        "layoutRules.appShell.topNav.background",
        "tokens.colors.shellTopbar",
        "colors.shellTopbar",
    ) or resolve_color_nested(
        data,
        "shellTopbar",
        "shell-topbar",
        "top-nav-bg",
        "topbar-bg",
        "top-header-bg",
        "nav-bg",
        fallback=primary,
    )
    surface = resolve_color_nested(data, "surface-card", "surface", "surface-1", fallback="#ffffff")
    canvas = resolve_color_nested(data, "canvas", "surface-canvas", fallback="#f3f5f8")
    border = resolve_color_nested(data, "border", "border-default", "hairline", fallback="#d9dee8")
    sidebar = resolve_color_nested(data, "shellSidebar", "sidebar", "surface-sidebar", "surface", fallback="#ffffff")
    # 表格表头：分别获取背景色和文字颜色
    table_header_bg = resolve_color_nested(data, "table-header-bg", "surface-table-header", "surface-soft", fallback="#f5f5f5")
    table_header_color = resolve_color_nested(data, "table-header-font", "table-header-color", "body", fallback="rgba(0,0,0,0.83)")
    text = resolve_color_nested(data, "text-heading", "text-primary", "ink", fallback="#172033")
    muted = resolve_color_nested(data, "text-muted", "ink-muted", fallback="#667085")
    product_name = humanize_identifier(str(data.get("name", ""))) or ("设计系统" if lang == "zh" else "Design System")
    primary_pattern = page_pattern_title(pattern_key, pattern_value, lang) if pattern_key else (
        pattern_names[0] if pattern_names else ("资产总览" if lang == "zh" else "System Overview")
    )
    secondary_pattern = pattern_names[1] if len(pattern_names) > 1 else ("工作台" if lang == "zh" else "Workspace")
    tertiary_pattern = pattern_names[2] if len(pattern_names) > 2 else ("质量检查" if lang == "zh" else "Quality Review")
    main_title = primary_pattern
    record_term = component_names[0] if component_names else ("数据资产" if lang == "zh" else "Design Asset")
    auxiliary_term = component_names[1] if len(component_names) > 1 else ("组件映射" if lang == "zh" else "Component Mapping")
    action_primary = terms["actions"][0] if terms["actions"] else ("查询" if lang == "zh" else "Search")
    action_secondary = terms["actions"][1] if len(terms["actions"]) > 1 else ("新建" if lang == "zh" else "Create")
    status_value = terms["statuses"][0] if terms["statuses"] else ("在线" if lang == "zh" else "Online")
    if lang == "zh":
        topbar = (product_name, primary_pattern, secondary_pattern, tertiary_pattern)
        rail = ("首页", primary_pattern, secondary_pattern, tertiary_pattern)
        tree = ("目录", record_term, auxiliary_term, "运行态", "已知缺口")
        labels = {
            "keyword": "关键词",
            "status": "状态",
            "all": "全部",
            "reset": "重置",
            "search": "查询",
            "title": main_title,
            "import": terms["actions"][2] if len(terms["actions"]) > 2 else "导入",
            "create": action_secondary,
            "name": "名称",
            "domain": "模块",
            "owner": "负责人",
            "actions": "操作",
            "sales": record_term,
            "governance": auxiliary_term,
            "reference": secondary_pattern,
            "online": status_value,
            "detail": "详情",
            "edit": "编辑",
            "lineage": "查看",
            "total": "未记录总数",
        }
    else:
        topbar = (product_name, primary_pattern, secondary_pattern, tertiary_pattern)
        rail = ("Home", primary_pattern, secondary_pattern, tertiary_pattern)
        tree = ("Catalog", record_term, auxiliary_term, "Runtime", "Known Gaps")
        labels = {
            "keyword": "Keyword",
            "status": "Status",
            "all": "All",
            "reset": "Reset",
            "search": action_primary,
            "title": main_title,
            "import": terms["actions"][2] if len(terms["actions"]) > 2 else "Import",
            "create": action_secondary,
            "name": "Name",
            "domain": "Module",
            "owner": "Owner",
            "actions": "Actions",
            "sales": record_term,
            "governance": auxiliary_term,
            "reference": secondary_pattern,
            "online": status_value,
            "detail": "Detail",
            "edit": "Edit",
            "lineage": "Inspect",
            "total": "Total not documented",
        }
    query_value = humanize_identifier(primary_pattern).replace(" ", "_").lower() or "design_asset"
    return f"""
      <div class="specimen {html.escape(archetype)}" style="--spec-primary:{html.escape(primary)};--spec-topbar-bg:{html.escape(topbar_bg)};--spec-surface:{html.escape(surface)};--spec-canvas:{html.escape(canvas)};--spec-border:{html.escape(border)};--spec-sidebar:{html.escape(sidebar)};--spec-table-header-bg:{html.escape(table_header_bg)};--spec-table-header-color:{html.escape(table_header_color)};--spec-text:{html.escape(text)};--spec-muted:{html.escape(muted)};--spec-topbar:{html.escape(shell['topbar'])};--spec-sidebar-width:{html.escape(shell['sidebar'])};--spec-tags:{html.escape(shell['tags'])}">
        <div class="spec-topbar"><strong>{topbar[0]}</strong><span>{topbar[1]}</span><span>{topbar[2]}</span><span>{topbar[3]}</span></div>
        {'<div class="spec-tags"><span class="active">' + html.escape(primary_pattern) + '</span><span>' + html.escape(secondary_pattern) + '</span><span>' + html.escape(tertiary_pattern) + '</span></div>' if shell['has_tags'] else ''}
        <div class="spec-body">
          <aside class="spec-rail"><span>{rail[0]}</span><span class="active">{rail[1]}</span><span>{rail[2]}</span><span>{rail[3]}</span></aside>
          <aside class="spec-tree"><strong>{tree[0]}</strong><span class="active">{tree[1]}</span><span>{tree[2]}</span><span>{tree[3]}</span><span>{tree[4]}</span></aside>
          <main class="spec-main">
            <div class="spec-filter"><label>{labels['keyword']}</label><input value="{html.escape(query_value)}" /><label>{labels['status']}</label><select><option>{labels['all']}</option></select><button>{labels['reset']}</button><button class="primary">{labels['search']}</button></div>
            <div class="spec-panel">
              <div class="spec-title"><strong>{labels['title']}</strong><span></span><button>{labels['import']}</button><button class="primary">{labels['create']}</button></div>
              <table class="spec-table">
                <thead><tr><th>{labels['name']}</th><th>{labels['domain']}</th><th>{labels['status']}</th><th>{labels['owner']}</th><th>{labels['actions']}</th></tr></thead>
                <tbody>
                  <tr><td>{html.escape(record_term.upper().replace(" ", "_"))}</td><td>{labels['sales']}</td><td><i></i>{labels['online']}</td><td>{'系统设计组' if lang == 'zh' else 'Design Ops'}</td><td>{labels['detail']}</td></tr>
                  <tr><td>{html.escape(auxiliary_term.upper().replace(" ", "_"))}</td><td>{labels['governance']}</td><td><i></i>{labels['online']}</td><td>{'前端平台组' if lang == 'zh' else 'UI Platform'}</td><td>{labels['edit']}</td></tr>
                  <tr><td>{html.escape(secondary_pattern.upper().replace(" ", "_"))}</td><td>{labels['reference']}</td><td><i></i>{labels['online']}</td><td>{'产品体验组' if lang == 'zh' else 'Product Design'}</td><td>{labels['lineage']}</td></tr>
                </tbody>
              </table>
              <div class="spec-pagination">{labels['total']} <b>1</b> 2 3 {'10 条/页' if lang == 'zh' else '10 / page'}</div>
            </div>
          </main>
        </div>
      </div>"""


# ---------------------------------------------------------------------------
# kit-mirror alias bridge — maps brand tokens to standardized names so the
# 9-pattern examples can render with the product's own design language.
# ---------------------------------------------------------------------------

def kit_mirror_alias_css(data: dict[str, Any], dark: bool) -> str:
    """Generate the CSS alias bridge that maps brand tokens → kit-mirror names."""
    colors = mapping(data, "colors")
    if dark and is_single_dark_theme(data):
        primary = resolve_color_nested(data, "primary", "ink-on-dark", "brand", "accent", fallback="#D7E2EA")
        on_primary = resolve_color_nested(data, "cta-text", "on-primary", fallback="#0C0C0C")
        ink = resolve_color_nested(data, "ink-on-dark", "ink", "primary", fallback="#D7E2EA")
        muted = resolve_color_nested(data, "ink-muted-dark", "ink-muted", fallback=ink)
        canvas = resolve_color_nested(data, "canvas-dark", "canvas", fallback="#0C0C0C")
        canvas_soft = resolve_color_nested(data, "surface-dark", "surface-1", "surface", fallback=canvas)
        border = resolve_color_nested(data, "hairline-on-dark", "hairline", fallback="rgba(215,226,234,0.35)")
        accent = resolve_color_nested(data, "cta-gradient-mid-1", "accent", fallback="#B600A8")
    elif dark:
        # 暗色模式只使用暗色专用 token 名称。不要通过子串匹配回退到亮色品牌色，
        # 否则会产生 #003EB3 在 #090b10 背景上不可见这类问题。
        primary = resolve_color_nested(data, "primary-dark", fallback="#8ab4ff")
        on_primary = resolve_color_nested(data, "text-on-dark", "on-primary-dark", fallback="#07111f")
        ink = resolve_color_nested(data, "ink-dark", "text-primary-dark", "text-on-dark", fallback="#f3f5f8")
        muted = resolve_color_nested(data, "ink-muted-dark", "text-muted-dark", "text-secondary-dark", fallback="#9aa4b2")
        canvas = resolve_color_nested(data, "canvas-dark", "surface-canvas-dark", fallback="#090b10")
        canvas_soft = resolve_color_nested(data, "surface-card-dark", "surface-dark", "surface-1-dark", fallback="#11151d")
        border = resolve_color_nested(data, "border-dark", "hairline-dark", fallback="rgba(255,255,255,0.12)")
        accent = resolve_color_nested(data, "accent-dark", "semantic-error-dark", fallback="#f96bee")
    else:
        primary = resolve_color_nested(data, "primary", "brand", "accent", fallback="#2563eb")
        on_primary = resolve_color_nested(data, "on-primary", "text-on-primary", "text-on-brand", "text-on-dark", fallback="#ffffff")
        ink = resolve_color_nested(data, "ink", "text-primary", fallback="#111827")
        muted = resolve_color_nested(data, "ink-muted", "text-muted", fallback="#6b7280")
        canvas = resolve_color_nested(data, "canvas", "surface-canvas", fallback="#ffffff")
        canvas_soft = resolve_color_nested(data, "canvas-alt", "surface-card", "surface-1", "surface", fallback="#f6f9fc")
        border = resolve_color_nested(data, "hairline", "border", fallback="#e3e8ee")
        accent = resolve_color_nested(data, "accent-2", "accent", "semantic-error", fallback="#ea2261")

    success = resolve_color_nested(data, "semantic-success", "success", fallback="#16a34a")
    warning = resolve_color_nested(data, "semantic-warning", "warning", fallback="#b66c00")
    danger = resolve_color_nested(data, "semantic-error", "semantic-danger", "error", fallback="#dc2626")

    body_type = first_typography(data, "body")
    display_type = first_typography(data, "display") or first_typography(data, "heading")
    font_sans = body_type.get("fontFamily", GENERIC_FONT_FALLBACK)
    font_display = display_type.get("fontFamily", font_sans)
    font_mono = "ui-monospace, SFMono-Regular, Menlo, Consolas, monospace"

    return f"""    --color-primary: {primary};
    --color-primary-foreground: {on_primary};
    --color-foreground: {ink};
    --color-foreground-muted: {muted};
    --color-foreground-tertiary: {muted};
    --color-foreground-disabled: {border};
    --color-foreground-on-primary: {on_primary};
    --color-canvas: {canvas};
    --color-canvas-soft: {canvas_soft};
    --color-surface-elevated: {canvas};
    --color-border: {border};
    --color-border-soft: {border};
    --color-accent: {accent};
    --color-accent-soft: color-mix(in srgb, {primary} 10%, transparent);
    --color-success: {success};
    --color-warning: {warning};
    --color-danger: {danger};
    --color-silver: #aaa;
    --color-avatar-fill: rgba(0,0,0,0.06);
    --color-chip-bg: rgba(0,0,0,0.06);
    --font-display: {font_display};
    --font-sans: {font_sans};
    --font-mono: {font_mono};
    --shadow-md: 0 1px 2px rgba(0,0,0,0.06);
    --shadow-lg: 0 8px 24px rgba(0,0,0,0.12);"""


def kit_mirror_examples_html(data: dict[str, Any], lang: str = "en") -> str:
    """Return the standardized 9-pattern kit-mirror product UI examples."""
    z = lang == "zh"
    t = {
        "pricing": "定价方案" if z else "Pricing",
        "pricing_intro": "三栏定价卡片，特色方案使用品牌色高亮。" if z else "Three-column pricing cards with a featured plan highlighted in the brand color.",
        "starter": "入门版" if z else "Starter",
        "pro": "专业版" if z else "Professional",
        "enterprise": "企业版" if z else "Enterprise",
        "free": "免费" if z else "Free",
        "per_month": "/月" if z else "/mo",
        "popular": "最受欢迎" if z else "Most popular",
        "get_started": "开始使用" if z else "Get started",
        "talk_sales": "联系销售" if z else "Talk to sales",
        "feature_1": "最多 5 个项目" if z else "Up to 5 projects",
        "feature_2": "基础分析报表" if z else "Basic analytics",
        "feature_3": "社区支持" if z else "Community support",
        "feature_pro1": "无限项目" if z else "Unlimited projects",
        "feature_pro2": "高级分析报表" if z else "Advanced analytics",
        "feature_pro3": "优先支持" if z else "Priority support",
        "feature_ent1": "无限项目与数据源" if z else "Unlimited everything",
        "feature_ent2": "自定义仪表盘" if z else "Custom dashboards",
        "feature_ent3": "专属客户经理" if z else "Dedicated account manager",

        "product_selector": "产品选择器" if z else "Product Selector",
        "product_selector_intro": "带搜索和分类筛选的产品网格。" if z else "Product grid with search and category filter.",
        "all_categories": "全部分类" if z else "All categories",
        "search_placeholder": "搜索产品..." if z else "Search products...",
        "design_kit": "设计组件库" if z else "Design Kit",
        "api_client": "API 客户端" if z else "API Client",
        "analytics_suite": "分析套件" if z else "Analytics Suite",
        "data_pipeline": "数据管道" if z else "Data Pipeline",
        "deploy": "部署工具" if z else "Deploy Tool",
        "monitoring": "监控面板" if z else "Monitoring",

        "shopping_cart": "购物车" if z else "Shopping Cart",
        "shopping_cart_intro": "两栏布局：左侧商品明细，右侧订单摘要。" if z else "Two-column layout — line items on the left, order summary on the right.",

        "app_shell": "应用框架" if z else "App Shell",
        "app_shell_intro": "侧边栏导航 + 数据表格，展示 CRUD 型后台的标准页面结构。" if z else "Sidebar navigation with a data table, showing the standard CRUD admin page structure.",
        "workspace": "工作台" if z else "Workspace",
        "data_assets": "数据资产" if z else "Data Assets",
        "reports": "报表分析" if z else "Reports",
        "settings": "系统设置" if z else "Settings",
        "home": "首页" if z else "Home",
        "assets": "资产" if z else "Assets",
        "models": "模型" if z else "Models",
        "tasks": "任务" if z else "Tasks",
        "import": "导入" if z else "Import",
        "new": "新建" if z else "New",
        "refresh": "刷新" if z else "Refresh",
        "search": "查询" if z else "Search",
        "reset": "重置" if z else "Reset",
        "online": "在线" if z else "Online",
        "pending": "待处理" if z else "Pending",
        "detail": "详情" if z else "Detail",
        "edit": "编辑" if z else "Edit",
        "total_items": "未记录总数" if z else "Total not documented",

        "data_table": "数据表格" if z else "Data Table",
        "data_table_intro": "带排序表头、状态标签和内联操作的完整数据表。" if z else "Full data table with sortable headers, status chips, and inline actions.",

        "auth_forms": "登录 / 注册" if z else "Auth Forms",
        "auth_intro": "居中卡片布局，含品牌主按钮、SSO 入口和协议勾选框。" if z else "Centered card layout with brand-primary button, SSO entry, and agreement checkbox.",
        "sign_in": "登录" if z else "Sign in",
        "email": "邮箱" if z else "Email",
        "password": "密码" if z else "Password",
        "remember_me": "记住我" if z else "Remember me",
        "forgot_password": "忘记密码？" if z else "Forgot password?",
        "continue_sso": "使用 SSO 登录" if z else "Continue with SSO",
        "create_account": "创建账号" if z else "Create account",
        "full_name": "姓名" if z else "Full Name",
        "agree_terms": "我同意" if z else "I agree to the",
        "terms": "服务条款" if z else "Terms",
        "privacy": "隐私政策" if z else "Privacy Policy",
        "new_here": "新用户？" if z else "New here?",
        "already_have": "已有账号？" if z else "Already have an account?",

        "modal": "模态对话框" if z else "Modal Dialog",
        "modal_intro": "居中卡片覆盖半透明遮罩，品牌主按钮 + 文字次按钮。" if z else "Centered card over a scrim with a primary action and text-link cancel.",
        "modal_confirm": "确认发布" if z else "Publish dataset to production?",
        "modal_body": "此操作将替换当前线上版本，所有下游消费者将在 5 分钟内收到更新。" if z else "This replaces the current production version. All downstream consumers will be updated within 5 minutes.",
        "modal_cancel": "取消" if z else "Cancel",
        "modal_confirm_btn": "确认发布" if z else "Publish",

        "empty_state": "空状态" if z else "Empty State",
        "empty_intro": "图标 + 引导文案 + 单一主操作按钮。" if z else "Outlined icon tile, declarative heading, body copy, and a single primary CTA.",
        "empty_title": "暂无数据" if z else "Nothing here yet.",
        "empty_body": "连接一个数据源或上传 CSV 文件来开始导入记录。" if z else "Connect a source or upload a CSV to start ingesting records into this workspace.",
        "empty_cta": "连接数据源" if z else "Connect a source",

        "toast_stack": "消息提示" if z else "Toast Stack",
        "toast_intro": "四种语义变体：信息、成功、警告、错误，带 3px 彩色左边条。" if z else "Four semantic variants — info, success, warning, error — each with a 3px accent edge.",
        "toast_info_tag": "信息" if z else "info",
        "toast_info_title": "同步进行中" if z else "Sync in progress",
        "toast_info_body": "正在回填 412 条记录到操作日志。" if z else "Backfilling 412 records into the operations log.",
        "toast_success_tag": "成功" if z else "success",
        "toast_success_title": "发布成功" if z else "Dataset promoted",
        "toast_success_body": "v2024.11.21 已上线，所有消费者已更新。" if z else "v2024.11.21 is live across all downstream consumers.",
        "toast_warning_tag": "警告" if z else "warning",
        "toast_warning_title": "配额接近上限" if z else "Approaching quota",
        "toast_warning_body": "本月计算额度已使用 88%。" if z else "88% of your monthly compute has been used.",
        "toast_error_tag": "错误" if z else "error",
        "toast_error_title": "同步失败" if z else "Sync failed",
        "toast_error_body": "数据源返回 502。已加入重试队列。" if z else "Watchlist source returned 502. Retry queued.",
    }

    body_kv = first_typography(data, "body")
    font_kit = body_kv.get("fontFamily", GENERIC_FONT_FALLBACK)
    primary_v = resolve_color_nested(data, "primary", "brand", "accent", fallback="#2563eb")
    ink_v = resolve_color_nested(data, "ink", "text-primary", fallback="#111827")
    muted_v = resolve_color_nested(data, "ink-muted", "text-muted", fallback="#6b7280")
    border_v = resolve_color_nested(data, "hairline", "border", fallback="#e3e8ee")
    canvas_v = resolve_color_nested(data, "canvas", "surface-canvas", fallback="#ffffff")
    canvas_soft_v = resolve_color_nested(data, "canvas-alt", "surface-card", "surface-1", "surface", fallback="#f6f9fc")
    success_v = resolve_color_nested(data, "semantic-success", "success", fallback="#16a34a")
    warning_v = resolve_color_nested(data, "semantic-warning", "warning", fallback="#b66c00")
    danger_v = resolve_color_nested(data, "semantic-error", "semantic-danger", "error", fallback="#dc2626")
    accent_v = resolve_color_nested(data, "accent-2", "accent", "semantic-error", fallback="#ea2261")
    on_primary_v = resolve_color_nested(data, "on-primary", "text-on-primary", fallback="#ffffff")

    return f"""
  <div class="kit-mirror" style="--color-primary:{primary_v};--color-primary-foreground:{on_primary_v};--color-foreground:{ink_v};--color-foreground-muted:{muted_v};--color-foreground-tertiary:{muted_v};--color-foreground-disabled:{border_v};--color-foreground-on-primary:{on_primary_v};--color-canvas:{canvas_v};--color-canvas-soft:{canvas_soft_v};--color-surface-elevated:{canvas_v};--color-border:{border_v};--color-border-soft:{border_v};--color-accent:{accent_v};--color-accent-soft:color-mix(in srgb,{primary_v} 10%,transparent);--color-success:{success_v};--color-warning:{warning_v};--color-danger:{danger_v};--color-silver:#aaa;--color-avatar-fill:rgba(0,0,0,0.06);--color-chip-bg:rgba(0,0,0,0.06);--font-display:{font_kit};--font-sans:{font_kit};--font-mono:ui-monospace,SFMono-Regular,Menlo,Consolas,monospace;--shadow-md:0 1px 2px rgba(0,0,0,0.06);--shadow-lg:0 8px 24px rgba(0,0,0,0.12);">
  <!-- ============ kit-mirror 9-pattern examples ============ -->
  <section class="ex-section">
    <div class="container">
      <h2 class="ex-h2">1. {t['pricing']}</h2>
      <p class="ex-intro">{t['pricing_intro']}</p>
      <div class="ex-grid-cards-three">
        <div class="ex-card-pricing">
          <h3 class="ex-card-tier">{t['starter']}</h3>
          <div class="ex-card-price">{t['free']}</div>
          <ul class="ex-card-list">
            <li>{t['feature_1']}</li><li>{t['feature_2']}</li><li>{t['feature_3']}</li>
          </ul>
          <button class="ex-outlined" style="width:100%">{t['get_started']}</button>
        </div>
        <div class="ex-card-pricing ex-card-pricing-featured">
          <div class="ex-mono" style="margin-bottom:6px;">{t['popular']}</div>
          <h3 class="ex-card-tier">{t['pro']}</h3>
          <div class="ex-card-price">$29<span style="font-size:16px;font-weight:400;">{t['per_month']}</span></div>
          <ul class="ex-card-list">
            <li>{t['feature_pro1']}</li><li>{t['feature_pro2']}</li><li>{t['feature_pro3']}</li>
          </ul>
          <button class="ex-primary" style="width:100%">{t['get_started']}</button>
        </div>
        <div class="ex-card-pricing">
          <h3 class="ex-card-tier">{t['enterprise']}</h3>
          <div class="ex-card-price" style="font-size:24px;font-weight:700;">{t['talk_sales']}</div>
          <ul class="ex-card-list">
            <li>{t['feature_ent1']}</li><li>{t['feature_ent2']}</li><li>{t['feature_ent3']}</li>
          </ul>
          <button class="ex-outlined" style="width:100%">{t['talk_sales']}</button>
        </div>
      </div>
    </div>
  </section>

  <section class="ex-section">
    <div class="container">
      <h2 class="ex-h2">2. {t['product_selector']}</h2>
      <p class="ex-intro">{t['product_selector_intro']}</p>
      <div class="ex-frame">
        <div style="display:flex;gap:12px;margin-bottom:20px;flex-wrap:wrap;">
          <input class="ex-input" style="max-width:280px;" placeholder="{t['search_placeholder']}">
          <select class="ex-input" style="max-width:180px;"><option>{t['all_categories']}</option></select>
        </div>
        <div class="ex-grid-cards-three">
          <div class="ex-card-product"><div class="ex-card-thumb"></div><strong>{t['design_kit']}</strong><span>{'Figma + React' if not z else 'Figma + React'}</span></div>
          <div class="ex-card-product"><div class="ex-card-thumb"></div><strong>{t['api_client']}</strong><span>REST & GraphQL</span></div>
          <div class="ex-card-product"><div class="ex-card-thumb"></div><strong>{t['analytics_suite']}</strong><span>SQL + Charts</span></div>
          <div class="ex-card-product"><div class="ex-card-thumb"></div><strong>{t['data_pipeline']}</strong><span>ETL + CDC</span></div>
          <div class="ex-card-product"><div class="ex-card-thumb"></div><strong>{t['deploy']}</strong><span>CI/CD</span></div>
          <div class="ex-card-product"><div class="ex-card-thumb"></div><strong>{t['monitoring']}</strong><span>Metrics + Alerts</span></div>
        </div>
      </div>
    </div>
  </section>

  <section class="ex-section">
    <div class="container">
      <h2 class="ex-h2">3. {t['shopping_cart']}</h2>
      <p class="ex-intro">{t['shopping_cart_intro']}</p>
      <div class="ex-frame" style="display:grid;grid-template-columns:1.4fr 1fr;gap:20px;">
        <div style="display:flex;flex-direction:column;gap:12px;">
          <div style="display:flex;gap:16px;align-items:flex-start;padding:16px;background:var(--color-canvas);border:1px solid var(--color-border);border-radius:6px;">
            <div style="width:80px;height:80px;background:var(--color-canvas-soft);border-radius:4px;flex-shrink:0;"></div>
            <div style="flex:1;min-width:0;"><strong>{t['design_kit']}</strong><p style="margin:4px 0;font-size:13px;color:var(--color-foreground-muted);">UI component library</p><span style="font-weight:600;">$49</span></div>
          </div>
          <div style="display:flex;gap:16px;align-items:flex-start;padding:16px;background:var(--color-canvas);border:1px solid var(--color-border);border-radius:6px;">
            <div style="width:80px;height:80px;background:var(--color-canvas-soft);border-radius:4px;flex-shrink:0;"></div>
            <div style="flex:1;min-width:0;"><strong>{t['api_client']}</strong><p style="margin:4px 0;font-size:13px;color:var(--color-foreground-muted);">SDK + CLI tools</p><span style="font-weight:600;">$29</span></div>
          </div>
        </div>
        <div style="padding:20px;background:var(--color-canvas-soft);border:1px solid var(--color-border);border-radius:6px;display:flex;flex-direction:column;gap:12px;">
          <strong style="font-size:16px;">{'订单摘要' if z else 'Order Summary'}</strong>
          <div style="display:flex;justify-content:space-between;font-size:14px;"><span>{'小计' if z else 'Subtotal'}</span><span>$78</span></div>
          <div style="display:flex;justify-content:space-between;font-size:14px;"><span>{'运费' if z else 'Shipping'}</span><span>{'免费' if z else 'Free'}</span></div>
          <div style="height:1px;background:var(--color-border);"></div>
          <div style="display:flex;justify-content:space-between;font-weight:700;"><span>{'合计' if z else 'Total'}</span><span>$78</span></div>
          <button class="ex-primary" style="width:100%;margin-top:4px;">{'结算' if z else 'Checkout'}</button>
        </div>
      </div>
    </div>
  </section>

  <section class="ex-section">
    <div class="container">
      <h2 class="ex-h2">4. {t['app_shell']}</h2>
      <p class="ex-intro">{t['app_shell_intro']}</p>
      <div class="ex-frame" style="min-height:420px;display:grid;grid-template-rows:44px 1fr;">
        <div style="display:flex;align-items:center;gap:20px;padding:0 16px;background:var(--color-primary);color:var(--color-primary-foreground);font-size:13px;font-weight:600;">
          <span>Design System</span><span style="opacity:.78;">{t['workspace']}</span><span style="opacity:.78;">{t['data_assets']}</span><span style="opacity:.78;">{t['settings']}</span>
        </div>
        <div style="display:grid;grid-template-columns:72px 164px 1fr;min-height:0;">
          <div style="display:grid;align-content:start;gap:2px;padding:8px 0;background:var(--color-canvas-soft);border-right:1px solid var(--color-border);">
            <span style="display:grid;place-items:center;min-height:48px;font-size:11px;color:var(--color-foreground-muted);">{t['home']}</span>
            <span style="display:grid;place-items:center;min-height:48px;font-size:11px;background:var(--color-accent-soft);color:var(--color-primary);border-right:3px solid var(--color-primary);font-weight:600;">{t['assets']}</span>
            <span style="display:grid;place-items:center;min-height:48px;font-size:11px;color:var(--color-foreground-muted);">{t['models']}</span>
            <span style="display:grid;place-items:center;min-height:48px;font-size:11px;color:var(--color-foreground-muted);">{t['tasks']}</span>
          </div>
          <div style="padding:12px;border-right:1px solid var(--color-border);color:var(--color-foreground-muted);font-size:12px;">
            <strong style="color:var(--color-foreground);display:block;margin-bottom:8px;">{'目录' if z else 'Catalog'}</strong>
            <span style="display:block;padding:6px 8px;border-radius:4px;color:var(--color-primary);background:var(--color-accent-soft);">{t['assets']}</span>
            <span style="display:block;padding:6px 8px;margin-top:4px;">{'元数据' if z else 'Metadata'}</span>
            <span style="display:block;padding:6px 8px;margin-top:4px;">{'血缘' if z else 'Lineage'}</span>
          </div>
          <div style="padding:12px;min-width:0;">
            <div style="display:flex;align-items:center;gap:10px;flex-wrap:wrap;margin-bottom:12px;padding:12px;background:var(--color-canvas-soft);border:1px solid var(--color-border);border-radius:4px;">
              <label style="font-size:12px;color:var(--color-foreground-muted);">{'关键词' if z else 'Keyword'}</label>
              <input class="ex-input" style="width:160px;height:30px;" placeholder="sample_item">
              <label style="font-size:12px;color:var(--color-foreground-muted);">{'状态' if z else 'Status'}</label>
              <select class="ex-input" style="width:100px;height:30px;"><option>{'全部' if z else 'All'}</option></select>
              <button class="ex-outlined" style="height:30px;padding:0 12px;font-size:13px;">{t['reset']}</button>
              <button class="ex-primary" style="height:30px;padding:0 12px;font-size:13px;">{t['search']}</button>
            </div>
            <div style="padding:12px;background:var(--color-canvas-soft);border:1px solid var(--color-border);border-radius:4px;">
              <div style="display:flex;align-items:center;justify-content:space-between;margin-bottom:10px;">
                <strong style="border-left:3px solid var(--color-primary);padding-left:8px;">{'列表样例' if z else 'List Example'}</strong>
                <div style="display:flex;gap:8px;"><button class="ex-outlined" style="height:28px;padding:0 10px;font-size:12px;">{t['import']}</button><button class="ex-primary" style="height:28px;padding:0 10px;font-size:12px;">{t['new']}</button></div>
              </div>
              <table style="width:100%;border-collapse:collapse;font-size:12px;table-layout:fixed;">
                <thead><tr style="text-align:left;"><th style="padding:8px 10px;border-bottom:1px solid var(--color-border);background:var(--color-canvas-soft);">{'名称' if z else 'Name'}</th><th style="padding:8px 10px;border-bottom:1px solid var(--color-border);background:var(--color-canvas-soft);">{'状态' if z else 'Status'}</th><th style="padding:8px 10px;border-bottom:1px solid var(--color-border);background:var(--color-canvas-soft);">{'操作' if z else 'Actions'}</th></tr></thead>
                <tbody>
                  <tr><td style="padding:8px 10px;border-bottom:1px solid var(--color-border-soft);"><span style="display:block;width:68%;height:10px;border-radius:999px;background:var(--color-border-soft);"></span></td><td style="padding:8px 10px;border-bottom:1px solid var(--color-border-soft);"><span style="display:inline-block;width:7px;height:7px;border-radius:50%;background:var(--color-success);margin-right:6px;"></span>{t['online']}</td><td style="padding:8px 10px;border-bottom:1px solid var(--color-border-soft);color:var(--color-primary);font-weight:600;">{t['detail']}</td></tr>
                  <tr><td style="padding:8px 10px;border-bottom:1px solid var(--color-border-soft);"><span style="display:block;width:54%;height:10px;border-radius:999px;background:var(--color-border-soft);"></span></td><td style="padding:8px 10px;border-bottom:1px solid var(--color-border-soft);"><span style="display:inline-block;width:7px;height:7px;border-radius:50%;background:var(--color-success);margin-right:6px;"></span>{t['online']}</td><td style="padding:8px 10px;border-bottom:1px solid var(--color-border-soft);color:var(--color-primary);font-weight:600;">{t['detail']}</td></tr>
                  <tr><td style="padding:8px 10px;border-bottom:1px solid var(--color-border-soft);"><span style="display:block;width:62%;height:10px;border-radius:999px;background:var(--color-border-soft);"></span></td><td style="padding:8px 10px;border-bottom:1px solid var(--color-border-soft);"><span style="display:inline-block;width:7px;height:7px;border-radius:50%;background:var(--color-warning);margin-right:6px;"></span>{t['pending']}</td><td style="padding:8px 10px;border-bottom:1px solid var(--color-border-soft);color:var(--color-primary);font-weight:600;">{t['edit']}</td></tr>
                </tbody>
              </table>
              <div style="display:flex;justify-content:flex-end;gap:8px;align-items:center;padding-top:12px;color:var(--color-foreground-muted);font-size:12px;">
                {t['total_items']} <span style="min-width:24px;display:inline-grid;place-items:center;background:var(--color-accent-soft);color:var(--color-primary);border-radius:4px;font-weight:700;">1</span> 2 3 {'10 条/页' if z else '10 / page'}
              </div>
            </div>
          </div>
        </div>
      </div>
    </div>
  </section>

  <section class="ex-section">
    <div class="container">
      <h2 class="ex-h2">5. {t['data_table']}</h2>
      <p class="ex-intro">{t['data_table_intro']}</p>
      <div class="ex-frame">
        <table style="width:100%;border-collapse:collapse;font-size:14px;">
          <thead><tr style="text-align:left;background:var(--color-canvas-soft);"><th style="padding:12px 16px;border-bottom:1px solid var(--color-border);font-family:var(--font-mono);font-size:11px;text-transform:uppercase;">{'名称' if z else 'Name'}</th><th style="padding:12px 16px;border-bottom:1px solid var(--color-border);font-family:var(--font-mono);font-size:11px;text-transform:uppercase;">{'类型' if z else 'Type'}</th><th style="padding:12px 16px;border-bottom:1px solid var(--color-border);font-family:var(--font-mono);font-size:11px;text-transform:uppercase;">{'状态' if z else 'Status'}</th><th style="padding:12px 16px;border-bottom:1px solid var(--color-border);font-family:var(--font-mono);font-size:11px;text-transform:uppercase;">{'负责人' if z else 'Owner'}</th></tr></thead>
          <tbody>
            <tr><td style="padding:12px 16px;border-bottom:1px solid var(--color-border-soft);font-weight:600;">ODS_CUSTOMER_ORDER</td><td style="padding:12px 16px;border-bottom:1px solid var(--color-border-soft);color:var(--color-foreground-muted);">{'表' if z else 'Table'}</td><td style="padding:12px 16px;border-bottom:1px solid var(--color-border-soft);"><span style="display:inline-flex;align-items:center;gap:6px;"><span style="width:7px;height:7px;border-radius:50%;background:var(--color-success);"></span>{t['online']}</span></td><td style="padding:12px 16px;border-bottom:1px solid var(--color-border-soft);color:var(--color-foreground-muted);">Admin</td></tr>
            <tr><td style="padding:12px 16px;border-bottom:1px solid var(--color-border-soft);font-weight:600;">DWD_ASSET_INDEX</td><td style="padding:12px 16px;border-bottom:1px solid var(--color-border-soft);color:var(--color-foreground-muted);">{'视图' if z else 'View'}</td><td style="padding:12px 16px;border-bottom:1px solid var(--color-border-soft);"><span style="display:inline-flex;align-items:center;gap:6px;"><span style="width:7px;height:7px;border-radius:50%;background:var(--color-success);"></span>{t['online']}</span></td><td style="padding:12px 16px;border-bottom:1px solid var(--color-border-soft);color:var(--color-foreground-muted);">DataOps</td></tr>
            <tr><td style="padding:12px 16px;border-bottom:1px solid var(--color-border-soft);font-weight:600;">DWD_SALES_SUMMARY</td><td style="padding:12px 16px;border-bottom:1px solid var(--color-border-soft);color:var(--color-foreground-muted);">{'物化视图' if z else 'MV'}</td><td style="padding:12px 16px;border-bottom:1px solid var(--color-border-soft);"><span style="display:inline-flex;align-items:center;gap:6px;"><span style="width:7px;height:7px;border-radius:50%;background:var(--color-warning);"></span>{t['pending']}</span></td><td style="padding:12px 16px;border-bottom:1px solid var(--color-border-soft);color:var(--color-foreground-muted);">Analyst</td></tr>
          </tbody>
        </table>
      </div>
    </div>
  </section>

  <section class="ex-section">
    <div class="container">
      <h2 class="ex-h2">6. {t['auth_forms']}</h2>
      <p class="ex-intro">{t['auth_intro']}</p>
      <div style="display:grid;grid-template-columns:repeat(auto-fit,minmax(320px,1fr));gap:24px;">
        <div style="background:var(--color-canvas);border:1px solid var(--color-border);border-radius:6px;padding:32px;">
          <div class="ex-mono" style="margin-bottom:12px;">/0.1 · {t['sign_in']}</div>
          <h3 style="font-family:var(--font-display);font-size:clamp(22px,3.5vw,28px);font-weight:700;line-height:1.05;color:var(--color-foreground);margin:0 0 24px;">{t['sign_in']}</h3>
          <div style="display:flex;flex-direction:column;gap:14px;">
            <div class="ex-field"><label class="ex-field-label">{t['email']}</label><input type="email" placeholder="you@company.com" class="ex-input"></div>
            <div class="ex-field"><label class="ex-field-label">{t['password']}</label><input type="password" placeholder="········" class="ex-input"></div>
          </div>
          <div style="display:flex;align-items:center;justify-content:space-between;margin-top:4px;">
            <label style="display:flex;align-items:center;gap:8px;font-size:13px;color:var(--color-foreground);"><input type="checkbox"> {t['remember_me']}</label>
            <a href="#" style="font-size:13px;color:var(--color-foreground);text-decoration:underline;">{t['forgot_password']}</a>
          </div>
          <button class="ex-primary" style="width:100%;margin-top:8px;">{t['sign_in']}</button>
          <div style="display:flex;align-items:center;gap:12px;margin:24px 0;">
            <span style="flex:1;height:1px;background:var(--color-border);"></span>
            <span class="ex-mono" style="font-size:10px;">{'或' if z else 'or'}</span>
            <span style="flex:1;height:1px;background:var(--color-border);"></span>
          </div>
          <button class="ex-outlined" style="width:100%;">{t['continue_sso']}</button>
          <div style="margin-top:20px;font-size:13px;color:var(--color-foreground-muted);text-align:center;">{t['new_here']} <a href="#" style="color:var(--color-foreground);text-decoration:underline;">{t['create_account']}</a></div>
        </div>
        <div style="background:var(--color-canvas);border:1px solid var(--color-border);border-radius:6px;padding:32px;">
          <div class="ex-mono" style="margin-bottom:12px;">/0.2 · {t['create_account']}</div>
          <h3 style="font-family:var(--font-display);font-size:clamp(22px,3.5vw,28px);font-weight:700;line-height:1.05;color:var(--color-foreground);margin:0 0 24px;">{'开始使用' if z else 'Start building.'}</h3>
          <div style="display:flex;flex-direction:column;gap:14px;">
            <div class="ex-field"><label class="ex-field-label">{t['full_name']}</label><input type="text" placeholder="{'张三' if z else 'Mira Reyes'}" class="ex-input"></div>
            <div class="ex-field"><label class="ex-field-label">{t['email']}</label><input type="email" placeholder="you@company.com" class="ex-input"></div>
            <div class="ex-field"><label class="ex-field-label">{t['password']}</label><input type="password" placeholder="········" class="ex-input"></div>
          </div>
          <label style="display:flex;align-items:flex-start;gap:8px;font-size:13px;color:var(--color-foreground-muted);margin-top:4px;line-height:1.5;">
            <input type="checkbox" style="margin-top:3px;">
            <span>{t['agree_terms']} <a href="#" style="color:var(--color-foreground);text-decoration:underline;">{t['terms']}</a> {'和' if z else 'and'} <a href="#" style="color:var(--color-foreground);text-decoration:underline;">{t['privacy']}</a>。</span>
          </label>
          <button class="ex-primary" style="width:100%;margin-top:8px;">{t['create_account']}</button>
          <div style="display:flex;align-items:center;gap:12px;margin:24px 0;">
            <span style="flex:1;height:1px;background:var(--color-border);"></span>
            <span class="ex-mono" style="font-size:10px;">{'或' if z else 'or'}</span>
            <span style="flex:1;height:1px;background:var(--color-border);"></span>
          </div>
          <button class="ex-outlined" style="width:100%;">{t['continue_sso']}</button>
          <div style="margin-top:20px;font-size:13px;color:var(--color-foreground-muted);text-align:center;">{t['already_have']} <a href="#" style="color:var(--color-foreground);text-decoration:underline;">{t['sign_in']}</a></div>
        </div>
      </div>
    </div>
  </section>

  <section class="ex-section">
    <div class="container">
      <h2 class="ex-h2">7. {t['modal']}</h2>
      <p class="ex-intro">{t['modal_intro']}</p>
      <div class="ex-frame short" style="position:relative;overflow:hidden;">
        <div style="padding:24px;opacity:0.35;">
          <div style="height:14px;width:40%;background:var(--color-border);border-radius:2px;margin-bottom:12px;"></div>
          <div style="height:12px;width:70%;background:var(--color-border);border-radius:2px;margin-bottom:8px;"></div>
          <div style="height:12px;width:60%;background:var(--color-border);border-radius:2px;"></div>
        </div>
        <div class="ex-scrim"></div>
        <div style="position:absolute;inset:0;display:flex;align-items:center;justify-content:center;padding:24px;">
          <div class="ex-modal-card">
            <div style="padding:24px 28px 16px;">
              <div class="ex-mono" style="margin-bottom:8px;">/0.1 · {t['modal_confirm_btn']}</div>
              <h4 style="font-family:var(--font-display);font-size:22px;font-weight:700;line-height:1.1;color:var(--color-foreground);margin:0;">{t['modal_confirm']}</h4>
            </div>
            <div style="padding:0 28px 20px;font-size:14px;color:var(--color-foreground-muted);line-height:1.5;">{t['modal_body']}</div>
            <div style="display:flex;align-items:center;justify-content:space-between;padding:16px 24px;border-top:1px solid var(--color-border);">
              <button class="ex-textlink">{t['modal_cancel']}</button>
              <button class="ex-primary" style="height:40px;padding:10px 18px;font-size:14px;">{t['modal_confirm_btn']}</button>
            </div>
          </div>
        </div>
      </div>
    </div>
  </section>

  <section class="ex-section">
    <div class="container">
      <h2 class="ex-h2">8. {t['empty_state']}</h2>
      <p class="ex-intro">{t['empty_intro']}</p>
      <div class="ex-emptystate">
        <div style="width:56px;height:56px;border:1px solid var(--color-border-soft);border-radius:6px;display:flex;align-items:center;justify-content:center;margin-bottom:20px;color:var(--color-foreground-muted);">
          <svg width="24" height="24" viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="1.5"><rect x="3.5" y="5.5" width="17" height="13" rx="1"/><path d="M3.5 9.5h17M8 5.5v13"/></svg>
        </div>
        <div class="ex-mono" style="margin-bottom:12px;">/0.1 · {'暂无数据' if z else 'No datasets'}</div>
        <h4 style="font-family:var(--font-display);font-size:clamp(22px,3.5vw,28px);font-weight:700;line-height:1.05;color:var(--color-foreground);margin:0 0 8px;">{t['empty_title']}</h4>
        <p style="font-size:15px;color:var(--color-foreground-muted);max-width:380px;margin:0 0 24px;line-height:1.5;">{t['empty_body']}</p>
        <button class="ex-primary">{t['empty_cta']}</button>
      </div>
    </div>
  </section>

  <section class="ex-section">
    <div class="container">
      <h2 class="ex-h2">9. {t['toast_stack']}</h2>
      <p class="ex-intro">{t['toast_intro']}</p>
      <div class="ex-grid-toasts">
        <div class="ex-toast" role="status">
          <div style="background:var(--color-foreground);"></div>
          <div style="padding:14px 16px;">
            <div style="display:flex;align-items:center;gap:8px;margin-bottom:4px;"><span style="width:6px;height:6px;background:var(--color-foreground);border-radius:9999px;"></span><span class="ex-mono" style="font-size:10px;">{t['toast_info_tag']}</span></div>
            <div style="font-size:14px;font-weight:600;color:var(--color-foreground);margin-bottom:2px;">{t['toast_info_title']}</div>
            <div style="font-size:13px;color:var(--color-foreground-muted);line-height:1.43;">{t['toast_info_body']}</div>
          </div>
          <button style="background:transparent;border:none;color:var(--color-foreground-muted);padding:12px 14px;font-size:14px;cursor:pointer;" aria-label="Dismiss">&times;</button>
        </div>
        <div class="ex-toast" role="status">
          <div style="background:var(--color-success);"></div>
          <div style="padding:14px 16px;">
            <div style="display:flex;align-items:center;gap:8px;margin-bottom:4px;"><span style="width:6px;height:6px;background:var(--color-success);border-radius:9999px;"></span><span class="ex-mono" style="font-size:10px;">{t['toast_success_tag']}</span></div>
            <div style="font-size:14px;font-weight:600;color:var(--color-foreground);margin-bottom:2px;">{t['toast_success_title']}</div>
            <div style="font-size:13px;color:var(--color-foreground-muted);line-height:1.43;">{t['toast_success_body']}</div>
          </div>
          <button style="background:transparent;border:none;color:var(--color-foreground-muted);padding:12px 14px;font-size:14px;cursor:pointer;" aria-label="Dismiss">&times;</button>
        </div>
        <div class="ex-toast" role="status">
          <div style="background:var(--color-warning);"></div>
          <div style="padding:14px 16px;">
            <div style="display:flex;align-items:center;gap:8px;margin-bottom:4px;"><span style="width:6px;height:6px;background:var(--color-warning);border-radius:9999px;"></span><span class="ex-mono" style="font-size:10px;">{t['toast_warning_tag']}</span></div>
            <div style="font-size:14px;font-weight:600;color:var(--color-foreground);margin-bottom:2px;">{t['toast_warning_title']}</div>
            <div style="font-size:13px;color:var(--color-foreground-muted);line-height:1.43;">{t['toast_warning_body']}</div>
          </div>
          <button style="background:transparent;border:none;color:var(--color-foreground-muted);padding:12px 14px;font-size:14px;cursor:pointer;" aria-label="Dismiss">&times;</button>
        </div>
        <div class="ex-toast" role="status">
          <div style="background:var(--color-danger);"></div>
          <div style="padding:14px 16px;">
            <div style="display:flex;align-items:center;gap:8px;margin-bottom:4px;"><span style="width:6px;height:6px;background:var(--color-danger);border-radius:9999px;"></span><span class="ex-mono" style="font-size:10px;">{t['toast_error_tag']}</span></div>
            <div style="font-size:14px;font-weight:600;color:var(--color-foreground);margin-bottom:2px;">{t['toast_error_title']}</div>
            <div style="font-size:13px;color:var(--color-foreground-muted);line-height:1.43;">{t['toast_error_body']}</div>
          </div>
          <button style="background:transparent;border:none;color:var(--color-foreground-muted);padding:12px 14px;font-size:14px;cursor:pointer;" aria-label="Dismiss">&times;</button>
        </div>
      </div>
    </div>
  </section>
  </div>"""


def kit_mirror_example_css() -> str:
    """Return the kit-mirror shared CSS for the 9-pattern examples.

    All generic tokens (--color-primary, --color-foreground, …) are scoped to
    the `.kit-mirror` container so they do NOT overwrite brand tokens in the
    rest of the preview. The alias bridge is emitted by kit_mirror_alias_css()
    and injected into `.kit-mirror { … }` at call sites.
    """
    return """
  .kit-mirror .ex-section { padding: clamp(48px, 8vw, 96px) 0; border-top: 1px solid var(--color-border); background: var(--color-canvas); }
  .kit-mirror .ex-section .container { max-width: 1200px; margin: 0 auto; padding: 0 32px; }
  .kit-mirror .ex-h2 { font-family: var(--font-display); font-size: clamp(32px, 5vw, 50px); font-weight: 700; line-height: 1.0; letter-spacing: -0.5px; color: var(--color-foreground); margin: 0 0 12px; }
  .kit-mirror .ex-intro { font-size: 18px; color: var(--color-foreground-muted); max-width: 720px; margin: 0 0 40px; line-height: 1.55; }
  .kit-mirror .ex-mono { font-family: var(--font-mono); font-size: 12px; color: var(--color-foreground-muted); }
  .kit-mirror .ex-field { display: flex; flex-direction: column; gap: 6px; }
  .kit-mirror .ex-field-label { font-family: var(--font-mono); font-size: 11px; text-transform: uppercase; color: var(--color-foreground-muted); }
  .kit-mirror .ex-input { background: var(--color-canvas); color: var(--color-foreground); border: 1px solid var(--color-border); border-radius: 6px; padding: 10px 12px; font-family: var(--font-sans); font-size: 16px; }
  .kit-mirror .ex-input::placeholder { color: var(--color-foreground-tertiary); }
  .kit-mirror .ex-input:focus { outline: 0; border-color: var(--color-primary); }
  .kit-mirror button.ex-primary { background: var(--color-primary); color: var(--color-primary-foreground); border: none; border-radius: 6px; padding: 10px 22px; font-family: var(--font-sans); font-size: 16px; font-weight: 600; cursor: pointer; height: 44px; display: inline-flex; align-items: center; justify-content: center; line-height: 1; }
  .kit-mirror button.ex-outlined { background: var(--color-canvas); color: var(--color-foreground); border: 1px solid var(--color-border); border-radius: 6px; padding: 10px 22px; font-family: var(--font-sans); font-size: 16px; font-weight: 600; cursor: pointer; height: 44px; display: inline-flex; align-items: center; justify-content: center; line-height: 1; }
  .kit-mirror button.ex-textlink { background: transparent; color: var(--color-foreground-muted); border: none; font-family: var(--font-sans); font-size: 15px; cursor: pointer; padding: 0; }
  .kit-mirror .ex-frame { border: 1px solid var(--color-border); border-radius: 6px; padding: 24px; background: var(--color-canvas-soft); }
  .kit-mirror .ex-frame.short { position: relative; min-height: 240px; }
  .kit-mirror .ex-scrim { position: absolute; inset: 0; background: rgba(0,0,0,0.38); z-index: 1; }
  .kit-mirror .ex-modal-card { position: relative; z-index: 2; background: var(--color-canvas); border: 1px solid var(--color-border); border-radius: 8px; max-width: 500px; width: 100%; box-shadow: var(--shadow-lg); }
  .kit-mirror .ex-emptystate { display: flex; flex-direction: column; align-items: center; text-align: center; padding: 64px 24px; }
  .kit-mirror .ex-grid-cards-three { display: grid; grid-template-columns: repeat(auto-fill, minmax(260px, 1fr)); gap: 24px; }
  .kit-mirror .ex-card-pricing { padding: 32px; background: var(--color-canvas); border: 1px solid var(--color-border); border-radius: 6px; }
  .kit-mirror .ex-card-pricing-featured { background: var(--color-primary); color: var(--color-primary-foreground); border-color: var(--color-primary); }
  .kit-mirror .ex-card-pricing-featured .ex-card-tier, .kit-mirror .ex-card-pricing-featured .ex-card-price { color: var(--color-primary-foreground); }
  .kit-mirror .ex-card-pricing-featured .ex-card-list li { color: var(--color-primary-foreground); opacity: 0.88; }
  .kit-mirror .ex-card-pricing-featured .ex-card-list li::before { color: var(--color-primary-foreground); }
  .kit-mirror .ex-card-tier { font-family: var(--font-display); font-size: 24px; font-weight: 700; margin: 0 0 8px; color: var(--color-foreground); }
  .kit-mirror .ex-card-price { font-family: var(--font-display); font-size: 50px; font-weight: 700; line-height: 1.12; margin: 8px 0 16px; color: var(--color-foreground); }
  .kit-mirror .ex-card-list { list-style: none; padding: 0; margin: 0 0 24px; font-size: 14px; line-height: 1.8; color: var(--color-foreground-muted); }
  .kit-mirror .ex-card-list li::before { content: "✓ "; color: var(--color-success); font-weight: 700; }
  .kit-mirror .ex-card-product { padding: 16px; border: 1px solid var(--color-border); border-radius: 6px; background: var(--color-canvas); display: flex; flex-direction: column; gap: 8px; }
  .kit-mirror .ex-card-product strong { color: var(--color-foreground); }
  .kit-mirror .ex-card-product span { color: var(--color-foreground-muted); font-size: 13px; }
  .kit-mirror .ex-card-thumb { height: 100px; background: var(--color-canvas-soft); border-radius: 4px; margin-bottom: 4px; }
  .kit-mirror .ex-grid-toasts { display: grid; grid-template-columns: repeat(auto-fill, minmax(360px, 1fr)); gap: 16px; }
  .kit-mirror .ex-toast { display: grid; grid-template-columns: 4px 1fr auto; border: 1px solid var(--color-border); border-radius: 6px; overflow: hidden; background: var(--color-canvas); }
  .kit-mirror .footer-ex { padding: 32px 48px; border-top: 1px solid var(--color-border); text-align: center; font-size: 14px; color: var(--color-foreground-muted); }
  @media (max-width: 720px) {
    .kit-mirror .ex-section .container { padding: 0 20px; }
    .kit-mirror .ex-grid-cards-three, .kit-mirror .ex-grid-toasts { grid-template-columns: 1fr; }
    .kit-mirror .ex-h2 { font-size: 28px; }
  }"""


def compact_value(value: Any, data: dict[str, Any] | None = None) -> str:
    if isinstance(value, dict):
        parts = []
        for key, child in value.items():
            normalized = token_value(child)
            if normalized:
                if data:
                    normalized = resolve_refs(normalized, data)
                parts.append(f"{key}: {normalized}")
            elif isinstance(child, dict):
                nested = compact_value(child, data)
                if nested:
                    parts.append(f"{key}: {nested}")
        return "; ".join(parts)
    if isinstance(value, list):
        rendered = []
        for item in value:
            item_value = compact_value(item, data)
            if item_value:
                rendered.append(item_value)
        return ", ".join(rendered)
    if isinstance(value, bool):
        return str(value).lower()
    normalized = token_value(value)
    return resolve_refs(normalized, data) if normalized and data else normalized


def dark_strategy(data: dict[str, Any], sections: dict[str, str], dark: bool) -> str:
    if not dark:
        runtime_theme = mapping(mapping(data, "runtime"), "theme")
        theme_mode = str(
            runtime_theme.get("mode", "")
            or runtime_theme.get("themeMode", "")
            or runtime_theme.get("name", "")
        ).strip().lower()
        if theme_mode == "dark-only" or is_single_dark_theme(data):
            return "Default Dark Theme"
        if theme_mode == "light-only":
            return "Default Light Theme"
        return "Default Preview"
    return resolve_dark_evidence(data, sections)["strategy"]


def css_token_vars(namespace: str, group: dict[str, Any]) -> list[str]:
    lines = []
    for key, value in group.items():
        normalized = token_value(value)
        if namespace in {"radius", "space"}:
            normalized = css_scalar(normalized, css_key="width")
        if normalized and is_safe_custom_property_value(normalized):
            lines.append(f"      {css_var_name(namespace, str(key))}: {normalized};")
    return lines


def root_vars(data: dict[str, Any], dark: bool) -> str:
    colors = mapping(data, "colors")
    typography = mapping(data, "typography")
    rounded = mapping(data, "rounded")
    spacing = mapping(data, "spacing")
    shadows = mapping(data, "shadows")

    if dark and is_single_dark_theme(data):
        page = resolve_color_nested(data, "canvas-dark", "canvas", "surface-canvas", fallback="#0C0C0C")
        surface = resolve_color_nested(data, "surface-card-dark", "surface-dark", "surface", "surface-1", fallback=page)
        elevated = resolve_color_nested(data, "surface-2-dark", "surface-elevated-dark", "surface-hover-dark", "surface-2", fallback=surface)
        ink = resolve_color_nested(data, "ink-on-dark", "ink-dark", "text-primary-dark", fallback="#D7E2EA")
        muted = resolve_color_nested(data, "ink-muted-dark", "text-muted-dark", "ink-muted", fallback=ink)
        border = resolve_color_nested(data, "hairline-on-dark", "border-dark", "hairline-dark", "hairline", fallback="rgba(215,226,234,0.35)")
        primary = resolve_color_nested(data, "primary", "ink-on-dark", "brand", "accent", fallback=ink)
    elif dark:
        page = resolve_color_nested(data, "canvas-dark", "surface-canvas-dark", "background-dark", fallback="#090b10")
        surface = resolve_color_nested(data, "surface-card-dark", "surface-dark", "surface-1-dark", fallback="#11151d")
        elevated = resolve_color_nested(data, "surface-2-dark", "surface-elevated-dark", "surface-hover-dark", fallback="#171d28")
        ink = resolve_color_nested(data, "ink-dark", "text-primary-dark", "text-on-dark", fallback="#D7E2EA")
        muted = resolve_color_nested(data, "ink-muted-dark", "text-muted-dark", "text-secondary-dark", fallback="#9aa4b2")
        border = resolve_color_nested(data, "border-dark", "hairline-dark", "stroke-dark", fallback="rgba(255,255,255,0.12)")
        primary = resolve_color_nested(data, "primary-dark", "accent-dark", fallback="#8ab4ff")
    else:
        page = resolve_color_nested(data, "surface-canvas", "canvas", fallback="#ffffff")
        surface = resolve_color_nested(data, "surface-card", "surface-1", "surface", fallback="#f8fafc")
        elevated = resolve_color_nested(data, "surface-table-header", "surface-2", fallback=surface)
        ink = resolve_color_nested(data, "ink", "text-primary", "text", "textStrong", fallback="#111827")
        muted = resolve_color_nested(data, "ink-muted", "text-muted", "textMuted", fallback=ink)
        border = resolve_color_nested(data, "hairline", "border", fallback="#d7dee8")
        primary = resolve_color_nested(data, "primary", "brand", "accent", fallback=ink)

    body_type = first_typography(data, "body")
    font_sans = body_type.get("fontFamily", GENERIC_FONT_FALLBACK)
    danger_color = resolve_color_nested(
        data,
        "danger",
        "semantic-error",
        "semantic-danger",
        "error",
        fallback=primary,
    )
    radius = first_css_length(token(data, "rounded", "card", "lg", "md", fallback="12px"), "12px")
    control_radius = first_css_length(token(data, "rounded", "control", "md", "sm", fallback="8px"), "8px")
    gap = first_css_length(token(data, "spacing", "section-gap", "lg", "md", fallback="24px"), "24px")
    if "card" in shadows:
        shadow = token(data, "shadows", "card", fallback="none")
    elif "surface" in shadows or "panel" in shadows:
        shadow = token(data, "shadows", "surface", "panel", fallback="none")
    elif "none" in shadows:
        shadow = token(data, "shadows", "none", fallback="none")
    else:
        shadow = "0 18px 40px rgba(15, 23, 42, 0.08)"

    pairs = {
        "preview-generated-from": '"design-md"',
        "bg-page": page,
        "bg-surface": surface,
        "bg-elevated": elevated,
        "text-primary": ink,
        "text-muted": muted,
        "brand": primary,
        "color-danger": danger_color,
        "border": border,
        "radius-card": radius,
        "radius-control": control_radius,
        "gap": gap,
        "shadow-card": shadow if not dark else ("0 22px 60px rgba(0, 0, 0, 0.42)" if shadow != "none" else "none"),
        "font-sans": str(font_sans),
        "font-mono": "ui-monospace, SFMono-Regular, Menlo, Consolas, monospace",
    }

    lines = [f"      --{key}: {value};" for key, value in pairs.items()]

    # ── Shell spec tokens ──
    # validate_design_folder.py looks for these CSS custom properties to confirm
    # the preview reflects layout.appShell.* values from DESIGN.md. They are
    # also consumed by the enterprise specimen block. Exposing them at :root
    # makes the contract work for non-enterprise archetypes (content-resource-
    # portal, brand-portfolio, marketing, mobile, …) too.
    for key, value in _shell_spec_vars(data, dark).items():
        if value:
            lines.append(f"      --{key}: {value};")

    # 暗色模式跳过亮色颜色 token，避免污染暗色页面框架。
    # spacing、radius、shadow 和 typography token 与模式无关。
    if not dark:
        lines.extend(css_token_vars("color", colors))
    lines.extend(css_token_vars("radius", rounded))
    lines.extend(css_token_vars("space", spacing))
    lines.extend(css_token_vars("shadow", shadows))
    for key, value in typography.items():
        if isinstance(value, dict):
            for nested_key, nested_value in value.items():
                resolved = responsive_token_value(
                    nested_value,
                    css_key={
                        "fontSize": "font-size",
                        "fontFamily": "font-family",
                        "fontWeight": "font-weight",
                        "lineHeight": "line-height",
                        "letterSpacing": "letter-spacing",
                    }.get(str(nested_key), ""),
                )
                resolved = resolve_refs(resolved, data)
                if not is_safe_custom_property_value(resolved):
                    continue
                if dark and nested_key == "color":
                    resolved = _invert_text_color_for_dark(resolved)
                lines.append(f"      {css_var_name('type', f'{key}-{nested_key}')}: {resolved};")
    # 注意：kit-mirror alias tokens（--color-primary、--color-foreground 等）
    # 不注入 :root，否则会覆盖非 kit 内容的品牌 token。
    # 它们只存在于 .kit-mirror 作用域中（见 render()）。
    return "\n".join(lines)


def portfolio_button_spec_section(data: dict[str, Any], lang: str) -> str:
    ink = resolve_color_nested(data, "ink-on-dark", "ink", "primary", fallback="#D7E2EA")
    cta_a = resolve_color_nested(data, "cta-gradient-start", fallback="#18011F")
    cta_b = resolve_color_nested(data, "cta-gradient-mid-1", fallback="#B600A8")
    cta_c = resolve_color_nested(data, "cta-gradient-mid-2", fallback="#7621B0")
    cta_d = resolve_color_nested(data, "cta-gradient-end", fallback="#BE4C00")
    description = (
        "ContactButton 使用紫红到橙色渐变、白色内描边和胶囊轮廓；LiveProjectButton 是透明幽灵按钮，仅用于项目卡片操作。"
        if lang == "zh"
        else "ContactButton uses the documented purple-magenta-orange gradient, white inset outline, and pill shape; LiveProjectButton is a transparent ghost button for project cards only."
    )
    return f"""
    <div class="component-demo">
      <div class="button-row">
        <button style="border:0;border-radius:9999px;padding:14px 42px;color:#fff;font-weight:500;text-transform:uppercase;letter-spacing:.12em;background:linear-gradient(123deg,{cta_a} 7%,{cta_b} 37%,{cta_c} 72%,{cta_d} 100%);box-shadow:0 4px 4px rgba(181,1,167,.25), inset 4px 4px 12px #7721B1;outline:2px solid #fff;outline-offset:-3px;">Contact Me</button>
        <button style="border:2px solid {ink};border-radius:9999px;background:transparent;color:{ink};padding:12px 28px;text-transform:uppercase;letter-spacing:.12em;font-weight:500;">Live Project</button>
      </div>
      <p class="muted" style="margin-top:14px;">{description}</p>
    </div>
    """


def portfolio_card_spec_section(data: dict[str, Any], lang: str) -> str:
    page = resolve_color_nested(data, "canvas-dark", "canvas", "surface-canvas", fallback="#0C0C0C")
    ink = resolve_color_nested(data, "ink-on-dark", "ink", "primary", fallback="#D7E2EA")
    copy = (
        "卡片头部保留编号、类别、项目名和 Live Project 操作；下方使用左列两张图、右列一张高图的组合。"
        if lang == "zh"
        else "The card header keeps the number, category, project name, and Live Project action; the media area uses two stacked images on the left and one tall image on the right."
    )
    return f"""
    <div class="component-demo">
      <article style="border:2px solid {ink};border-radius:clamp(40px,5vw,60px);background:{page};color:{ink};padding:clamp(16px,3vw,32px);">
        <div style="display:flex;align-items:center;justify-content:space-between;gap:20px;margin-bottom:20px;">
          <span style="font-size:clamp(3rem,10vw,140px);font-weight:900;line-height:.9;">01</span>
          <div style="min-width:0;flex:1;">
            <span style="display:block;text-transform:uppercase;letter-spacing:.12em;opacity:.72;">Client</span>
            <h3 style="font-size:clamp(1.4rem,4vw,3.8rem);line-height:1;text-transform:uppercase;margin:0;">Nextlevel Studio</h3>
          </div>
          <button style="border:2px solid {ink};border-radius:9999px;background:transparent;color:{ink};padding:12px 28px;text-transform:uppercase;letter-spacing:.12em;font-weight:500;">Live Project</button>
        </div>
        <div style="display:grid;grid-template-columns:1fr 1.4fr;gap:16px;">
          <div style="display:grid;gap:16px;">
            <div style="height:clamp(130px,16vw,230px);border-radius:clamp(32px,4vw,56px);background:linear-gradient(135deg,#1b1e24,#687383);"></div>
            <div style="height:clamp(160px,22vw,340px);border-radius:clamp(32px,4vw,56px);background:linear-gradient(135deg,#232733,#798493);"></div>
          </div>
          <div style="min-height:clamp(320px,38vw,560px);border-radius:clamp(32px,4vw,56px);background:linear-gradient(135deg,#191d24,#586270);"></div>
        </div>
      </article>
      <p class="muted" style="margin-top:14px;">{copy}</p>
    </div>
    """


def media_content_component_spec(data: dict[str, Any], lang: str, variant: str) -> str:
    z = lang == "zh"
    primary = token(data, "colors", "primary", "brand", fallback="#4370F5")
    surface = token(data, "colors", "surface", "surfaceCard", fallback="#FFFFFF")
    canvas = token(data, "colors", "canvas", "background", fallback="#F5F7FD")
    tag_bg = token(data, "colors", "tagBg", "borderLight", fallback="#F2F4F6")
    text = token(data, "colors", "text", "textStrong", fallback="rgba(0,0,0,.84)")
    muted = token(data, "colors", "textMuted", "textSubtle", fallback="rgba(0,0,0,.6)")

    templates = data.get("pageTemplates")
    items = templates if isinstance(templates, list) else list(templates.values()) if isinstance(templates, dict) else []
    sample: dict[str, Any] = {}
    for item in items:
        if isinstance(item, dict) and isinstance(item.get("sampleContent"), dict):
            sample = item["sampleContent"]
            break
    tabs = sample.get("tabs") if isinstance(sample.get("tabs"), list) else []
    if not tabs:
        tabs = ["推荐", "最新", "热门", "知识体系", "推荐作者", "热门问答"] if z else ["Recommended", "Latest", "Hot", "Topics", "Authors", "Q&A"]
    articles = sample.get("articles") if isinstance(sample.get("articles"), list) else []
    article = articles[0] if articles and isinstance(articles[0], dict) else {}
    quick_cards = sample.get("quickCards") if isinstance(sample.get("quickCards"), list) else []
    if not quick_cards:
        quick_cards = [
            {"title": "热门导航" if z else "Hot Links", "links": ["热门专题", "热门作者", "优选企服"] if z else ["Topics", "Authors", "Services"]},
            {"title": "百宝箱" if z else "Toolkit", "links": ["书单", "AI产品导航", "行业快讯"] if z else ["Books", "AI Tools", "News"]},
        ]

    if variant == "tabs":
        tabs_html = "".join(
            f'<span style="position:relative;padding:0 14px;line-height:50px;font-size:16px;color:{text if index == 0 else muted};">{html.escape(str(tab))}<i style="position:absolute;left:0;right:0;top:0;height:{3 if index == 0 else 0}px;background:{primary};"></i></span>'
            for index, tab in enumerate(tabs[:6])
        )
        return f"""
    <div class="component-demo" style="background:{canvas};padding:16px;">
      <div style="height:60px;background:{surface};display:flex;align-items:center;justify-content:space-between;padding:0 24px;border-bottom:1px solid var(--border);">
        <strong style="font-size:16px;color:{text};">{html.escape(str(data.get('name') or ('内容门户' if z else 'Content Portal')))}</strong>
        <span style="padding:6px 14px;border-radius:4px;background:{primary};color:#fff;font-size:14px;">{'发布' if z else 'Publish'}</span>
      </div>
      <nav style="margin-top:12px;display:flex;align-items:stretch;background:{surface};border-radius:10px;box-shadow:0 1px 1px rgba(0,0,0,.05);overflow:hidden;">{tabs_html}</nav>
    </div>"""

    if variant == "article":
        tags = article.get("tags") if isinstance(article.get("tags"), list) else []
        tags_html = "".join(f'<span style="font-size:12px;padding:1px 8px;background:{tag_bg};border-radius:4px;color:{muted};">{html.escape(str(tag))}</span>' for tag in tags[:4])
        image = str(article.get("image") or "").strip()
        image_style = f"background:#eef0f4 center/cover no-repeat url({html.escape(image)});" if image else "background:#eef0f4;"
        return f"""
    <div class="component-demo" style="background:{canvas};padding:16px;">
      <article style="display:grid;grid-template-columns:236px 1fr;gap:15px;padding:15px;background:{surface};border-radius:10px;box-shadow:0 1px 1px rgba(0,0,0,.05);">
        <div style="width:236px;height:143px;border-radius:5px;position:relative;{image_style}">
          <span style="position:absolute;left:10px;top:10px;padding:2px 8px;border-radius:5px;background:rgba(0,0,0,.55);color:#fff;font-size:12px;">{html.escape(str(article.get('category') or ('公开课' if z else 'Course')))}</span>
        </div>
        <div style="display:grid;gap:8px;align-content:start;">
          <h4 style="margin:0;font-size:20px;line-height:1.4;font-weight:400;color:{text};">{html.escape(str(article.get('title') or ('内容标题占位' if z else 'Content title placeholder')))}</h4>
          <p style="margin:0;font-size:14px;line-height:1.8;color:{muted};">{html.escape(str(article.get('excerpt') or ('摘要最多两行，辅助用户扫读内容价值。' if z else 'Excerpt supports quick scanning of content value.')))}</p>
          <div style="display:flex;gap:8px;flex-wrap:wrap;">{tags_html}</div>
          <div style="font-size:12px;color:{muted};">{html.escape(str(article.get('author') or ('作者占位' if z else 'Author placeholder')))}</div>
        </div>
      </article>
    </div>"""

    cards = []
    for card in quick_cards[:3]:
        if not isinstance(card, dict):
            continue
        links = card.get("links") if isinstance(card.get("links"), list) else []
        chips = "".join(f'<span style="font-size:12px;padding:2px 8px;background:color-mix(in srgb,{primary} 10%,#fff);border-radius:4px;color:{primary};">{html.escape(str(link))}</span>' for link in links[:5])
        cards.append(f'<article style="background:{surface};border:1px solid var(--border);border-radius:10px;padding:14px;box-shadow:0 1px 1px rgba(0,0,0,.05);"><strong style="font-size:14px;color:{text};">{html.escape(str(card.get("title") or ""))}</strong><div style="display:flex;gap:6px;flex-wrap:wrap;margin-top:10px;">{chips}</div></article>')
    return f"""
    <div class="component-demo" style="background:{canvas};padding:16px;display:grid;grid-template-columns:1fr 335px;gap:20px;">
      <div style="display:grid;grid-template-columns:repeat(2,minmax(0,1fr));gap:12px;">{''.join(cards)}</div>
      <aside style="background:{surface};border-radius:10px;padding:14px;box-shadow:0 1px 1px rgba(0,0,0,.05);display:grid;gap:10px;">
        <strong style="font-size:13px;color:{text};">{'右侧推荐' if z else 'Right Rail'}</strong>
        <div style="height:56px;background:{tag_bg};border-radius:5px;"></div>
        <div style="height:56px;background:{tag_bg};border-radius:5px;"></div>
      </aside>
    </div>"""


def component_specs_html(data: dict[str, Any], labels: dict[str, str], lang: str, archetype: str) -> str:
    """Render component preview sections without inventing irrelevant component families."""
    intro = f"""
    <!-- ============ Section 3: Component Examples / Specifications ============ -->
    <section id="component-specs" style="padding:0;border:none;background:transparent;box-shadow:none;">
      <div style="border:1px solid var(--border);border-radius:var(--radius-card);background:var(--bg-surface);padding:clamp(20px,4vw,32px);">
        <div class="section-head">
          <div>
            <h2>{labels['component_specs']}</h2>
            <p>{labels['component_specs_copy']}</p>
          </div>
        </div>
      </div>
    </section>
    """
    if archetype == "brand-portfolio":
        note = (
            "仅展示输入规范中明确出现的作品集组件，避免把后台表单、表格、分页、弹窗等通用组件误写入该设计系统。"
            if lang == "zh"
            else "Only documented portfolio components are rendered here; generic admin form, table, pagination, and dialog families are omitted."
        )
        card_note = (
            "项目卡片沿用圆角、描边、三图布局和暗色背景规则。"
            if lang == "zh"
            else "Project cards preserve the documented radius, outline, three-image layout, and dark surface rules."
        )
        return (
            intro
            + f"""
    <!-- 3.1 Documented Calls To Action -->
    <section id="buttons">
      <div class="section-head"><div><h3 style="margin:0;">ContactButton / LiveProjectButton</h3><p>{note}</p></div></div>
      {portfolio_button_spec_section(data, lang)}
    </section>

    <!-- 3.2 Documented Project Cards -->
    <section id="cards">
      <div class="section-head"><div><h3 style="margin:0;">Project Cards</h3><p>{card_note}</p></div></div>
      {portfolio_card_spec_section(data, lang)}
    </section>
    """
        )
    if archetype in {"media-content", "content-resource-portal"}:
        note = (
            "仅展示内容门户中实际需要的组件，避免把后台表格、抽屉、开关等通用管理组件误写入该设计系统。"
            if lang == "zh"
            else "Only content-portal components are shown here; generic admin tables, drawers, and switches are omitted."
        )
        return (
            intro
            + f"""
    <!-- 3.1 Content Navigation -->
    <section id="buttons">
      <span id="tabs" class="toc-anchor"></span>
      <div class="section-head"><div><h3 style="margin:0;">{'频道 Tab / 顶部导航' if lang == 'zh' else 'Channel Tabs / Top Navigation'}</h3><p>{note}</p></div></div>
      {media_content_component_spec(data, lang, "tabs")}
    </section>

    <!-- 3.2 Article Cards -->
    <section id="cards">
      <div class="section-head"><div><h3 style="margin:0;">{'文章卡片 / 信息流' if lang == 'zh' else 'Article Cards / Feed'}</h3><p>{'横向图文卡片、分类角标、作者元信息和标签是核心组件。' if lang == 'zh' else 'Horizontal image-text cards, category badges, author metadata, and tags are the core components.'}</p></div></div>
      {media_content_component_spec(data, lang, "article")}
    </section>

    <!-- 3.3 Quick Entry and Right Rail -->
    <section id="right-rail">
      <div class="section-head"><div><h3 style="margin:0;">{'快捷入口 / 右侧挂件' if lang == 'zh' else 'Quick Entry / Right Rail'}</h3><p>{'用于热门导航、百宝箱、推荐文章和运营位。' if lang == 'zh' else 'Used for quick links, toolkits, recommended posts, and promo slots.'}</p></div></div>
      {media_content_component_spec(data, lang, "rail")}
    </section>
    """
        )
    return (
        intro
        + f"""
    <!-- 3.1 Buttons -->
    <section id="buttons">
      <div class="section-head"><div><h3 style="margin:0;">{labels['buttons']}</h3><p>{labels['buttons_copy']}</p></div></div>
      {button_spec_section(data, lang)}
    </section>

    <!-- 3.2 Data Entry -->
    <section id="inputs">
      <div class="section-head"><div><h3 style="margin:0;">{labels['inputs']}</h3><p>{labels['inputs_copy']}</p></div></div>
      {input_spec_section(data, lang)}
    </section>

    <!-- 3.3 Data Display -->
    <section id="data-display">
      <div class="section-head"><div><h3 style="margin:0;">{labels['data_display']}</h3><p>{labels['data_display_copy']}</p></div></div>
      {data_display_spec(data, lang)}
    </section>

    <!-- 3.4 Tags -->
    <section id="tags">
      <div class="section-head"><div><h3 style="margin:0;">{labels['tags']}</h3><p>{labels['tags_copy']}</p></div></div>
      {tag_spec_section(data, lang)}
    </section>

    <!-- 3.5 Pagination -->
    <section id="pagination">
      <div class="section-head"><div><h3 style="margin:0;">{labels['pagination']}</h3><p>{labels['pagination_copy']}</p></div></div>
      {pagination_spec(data, lang)}
    </section>

    <!-- 3.6 Tabs -->
    <section id="tabs">
      <div class="section-head"><div><h3 style="margin:0;">{labels['tabs']}</h3><p>{labels['tabs_copy']}</p></div></div>
      {tabs_spec(data, lang)}
    </section>

    <!-- 3.7 Dialogs / Drawers -->
    <section id="dialogs">
      <div class="section-head"><div><h3 style="margin:0;">{labels['dialogs']}</h3><p>{labels['dialogs_copy']}</p></div></div>
      {dialog_spec(data, lang)}
    </section>

    <!-- 3.8 Cards -->
    <section id="cards">
      <div class="section-head"><div><h3 style="margin:0;">{labels['cards']}</h3><p>{labels['cards_copy']}</p></div></div>
      {card_spec_section(data, lang)}
    </section>
    """
    )


def render(data: dict[str, Any], sections: dict[str, str], dark: bool) -> str:
    lang = detect_language(data, " ".join(sections.values()))
    labels = LABELS[lang]
    name = html.escape(str(data.get("name", "Design System")))
    version = html.escape(str(data.get("version", "2.0")))
    description = html.escape(str(data.get("description", "Design.md 2.0 token catalog.")))
    strategy = dark_strategy(data, sections, dark)
    root = root_vars(data, dark)
    display_type = first_typography(data, "display") or first_typography(data, "heading")
    display_style = style_from_type(display_type)
    colors = mapping(data, "colors")
    typography = mapping(data, "typography")
    components = mapping(data, "components")
    patterns = mapping(data, "patterns")
    page_patterns = mapping(data, "pagePatterns")
    component_mappings = mapping(data, "componentMappings")
    evidence = mapping(data, "evidence")
    runtime = mapping(data, "runtime")
    pattern_count = len(patterns) + len(page_patterns)
    runtime_summary = compact_value(runtime.get("theme", runtime), data) or labels["runtime_missing"]
    dark_info = resolve_dark_evidence(data, sections)
    gap_notes = preview_gap_notes(data, sections, lang)
    section_schema = preview_section_schema(labels, data)
    top_nav = preview_top_nav(section_schema)
    toc = preview_sidebar_toc(section_schema)

    primary = resolve_color_nested(data, "primary", "brand", "accent", fallback="#2563eb")
    body_type = first_typography(data, "body")
    font_family_val = html.escape(str(body_type.get("fontFamily", "system-ui, sans-serif")))
    archetype = infer_archetype(data)

    return f"""<!DOCTYPE html>
<html lang="{'zh-CN' if lang == 'zh' else 'en'}" data-preview-source="design-md" data-dark-strategy="{html.escape(strategy)}">
<head>
  <meta charset="UTF-8" />
  <meta name="viewport" content="width=device-width, initial-scale=1.0" />
  <title>{name} {'设计系统预览' if lang == 'zh' else 'Design System Preview'}</title>
  <style>
    :root {{
{root}
    }}
    * {{ box-sizing: border-box; }}
    html {{ scroll-behavior: smooth; }}
    section[id], .toc-anchor {{ scroll-margin-top: 88px; }}
    body {{
      margin: 0;
      background: var(--bg-page);
      color: var(--text-primary);
      font: 16px/1.5 var(--font-sans);
    }}
    .top-nav {{ position: sticky; top: 0; z-index: 10; display: flex; align-items: center; justify-content: space-between; gap: 16px; padding: 12px 28px; background: var(--bg-page); border-bottom: 1px solid var(--border); backdrop-filter: blur(12px); }}
    .top-nav-title {{ font-family: var(--font-sans); font-weight: 700; font-size: 16px; color: var(--text-primary); text-decoration: none; }}
    .top-nav-links {{ display: flex; gap: 14px; flex-wrap: wrap; }}
    .top-nav-links a {{ font-size: 13px; color: var(--text-muted); text-decoration: none; font-weight: 500; }}
    .top-nav-links a:hover {{ color: var(--brand); }}
    .layout {{ display: grid; grid-template-columns: minmax(180px, 220px) minmax(0, 1fr); gap: 28px; max-width: 1440px; margin: 0 auto; padding: 28px 24px 80px; }}
    .toc {{ position: sticky; top: 24px; align-self: start; display: grid; gap: 12px; padding: 14px; border: 1px solid var(--border); border-radius: var(--radius-card); background: var(--bg-surface); }}
    .toc strong {{ display: block; margin-bottom: 8px; font-size: 14px; color: var(--text-primary); }}
    .toc-group {{ display: grid; gap: 6px; }}
    .toc-parent, .toc-child {{ color: var(--text-muted); text-decoration: none; border-radius: var(--radius-control); }}
    .toc-parent {{ padding: 4px 8px; color: var(--text-primary); font-size: 13px; font-weight: 600; background: color-mix(in srgb, var(--bg-elevated) 72%, transparent); }}
    .toc-children {{ display: grid; gap: 2px; padding-left: 10px; border-left: 1px solid var(--border); margin-left: 8px; }}
    .toc-child {{ position: relative; padding: 3px 8px 3px 10px; font-size: 12px; line-height: 1.45; }}
    .toc-child::before {{ content: ""; position: absolute; left: -11px; top: 50%; width: 8px; border-top: 1px solid var(--border); transform: translateY(-50%); }}
    .toc a:hover {{ color: var(--text-primary); background: var(--bg-elevated); }}
    .page {{ min-width: 0; }}
    section {{
      border: 1px solid var(--border);
      border-radius: var(--radius-card);
      background: var(--bg-surface);
      box-shadow: var(--shadow-card);
    }}
    section {{ margin-top: var(--gap); padding: clamp(20px, 4vw, 32px); }}
    h2 {{ margin: 0 0 4px; font-size: 22px; font-weight: 700; }}
    h3 {{ margin: 20px 0 12px; font-size: 17px; font-weight: 600; }}
    h4 {{ margin: 14px 0 8px; font-size: 14px; font-weight: 600; }}
    p {{ color: var(--text-muted); line-height: 1.6; margin: 6px 0 0; }}
    .section-head {{ margin-bottom: 18px; }}
    .section-head p {{ max-width: 760px; }}
    .section-note {{ margin: 0 0 14px; padding: 10px 12px; border: 1px solid var(--border); border-radius: var(--radius-control); background: var(--bg-elevated); color: var(--text-muted); font-size: 13px; }}
    .review-summary {{
      display: grid; grid-template-columns: repeat(auto-fit, minmax(140px, 1fr)); gap: 12px;
      padding: 14px; border: 1px solid var(--border); border-radius: var(--radius-card);
      background: linear-gradient(135deg, color-mix(in srgb, var(--brand) 9%, var(--bg-surface)), var(--bg-surface));
    }}
    .review-summary div {{ display: grid; gap: 4px; }}
    .review-summary span {{ color: var(--text-muted); font-size: 12px; }}
    .review-summary strong {{ color: var(--text-primary); font-size: 18px; line-height: 1.2; }}
    .grid {{ display: grid; gap: 14px; }}
    .colors {{ grid-template-columns: repeat(auto-fit, minmax(200px, 1fr)); }}
    .components {{ grid-template-columns: repeat(auto-fit, minmax(240px, 1fr)); }}
    .comp-grid {{ display: grid; grid-template-columns: repeat(auto-fit, minmax(300px, 1fr)); gap: 16px; }}
    .swatch, .component-card, .type-row, .scale-row, .surface-card {{
      border: 1px solid var(--border);
      border-radius: var(--radius-card);
      background: var(--bg-elevated);
      overflow: hidden;
    }}
    .swatch-color {{ height: 72px; }}
    .swatch-body, .component-card, .type-row, .scale-row, .surface-card {{ padding: 14px; }}
    .swatch-body strong {{ display: block; font-size: 13px; }}
    .swatch-body span {{ display: block; margin-top: 3px; color: var(--text-muted); font-size: 12px; }}
    .swatch-body .usage {{ color: var(--text-muted); font-size: 11px; margin-top: 6px; font-style: italic; }}
    code {{ color: var(--text-muted); font-family: var(--font-mono); font-size: 12px; }}
    .muted {{ color: var(--text-muted); }}
    .type-showcase {{ display: grid; grid-template-columns: minmax(0, 1.15fr) minmax(320px, .85fr); gap: 16px; margin-bottom: 16px; }}
    .type-ladder, .type-context-demo {{ padding: 16px; display: grid; gap: 14px; }}
    .type-card-title {{ display: grid; gap: 4px; }}
    .type-card-title strong {{ font-size: 14px; color: var(--text-primary); }}
    .type-card-title span {{ font-size: 12px; color: var(--text-muted); }}
    .type-ladder-list {{ display: grid; gap: 10px; }}
    .type-ladder-row {{
      display: grid; grid-template-columns: minmax(124px, 156px) minmax(0, 1fr) auto;
      gap: 12px; align-items: center; padding: 10px 12px; border: 1px solid var(--border);
      border-radius: var(--radius-control); background: var(--bg-surface);
    }}
    .type-ladder-row > span {{ color: var(--text-muted); font-size: 12px; }}
    .type-ladder-row > strong {{ min-width: 0; color: var(--text-primary); }}
    .type-context-shell {{ border: 1px solid var(--border); border-radius: var(--radius-card); background: var(--bg-surface); overflow: hidden; }}
    .type-context-head {{
      display: flex; align-items: center; justify-content: space-between; gap: 12px;
      padding: 14px 16px; border-bottom: 1px solid var(--border); background: var(--bg-elevated);
    }}
    .type-context-head strong {{ color: var(--text-primary); font-size: 16px; font-weight: 600; line-height: 1.5; }}
    .type-context-head button {{
      height: 32px; padding: 0 14px; border: none; border-radius: var(--radius-control);
      background: var(--brand); color: #fff; font: 500 14px/1.2 var(--font-sans);
    }}
    .type-context-panel {{ display: grid; gap: 8px; padding: 16px; }}
    .type-context-panel strong {{ color: var(--text-primary); font-size: 16px; font-weight: 600; line-height: 1.5; }}
    .type-context-panel p {{ margin: 0; color: var(--text-primary); font-size: 14px; line-height: 1.5; }}
    .type-context-panel span {{ color: var(--text-muted); font-size: 12px; line-height: 1.4; }}
    .type-semantic-note {{
      margin-bottom: 16px; display: flex; flex-wrap: wrap; gap: 10px; align-items: center;
      padding: 12px 14px; border: 1px solid var(--border); border-radius: var(--radius-card);
      background: color-mix(in srgb, var(--brand) 6%, var(--bg-surface));
    }}
    .type-semantic-note strong {{ font-size: 13px; color: var(--text-primary); }}
    .type-semantic-note span {{ color: var(--text-muted); font-size: 13px; }}
    .type-matrix {{ border: 1px solid var(--border); border-radius: var(--radius-card); overflow: hidden; background: var(--bg-surface); }}
    .type-matrix-head, .type-matrix-row {{
      display: grid; grid-template-columns: 132px 92px minmax(180px, 1fr) 170px minmax(180px, 1fr);
      gap: 14px; align-items: center; padding: 12px 14px;
    }}
    .type-matrix-head {{ background: var(--bg-elevated); border-bottom: 1px solid var(--border); }}
    .type-matrix-head strong {{ font-size: 12px; color: var(--text-muted); font-weight: 600; }}
    .type-matrix-row {{ border-bottom: 1px solid var(--border); }}
    .type-matrix-row:last-child {{ border-bottom: 0; }}
    .type-matrix-row > strong {{ font-size: 13px; color: var(--text-primary); }}
    .type-matrix-row > span:last-child {{ color: var(--text-muted); font-size: 12px; }}
    .type-group-chip {{
      display: inline-flex; align-items: center; justify-content: center; width: fit-content;
      min-height: 22px; padding: 0 8px; border: 1px solid var(--border); border-radius: 999px;
      background: var(--bg-elevated); color: var(--text-muted); font-size: 12px;
    }}
    .type-sample-cell {{ color: var(--text-primary); min-width: 0; }}
    .scale-gallery, .radius-gallery, .elevation-gallery {{
      display: grid; grid-template-columns: repeat(auto-fit, minmax(220px, 1fr)); gap: 14px;
    }}
    .scale-card, .radius-card-demo, .elevation-card-demo {{
      border: 1px solid var(--border); border-radius: var(--radius-card); background: var(--bg-elevated);
      padding: 14px; display: grid; gap: 10px;
    }}
    .scale-meta {{ display: flex; align-items: baseline; justify-content: space-between; gap: 10px; }}
    .scale-meta strong {{ font-size: 14px; color: var(--text-primary); }}
    .scale-visual {{ min-height: 32px; display: flex; align-items: center; padding: 0 10px; border-radius: var(--radius-control); background: var(--bg-page); border: 1px dashed var(--border); overflow: hidden; }}
    #spacing .scale-visual.spacing-true-scale {{
      min-height: 40px; overflow: visible; justify-content: flex-start; padding: 8px 12px;
    }}
    .spacing-gap-demo {{ display: flex; align-items: center; flex-shrink: 0; }}
    .spacing-block {{
      width: 20px; height: 20px; flex-shrink: 0; border-radius: 3px;
      background: color-mix(in srgb, var(--brand) 72%, var(--bg-elevated));
      border: 1px solid color-mix(in srgb, var(--brand) 40%, var(--border));
    }}
    .spacing-gap {{
      flex-shrink: 0; height: 20px; min-width: 0; box-sizing: border-box;
      background: repeating-linear-gradient(
        90deg,
        color-mix(in srgb, var(--brand) 35%, transparent) 0 1px,
        transparent 1px 4px
      );
      border-top: 1px dashed color-mix(in srgb, var(--brand) 55%, var(--border));
      border-bottom: 1px dashed color-mix(in srgb, var(--brand) 55%, var(--border));
    }}
    .measure-rich {{ display: inline-block; height: 14px; min-width: 4px; border-radius: 999px; background: var(--brand); }}
    .measure-rich.text {{ width: 24px; background: transparent; color: var(--text-muted); }}
    .usage-strip {{
      margin-top: 14px; padding: 14px; border: 1px solid var(--border); border-radius: var(--radius-card);
      background: var(--bg-elevated); display: grid; gap: 10px;
    }}
    .usage-strip strong {{ font-size: 13px; color: var(--text-primary); }}
    .usage-strip > div {{ display: flex; flex-wrap: wrap; gap: 8px; }}
    .mini-pill {{
      display: inline-flex; align-items: center; min-height: 24px; padding: 0 10px;
      border: 1px solid var(--border); border-radius: 999px; background: var(--bg-surface);
      color: var(--text-muted); font-size: 12px;
    }}
    .radius-shape {{
      width: 100%; min-height: 68px; background: color-mix(in srgb, var(--brand) 16%, var(--bg-page));
      border: 1px solid color-mix(in srgb, var(--brand) 30%, var(--border));
    }}
    .floating-surface {{
      width: 100%; min-height: 68px; border-radius: var(--radius-control);
      background: var(--bg-surface); border: 1px solid var(--border);
    }}
    .tag-row {{ display: flex; gap: 8px; flex-wrap: wrap; margin-top: 10px; }}
    .chip {{
      display: inline-flex; align-items: center; min-height: 26px; padding: 0 10px;
      border: 1px solid var(--border); border-radius: var(--radius-control);
      color: var(--text-muted); font-size: 12px;
    }}
    .chip-primary {{ color: var(--brand); border-color: color-mix(in srgb, var(--brand) 45%, transparent); background: color-mix(in srgb, var(--brand) 10%, transparent); }}
    .chip-success {{ color: #389e0d; border-color: rgba(56,158,13,.35); background: rgba(56,158,13,.06); }}
    .chip-warning {{ color: #d48806; border-color: rgba(212,136,6,.35); background: rgba(212,136,6,.06); }}
    .chip-danger {{ color: var(--color-danger, var(--brand)); border-color: color-mix(in srgb, var(--color-danger, var(--brand)) 35%, transparent); background: color-mix(in srgb, var(--color-danger, var(--brand)) 8%, transparent); }}
    .chip-info {{ color: #1677ff; border-color: rgba(22,119,255,.35); background: rgba(22,119,255,.06); }}
    .chip-disabled {{ opacity: .45; pointer-events: none; }}
    .sample-line {{ display: flex; flex-wrap: wrap; gap: 10px; margin-top: 10px; align-items: center; }}
    .sample-line .btn-label {{ font-size: 12px; color: var(--text-muted); min-width: 60px; }}
    .btn-sample {{
      display: inline-flex; align-items: center; justify-content: center;
      font: 600 13px/1 var(--font-sans); border-radius: var(--radius-control);
      cursor: default; white-space: nowrap;
    }}
    .btn-sample.sm {{ height: 28px; padding: 0 12px; font-size: 12px; }}
    .btn-sample.md {{ height: 32px; padding: 0 16px; font-size: 13px; }}
    .btn-sample.lg {{ height: 40px; padding: 0 20px; font-size: 15px; }}
    .btn-sample.primary {{ background: var(--brand); color: #fff; border: none; }}
    .btn-sample.default {{ background: var(--bg-page); color: var(--text-primary); border: 1px solid var(--border); }}
    .btn-sample.ghost {{ background: transparent; color: var(--brand); border: 1px solid var(--brand); }}
    .btn-sample.text {{ background: transparent; color: var(--brand); border: none; }}
    .btn-sample.danger {{ background: var(--color-danger, var(--brand)); color: #fff; border: none; }}
    .btn-sample.disabled {{ opacity: .45; }}
    .input-group {{ display: grid; gap: 8px; margin-top: 10px; }}
    .input-row {{ display: flex; flex-wrap: wrap; gap: 10px; align-items: center; }}
    .input-demo {{
      height: 32px; border: 1px solid var(--border); border-radius: var(--radius-control);
      padding: 0 11px; background: var(--bg-page); color: var(--text-primary);
      font: 13px var(--font-sans); min-width: 0; width: 180px;
    }}
    .input-demo:focus {{ outline: none; border-color: var(--brand); box-shadow: 0 0 0 2px color-mix(in srgb, var(--brand) 20%, transparent); }}
    .input-demo.error {{ border-color: var(--color-danger, var(--brand)); }}
    .input-demo:disabled {{ opacity: .45; background: var(--bg-elevated); }}
    .table-demo {{ margin-top: 10px; border: 1px solid var(--border); border-radius: var(--radius-control); overflow: hidden; font-size: 12px; }}
    .table-demo > div {{ display: grid; grid-template-columns: 1.2fr 0.8fr 0.6fr 0.8fr; gap: 8px; padding: 8px 10px; border-bottom: 1px solid var(--border); }}
    .table-demo > div:last-child {{ border-bottom: 0; }}
    .table-demo .header {{ background: var(--bg-surface); font-weight: 700; }}
    .table-demo .hover:hover {{ background: color-mix(in srgb, var(--brand) 5%, transparent); }}
    .demarcation {{ border: 1px dashed var(--border); background: var(--bg-page); border-radius: var(--radius-control); padding: 16px; margin-top: 10px; }}
    .layout-diagram {{ display: grid; margin-top: 10px; border: 1px solid var(--border); border-radius: var(--radius-control); overflow: hidden; font-size: 12px; text-align: center; }}
    .layout-diagram .region {{ padding: 14px 10px; }}
    .layout-diagram .header {{ background: var(--spec-topbar-bg, var(--bg-surface)); color: var(--text-primary); font-weight: 600; }}
    .layout-diagram .sider-content {{ display: grid; grid-template-columns: 0.25fr 0.75fr; }}
    .layout-diagram .sider {{ background: var(--spec-sidebar, var(--bg-surface)); color: var(--spec-sidebar-text, var(--text-muted)); padding: 28px 10px; }}
    .layout-diagram .content {{ background: var(--spec-canvas, var(--bg-surface)); padding: 28px 10px; color: var(--text-muted); }}
    .layout-diagram .tabs {{ background: color-mix(in srgb, var(--spec-primary, var(--brand)) 10%, transparent); color: var(--text-muted); border-top: 1px solid var(--border); }}
    .radius-box {{ display: inline-block; width: 52px; height: 32px; background: var(--brand); vertical-align: middle; }}
    .shadow-box {{ display: inline-block; width: 52px; height: 32px; background: var(--bg-surface); border: 1px solid var(--border); vertical-align: middle; }}
    .measure {{ display: inline-block; height: 12px; background: var(--brand); border-radius: 999px; min-width: 4px; }}
    .legend {{ display: flex; gap: 20px; flex-wrap: wrap; margin-bottom: 10px; }}
    .legend-item {{ display: flex; align-items: center; gap: 6px; font-size: 12px; color: var(--text-muted); }}
    .legend-box {{ width: 14px; height: 14px; border-radius: 3px; border: 1px solid var(--border); }}

    .specimen {{ margin: 14px 0; border: 1px solid var(--spec-border); border-radius: var(--radius-card); overflow: hidden; background: var(--spec-canvas); color: var(--spec-text); font-size: 13px; }}
    .spec-topbar {{ min-height: var(--spec-topbar); display: flex; align-items: center; gap: 20px; padding: 0 16px; background: var(--spec-topbar-bg, var(--spec-primary)); color: white; }}
    .spec-topbar span {{ color: rgba(255,255,255,.82); }}
    .spec-tags {{ display: flex; align-items: center; gap: 18px; min-height: var(--spec-tags); padding: 0 16px; border-bottom: 1px solid var(--spec-border); background: color-mix(in srgb, var(--spec-surface) 92%, white); color: var(--spec-muted); }}
    .spec-tags span {{ display: inline-flex; align-items: center; min-height: calc(var(--spec-tags) - 6px); }}
    .spec-tags .active {{ color: var(--spec-primary); border-bottom: 2px solid var(--spec-primary); }}
    .spec-app-body {{ display: grid; grid-template-columns: var(--spec-sidebar-width) minmax(0, 1fr); min-height: 390px; background: var(--spec-canvas); }}
    .spec-sidebar-menu {{ display: grid; align-content: start; gap: 2px; padding: 8px 0; background: var(--spec-sidebar); color: var(--spec-sidebar-text, var(--spec-muted)); border-right: 1px solid var(--spec-border); box-shadow: inset -1px 0 0 rgba(0,0,0,.02); }}
    .spec-sidebar-menu span {{ display: flex; align-items: center; min-height: 46px; padding: 0 16px 0 22px; border-right: 4px solid transparent; }}
    .spec-sidebar-menu .active {{ color: var(--spec-primary); background: var(--spec-sidebar-active-bg, color-mix(in srgb, var(--spec-primary) 10%, transparent)); border-right-color: var(--spec-primary); font-weight: 600; }}
    .spec-workspace {{ min-width: 0; display: flex; flex-direction: column; }}
    .spec-body {{ display: grid; grid-template-columns: 72px minmax(156px, var(--spec-sidebar-width)) minmax(0, 1fr); min-height: 390px; }}
    .spec-rail {{ display: grid; align-content: start; gap: 4px; padding: 10px 0; background: var(--spec-sidebar); color: rgba(255,255,255,.72); }}
    .spec-rail span {{ display: grid; place-items: center; min-height: 52px; border-left: 3px solid transparent; }}
    .spec-rail .active {{ border-left-color: var(--spec-primary); color: #fff; background: rgba(0,0,0,.22); }}
    .spec-tree {{ display: grid; align-content: start; gap: 8px; padding: 16px 12px; background: var(--spec-surface); border-right: 1px solid var(--spec-border); color: var(--spec-muted); }}
    .spec-tree strong {{ color: var(--spec-text); margin-bottom: 4px; }}
    .spec-tree span {{ padding: 7px 8px; border-radius: 4px; }}
    .spec-tree .active {{ color: var(--spec-primary); background: color-mix(in srgb, var(--spec-primary) 10%, transparent); }}
    .spec-main {{ min-width: 0; padding: 12px; }}
    .spec-filter {{ display: flex; flex-wrap: wrap; align-items: center; gap: 10px; margin-bottom: 12px; padding: 12px; background: var(--spec-surface); border: 1px solid var(--spec-border); }}
    .spec-filter label {{ color: var(--spec-muted); font-size: 12px; }}
    .spec-filter input, .spec-filter select {{ width: 150px; min-width: 0; height: 30px; border: 1px solid var(--spec-border); border-radius: 4px; padding: 0 8px; }}
    .spec-table a {{ color: var(--spec-primary); text-decoration: none; font-weight: 600; }}
    .spec-filter button, .spec-title button {{ height: 30px; border: 1px solid var(--spec-border); border-radius: 4px; background: var(--spec-surface); color: var(--spec-text); padding: 0 10px; }}
    .spec-filter .primary, .spec-title .primary {{ background: var(--spec-primary); border-color: var(--spec-primary); color: white; }}
    .spec-panel {{ padding: 12px; background: var(--spec-surface); border: 1px solid var(--spec-border); }}
    .spec-title {{ display: flex; align-items: center; gap: 8px; margin-bottom: 10px; }}
    .spec-title strong {{ border-left: 3px solid var(--spec-primary); padding-left: 8px; }}
    .spec-title span {{ flex: 1; }}
    .spec-table {{ width: 100%; border-collapse: collapse; table-layout: fixed; }}
    .spec-table th, .spec-table td {{ padding: 9px 10px; border-bottom: 1px solid var(--spec-border); overflow: hidden; text-overflow: ellipsis; white-space: nowrap; }}
    .spec-table th {{ background: var(--spec-table-header-bg); color: var(--spec-table-header-color); text-align: left; }}
    .spec-table td:last-child {{ color: var(--spec-primary); font-weight: 600; }}
    .spec-table i {{ display: inline-block; width: 7px; height: 7px; margin-right: 6px; border-radius: 50%; background: #52c41a; }}
    .spec-pagination {{ display: flex; justify-content: flex-end; gap: 10px; padding-top: 12px; color: var(--spec-muted); }}
    .spec-pagination b {{ min-width: 24px; display: inline-grid; place-items: center; background: color-mix(in srgb, var(--spec-primary) 12%, transparent); color: var(--spec-primary); border-radius: 4px; }}
    .source-shell {{ display: grid; grid-template-columns: var(--spec-sidebar-width) minmax(0, 1fr); min-height: 520px; background: var(--spec-canvas); }}
    .source-sidebar {{ border-right: 0; box-shadow: 2px 0 8px rgba(29,35,41,.05); }}
    .source-logo {{ display: flex; align-items: center; min-height: var(--spec-topbar); padding: 0 18px 0 22px; color: var(--spec-text); box-shadow: 0 4px 2px -2px rgba(0,21,41,.08); font-weight: 600; }}
    .source-sidebar span {{ min-height: 40px; margin: 0 18px; padding: 0 16px 0 24px; border-right: 0; border-radius: 8px; }}
    .source-sidebar .active {{ border-right-color: transparent; font-weight: 400; }}
    .source-topbar {{ justify-content: flex-end; border-bottom: 0; box-shadow: 0 1px 4px rgba(0,21,41,.08); color: var(--spec-text); }}
    .source-topbar span {{ color: var(--spec-text); }}
    .source-main {{ padding: 20px 32px 24px; }}
    .source-split {{ display: grid; grid-template-columns: 274px minmax(0,1fr); gap: 16px; align-items: start; }}
    .source-tree, .source-content {{ min-width: 0; background: var(--spec-surface); border-radius: 12px; }}
    .source-tree {{ display: grid; align-content: start; gap: 8px; min-height: 390px; padding: 16px; color: var(--spec-text); border-right: 0; }}
    .source-tree span {{ min-height: 32px; display: flex; align-items: center; padding: 0 8px; border-radius: 4px; }}
    .source-tree .active {{ color: var(--spec-primary); background: color-mix(in srgb, var(--spec-primary) 10%, transparent); }}
    .source-search {{ height: 32px; display: flex; align-items: center; padding: 0 11px; border: 1px solid var(--spec-border); border-radius: 4px; color: var(--spec-muted); background: var(--spec-surface); }}
    .source-content {{ padding: 0; background: transparent; }}
    .source-toolbar {{ min-height: 32px; display: flex; flex-wrap: wrap; align-items: center; gap: 8px; margin-bottom: 16px; color: var(--spec-text); }}
    .source-toolbar strong {{ margin-right: auto; font-size: 16px; font-weight: 600; color: var(--spec-text); }}
    .source-toolbar input {{ height: 32px; width: 180px; border: 1px solid var(--spec-border); border-radius: 4px; padding: 0 11px; background: var(--spec-surface); color: var(--spec-text); }}
    .source-toolbar button {{ height: 32px; border: 1px solid var(--spec-border); border-radius: 4px; padding: 0 15px; background: var(--spec-surface); color: var(--spec-text); }}
    .source-toolbar .primary {{ border-color: var(--spec-primary); background: var(--spec-primary); color: #fff; }}
    .source-tabs {{ display: flex; gap: 32px; height: 45px; margin-bottom: 16px; border-bottom: 1px solid var(--spec-border); }}
    .source-tabs span {{ display: inline-flex; align-items: center; padding: 0 16px; color: var(--spec-muted); }}
    .source-tabs .active {{ color: var(--spec-primary); border-bottom: 2px solid var(--spec-primary); }}
    .source-card-grid {{ display: grid; grid-template-columns: repeat(auto-fit, minmax(220px, 1fr)); gap: 16px; }}
    .source-card {{ min-height: 180px; display: grid; align-content: start; gap: 10px; padding: 16px; border: 1px solid color-mix(in srgb, var(--spec-border) 75%, #fff); border-radius: 12px; background: var(--spec-surface); }}
    .source-card strong {{ color: var(--spec-text); font-size: 16px; }}
    .source-card p {{ margin: 0; color: var(--spec-muted); font-size: 13px; }}
    .source-card a, .spec-table a {{ color: var(--spec-primary); text-decoration: none; }}
    .usage-banner {{ padding: 10px 14px; border: 1px solid var(--border); border-radius: var(--radius-control); background: var(--bg-elevated); color: var(--text-muted); font-size: 12px; margin-top: var(--gap); text-align: center; }}
    .template-summary {{
      display: grid; grid-template-columns: repeat(auto-fit, minmax(220px, 1fr)); gap: 12px;
      margin-top: 14px; margin-bottom: 18px;
    }}
    .template-summary article {{
      border: 1px solid var(--border); border-radius: var(--radius-card); background: var(--bg-elevated);
      padding: 14px; display: grid; gap: 8px;
    }}
    .template-summary strong {{ font-size: 14px; color: var(--text-primary); }}
    .template-summary span {{ color: var(--text-muted); font-size: 12px; }}
    @media (max-width: 760px) {{
      .layout {{ grid-template-columns: 1fr; padding: 16px; }}
      .toc {{ position: static; }}
      .toc-parent {{ padding: 3px 6px; font-size: 12px; }}
      .toc-child {{ padding: 2px 6px 2px 8px; font-size: 11px; }}
      .type-showcase {{ grid-template-columns: 1fr; }}
      .type-ladder-row {{ grid-template-columns: 1fr; }}
      .type-matrix-head, .type-matrix-row {{ grid-template-columns: 1fr; gap: 8px; }}
      .type-matrix-head strong:not(:first-child) {{ display: none; }}
      .comp-grid {{ grid-template-columns: 1fr; }}
      .colors {{ grid-template-columns: repeat(auto-fit, minmax(140px, 1fr)); }}
      .spec-body {{ grid-template-columns: 1fr; }}
      .spec-rail, .spec-tree {{ display: none; }}
      .layout-diagram .sider-content {{ grid-template-columns: 1fr; }}
      .input-demo {{ width: 140px; }}
    }}
  </style>
</head>
<body>
  <header class="top-nav" id="top">
    <a class="top-nav-title" href="#top">{name}</a>
    <nav class="top-nav-links">
      {top_nav}
    </nav>
  </header>
  <div class="layout">
    <nav class="toc" aria-label="{labels['preview_aria']}">
      <strong>{labels['preview']}</strong>
      {toc}
    </nav>
  <main class="page">
    {f'<div class="section-note dark-strategy-note">{labels["inspection_note"]}</div>' if dark and strategy in {"Dark Strategy Unavailable", "Dark Inspection View"} else ''}

    <!-- ============ Section 1: Design Style Overview ============ -->
    <section id="style-overview">
      <div class="section-head">
        <div>
          <h2>{labels['style_overview']}</h2>
          <p>{labels['style_overview_copy']}</p>
        </div>
      </div>
      {style_overview_card(data, lang)}
    </section>

    <!-- ============ Section 2: Basic Design Tokens / UI Specs ============ -->
    <section id="ui-specs" style="padding:0;border:none;background:transparent;box-shadow:none;">
      <div style="border:1px solid var(--border);border-radius:var(--radius-card);background:var(--bg-surface);padding:clamp(20px,4vw,32px);">
        <div class="section-head">
          <div>
            <h2>{labels['ui_specs']}</h2>
            <p>{labels['ui_specs_copy']}</p>
          </div>
        </div>
      </div>
    </section>

    <!-- 2.1 Colors -->
    <section id="colors">
      <div class="section-head"><div><h3 style="margin:0;">{labels['color_roles']}</h3><p>{labels['color_copy']}</p></div></div>
      {grouped_swatches(colors)}
    </section>

    <!-- 2.2 Typography -->
    <section id="typography">
      <div class="section-head"><div><h3 style="margin:0;">{labels['type_scale']}</h3><p>{labels['type_copy']}</p></div></div>
      {typography_samples(data, lang)}
    </section>

    <!-- 2.3 Layout / Grid -->
    <section id="layout-grid">
      <div class="section-head"><div><h3 style="margin:0;">{labels['layout_grid']}</h3><p>{labels['layout_grid_copy']}</p></div></div>
      {layout_grid_spec(data, archetype, lang)}
    </section>

    <!-- 2.4 Icons -->
    <section id="icons">
      <div class="section-head"><div><h3 style="margin:0;">{labels['icons']}</h3><p>{labels['icons_copy']}</p></div></div>
      {icon_spec(data, sections, lang)}
    </section>

    <!-- 2.5 Spacing -->
    <section id="spacing">
      <div class="section-head"><div><h3 style="margin:0;">{labels['spacing']}</h3><p>{labels['spacing_copy']}</p></div></div>
      {spacing_spec(mapping(data, "spacing"), lang)}
    </section>

    <!-- 2.6 Radius -->
    <section id="radius">
      <div class="section-head"><div><h3 style="margin:0;">{labels['radius']}</h3><p>{labels['radius_copy']}</p></div></div>
      {radius_spec(mapping(data, "rounded"), lang)}
    </section>

    <!-- 2.7 Shadows -->
    <section id="elevation">
      <div class="section-head"><div><h3 style="margin:0;">{labels['elevation']}</h3><p>{labels['elevation_copy']}</p></div></div>
      {elevation_spec(mapping(data, "shadows"), lang)}
    </section>

    {component_specs_html(data, labels, lang, archetype)}

    <!-- ============ Section 4: Real Pages / Template Page Examples ============ -->
    <section id="template-pages" style="padding:0;border:none;background:transparent;box-shadow:none;">
      <div style="border:1px solid var(--border);border-radius:var(--radius-card);background:var(--bg-surface);padding:clamp(20px,4vw,32px);">
        <div class="section-head">
          <div>
            <h2>{labels['template_pages']}</h2>
            <p>{labels['template_pages_copy']}</p>
          </div>
        </div>
      </div>
    </section>
    {template_pages_section(data, sections, archetype, lang)}

    <!-- Lightweight usage note -->
    <div class="usage-banner">{labels['usage_note_copy']}</div>

  </main>
  </div>
</body>
</html>
"""


def resolve_primary_color(data: dict[str, Any]) -> str:
    """Resolve the brand primary color, walking nested color groups.

    DESIGN.md writers put colors either flat (colors.primary) or grouped
    (colors.primary-colors.primary.value). Try in order:
      1. colors.primary / brand / accent (flat)
      2. colors.*.primary.value (any nested group)
      3. recommendedTokens.colors[*].primary
      4. fallback
    """
    colors = mapping(data, "colors")
    for candidate in ("primary", "brand", "accent"):
        if candidate in colors:
            v = token_value(colors[candidate])
            if v:
                return v
    for _, group in colors.items():
        if isinstance(group, dict):
            for cand in ("primary", "brand", "accent"):
                if cand in group:
                    v = token_value(group[cand])
                    if v:
                        return v
    recommended = data.get("recommendedTokens", {})
    if isinstance(recommended, dict):
        rc = recommended.get("colors")
        if isinstance(rc, list):
            for item in rc:
                if isinstance(item, dict):
                    for k, v in item.items():
                        if "primary" in str(k).lower() or "brand" in str(k).lower():
                            sv = token_value(v)
                            if sv:
                                return sv
                    if "value" in item:
                        sv = token_value(item.get("value"))
                        if sv:
                            return sv
    return "#2563eb"


_DENSITY_ZH = {
    "compact": "紧凑密度",
    "comfortable": "标准密度",
    "spacious": "宽松密度",
    "dense": "紧凑密度",
}
_DENSITY_EN = {
    "compact": "Compact",
    "comfortable": "Comfortable",
    "spacious": "Spacious",
    "dense": "Compact / Dense",
}
_PRODUCT_TYPE_ZH = {
    "enterprise-admin": "企业级管理后台",
    "product-dashboard": "数据仪表盘",
    "marketing": "营销官网 / 落地页",
    "marketplace": "平台 / 市场",
    "consumer": "消费级应用",
    "editor-workbench": "编辑器 / 工作台",
    "documentation": "文档站点",
}
_PRODUCT_TYPE_EN = {
    "enterprise-admin": "Enterprise Admin",
    "product-dashboard": "Data Dashboard",
    "marketing": "Marketing / Landing",
    "marketplace": "Marketplace",
    "consumer": "Consumer App",
    "editor-workbench": "Editor / Workbench",
    "documentation": "Documentation Site",
}


def resolve_density_label(data: dict[str, Any], lang: str) -> str:
    raw = str(data.get("density", "")).strip().lower()
    table = _DENSITY_ZH if lang == "zh" else _DENSITY_EN
    if raw in table:
        return table[raw]
    spacing_data = mapping(data, "spacing")
    base_val = token_value(spacing_data.get("base") or spacing_data.get("md") or "")
    try:
        n = float(re.sub(r"[^0-9.]", "", base_val)) if base_val else 0
    except ValueError:
        n = 0
    if 0 < n <= 12:
        return _DENSITY_ZH["compact"] if lang == "zh" else _DENSITY_EN["compact"]
    return _DENSITY_ZH["comfortable"] if lang == "zh" else _DENSITY_EN["comfortable"]


def resolve_product_type_label(data: dict[str, Any], lang: str) -> str:
    raw = str(data.get("productType", "")).strip().lower()
    if raw:
        table = _PRODUCT_TYPE_ZH if lang == "zh" else _PRODUCT_TYPE_EN
        return table.get(raw, raw)
    archetype = infer_archetype(data)
    table = _PRODUCT_TYPE_ZH if lang == "zh" else _PRODUCT_TYPE_EN
    return table.get(archetype, archetype)


def resolve_component_system_label(data: dict[str, Any], lang: str) -> str:
    libs = data.get("componentLibraries")
    if isinstance(libs, list) and libs:
        cleaned = []
        for item in libs:
            if isinstance(item, dict):
                label = str(item.get("name") or item.get("library") or "").strip()
                version = str(item.get("version") or "").strip()
                if label and version:
                    label = f"{label} {version}"
            else:
                label = str(item).strip()
            if label:
                cleaned.append(label)
        if cleaned:
            return " / ".join(cleaned[:4])
    components = mapping(data, "components")
    component_mappings = mapping(data, "componentMappings")
    all_text = " ".join(
        str(v) for v in list(components.values()) + list(component_mappings.values())
        if isinstance(v, (dict, str))
    ).lower()
    if any(t in all_text for t in ("el-", "element-ui", "element ui")):
        return "Element UI"
    if "vxe" in all_text:
        return "VXE-Table"
    if any(t in all_text for t in ("ant design", "ant-design", " antd ", "a-")):
        return "Ant Design"
    if "arco" in all_text:
        return "Arco Design"
    if "shadcn" in all_text:
        return "shadcn/ui"
    if "bootstrap" in all_text:
        return "Bootstrap"
    return "自研组件库" if lang == "zh" else "Custom Components"


def resolve_typical_pages_label(data: dict[str, Any], lang: str) -> str:
    patterns = mapping(data, "pagePatterns")
    if not patterns:
        patterns = mapping(data, "patterns")
    items: list[str] = []
    for key, value in patterns.items():
        label = str(key)
        if isinstance(value, dict):
            scenarios = value.get("applicableScenarios") or value.get("sourceUrls")
            if scenarios:
                s = str(scenarios).split("/")[0].split("，")[0].split(",")[0].strip()
                if s and len(s) <= 20:
                    label = f"{key}（{s}）" if lang == "zh" else f"{key} ({s})"
        items.append(label)
        if len(items) >= 4:
            break
    return "、".join(items) if lang == "zh" and items else ", ".join(items) if items else "—"


def style_overview_card(data: dict[str, Any], lang: str) -> str:
    """Section 1: Design style overview card — front-matter-driven, no fallbacks."""
    name = str(data.get("name", "")) or ("产品名称" if lang == "zh" else "Product Name")
    desc = str(data.get("description", ""))
    primary = resolve_primary_color(data)
    body_type = first_typography(data, "body")
    font_val = html.escape(str(body_type.get("fontFamily", "system-ui, sans-serif")))
    density = resolve_density_label(data, lang)
    product_type = resolve_product_type_label(data, lang)
    comp_system = resolve_component_system_label(data, lang)
    typical_pages = resolve_typical_pages_label(data, lang)
    evidence = mapping(data, "evidence")
    confidence = mapping(data, "confidence")
    unresolved = mapping(data, "unresolvedItems")
    conflicts = mapping(data, "conflicts")
    mode = str(evidence.get("mode", "—")) or "—"
    overall = str(confidence.get("overall", evidence.get("confidence", "—"))) or "—"
    gap_count = len(unresolved) if isinstance(unresolved, dict) else 0
    conflict_count = len(conflicts) if isinstance(conflicts, dict) else 0

    style_desc = desc
    if not style_desc:
        archetype = infer_archetype(data)
        if archetype == "enterprise-admin":
            style_desc = ("高密度、功能优先的企业级后台管理界面。" if lang == "zh"
                          else "High-density, function-first enterprise admin interface.")
        elif archetype == "marketing":
            style_desc = ("强调转化的 SaaS 营销官网。" if lang == "zh"
                          else "Conversion-focused SaaS marketing site.")
        else:
            style_desc = ("应用界面。" if lang == "zh" else "Application interface.")

    name_esc = html.escape(name)
    desc_esc = html.escape(style_desc)
    return f"""
    <div class="review-summary">
      <div>
        <span>{('证据模式' if lang == 'zh' else 'Evidence Mode')}</span>
        <strong>{html.escape(mode)}</strong>
      </div>
      <div>
        <span>{('整体置信度' if lang == 'zh' else 'Overall Confidence')}</span>
        <strong>{html.escape(overall)}</strong>
      </div>
      <div>
        <span>{('待确认项' if lang == 'zh' else 'Open Items')}</span>
        <strong>{gap_count}</strong>
      </div>
      <div>
        <span>{('冲突项' if lang == 'zh' else 'Conflicts')}</span>
        <strong>{conflict_count}</strong>
      </div>
    </div>
    <div style="display:grid;grid-template-columns:repeat(auto-fit,minmax(280px,1fr));gap:16px;margin-top:16px;">
      <div class="surface-card" style="padding:16px;">
        <strong style="font-size:14px;">{('产品名称' if lang == 'zh' else 'Product Name')}</strong>
        <p style="font-size:18px;font-weight:700;color:var(--text-primary);margin-top:8px;">{name_esc}</p>
      </div>
      <div class="surface-card" style="padding:16px;">
        <strong style="font-size:14px;">{('风格摘要' if lang == 'zh' else 'Style Summary')}</strong>
        <p style="font-size:13px;margin-top:8px;color:var(--text-primary);line-height:1.6;">{desc_esc}</p>
      </div>
    </div>
    <div class="comp-grid" style="margin-top:16px;">
      <div class="surface-card" style="padding:16px;">
        <strong style="font-size:13px;">{('主色' if lang == 'zh' else 'Main Color')}</strong>
        <div style="display:flex;align-items:center;gap:10px;margin-top:8px;">
          <span style="display:inline-block;width:28px;height:28px;border-radius:6px;background:{html.escape(primary)};border:1px solid var(--border);"></span>
          <code>{html.escape(primary)}</code>
        </div>
      </div>
      <div class="surface-card" style="padding:16px;">
        <strong style="font-size:13px;">{('字体' if lang == 'zh' else 'Font Family')}</strong>
        <p style="font-size:13px;margin-top:8px;color:var(--text-primary);word-break:break-all;">{font_val}</p>
      </div>
      <div class="surface-card" style="padding:16px;">
        <strong style="font-size:13px;">{('页面密度' if lang == 'zh' else 'Page Density')}</strong>
        <p style="font-size:13px;margin-top:8px;color:var(--text-primary);">{html.escape(density)}</p>
      </div>
      <div class="surface-card" style="padding:16px;">
        <strong style="font-size:13px;">{('组件体系' if lang == 'zh' else 'Component System')}</strong>
        <p style="font-size:13px;margin-top:8px;color:var(--text-primary);">{html.escape(comp_system)}</p>
      </div>
      <div class="surface-card" style="padding:16px;">
        <strong style="font-size:13px;">{('产品类型' if lang == 'zh' else 'Product Type')}</strong>
        <p style="font-size:13px;margin-top:8px;color:var(--text-primary);">{html.escape(product_type)}</p>
      </div>
      <div class="surface-card" style="padding:16px;">
        <strong style="font-size:13px;">{('典型页面' if lang == 'zh' else 'Typical Pages')}</strong>
        <p style="font-size:13px;margin-top:8px;color:var(--text-primary);word-break:break-all;">{html.escape(typical_pages)}</p>
      </div>
    </div>
    """


def layout_grid_spec(data: dict[str, Any], archetype: str, lang: str) -> str:
    """Section 2.3: Layout / Grid visualization."""
    z = lang == "zh"
    gaps = mapping(data, "spacing")
    layout_rules = mapping(data, "layoutRules")
    layout_root = mapping(data, "layout")
    page_templates = mapping(data, "pageTemplates")
    page_patterns = mapping(data, "pagePatterns")
    patterns = mapping(data, "patterns")
    layout_text = " ".join(
        [
            collect_text(layout_rules),
            collect_text(layout_root),
            collect_text(page_templates),
            collect_text(page_patterns),
            collect_text(patterns),
            str(data.get("interfaceArchetype", "")),
            str(data.get("productType", "")),
        ]
    ).lower()
    gutter = token(data, "spacing", "page-margin", "gutter", "md", fallback="20px")

    app_shell = mapping(layout_rules, "appShell") or mapping(layout_root, "appShell")
    topbar_rules = (
        mapping(app_shell, "topbar")
        or mapping(app_shell, "topBar")
        or mapping(app_shell, "topNav")
    )
    content_rules = mapping(app_shell, "content")
    sidebar_rules = mapping(app_shell, "sidebar")
    sidebar_strategy = str(
        content_rules.get("sidebarStrategy")
        or app_shell.get("sidebarStrategy")
        or ""
    ).lower()
    is_right_rail_strategy = any(
        term in sidebar_strategy
        for term in (
            "right",
            "auto-right",
            "flex-auto-right",
            "trailing",
            "end",
            "rail-right",
        )
    )

    container_max_raw = _example_lookup(
        data,
        "layout.appShell.content.containerMaxWidth",
        "layout.appShell.topbar.containerMaxWidth",
        "layout.appShell.topBar.containerMaxWidth",
        "layout.appShell.topNav.containerMaxWidth",
        "layout.container.maxWidth",
        "layout.appShell.maxWidth",
        "layoutRules.appShell.content.containerMaxWidth",
        "layoutRules.appShell.topbar.containerMaxWidth",
        "layoutRules.appShell.topBar.containerMaxWidth",
        "layoutRules.appShell.topNav.containerMaxWidth",
        "layoutRules.container.maxWidth",
        "layoutRules.appShell.maxWidth",
    )
    content_max = _example_css_length(
        container_max_raw,
        "1440px" if archetype != "marketing" else "1280px",
    )

    page_margin_raw = _example_lookup(
        data,
        "layout.appShell.content.paddingX",
        "layout.appShell.content.containerPadding",
        "layout.appShell.containerPadding",
        "layoutRules.appShell.content.paddingX",
        "layoutRules.appShell.content.containerPadding",
        "layoutRules.appShell.containerPadding",
        "tokens.spacing.containerPadding",
        "tokens.spacing.page-margin.container-padding",
        "spacing.containerPadding",
        "spacing.page-margin.container-padding",
    )
    if not page_margin_raw:
        page_margin_raw = token(
            data,
            "spacing",
            "containerPadding",
            "container-padding",
            "page-margin",
            "lg",
            fallback="24px",
        )
    page_margin = _example_css_length(page_margin_raw, "24px")

    responsive_rule = _example_lookup(
        data,
        "layout.responsive.rule",
        "layout.responsive.summary",
        "layout.responsive.description",
        "layout.responsive.strategy",
        "layoutRules.responsive.rule",
        "layoutRules.responsive.summary",
        "layoutRules.responsive.description",
        "layoutRules.responsive.strategy",
    )
    if not responsive_rule:
        responsive_rule = (
            "流式布局，最小宽度 1280px" if z else "Fluid layout, min-width 1280px"
        )

    has_left_sidebar = bool(sidebar_rules) and not is_right_rail_strategy
    has_right_rail = (not has_left_sidebar) and (
        is_right_rail_strategy
        or any(
            term in layout_text
            for term in (
                "挂件",
                "右侧挂件",
                "右侧栏",
                "right rail",
                "right-rail",
                "right-sidebar",
                "aside-right",
                "widget-post-item",
                "widget post item",
            )
        )
    )
    has_topbar = bool(topbar_rules)
    no_shell = any(
        term in layout_text
        for term in (
            "no persistent app shell",
            "no app shell",
            "no sidebar",
            "无侧栏",
            "无持久",
            "single-page",
            "section order",
            "section stack",
            "herosection",
        )
    )

    source_backed_layout = is_extraction_backed(data) and bool(app_shell)
    if source_backed_layout:
        def shell_raw(*values: Any, fallback: str = "") -> str:
            for value in values:
                if value in (None, "", [], {}):
                    continue
                resolved = resolve_all_refs(str(value), data).strip()
                if resolved and "{" not in resolved:
                    return resolved
            return fallback

        topbar_bg = shell_raw(
            topbar_rules.get("background") if isinstance(topbar_rules, dict) else "",
            topbar_rules.get("backgroundColor") if isinstance(topbar_rules, dict) else "",
            _example_lookup(
                data,
                "layout.appShell.topbar.background",
                "layout.appShell.topBar.background",
                "layout.appShell.topNav.background",
                "tokens.colors.shellTopbar",
                "colors.shellTopbar",
            ),
            fallback="#FFFFFF",
        )
        topbar_text = shell_raw(
            topbar_rules.get("textColor") if isinstance(topbar_rules, dict) else "",
            _example_lookup(data, "tokens.colors.text", "colors.text", "tokens.colors.textStrong", "colors.textStrong"),
            fallback="rgba(0,0,0,0.65)",
        )
        sidebar_bg = shell_raw(
            sidebar_rules.get("background") if isinstance(sidebar_rules, dict) else "",
            sidebar_rules.get("backgroundColor") if isinstance(sidebar_rules, dict) else "",
            _example_lookup(data, "layout.appShell.sidebar.background", "tokens.colors.shellSidebar", "colors.shellSidebar"),
            fallback="#FFFFFF",
        )
        sidebar_text = shell_raw(
            sidebar_rules.get("textColor") if isinstance(sidebar_rules, dict) else "",
            _example_lookup(data, "tokens.colors.text", "colors.text", "tokens.colors.textMuted", "colors.textMuted"),
            fallback="rgba(0,0,0,0.65)",
        )
        sidebar_active = shell_raw(
            sidebar_rules.get("activeBackground") if isinstance(sidebar_rules, dict) else "",
            _example_lookup(data, "tokens.colors.activeSurface", "colors.activeSurface", "tokens.colors.shellSidebarActiveBg", "colors.shellSidebarActiveBg"),
            fallback="#F0F7FF",
        )
        content_bg = shell_raw(
            content_rules.get("background") if isinstance(content_rules, dict) else "",
            content_rules.get("backgroundColor") if isinstance(content_rules, dict) else "",
            _example_lookup(data, "layout.appShell.content.background", "tokens.colors.canvas", "colors.canvas", "tokens.colors.shellCanvas", "colors.shellCanvas"),
            fallback="#F9FAFC",
        )
        surface_bg = shell_raw(_example_lookup(data, "tokens.colors.surface", "colors.surface"), fallback="#FFFFFF")
        topbar_height = _example_css_length(
            shell_raw(topbar_rules.get("height") if isinstance(topbar_rules, dict) else "", fallback="64px"),
            "64px",
        )
        sidebar_width = _example_css_length(
            shell_raw(
                sidebar_rules.get("expandedWidth") if isinstance(sidebar_rules, dict) else "",
                sidebar_rules.get("width") if isinstance(sidebar_rules, dict) else "",
                fallback="240px",
            ),
            "240px",
        )
        content_padding = shell_raw(
            content_rules.get("padding") if isinstance(content_rules, dict) else "",
            page_margin,
            fallback=page_margin,
        )
        menu_items = extraction_sidebar_items(data, page_template_items(data), lang)[:4]
        if not menu_items:
            menu_items = ["首页", "知识生产", "知识库", "知识服务"] if z else ["Home", "Production", "Knowledge Base", "Services"]
        menu_html = "".join(
            (
                f'<div style="min-height:32px;display:flex;align-items:center;padding:4px 12px;border-radius:6px;'
                f'background:{html.escape(sidebar_active if index == 1 else "transparent")};'
                f'color:{html.escape("var(--brand)" if index == 1 else sidebar_text)};'
                f'font-weight:{600 if index == 1 else 400};text-align:left;">{html.escape(str(item))}</div>'
            )
            for index, item in enumerate(menu_items)
        )
        sample_templates = page_template_items(data)
        def template_name(item: dict[str, Any], fallback: str) -> str:
            return _first_string(
                item.get("title"),
                item.get("name"),
                item.get("id"),
                item.get("key"),
                item.get("path"),
                fallback,
            )
        first_template_name = template_name(sample_templates[0], "页面内容" if z else "Page Content") if sample_templates else ("页面内容" if z else "Page Content")
        second_template_name = template_name(sample_templates[1], "表格 / 卡片内容" if z else "Table / Card Content") if len(sample_templates) > 1 else ("表格 / 卡片内容" if z else "Table / Card Content")
        layout_html = f"""
    <div class="layout-diagram" data-layout-source="design-md" style="--diagram-topbar-bg:{html.escape(topbar_bg)};--diagram-topbar-text:{html.escape(topbar_text)};--diagram-sidebar-bg:{html.escape(sidebar_bg)};--diagram-sidebar-text:{html.escape(sidebar_text)};--diagram-content-bg:{html.escape(content_bg)};--diagram-surface-bg:{html.escape(surface_bg)};">
      <div class="region header" style="height:{html.escape(topbar_height)};display:flex;align-items:center;justify-content:flex-end;background:{html.escape(topbar_bg)};color:{html.escape(topbar_text)};border-bottom:1px solid var(--border);box-shadow:var(--shadow-card);padding:0 18px;">{html.escape('64px 白色顶栏 / 用户工具区' if z else '64px light topbar / user tools')}</div>
      <div class="sider-content" style="grid-template-columns:{html.escape(sidebar_width)} minmax(0,1fr);">
        <div class="region sider" style="display:grid;align-content:start;gap:8px;padding:12px 18px;background:{html.escape(sidebar_bg)};color:{html.escape(sidebar_text)};border-right:1px solid var(--border);box-shadow:2px 0 8px rgba(29,35,41,0.05);text-align:left;">
          <div style="height:40px;display:flex;align-items:center;font-weight:600;color:var(--text-primary);">{html.escape(data.get('name') or ('产品导航' if z else 'Product Navigation'))}</div>
          {menu_html}
        </div>
        <div class="region content" style="display:grid;gap:12px;padding:{html.escape(content_padding)};background:{html.escape(content_bg)};text-align:left;">
          <div style="height:32px;background:{html.escape(surface_bg)};border:1px solid var(--border);border-radius:4px;display:flex;align-items:center;padding:0 12px;color:var(--text-muted);">{html.escape(humanize_identifier(str(first_template_name)))}</div>
          <div style="height:92px;background:{html.escape(surface_bg)};border:1px solid var(--border);border-radius:4px;display:grid;place-items:center;color:var(--text-muted);">{html.escape(humanize_identifier(str(second_template_name)))}</div>
        </div>
      </div>
    </div>"""
        legend_html = f"""
    <div class="legend" data-layout-source="design-md">
      <div class="legend-item"><span class="legend-box" style="background:{html.escape(topbar_bg)};border-color:var(--border);"></span>{'顶栏：来自 layout.appShell.topbar' if z else 'Topbar: from layout.appShell.topbar'}</div>
      <div class="legend-item"><span class="legend-box" style="background:{html.escape(sidebar_bg)};border-color:var(--border);"></span>{'侧栏：来自 layout.appShell.sidebar' if z else 'Sidebar: from layout.appShell.sidebar'}</div>
      <div class="legend-item"><span class="legend-box" style="background:{html.escape(content_bg)};border-color:var(--border);"></span>{'内容画布：来自 layout.appShell.content' if z else 'Canvas: from layout.appShell.content'}</div>
    </div>"""

    if source_backed_layout:
        pass
    elif (archetype == "brand-portfolio" or no_shell) and not (
        ("enterprise" in archetype or "dashboard" in archetype) and has_left_sidebar
    ):
        templates = list(page_templates.keys()) or list(page_patterns.keys()) or list(patterns.keys())
        if not templates:
            section_order = mapping(layout_rules, "sectionOrder")
            if isinstance(section_order, dict):
                templates = [str(value) for value in section_order.values()]
            elif isinstance(section_order, list):
                templates = [str(value) for value in section_order]
        if not templates:
            templates = ["HeroSection", "MarqueeSection", "AboutSection", "ServicesSection", "ProjectsSection"] if archetype == "brand-portfolio" else []
        if templates:
            section_rows = "".join(
                f'<div class="region" style="background:{("var(--brand)" if index == 0 else "var(--bg-surface)" if index % 2 else "var(--bg-elevated)")};color:{("#fff" if index == 0 else "var(--text-primary)")};padding:{("28px 10px" if index == 0 else "18px 10px")};">{html.escape(humanize_identifier(str(name)))}</div>'
                for index, name in enumerate(templates[:7])
            )
            layout_html = f"""
    <div class="layout-diagram">
      {section_rows}
    </div>"""
        else:
            layout_html = f"""
    <div class="layout-diagram">
      <div class="region" style="background:var(--bg-surface);padding:40px 10px;color:var(--text-muted);">{'布局证据不足，需要确认' if z else 'Layout needs confirmation'}</div>
    </div>"""
        legend_html = f"""
    <div class="legend">
      <div class="legend-item"><span class="legend-box" style="background:var(--brand);"></span>{'首屏 / 品牌区' if z else 'Hero / Brand Section'}</div>
      <div class="legend-item"><span class="legend-box" style="background:var(--bg-surface);border-color:var(--border);"></span>{'页面分区' if z else 'Page Section'}</div>
      <div class="legend-item"><span class="legend-box" style="background:var(--bg-elevated);border-color:var(--border);"></span>{'媒体 / 内容模块' if z else 'Media / Content Module'}</div>
    </div>"""

    elif ("enterprise" in archetype or "dashboard" in archetype) and has_left_sidebar:
        layout_html = f"""
    <div class="layout-diagram">
      <div class="region header">Topbar / {'顶部导航' if z else 'Top Navigation'}</div>
      <div class="region tabs">{'标签导航 / Tab Navigation (可选)' if z else 'Tab Navigation (optional)'}</div>
      <div class="sider-content">
        <div class="region sider" style="display:grid;align-content:start;gap:10px;padding:16px 12px;">
          <div style="opacity:.7;">{'菜单' if z else 'Menu 1'}</div>
          <div style="opacity:.5;">{'菜单' if z else 'Menu 2'}</div>
          <div style="opacity:.5;">{'菜单' if z else 'Menu 3'}</div>
        </div>
        <div class="region content" style="display:grid;gap:10px;padding:16px;">
          <div style="height:30px;background:var(--bg-elevated);border-radius:4px;"></div>
          <div style="height:100px;background:var(--bg-elevated);border-radius:4px;"></div>
        </div>
      </div>
    </div>"""
        legend_html = f"""
    <div class="legend">
      <div class="legend-item"><span class="legend-box" style="background:var(--brand);"></span>{'顶部导航 / 品牌区' if z else 'Top Nav / Brand'}</div>
      <div class="legend-item"><span class="legend-box" style="background:color-mix(in srgb, var(--brand) 80%, #000);"></span>{'侧栏 / 菜单' if z else 'Sidebar / Menu'}</div>
      <div class="legend-item"><span class="legend-box" style="background:var(--bg-surface);border-color:var(--border);"></span>{'内容区' if z else 'Content Area'}</div>
    </div>"""

    elif archetype in {"media-content", "content-resource-portal"} or (has_topbar and has_right_rail):
        right_rail_html = (
            """
        <div class="region" style="background:var(--bg-elevated);padding:16px 12px;border-left:1px solid var(--border);display:grid;gap:10px;align-content:start;">
          <div style="opacity:.7;font-weight:600;">{rail_title}</div>
          <div style="opacity:.55;">{rail_item_1}</div>
          <div style="opacity:.55;">{rail_item_2}</div>
        </div>""".format(
                rail_title='右侧挂件栏' if z else 'Right Rail',
                rail_item_1='推荐文章 / 排行榜' if z else 'Recommended / Ranking',
                rail_item_2='运营位 / 公开课' if z else 'Promo / Lessons',
            )
            if has_right_rail
            else ""
        )
        grid_cols = "1fr 0.32fr" if has_right_rail else "1fr"
        layout_html = f"""
    <div class="layout-diagram">
      <div class="region header">Topbar / {'顶部导航' if z else 'Top Navigation'}</div>
      <div class="region tabs">{'频道 Tab / Channel Tabs (可选)' if z else 'Channel Tabs (optional)'}</div>
      <div class="sider-content" style="grid-template-columns:{grid_cols};">
        <div class="region content" style="display:grid;gap:10px;padding:16px;">
          <div style="height:24px;background:var(--bg-elevated);border-radius:4px;width:55%;"></div>
          <div style="height:80px;background:var(--bg-elevated);border-radius:4px;"></div>
          <div style="height:80px;background:var(--bg-elevated);border-radius:4px;"></div>
        </div>
        {right_rail_html}
      </div>
      <div class="region" style="background:#222C3C;color:#fff;opacity:.9;padding:14px 10px;">{'页脚 / Footer' if z else 'Footer'}</div>
    </div>"""
        right_rail_legend = (
            f"""<div class="legend-item"><span class="legend-box" style="background:var(--bg-elevated);border-color:var(--border);"></span>{'右侧挂件栏 / Right Rail' if z else 'Right Rail'}</div>"""
            if has_right_rail
            else ""
        )
        legend_html = f"""
    <div class="legend">
      <div class="legend-item"><span class="legend-box" style="background:var(--brand);"></span>{'顶部导航 / 品牌区' if z else 'Top Nav / Brand'}</div>
      <div class="legend-item"><span class="legend-box" style="background:var(--bg-surface);border-color:var(--border);"></span>{'主信息流 / Content' if z else 'Main Feed / Content'}</div>
      {right_rail_legend}
    </div>"""

    elif "marketing" in archetype:
        layout_html = f"""
    <div class="layout-diagram">
      <div class="region header">{'顶部导航 / Nav' if z else 'Nav'}</div>
      <div class="region" style="background:var(--bg-surface);padding:32px 10px;font-weight:600;color:var(--text-primary);">{'Hero / 主视觉区' if z else 'Hero Section'}</div>
      <div style="display:grid;grid-template-columns:1fr 1fr;">
        <div class="region" style="background:var(--bg-elevated);">{'内容分区' if z else 'Content 1'}</div>
        <div class="region" style="background:var(--bg-surface);">{'内容分区' if z else 'Content 2'}</div>
      </div>
      <div class="region" style="background:var(--brand);color:#fff;opacity:.85;">CTA / {'行动号召' if z else 'Call to Action'}</div>
    </div>"""
        legend_html = f"""
    <div class="legend">
      <div class="legend-item"><span class="legend-box" style="background:var(--brand);"></span>{'品牌 / CTA' if z else 'Brand / CTA'}</div>
      <div class="legend-item"><span class="legend-box" style="background:var(--bg-surface);border-color:var(--border);"></span>{'内容分区' if z else 'Content Section'}</div>
      <div class="legend-item"><span class="legend-box" style="background:var(--bg-elevated);border-color:var(--border);"></span>{'辅助分区' if z else 'Supporting Section'}</div>
    </div>"""

    elif "mobile" in archetype:
        layout_html = f"""
    <div class="layout-diagram" style="max-width:380px;margin:0 auto;">
      <div class="region header" style="font-size:12px;">{'状态栏 + 顶部导航' if z else 'Status Bar + Top Nav'}</div>
      <div class="region" style="padding:64px 10px;background:var(--bg-surface);color:var(--text-muted);">{'核心内容区' if z else 'Content Area'}</div>
      <div class="region" style="display:grid;grid-template-columns:repeat(4,1fr);gap:4px;background:var(--bg-surface);border-top:1px solid var(--border);padding:8px;">
        <div style="opacity:.5;">{'首页' if z else 'Home'}</div>
        <div style="opacity:.7;color:var(--brand);font-weight:600;">{'列表' if z else 'List'}</div>
        <div style="opacity:.5;">{'消息' if z else 'Msg'}</div>
        <div style="opacity:.5;">{'我的' if z else 'Profile'}</div>
      </div>
    </div>"""
        legend_html = f"""
    <div class="legend">
      <div class="legend-item"><span class="legend-box" style="background:var(--brand);"></span>{'顶部导航 / 品牌区' if z else 'Top Nav / Brand'}</div>
      <div class="legend-item"><span class="legend-box" style="background:var(--bg-surface);border-color:var(--border);"></span>{'内容区' if z else 'Content Area'}</div>
      <div class="legend-item"><span class="legend-box" style="background:var(--bg-elevated);border-color:var(--border);"></span>{'底部导航' if z else 'Bottom Nav'}</div>
    </div>"""

    else:
        layout_html = f"""
    <div class="layout-diagram">
      <div class="region" style="background:var(--bg-surface);padding:40px 10px;color:var(--text-muted);">{'布局证据不足，需要确认' if z else 'Layout needs confirmation'}</div>
    </div>"""
        legend_html = f"""
    <div class="legend">
      <div class="legend-item"><span class="legend-box" style="background:var(--bg-surface);border-color:var(--border);"></span>{'已记录区域' if z else 'Documented Region'}</div>
      <div class="legend-item"><span class="legend-box" style="background:var(--bg-elevated);border-color:var(--border);"></span>{'待确认区域' if z else 'Unconfirmed Region'}</div>
    </div>"""

    section_note = (
        "以下布局示意图严格来自 DESIGN.md 的 layout.appShell / pageTemplates / sampleContent；未使用通用企业后台 fallback。"
        if source_backed_layout and z
        else "Layout diagram is generated from DESIGN.md layout.appShell / pageTemplates / sampleContent; generic admin fallback is disabled."
        if source_backed_layout
        else "以下展示页面框架结构，数字和布局仅供参考，以实际产品为准。"
        if z
        else "Page framework diagram below. Actual dimensions may vary."
    )

    return f"""
    <div class="section-note">{html.escape(section_note)}</div>
    {legend_html}
    {layout_html}
    <div class="comp-grid" style="margin-top:16px;">
      <div class="surface-card" style="padding:14px;">
        <strong style="font-size:13px;">{'标准画板宽度' if z else 'Canvas Width'}</strong>
        <p style="font-size:13px;margin-top:4px;color:var(--text-primary);">{content_max}</p>
      </div>
      <div class="surface-card" style="padding:14px;">
        <strong style="font-size:13px;">{'页面安全边距' if z else 'Page Margin'}</strong>
        <p style="font-size:13px;margin-top:4px;color:var(--text-primary);">{page_margin}</p>
      </div>
      <div class="surface-card" style="padding:14px;">
        <strong style="font-size:13px;">{'栅格间距 (Gutter)' if z else 'Grid Gutter'}</strong>
        <p style="font-size:13px;margin-top:4px;color:var(--text-primary);">{gutter}</p>
      </div>
      <div class="surface-card" style="padding:14px;">
        <strong style="font-size:13px;">{'适配说明' if z else 'Responsive'}</strong>
        <p style="font-size:13px;margin-top:4px;color:var(--text-primary);">{html.escape(responsive_rule)}</p>
      </div>
    </div>
    """


def icon_spec(data: dict[str, Any], sections: dict[str, str], lang: str) -> str:
    """Section 2.4: Icon specification."""
    z = lang == "zh"
    sections_text = " ".join(sections.values()).lower()
    has_icon_info = any(
        t in sections_text for t in ("icon", "图标", "svg", "material", "font-awesome", "lucide", "heroicons")
    )
    components_text = " ".join([str(v) for v in mapping(data, "components").keys()]).lower()
    has_icon_comp = any(t in components_text for t in ("icon", "svg"))

    if not has_icon_info and not has_icon_comp:
        return f"""
    <div class="section-note" style="margin-bottom:0;">
      {'未识别到完整图标体系。以下展示通用图标占位样例，实际图标规范请参考 DESIGN.md。' if z else 'No complete icon system detected. Generic icon placeholders shown below. Refer to DESIGN.md for actual icon specs.'}
    </div>
    <div style="display:flex;gap:20px;flex-wrap:wrap;margin-top:14px;padding:14px;background:var(--bg-elevated);border:1px solid var(--border);border-radius:var(--radius-card);">
      <div style="text-align:center;width:48px;">
        <svg width="24" height="24" viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="2" style="color:var(--text-muted);"><circle cx="12" cy="12" r="10"/><path d="M12 6v6l4 2"/></svg>
        <div style="font-size:11px;color:var(--text-muted);margin-top:4px;">{'时间' if z else 'Time'}</div>
      </div>
      <div style="text-align:center;width:48px;">
        <svg width="24" height="24" viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="2" style="color:var(--text-muted);"><path d="M3 9l9-7 9 7v11a2 2 0 0 1-2 2H5a2 2 0 0 1-2-2z"/><polyline points="9 22 9 12 15 12 15 22"/></svg>
        <div style="font-size:11px;color:var(--text-muted);margin-top:4px;">{'首页' if z else 'Home'}</div>
      </div>
      <div style="text-align:center;width:48px;">
        <svg width="24" height="24" viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="2" style="color:var(--text-muted);"><ellipse cx="12" cy="5" rx="9" ry="3"/><path d="M21 12c0 1.66-4 3-9 3s-9-1.34-9-3"/><path d="M3 5v14c0 1.66 4 3 9 3s9-1.34 9-3V5"/></svg>
        <div style="font-size:11px;color:var(--text-muted);margin-top:4px;">{'数据' if z else 'Data'}</div>
      </div>
      <div style="text-align:center;width:48px;">
        <svg width="24" height="24" viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="2" style="color:var(--text-muted);"><circle cx="12" cy="12" r="3"/><path d="M19.4 15a1.65 1.65 0 0 0 .33 1.82l.06.06a2 2 0 0 1 0 2.83 2 2 0 0 1-2.83 0l-.06-.06a1.65 1.65 0 0 0-1.82-.33 1.65 1.65 0 0 0-1 1.51V21a2 2 0 0 1-2 2 2 2 0 0 1-2-2v-.09A1.65 1.65 0 0 0 9 19.4a1.65 1.65 0 0 0-1.82.33l-.06.06a2 2 0 0 1-2.83 0 2 2 0 0 1 0-2.83l.06-.06A1.65 1.65 0 0 0 4.68 15a1.65 1.65 0 0 0-1.51-1H3a2 2 0 0 1-2-2 2 2 0 0 1 2-2h.09A1.65 1.65 0 0 0 4.6 9a1.65 1.65 0 0 0-.33-1.82l-.06-.06a2 2 0 0 1 0-2.83 2 2 0 0 1 2.83 0l.06.06A1.65 1.65 0 0 0 9 4.68a1.65 1.65 0 0 0 1-1.51V3a2 2 0 0 1 2-2 2 2 0 0 1 2 2v.09a1.65 1.65 0 0 0 1 1.51 1.65 1.65 0 0 0 1.82-.33l.06-.06a2 2 0 0 1 2.83 0 2 2 0 0 1 0 2.83l-.06.06a1.65 1.65 0 0 0-.33 1.82V9a1.65 1.65 0 0 0 1.51 1H21a2 2 0 0 1 2 2 2 2 0 0 1-2 2h-.09a1.65 1.65 0 0 0-1.51 1z"/></svg>
        <div style="font-size:11px;color:var(--text-muted);margin-top:4px;">{'设置' if z else 'Settings'}</div>
      </div>
      <div style="text-align:center;width:48px;">
        <svg width="24" height="24" viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="2" style="color:var(--text-muted);"><path d="M14 2H6a2 2 0 0 0-2 2v16a2 2 0 0 0 2 2h12a2 2 0 0 0 2-2V8z"/><polyline points="14 2 14 8 20 8"/><line x1="16" y1="13" x2="8" y2="13"/><line x1="16" y1="17" x2="8" y2="17"/></svg>
        <div style="font-size:11px;color:var(--text-muted);margin-top:4px;">{'文档' if z else 'Doc'}</div>
      </div>
      <div style="text-align:center;width:48px;">
        <svg width="24" height="24" viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="2" style="color:var(--text-muted);"><path d="M21 15v4a2 2 0 0 1-2 2H5a2 2 0 0 1-2-2v-4"/><polyline points="7 10 12 15 17 10"/><line x1="12" y1="15" x2="12" y2="3"/></svg>
        <div style="font-size:11px;color:var(--text-muted);margin-top:4px;">{'下载' if z else 'Download'}</div>
      </div>
    </div>
    """

    return f"""
    <div class="comp-grid" style="margin-top:10px;">
      <div class="surface-card" style="padding:14px;">
        <strong style="font-size:13px;">{'图标风格' if z else 'Icon Style'}</strong>
        <p style="font-size:13px;margin-top:4px;color:var(--text-primary);">{'线性 / 面性混合' if z else 'Line / Filled Mixed'}</p>
      </div>
      <div class="surface-card" style="padding:14px;">
        <strong style="font-size:13px;">{'默认尺寸' if z else 'Default Size'}</strong>
        <p style="font-size:13px;margin-top:4px;color:var(--text-primary);">16×16px</p>
      </div>
      <div class="surface-card" style="padding:14px;">
        <strong style="font-size:13px;">{'导航尺寸' if z else 'Nav Size'}</strong>
        <p style="font-size:13px;margin-top:4px;color:var(--text-primary);">18×18px</p>
      </div>
      <div class="surface-card" style="padding:14px;">
        <strong style="font-size:13px;">{'提示尺寸' if z else 'Alert Size'}</strong>
        <p style="font-size:13px;margin-top:4px;color:var(--text-primary);">24×24px</p>
      </div>
      <div class="surface-card" style="padding:14px;">
        <strong style="font-size:13px;">{'格式' if z else 'Format'}</strong>
        <p style="font-size:13px;margin-top:4px;color:var(--text-primary);">SVG</p>
      </div>
      <div class="surface-card" style="padding:14px;">
        <strong style="font-size:13px;">{'默认颜色' if z else 'Default Color'}</strong>
        <p style="font-size:13px;margin-top:4px;color:var(--text-primary);">{'跟随文字颜色' if z else 'Inherit text color'}</p>
      </div>
    </div>
    """


def button_spec_section(data: dict[str, Any], lang: str) -> str:
    """Section 3.1: Button specification with states and sizing."""
    z = lang == "zh"
    primary = token(data, "colors", "primary", "brand", "accent", fallback="var(--brand)")
    danger = token(data, "colors", "danger", "semantic-error", "error", fallback="var(--brand)")
    height_value, height_source = documented_spec_value(
        data,
        ("button", "buttons"),
        ("height", "defaultHeight", "buttonHeight"),
    )
    radius_value, radius_source = documented_spec_value(
        data,
        ("button", "buttons"),
        ("radius", "borderRadius", "rounded"),
        "rounded",
        ("button", "control", "sm", "md"),
    )
    gap_value, gap_source = documented_spec_value(
        data,
        ("button", "buttons"),
        ("gap", "buttonGap", "spacing"),
        "spacing",
        ("buttonGap", "button-gap"),
    )

    btn_rules = [
        (('主按钮' if z else 'Primary'), 'primary md', ('' if z else 'Primary action'), primary, '#fff', 'none'),
        (('次按钮' if z else 'Default'), 'default md', ('' if z else 'Secondary'), 'transparent', 'var(--text-primary)', '1px solid var(--border)'),
        (('幽灵按钮' if z else 'Ghost'), 'ghost md', ('' if z else 'Ghost'), 'transparent', primary, f'1px solid {primary}'),
        (('文字按钮' if z else 'Text'), 'text md', ('' if z else 'Text'), 'transparent', primary, 'none'),
        (('危险按钮' if z else 'Danger'), 'danger md', ('' if z else 'Danger'), danger, '#fff', 'none'),
    ]

    btn_html_parts = []
    for name, cls, placeholder, bg, color_, border_ in btn_rules:
        btn_html_parts.append(
            f'<button class="btn-sample {cls}" style="background:{bg};color:{color_};border:{border_};">{name}</button>'
        )

    sizes = [
        (('小' if z else 'Small'), 'sm'),
        (('中' if z else 'Medium'), 'md'),
        (('大' if z else 'Large'), 'lg'),
    ]
    size_html = "".join(
        f'<button class="btn-sample {s[1]}" style="color:var(--brand);border:1px solid var(--border);background:transparent;">{s[0]}</button>'
        for s in sizes
    )

    states_buttons = " ".join(
        [
            f'<button class="btn-sample primary md">{("主按钮" if z else "Primary")}</button>',
            f'<button class="btn-sample primary md" style="opacity:.8;">{("Hover" if z else "Hover")}</button>',
            f'<button class="btn-sample primary md" style="opacity:.7;">{("Active" if z else "Active")}</button>',
            f'<button class="btn-sample primary md disabled">{("禁用" if z else "Disabled")}</button>',
        ]
    )

    return f"""
    <div style="margin-top:10px;">
      <h4 style="margin:0 0 6px;">{'按钮变体' if z else 'Button Variants'}</h4>
      <div class="sample-line">{"".join(btn_html_parts[:3])}</div>
      <div class="sample-line">{"".join(btn_html_parts[3:])}</div>

      <h4 style="margin-top:20px;margin-bottom:6px;">{'尺寸等级' if z else 'Size Levels'}</h4>
      <div class="sample-line">{size_html}</div>

      <h4 style="margin-top:20px;margin-bottom:6px;">{'交互状态' if z else 'Interaction States'}</h4>
      <div class="sample-line">{states_buttons}</div>

      <h4 style="margin-top:20px;margin-bottom:6px;">{'关键规则' if z else 'Key Rules'}</h4>
      <div style="display:grid;grid-template-columns:repeat(auto-fit,minmax(200px,1fr));gap:10px;margin-top:8px;">
        <div class="surface-card" style="padding:10px;">
          <strong style="font-size:12px;">{'默认高度' if z else 'Default Height'}</strong>
          <p style="font-size:13px;margin-top:4px;color:var(--text-primary);">{spec_value_markup(height_value, height_source, lang)}</p>
        </div>
        <div class="surface-card" style="padding:10px;">
          <strong style="font-size:12px;">{'圆角' if z else 'Border Radius'}</strong>
          <p style="font-size:13px;margin-top:4px;color:var(--text-primary);">{spec_value_markup(radius_value, radius_source, lang)}</p>
        </div>
        <div class="surface-card" style="padding:10px;">
          <strong style="font-size:12px;">{'按钮间距' if z else 'Button Gap'}</strong>
          <p style="font-size:13px;margin-top:4px;color:var(--text-primary);">{spec_value_markup(gap_value, gap_source, lang)}</p>
        </div>
        <div class="surface-card" style="padding:10px;">
          <strong style="font-size:12px;">{'规则' if z else 'Rule'}</strong>
          <p style="font-size:13px;margin-top:4px;color:var(--text-primary);">{('一个页面区最多一个主按钮' if z else 'Max one primary button per section')}</p>
        </div>
      </div>
    </div>
    """


def input_spec_section(data: dict[str, Any], lang: str) -> str:
    """Section 3.2: Data entry component specification."""
    z = lang == "zh"
    primary = token(data, "colors", "primary", "brand", fallback="var(--brand)")
    examples, example_source = source_input_examples(data)
    input_placeholder = component_example_text(examples, "placeholder", "inputPlaceholder", "label", "name")
    input_value = component_example_text(examples, "value", "inputValue", "defaultValue")
    error_value = component_example_text(examples, "errorValue", "invalidValue")
    search_placeholder = component_example_text(examples, "searchPlaceholder", "search", "filter") or input_placeholder
    textarea_value = component_example_text(examples, "textarea", "textareaValue", "description", "body")
    select_options = first_sample_list(examples, "options", "selectOptions", "items")
    selected_option = str(select_options[0]) if select_options else ("已选" if z else "Selected")
    note = f'<div class="section-note" data-example-source="neutral-state">{neutral_state_note(lang)}</div>' if example_source == "neutral-state" else ""
    height_value, height_source = documented_spec_value(
        data,
        ("input", "inputs", "form", "forms"),
        ("height", "defaultHeight", "inputHeight", "controlHeight"),
    )
    radius_value, radius_source = documented_spec_value(
        data,
        ("input", "inputs", "form", "forms"),
        ("radius", "borderRadius", "rounded"),
        "rounded",
        ("input", "control", "sm", "md"),
    )

    return f"""
    {note}
    <div class="comp-grid" style="margin-top:10px;">
      <div class="surface-card" style="padding:16px;">
        <h4 style="margin:0 0 8px;">{'输入框' if z else 'Input'}</h4>
        <div class="input-group" data-example-source="{example_source}">
          <input class="input-demo" placeholder="{html.escape(input_placeholder)}" value="{html.escape(input_value)}" />
          <input class="input-demo" placeholder="{html.escape(input_placeholder)}" value="{html.escape(input_value)}" style="border-color:{primary};box-shadow:0 0 0 2px color-mix(in srgb, {primary} 20%, transparent);" />
          <input class="input-demo error" placeholder="{html.escape(input_placeholder)}" value="{html.escape(error_value)}" />
          <input class="input-demo" placeholder="{'禁用' if z else 'Disabled'}" disabled />
        </div>
        <div style="margin-top:8px;display:grid;grid-template-columns:repeat(auto-fit,minmax(140px,1fr));gap:8px;">
          <div><code style="font-size:11px;">{'高度' if z else 'Height'}: {spec_value_markup(height_value, height_source, lang)}</code></div>
          <div><code style="font-size:11px;">{'圆角' if z else 'Radius'}: {spec_value_markup(radius_value, radius_source, lang)}</code></div>
        </div>
      </div>

      <div class="surface-card" style="padding:16px;">
        <h4 style="margin:0 0 8px;">{'下拉选择' if z else 'Select'}</h4>
        <div class="input-row" data-example-source="{example_source}">
          <select class="input-demo" style="width:180px;">
            <option>{html.escape(selected_option)}</option>
            <option selected>{('选中' if z else 'Selected')}</option>
          </select>
          <select class="input-demo" style="width:180px;" disabled>
            <option>{('禁用' if z else 'Disabled')}</option>
          </select>
        </div>
      </div>

      <div class="surface-card" style="padding:16px;">
        <h4 style="margin:0 0 8px;">{'搜索框' if z else 'Search Box'}</h4>
        <div class="input-row" data-example-source="{example_source}">
          <input class="input-demo" placeholder="{html.escape(search_placeholder)}" style="width:220px;" />
          <button class="btn-sample primary sm">{'查询' if z else 'Search'}</button>
        </div>
      </div>
    </div>

    <div class="comp-grid" style="margin-top:12px;">
      <div class="surface-card" style="padding:16px;">
        <h4 style="margin:0 0 8px;">{'复选框 / 单选框' if z else 'Checkbox / Radio'}</h4>
        <div class="sample-line">
          <label style="display:inline-flex;align-items:center;gap:6px;font-size:13px;cursor:default;margin:0;">
            <span style="display:inline-flex;width:14px;height:14px;border:2px solid {primary};border-radius:3px;background:{primary};align-items:center;justify-content:center;font-size:10px;color:#fff;line-height:1;">✓</span>
            {('已选' if z else 'Checked')}
          </label>
          <label style="display:inline-flex;align-items:center;gap:6px;font-size:13px;cursor:default;margin:0;">
            <span style="display:inline-flex;width:14px;height:14px;border:2px solid var(--border);border-radius:3px;"></span>
            {('未选' if z else 'Unchecked')}
          </label>
          <label style="display:inline-flex;align-items:center;gap:6px;font-size:13px;cursor:default;margin:0;">
            <span style="display:inline-flex;width:14px;height:14px;border:2px solid {primary};border-radius:50%;background:radial-gradient(circle,{primary} 40%,transparent 42%);"></span>
            {('已选' if z else 'Selected')}
          </label>
          <label style="display:inline-flex;align-items:center;gap:6px;font-size:13px;cursor:default;margin:0;">
            <span style="display:inline-flex;width:14px;height:14px;border:2px solid var(--border);border-radius:50%;"></span>
            {('未选' if z else 'Unselected')}
          </label>
        </div>
      </div>

      <div class="surface-card" style="padding:16px;">
        <h4 style="margin:0 0 8px;">{'开关' if z else 'Switch'}</h4>
        <div class="sample-line">
          <span style="display:inline-flex;width:36px;height:20px;border-radius:10px;background:{primary};align-items:center;padding:0 2px;justify-content:flex-end;"><span style="width:16px;height:16px;border-radius:50%;background:#fff;"></span></span>
          <span style="font-size:12px;color:var(--text-muted);">{('开启' if z else 'On')}</span>
          <span style="display:inline-flex;width:36px;height:20px;border-radius:10px;background:var(--bg-elevated);border:1px solid var(--border);align-items:center;padding:0 2px;"><span style="width:16px;height:16px;border-radius:50%;background:var(--text-muted);"></span></span>
          <span style="font-size:12px;color:var(--text-muted);">{('关闭' if z else 'Off')}</span>
        </div>
      </div>
    </div>

    <div class="surface-card" style="padding:16px;margin-top:12px;">
      <h4 style="margin:0 0 8px;">{'文本域' if z else 'Textarea'}</h4>
      <textarea class="input-demo" data-example-source="{example_source}" style="width:100%;min-height:64px;resize:vertical;height:auto;" placeholder="{html.escape(input_placeholder)}">{html.escape(textarea_value)}</textarea>
    </div>
    """


def data_display_spec(data: dict[str, Any], lang: str) -> str:
    """Section 3.3: Data display component specification."""
    z = lang == "zh"
    primary = token(data, "colors", "primary", "brand", fallback="var(--brand)")
    header_bg = token(data, "colors", "table-header-bg", "surface-table-header", fallback="var(--bg-elevated)")
    columns, rows, example_source = source_table_examples(data, lang)
    if not columns and rows and isinstance(rows[0], dict):
        columns = [str(key) for key in rows[0].keys()]
    columns = columns[:5] or [("列" if z else "Column"), ("列" if z else "Column"), ("操作" if z else "Action")]

    def row_values(row: Any) -> list[str]:
        if isinstance(row, dict):
            values = [str(row.get(column, "")) for column in columns]
        elif isinstance(row, list):
            values = [str(item) for item in row]
        else:
            values = [str(row)]
        while len(values) < len(columns):
            values.append("")
        return values[: len(columns)]

    grid_cols = " ".join(["1fr"] * min(max(len(columns), 1), 5))
    header = "".join(f"<span>{html.escape(column)}</span>" for column in columns[:5])
    body_rows = ""
    for row in rows[:4]:
        cells = "".join(
            f'<span>{"<a href=\"#\" style=\"color:" + html.escape(primary) + ";text-decoration:none;font-weight:500;\">" + html.escape(value) + "</a>" if index == 0 and value else html.escape(value)}</span>'
            for index, value in enumerate(row_values(row)[:5])
        )
        body_rows += f'<div class="hover" style="grid-template-columns:{grid_cols};">{cells}</div>'
    if not body_rows:
        skeleton_cells = "".join(f"<span>{skeleton_bar(width)}</span>" for width in ("72%", "48%", "34%", "58%", "42%")[: len(columns)])
        body_rows = "".join(
            f'<div class="hover" style="grid-template-columns:{grid_cols};">{skeleton_cells}</div>'
            for _ in range(4)
        )
    first_row = row_values(rows[0]) if rows else []
    desc_name = first_row[0] if first_row else ""
    desc_type = first_row[1] if len(first_row) > 1 else ""
    note = f'<div class="section-note" data-example-source="neutral-state">{neutral_state_note(lang)}</div>' if example_source == "neutral-state" else ""

    desc_values = (
        f"""
          <strong style="color:var(--text-muted);">{html.escape(columns[0] if columns else ('名称' if z else 'Name'))}:</strong><span style="color:var(--text-primary);">{html.escape(str(desc_name))}</span>
          <strong style="color:var(--text-muted);">{html.escape(columns[1] if len(columns) > 1 else ('类型' if z else 'Type'))}:</strong><span style="color:var(--text-primary);">{html.escape(str(desc_type))}</span>
        """
        if first_row
        else f"""
          <strong style="color:var(--text-muted);">{html.escape(columns[0])}:</strong><span>{skeleton_bar('64%')}</span>
          <strong style="color:var(--text-muted);">{html.escape(columns[1] if len(columns) > 1 else ('列' if z else 'Column'))}:</strong><span>{skeleton_bar('46%')}</span>
        """
    )

    return f"""
    {note}
    <div class="table-demo" data-example-source="{example_source}">
      <div class="header" style="background:{header_bg};grid-template-columns:{grid_cols};">
        {header}
      </div>
      {body_rows}
    </div>

    <div class="comp-grid" style="margin-top:12px;">
      <div class="surface-card" style="padding:14px;">
        <strong style="font-size:13px;">{'空状态' if z else 'Empty State'}</strong>
        <div style="text-align:center;padding:20px 0;margin-top:8px;">
          <svg width="48" height="48" viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="1.5" style="color:var(--text-muted);opacity:.4;">
            <path d="M13 2H6a2 2 0 0 0-2 2v16a2 2 0 0 0 2 2h12a2 2 0 0 0 2-2V9z"/><polyline points="13 2 13 9 20 9"/>
          </svg>
          <p style="font-size:13px;color:var(--text-muted);margin-top:8px;">{'暂无数据' if z else 'No data available'}</p>
          <button class="btn-sample primary sm" style="margin-top:8px;">{'新建' if z else 'Create'}</button>
        </div>
      </div>
      <div class="surface-card" style="padding:14px;">
        <strong style="font-size:13px;">{'加载状态' if z else 'Loading State'}</strong>
        <div style="display:grid;gap:8px;padding:12px 0;">
          <div style="height:12px;background:var(--bg-page);border-radius:999px;width:60%;"></div>
          <div style="height:12px;background:var(--bg-elevated);border-radius:999px;width:80%;"></div>
          <div style="height:12px;background:var(--bg-elevated);border-radius:999px;width:45%;"></div>
        </div>
      </div>
      <div class="surface-card" style="padding:14px;">
        <strong style="font-size:13px;">{'描述列表' if z else 'Description List'}</strong>
        <div style="display:grid;grid-template-columns:auto 1fr;gap:6px 12px;margin-top:8px;font-size:12px;">
          {desc_values}
        </div>
      </div>
    </div>
    """


def tag_spec_section(data: dict[str, Any], lang: str) -> str:
    """Section 3.4: Tag component specification."""
    z = lang == "zh"
    primary = token(data, "colors", "primary", "brand", fallback="var(--brand)")
    examples = component_example_mapping(data, "tag", "tags", "badge", "badges")
    radius_value, radius_source = documented_spec_value(
        data,
        ("tag", "tags", "badge", "badges"),
        ("radius", "borderRadius", "rounded"),
        "rounded",
        ("tag", "badge", "control", "sm"),
    )
    font_size_value, font_size_source = documented_spec_value(
        data,
        ("tag", "tags", "badge", "badges"),
        ("fontSize", "font-size", "textSize"),
        "typography",
        ("tag", "caption"),
    )
    height_value, height_source = documented_spec_value(
        data,
        ("tag", "tags", "badge", "badges"),
        ("height", "tagHeight", "badgeHeight"),
    )
    padding_value, padding_source = documented_spec_value(
        data,
        ("tag", "tags", "badge", "badges"),
        ("padding", "horizontalPadding", "paddingX"),
    )
    labels = {
        "default": component_example_text(examples, "default", "primary") or ("Default" if not z else "默认"),
        "success": component_example_text(examples, "success") or ("Success" if not z else "成功"),
        "warning": component_example_text(examples, "warning") or ("Warning" if not z else "警告"),
        "error": component_example_text(examples, "error", "danger") or ("Error" if not z else "错误"),
        "info": component_example_text(examples, "info") or ("Info" if not z else "信息"),
        "disabled": component_example_text(examples, "disabled") or ("Disabled" if not z else "禁用"),
    }
    source = "source-example" if examples else "neutral-state"

    return f"""
    <div class="tag-row" data-example-source="{source}">
      <span class="chip chip-primary">{html.escape(labels['default'])}</span>
      <span class="chip chip-success">{html.escape(labels['success'])}</span>
      <span class="chip chip-warning">{html.escape(labels['warning'])}</span>
      <span class="chip chip-danger">{html.escape(labels['error'])}</span>
      <span class="chip chip-info">{html.escape(labels['info'])}</span>
      <span class="chip chip-disabled">{html.escape(labels['disabled'])}</span>
    </div>
    <div class="comp-grid" style="margin-top:12px;">
      <div class="surface-card" style="padding:10px;">
        <strong style="font-size:12px;">{'圆角' if z else 'Radius'}</strong>
        <p style="font-size:13px;margin-top:4px;color:var(--text-primary);">{spec_value_markup(radius_value, radius_source, lang)}</p>
      </div>
      <div class="surface-card" style="padding:10px;">
        <strong style="font-size:12px;">{'字号' if z else 'Font Size'}</strong>
        <p style="font-size:13px;margin-top:4px;color:var(--text-primary);">{spec_value_markup(font_size_value, font_size_source, lang)}</p>
      </div>
      <div class="surface-card" style="padding:10px;">
        <strong style="font-size:12px;">{'高度' if z else 'Height'}</strong>
        <p style="font-size:13px;margin-top:4px;color:var(--text-primary);">{spec_value_markup(height_value, height_source, lang)}</p>
      </div>
      <div class="surface-card" style="padding:10px;">
        <strong style="font-size:12px;">{'文字左右间距' if z else 'Horizontal Padding'}</strong>
        <p style="font-size:13px;margin-top:4px;color:var(--text-primary);">{spec_value_markup(padding_value, padding_source, lang)}</p>
      </div>
    </div>
    """


def pagination_spec(data: dict[str, Any], lang: str) -> str:
    """Section 3.5: Pagination component."""
    z = lang == "zh"
    primary = token(data, "colors", "primary", "brand", fallback="var(--brand)")
    examples = component_example_mapping(data, "pagination", "pager")
    total_value = component_example_text(examples, "total", "totalCount", "summary")
    page_size_value = component_example_text(examples, "pageSize", "perPage")
    total_markup = spec_value_markup(total_value, "component" if total_value else "not-documented", lang)
    page_size_markup = spec_value_markup(page_size_value, "component" if page_size_value else "not-documented", lang)

    return f"""
    <div style="display:flex;flex-wrap:wrap;align-items:center;gap:10px;margin-top:10px;padding:12px;background:var(--bg-elevated);border:1px solid var(--border);border-radius:var(--radius-control);">
      <span style="font-size:12px;color:var(--text-muted);cursor:default;opacity:.5;">&lt; {'上一页' if z else 'Prev'}</span>
      <span style="display:inline-flex;align-items:center;justify-content:center;min-width:24px;height:24px;background:color-mix(in srgb, {primary} 12%, transparent);color:{primary};border-radius:4px;font-size:12px;font-weight:600;">1</span>
      <span style="font-size:12px;color:var(--text-muted);cursor:default;">2</span>
      <span style="font-size:12px;color:var(--text-muted);cursor:default;">3</span>
      <span style="font-size:12px;color:var(--text-muted);cursor:default;">4</span>
      <span style="font-size:12px;color:var(--text-muted);cursor:default;">5</span>
      <span style="font-size:12px;color:var(--text-muted);">...</span>
      <span style="font-size:12px;color:var(--text-muted);cursor:default;">10</span>
      <span style="font-size:12px;color:var(--text-muted);cursor:default;">{'下一页' if z else 'Next'} &gt;</span>
      <span style="font-size:12px;color:var(--text-muted);margin-left:4px;">{'总数' if z else 'Total'} {total_markup}</span>
    </div>
    <div style="display:flex;flex-wrap:wrap;gap:12px;margin-top:10px;font-size:12px;color:var(--text-muted);">
      <span>{'每页条数' if z else 'Per page'}: {page_size_markup}</span>
      <span>{'跳至' if z else 'Jump to'}: <input class="input-demo" style="width:50px;height:24px;padding:0 4px;font-size:12px;" value="1" /></span>
    </div>
    """


def tabs_spec(data: dict[str, Any], lang: str) -> str:
    """Section 3.6: Tabs specification."""
    z = lang == "zh"
    primary = token(data, "colors", "primary", "brand", fallback="var(--brand)")

    return f"""
    <div style="display:flex;gap:0;border-bottom:2px solid var(--border);margin-top:10px;">
      <span style="padding:8px 16px;font-size:13px;color:{primary};font-weight:600;border-bottom:2px solid {primary};margin-bottom:-2px;cursor:default;">{'标签一' if z else 'Tab 1'}</span>
      <span style="padding:8px 16px;font-size:13px;color:var(--text-muted);cursor:default;">{'标签二' if z else 'Tab 2'}</span>
      <span style="padding:8px 16px;font-size:13px;color:var(--text-muted);cursor:default;">{'标签三' if z else 'Tab 3'}</span>
      <span style="padding:8px 16px;font-size:13px;color:var(--text-muted);cursor:default;opacity:.45;">{'禁用' if z else 'Disabled'}</span>
    </div>
    <div style="margin-top:8px;font-size:13px;color:var(--text-muted);">
      <p>{('当前激活标签对应的面板内容。' if z else 'Content panel for the active tab.')}</p>
    </div>

    <h4 style="margin-top:16px;">{'顶部标签导航' if z else 'Top Tab Navigation'}</h4>
    <div style="display:flex;gap:4px;flex-wrap:wrap;margin-top:8px;padding:8px 12px;background:var(--bg-elevated);border:1px solid var(--border);border-radius:var(--radius-control);">
      <span style="padding:4px 12px;font-size:12px;background:var(--bg-surface);border-radius:var(--radius-control);color:var(--text-primary);cursor:default;">{'当前页面' if z else 'Current Page'}</span>
      <span style="padding:4px 12px;font-size:12px;color:var(--text-muted);cursor:default;">{'新页面' if z else 'New Page'}</span>
      <span style="padding:4px 12px;font-size:12px;color:var(--text-muted);cursor:default;">{'设置' if z else 'Settings'}</span>
    </div>
    """


def dialog_spec(data: dict[str, Any], lang: str) -> str:
    """Section 3.7: Dialog and drawer specification."""
    z = lang == "zh"
    primary = token(data, "colors", "primary", "brand", fallback="var(--brand)")
    dialog_width, dialog_width_source = documented_spec_value(
        data,
        ("dialog", "modal", "dialogs", "modals"),
        ("width", "defaultWidth", "dialogWidth", "modalWidth"),
    )
    dialog_max_height, dialog_max_height_source = documented_spec_value(
        data,
        ("dialog", "modal", "dialogs", "modals"),
        ("maxHeight", "max-height"),
    )
    dialog_radius, dialog_radius_source = documented_spec_value(
        data,
        ("dialog", "modal", "dialogs", "modals"),
        ("radius", "borderRadius", "rounded"),
        "rounded",
        ("modal", "dialog", "lg"),
    )
    drawer_width, drawer_width_source = documented_spec_value(
        data,
        ("drawer", "drawers"),
        ("width", "defaultWidth", "drawerWidth"),
    )
    drawer_usage, drawer_usage_source = documented_spec_value(
        data,
        ("drawer", "drawers"),
        ("usage", "use", "scenario", "description"),
    )

    return f"""
    <div class="comp-grid">
      <div class="surface-card" style="padding:16px;">
        <h4 style="margin:0 0 8px;">{'标准弹窗' if z else 'Standard Dialog'}</h4>
        <div style="border:1px solid var(--border);border-radius:var(--radius-card);overflow:hidden;background:var(--bg-surface);">
          <div style="display:flex;align-items:center;justify-content:space-between;padding:14px 16px;border-bottom:1px solid var(--border);">
            <strong style="font-size:14px;">{'弹窗标题' if z else 'Dialog Title'}</strong>
            <span style="color:var(--text-muted);cursor:default;">✕</span>
          </div>
          <div style="padding:16px;min-height:60px;">
            <p style="font-size:13px;color:var(--text-muted);">{('弹窗内容区域，可包含表单、表格或文案信息。' if z else 'Dialog content area, can contain forms, tables, or text.')}</p>
          </div>
          <div style="display:flex;justify-content:flex-end;gap:10px;padding:12px 16px;border-top:1px solid var(--border);">
            <button class="btn-sample default sm">{('取消' if z else 'Cancel')}</button>
            <button class="btn-sample primary sm">{('确认' if z else 'Confirm')}</button>
          </div>
        </div>
        <div class="comp-grid" style="margin-top:10px;">
          <div class="surface-card" style="padding:10px;">
            <strong style="font-size:12px;">{'弹窗宽度' if z else 'Dialog Width'}</strong>
            <p style="font-size:12px;margin-top:4px;color:var(--text-primary);">{spec_value_markup(dialog_width, dialog_width_source, lang)}</p>
          </div>
          <div class="surface-card" style="padding:10px;">
            <strong style="font-size:12px;">{'最大高度' if z else 'Max Height'}</strong>
            <p style="font-size:12px;margin-top:4px;color:var(--text-primary);">{spec_value_markup(dialog_max_height, dialog_max_height_source, lang)}</p>
          </div>
          <div class="surface-card" style="padding:10px;">
            <strong style="font-size:12px;">{'圆角' if z else 'Radius'}</strong>
            <p style="font-size:12px;margin-top:4px;color:var(--text-primary);">{spec_value_markup(dialog_radius, dialog_radius_source, lang)}</p>
          </div>
        </div>
      </div>

      <div class="surface-card" style="padding:16px;">
        <h4 style="margin:0 0 8px;">{'抽屉' if z else 'Drawer'}</h4>
        <div style="border:1px solid var(--border);border-radius:var(--radius-card);overflow:hidden;background:var(--bg-surface);border-left:4px solid {primary};">
          <div style="display:flex;align-items:center;justify-content:space-between;padding:14px 16px;border-bottom:1px solid var(--border);">
            <strong style="font-size:14px;">{'抽屉标题' if z else 'Drawer Title'}</strong>
            <span style="color:var(--text-muted);cursor:default;">✕</span>
          </div>
          <div style="padding:16px;display:grid;gap:10px;">
            <div><strong style="font-size:12px;color:var(--text-muted);">{('字段名' if z else 'Field')}:</strong> <span style="font-size:13px;color:var(--text-primary);">{('值' if z else 'Value')}</span></div>
            <div><strong style="font-size:12px;color:var(--text-muted);">{('字段名' if z else 'Field')}:</strong> <span style="font-size:13px;color:var(--text-primary);">{('值' if z else 'Value')}</span></div>
            <div><strong style="font-size:12px;color:var(--text-muted);">{('状态' if z else 'Status')}:</strong> <span class="chip chip-success">{('在线' if z else 'Online')}</span></div>
          </div>
          <div style="display:flex;justify-content:flex-end;gap:10px;padding:12px 16px;border-top:1px solid var(--border);">
            <button class="btn-sample default sm">{('取消' if z else 'Cancel')}</button>
            <button class="btn-sample primary sm">{('保存' if z else 'Save')}</button>
          </div>
        </div>
        <div class="comp-grid" style="margin-top:10px;">
          <div class="surface-card" style="padding:10px;">
            <strong style="font-size:12px;">{'抽屉宽度' if z else 'Drawer Width'}</strong>
            <p style="font-size:12px;margin-top:4px;color:var(--text-primary);">{spec_value_markup(drawer_width, drawer_width_source, lang)}</p>
          </div>
          <div class="surface-card" style="padding:10px;">
            <strong style="font-size:12px;">{'适用场景' if z else 'Usage'}</strong>
            <p style="font-size:12px;margin-top:4px;color:var(--text-primary);">{spec_value_markup(drawer_usage, drawer_usage_source, lang)}</p>
          </div>
        </div>
      </div>
    </div>
    """


def card_spec_section(data: dict[str, Any], lang: str) -> str:
    """Section 3.8: Card component specification."""
    z = lang == "zh"
    primary = token(data, "colors", "primary", "brand", fallback="var(--brand)")
    gap_value, gap_source = documented_spec_value(
        data,
        ("card", "cards", "metric", "metrics"),
        ("gap", "cardGap", "gridGap"),
        "spacing",
        ("card-gap", "cardGap"),
    )
    padding_value, padding_source = documented_spec_value(
        data,
        ("card", "cards", "metric", "metrics"),
        ("padding", "cardPadding"),
        "spacing",
        ("card-padding", "cardPadding"),
    )
    columns_value, columns_source = documented_spec_value(
        data,
        ("card", "cards", "metric", "metrics"),
        ("columns", "cardsPerRow", "perRow"),
    )
    radius_value, radius_source = documented_spec_value(
        data,
        ("card", "cards", "metric", "metrics"),
        ("radius", "borderRadius", "rounded"),
        "rounded",
        ("card", "md", "lg"),
    )
    cards, example_source = source_card_examples(data)

    def card_text(item: Any, *keys: str) -> str:
        if isinstance(item, dict):
            for key in keys:
                value = item.get(key)
                if isinstance(value, str) and value.strip():
                    return value.strip()
                if isinstance(value, (int, float)):
                    return str(value)
            return ""
        return str(item).strip()

    def render_info_card(index: int) -> str:
        item = cards[index] if index < len(cards) else {}
        title = card_text(item, "title", "name", "label")
        desc = card_text(item, "description", "desc", "summary", "body")
        action = card_text(item, "action", "cta")
        if not title and not desc:
            return f"""
        <div style="border:1px solid var(--border);border-radius:var(--radius-card);padding:14px;background:var(--bg-surface);" data-example-source="neutral-state">
          {skeleton_bar('58%')}
          <div style="margin-top:10px;">{skeleton_bar('88%')}</div>
          <div style="margin-top:8px;">{skeleton_bar('66%')}</div>
          <div style="display:flex;gap:8px;margin-top:14px;">{skeleton_bar('36%')}{skeleton_bar('28%')}</div>
        </div>"""
        action_html = f'<button class="btn-sample text sm">{html.escape(action)}</button>' if action else ""
        return f"""
        <div style="border:1px solid var(--border);border-radius:var(--radius-card);padding:14px;background:var(--bg-surface);" data-example-source="{example_source}">
          <strong style="font-size:14px;">{html.escape(title)}</strong>
          <p style="font-size:12px;margin-top:6px;color:var(--text-muted);">{html.escape(desc)}</p>
          <div style="display:flex;gap:8px;margin-top:10px;">{action_html}</div>
        </div>"""

    note = f'<div class="section-note" data-example-source="neutral-state">{neutral_state_note(lang)}</div>' if example_source == "neutral-state" else ""

    return f"""
    {note}
    <div class="comp-grid">
      <div class="surface-card" style="padding:16px;">
        <h4 style="margin:0 0 8px;">{'信息卡片' if z else 'Info Card'}</h4>
        {render_info_card(0)}
      </div>

      <div class="surface-card" style="padding:16px;">
        <h4 style="margin:0 0 8px;">{'指标卡片' if z else 'Metric Card'}</h4>
        <div style="border:1px solid var(--border);border-radius:var(--radius-card);padding:14px;background:var(--bg-surface);text-align:center;" data-example-source="{example_source}">
          <div style="font-size:12px;color:var(--text-muted);">{html.escape(card_text(cards[1], 'title', 'name', 'label') if len(cards) > 1 else '')}</div>
          <div style="font-size:28px;font-weight:700;color:var(--text-primary);margin:8px 0;">{html.escape(card_text(cards[1], 'value', 'count', 'metric') if len(cards) > 1 else '—')}</div>
          <div style="font-size:12px;color:var(--text-muted);">{html.escape(card_text(cards[1], 'description', 'summary', 'trend') if len(cards) > 1 else '')}</div>
        </div>
      </div>

      <div class="surface-card" style="padding:16px;">
        <h4 style="margin:0 0 8px;">{'操作卡片' if z else 'Action Card'}</h4>
        {render_info_card(2)}
      </div>
    </div>
    <div class="comp-grid" style="margin-top:12px;">
      <div class="surface-card" style="padding:10px;">
        <strong style="font-size:12px;">{('卡片间距' if z else 'Card Gap')}</strong>
        <p style="font-size:13px;margin-top:4px;color:var(--text-primary);">{spec_value_markup(gap_value, gap_source, lang)}</p>
      </div>
      <div class="surface-card" style="padding:10px;">
        <strong style="font-size:12px;">{('卡片内边距' if z else 'Card Padding')}</strong>
        <p style="font-size:13px;margin-top:4px;color:var(--text-primary);">{spec_value_markup(padding_value, padding_source, lang)}</p>
      </div>
      <div class="surface-card" style="padding:10px;">
        <strong style="font-size:12px;">{('一行推荐数量' if z else 'Cards per Row')}</strong>
        <p style="font-size:13px;margin-top:4px;color:var(--text-primary);">{spec_value_markup(columns_value, columns_source, lang)}</p>
      </div>
      <div class="surface-card" style="padding:10px;">
        <strong style="font-size:12px;">{('圆角' if z else 'Radius')}</strong>
        <p style="font-size:13px;margin-top:4px;color:var(--text-primary);">{spec_value_markup(radius_value, radius_source, lang)}</p>
      </div>
    </div>
    """


def template_pages_section(data: dict[str, Any], sections: dict[str, str], archetype: str, lang: str) -> str:
    """Section 4: Real page / template page examples based on product type."""
    z = lang == "zh"
    labels = LABELS[lang]

    if "enterprise" in archetype or archetype in ("admin",):
        return _enterprise_template_pages(data, sections, lang)
    elif "dashboard" in archetype or "analytics" in archetype:
        return _dashboard_template_pages(data, sections, lang)
    elif archetype == "brand-portfolio":
        return _brand_portfolio_template_pages(data, sections, lang)
    elif archetype in {"media-content", "content-resource-portal"}:
        return _media_content_template_pages(data, sections, lang)
    elif archetype == "marketing":
        return _marketing_template_pages(data, sections, lang)
    elif "mobile" in archetype:
        return _mobile_template_pages(data, sections, lang)
    elif "consumer" in archetype:
        return _mobile_template_pages(data, sections, lang)
    else:
        return _generic_template_pages(data, sections, lang)


def template_summary_cards(data: dict[str, Any], lang: str, fallback: list[tuple[str, str]]) -> str:
    z = lang == "zh"
    items: list[tuple[str, str]] = []
    templates = page_template_items(data)
    patterns = mapping(data, "pagePatterns")

    def _structure_hint(item: Any) -> str:
        if isinstance(item, dict):
            for key in ("type", "area", "key", "name", "title", "purpose", "description"):
                value = item.get(key)
                if value:
                    return str(value)
            compact = compact_value(item, data)
            return compact or ""
        if isinstance(item, str):
            return item
        rendered = compact_value(item, data)
        return rendered or ""

    for value in templates:
        title = str(value.get("name") or value.get("title") or value.get("id") or "").strip()
        summary = ""
        structure = value.get("structure") or value.get("sections")
        if isinstance(structure, list) and structure:
            summary = " · ".join(filter(None, (_structure_hint(item) for item in structure[:3])))
        elif value.get("purpose"):
            summary = str(value.get("purpose"))
        if title:
            items.append((title, summary or ("已记录模板结构" if z else "Template structure documented")))
        if len(items) >= 3:
            break

    for key, value in patterns.items():
        if len(items) >= 3:
            break
        title = str(key).replace("-", " ").replace("_", " ").strip()
        summary = ""
        if isinstance(value, dict):
            structure = value.get("structure")
            evidence = value.get("evidence")
            if isinstance(structure, list) and structure:
                summary = " · ".join(filter(None, (_structure_hint(item) for item in structure[:3])))
            elif evidence:
                summary = str(evidence)
        if title:
            items.append((title, summary or ("已记录模板结构" if z else "Template structure documented")))
    if not items:
        items = fallback[:3]
    cards = "".join(
        f"""
        <article>
          <strong>{html.escape(title)}</strong>
          <span>{html.escape(summary)}</span>
        </article>"""
        for title, summary in items
    )
    return f"""
    <div id="template-summary" class="section-note toc-anchor">{'先识别应复用的页面模板，再查看下方具体页面样例。' if z else 'Identify the page templates to reuse first, then inspect the rendered examples below.'}</div>
    <div class="template-summary">{cards}</div>
    """


def _brand_portfolio_template_pages(data: dict[str, Any], sections: dict[str, str], lang: str) -> str:
    """Brand/portfolio template pages without SaaS/admin fallback copy."""
    z = lang == "zh"
    labels = LABELS[lang]
    fallback = [
        (("待补充品牌页面模板" if z else "Brand page template required"), ("需要 sections/structure 与 sampleContent/sampleData" if z else "Requires sections/structure plus sampleContent/sampleData")),
    ]
    copy = (
        "当前 DESIGN.md 缺少可渲染的品牌 / 作品集页面模板；preview 不再套用通用个人作品集样例。"
        if z
        else "DESIGN.md lacks a renderable brand/portfolio page template; preview no longer injects a generic personal portfolio page."
    )
    return render_source_template_page_section(
        data, lang, "brand-portfolio", labels["marketing_pages"], copy, fallback,
        "hero", "portfolio", "brand", "landing", "作品", "品牌",
    )


def _media_content_template_pages(data: dict[str, Any], sections: dict[str, str], lang: str) -> str:
    """Media-content / content-portal template pages.

    Renders a representative content-feed page (topbar + channel tabs + main
    feed + right rail + footer) from the documented pageTemplates sampleContent.
    Falls back to neutral placeholders when sampleContent is missing.
    """
    z = lang == "zh"
    heading = "媒体内容 / 内容流模板页面" if z else "Media Content / Content Feed Pages"
    fallback = [
        (("待补充内容页模板" if z else "Content page template required"), ("需要 sections/structure 与 sampleContent/sampleData" if z else "Requires sections/structure plus sampleContent/sampleData")),
    ]
    copy = (
        "当前 DESIGN.md 缺少可渲染的内容页模板；preview 不再套用通用文章流、推荐挂件或页脚样例。"
        if z
        else "DESIGN.md lacks a renderable content page template; preview no longer injects generic feed, recommendation, or footer examples."
    )
    return render_source_template_page_section(
        data, lang, "media-content", heading, copy, fallback,
        "content", "feed", "article", "media", "portal", "内容", "文章",
    )

    primary = token(data, "colors", "primary", "brand", fallback="#4370F5")
    canvas = token(data, "colors", "canvas", "background", fallback="#F5F7FD")
    surface = token(data, "colors", "surface", "surfaceCard", fallback="#FFFFFF")
    footer_bg = token(data, "colors", "shellFooter", "footerBg", fallback="#222C3C")
    tag_bg = token(data, "colors", "tagBg", "borderLight", fallback="#F2F4F6")

    templates = data.get("pageTemplates") or []
    primary_template: dict[str, Any] = {}
    if isinstance(templates, list):
        for item in templates:
            if isinstance(item, dict):
                priority = str(item.get("priority", "")).lower()
                if priority == "primary":
                    primary_template = item
                    break
        if not primary_template and templates and isinstance(templates[0], dict):
            primary_template = templates[0]
    sample = primary_template.get("sampleContent") or primary_template.get("sampleData") or {}
    if not isinstance(sample, dict):
        sample = {}

    site_name = str(sample.get("siteName") or data.get("name") or ("内容门户" if z else "Content Portal"))
    tabs = sample.get("tabs") if isinstance(sample.get("tabs"), list) else None
    if not tabs:
        tabs = ["推荐", "最新", "热门", "知识体系"] if z else ["Recommended", "Latest", "Hot", "Topics"]
    articles_raw = sample.get("articles") if isinstance(sample.get("articles"), list) else []
    if not articles_raw:
        articles_raw = [
            {
                "category": "AI" if z else "AI",
                "title": "内容标题占位 A" if z else "Content title placeholder A",
                "excerpt": "占位摘要，实际渲染时取自 pageTemplates.sampleContent。" if z else "Placeholder excerpt; sourced from pageTemplates.sampleContent.",
                "author": "作者占位" if z else "Author placeholder",
                "tags": (["示例标签", "示例话题"] if z else ["sample-tag", "sample-topic"]),
            },
            {
                "category": "职场" if z else "Career",
                "title": "内容标题占位 B" if z else "Content title placeholder B",
                "excerpt": "占位摘要，实际渲染时取自 pageTemplates.sampleContent。" if z else "Placeholder excerpt; sourced from pageTemplates.sampleContent.",
                "author": "作者占位" if z else "Author placeholder",
                "tags": (["列表设计", "卡片规范"] if z else ["list-design", "card-spec"]),
            },
        ]

    quick_nav_raw = sample.get("quickNav") if isinstance(sample.get("quickNav"), list) else []
    quick_nav_cards = ""
    if quick_nav_raw:
        cards = []
        for group in quick_nav_raw[:3]:
            if not isinstance(group, dict):
                continue
            title = str(group.get("title") or "")
            links = group.get("links") or []
            if not isinstance(links, list):
                links = []
            chips = "".join(
                f'<span style="display:inline-block;padding:2px 8px;background:{tag_bg};border-radius:4px;font-size:12px;color:var(--text-muted);">{html.escape(str(link))}</span>'
                for link in links[:6]
            )
            cards.append(
                f'<div class="surface-card" style="padding:14px;display:grid;gap:8px;">'
                f'<strong style="font-size:13px;">{html.escape(title)}</strong>'
                f'<div style="display:flex;flex-wrap:wrap;gap:6px;">{chips}</div>'
                f"</div>"
            )
        if cards:
            quick_nav_cards = (
                f'<h4 style="margin-top:16px;">{"快捷导航" if z else "Quick Nav"}</h4>'
                f'<div class="comp-grid" style="margin-top:8px;">{"".join(cards)}</div>'
            )

    def render_article(item: Any) -> str:
        if not isinstance(item, dict):
            return ""
        title = html.escape(str(item.get("title") or ""))
        excerpt = html.escape(str(item.get("excerpt") or item.get("summary") or ""))
        category = html.escape(str(item.get("category") or ""))
        author = html.escape(str(item.get("author") or ""))
        tags_raw = item.get("tags") or []
        if not isinstance(tags_raw, list):
            tags_raw = []
        thumb = str(item.get("thumb") or item.get("image") or "").strip()
        tags_html = "".join(
            f'<span style="font-size:12px;padding:1px 8px;background:{tag_bg};border-radius:4px;color:var(--text-muted);">{html.escape(str(tag))}</span>'
            for tag in tags_raw[:4]
        )
        thumb_style = (
            f"background:#eef0f4 center/cover no-repeat url({html.escape(thumb)});"
            if thumb
            else "background:#eef0f4;"
        )
        category_badge = (
            f'<span style="position:absolute;top:8px;left:8px;font-size:12px;padding:1px 8px;background:rgba(0,0,0,0.55);color:#fff;border-radius:3px;">{category}</span>'
            if category
            else ""
        )
        return f"""
        <article style="display:grid;grid-template-columns:236px 1fr;gap:15px;padding:15px;background:{surface};border-radius:4px;box-shadow:0 1px 1px rgba(0,0,0,0.05);">
          <div style="width:236px;height:143px;border-radius:3px;position:relative;{thumb_style}">{category_badge}</div>
          <div style="display:grid;gap:8px;align-content:start;">
            <h5 style="margin:0;font-size:20px;line-height:1.4;color:var(--text-primary);">{title}</h5>
            <p style="margin:0;font-size:14px;line-height:1.5;color:var(--text-muted);">{excerpt}</p>
            <div style="display:flex;gap:8px;flex-wrap:wrap;">{tags_html}</div>
            <div style="font-size:12px;color:var(--text-muted);">{author}</div>
          </div>
        </article>
        """

    articles_html = "".join(render_article(item) for item in articles_raw[:3])

    tabs_html = "".join(
        f'<span style="padding:0 14px;line-height:50px;font-size:16px;color:{("var(--text-primary)" if i == 0 else "var(--text-muted)")};border-bottom:{("3px solid " + primary) if i == 0 else "none"};">{html.escape(str(t))}</span>'
        for i, t in enumerate(tabs[:6])
    )

    fallback = [
        (("首页内容流" if z else "Home Feed"), ("顶栏 + 频道 Tab + 文章列表 + 右侧挂件" if z else "Topbar + channel tabs + article list + right rail")),
        (("文章详情页" if z else "Article Detail"), ("标题 + 正文 + 作者卡 + 推荐挂件" if z else "Title + body + author card + recommendation rail")),
        (("分类 / 标签页" if z else "Category / Tag"), ("分类信息流，复用文章卡片组件" if z else "Category feed reusing article cards")),
    ]

    return f"""
    <section>
      <div class="section-head"><div><h3 style="margin:0;">{('媒体内容 / 内容流模板页面' if z else 'Media Content / Content Feed Pages')}</h3><p>{('基于已记录 pageTemplates 还原文章流页面骨架：顶栏 + 频道 Tab + 主信息流 + 右侧挂件 + 深色页脚。' if z else 'Reconstructs the content-feed page skeleton from documented pageTemplates: topbar, channel tabs, main feed, right rail, dark footer.')}</p></div></div>
      {template_summary_cards(data, lang, fallback)}

      <div id="template-examples" class="toc-anchor"></div>
      <h4>{('首页内容流样例' if z else 'Home Feed Sample')}</h4>
      <div style="margin-top:8px;background:{canvas};border:1px solid var(--border);border-radius:var(--radius-card);overflow:hidden;">
        <div style="background:{surface};border-bottom:1px solid var(--border);padding:0 24px;height:60px;display:flex;align-items:center;justify-content:space-between;">
          <div style="display:flex;align-items:center;gap:20px;">
            <strong style="font-size:16px;color:var(--text-primary);">{html.escape(site_name)}</strong>
            <span style="font-size:14px;color:var(--text-muted);">{('培训课程 · 分类浏览 · 活动' if z else 'Courses · Categories · Events')}</span>
          </div>
          <div style="display:flex;align-items:center;gap:12px;font-size:14px;color:var(--text-muted);">
            <span>{('搜索' if z else 'Search')}</span>
            <span style="padding:6px 14px;background:{primary};color:#fff;border-radius:4px;">{('发布' if z else 'Publish')}</span>
          </div>
        </div>
        <div style="background:{surface};border-bottom:1px solid var(--border);padding:0 24px;display:flex;align-items:stretch;">
          {tabs_html}
        </div>
        <div style="display:grid;grid-template-columns:1fr 280px;gap:20px;padding:20px 24px;">
          <div style="display:grid;gap:15px;">{articles_html}</div>
          <aside style="display:grid;gap:12px;align-content:start;">
            <div class="surface-card" style="padding:14px;">
              <strong style="font-size:13px;">{('推荐挂件 / Right Rail' if z else 'Recommendation / Right Rail')}</strong>
              <div style="display:grid;gap:8px;margin-top:8px;">
                <div style="display:grid;grid-template-columns:100px 1fr;gap:8px;align-items:center;">
                  <div style="width:100px;height:60px;background:#eef0f4;border-radius:3px;"></div>
                  <span style="font-size:13px;color:var(--text-primary);">{('内容占位' if z else 'Content placeholder')}</span>
                </div>
                <div style="display:grid;grid-template-columns:100px 1fr;gap:8px;align-items:center;">
                  <div style="width:100px;height:60px;background:#eef0f4;border-radius:3px;"></div>
                  <span style="font-size:13px;color:var(--text-primary);">{('内容占位' if z else 'Content placeholder')}</span>
                </div>
              </div>
            </div>
            <div class="surface-card" style="padding:14px;background:{tag_bg};">
              <strong style="font-size:13px;">{('公开课 / 会员等运营位' if z else 'Promo / Membership slot')}</strong>
            </div>
          </aside>
        </div>
        <div style="background:{footer_bg};color:#fff;opacity:.9;padding:20px 24px;font-size:13px;">{('页脚 / Site Footer — 链接区 + 版权条' if z else 'Site Footer — link grid + copyright bar')}</div>
      </div>
      {quick_nav_cards}
    </section>
    """


def _generic_template_pages(data: dict[str, Any], sections: dict[str, str], lang: str) -> str:
    """Neutral template page area for unknown archetypes."""
    z = lang == "zh"
    fallback = [
        (("待确认页面模板" if z else "Unconfirmed Page Template"), ("缺少足够布局证据" if z else "Insufficient layout evidence")),
    ]
    return f"""
    <section>
      <div class="section-head"><div><h3 style="margin:0;">{'页面模板' if z else 'Template Pages'}</h3><p>{'当前证据不足，不能安全套用后台、营销或移动端模板。' if z else 'Evidence is insufficient, so no admin, marketing, or mobile shell is invented.'}</p></div></div>
      {template_summary_cards(data, lang, fallback)}
      {layout_grid_spec(data, 'unknown', lang)}
    </section>
    """


def _enterprise_template_pages(data: dict[str, Any], sections: dict[str, str], lang: str) -> str:
    """Enterprise admin template pages."""
    z = lang == "zh"
    labels = LABELS[lang]
    renderable_templates = enterprise_renderable_templates(data)
    if renderable_templates:
        specimen = representative_specimen(data, sections, lang)
        selected = choose_enterprise_renderable_template(data, "tree-table", "tree", "table", "list", "management", "管理")
        sample = sample_mapping(selected)
        title = str(sample.get("title") or sample.get("pageTitle") or selected.get("name") or selected.get("id") or ("源产品页面样例" if z else "Source-Matched Page Specimen"))
        copy = (
            "以下样例严格由 DESIGN.md.pageTemplates 与 sampleContent 生成；URL/source 模式下禁止回退到通用企业后台文案。"
            if z else
            "The specimen below is generated strictly from DESIGN.md pageTemplates and sampleContent; URL/source modes do not fall back to generic admin copy."
        )
        fallback = [
            (str(template.get("name") or template.get("title") or template.get("id") or ("企业后台页面模板" if z else "Enterprise Page Template")), "sections/structure + sampleContent")
            for template in renderable_templates[:3]
        ]
        return f"""
    <section>
      <div class="section-head"><div><h3 style="margin:0;">{labels['enterprise_pages']}</h3><p>{html.escape(copy)}</p></div></div>
      {template_summary_cards(data, lang, fallback)}

      <div id="template-examples" class="toc-anchor"></div>
      <h4 style="margin-top:16px;">{html.escape(title)}</h4>
      {specimen}
    </section>
    """

    fallback = [
        (
            "待补充企业后台页面模板" if z else "Enterprise page template required",
            "需要 sections/structure 与 sampleContent/sampleData" if z else "Requires sections/structure plus sampleContent/sampleData",
        )
    ]
    copy = (
        "当前 DESIGN.md 缺少可渲染的企业后台页面模板；preview 不再套用通用后台表格、弹窗或抽屉样例。"
        if z
        else "DESIGN.md lacks a renderable enterprise page template; preview no longer injects generic admin table, modal, or drawer examples."
    )
    return f"""
    <section>
      <div class="section-head"><div><h3 style="margin:0;">{labels['enterprise_pages']}</h3><p>{html.escape(copy)}</p></div></div>
      {template_summary_cards(data, lang, fallback)}

      <div id="template-examples" class="toc-anchor"></div>
      {enterprise_admin_specimen(data, lang)}
    </section>
    """


def _marketing_template_pages(data: dict[str, Any], sections: dict[str, str], lang: str) -> str:
    """Marketing site template pages."""
    z = lang == "zh"
    labels = LABELS[lang]
    fallback = [
        (("待补充营销页面模板" if z else "Marketing page template required"), ("需要 sections/structure 与 sampleContent/sampleData" if z else "Requires sections/structure plus sampleContent/sampleData")),
    ]
    copy = (
        "当前 DESIGN.md 缺少可渲染的营销页模板；preview 不再套用通用落地页、功能卡或 CTA 样例。"
        if z
        else "DESIGN.md lacks a renderable marketing page template; preview no longer injects generic landing, feature-card, or CTA examples."
    )
    return render_source_template_page_section(
        data, lang, "marketing", labels["marketing_pages"], copy, fallback,
        "hero", "landing", "marketing", "conversion", "cta", "营销",
    )


def _dashboard_template_pages(data: dict[str, Any], sections: dict[str, str], lang: str) -> str:
    """Data dashboard template pages."""
    z = lang == "zh"
    labels = LABELS[lang]
    fallback = [
        (("待补充仪表盘模板" if z else "Dashboard page template required"), ("需要 sections/structure 与 sampleContent/sampleData" if z else "Requires sections/structure plus sampleContent/sampleData")),
    ]
    copy = (
        "当前 DESIGN.md 缺少可渲染的仪表盘模板；preview 不再套用通用指标、趋势或告警样例。"
        if z
        else "DESIGN.md lacks a renderable dashboard page template; preview no longer injects generic metrics, trend, or alert examples."
    )
    return render_source_template_page_section(
        data, lang, "dashboard", labels["dashboard_pages"], copy, fallback,
        "dashboard", "overview", "metrics", "analytics", "chart", "仪表盘", "指标",
    )


def _mobile_template_pages(data: dict[str, Any], sections: dict[str, str], lang: str) -> str:
    """Mobile app template pages."""
    z = lang == "zh"
    labels = LABELS[lang]
    fallback = [
        (("待补充移动端模板" if z else "Mobile page template required"), ("需要 sections/structure 与 sampleContent/sampleData" if z else "Requires sections/structure plus sampleContent/sampleData")),
    ]
    copy = (
        "当前 DESIGN.md 缺少可渲染的移动端模板；preview 不再套用通用移动首页或列表样例。"
        if z
        else "DESIGN.md lacks a renderable mobile page template; preview no longer injects generic mobile home or list examples."
    )
    return render_source_template_page_section(
        data, lang, "mobile", labels["mobile_pages"], copy, fallback,
        "mobile", "home", "feed", "list", "detail", "移动", "首页",
    )


def first_mapping_name(*groups: dict[str, Any]) -> str:
    for group in groups:
        for key in group:
            return str(key)
    return "table-management"


def _example_slug(value: Any) -> str:
    text = re.sub(r"([a-z0-9])([A-Z])", r"\1-\2", str(value or ""))
    text = re.sub(r"[\s_]+", "-", text.strip()).lower()
    text = re.sub(r"[^a-z0-9\u4e00-\u9fff\-]+", "-", text)
    return re.sub(r"-{2,}", "-", text).strip("-") or "section"


def _example_items(value: Any) -> list[Any]:
    if isinstance(value, list):
        return value
    if isinstance(value, (dict, str)):
        return [value]
    return []


def _example_archetype_from_text(text: str) -> str:
    lowered = str(text or "").lower()
    if lowered.startswith("custom:"):
        return lowered
    checks = (
        ("content-resource-portal", ("content-resource-portal", "资源门户", "资源库", "数字资源", "档案", "素材库", "专题展")),
        ("media-content", ("media-content", "media content", "news", "content portal", "content community", "媒体内容", "资讯门户", "内容社区", "媒体资讯", "新闻", "视频", "播客", "内容流", "文章流")),
        ("brand-portfolio", ("brand-portfolio", "作品集", "个人品牌", "portfolio", "creator")),
        ("marketing-site", ("marketing-site", "landing", "pricing", "cta", "营销", "落地页", "官网")),
        ("mobile-app", ("mobile-app", "移动端", "tabbar", "ios", "android")),
        ("data-screen", ("data-screen", "大屏", "全屏", "监控大屏", "告警", "实时")),
        ("aigc-workbench", ("aigc-workbench", "aigc", "prompt", "参数", "结果预览", "任务历史")),
        ("chat-agent", ("chat-agent", "copilot", "对话", "聊天", "assistant", "客服", "知识问答")),
        ("docs-portal", ("docs-portal", "documentation", "api 文档", "文档站", "开发者中心", "docs")),
        ("workflow-automation", ("workflow-automation", "流程编排", "节点画布", "执行记录", "automation")),
        ("editor-workbench", ("editor-workbench", "editor canvas", "属性面板", "工具栏画布", "节点编辑器")),
        ("settings-admin", ("settings-admin", "设置中心", "账号", "组织", "权限", "计费", "billing")),
        ("enterprise-admin", ("enterprise-admin", "后台", "管理", "crud", "审批", "配置", "任务", "表管理")),
        ("analytics-dashboard", ("analytics-dashboard", "dashboard", "analytics", "metric", "chart", "仪表盘", "指标", "趋势")),
        ("ecommerce", ("ecommerce", "商品", "购物车", "订单", "sku")),
        ("marketplace", ("marketplace", "房源", "课程", "服务", "人才", "匹配", "listing")),
        ("file-asset-manager", ("file-asset-manager", "文件库", "素材", "上传", "版本管理")),
    )
    for archetype, terms in checks:
        if any(term in lowered for term in terms):
            return archetype
    return "enterprise-admin" if any(term in lowered for term in ("admin", "management")) else "analytics-dashboard"


def _example_archetype(data: dict[str, Any]) -> str:
    explicit_type = str(data.get("productType", "")).strip()
    if explicit_type:
        explicit_result = _example_archetype_from_text(explicit_type)
        if explicit_result != "analytics-dashboard" or any(term in explicit_type.lower() for term in ("analytics", "dashboard", "指标", "仪表盘")):
            return explicit_result
    explicit_interface = str(data.get("interfaceArchetype", "")).strip()
    if explicit_interface:
        interface_result = _example_archetype_from_text(explicit_interface)
        if interface_result != "analytics-dashboard" or any(term in explicit_interface.lower() for term in ("analytics", "dashboard", "指标", "仪表盘")):
            return interface_result
    text = " ".join(
        [
            str(data.get("description", "")),
            collect_text(data.get("pageTemplates", "")),
            collect_text(data.get("pagePatterns", "")),
        ]
    )
    return _example_archetype_from_text(text)


def _example_template_sections(template: dict[str, Any]) -> list[str]:
    raw = template.get("_sections", template.get("sections", template.get("structure", [])))
    result: list[str] = []
    for item in _example_items(raw):
        if isinstance(item, dict):
            if "type" in item:
                result.append(_example_slug(item.get("type")))
            elif len(item) == 1:
                result.append(_example_slug(next(iter(item.keys()))))
            else:
                result.extend(_example_slug(key) for key in item.keys())
        else:
            result.append(_example_slug(item))
    return [item for item in result if item]


def _example_page_templates(data: dict[str, Any]) -> list[dict[str, Any]]:
    templates: list[dict[str, Any]] = []
    raw = data.get("pageTemplates")
    if isinstance(raw, dict):
        iterable = raw.items()
    elif isinstance(raw, list):
        iterable = ((str(index), item) for index, item in enumerate(raw))
    else:
        iterable = []
    for key, item in iterable:
        if not isinstance(item, dict):
            continue
        template_key = str(item.get("key") or item.get("id") or item.get("name") or item.get("title") or "").strip()
        if not template_key:
            template_key = _example_slug(f"template-{key}")
        raw_sections = item.get("sections", item.get("structure", []))
        sections = _example_template_sections(item)
        templates.append({**item, "_key": template_key, "_sections": sections, "_raw_sections": raw_sections})
    return templates


def _example_page_patterns(data: dict[str, Any]) -> list[dict[str, Any]]:
    patterns: list[dict[str, Any]] = []
    raw = data.get("pagePatterns")
    if isinstance(raw, dict):
        for key, item in raw.items():
            if isinstance(item, dict):
                patterns.append({**item, "_key": str(key), "_sections": _example_template_sections(item)})
            else:
                patterns.append({"_key": str(key), "description": str(item), "_sections": _example_template_sections(item)})
    return patterns


def _example_pick_template(data: dict[str, Any], archetype: str) -> tuple[dict[str, Any] | None, str]:
    templates = _example_page_templates(data)
    usable = [item for item in templates if item.get("_sections")]
    if usable:
        same = [
            item for item in usable
            if not item.get("archetype") or _example_archetype_from_text(str(item.get("archetype"))) == archetype
        ]
        candidates = same or usable
        primary = [item for item in candidates if str(item.get("priority", "")).lower() == "primary"]
        return sorted(primary or candidates, key=lambda item: -len(item.get("_sections", [])))[0], "pageTemplates"
    patterns = _example_page_patterns(data)
    usable_patterns = [item for item in patterns if item.get("_sections") or item.get("_key")]
    if usable_patterns:
        return usable_patterns[0], "pagePatterns"
    return None, "inferred"


def _example_list_strings(value: Any) -> list[str]:
    if isinstance(value, list):
        return [str(item).strip() for item in value if str(item).strip()]
    if isinstance(value, dict):
        return [str(key).strip() for key in value.keys() if str(key).strip()]
    if isinstance(value, str) and value.strip():
        return [value.strip()]
    return []


def _example_sample(value: Any) -> dict[str, Any]:
    return value if isinstance(value, dict) else {}


def _example_first_mapping(value: Any) -> dict[str, Any] | None:
    if isinstance(value, list):
        for item in value:
            if isinstance(item, dict):
                return item
    if isinstance(value, dict):
        for item in value.values():
            if isinstance(item, dict):
                return item
    return None


def _example_section_type_from_component(name: str) -> str:
    text = _example_slug(name)
    if any(term in text for term in ("search", "filter", "input", "field", "form")):
        return "search-toolbar"
    if "table" in text:
        return "data-table"
    if any(term in text for term in ("tab", "channel", "nav")):
        return "channel-tabs"
    if any(term in text for term in ("article", "feed", "post")):
        return "article-feed"
    if any(term in text for term in ("resource-card", "asset-card")):
        return "resource-card-grid"
    if any(term in text for term in ("card", "panel", "surface")):
        return "card-grid"
    if any(term in text for term in ("metric", "kpi")):
        return "metric-grid"
    if "chart" in text:
        return "chart-panel"
    if any(term in text for term in ("prompt", "textarea")):
        return "prompt-input"
    if any(term in text for term in ("chat", "conversation")):
        return "chat-thread"
    if any(term in text for term in ("map", "geo")):
        return "map-panel"
    if any(term in text for term in ("button", "action", "toolbar")):
        return "action-toolbar"
    return text


def _example_component_patterns(data: dict[str, Any]) -> list[str]:
    names: list[str] = []
    for key in ("components", "componentRecipes", "componentMappings"):
        value = data.get(key)
        if isinstance(value, dict):
            names.extend(str(name) for name in value.keys())
    result: list[str] = []
    for name in names:
        section_type = _example_section_type_from_component(name)
        if section_type and section_type not in result:
            result.append(section_type)
    return result[:6]


def _example_pattern_sections(data: dict[str, Any]) -> tuple[list[str], str, str]:
    selected, source = _example_pick_template(data, _example_archetype(data))
    if selected:
        key = str(selected.get("_key") or selected.get("key") or selected.get("id") or selected.get("name") or source)
        return _example_list_strings(selected.get("_sections")), key, source
    patterns = _example_page_patterns(data)
    if patterns:
        first = patterns[0]
        key = str(first.get("_key") or "pagePatterns")
        return _example_list_strings(first.get("_sections")), key, "pagePatterns"
    component_patterns = _example_component_patterns(data)
    if component_patterns:
        return component_patterns, "components", "components"
    return [], "insufficient-design-md", "fallback-insufficient-design-md"


def _example_infer_request_text(
    data: dict[str, Any],
    lang: str,
    target_page: str,
    capabilities: list[str],
) -> str:
    z = lang == "zh"
    product_name = str(data.get("name") or ("当前产品" if z else "the product")).strip()
    use_cases = _example_list_strings(mapping(data, "product").get("primaryUseCases") or data.get("primaryUseCases"))
    if not capabilities:
        capabilities = use_cases[:4]
    capability_text = "、".join(capabilities[:5]) if z else ", ".join(capabilities[:5])
    if not capability_text:
        capability_text = "核心业务能力" if z else "the core product capabilities"
    if z:
        return f"基于 {product_name} 的设计规范，生成一个{target_page}，需要覆盖{capability_text}，并严格遵守 DESIGN.md 中的布局、组件、令牌和禁用规则。"
    return f"Create a {target_page} for {product_name} that covers {capability_text} and follows the layout, components, tokens, and forbidden patterns in DESIGN.md."


def infer_prototype_example(data: dict[str, Any], sections: dict[str, str]) -> dict[str, Any]:
    lang = detect_language(data, " ".join(sections.values()))
    z = lang == "zh"
    patterns, pattern_key, pattern_source = _example_pattern_sections(data)
    template = None
    for item in _example_page_templates(data):
        if str(item.get("_key", "")) == pattern_key:
            template = item
            break
    target_page = str(
        (template or {}).get("name")
        or (template or {}).get("title")
        or mapping(data, "product").get("type")
        or data.get("productType")
        or ("代表性原型页面" if z else "representative prototype page")
    )
    capabilities = (
        _example_list_strings((template or {}).get("appliesTo"))
        or _example_list_strings(mapping(data, "product").get("primaryUseCases") or data.get("primaryUseCases"))
        or _example_list_strings(patterns)
    )
    example = {
        "id": "generated-representative-example",
        "source": "generated-from-design-md",
        "targetUser": mapping(data, "product").get("targetUser") or ("目标用户" if z else "target user"),
        "targetPage": target_page,
        "requiredCapabilities": capabilities[:6],
        "expectedPatterns": patterns,
        "rationale": (
            "根据 DESIGN.md 中的产品画像、主要使用场景、页面模式和组件描述自动推导，用于验证 DESIGN.md 是否能约束典型页面生成。"
            if z
            else "Inferred from the product profile, primary use cases, page patterns, and components in DESIGN.md to validate whether DESIGN.md constrains a typical generated page."
        ),
        "patternKey": pattern_key,
        "patternSource": pattern_source,
    }
    example["userRequest"] = _example_infer_request_text(data, lang, target_page, capabilities)
    if not str(example.get("userRequest", "")).strip():
        example["userRequest"] = _example_infer_request_text(
            data,
            lang,
            str(example.get("targetPage") or ("代表性原型页面" if z else "representative prototype page")),
            _example_list_strings(example.get("requiredCapabilities")),
        )
    return example


def _example_normalize_section(section: Any, sample: dict[str, Any] | None = None) -> list[dict[str, Any]]:
    sample = sample or {}
    if isinstance(section, str):
        return [{"type": _example_slug(section)}]
    if not isinstance(section, dict):
        return [{"type": _example_slug(section)}]
    control_keys = {
        "type", "area", "key", "name", "title", "purpose", "description", "sampleContent",
        "sampleData", "layout", "components", "evidence", "confidence", "fields", "columns",
        "rows", "tabs", "articles", "cards",
    }
    nested: list[Any] = []
    for key in ("sections", "children", "blocks"):
        if isinstance(section.get(key), list):
            nested.extend(section[key])
    for key in ("left", "right", "main", "aside", "header", "footer"):
        value = section.get(key)
        if isinstance(value, list):
            nested.extend(value)
        elif isinstance(value, dict):
            nested.append(value)
    if nested and str(section.get("type", section.get("area", ""))).strip().lower() in {"", "content", "layout", "main"}:
        expanded: list[dict[str, Any]] = []
        for item in nested:
            expanded.extend(_example_normalize_section(item, sample))
        return expanded
    if len(section) == 1:
        key, value = next(iter(section.items()))
        normalized: dict[str, Any] = {"type": _example_slug(key)}
        if isinstance(value, dict):
            normalized.update(value)
        elif str(value).strip():
            normalized["description"] = str(value).strip()
        return [normalized]
    normalized = dict(section)
    if "type" not in normalized:
        semantic_keys = [key for key in section.keys() if key not in control_keys]
        if semantic_keys:
            key = semantic_keys[0]
            normalized["type"] = _example_slug(key)
            value = section.get(key)
            if isinstance(value, dict):
                normalized.update(value)
            elif str(value).strip():
                normalized.setdefault("description", str(value).strip())
        elif "area" in normalized:
            normalized["type"] = normalized["area"]
        elif "name" in normalized:
            normalized["type"] = normalized["name"]
    normalized["type"] = _example_slug(normalized.get("type"))
    return [normalized]


def _example_find_sections_for_patterns(
    data: dict[str, Any],
    patterns: list[str],
) -> tuple[list[Any], str, str, dict[str, Any]]:
    pattern_slugs = [_example_slug(pattern) for pattern in patterns if str(pattern).strip()]
    pattern_slug_set = set(pattern_slugs)
    templates = _example_page_templates(data)
    if pattern_slug_set:
        for template in templates:
            section_slugs = {_example_slug(section) for section in _example_list_strings(template.get("_sections"))}
            if section_slugs & pattern_slug_set:
                return (
                    list(_example_items(template.get("_raw_sections"))) or list(template.get("_sections", [])),
                    str(template.get("_key") or "pageTemplates"),
                    "pageTemplates",
                    _example_sample(template.get("sampleContent") or template.get("sampleData")),
                )
    selected, source = _example_pick_template(data, _example_archetype(data))
    if selected:
        return (
            list(_example_items(selected.get("_raw_sections"))) or list(selected.get("_sections", [])),
            str(selected.get("_key") or source),
            source,
            _example_sample(selected.get("sampleContent") or selected.get("sampleData")),
        )
    if pattern_slugs:
        return list(pattern_slugs), "generation-input.expectedPatterns", "generation-input", {}
    return [], "insufficient-design-md", "fallback-insufficient-design-md", {}


def derive_sections_from_example(
    data: dict[str, Any],
    example: dict[str, Any],
    lang: str,
) -> tuple[list[dict[str, Any]], str, str]:
    sample = _example_sample(example.get("sampleContent") or example.get("sampleData"))
    expected_patterns = _example_list_strings(example.get("expectedPatterns"))
    raw_sections, pattern_key, pattern_source, template_sample = _example_find_sections_for_patterns(data, expected_patterns)
    if not sample:
        sample = template_sample
    sections: list[dict[str, Any]] = []
    for raw in raw_sections:
        sections.extend(_example_normalize_section(raw, sample))
    for section in sections:
        if sample and "sampleContent" not in section and "sampleData" not in section:
            section["sampleContent"] = sample
        stype = _example_slug(section.get("type"))
        if "title" not in section:
            section["title"] = section.get("name") or section.get("label") or stype
        if stype in {"search-toolbar", "filter-toolbar", "mobile-filter"}:
            fields = section.get("fields") or sample.get("fields") or sample.get("filters")
            if fields:
                section["fields"] = fields
        if stype in {"data-table", "history-table", "alert-table", "resource-results"}:
            for key in ("columns", "rows"):
                if key not in section and sample.get(key):
                    section[key] = sample[key]
        if stype == "channel-tabs" and "tabs" not in section and sample.get("tabs"):
            section["tabs"] = sample["tabs"]
        if stype == "article-feed" and "articles" not in section and sample.get("articles"):
            section["articles"] = sample["articles"]
        if stype in {"quick-entry-cards", "card-grid"} and "cards" not in section:
            cards = sample.get("cards") or sample.get("quickCards")
            if cards:
                section["cards"] = cards
    if not sections:
        message = (
            "DESIGN.md 没有提供足够的 pageTemplates、pagePatterns 或组件结构，无法可靠生成示例页面。"
            if lang == "zh"
            else "DESIGN.md does not provide enough pageTemplates, pagePatterns, or component structure to generate a reliable example page."
        )
        sections = [{"type": "diagnostic", "title": "DESIGN.md 生成能力不足" if lang == "zh" else "Insufficient DESIGN.md", "description": message}]
        pattern_key = "insufficient-design-md"
        pattern_source = "fallback-insufficient-design-md"
    return sections, pattern_key, pattern_source


def _example_generation_rules(data: dict[str, Any], key: str) -> list[str]:
    rules = data.get("generationRules", data.get("aiGenerationRules", {}))
    if isinstance(rules, dict):
        value = rules.get(key)
    else:
        value = rules
    return [line.strip(" -") for line in re.split(r"[\n。；;]+", collect_text(value)) if line.strip()][:6]


def build_example_scenario(data: dict[str, Any], sections: dict[str, str]) -> dict[str, Any]:
    example = infer_prototype_example(data, sections)
    lang = detect_language(data, collect_text(example))
    archetype = _example_archetype(data)
    evidence = mapping(data, "evidence")
    page_sections, pattern_key, pattern_source = derive_sections_from_example(data, example, lang)
    user_request = str(example.get("userRequest", "")).strip()
    target_page = str(example.get("targetPage") or example.get("pageName") or example.get("title") or pattern_key).strip()
    capabilities = _example_list_strings(example.get("requiredCapabilities"))
    design_rules = _example_generation_rules(data, "must")
    forbidden_rules = _example_generation_rules(data, "mustNot")
    if not design_rules:
        design_rules = [str(rule) for rule in _example_list_strings(mapping(data, "generationRules").get("selfCheck"))[:3]]
    if not design_rules:
        design_rules = ["Use DESIGN.md tokens, layout, components, page patterns, and forbidden rules."]
    reason = str(example.get("rationale") or "").strip()
    if not reason:
        reason = (
            "示例需求由 DESIGN.md 自动推导；页面用于检验该规范能否约束下游原型生成。"
            if lang == "zh"
            else "The example request is inferred from DESIGN.md to verify whether the specification constrains downstream prototype generation."
        )
    return {
        "pageName": target_page,
        "archetype": archetype,
        "reason": reason,
        "source": {
            "productType": str(data.get("productType", "")),
            "interfaceArchetype": str(data.get("interfaceArchetype", "")),
            "template": pattern_key,
            "templateSource": pattern_source,
            "inputSource": str(example.get("source") or "generated-from-design-md"),
            "evidenceMode": str(evidence.get("mode", "")),
        },
        "generationInput": {
            "source": str(example.get("source") or "generated-from-design-md"),
            "userRequest": user_request,
            "targetUser": str(example.get("targetUser", "")),
            "targetPage": target_page,
            "requiredCapabilities": capabilities,
            "expectedPatterns": _example_list_strings(example.get("expectedPatterns")),
            "designRulesUsed": design_rules,
            "forbiddenRulesApplied": forbidden_rules,
            "rationale": reason,
        },
        "pageGoal": user_request,
        "sections": page_sections,
        "interactions": capabilities,
        "designRulesUsed": design_rules,
        "forbiddenRulesApplied": forbidden_rules,
        "navigation": _example_list_strings(example.get("navigation")),
        "sidebar": _example_list_strings(example.get("sidebar")),
    }


def _example_shell_tokens(data: dict[str, Any]) -> dict[str, str]:
    shell = shell_metrics(data)
    runtime_text = collect_text(data.get("runtime", "")) + " " + collect_text(data.get("patterns", "")) + " " + collect_text(data.get("layoutRules", ""))
    has_tags = bool(shell.get("has_tags")) or any(term in runtime_text.lower() for term in ("tags", "tab bar", "标签栏", "页签"))
    return {
        "topbar_height": _example_css_length(_example_lookup(data, "layoutRules.appShell.topbar.height", "layoutRules.appShell.topBar.height", "layoutRules.appShell.topNav.height") or shell.get("topbar"), "64px"),
        "topbar_bg": _example_lookup(data, "layoutRules.appShell.topbar.background", "layoutRules.appShell.topBar.background", "layoutRules.appShell.topNav.background", "recommendedTokens.color.topbar") or resolve_color_nested(data, "shell-topbar", "topbar", "topbar-bg", "primary", fallback="#001D66"),
        "topbar_text": _example_lookup(data, "layoutRules.appShell.topbar.textColor", "layoutRules.appShell.topBar.textColor", "layoutRules.appShell.topNav.textColor") or "#ffffff",
        "sidebar_width": _example_css_length(_example_lookup(data, "layoutRules.appShell.sidebar.width", "recommendedTokens.layout.sidebarWidth") or shell.get("sidebar"), "240px"),
        "sidebar_collapsed": _example_css_length(_example_lookup(data, "layoutRules.appShell.sidebar.collapsedWidth", "recommendedTokens.layout.sidebarCollapsedWidth") or shell.get("sidebar_collapsed"), "80px"),
        "sidebar_bg": _example_lookup(data, "layoutRules.appShell.sidebar.background", "recommendedTokens.color.sidebar") or resolve_color_nested(data, "shell-sidebar", "sidebar", "surface-1", fallback="#ffffff"),
        "sidebar_active": _example_lookup(data, "layoutRules.appShell.sidebar.activeBg") or resolve_color_nested(data, "secondary-01", fallback="#e6f4ff"),
        "tags_height": _example_css_length(_example_lookup(data, "layoutRules.appShell.tags.height", "layoutRules.appShell.tagsView.height") or ("32px" if has_tags else shell.get("tags")), "32px" if has_tags else "0px"),
        "tags_bg": _example_lookup(data, "layoutRules.appShell.tags.background", "layoutRules.appShell.tagsView.background") or resolve_color_nested(data, "shell-tags", "shell-topbar", fallback="#001D66"),
        "canvas": _example_lookup(data, "layoutRules.appShell.content.canvas", "recommendedTokens.color.canvas") or resolve_color_nested(data, "canvas", "surface-canvas", fallback="#f0f2f5"),
    }


def render_example_from_scenario(data: dict[str, Any], scenario: dict[str, Any]) -> str:
    lang = detect_language(data, collect_text(scenario))
    z = lang == "zh"
    name = html.escape(str(data.get("name", "Design System")))
    page_name = html.escape(str(scenario.get("pageName", "Prototype Example")))
    archetype = str(scenario.get("archetype", "enterprise-admin"))
    source = scenario.get("source", {}) if isinstance(scenario.get("source"), dict) else {}
    generation_input = scenario.get("generationInput", {}) if isinstance(scenario.get("generationInput"), dict) else {}
    pattern = str(source.get("template") or "inferred/fallback")
    pattern_source = str(source.get("templateSource") or "inferred")
    shell = _example_shell_tokens(data)
    primary = _example_lookup(data, "recommendedTokens.color.primary") or resolve_color_nested(data, "primary", "brand", fallback="#003EB3")
    primary_hover = resolve_color_nested(data, "primary-hover", fallback="#0958d9")
    surface = _example_lookup(data, "recommendedTokens.color.surface") or resolve_color_nested(data, "surface-1", "surface", fallback="#ffffff")
    elevated = resolve_color_nested(data, "surface-2", "surface-soft", fallback="#f5f5f5")
    border = _example_lookup(data, "recommendedTokens.color.border") or resolve_color_nested(data, "hairline", "border", fallback="#d9d9d9")
    ink = _example_lookup(data, "recommendedTokens.color.text") or resolve_color_nested(data, "ink", "text-primary", fallback="rgba(0,0,0,0.68)")
    ink_heavy = resolve_color_nested(data, "ink-heavy", "text-heading", fallback="rgba(0,0,0,0.83)")
    muted = _example_lookup(data, "recommendedTokens.color.placeholder") or resolve_color_nested(data, "ink-muted", "text-muted", fallback="rgba(0,0,0,0.4)")
    radius = _example_css_length(token(data, "rounded", "sm", "md", fallback="4px"), "4px")
    card_radius = _example_css_length(token(data, "rounded", "lg", "md", fallback="8px"), "8px")
    gap = _example_css_length(token(data, "spacing", "lg", "md", fallback="16px"), "16px")
    body_type = first_typography(data, "body")
    font = html.escape(str(body_type.get("fontFamily", 'system-ui, -apple-system, BlinkMacSystemFont, "Segoe UI", sans-serif')))
    scenario_json = json.dumps(scenario, ensure_ascii=False, indent=2).replace("</", "<\\/")
    generation_input_json = json.dumps(generation_input, ensure_ascii=False, indent=2).replace("</", "<\\/")
    nav_items = [str(item) for item in scenario.get("navigation", []) if str(item).strip()][:6]
    side_items = [str(item) for item in scenario.get("sidebar", []) if str(item).strip()][:8]

    def esc(value: Any) -> str:
        return html.escape(str(value or ""))

    def render_fields(fields: list[Any]) -> str:
        return "".join(
            f'<label><span>{esc(field)}</span><input value="{esc(_example_field_value(str(field), z))}" /></label>'
            for field in fields[:6]
        )

    def render_table(section: dict[str, Any], *, compact: bool = False) -> str:
        columns = [str(item) for item in section.get("columns", [])][:10]
        rows = section.get("rows", [])
        if not columns and rows and isinstance(rows[0], list):
            columns = [f"字段 {index + 1}" for index in range(len(rows[0]))] if z else [f"Field {index + 1}" for index in range(len(rows[0]))]
        head = "".join(f"<th>{esc(col)}</th>" for col in columns)
        body = ""
        for row in rows[:5] if isinstance(rows, list) else []:
            values = row if isinstance(row, list) else list(row.values()) if isinstance(row, dict) else [row]
            cells = "".join(f"<td>{esc(value)}</td>" for value in values[: len(columns) or 6])
            body += f"<tr>{cells}</tr>"
        return f'<table class="data-table {"compact" if compact else ""}"><thead><tr>{head}</tr></thead><tbody>{body}</tbody></table>'

    def render_section(section: dict[str, Any]) -> str:
        stype = _example_slug(section.get("type"))
        title = esc(section.get("title") or stype)
        desc = esc(section.get("description", ""))
        fields = section.get("fields", [])
        if not isinstance(fields, list):
            fields = [fields]
        if stype in {"search-toolbar", "filter-toolbar", "mobile-filter"}:
            return f'<section class="panel search-toolbar" data-section-type="{esc(stype)}"><div class="panel-title">{title}</div><div class="filter-grid">{render_fields(fields)}</div><div class="toolbar-actions"><button class="btn">{ "重置" if z else "Reset" }</button><button class="btn primary">{ "查询" if z else "Search" }</button></div></section>'
        if stype == "action-toolbar":
            buttons = "".join(f'<button class="btn {"primary" if index == 0 else ""}">{esc(item)}</button>' for index, item in enumerate(fields[:5]))
            return f'<section class="panel action-toolbar" data-section-type="{esc(stype)}"><div class="panel-title">{title}</div><div class="toolbar-actions">{buttons}</div></section>'
        if stype in {"data-table", "history-table", "alert-table", "resource-results"}:
            actions = section.get("actions")
            if not isinstance(actions, list) or not actions:
                actions = ["筛选", "查看详情"] if z else ["Filter", "View detail"]
            buttons = "".join(f'<button class="btn {"primary" if index == len(actions[:3]) - 1 else ""}">{esc(item)}</button>' for index, item in enumerate(actions[:3]))
            pagination_text = esc(section.get("pagination") or section.get("summary") or ("示例数据" if z else "Sample data"))
            return f'<section class="panel table-panel" data-section-type="{esc(stype)}"><div class="panel-head"><div><div class="panel-title">{title}</div><p>{desc or esc(scenario.get("pageGoal", ""))}</p></div><div class="toolbar-actions">{buttons}</div></div>{render_table(section)}<div class="pagination"><span>{pagination_text}</span><button class="page-no active">1</button><button class="page-no">2</button><button class="page-no">3</button></div></section>'
        if stype in {"pagination"}:
            return f'<section class="panel pagination-only" data-section-type="{esc(stype)}"><div class="panel-title">{title}</div><span>{esc(section.get("description") or ("分页总数未记录" if z else "Pagination total not documented"))}</span><button class="page-no active">1</button><button class="page-no">2</button><button class="page-no">3</button></section>'
        if stype in {"detail-drawer", "detail-panel", "inspector-panel", "citation-panel", "contact-panel"}:
            detail_fields = "".join(f"<div><span>{esc(field)}</span><strong>{esc(_example_field_value(str(field), z))}</strong></div>" for field in fields[:5])
            return f'<aside class="panel detail-drawer" data-section-type="{esc(stype)}"><div class="panel-title">{title}</div><p>{desc}</p><div class="detail-grid">{detail_fields}</div><button class="btn primary">{ "保存配置" if z else "Save" }</button></aside>'
        if stype in {"metric-grid"}:
            rows = section.get("rows", [])
            cards = "".join(f'<div class="metric-card"><span>{esc((row[0] if isinstance(row, list) and row else "KPI"))}</span><strong>{esc((row[1] if isinstance(row, list) and len(row) > 1 else "98.7%"))}</strong><em>{esc((row[2] if isinstance(row, list) and len(row) > 2 else "+3.2%"))}</em></div>' for row in rows[:4] if isinstance(rows, list))
            return f'<section class="panel" data-section-type="{esc(stype)}"><div class="panel-title">{title}</div><div class="metric-grid">{cards}</div></section>'
        if stype in {"chart-panel", "result-preview", "canvas-workspace"}:
            return f'<section class="panel visual-panel" data-section-type="{esc(stype)}"><div class="panel-title">{title}</div><p>{desc or esc(scenario.get("pageGoal", ""))}</p><div class="chart-placeholder"><span>{title}</span></div>{render_table(section, compact=True) if section.get("rows") else ""}</section>'
        if stype in {"prompt-input"}:
            prompt = esc(section.get("prompt") or section.get("placeholder") or generation_input.get("userRequest") or ("输入生成需求" if z else "Enter generation request"))
            return f'<section class="panel prompt-panel" data-section-type="{esc(stype)}"><div class="panel-title">{title}</div><textarea>{prompt}</textarea><div class="filter-grid">{render_fields(fields[1:])}</div><button class="btn primary">{ "生成" if z else "Generate" }</button></section>'
        if stype in {"chat-thread"}:
            messages = section.get("messages")
            if not isinstance(messages, list) or not messages:
                messages = [
                    {"role": "user", "content": generation_input.get("userRequest") or ("请处理这个页面需求" if z else "Please handle this page request")},
                    {"role": "assistant", "content": section.get("description") or ("已根据规范组织页面内容。" if z else "The page has been structured from the specification.")},
                ]
            message_html = ""
            for item in messages[:6]:
                if isinstance(item, dict):
                    role = "user" if str(item.get("role", "")).lower() == "user" else "assistant"
                    content = item.get("content") or item.get("text") or ""
                else:
                    role = "assistant"
                    content = item
                message_html += f'<div class="message {role}">{esc(content)}</div>'
            return f'<section class="panel chat-thread" data-section-type="{esc(stype)}"><div class="panel-title">{title}</div>{message_html}</section>'
        if stype in {"conversation-list", "mobile-list"}:
            return f'<section class="panel list-panel" data-section-type="{esc(stype)}"><div class="panel-title">{title}</div>{render_table(section, compact=True)}</section>'
        if stype in {"bottom-tabbar"}:
            items = "".join(f"<span>{esc(item)}</span>" for item in fields[:4])
            return f'<nav class="bottom-tabbar" data-section-type="{esc(stype)}">{items}</nav>'
        if stype in {"quick-entry-cards"}:
            cards = section.get("cards", [])
            if not isinstance(cards, list):
                cards = []
            card_html = ""
            for card in cards[:3]:
                if not isinstance(card, dict):
                    continue
                links = card.get("links", [])
                if not isinstance(links, list):
                    links = []
                chips = "".join(f"<span>{esc(link)}</span>" for link in links[:6])
                card_html += f'<article class="quick-card"><h3>{esc(card.get("title"))}</h3><div>{chips}</div></article>'
            return f'<section class="quick-entry-wrap" data-section-type="{esc(stype)}"><div class="panel-title">{title}</div><div class="quick-entry-cards">{card_html}</div></section>'
        if stype in {"channel-tabs"}:
            tabs = section.get("tabs", [])
            if not isinstance(tabs, list):
                tabs = []
            tab_html = "".join(f'<span class="{("active" if index == 0 else "")}">{esc(tab)}</span>' for index, tab in enumerate(tabs[:8]))
            return f'<section class="channel-tabs-wrap" data-section-type="{esc(stype)}"><div class="panel-title">{title}</div><nav class="channel-tabs">{tab_html}</nav></section>'
        if stype in {"article-feed"}:
            articles = section.get("articles", [])
            if not isinstance(articles, list):
                articles = []
            article_html = "".join(render_article_card(article) for article in articles[:5] if isinstance(article, dict))
            return f'<section class="article-feed" data-section-type="{esc(stype)}"><div class="panel-title">{title}</div>{article_html}</section>'
        if stype in {"right-rail"}:
            items = section.get("items")
            if not isinstance(items, list) or not items:
                items = fields[:3] or (["相关信息", "辅助操作", "状态提示"] if z else ["Related info", "Secondary action", "Status hint"])
            rail_items = "".join(f'<div class="rail-item">{esc(item)}</div>' for item in items[:4])
            return f'<aside class="right-rail" data-section-type="{esc(stype)}"><div class="panel-title">{title}</div><p>{desc}</p>{rail_items}</aside>'
        if stype in {"site-footer"}:
            return f'<footer class="site-footer" data-section-type="{esc(stype)}">{title} · Site Footer</footer>'
        if stype in {"diagnostic"}:
            checks = section.get("checks")
            if not isinstance(checks, list):
                checks = []
            check_html = "".join(f"<li>{esc(item)}</li>" for item in checks[:6])
            return f'<section class="panel diagnostic-panel" data-section-type="{esc(stype)}"><div class="panel-title">{title}</div><p>{desc}</p><ul>{check_html}</ul></section>'
        return f'<section class="panel" data-section-type="{esc(stype)}"><div class="panel-title">{title}</div><p>{desc or esc(scenario.get("pageGoal", ""))}</p></section>'

    def render_article_card(article: dict[str, Any]) -> str:
        tags = article.get("tags", [])
        if not isinstance(tags, list):
            tags = []
        tag_html = "".join(f"<span>{esc(tag)}</span>" for tag in tags[:4])
        image = str(article.get("image") or article.get("thumb") or "").strip()
        image_style = f"background-image:url({html.escape(image, quote=True)});" if image else ""
        category = esc(article.get("category", ""))
        category_badge = f'<span class="category-badge">{category}</span>' if category else ""
        return f"""
        <article class="article-card">
          <div class="article-thumb" style="{image_style}">{category_badge}</div>
          <div class="article-body">
            <h2>{esc(article.get("title"))}</h2>
            <p>{esc(article.get("excerpt") or article.get("summary") or "")}</p>
            <div class="article-tags">{tag_html}</div>
            <div class="article-meta">{esc(article.get("author"))}</div>
          </div>
        </article>"""

    content_sections = "".join(render_section(section) for section in scenario.get("sections", []) if isinstance(section, dict))
    side_html = ""
    if side_items:
        side_links = []
        for index, item in enumerate(side_items):
            active_class = "active" if index == 1 or (index == 0 and len(side_items) == 1) else ""
            side_links.append(f'<a class="{active_class}">{esc(item)}</a>')
        side_title = "侧栏导航" if z else "Sidebar"
        side_html = f'<aside class="sidebar"><div class="sidebar-title">{side_title}</div>{"".join(side_links)}</aside>'
    tags_height_num = shell["tags_height"]
    tags_bar = ""
    if tags_height_num != "0px":
        tags_bar = f'<div class="tags-bar"><span>{page_name}</span><button type="button">x</button></div>'
    meta = f"""
        <section class="panel generation-info">
          <div class="panel-title">{'生成信息' if z else 'Generation Info'}</div>
          <div class="info-grid">
            <div><span>{'示例页面名称' if z else 'Example Page'}</span><strong>{page_name}</strong></div>
            <div><span>{'来源' if z else 'Source'}</span><strong>DESIGN.md / {esc(pattern_source)} / {esc(pattern)}</strong></div>
            <div><span>{'生成依据' if z else 'Reason'}</span><strong>{esc(scenario.get('reason', ''))}</strong></div>
          </div>
        </section>"""
    input_required = generation_input.get("requiredCapabilities")
    if not isinstance(input_required, list):
        input_required = []
    input_patterns = generation_input.get("expectedPatterns")
    if not isinstance(input_patterns, list):
        input_patterns = []
    input_rules = generation_input.get("designRulesUsed")
    if not isinstance(input_rules, list):
        input_rules = []
    input_cap_html = "".join(f"<span>{esc(item)}</span>" for item in input_required[:8])
    input_pattern_html = "".join(f"<span>{esc(item)}</span>" for item in input_patterns[:8])
    input_rule_html = "".join(f"<li>{esc(item)}</li>" for item in input_rules[:5])
    generation_input_panel = f"""
        <section class="panel generation-input" data-section-type="generation-input">
          <div class="panel-title">{'示例用户功能描述' if z else 'Sample User Request'}</div>
          <p>{esc(generation_input.get('userRequest') or scenario.get('pageGoal', ''))}</p>
          <div class="info-grid">
            <div><span>{'目标用户' if z else 'Target User'}</span><strong>{esc(generation_input.get('targetUser') or ('未显式指定' if z else 'Not specified'))}</strong></div>
            <div><span>{'目标页面' if z else 'Target Page'}</span><strong>{esc(generation_input.get('targetPage') or scenario.get('pageName', ''))}</strong></div>
            <div><span>{'输入来源' if z else 'Input Source'}</span><strong>{esc(generation_input.get('source') or source.get('inputSource') or 'generated-from-design-md')}</strong></div>
          </div>
          <div class="chip-row">{input_cap_html}{input_pattern_html}</div>
          <ul class="rule-list">{input_rule_html}</ul>
        </section>"""
    layout_class = "with-sidebar" if side_items else "no-sidebar"
    if archetype == "media-content":
        layout_class += " media-shell"
    if archetype == "mobile-app":
        layout_class += " mobile-frame"
    primary_action = esc(scenario.get("primaryAction") or generation_input.get("primaryAction") or ("生成示例" if z else "Generate example"))

    return f"""<!DOCTYPE html>
<html lang="{'zh-CN' if z else 'en'}" data-example-source="design-md" data-example-archetype="{html.escape(archetype, quote=True)}" data-example-pattern="{html.escape(pattern, quote=True)}" data-example-pattern-source="{html.escape(pattern_source, quote=True)}">
<head>
  <meta charset="UTF-8" />
  <meta name="viewport" content="width=device-width, initial-scale=1.0" />
  <title>{name} {page_name}</title>
  <style>
    :root {{
      --page: {shell['canvas']};
      --surface: {surface};
      --elevated: {elevated};
      --ink: {ink};
      --ink-heavy: {ink_heavy};
      --muted: {muted};
      --border: {border};
      --primary: {primary};
      --primary-hover: {primary_hover};
      --primary-light: {shell['sidebar_active']};
      --topbar-bg: {shell['topbar_bg']};
      --topbar-text: {shell['topbar_text']};
      --topbar-height: {shell['topbar_height']};
      --sidebar-width: {shell['sidebar_width']};
      --sidebar-collapsed-width: {shell['sidebar_collapsed']};
      --sidebar-bg: {shell['sidebar_bg']};
      --tags-height: {shell['tags_height']};
      --tags-bg: {shell['tags_bg']};
      --radius: {radius};
      --card-radius: {card_radius};
      --gap: {gap};
      --font: {font};
    }}
    * {{ box-sizing: border-box; }}
    body {{ margin: 0; min-height: 100vh; background: var(--page); color: var(--ink); font: 14px/1.5 var(--font); }}
    button, input, select, textarea {{ font: inherit; }}
    .topbar {{ height: var(--topbar-height); display: flex; align-items: center; gap: 18px; padding: 0 20px; background: var(--topbar-bg); color: var(--topbar-text); box-shadow: 0 1px 4px rgba(0,21,41,.08); }}
    .brand {{ min-width: 180px; font-weight: 600; color: var(--topbar-text); }}
    .topnav {{ margin-left: auto; display: flex; height: 100%; }}
    .topnav span {{ display: flex; align-items: center; padding: 0 12px; color: var(--topbar-text); opacity: .9; }}
    .topnav span.active {{ background: rgba(255,255,255,.16); opacity: 1; }}
    .tags-bar {{ height: var(--tags-height); min-height: var(--tags-height); display: flex; align-items: center; gap: 8px; padding: 0 12px; background: var(--tags-bg); color: var(--topbar-text); font-size: 12px; }}
    .tags-bar span {{ background: rgba(255,255,255,.16); padding: 4px 12px; border-radius: 2px; }}
    .tags-bar button {{ border: 0; background: transparent; color: inherit; }}
    .shell {{ display: grid; min-height: calc(100vh - var(--topbar-height) - var(--tags-height)); }}
    .shell.with-sidebar {{ grid-template-columns: var(--sidebar-width) minmax(0, 1fr); }}
    .sidebar {{ background: var(--sidebar-bg); box-shadow: 2px 0 6px rgba(0,21,41,.15); padding: 10px 0; }}
    .sidebar-title {{ padding: 10px 20px; color: var(--muted); font-size: 12px; }}
    .sidebar a {{ display: flex; align-items: center; min-height: 46px; padding: 0 20px; color: var(--ink); text-decoration: none; border-right: 4px solid transparent; }}
    .sidebar a.active {{ background: var(--primary-light); color: var(--primary); border-right-color: var(--primary); font-weight: 600; }}
    .content {{ display: grid; align-content: start; gap: var(--gap); padding: var(--gap); }}
    .page-head {{ display: flex; align-items: center; justify-content: space-between; gap: 16px; }}
    .page-head h1 {{ margin: 0; color: var(--ink-heavy); font-size: 20px; font-weight: 600; }}
    .page-head p {{ margin: 4px 0 0; color: var(--muted); }}
    .panel {{ background: var(--surface); border: 1px solid var(--border); border-radius: var(--radius); padding: 16px; }}
    .panel-title {{ color: var(--ink-heavy); font-size: 16px; font-weight: 600; margin-bottom: 12px; }}
    .panel p {{ margin: 0 0 12px; color: var(--muted); }}
    .panel-head {{ display: flex; align-items: flex-start; justify-content: space-between; gap: 16px; margin-bottom: 12px; }}
    .filter-grid {{ display: grid; grid-template-columns: repeat(3, minmax(160px, 1fr)); gap: 12px; }}
    label span, .detail-grid span, .info-grid span {{ display: block; color: var(--muted); font-size: 12px; margin-bottom: 4px; }}
    input, select {{ width: 100%; height: 32px; border: 1px solid var(--border); border-radius: var(--radius); background: #fff; color: var(--ink); padding: 0 10px; }}
    textarea {{ width: 100%; min-height: 108px; border: 1px solid var(--border); border-radius: var(--radius); padding: 10px; color: var(--ink); }}
    .toolbar-actions {{ display: flex; align-items: center; gap: 8px; justify-content: flex-end; margin-top: 12px; }}
    .btn {{ height: 32px; padding: 0 12px; border-radius: var(--radius); border: 1px solid var(--border); background: var(--surface); color: var(--ink); }}
    .btn.primary {{ background: var(--primary); border-color: var(--primary); color: #fff; }}
    .data-table {{ width: 100%; border-collapse: collapse; font-size: 13px; }}
    .data-table th {{ text-align: left; background: var(--elevated); color: var(--ink-heavy); font-weight: 600; border-bottom: 1px solid var(--border); padding: 10px 8px; white-space: nowrap; }}
    .data-table td {{ border-bottom: 1px solid var(--border); padding: 10px 8px; color: var(--ink); }}
    .data-table tr:hover td {{ background: color-mix(in srgb, var(--primary-light) 55%, transparent); }}
    .pagination, .pagination-only {{ display: flex; align-items: center; justify-content: flex-end; gap: 8px; color: var(--muted); }}
    .page-no {{ min-width: 30px; height: 30px; border: 1px solid var(--border); border-radius: var(--radius); background: var(--surface); }}
    .page-no.active {{ background: var(--primary); border-color: var(--primary); color: #fff; }}
    .detail-drawer {{ border-left: 4px solid var(--primary); }}
    .detail-grid, .info-grid {{ display: grid; grid-template-columns: repeat(3, minmax(0, 1fr)); gap: 12px; }}
    .detail-grid strong, .info-grid strong {{ color: var(--ink-heavy); font-weight: 500; }}
    .metric-grid {{ display: grid; grid-template-columns: repeat(3, minmax(0, 1fr)); gap: 12px; }}
    .metric-card {{ border: 1px solid var(--border); border-radius: var(--radius); padding: 14px; background: var(--elevated); }}
    .metric-card span {{ color: var(--muted); font-size: 12px; }}
    .metric-card strong {{ display: block; margin-top: 6px; color: var(--ink-heavy); font-size: 24px; }}
    .metric-card em {{ color: var(--primary); font-style: normal; }}
    .chart-placeholder {{ min-height: 240px; border: 1px dashed var(--border); border-radius: var(--radius); background: linear-gradient(135deg, var(--elevated), var(--surface)); display: grid; place-items: center; color: var(--muted); }}
    .message {{ padding: 10px 12px; border-radius: var(--radius); margin-bottom: 8px; max-width: 72%; }}
    .message.user {{ margin-left: auto; background: var(--primary); color: #fff; }}
    .message.assistant {{ background: var(--elevated); }}
    .bottom-tabbar {{ position: sticky; bottom: 0; display: grid; grid-template-columns: repeat(4, 1fr); background: var(--surface); border-top: 1px solid var(--border); }}
    .bottom-tabbar span {{ padding: 12px; text-align: center; color: var(--muted); }}
    .mobile-frame {{ max-width: 430px; margin: 20px auto; min-height: 760px; border: 1px solid var(--border); border-radius: 24px; overflow: hidden; box-shadow: 0 12px 40px rgba(0,0,0,.12); }}
    .media-shell .content {{ max-width: 1194px; width: min(1194px, calc(100vw - 32px)); margin: 0 auto; grid-template-columns: minmax(0, 1fr) 335px; align-items: start; }}
    .media-shell .page-head, .media-shell .quick-entry-wrap, .media-shell .channel-tabs-wrap, .media-shell .site-footer, .media-shell .generation-info, .media-shell .generation-input {{ grid-column: 1 / -1; }}
    .quick-entry-cards {{ display: grid; grid-template-columns: repeat(3, minmax(0, 1fr)); gap: 15px; }}
    .quick-card {{ background: var(--surface); border: 1px solid var(--border); border-radius: var(--card-radius); padding: 12px 15px; box-shadow: 0 1px 1px rgba(0,0,0,.05); }}
    .quick-card h3 {{ margin: 0 0 10px; color: var(--ink-heavy); font-size: 16px; }}
    .quick-card div {{ display: flex; flex-wrap: wrap; gap: 6px; }}
    .quick-card span, .article-tags span {{ display: inline-flex; align-items: center; min-height: 22px; padding: 1px 8px; border-radius: 4px; background: var(--elevated); color: var(--primary); font-size: 12px; }}
    .channel-tabs {{ display: flex; align-items: stretch; min-height: 50px; background: var(--surface); border-radius: var(--card-radius); box-shadow: 0 1px 1px rgba(0,0,0,.05); overflow: hidden; }}
    .channel-tabs span {{ position: relative; display: flex; align-items: center; padding: 0 15px; color: var(--ink); font-size: 16px; }}
    .channel-tabs span.active::before {{ content: ""; position: absolute; top: 0; left: 0; right: 0; height: 3px; background: var(--primary); }}
    .article-feed {{ display: grid; gap: 15px; }}
    .article-card {{ display: grid; grid-template-columns: 236px minmax(0, 1fr); gap: 15px; padding: 15px; background: var(--surface); border-radius: var(--card-radius); box-shadow: 0 1px 1px rgba(0,0,0,.05); }}
    .article-thumb {{ position: relative; width: 236px; height: 143px; border-radius: 5px; background: var(--elevated) center/cover no-repeat; overflow: hidden; }}
    .category-badge {{ position: absolute; left: 10px; top: 10px; padding: 2px 8px; border-radius: 5px; background: rgba(0,0,0,.55); color: #fff; font-size: 12px; }}
    .article-body {{ display: grid; gap: 8px; align-content: start; }}
    .article-body h2 {{ margin: 0; color: var(--ink-heavy); font-size: 20px; line-height: 1.4; font-weight: 400; }}
    .article-body p {{ margin: 0; color: var(--ink); line-height: 1.8; }}
    .article-tags {{ display: flex; gap: 8px; flex-wrap: wrap; }}
    .article-meta {{ color: var(--muted); font-size: 12px; }}
    .right-rail {{ background: var(--surface); border-radius: var(--card-radius); padding: 16px; box-shadow: 0 1px 1px rgba(0,0,0,.05); display: grid; gap: 10px; }}
    .rail-item {{ min-height: 54px; padding: 10px; background: var(--elevated); border-radius: 5px; color: var(--ink); }}
    .rail-promo {{ padding: 12px; border-radius: 5px; background: color-mix(in srgb, var(--primary) 10%, var(--surface)); color: var(--primary); }}
    .site-footer {{ background: #222c3c; color: rgba(255,255,255,.78); padding: 20px 24px; border-radius: var(--card-radius); }}
    .generation-info {{ border-style: dashed; }}
    .generation-input {{ border-left: 4px solid var(--primary); }}
    .chip-row {{ display: flex; flex-wrap: wrap; gap: 8px; margin-top: 12px; }}
    .chip-row span {{ display: inline-flex; align-items: center; min-height: 24px; padding: 2px 8px; border-radius: var(--radius); background: var(--elevated); color: var(--primary); font-size: 12px; }}
    .rule-list {{ margin: 12px 0 0; padding-left: 18px; color: var(--muted); }}
    .diagnostic-panel {{ border-color: #faad14; background: color-mix(in srgb, #faad14 8%, var(--surface)); }}
    @media (max-width: 980px) {{
      .shell.with-sidebar {{ grid-template-columns: 1fr; }}
      .sidebar {{ display: none; }}
      .media-shell .content {{ grid-template-columns: 1fr; }}
      .media-shell .page-head, .media-shell .quick-entry-wrap, .media-shell .channel-tabs-wrap, .media-shell .site-footer, .media-shell .generation-info, .media-shell .generation-input {{ grid-column: auto; }}
      .quick-entry-cards {{ grid-template-columns: 1fr; }}
      .article-card {{ grid-template-columns: 1fr; }}
      .filter-grid, .detail-grid, .info-grid, .metric-grid {{ grid-template-columns: 1fr; }}
      .topnav {{ display: none; }}
    }}
  </style>
</head>
<body>
  <header class="topbar">
    <div class="brand">{name}</div>
    <nav class="topnav">{''.join(f'<span class="{("active" if index == 0 else "")}">{esc(item)}</span>' for index, item in enumerate(nav_items))}</nav>
  </header>
  {tags_bar}
  <div class="shell {layout_class}">
    {side_html}
    <main class="content">
      <div class="page-head"><div><h1>{page_name}</h1><p>{esc(scenario.get("pageGoal", ""))}</p></div><button class="btn primary">{primary_action}</button></div>
      {generation_input_panel}
      {content_sections}
      {meta}
    </main>
  </div>
  <script type="application/json" id="example-generation-input">{generation_input_json}</script>
  <script type="application/json" id="example-scenario">{scenario_json}</script>
</body>
</html>
"""


def _example_field_value(field: str, z: bool) -> str:
    lowered = field.lower()
    if any(term in lowered for term in ("任务", "task")):
        return "ods_mysql_order_to_dwd" if z else "ods_mysql_order_to_dwd"
    if any(term in lowered for term in ("数据源", "source")):
        return "MySQL-订单库" if z else "MySQL Orders"
    if any(term in lowered for term in ("目标", "target")):
        return "dwd_order_detail" if z else "dwd_order_detail"
    if any(term in lowered for term in ("状态", "status")):
        return "运行中" if z else "Running"
    if any(term in lowered for term in ("负责人", "owner")):
        return "林晨" if z else "Lin Chen"
    if any(term in lowered for term in ("时间", "date", "range")):
        return "最近 7 天" if z else "Last 7 days"
    if any(term in lowered for term in ("关键词", "keyword", "搜索", "search")):
        return "订单同步" if z else "order sync"
    if any(term in lowered for term in ("prompt",)):
        return "生成一版说明" if z else "Generate copy"
    return "全部" if z else "All"


def render_example(data: dict[str, Any], sections: dict[str, str]) -> str:
    scenario = build_example_scenario(data, sections)
    return render_example_from_scenario(data, scenario)

def main() -> int:
    parser = argparse.ArgumentParser(description="从 DESIGN.md 渲染预览文件。")
    parser.add_argument("design_dir", help="设计系统文件夹路径")
    parser.add_argument(
        "--markdown-name",
        choices=("auto", "DESIGN.md", "design.md"),
        default="auto",
        help="Markdown 设计文件名。默认自动检测。",
    )
    parser.add_argument(
        "--render-example",
        action="store_true",
        help=(
            "仅用于旧版兼容：当 example.html 仍处于诊断状态时，也使用 Python 渲染器生成它。"
            "除非同时设置 --force-render-example，否则会保留 Agent 编写的 example.html "
            "（data-example-source=design-md）。默认不触碰 example.html，交由 Agent 生成。"
        ),
    )
    parser.add_argument(
        "--force-render-example",
        action="store_true",
        help=(
            "强制旧版 Python 渲染器覆盖 example.html，即使它看起来已经由 Agent 编写。"
            "该参数会隐含启用 --render-example，请谨慎使用。"
        ),
    )
    args = parser.parse_args()
    if args.force_render_example:
        args.render_example = True

    design_dir = Path(args.design_dir).resolve()
    try:
        design_md = resolve_design_md(design_dir, args.markdown_name)
        data, body = extract_design_doc(design_md.read_text(encoding="utf-8"))
        sections = extract_sections(body)
        (design_dir / "preview.html").write_text(resolve_all_refs(render(data, sections, dark=False), data), encoding="utf-8")
        (design_dir / "preview-dark.html").write_text(resolve_all_refs(render(data, sections, dark=True), data), encoding="utf-8")
        example_path = design_dir / "example.html"
        example_status: str
        if args.render_example:
            if _is_agent_authored_example(example_path) and not args.force_render_example:
                example_status = "已跳过（检测到 Agent 编写的 example；如需覆盖请传 --force-render-example）"
            else:
                example_path.write_text(
                    resolve_all_refs(render_example(data, sections), data),
                    encoding="utf-8",
                )
                example_status = "已通过旧版兜底渲染"
        else:
            example_status = "未修改（由 Agent 管理）"
        print(f"[完成] 已渲染预览：{design_dir}")
        print(f" - {design_dir / 'preview.html'}")
        print(f" - {design_dir / 'preview-dark.html'}")
        print(f" - {example_path} {example_status}")
    except Exception as exc:
        print(f"[错误] {exc}", file=sys.stderr)
        return 1
    return 0


def _is_agent_authored_example(example_path: Path) -> bool:
    """判断 example.html 是否已经像真实 Agent 样例。

    脚手架诊断模板带有 ``data-example-source="diagnostic"``，且 ``userRequest`` 为空。
    其它状态通常说明 Agent 已填充页面；旧版 Python 渲染器不能静默覆盖它
    （见 SKILL.md §6 和 references/output-contract.md）。
    """
    if not example_path.exists():
        return False
    try:
        content = example_path.read_text(encoding="utf-8")
    except Exception:
        return False
    if 'data-example-source="design-md"' in content:
        return True
    diagnostic_markers = (
        'data-example-source="diagnostic"',
        'data-example-pattern-source="agent-required"',
        '"source": "diagnostic"',
    )
    if any(marker in content for marker in diagnostic_markers):
        return False
    # 未知 / 自定义状态：保守处理，保护已有文件。
    return True


if __name__ == "__main__":
    raise SystemExit(main())
