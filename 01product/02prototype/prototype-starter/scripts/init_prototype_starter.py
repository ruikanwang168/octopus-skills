#!/usr/bin/env python3
"""Initialize an HTML, React, or Vue product prototype workspace from DESIGN.md."""

from __future__ import annotations

import argparse
import datetime as _dt
import hashlib
import html
import json
from pathlib import Path
import re
import shutil
import sys
import textwrap
from typing import Any

from extract_design_contract import (
    build_check_rules,
    build_design_contract,
    check_rules_json,
    contract_json,
    design_runtime_hashes,
    design_runtime_sha256,
    load_design,
)
from validate_design_readiness import format_text as format_readiness_text
from validate_design_readiness import validate_design_readiness
from layout_model import dom_count, is_layout_v2, normalize_layout_model, region_count


TOKEN_REF_RE = re.compile(r"\{tokens\.([A-Za-z0-9_.-]+)\}")
SUPPORTED_FRAMEWORKS = {"html", "react", "vue"}
WRITE_PLAN_ONLY = False
WRITE_BACKUP_DIR: Path | None = None
WRITE_BACKUP_SOURCE_ROOT: Path | None = None


def kebab(value: str) -> str:
    value = re.sub(r"([a-z0-9])([A-Z])", r"\1-\2", value)
    value = re.sub(r"[^a-zA-Z0-9]+", "-", value).strip("-")
    return value.lower() or "value"


def token_path_to_var(path: str) -> str:
    parts = [kebab(part) for part in path.split(".") if part]
    if not parts:
        return "--token-value"
    if parts[0] == "colors" and len(parts) >= 2:
        return "--color-" + "-".join(parts[1:])
    if parts[0] == "spacing" and len(parts) >= 2:
        return "--space-" + "-".join(parts[1:])
    if parts[0] == "radius" and len(parts) >= 2:
        return "--radius-" + "-".join(parts[1:])
    if parts[0] == "shadow" and len(parts) >= 2:
        return "--shadow-" + "-".join(parts[1:])
    if parts[0] == "motion" and len(parts) >= 2:
        return "--motion-" + "-".join(parts[1:])
    if parts[0] == "typography":
        if parts[1:] in (["base-font-family"], ["base-fontfamily"]):
            return "--font-family-base"
        if len(parts) >= 3:
            prop = {
                "font-size": "size",
                "font-weight": "weight",
                "line-height": "line-height",
            }.get(parts[2], parts[2])
            return "--font-" + parts[1] + "-" + prop
    return "--" + "-".join(parts)


def replace_token_refs(value: str) -> str:
    return TOKEN_REF_RE.sub(lambda match: f"var({token_path_to_var(match.group(1))})", value)


def css_value(value: Any, *, unit: str = "") -> str:
    if value is None or isinstance(value, (dict, list)):
        return ""
    if isinstance(value, bool):
        return "true" if value else "false"
    if isinstance(value, (int, float)):
        return f"{value}px" if unit == "px" else str(value)
    return replace_token_refs(str(value))


def css_var_line(name: str, value: Any, *, unit: str = "") -> str:
    rendered = css_value(value, unit=unit)
    return f"  {name}: {rendered};" if rendered else ""


def clean_block(text: str) -> str:
    return textwrap.dedent(text).strip() + "\n"


def normalize_framework(value: Any) -> str:
    raw = str(value or "").strip().lower()
    if not raw:
        return ""
    aliases = {
        "static": "html",
        "static-html": "html",
        "vanilla": "html",
        "vanilla-js": "html",
        "html": "html",
        "react": "react",
        "reactjs": "react",
        "vue": "vue",
        "vue3": "vue",
        "vue.js": "vue",
        "vuejs": "vue",
    }
    normalized = aliases.get(raw)
    if normalized:
        return normalized
    if "react" in raw:
        return "react"
    if "vue" in raw:
        return "vue"
    if raw in SUPPORTED_FRAMEWORKS:
        return raw
    raise SystemExit(f"Unsupported framework: {value}. Expected html, react, or vue.")


def framework_label(framework: str) -> str:
    return {
        "html": "静态 HTML 产品原型",
        "react": "React 产品原型",
        "vue": "Vue 产品原型",
    }[framework]


def mapping(value: Any, key: str) -> dict[str, Any]:
    if isinstance(value, dict) and isinstance(value.get(key), dict):
        return value[key]
    return {}


def collect_design_class_names(value: Any, output: set[str] | None = None, *, allow_string: bool = False) -> set[str]:
    if output is None:
        output = set()
    if not value:
        return output
    if isinstance(value, list):
        for item in value:
            collect_design_class_names(item, output, allow_string=allow_string)
        return output
    if isinstance(value, dict):
        for key, item in value.items():
            if re.fullmatch(r"classNames?|classes|selector|source", str(key), re.I):
                if isinstance(item, dict):
                    collect_design_class_names(list(item.values()), output, allow_string=True)
                else:
                    collect_design_class_names(item, output, allow_string=True)
            elif isinstance(item, (dict, list)):
                collect_design_class_names(item, output, allow_string=False)
        return output
    if allow_string and isinstance(value, str):
        for match in re.findall(r"\.?[A-Za-z][A-Za-z0-9_-]{2,}", value):
            cleaned = match.lstrip(".")
            if cleaned not in {"div", "span", "button", "input", "select", "table", "thead", "tbody", "header", "footer", "section", "main", "aside"}:
                output.add(cleaned)
    return output


def product_fingerprints(design: dict[str, Any]) -> set[str]:
    return collect_design_class_names(
        {
            "layout": design.get("layout"),
            "components": design.get("components"),
            "pageTemplates": design.get("pageTemplates"),
            "generationRules": design.get("generationRules"),
        }
    )


def uses_avue_fingerprint(design: dict[str, Any]) -> bool:
    names = product_fingerprints(design)
    return any(name.startswith("avue-") for name in names) or bool(
        names.intersection({"theme-white", "basic-container", "main-basic-container", "top-search", "title_new"})
    )


def normalize_class_names(value: Any) -> str:
    if not isinstance(value, str):
        return ""
    return " ".join(part.lstrip(".") for part in value.split() if part.strip())


def class_from(class_map: dict[str, Any], *keys: str) -> str:
    for key in keys:
        value = normalize_class_names(class_map.get(key))
        if value:
            return value
    return ""


def shell_classes(design: dict[str, Any]) -> dict[str, str]:
    if uses_avue_fingerprint(design):
        classes = {
            "root": "avue-contail theme-white",
            "root_base": "avue-contail",
            "header": "avue-header",
            "logo": "avue-header__logo",
            "toggle": "avue-header__toggle",
            "top_menu": "avue-top-menu",
            "top_menu_item": "avue-top-menu__item",
            "header_right": "avue-header__right",
            "layout": "avue-layout",
            "sidebar": "avue-left",
            "sidebar_nav": "avue-sidebar",
            "sidebar_item": "avue-sidebar__item",
            "main": "avue-main",
            "tabs": "avue-tags",
            "tab_item": "avue-tags__item",
            "view": "avue-view",
            "panel": "basic-container",
            "assistant": "chat-robot",
            "section_header": "title_new",
            "section_title": "title_new_left",
            "section_actions": "title_new_right",
            "filter": "top-search",
            "filter_grid": "top-search__grid",
            "filter_field": "top-search__field",
            "filter_label": "top-search__label",
            "filter_input": "top-search__input",
            "filter_select": "top-search__select",
            "filter_actions": "top-search__actions",
        }
    else:
        classes = {
            "root": "product-shell",
            "root_base": "product-shell",
            "header": "product-topbar",
            "logo": "product-topbar__brand",
            "toggle": "product-topbar__toggle",
            "top_menu": "product-topnav",
            "top_menu_item": "product-topnav__item",
            "header_right": "product-topbar__actions",
            "layout": "product-layout",
            "sidebar": "product-sidebar",
            "sidebar_nav": "product-sidebar__nav",
            "sidebar_item": "product-sidebar__item",
            "main": "product-main",
            "tabs": "product-tabs",
            "tab_item": "product-tabs__item",
            "view": "product-view",
            "panel": "product-panel",
            "assistant": "product-assistant",
            "section_header": "product-section-heading",
            "section_title": "product-section-heading__title",
            "section_actions": "product-section-heading__actions",
            "filter": "product-filter",
            "filter_grid": "product-filter__grid",
            "filter_field": "product-filter__field",
            "filter_label": "product-filter__label",
            "filter_input": "product-filter__input",
            "filter_select": "product-filter__select",
            "filter_actions": "product-filter__actions",
        }

    layout = design.get("layout") if isinstance(design.get("layout"), dict) else {}
    app_shell = mapping(layout, "appShell")
    app_classes = mapping(app_shell, "classNames")
    components = design.get("components") if isinstance(design.get("components"), dict) else {}
    filter_classes = mapping(mapping(components, "filter"), "classNames")
    section_classes = mapping(mapping(components, "sectionTitle"), "classNames")
    container_classes = mapping(mapping(components, "container"), "classNames")

    overrides = {
        "root": class_from(app_classes, "root", "shell", "appRoot"),
        "root_base": class_from(app_classes, "rootBase", "base", "root_base"),
        "header": class_from(app_classes, "header", "topbar", "topBar"),
        "logo": class_from(app_classes, "logo", "brand"),
        "toggle": class_from(app_classes, "toggle", "sidebarToggle"),
        "top_menu": class_from(app_classes, "topMenu", "topNav", "top_menu"),
        "top_menu_item": class_from(app_classes, "topMenuItem", "topNavItem", "top_menu_item"),
        "header_right": class_from(app_classes, "headerRight", "actions", "header_right"),
        "layout": class_from(app_classes, "layout", "body", "workspace"),
        "sidebar": class_from(app_classes, "sidebar", "leftNav", "left"),
        "sidebar_nav": class_from(app_classes, "sidebarNav", "sidebar_nav", "menu"),
        "sidebar_item": class_from(app_classes, "sidebarItem", "sidebar_item", "menuItem"),
        "main": class_from(app_classes, "main", "content"),
        "tabs": class_from(app_classes, "routeTagsBar", "tabs", "tags"),
        "tab_item": class_from(app_classes, "routeTagItem", "tabItem", "tagItem"),
        "view": class_from(app_classes, "view", "pageCanvas", "canvas"),
        "panel": class_from(app_classes, "panel") or class_from(container_classes, "root", "panel", "container"),
        "assistant": class_from(app_classes, "assistant", "chatBot"),
        "section_header": class_from(section_classes, "root", "header"),
        "section_title": class_from(section_classes, "title", "left"),
        "section_actions": class_from(section_classes, "actions", "right"),
        "filter": class_from(filter_classes, "root", "filter", "search"),
        "filter_grid": class_from(filter_classes, "grid", "row", "body"),
        "filter_field": class_from(filter_classes, "field", "item"),
        "filter_label": class_from(filter_classes, "label"),
        "filter_input": class_from(filter_classes, "input"),
        "filter_select": class_from(filter_classes, "select"),
        "filter_actions": class_from(filter_classes, "actions", "buttons"),
    }
    for key, value in overrides.items():
        if value:
            classes[key] = value
    if classes["root"] and not overrides["root_base"]:
        classes["root_base"] = classes["root"].split()[0]
    return classes


def css_class_selector(class_names: str) -> str:
    return "." + ".".join(part for part in class_names.split() if part)


def token_unit(path: list[str]) -> str:
    if not path:
        return ""
    if path[0] in {"spacing", "radius"}:
        return "px"
    if path[0] == "typography" and path[-1] in {"fontSize", "font-size", "size"}:
        return "px"
    return ""


def collect_nested_token_vars(value: Any, path: list[str]) -> list[tuple[str, Any, str]]:
    if isinstance(value, dict):
        rows: list[tuple[str, Any, str]] = []
        for key, item in value.items():
            rows.extend(collect_nested_token_vars(item, [*path, str(key)]))
        return rows
    if isinstance(value, list):
        return []
    return [(token_path_to_var(".".join(path)), value, token_unit(path))]


def collect_token_vars(tokens: dict[str, Any]) -> list[tuple[str, Any, str]]:
    variables: list[tuple[str, Any, str]] = []

    for key, value in (tokens.get("colors") or {}).items():
        variables.append((f"--color-{kebab(str(key))}", value, ""))

    typography = tokens.get("typography") or {}
    if isinstance(typography, dict):
        for key, value in typography.items():
            if key in {"baseFontFamily", "fontFamily", "base"} and not isinstance(value, dict):
                variables.append(("--font-family-base", value, ""))
            elif isinstance(value, dict):
                prefix = f"--font-{kebab(str(key))}"
                for prop, prop_value in value.items():
                    prop_name = {
                        "fontSize": "size",
                        "fontWeight": "weight",
                        "lineHeight": "line-height",
                    }.get(str(prop), kebab(str(prop)))
                    unit = "px" if prop_name == "size" else ""
                    variables.append((f"{prefix}-{prop_name}", prop_value, unit))

    for key, value in (tokens.get("spacing") or {}).items():
        variables.append((f"--space-{kebab(str(key))}", value, "px"))
    for key, value in (tokens.get("radius") or {}).items():
        variables.append((f"--radius-{kebab(str(key))}", value, "px"))
    for key, value in (tokens.get("shadow") or {}).items():
        variables.append((f"--shadow-{kebab(str(key))}", value, ""))
    for key, value in (tokens.get("motion") or {}).items():
        variables.append((f"--motion-{kebab(str(key))}", value, ""))

    known = {"colors", "typography", "spacing", "radius", "shadow", "motion"}
    for group, group_value in tokens.items():
        if group in known or not isinstance(group_value, dict):
            continue
        for key, value in group_value.items():
            if isinstance(value, (dict, list)):
                continue
            variables.append((f"--{kebab(str(group))}-{kebab(str(key))}", value, ""))

    by_name = {name: (name, value, unit) for name, value, unit in variables}
    for group, value in tokens.items():
        if isinstance(value, dict):
            for name, token_value, unit in collect_nested_token_vars(value, [str(group)]):
                by_name.setdefault(name, (name, token_value, unit))

    return list(by_name.values())


def render_tokens_css(design: dict[str, Any], source_hash: str) -> str:
    tokens = design.get("tokens") if isinstance(design.get("tokens"), dict) else {}
    variables = [
        line
        for name, value, unit in collect_token_vars(tokens)
        if (line := css_var_line(name, value, unit=unit))
    ]

    return "\n".join(
        [
            f"/* Generated from DESIGN.md front matter. sourceSha256={source_hash} */",
            ":root {",
            *variables,
            "}",
            "",
            "*,",
            "*::before,",
            "*::after {",
            "  box-sizing: border-box;",
            "}",
            "",
            "html {",
            "  min-height: 100%;",
            "  background: var(--color-canvas);",
            "  color: var(--color-text);",
            "  font-family: var(--font-family-base);",
            "  font-size: var(--font-body-size);",
            "  line-height: var(--font-body-line-height);",
            "}",
            "",
            "body {",
            "  min-height: 100vh;",
            "  margin: 0;",
            "  background: var(--color-canvas);",
            "  color: var(--color-text);",
            "}",
            "",
            "button,",
            "input,",
            "select,",
            "textarea {",
            "  font: inherit;",
            "}",
            "",
        ]
    )


def render_layout_css(design: dict[str, Any]) -> str:
    layout = design.get("layout") if isinstance(design.get("layout"), dict) else {}
    app_shell = mapping(layout, "appShell")
    topbar = mapping(app_shell, "topbar")
    sidebar = mapping(app_shell, "sidebar")
    route_tags = mapping(app_shell, "routeTagsBar")
    page_canvas = mapping(app_shell, "pageCanvas")

    topbar_height = css_value(topbar.get("height"), unit="px")
    sidebar_width = css_value(sidebar.get("width"), unit="px")
    sidebar_collapsed = css_value(sidebar.get("collapsedWidth"), unit="px")
    sidebar_expanded = css_value(sidebar.get("expandedWidth"), unit="px")
    topbar_bg = css_value(topbar.get("background"))
    topbar_text = css_value(topbar.get("textColor"))
    sidebar_bg = css_value(sidebar.get("background"))
    content_bg = css_value(page_canvas.get("background"))
    tags_height = css_value(route_tags.get("height"), unit="px")
    tags_bg = css_value(route_tags.get("background"))
    active_bg = css_value(sidebar.get("activeBackground"))
    active_text = css_value(sidebar.get("activeText"))
    responsive = mapping(layout, "responsive")
    breakpoint = css_value(responsive.get("breakpoint"), unit="px")
    scroll_owner = str(layout.get("scrollOwner") or "")
    root_overflow = "hidden" if scroll_owner in {"view", "pageCanvas", "main"} else "visible"
    view_overflow = "auto" if scroll_owner in {"view", "pageCanvas"} else "visible"
    classes = shell_classes(design)
    root = css_class_selector(classes["root"])
    root_base = css_class_selector(classes["root_base"])
    header = css_class_selector(classes["header"])
    logo = css_class_selector(classes["logo"])
    toggle = css_class_selector(classes["toggle"])
    top_menu = css_class_selector(classes["top_menu"])
    top_menu_item = css_class_selector(classes["top_menu_item"])
    header_right = css_class_selector(classes["header_right"])
    layout_class = css_class_selector(classes["layout"])
    sidebar_class = css_class_selector(classes["sidebar"])
    sidebar_nav = css_class_selector(classes["sidebar_nav"])
    sidebar_item = css_class_selector(classes["sidebar_item"])
    main = css_class_selector(classes["main"])
    tabs = css_class_selector(classes["tabs"])
    tab_item = css_class_selector(classes["tab_item"])
    view = css_class_selector(classes["view"])
    panel = css_class_selector(classes["panel"])
    assistant = css_class_selector(classes["assistant"])
    theme_rule = f"{root}.theme-white {{\n          background: {content_bg};\n        }}" if uses_avue_fingerprint(design) else ""

    return clean_block(
        f"""
        /* Product shell generated from DESIGN.md product layout rules. */
        :root {{
          --topbar-h: {topbar_height};
          --sidebar-w: {sidebar_width};
          --sidebar-collapsed-w: {sidebar_collapsed};
          --sidebar-expanded-w: {sidebar_expanded};
          --tags-h: {tags_height};
        }}

        {root} {{
          height: 100vh;
          overflow: {root_overflow};
          background: {content_bg};
          color: var(--color-text);
        }}

        {root_base}.is-expanded {{
          --sidebar-w: var(--sidebar-expanded-w);
        }}

        {theme_rule}

        {header} {{
          position: fixed;
          top: 0;
          left: 0;
          right: 0;
          z-index: 1000;
          height: var(--topbar-h);
          display: flex;
          align-items: center;
          gap: var(--space-md);
          padding: 0 var(--space-lg);
          background: {topbar_bg};
          color: {topbar_text};
          box-shadow: var(--shadow-topbar);
        }}

        {logo} {{
          display: flex;
          align-items: center;
          gap: var(--space-sm);
          margin-right: var(--space-sm);
          white-space: nowrap;
          font-size: 16px;
          font-weight: var(--font-heading-weight);
        }}

        {toggle} {{
          width: 32px;
          height: 32px;
          display: flex;
          align-items: center;
          justify-content: center;
          color: {topbar_text};
          background: transparent;
          border: 0;
          border-radius: var(--radius-sm);
          cursor: pointer;
        }}

        {toggle}:hover {{
          background: rgba(255, 255, 255, .12);
        }}

        {top_menu} {{
          min-width: 0;
          flex: 1;
          display: flex;
          align-items: center;
          gap: var(--space-xs);
          overflow: hidden;
        }}

        {top_menu_item} {{
          display: flex;
          align-items: center;
          gap: var(--space-xs);
          min-height: 32px;
          padding: 0 var(--space-md);
          color: rgba(255, 255, 255, .86);
          text-decoration: none;
          white-space: nowrap;
          border-radius: var(--radius-sm);
        }}

        {top_menu_item}.is-active {{
          color: var(--color-on-primary);
          background: var(--color-topbar-active);
        }}

        {header_right} {{
          display: flex;
          align-items: center;
          gap: var(--space-lg);
          color: rgba(255, 255, 255, .86);
          font-size: 13px;
          white-space: nowrap;
        }}

        {layout_class} {{
          min-height: 100vh;
          display: flex;
          padding-top: var(--topbar-h);
        }}

        {sidebar_class} {{
          position: fixed;
          top: var(--topbar-h);
          left: 0;
          z-index: 900;
          width: var(--sidebar-w);
          height: calc(100vh - var(--topbar-h));
          background: {sidebar_bg};
          box-shadow: var(--shadow-sidebar);
          overflow: hidden;
          transition: width .2s;
        }}

        {sidebar_nav} {{
          height: 100%;
          padding: var(--space-xs) 0;
          overflow-y: auto;
        }}

        {sidebar_item} {{
          display: flex;
          align-items: center;
          justify-content: center;
          flex-direction: column;
          gap: 4px;
          min-height: 56px;
          padding: var(--space-xs) 6px;
          position: relative;
          color: var(--color-sidebar-text);
          text-decoration: none;
          text-align: center;
          font-size: 12px;
        }}

        {root_base}.is-expanded {sidebar_item} {{
          flex-direction: row;
          justify-content: flex-start;
          min-height: 46px;
          padding: 0 var(--space-lg);
          gap: var(--space-sm);
          text-align: left;
          font-size: var(--font-body-size);
        }}

        {sidebar_item}.is-active {{
          color: {active_text};
          background: {active_bg};
          border-right: 4px solid var(--color-primary);
        }}

        {main} {{
          min-width: 0;
          width: calc(100% - var(--sidebar-w));
          min-height: calc(100vh - var(--topbar-h));
          margin-left: var(--sidebar-w);
          display: flex;
          flex-direction: column;
          background: {content_bg};
          transition: margin-left .2s, width .2s;
        }}

        {tabs} {{
          height: var(--tags-h);
          flex-shrink: 0;
          display: flex;
          align-items: center;
          gap: 4px;
          padding: 0 var(--space-md);
          background: {tags_bg};
          border-bottom: 1px solid var(--color-border-light);
          box-shadow: var(--shadow-tags);
        }}

        {tab_item} {{
          padding: 6px var(--space-md);
          color: var(--color-text-muted);
          text-decoration: none;
          white-space: nowrap;
          border-bottom: 3px solid transparent;
        }}

        {tab_item}.is-active {{
          color: var(--color-primary);
          border-bottom-color: var(--color-primary);
        }}

        {view} {{
          flex: 1;
          min-height: 0;
          padding: var(--space-md);
          overflow: {view_overflow};
        }}

        {panel} {{
          min-height: 100%;
          padding: var(--space-card-padding);
          background: var(--color-surface);
        }}

        {assistant} {{
          position: fixed;
          right: 40px;
          bottom: 40px;
          z-index: 800;
          width: 56px;
          height: 56px;
          display: flex;
          align-items: center;
          justify-content: center;
          color: var(--color-on-primary);
          background: var(--color-primary);
          border: 0;
          border-radius: 50%;
          box-shadow: var(--shadow-assistant);
          cursor: pointer;
        }}

        @media (max-width: {breakpoint}) {{
          {header_right} {{
            display: none;
          }}

          {sidebar_class} {{
            display: none;
          }}

          {main} {{
            width: 100%;
            margin-left: 0;
          }}
        }}
        """
    )


def render_components_css(design: dict[str, Any]) -> str:
    components = design.get("components") if isinstance(design.get("components"), dict) else {}
    button = mapping(components, "button")
    primary = mapping(button, "primary")
    table = mapping(components, "table")

    button_height = css_value(button.get("height"), unit="px")
    button_radius = css_value(primary.get("radius"))
    primary_bg = css_value(primary.get("background"))
    primary_hover = css_value(primary.get("hoverBackground"))
    primary_text = css_value(primary.get("textColor"))
    header_text = css_value(table.get("headerTextColor"))
    body_text = css_value(table.get("bodyTextColor"))
    responsive = mapping(mapping(design, "layout"), "responsive")
    breakpoint = css_value(responsive.get("breakpoint"), unit="px")
    classes = shell_classes(design)
    filter_class = css_class_selector(classes["filter"])
    filter_grid = css_class_selector(classes["filter_grid"])
    filter_field = css_class_selector(classes["filter_field"])
    filter_label = css_class_selector(classes["filter_label"])
    filter_input = css_class_selector(classes["filter_input"])
    filter_select = css_class_selector(classes["filter_select"])
    filter_actions = css_class_selector(classes["filter_actions"])
    filter_row_extra = css_class_selector("top-search__row-extra" if uses_avue_fingerprint(design) else "product-filter__row-extra")
    section_header = css_class_selector(classes["section_header"])
    section_title = css_class_selector(classes["section_title"])
    section_actions = css_class_selector(classes["section_actions"])

    return clean_block(
        f"""
        /* Product components generated from DESIGN.md component rules. */
        .btn {{
          height: {button_height};
          display: inline-flex;
          align-items: center;
          justify-content: center;
          gap: var(--space-xs);
          padding: 0 15px;
          color: var(--color-text);
          background: var(--color-surface);
          border: 1px solid var(--color-border);
          border-radius: {button_radius};
          font-size: var(--font-button-size);
          cursor: pointer;
          transition: var(--motion-fast);
        }}

        .btn:hover {{
          color: var(--color-primary);
          border-color: var(--color-primary);
        }}

        .btn--primary {{
          color: {primary_text};
          background: {primary_bg};
          border-color: {primary_bg};
        }}

        .btn--primary:hover {{
          color: {primary_text};
          background: {primary_hover};
          border-color: {primary_hover};
        }}

        .btn--text {{
          padding: 0 var(--space-xs);
          color: var(--color-primary);
          background: transparent;
          border-color: transparent;
        }}

        .btn--text:hover {{
          color: var(--color-primary-hover);
          border-color: transparent;
        }}

        .btn--icon {{
          width: {button_height};
          padding: 0;
        }}

        .product-icon {{
          width: 16px;
          height: 16px;
          display: inline-flex;
          align-items: center;
          justify-content: center;
          flex: 0 0 auto;
          line-height: 0;
        }}

        .product-icon svg {{
          width: 100%;
          height: 100%;
          display: block;
          stroke: currentColor;
        }}

        .search-container,
        .list-container {{
          background: var(--color-surface);
        }}

        .search-container {{
          margin-bottom: var(--space-md);
          padding: var(--space-lg);
        }}

        .list-container {{
          padding: var(--space-lg);
        }}

        {filter_class} {{
          width: 100%;
        }}

        {filter_grid} {{
          display: grid;
          grid-template-columns: repeat(3, minmax(220px, 1fr)) auto;
          gap: var(--space-md) var(--space-lg);
          align-items: center;
        }}

        {filter_grid}.is-collapsed {filter_row_extra} {{
          display: none;
        }}

        {filter_field} {{
          display: flex;
          align-items: center;
          gap: var(--space-sm);
          min-width: 0;
        }}

        {filter_field} label,
        {filter_label} {{
          flex: 0 0 auto;
          min-width: 72px;
          margin: 0;
          color: var(--color-text-strong);
          font-size: var(--font-caption-size);
          text-align: right;
          white-space: nowrap;
        }}

        {filter_input},
        {filter_select} {{
          min-width: 0;
          width: 100%;
          height: {button_height};
          padding: 0 var(--space-sm);
          color: var(--color-text);
          background: var(--color-surface);
          border: 1px solid var(--color-border-light);
          border-radius: {button_radius};
          font-size: var(--font-caption-size);
        }}

        {filter_actions} {{
          display: flex;
          align-items: center;
          justify-content: flex-end;
          gap: var(--space-xs);
        }}

        {section_header} {{
          display: flex;
          align-items: center;
          justify-content: space-between;
          gap: var(--space-md);
          margin-bottom: var(--space-md);
        }}

        {section_title} {{
          position: relative;
          padding-left: var(--space-sm);
          color: var(--color-text-strong);
          font-size: var(--font-heading-size);
          font-weight: var(--font-heading-weight);
        }}

        {section_title}::before {{
          content: "";
          position: absolute;
          left: 0;
          top: 50%;
          width: 2px;
          height: 18px;
          background: var(--color-primary);
          transform: translateY(-50%);
        }}

        {section_actions} {{
          display: flex;
          align-items: center;
          gap: var(--space-xs);
        }}

        .segmented-control {{
          display: inline-flex;
          align-items: center;
          border: 1px solid var(--color-border-light);
          border-radius: var(--radius-sm);
          overflow: hidden;
          background: var(--color-surface);
        }}

        .segmented-control__item {{
          min-height: {button_height};
          display: inline-flex;
          align-items: center;
          gap: var(--space-xs);
          padding: 0 var(--space-md);
          color: var(--color-text);
          background: transparent;
          border: 0;
          border-right: 1px solid var(--color-border-light);
          cursor: pointer;
        }}

        .segmented-control__item:last-child {{
          border-right: 0;
        }}

        .segmented-control__item.is-active {{
          color: var(--color-primary);
          background: var(--color-primary-soft);
        }}

        .data-table-wrap {{
          overflow-x: auto;
        }}

        .data-table {{
          width: 100%;
          border-collapse: collapse;
          font-size: var(--font-body-size);
          color: {body_text};
          background: var(--color-surface);
        }}

        .data-table th,
        .data-table td {{
          padding: var(--space-sm) var(--space-md);
          text-align: left;
          border-bottom: 1px solid var(--color-border-light);
          white-space: nowrap;
        }}

        .data-table th {{
          color: {header_text};
          background: var(--color-surface-muted);
          font-weight: var(--font-heading-weight);
        }}

        .data-table tbody tr:hover {{
          background: var(--color-table-hover);
        }}

        .data-table a,
        .link-name {{
          color: var(--color-primary);
          text-decoration: none;
        }}

        .table-actions {{
          display: flex;
          align-items: center;
          gap: var(--space-md);
          flex-wrap: wrap;
        }}

        .status-cell {{
          display: inline-flex;
          align-items: center;
          gap: var(--space-xs);
          white-space: nowrap;
        }}

        .status-dot {{
          width: 8px;
          height: 8px;
          display: inline-block;
          border-radius: 999px;
          background: var(--color-success);
        }}

        .status-dot--warning {{
          background: var(--color-warning);
        }}

        .status-dot--error {{
          background: var(--color-error);
        }}

        .pagination-bar {{
          display: flex;
          align-items: center;
          justify-content: flex-end;
          gap: var(--space-xs);
          margin-top: var(--space-lg);
          color: var(--color-text-muted);
          font-size: 13px;
        }}

        .pagination-bar__page,
        .pagination-bar__size,
        .pagination-bar__jump {{
          min-height: 32px;
          display: inline-flex;
          align-items: center;
          justify-content: center;
          padding: 0 var(--space-sm);
          color: var(--color-text);
          background: var(--color-surface);
          border: 1px solid var(--color-border-light);
          border-radius: var(--radius-sm);
        }}

        .pagination-bar__page.is-active {{
          color: var(--color-primary);
          background: var(--color-primary-soft);
          border-color: transparent;
        }}

        .message-toast {{
          position: fixed;
          top: calc(var(--topbar-h) + var(--space-lg));
          left: 50%;
          z-index: 1200;
          display: flex;
          align-items: center;
          gap: var(--space-xs);
          min-height: 40px;
          padding: 0 var(--space-lg);
          color: var(--color-text);
          background: var(--color-surface);
          border: 1px solid var(--color-border-light);
          border-radius: var(--radius-sm);
          box-shadow: var(--shadow-modal);
          transform: translateX(-50%);
        }}

        @media (max-width: {breakpoint}) {{
          {filter_grid} {{
            grid-template-columns: 1fr;
          }}

          {filter_field} {{
            align-items: flex-start;
            flex-direction: column;
          }}

          {filter_field} label,
          {filter_label} {{
            text-align: left;
          }}

          {filter_actions},
          {section_header} {{
            justify-content: flex-start;
            flex-wrap: wrap;
          }}
        }}
        """
    )


def render_universal_components_css(design: dict[str, Any]) -> str:
    rows = ["/* Component CSS contains only selectors and values explicitly declared in DESIGN. */"]
    components = design.get("components") if isinstance(design.get("components"), dict) else {}
    for component_id, component in components.items():
        if not isinstance(component, dict):
            continue
        selector = component.get("selector")
        styles = component.get("styles")
        if isinstance(selector, str) and selector and isinstance(styles, dict):
            declarations = _css_declarations(styles.get("base") if isinstance(styles.get("base"), dict) else styles)
            if declarations:
                rows.append(f"{selector}{{{''.join(declarations)}}}")
    return "\n".join(rows) + "\n"


def render_universal_patterns_css(design: dict[str, Any]) -> str:
    rows = ["/* Page-pattern CSS contains only template styles explicitly declared in DESIGN. */"]
    for template in design.get("pageTemplates", []) if isinstance(design.get("pageTemplates"), list) else []:
        if not isinstance(template, dict):
            continue
        for rule in template.get("styles", []) if isinstance(template.get("styles"), list) else []:
            if not isinstance(rule, dict) or not isinstance(rule.get("selector"), str):
                continue
            declarations = _css_declarations(rule.get("declarations"))
            if declarations:
                rows.append(f"{rule['selector']}{{{''.join(declarations)}}}")
    return "\n".join(rows) + "\n"


def render_universal_shell_js() -> str:
    return clean_block(
        """
        // Layout contract v2 does not assume sidebar, tabs, modal, or navigation behavior.
        // Add interactions only when a confirmed component or template declares them.
        window.prototypeLayoutContractVersion = 2;
        """
    )


def render_patterns_css(design: dict[str, Any]) -> str:
    templates = design.get("pageTemplates")
    if not isinstance(templates, list):
        templates = []

    comments = []
    breakpoint = css_value(mapping(mapping(design, "layout"), "responsive").get("breakpoint"), unit="px")
    for item in templates:
        if not isinstance(item, dict):
            continue
        template_id = item.get("id") or item.get("name") or "page-template"
        purpose = str(item.get("purpose") or "").replace("*/", "")
        comments.append(f"/* pageTemplate:{template_id} purpose={purpose} */")

    return clean_block(
        f"""
        /* Product page patterns generated from DESIGN.md pageTemplates. */
        {chr(10).join(comments)}

        .drawer-mask,
        .confirm-mask {{
          position: fixed;
          inset: 0;
          z-index: 1100;
          display: none;
          background: var(--color-overlay, rgba(0, 0, 0, .35));
        }}

        .drawer-mask.is-open,
        .confirm-mask.is-open {{
          display: block;
        }}

        .drawer-panel {{
          position: fixed;
          top: 0;
          right: 0;
          z-index: 1110;
          width: 60vw;
          height: 100vh;
          display: grid;
          grid-template-rows: auto minmax(0, 1fr) auto;
          background: var(--color-surface);
          box-shadow: -2px 0 12px rgba(0, 0, 0, .12);
          transform: translateX(100%);
          transition: transform .24s ease, right .24s ease;
        }}

        .drawer-panel.is-open {{
          transform: translateX(0);
        }}

        .drawer-panel.is-shifted {{
          right: var(--drawer-shift, 0);
        }}

        .drawer-panel--30 {{ width: 30vw; }}
        .drawer-panel--45 {{ width: 45vw; }}
        .drawer-panel--60 {{ width: 60vw; }}
        .drawer-panel--75 {{ width: 75vw; }}
        .drawer-panel--85 {{ width: 85vw; }}

        .drawer-panel__header,
        .drawer-panel__footer {{
          display: flex;
          align-items: center;
          justify-content: space-between;
          gap: var(--space-md);
          padding: var(--space-lg) var(--space-xl);
          border-bottom: 1px solid var(--color-border-light);
        }}

        .drawer-panel__footer {{
          justify-content: flex-end;
          border-top: 1px solid var(--color-border-light);
          border-bottom: 0;
        }}

        .drawer-panel__title {{
          margin: 0;
          color: var(--color-text-strong);
          font-size: var(--font-heading-size);
          font-weight: var(--font-heading-weight);
        }}

        .drawer-panel__body {{
          padding: var(--space-xl);
          overflow: auto;
        }}

        .form-row {{
          margin-bottom: var(--space-lg);
        }}

        .form-label.is-required::before {{
          content: "*";
          margin-right: 4px;
          color: var(--color-error, #ef4444);
        }}

        .form-control,
        .disabled-input {{
          width: 100%;
        }}

        .disabled-input {{
          color: var(--color-text-muted);
          background: var(--color-surface-muted);
          cursor: not-allowed;
        }}

        .char-count {{
          margin-left: auto;
          color: var(--color-text-muted);
          font-size: 12px;
        }}

        .switch-control {{
          width: 40px;
          height: 22px;
          display: inline-flex;
          align-items: center;
          padding: 2px;
          background: var(--color-border);
          border-radius: 999px;
        }}

        .switch-control::before {{
          content: "";
          width: 18px;
          height: 18px;
          display: block;
          background: var(--color-surface);
          border-radius: 50%;
          box-shadow: 0 1px 2px rgba(0, 0, 0, .16);
        }}

        .switch-control.is-on {{
          justify-content: flex-end;
          background: var(--color-primary);
        }}

        .dashed-add-button {{
          width: 100%;
          min-height: 36px;
          display: inline-flex;
          align-items: center;
          justify-content: center;
          gap: var(--space-xs);
          color: var(--color-primary);
          background: transparent;
          border: 1px dashed var(--color-primary);
          border-radius: var(--radius-sm);
          cursor: pointer;
        }}

        .confirm-dialog {{
          position: fixed;
          top: 50%;
          left: 50%;
          z-index: 1120;
          width: min(420px, calc(100vw - 32px));
          display: none;
          background: var(--color-surface);
          border-radius: var(--radius-md);
          box-shadow: var(--color-modal-shadow, 0 2px 12px rgba(0, 0, 0, .18));
          transform: translate(-50%, -50%);
        }}

        .confirm-dialog.is-open {{
          display: block;
        }}

        .confirm-dialog__body {{
          padding: var(--space-xl);
        }}

        .confirm-dialog__footer {{
          display: flex;
          align-items: center;
          justify-content: flex-end;
          gap: var(--space-xs);
          padding: var(--space-lg) var(--space-xl);
          border-top: 1px solid var(--color-border-light);
        }}

        .config_tit,
        .config-tit {{
          min-height: 32px;
          display: grid;
          grid-template-columns: auto minmax(0, 1fr);
          align-items: center;
          gap: var(--space-md);
          margin: var(--space-lg) 0;
          padding: 0 var(--space-md);
          background: var(--color-section-header-bg);
          border-radius: var(--radius-sm);
        }}

        .config_tit .num,
        .config-tit__num {{
          width: 30px;
          height: 30px;
          display: inline-flex;
          align-items: center;
          justify-content: center;
          color: #fff;
          background: var(--color-primary);
          border-radius: 50%;
          font-weight: var(--font-heading-weight);
        }}

        .object-summary {{
          display: grid;
          grid-template-columns: repeat(4, minmax(0, 1fr));
          gap: var(--space-md);
          margin-bottom: var(--space-lg);
          padding: var(--space-lg);
          background: var(--color-surface-muted);
          border: 1px solid var(--color-border-light);
          border-radius: var(--radius-sm);
        }}

        .object-summary__item {{
          display: grid;
          gap: var(--space-xs);
        }}

        .object-summary__item span {{
          color: var(--color-text-muted);
        }}

        .detail-tabs {{
          display: flex;
          align-items: center;
          gap: var(--space-xl);
          margin-bottom: var(--space-lg);
          border-bottom: 1px solid var(--color-border-light);
        }}

        .detail-tabs__item {{
          position: relative;
          padding: var(--space-md) 0;
          color: var(--color-text);
          text-decoration: none;
        }}

        .detail-tabs__item.is-active {{
          color: var(--color-primary);
          font-weight: var(--font-heading-weight);
        }}

        .detail-tabs__item.is-active::after {{
          content: "";
          position: absolute;
          left: 0;
          right: 0;
          bottom: -1px;
          height: 2px;
          background: var(--color-primary);
        }}

        .attr-grid {{
          display: grid;
          grid-template-columns: repeat(3, minmax(0, 1fr));
          gap: var(--space-md);
        }}

        .attr-item {{
          display: grid;
          gap: var(--space-xs);
          color: var(--color-text-muted);
        }}

        .attr-item strong {{
          color: var(--color-text-strong);
        }}

        @media (max-width: {breakpoint}) {{
          .object-summary,
          .attr-grid {{
            grid-template-columns: 1fr;
          }}

          .drawer-panel,
          .drawer-panel--30,
          .drawer-panel--45,
          .drawer-panel--60,
          .drawer-panel--75,
          .drawer-panel--85 {{
            width: 100vw;
          }}
        }}
        """
    )


def render_prototype_meta_css(design: dict[str, Any]) -> str:
    breakpoint = css_value(mapping(mapping(design, "layout"), "responsive").get("breakpoint"), unit="px")
    return clean_block(
        """
        /* Prototype library and metadata styles. Product pages should prefer product-* classes. */
        .proto-library,
        .proto-feature-entry {
          width: min(1120px, calc(100% - 48px));
          margin: 0 auto;
          padding: var(--space-xl) 0;
        }

        .proto-library-header,
        .proto-entry-card {
          display: grid;
          gap: var(--space-lg);
        }

        .proto-library-header h1,
        .proto-entry-card h1 {
          margin: 0;
          color: var(--color-text-strong);
          font-size: var(--font-heading-size);
          font-weight: var(--font-heading-weight);
        }

        .proto-kicker,
        .proto-page-summary,
        .proto-library-header p {
          margin: 0;
          color: var(--color-text-muted);
        }

        .proto-entry-card,
        .proto-info-item,
        .proto-feature-card,
        .proto-page-card {
          background: var(--color-surface);
          border: 1px solid var(--color-border-light);
          border-radius: var(--radius-md);
          box-shadow: var(--shadow-card);
        }

        .proto-entry-card,
        .proto-info-item {
          padding: var(--space-lg);
        }

        .proto-feature-list,
        .proto-page-list,
        .proto-info-grid {
          display: grid;
          gap: var(--space-md);
        }

        .proto-info-grid {
          grid-template-columns: repeat(4, minmax(0, 1fr));
        }

        .proto-feature-card,
        .proto-page-card {
          display: grid;
          gap: var(--space-xs);
          padding: var(--space-lg);
          color: inherit;
          text-decoration: none;
        }

        .proto-info-item span,
        .proto-feature-card small,
        .proto-page-card span {
          color: var(--color-text-muted);
        }

        .proto-back-link {
          color: var(--color-primary);
          text-decoration: none;
        }

        .proto-section-title {
          display: flex;
          align-items: center;
          justify-content: space-between;
          gap: var(--space-md);
          padding: var(--space-lg) 0;
        }

        .proto-section-title h2 {
          margin: 0;
          color: var(--color-text-strong);
          font-size: var(--font-body-size);
          font-weight: var(--font-heading-weight);
        }

        [data-page-key] {
          scroll-margin-top: calc(var(--topbar-h) + var(--tags-h) + var(--space-lg));
        }

        @media (max-width: __BREAKPOINT__) {
          .proto-info-grid {
            grid-template-columns: 1fr;
          }
        }
        """
    ).replace("__BREAKPOINT__", breakpoint)


def markdown_list(items: list[Any], *, fallback: str) -> str:
    normalized = [str(item) for item in items if str(item).strip()]
    if not normalized:
        return f"- {fallback}"
    return "\n".join(f"- {item}" for item in normalized)


def page_template_list(design: dict[str, Any]) -> str:
    templates = design.get("pageTemplates") if isinstance(design.get("pageTemplates"), list) else []
    rows: list[str] = []
    for item in templates:
        if not isinstance(item, dict):
            continue
        template_id = str(item.get("id") or "page-template")
        name = str(item.get("name") or template_id)
        purpose = str(item.get("purpose") or "用于对应页面类型")
        rows.append(f"- `{template_id}`：{name}。{purpose}")
    return "\n".join(rows) or "- 根据 `design-system/design-contract.json` 中的 `pageTemplates` 选择页面结构。"


def self_check_list(design: dict[str, Any]) -> str:
    rules = mapping(design, "generationRules")
    items = rules.get("selfCheck") if isinstance(rules.get("selfCheck"), list) else []
    return markdown_list(items, fallback="页面应复用共享 CSS、组件类和相对路径，并保持可见文案为中文。")


def scalar_text(value: Any) -> str:
    if value in ({}, [], None, ""):
        return ""
    if isinstance(value, bool):
        return "true" if value else "false"
    return str(value)


def join_texts(items: list[str], *, limit: int = 16) -> str:
    visible = [item for item in items if item]
    if not visible:
        return ""
    if len(visible) <= limit:
        return "、".join(visible)
    return "、".join(visible[:limit]) + f" 等 {len(visible)} 项"


def template_texts(items: Any) -> list[str]:
    if not isinstance(items, list):
        return []
    texts: list[str] = []
    for item in items:
        if isinstance(item, dict) and item.get("text"):
            texts.append(str(item["text"]))
        elif isinstance(item, str):
            texts.append(item)
    return texts


def copywriting_guidance(design: dict[str, Any]) -> str:
    copywriting = design.get("copywriting")
    if not isinstance(copywriting, dict):
        return ""

    rows: list[str] = [
        "## 文案规则",
        "",
        "- `copywriting` 已写入 `design-system/design-contract.json`，新增页面文案应优先遵循该契约中已提供的规则。",
    ]

    message = copywriting.get("message")
    if isinstance(message, dict):
        details: list[str] = []
        if message.get("source"):
            details.append(f"来源：{message['source']}")
        if message.get("use"):
            details.append(f"用途：{message['use']}")
        length = message.get("length")
        if isinstance(length, dict):
            length_parts = []
            if length.get("min") is not None and length.get("max") is not None:
                length_parts.append(f"{length['min']}-{length['max']} 字")
            if length.get("rule"):
                length_parts.append(str(length["rule"]))
            if length_parts:
                details.append("长度：" + "，".join(length_parts))
        if details:
            rows.append("- Message 轻提示：" + "；".join(details) + "。")

        success = message.get("success")
        if isinstance(success, dict):
            success_parts: list[str] = []
            for key, label in (
                ("format", "格式"),
                ("charLength", "长度"),
                ("punctuation", "标点"),
            ):
                value = scalar_text(success.get(key))
                if value:
                    success_parts.append(f"{label}：{value}")
            templates = join_texts(template_texts(success.get("templates")))
            if templates:
                success_parts.append(f"模板：{templates}")
            if success_parts:
                rows.append("- 成功 Message：" + "；".join(success_parts) + "。")

        error = message.get("error")
        if isinstance(error, dict):
            error_parts: list[str] = []
            if error.get("priority"):
                error_parts.append(f"优先级：{error['priority']}")
            templates = join_texts(template_texts(error.get("fallbackTemplates")))
            if templates:
                error_parts.append(f"兜底模板：{templates}")
            if error_parts:
                rows.append("- 失败 Message：" + "；".join(error_parts) + "。")

    content_dialog = copywriting.get("contentDialog")
    if isinstance(content_dialog, dict):
        details: list[str] = []
        if content_dialog.get("use"):
            details.append(f"用途：{content_dialog['use']}")
        length = content_dialog.get("length")
        if isinstance(length, dict):
            length_parts = []
            if length.get("min") is not None and length.get("max") is not None:
                length_parts.append(f"{length['min']}-{length['max']} 字")
            if length.get("rule"):
                length_parts.append(str(length["rule"]))
            if length_parts:
                details.append("长度：" + "，".join(length_parts))
        patterns = content_dialog.get("patterns")
        pattern_examples: list[str] = []
        if isinstance(patterns, list):
            for item in patterns:
                if isinstance(item, dict):
                    pattern_examples.extend(str(example) for example in item.get("examples", []) if example)
        examples = join_texts(pattern_examples, limit=10)
        if examples:
            details.append(f"示例：{examples}")
        if details:
            rows.append("- 内容弹窗标题：" + "；".join(details) + "。")

    form_validation = copywriting.get("formValidation")
    if isinstance(form_validation, dict):
        details: list[str] = []
        for key, label in (("input", "输入"), ("select", "选择"), ("placeholder", "占位")):
            value = form_validation.get(key)
            if isinstance(value, dict):
                formats = value.get("formats")
                if not formats and value.get("format"):
                    formats = [value.get("format")]
                if isinstance(formats, list) and formats:
                    details.append(f"{label}：{join_texts([str(item) for item in formats], limit=4)}")
        format_rules = form_validation.get("format")
        if isinstance(format_rules, dict):
            templates = join_texts(template_texts(format_rules.get("templates")), limit=10)
            if templates:
                details.append(f"格式校验：{templates}")
        if details:
            rows.append("- 表单文案：" + "；".join(details) + "。")

    punctuation = copywriting.get("punctuation")
    punctuation_rules = punctuation.get("rules") if isinstance(punctuation, dict) else None
    if isinstance(punctuation_rules, list):
        rendered_rules: list[str] = []
        for item in punctuation_rules:
            if isinstance(item, dict) and item.get("rule"):
                rendered_rules.append(str(item["rule"]))
        joined = join_texts(rendered_rules, limit=8)
        if joined:
            rows.append("- 标点规则：" + joined + "。")

    return "\n".join(rows).rstrip() + "\n"


def legacy_token_guidance(design: dict[str, Any]) -> str:
    legacy_tokens = design.get("legacyTokens")
    if not isinstance(legacy_tokens, dict):
        return ""
    rows = ["## 遗留 Token 约束", "", "- `legacyTokens` 仅用于识别存量遗留值，新页面不要把这些值作为新的主色、背景或组件 token。"]
    for key, value in legacy_tokens.items():
        if not isinstance(value, dict) or "value" not in value:
            continue
        note = f"：{value['note']}" if value.get("note") else ""
        rows.append(f"- `{key}` = `{value['value']}`{note}")
    return "\n".join(rows).rstrip() + "\n" if len(rows) > 3 else ""


def contract_context_guidance(design: dict[str, Any]) -> str:
    rows: list[str] = []
    known_limits = design.get("knownLimits")
    if isinstance(known_limits, dict):
        limit_rows: list[str] = []
        items = known_limits.get("items")
        if isinstance(items, list):
            limit_rows.extend(f"- {item}" for item in items if item)
        decisions = known_limits.get("defaultDecisions")
        if isinstance(decisions, dict):
            for key, value in decisions.items():
                if value not in ({}, [], None, ""):
                    limit_rows.append(f"- 默认 `{key}`：{value}")
        if limit_rows:
            rows.extend(["## 已知限制与默认判断", "", *limit_rows])

    assumptions = design.get("assumptions")
    if isinstance(assumptions, list) and assumptions:
        if rows:
            rows.append("")
        rows.extend(["## 设计假设", "", *[f"- {item}" for item in assumptions if item]])

    return "\n".join(rows).rstrip() + "\n" if rows else ""


def render_template(skill_dir: Path, template_name: str, replacements: dict[str, str]) -> str:
    text = (skill_dir / "assets" / template_name).read_text(encoding="utf-8")
    for key, value in replacements.items():
        text = text.replace(key, value)
    return text


def make_nav_items(design: dict[str, Any], classes: dict[str, str]) -> str:
    content = primary_template(design).get("previewContent") or {}
    names = content.get("topNavigation") if isinstance(content, dict) else []
    names = [str(name) for name in names] if isinstance(names, list) else []
    rendered = []
    for index, name in enumerate(names[:4]):
        active = " is-active" if index == 0 else ""
        rendered.append(f'        <a class="{classes["top_menu_item"]}{active}" href="#">{html.escape(name)}</a>')
    return "\n".join(rendered)


def make_side_nav_items(design: dict[str, Any], classes: dict[str, str]) -> str:
    content = primary_template(design).get("previewContent") or {}
    names = content.get("sideNavigation") if isinstance(content, dict) else []
    names = [str(name) for name in names] if isinstance(names, list) else []
    rendered = []
    for index, name in enumerate(names[:6]):
        active = " is-active" if index == 0 else ""
        icon = ["database", "file", "list", "settings", "filter", "calendar"][index % 6]
        rendered.append(f'          <a class="{classes["sidebar_item"]}{active}" href="#"><span class="product-icon" data-icon="{icon}"></span>{html.escape(name)}</a>')
    return "\n".join(rendered)


def primary_template(design: dict[str, Any]) -> dict[str, Any]:
    templates = design.get("pageTemplates") if isinstance(design.get("pageTemplates"), list) else []
    for item in templates:
        if isinstance(item, dict) and item.get("representative") is True:
            return item
    return {}


def preview_content(design: dict[str, Any]) -> dict[str, Any]:
    value = primary_template(design).get("previewContent")
    return value if isinstance(value, dict) else {}


def make_sample_rows(design: dict[str, Any]) -> str:
    table = preview_content(design).get("table") or {}
    rows = table.get("rows") if isinstance(table, dict) else []
    rendered = []
    for row in rows if isinstance(rows, list) else []:
        cells = row if isinstance(row, list) else list(row.values()) if isinstance(row, dict) else [row]
        rendered.append("                <tr>" + "".join(f"<td>{html.escape(str(cell))}</td>" for cell in cells) + "</tr>")
    return "\n".join(rendered)


def make_table_headers(design: dict[str, Any]) -> str:
    table = preview_content(design).get("table") or {}
    columns = table.get("columns") if isinstance(table, dict) and isinstance(table.get("columns"), list) else []
    return "\n".join(f"                  <th>{html.escape(str(column))}</th>" for column in columns if _present_template_value(column))


def _present_template_value(value: Any) -> bool:
    return value not in (None, "", [], {})


def make_filter_fields(design: dict[str, Any], classes: dict[str, str]) -> str:
    filters = preview_content(design).get("filters") or []
    rows: list[str] = []
    for field in filters if isinstance(filters, list) else []:
        if not isinstance(field, dict):
            continue
        label = html.escape(str(field.get("label") or ""))
        if field.get("type") == "select":
            options = "".join(f"<option>{html.escape(str(item))}</option>" for item in field.get("options", []) if _present_template_value(item))
            control = f'<select class="{classes["filter_select"]}">{options}</select>'
        else:
            placeholder = html.escape(str(field.get("placeholder") or ""))
            control = f'<input class="{classes["filter_input"]}" type="search" placeholder="{placeholder}">'
        rows.append(f'                <div class="{classes["filter_field"]}"><label>{label}</label>{control}</div>')
    return "\n".join(rows)


def make_action_buttons(design: dict[str, Any]) -> str:
    actions = preview_content(design).get("actions") or []
    return "\n".join(f'                <button class="btn{(" btn--primary" if index == 0 else "")}" type="button">{html.escape(str(action))}</button>' for index, action in enumerate(actions) if _present_template_value(action))


def make_filter_action_buttons(design: dict[str, Any]) -> str:
    actions = preview_content(design).get("filterActions") or []
    return "\n".join(f'                  <button class="btn{(" btn--primary" if index == len(actions) - 1 else "")}" type="button">{html.escape(str(action))}</button>' for index, action in enumerate(actions) if _present_template_value(action))


def make_pagination(design: dict[str, Any]) -> str:
    pagination = preview_content(design).get("pagination") or {}
    if not isinstance(pagination, dict):
        return ""
    summary = html.escape(str(pagination.get("summary") or ""))
    pages = pagination.get("pages") if isinstance(pagination.get("pages"), list) else []
    page_size = html.escape(str(pagination.get("pageSize") or ""))
    page_items = "".join(f'<span class="pagination-bar__page{(" is-active" if index == 0 else "")}">{html.escape(str(value))}</span>' for index, value in enumerate(pages))
    return f'<footer class="pagination-bar" data-prototype-role="pagination"><span>{summary}</span>{page_items}<span class="pagination-bar__size">{page_size}</span></footer>'


def framework_rules(framework: str) -> str:
    if framework == "react":
        return clean_block(
            """
            ## React 原型规则

            - 当前项目使用 React + Vite，入口为 `src/main.jsx`，应用壳为 `src/App.jsx`。
            - 功能组件放在 `src/features/NN-feature-name/`，并通过 `src/prototype-registry.js` 注册。
            - 组件应优先复用产品类名、`shared/css/product-*.css` 和 CSS 变量，不要把页面壳层改回通用 `proto-*`。
            - 新增功能时继续使用 `node scripts/new-feature.cjs ...`，脚本会创建 React 组件并更新注册表。
            """
        ).strip()
    if framework == "vue":
        return clean_block(
            """
            ## Vue 原型规则

            - 当前项目使用 Vue 3 + Vite，入口为 `src/main.js`，应用壳为 `src/App.vue`。
            - 功能组件放在 `src/features/NN-feature-name/`，并通过 `src/prototype-registry.js` 注册。
            - 组件应优先复用产品类名、`shared/css/product-*.css` 和 CSS 变量，不要把页面壳层改回通用 `proto-*`。
            - 新增功能时继续使用 `node scripts/new-feature.cjs ...`，脚本会创建 Vue SFC 并更新注册表。
            """
        ).strip()
    return clean_block(
        """
        ## 框架模式

        - 当前项目为默认 HTML 模式。只有用户明确要求 React 或 Vue 时，才切换到框架项目。
        """
    ).strip()


def template_replacements(
    design: dict[str, Any],
    project_name: str,
    framework: str,
    source_hash: str,
    runtime_hash: str,
) -> dict[str, str]:
    product_name = str(design.get("name"))
    summary = str(design.get("summary"))
    language = str(design.get("language"))
    template = primary_template(design)
    content = preview_content(design)
    classes = shell_classes(design)
    return {
        "{{LANG}}": html.escape(language),
        "{{PRODUCT_NAME}}": html.escape(product_name),
        "{{DESIGN_SUMMARY}}": html.escape(summary),
        "{{DESIGN_SOURCE_SHA}}": html.escape(source_hash),
        "{{DESIGN_RUNTIME_SHA}}": html.escape(runtime_hash),
        "{{DESIGN_CONTRACT_VERSION}}": "4",
        "{{PAGE_TEMPLATE_ID}}": html.escape(str(template.get("id"))),
        "{{PAGE_TEMPLATE_NAME}}": html.escape(str(template.get("name"))),
        "{{PAGE_SUMMARY}}": html.escape(str(content.get("summary") or summary)),
        "{{USER_LABEL}}": html.escape(str(content.get("userLabel"))),
        "{{NAV_ITEMS}}": make_nav_items(design, classes),
        "{{SIDE_NAV_ITEMS}}": make_side_nav_items(design, classes),
        "{{FILTER_FIELDS}}": make_filter_fields(design, classes),
        "{{FILTER_ACTIONS}}": make_filter_action_buttons(design),
        "{{PAGE_ACTIONS}}": make_action_buttons(design),
        "{{TABLE_HEADERS}}": make_table_headers(design),
        "{{SAMPLE_ROWS}}": make_sample_rows(design),
        "{{PAGINATION}}": make_pagination(design),
        "{{SHELL_ROOT_CLASS}}": classes["root"],
        "{{SHELL_HEADER_CLASS}}": classes["header"],
        "{{SHELL_LOGO_CLASS}}": classes["logo"],
        "{{SHELL_TOGGLE_CLASS}}": classes["toggle"],
        "{{SHELL_TOP_MENU_CLASS}}": classes["top_menu"],
        "{{SHELL_HEADER_RIGHT_CLASS}}": classes["header_right"],
        "{{SHELL_LAYOUT_CLASS}}": classes["layout"],
        "{{SHELL_SIDEBAR_CLASS}}": classes["sidebar"],
        "{{SHELL_SIDEBAR_NAV_CLASS}}": classes["sidebar_nav"],
        "{{SHELL_MAIN_CLASS}}": classes["main"],
        "{{SHELL_TABS_CLASS}}": classes["tabs"],
        "{{SHELL_TAB_ITEM_CLASS}}": classes["tab_item"],
        "{{SHELL_VIEW_CLASS}}": classes["view"],
        "{{SHELL_PANEL_CLASS}}": classes["panel"],
        "{{SHELL_ASSISTANT_CLASS}}": classes["assistant"],
        "{{SECTION_HEADER_CLASS}}": classes["section_header"],
        "{{SECTION_TITLE_CLASS}}": classes["section_title"],
        "{{SECTION_ACTIONS_CLASS}}": classes["section_actions"],
        "{{FILTER_CLASS}}": classes["filter"],
        "{{FILTER_GRID_CLASS}}": classes["filter_grid"],
        "{{FILTER_FIELD_CLASS}}": classes["filter_field"],
        "{{FILTER_LABEL_CLASS}}": classes["filter_label"],
        "{{FILTER_INPUT_CLASS}}": classes["filter_input"],
        "{{FILTER_SELECT_CLASS}}": classes["filter_select"],
        "{{FILTER_ACTIONS_CLASS}}": classes["filter_actions"],
        "{{PAGE_TEMPLATE_LIST}}": page_template_list(design),
        "{{SELF_CHECK_LIST}}": self_check_list(design),
        "{{COPYWRITING_GUIDANCE}}": copywriting_guidance(design),
        "{{LEGACY_TOKEN_GUIDANCE}}": legacy_token_guidance(design),
        "{{CONTRACT_CONTEXT_GUIDANCE}}": contract_context_guidance(design),
        "{{PROJECT_MODE_NAME}}": framework_label(framework),
        "{{FRAMEWORK_RULES}}": framework_rules(framework),
    }


def render_project_readme(project_name: str, source_hash: str, framework: str, design: dict[str, Any] | None = None) -> str:
    run_command = "直接打开 index.html" if framework == "html" else "npm install && npm run dev"
    feature_target = "HTML 页面" if framework == "html" else f"{framework_label(framework)}组件"
    feature_guidance = (
        "node scripts/new-feature.cjs --feature \"工作台升级\" --page \"工作台首页\" --layout-profile <profile-id> --template <template-id>"
        if design and is_layout_v2(design)
        else 'node scripts/new-feature.cjs 02-workbench-upgrade "工作台升级" --updated 2026-06-01 --iteration V2 --pages "工作台首页:workbench-home.html,任务提醒:task-reminder.html"'
    )
    return clean_block(
        f"""
        # {project_name}

        This {framework} prototype workspace was generated from `DESIGN.md`.

        - Design contract: `design-system/design-contract.json`
        - Normalized layout model: `design-system/layout-model.json`
        - Context router: `design-system/context-index.json`
        - Check rules: `design-system/check-rules.json`
        - Fidelity guardrails: `design-system/fidelity-guardrails.json`
        - Fidelity reviews: `design-system/fidelity-reviews.json`
        - Evidence sources: `design-system/evidence-sources.json`
        - Design gaps: `design-system/design-gaps.json`
        - Design change plan: `design-system/design-change-plan.json`
        - Prototype framework: `{framework}`
        - Source hash: `{source_hash}`
        - Project rules: `AGENTS.md`
        - Product shared CSS: `shared/css/product-*.css`
        - Product shared JS: `shared/js/product-icons.js`, `shared/js/product-shell.js`
        - Feature output: `{feature_target}`
        - Run locally: `{run_command}`

        Create clickable placeholders when only page names are known:

        ```bash
        {feature_guidance}
        ```

        Create confirmed business scaffolds, product-evidence reconstructions, or incremental baseline copies with a manifest. Reconstruction requires registered evidence IDs; incremental requires a local baseline plus change/preserve/allowed-file rules:

        ```bash
        node scripts/new-feature.cjs --manifest feature-manifest.json
        ```

        Check compliance:

        ```bash
        node scripts/check-prototype-compliance.cjs
        ```

        Normal compliance allows placeholders with warnings. The release gate fails while any placeholder remains.

        After inspecting every viewport declared by the selected layout profile, record screenshot evidence and run the release gate:

        ```bash
        node scripts/record-fidelity-review.cjs 02-feature-name/page-a.html --viewport mobile,fidelity-evidence/current-mobile.png,390,844
        node scripts/check-prototype-compliance.cjs --release
        ```

        Full manifests, evidence registration, design-gap governance, and visual comparison rules are documented in `docs/prototype-workflows.md`.
        """
    )


def render_product_icons_js() -> str:
    return clean_block(
        r"""
        (function () {
          var icons = {
            search: '<circle cx="11" cy="11" r="7"></circle><path d="m20 20-3.5-3.5"></path>',
            refresh: '<path d="M20 11a8.1 8.1 0 0 0-15.5-2M4 5v4h4"></path><path d="M4 13a8.1 8.1 0 0 0 15.5 2M20 19v-4h-4"></path>',
            plus: '<path d="M12 5v14"></path><path d="M5 12h14"></path>',
            settings: '<circle cx="12" cy="12" r="3"></circle><path d="M19.4 15a1.7 1.7 0 0 0 .3 1.9l.1.1a2 2 0 1 1-2.8 2.8l-.1-.1a1.7 1.7 0 0 0-1.9-.3 1.7 1.7 0 0 0-1 1.6V21a2 2 0 1 1-4 0v-.1a1.7 1.7 0 0 0-1-1.6 1.7 1.7 0 0 0-1.9.3l-.1.1A2 2 0 1 1 4.2 17l.1-.1A1.7 1.7 0 0 0 4.6 15a1.7 1.7 0 0 0-1.6-1H3a2 2 0 1 1 0-4h.1a1.7 1.7 0 0 0 1.6-1 1.7 1.7 0 0 0-.3-1.9L4.2 7A2 2 0 1 1 7 4.2l.1.1A1.7 1.7 0 0 0 9 4.6a1.7 1.7 0 0 0 1-1.6V3a2 2 0 1 1 4 0v.1a1.7 1.7 0 0 0 1 1.6 1.7 1.7 0 0 0 1.9-.3l.1-.1A2 2 0 1 1 19.8 7l-.1.1a1.7 1.7 0 0 0-.3 1.9 1.7 1.7 0 0 0 1.6 1h.1a2 2 0 1 1 0 4H21a1.7 1.7 0 0 0-1.6 1Z"></path>',
            menu: '<path d="M4 6h16"></path><path d="M4 12h16"></path><path d="M4 18h16"></path>',
            close: '<path d="M18 6 6 18"></path><path d="m6 6 12 12"></path>',
            user: '<path d="M20 21a8 8 0 0 0-16 0"></path><circle cx="12" cy="7" r="4"></circle>',
            bell: '<path d="M18 8a6 6 0 1 0-12 0c0 7-3 7-3 9h18c0-2-3-2-3-9"></path><path d="M10 21h4"></path>',
            help: '<circle cx="12" cy="12" r="10"></circle><path d="M9.1 9a3 3 0 1 1 5.7 1.3c-.8 1.2-2.1 1.5-2.6 2.7"></path><path d="M12 17h.01"></path>',
            down: '<path d="m6 9 6 6 6-6"></path>',
            right: '<path d="m9 18 6-6-6-6"></path>',
            eye: '<path d="M2 12s3.5-7 10-7 10 7 10 7-3.5 7-10 7S2 12 2 12Z"></path><circle cx="12" cy="12" r="3"></circle>',
            list: '<path d="M8 6h13"></path><path d="M8 12h13"></path><path d="M8 18h13"></path><path d="M3 6h.01"></path><path d="M3 12h.01"></path><path d="M3 18h.01"></path>',
            edit: '<path d="M12 20h9"></path><path d="M16.5 3.5a2.1 2.1 0 0 1 3 3L7 19l-4 1 1-4Z"></path>',
            delete: '<path d="M3 6h18"></path><path d="M8 6V4h8v2"></path><path d="M19 6l-1 14H6L5 6"></path>',
            upload: '<path d="M12 16V4"></path><path d="m7 9 5-5 5 5"></path><path d="M5 20h14"></path>',
            filter: '<path d="M4 5h16l-6 7v5l-4 2v-7Z"></path>',
            calendar: '<path d="M8 2v4"></path><path d="M16 2v4"></path><rect x="3" y="4" width="18" height="18" rx="2"></rect><path d="M3 10h18"></path>',
            database: '<ellipse cx="12" cy="5" rx="8" ry="3"></ellipse><path d="M4 5v14c0 1.7 3.6 3 8 3s8-1.3 8-3V5"></path><path d="M4 12c0 1.7 3.6 3 8 3s8-1.3 8-3"></path>',
            file: '<path d="M14 2H6a2 2 0 0 0-2 2v16a2 2 0 0 0 2 2h12a2 2 0 0 0 2-2V8Z"></path><path d="M14 2v6h6"></path>',
            home: '<path d="m3 11 9-8 9 8"></path><path d="M5 10v11h14V10"></path>',
            bot: '<rect x="5" y="8" width="14" height="10" rx="4"></rect><path d="M12 8V4"></path><circle cx="9" cy="13" r="1"></circle><circle cx="15" cy="13" r="1"></circle>',
            success: '<path d="M20 6 9 17l-5-5"></path>',
            warning: '<path d="M12 9v4"></path><path d="M12 17h.01"></path><path d="M10.3 3.9 2.4 18a2 2 0 0 0 1.7 3h15.8a2 2 0 0 0 1.7-3L13.7 3.9a2 2 0 0 0-3.4 0Z"></path>'
          };

          function svg(name) {
            var body = icons[name] || icons.file;
            return '<svg viewBox="0 0 24 24" fill="none" stroke-width="2" stroke-linecap="round" stroke-linejoin="round" aria-hidden="true">' + body + '</svg>';
          }

          function render(root) {
            (root || document).querySelectorAll('[data-icon]').forEach(function (node) {
              if (node.__productIconRendered === node.getAttribute('data-icon')) return;
              node.innerHTML = svg(node.getAttribute('data-icon'));
              node.__productIconRendered = node.getAttribute('data-icon');
            });
          }

          window.productIcons = { render: render, icons: icons };
          if (document.readyState === 'loading') {
            document.addEventListener('DOMContentLoaded', function () { render(document); });
          } else {
            render(document);
          }
        })();
        """
    )


def render_product_shell_js(design: dict[str, Any]) -> str:
    classes = shell_classes(design)
    toggle_selector = f'[data-sidebar-toggle], #sidebar-toggle, {css_class_selector(classes["toggle"])}'
    root_selector = css_class_selector(classes["root_base"])
    filter_selector = css_class_selector(classes["filter"])
    filter_grid_selector = css_class_selector(classes["filter_grid"])
    script = clean_block(
        """
        (function () {
          function refreshIcons() {
            if (window.productIcons && typeof window.productIcons.render === 'function') {
              window.productIcons.render(document);
            }
          }

          function closest(root, selector) {
            return root && root.closest ? root.closest(selector) : null;
          }

          document.addEventListener('click', function (event) {
            var sidebarToggle = event.target.closest('__TOGGLE_SELECTOR__');
            if (sidebarToggle) {
              var shell = document.querySelector('__ROOT_SELECTOR__');
              if (shell) shell.classList.toggle('is-expanded');
              refreshIcons();
              return;
            }

            var searchToggle = event.target.closest('[data-search-toggle], #search-toggle');
            if (searchToggle) {
              var search = closest(searchToggle, '__FILTER_SELECTOR__') || document.querySelector('__FILTER_SELECTOR__');
              var grid = search ? search.querySelector('__FILTER_GRID_SELECTOR__') : null;
              if (grid) {
                grid.classList.toggle('is-collapsed');
                var text = searchToggle.querySelector('[data-toggle-text]');
                if (text) {
                  text.textContent = grid.classList.contains('is-collapsed') ? '展开' : '收起';
                } else {
                  searchToggle.textContent = grid.classList.contains('is-collapsed') ? '展开' : '收起';
                }
                refreshIcons();
              }
              return;
            }

            var closeDrawer = event.target.closest('[data-close-drawer]');
            if (closeDrawer) {
              var drawer = closest(closeDrawer, '.drawer-panel');
              if (drawer) drawer.classList.remove('is-open');
              updateDrawerMask();
              updateDrawerShift();
            }
          });

          window.prototypeShell = window.prototypeShell || {};

          window.prototypeShell.toast = function (message) {
            var toast = document.querySelector('.message-toast');
            if (!toast) {
              toast = document.createElement('div');
              toast.className = 'message-toast';
              document.body.appendChild(toast);
            }
            toast.textContent = message || '操作成功';
            window.clearTimeout(toast.__timer);
            toast.__timer = window.setTimeout(function () {
              if (toast && toast.parentNode) toast.parentNode.removeChild(toast);
            }, 1800);
          };

          window.prototypeShell.openDrawer = function (id) {
            var drawer = document.getElementById(id);
            if (!drawer) return;
            drawer.classList.add('is-open');
            updateDrawerMask();
            updateDrawerShift();
          };

          window.prototypeShell.closeDrawers = function () {
            document.querySelectorAll('.drawer-panel.is-open').forEach(function (drawer) {
              drawer.classList.remove('is-open');
              drawer.style.removeProperty('--drawer-shift');
            });
            updateDrawerMask();
          };

          function updateDrawerMask() {
            var mask = document.querySelector('.drawer-mask');
            if (!mask) return;
            var hasOpen = document.querySelector('.drawer-panel.is-open');
            mask.classList.toggle('is-open', Boolean(hasOpen));
          }

          function updateDrawerShift() {
            var openPanels = Array.prototype.slice.call(document.querySelectorAll('.drawer-panel.is-open'));
            openPanels.forEach(function (panel, index) {
              if (index < openPanels.length - 1) {
                panel.classList.add('is-shifted');
                panel.style.setProperty('--drawer-shift', '180px');
              } else {
                panel.classList.remove('is-shifted');
                panel.style.removeProperty('--drawer-shift');
              }
            });
          }

          var drawerMask = document.querySelector('.drawer-mask');
          if (drawerMask) {
            drawerMask.addEventListener('click', window.prototypeShell.closeDrawers);
          }

          refreshIcons();
        })();
        """
    )
    return (
        script.replace("__TOGGLE_SELECTOR__", toggle_selector)
        .replace("__ROOT_SELECTOR__", root_selector)
        .replace("__FILTER_SELECTOR__", filter_selector)
        .replace("__FILTER_GRID_SELECTOR__", filter_grid_selector)
    )


def render_prototype_config(framework: str, project_name: str, authoring_mode: str) -> str:
    config = {
        "framework": framework,
        "fidelity": "product",
        "projectName": project_name,
        "authoringMode": authoring_mode,
        "sharedOwnership": "llm" if authoring_mode == "llm" else "generator",
        "featureRoot": "src/features" if framework in {"react", "vue"} else ".",
        "registry": "src/prototype-registry.js" if framework in {"react", "vue"} else None,
        "sharedCss": [
            "shared/css/tokens.css",
            "shared/css/product-shell.css",
            "shared/css/product-components.css",
            "shared/css/product-patterns.css",
            "shared/css/prototype-meta.css",
        ],
        "sharedJs": ["shared/js/product-icons.js", "shared/js/product-shell.js"],
    }
    return json.dumps(config, ensure_ascii=False, indent=2) + "\n"


def render_shared_registry(source_hash: str, existing_path: Path | None = None) -> str:
    registry = {
        "version": 1,
        "designSourceSha256": source_hash,
        "components": {},
        "patterns": {},
        "interactions": {},
        "promotionRules": {
            "featureLocal": "Used by one page or one feature only",
            "sharedCandidate": "Used by two or more features or explicitly defined as a product pattern in DESIGN.md",
            "requiredFields": ["description", "files", "selectors", "usedBy"],
        },
    }
    if existing_path and existing_path.exists():
        try:
            existing = json.loads(existing_path.read_text(encoding="utf-8"))
        except (OSError, json.JSONDecodeError):
            existing = {}
        if isinstance(existing, dict):
            for section in ("components", "patterns", "interactions"):
                if isinstance(existing.get(section), dict):
                    registry[section] = existing[section]
    return json.dumps(registry, ensure_ascii=False, indent=2) + "\n"


def render_persistent_ledger(existing_path: Path, key: str) -> str:
    """Create a user-owned ledger without discarding valid existing entries."""
    ledger: dict[str, Any] = {"version": 1, key: {}}
    if existing_path.exists():
        try:
            existing = json.loads(existing_path.read_text(encoding="utf-8"))
        except (OSError, json.JSONDecodeError):
            existing = {}
        if isinstance(existing, dict) and isinstance(existing.get(key), dict):
            ledger[key] = existing[key]
    return json.dumps(ledger, ensure_ascii=False, indent=2) + "\n"


def render_design_change_plan(
    previous: dict[str, Any],
    current: dict[str, Any],
    reviews_path: Path,
    registry_path: Path,
    generated_at: str,
) -> tuple[str, list[str], list[str]]:
    domains = ["tokens", "shell", "components", "patterns", "rules"]
    previous_hashes = previous.get("runtimeHashes") or previous.get("meta", {}).get("runtimeHashes") or {}
    current_hashes = current.get("runtimeHashes") or current.get("meta", {}).get("runtimeHashes") or {}
    changed = [domain for domain in domains if previous_hashes.get(domain) != current_hashes.get(domain)]
    try:
        reviews = json.loads(reviews_path.read_text(encoding="utf-8")).get("reviews", {})
    except (OSError, json.JSONDecodeError):
        reviews = {}
    try:
        registry = json.loads(registry_path.read_text(encoding="utf-8"))
    except (OSError, json.JSONDecodeError):
        registry = {}
    affected_pages: set[str] = set()
    affected_refs: set[str] = set()
    global_change = bool({"tokens", "shell"}.intersection(changed))
    review_values = reviews.values() if isinstance(reviews, dict) else []
    for review in review_values:
        dependencies = review.get("designDomains") if isinstance(review, dict) else None
        dependencies = dependencies if isinstance(dependencies, list) and dependencies else domains
        if global_change or set(changed).intersection(dependencies):
            page_key = review.get("pageKey") or review.get("path")
            if page_key:
                affected_pages.add(str(page_key))
            for ref in review.get("sharedRefs", []) if isinstance(review, dict) else []:
                affected_refs.add(str(ref))
    if {"tokens", "shell"}.intersection(changed):
        for section in ("components", "patterns", "interactions"):
            entries = registry.get(section, {}) if isinstance(registry, dict) else {}
            for name, entry in entries.items():
                affected_refs.add(f"{section}.{name}")
                for page_key in entry.get("usedBy", []) if isinstance(entry, dict) else []:
                    affected_pages.add(str(page_key))
    plan = {
        "version": 1,
        "generatedAt": generated_at,
        "previous": {
            "sourceSha256": previous.get("sourceSha256") or previous.get("meta", {}).get("sourceSha256", ""),
            "designRuntimeSha256": previous.get("designRuntimeSha256") or previous.get("meta", {}).get("designRuntimeSha256", ""),
            "runtimeHashes": previous_hashes,
        },
        "current": {
            "sourceSha256": current.get("sourceSha256") or current.get("meta", {}).get("sourceSha256", ""),
            "designRuntimeSha256": current.get("designRuntimeSha256") or current.get("meta", {}).get("designRuntimeSha256", ""),
            "runtimeHashes": current_hashes,
        },
        "changedDomains": changed,
        "affectedPageKeys": sorted(affected_pages),
        "affectedSharedRefs": sorted(affected_refs),
        "requiredActions": (
            ["Reconcile shared or shell assets", "Re-finalize the design system", "Re-review affected pages"]
            if changed
            else ["No rendered-design reconciliation required"]
        ),
    }
    return json.dumps(plan, ensure_ascii=False, indent=2) + "\n", changed, sorted(affected_pages)


def render_authoring_status(
    source_hash: str,
    runtime_hash: str,
    authoring_mode: str,
    existing_path: Path | None = None,
) -> str:
    status = {
        "version": 3,
        "mode": authoring_mode,
        "status": "pending-layout-review",
        "designSourceSha256": source_hash,
        "designRuntimeSha256": runtime_hash,
        "authoredAt": None,
        "files": {},
        "visualEvidence": {},
    }
    if existing_path and existing_path.exists():
        try:
            existing = json.loads(existing_path.read_text(encoding="utf-8"))
        except (OSError, json.JSONDecodeError):
            existing = {}
        if (
            isinstance(existing, dict)
            and existing.get("status") == "ready"
            and existing.get("mode") == authoring_mode
            and existing.get("designRuntimeSha256") == runtime_hash
        ):
            if int(existing.get("version") or 1) >= 3 and existing.get("manifest") and existing.get("layoutReport"):
                status.update(existing)
            else:
                status["legacyStatus"] = "ready"
                status["migrationReason"] = "Layout evidence was not produced from the v2 region contract and dynamic viewport manifest."
            status["designSourceSha256"] = source_hash
            status["designRuntimeSha256"] = runtime_hash
    return json.dumps(status, ensure_ascii=False, indent=2) + "\n"


def render_authoring_brief(project_name: str, framework: str, source_hash: str) -> str:
    return clean_block(
        f"""
        # Product Design-System Authoring Brief

        Project: {project_name}
        Framework: {framework}
        DESIGN.md SHA-256: {source_hash}

        The initializer creates a traceable seed, not permission to infer missing product facts.

        1. Read `design-system/authoring-context.json`. For layout contract v2, load only the current template's routed `design-system/contexts/layout/<profile>.json`. `design-contract.json` and `check-rules.json` are machine input; do not load them in normal authoring.
        2. Read the complete `DESIGN.md` only for the first shared-system pass, a confirmed design gap, or a conflict that the compact context cannot resolve.
        3. Author only representative templates declared with `representative: true`. Keep developer launchers and audit controls outside the product root.
        4. Run `node scripts/prepare-layout-audit.cjs`, serve the project with a local HTTP server, and open `design-system/layout-audit.html`.
        5. Save the exported report as `design-system/layout-report.json`; capture each raw representative page at the exact manifest viewports.
        6. Finalize with `node scripts/finalize-design-system.cjs --manifest design-system/preview-manifest.json`.

        Shared files and representative previews are agent/user-owned after creation. Refresh does not overwrite them. Promote only evidence-backed patterns used by two features or explicitly declared stable in DESIGN.
        """
    )


def render_fidelity_guardrails(
    design: dict[str, Any],
    *,
    source_hash: str,
    runtime_hash: str,
    framework: str,
    check_rules: dict[str, Any],
) -> str:
    guardrails = {
        "version": 1,
        "sourceSha256": source_hash,
        "designRuntimeSha256": runtime_hash,
        "framework": framework,
        "requiredBeforeEditing": [
            "Read AGENTS.md",
            "Read design-system/context-index.json and select one task profile",
            "Read only the selected domain from design-system/authoring-context.json",
            "Read design-system/shared-registry.json before adding reusable UI or interaction code",
            "Read the full DESIGN.md only for first shared authoring, a confirmed design gap, or a compact-context conflict",
        ],
        "sharedCss": [
            "shared/css/tokens.css",
            "shared/css/product-shell.css",
            "shared/css/product-components.css",
            "shared/css/product-patterns.css",
            "shared/css/prototype-meta.css",
        ],
        "sharedJs": ["shared/js/product-icons.js", "shared/js/product-shell.js"],
        "pageMetadata": check_rules.get("productFidelity", {}).get("requiredPageMetadata", []),
        "productFidelity": check_rules.get("productFidelity", {}),
        "copywriting": check_rules.get("copywriting", {}),
        "legacyTokens": check_rules.get("legacyTokens", {}),
        "selfCheck": mapping(design, "generationRules").get("selfCheck", []),
        "blockingCheck": "node scripts/check-prototype-compliance.cjs",
        "reviewCommand": "node scripts/record-fidelity-review.cjs <page-or-component> --viewport <id>,<image>,<width>,<height>[,<dpr>]",
        "incrementalDiffCommand": "python3 scripts/compare-prototype-screenshots.py --baseline-desktop <baseline.png> --current-desktop <current.png> --baseline-mobile <baseline-mobile.png> --current-mobile <current-mobile.png> --masks <masks.json> --output <visual-diff.json>",
        "reconstructionDiffCommand": "python3 scripts/compare-prototype-screenshots.py --mode reconstruction --baseline-desktop <reference.png> --current-desktop <current.png> --baseline-mobile <reference-mobile.png> --current-mobile <current-mobile.png> --masks <unstable-masks.json> --output <comparison-report.json>",
        "evidenceSources": "design-system/evidence-sources.json",
        "designGaps": "design-system/design-gaps.json",
        "releaseCheck": "node scripts/check-prototype-compliance.cjs --release",
        "prepareLayoutAudit": "node scripts/prepare-layout-audit.cjs",
        "finalizeDesignSystem": "node scripts/finalize-design-system.cjs --manifest design-system/preview-manifest.json",
    }
    return json.dumps(guardrails, ensure_ascii=False, indent=2) + "\n"


def render_context_index(
    design: dict[str, Any],
    *,
    source_hash: str,
    runtime_hash: str,
    framework: str,
    check_rules: dict[str, Any],
    runtime_hashes: dict[str, str] | None = None,
) -> str:
    section_hashes = {
        key: hashlib.sha256(
            json.dumps(value, ensure_ascii=False, sort_keys=True, separators=(",", ":")).encode("utf-8")
        ).hexdigest()
        for key, value in design.items()
        if key in {"tokens", "layout", "components", "pageTemplates", "generationRules", "copywriting"}
    }
    context = {
        "version": 1,
        "framework": framework,
        "sourceSha256": source_hash,
        "designRuntimeSha256": runtime_hash,
        "runtimeHashes": runtime_hashes or {},
        "sectionSha256": section_hashes,
        "defaultProfile": "new-feature",
        "profiles": {
            "design-system": {
                "when": ["initial authoring", "DESIGN changed", "shared changed", "new stable pattern"],
                "read": [
                    "design-system/authoring-brief.md",
                    "design-system/authoring-context.json",
                    "design-system/shared-registry.json",
                    "only shared/templates files named by the selected domain",
                ],
                "readFullDesignOnlyIf": ["first shared-system authoring pass", "confirmed design gap", "compact context conflict"],
            },
            "new-feature": {
                "when": ["new page reusing existing product patterns"],
                "read": [
                    "AGENTS.md",
                    "design-system/fidelity-guardrails.json",
                    "relevant shared-registry entries",
                    "feature-manifest.json",
                    "closest existing page and only referenced shared files",
                ],
                "readFullDesignOnlyIf": ["contract conflict", "missing pattern", "shared change required"],
            },
            "incremental": {
                "when": ["upgrade", "optimization", "field addition", "small adjustment with a local baseline"],
                "read": [
                    "AGENTS.md",
                    "baseline page/component",
                    "incremental-contract.json",
                    "feature-manifest.json",
                    "relevant shared-registry entries and referenced shared files",
                ],
                "readFullDesignOnlyIf": ["shared change required", "new stable pattern", "evidence conflict"],
            },
            "reconstruction": {
                "when": ["product screenshot", "product URL", "existing product without a local prototype baseline"],
                "read": [
                    "AGENTS.md",
                    "design-system/evidence-sources.json",
                    "reconstruction-contract.json",
                    "relevant shared-registry entries and referenced shared files",
                    "closest approved page when available",
                ],
                "readFullDesignOnlyIf": ["shared gap confirmed", "design gap confirmed", "evidence conflict"],
            },
            "verification": {
                "when": ["compliance", "review", "release"],
                "read": [
                    "design-system/fidelity-guardrails.json",
                    "target page/component",
                    "design-system/fidelity-reviews.json",
                    "fidelity evidence and incremental contract when present",
                    "design-system/design-gaps.json",
                ],
            },
        },
        "pageTemplates": check_rules.get("productFidelity", {}).get("pageTemplateIds", []),
        "classFingerprints": check_rules.get("productFidelity", {}).get("classFingerprints", []),
        "blockingChecks": [
            "node scripts/check-prototype-compliance.cjs",
            "node scripts/check-prototype-compliance.cjs --release",
        ],
    }
    return json.dumps(context, ensure_ascii=False, indent=2) + "\n"


def render_authoring_context(design: dict[str, Any], source_hash: str, runtime_hash: str) -> str:
    if is_layout_v2(design):
        model = normalize_layout_model(design)
        context = {
            "version": 2,
            "sourceSha256": source_hash,
            "designRuntimeSha256": runtime_hash,
            "identity": {key: design.get(key) for key in ("name", "language", "summary", "initialization")},
            "routing": {
                str(profile.get("id")): f"design-system/contexts/layout/{kebab(str(profile.get('id')))}.json"
                for profile in model.get("profiles", [])
            },
            "verification": ["design-system/layout-model.json", "design-system/layout-contract.json", "design-system/preview-manifest.json"],
            "machineOnly": ["design-system/design-contract.json", "design-system/check-rules.json"],
        }
        return json.dumps(context, ensure_ascii=False, indent=2) + "\n"
    representatives = [
        item for item in design.get("pageTemplates", [])
        if isinstance(item, dict) and item.get("representative") is True
    ]
    referenced_components = {
        str(name)
        for item in representatives
        for name in (item.get("components") if isinstance(item.get("components"), list) else [])
    }
    components = design.get("components") if isinstance(design.get("components"), dict) else {}
    context = {
        "version": 1,
        "sourceSha256": source_hash,
        "designRuntimeSha256": runtime_hash,
        "identity": {key: design.get(key) for key in ("name", "language", "summary", "initialization")},
        "domains": {
            "tokens": design.get("tokens", {}),
            "layout": design.get("layout", {}),
            "components": {key: components[key] for key in sorted(referenced_components) if key in components},
            "representativeTemplates": representatives,
            "rules": design.get("generationRules", {}),
        },
        "routing": {
            "tokens": ["domains.tokens"],
            "shell": ["domains.tokens", "domains.layout"],
            "components": ["domains.tokens", "domains.components"],
            "patterns": ["domains.representativeTemplates", "domains.components"],
            "verification": ["design-system/layout-contract.json", "design-system/preview-manifest.json"],
        },
        "machineOnly": ["design-system/design-contract.json", "design-system/check-rules.json"],
    }
    return json.dumps(context, ensure_ascii=False, indent=2) + "\n"


def _referenced_token_paths(value: Any) -> set[str]:
    if isinstance(value, dict):
        return set().union(*(_referenced_token_paths(item) for item in value.values()), set())
    if isinstance(value, list):
        return set().union(*(_referenced_token_paths(item) for item in value), set())
    if isinstance(value, str):
        return set(TOKEN_REF_RE.findall(value))
    return set()


def _token_subset(tokens: dict[str, Any], paths: set[str]) -> dict[str, Any]:
    result: dict[str, Any] = {}
    for dotted in sorted(paths):
        source: Any = tokens
        valid = True
        for part in dotted.split("."):
            if not isinstance(source, dict) or part not in source:
                valid = False
                break
            source = source[part]
        if not valid:
            continue
        target = result
        parts = dotted.split(".")
        for part in parts[:-1]:
            target = target.setdefault(part, {})
        target[parts[-1]] = source
    return result


def render_profile_contexts(design: dict[str, Any], source_hash: str, runtime_hash: str) -> dict[str, str]:
    if not is_layout_v2(design):
        return {}
    model = normalize_layout_model(design)
    components = design.get("components") if isinstance(design.get("components"), dict) else {}
    tokens = design.get("tokens") if isinstance(design.get("tokens"), dict) else {}
    outputs: dict[str, str] = {}
    for profile in model.get("profiles", []):
        profile_id = str(profile.get("id"))
        templates = [item for item in model.get("pageTemplates", []) if item.get("layoutProfile") == profile_id]
        component_ids = {str(ref) for template in templates for ref in template.get("components", []) if isinstance(ref, str)}
        token_paths = _referenced_token_paths(profile) | _referenced_token_paths(templates) | _referenced_token_paths({key: components.get(key) for key in component_ids})
        context = {
            "version": 1,
            "sourceSha256": source_hash,
            "designRuntimeSha256": runtime_hash,
            "profile": profile,
            "templates": templates,
            "components": {key: components[key] for key in sorted(component_ids) if key in components},
            "tokens": _token_subset(tokens, token_paths),
            "rules": design.get("generationRules", {}),
        }
        outputs[f"design-system/contexts/layout/{kebab(profile_id)}.json"] = json.dumps(context, ensure_ascii=False, indent=2) + "\n"
    return outputs


def render_fidelity_reviews(source_hash: str, runtime_hash: str) -> str:
    reviews = {
        "version": 1,
        "designRuntimeSha256": runtime_hash,
        "reviews": {},
    }
    return json.dumps(reviews, ensure_ascii=False, indent=2) + "\n"


def _selector_attrs(selector: str, region_id: str) -> str:
    if selector.startswith("."):
        return f'class="{html.escape(" ".join(part for part in selector.split(".") if part))}" data-layout-region="{html.escape(region_id)}"'
    if selector.startswith("#"):
        return f'id="{html.escape(selector[1:])}" data-layout-region="{html.escape(region_id)}"'
    match = re.fullmatch(r"\[([^=\]]+)(?:=[\"']([^\"']+)[\"'])?\]", selector)
    if match:
        value = f'="{html.escape(match.group(2))}"' if match.group(2) is not None else ""
        return f'{html.escape(match.group(1))}{value} data-layout-region="{html.escape(region_id)}"'
    return f'data-layout-region="{html.escape(region_id)}"'


def _render_items(items: Any, *, tag: str = "span", class_name: str = "") -> str:
    values = items if isinstance(items, list) else []
    attr = f' class="{class_name}"' if class_name else ""
    return "".join(f"<{tag}{attr}>{html.escape(str(item.get('label') if isinstance(item, dict) and item.get('label') is not None else item))}</{tag}>" for item in values)


def render_content_block(block: dict[str, Any]) -> str:
    kind = str(block.get("type") or "")
    block_id = html.escape(str(block.get("id") or ""))
    attrs = f' data-content-block="{block_id}" data-block-type="{html.escape(kind)}"'
    if kind == "heading":
        level = int(block.get("level") or 2) if str(block.get("level") or "2").isdigit() else 2
        level = min(6, max(1, level))
        return f"<h{level}{attrs}>{html.escape(str(block.get('text') or ''))}</h{level}>"
    if kind == "text":
        return f"<p{attrs}>{html.escape(str(block.get('text') or ''))}</p>"
    if kind == "navigation":
        return f'<nav{attrs} aria-label="{html.escape(str(block.get("label") or ""))}">{_render_items(block.get("items"), tag="a")}</nav>'
    if kind == "actions":
        return f"<div{attrs}>{_render_items(block.get('items'), tag='button')}</div>"
    if kind == "form":
        fields: list[str] = []
        for field in block.get("fields", []) if isinstance(block.get("fields"), list) else []:
            if not isinstance(field, dict):
                continue
            label = html.escape(str(field.get("label") or ""))
            placeholder = html.escape(str(field.get("placeholder") or ""))
            fields.append(f'<label><span>{label}</span><input type="text" placeholder="{placeholder}"></label>')
        return f"<form{attrs}>{''.join(fields)}</form>"
    if kind == "table":
        columns = block.get("columns") if isinstance(block.get("columns"), list) else []
        rows = block.get("rows") if isinstance(block.get("rows"), list) else []
        head = "".join(f"<th>{html.escape(str(column.get('label') if isinstance(column, dict) and column.get('label') is not None else column))}</th>" for column in columns)
        body: list[str] = []
        for row in rows:
            cells = row if isinstance(row, list) else list(row.values()) if isinstance(row, dict) else [row]
            body.append("<tr>" + "".join(f"<td>{html.escape(str(cell))}</td>" for cell in cells) + "</tr>")
        return f"<div{attrs}><table><thead><tr>{head}</tr></thead><tbody>{''.join(body)}</tbody></table></div>"
    if kind in {"list", "cards"}:
        tag = "ul" if kind == "list" else "div"
        item_tag = "li" if kind == "list" else "article"
        return f"<{tag}{attrs}>{_render_items(block.get('items'), tag=item_tag)}</{tag}>"
    if kind == "media":
        source = html.escape(str(block.get("src") or ""))
        alt = html.escape(str(block.get("alt") or ""))
        return f'<figure{attrs}><img src="{source}" alt="{alt}"></figure>'
    if kind == "detail":
        rows = []
        for item in block.get("items", []) if isinstance(block.get("items"), list) else []:
            if isinstance(item, dict):
                rows.append(f"<div><dt>{html.escape(str(item.get('label') or ''))}</dt><dd>{html.escape(str(item.get('value') or ''))}</dd></div>")
        return f"<dl{attrs}>{''.join(rows)}</dl>"
    if kind == "component":
        return f'<div{attrs} data-component-ref="{html.escape(str(block.get("component") or ""))}">{html.escape(str(block.get("content") or ""))}</div>'
    return f'<div{attrs} data-authoring-slot="pending"></div>'


def _region_payload(template: dict[str, Any], region: dict[str, Any]) -> str:
    preview = template.get("previewContent") if isinstance(template.get("previewContent"), dict) else {}
    regions = preview.get("regions") if isinstance(preview.get("regions"), dict) else {}
    payload = regions.get(region.get("id"))
    blocks: list[dict[str, Any]] = []
    if isinstance(payload, dict) and isinstance(payload.get("blocks"), list):
        blocks = [item for item in payload.get("blocks", []) if isinstance(item, dict)]
    elif isinstance(payload, list):
        if all(isinstance(item, dict) and item.get("type") for item in payload):
            blocks = [item for item in payload if isinstance(item, dict)]
        else:
            return _render_items(payload)
    elif isinstance(payload, str):
        return html.escape(payload)
    elif isinstance(payload, dict):
        if payload.get("text") is not None:
            return html.escape(str(payload.get("text")))
        if isinstance(payload.get("items"), list):
            return _render_items(payload.get("items"))
    # Template-level blocks describe page content.  They belong to the declared
    # content region, never to its structural `main` ancestor as well.  Rendering
    # them in both places duplicates business content and can put it before a
    # required route-tabs region.
    if not blocks and region.get("role") == "content":
        blocks = [item for item in preview.get("blocks", []) if isinstance(item, dict)] if isinstance(preview.get("blocks"), list) else []
    return "".join(render_content_block(block) for block in blocks)


def render_universal_preview_page(
    design: dict[str, Any],
    template: dict[str, Any],
    profile: dict[str, Any],
    source_hash: str,
    runtime_hash: str,
    *,
    pending: bool,
) -> str:
    regions = profile.get("regions", [])
    region_map = {str(item.get("id")): item for item in regions}
    children: dict[str | None, list[dict[str, Any]]] = {}
    for region in regions:
        viewport_ids = [str(item.get("id")) for item in profile.get("viewports", [])]
        if all(region.get("presence", {}).get(viewport_id) == "absent" for viewport_id in viewport_ids):
            continue
        children.setdefault(region.get("parent"), []).append(region)

    tag_by_role = {
        "header": "header",
        "navigation-primary": "nav",
        "navigation-secondary": "aside",
        "bottom-navigation": "nav",
        "footer": "footer",
        "main": "main",
    }

    def render_region(region_id: str) -> str:
        region = region_map[region_id]
        tag = tag_by_role.get(str(region.get("role")), "div")
        attrs = _selector_attrs(str(region.get("selector") or ""), region_id)
        if region_id == profile.get("rootRegion"):
            attrs += (
                f' data-page-key="design-system-preview-{html.escape(kebab(str(template.get("id"))))}"'
                f' data-layout-profile="{html.escape(str(profile.get("id")))}"'
                f' data-design-source-sha="{html.escape(source_hash)}"'
                f' data-design-runtime-sha="{html.escape(runtime_hash)}"'
                f' data-design-contract-version="5"'
                + (' data-authoring-pending="true"' if pending else '')
            )
        body = _region_payload(template, region)
        body += "".join(render_region(str(child.get("id"))) for child in children.get(region_id, []))
        return f"<{tag} {attrs}>{body}</{tag}>"

    root_id = str(profile.get("rootRegion"))
    language = html.escape(str(design.get("language") or ""))
    title = html.escape(str(template.get("name") or template.get("id") or ""))
    return clean_block(
        f"""
        <!doctype html>
        <html lang="{language}">
        <head>
          <meta charset="utf-8">
          <meta name="viewport" content="width=device-width, initial-scale=1">
          <title>{title}</title>
          <link rel="stylesheet" href="../../shared/css/tokens.css">
          <link rel="stylesheet" href="../../shared/css/product-shell.css">
          <link rel="stylesheet" href="../../shared/css/product-components.css">
          <link rel="stylesheet" href="../../shared/css/product-patterns.css">
        </head>
        <body>{render_region(root_id)}</body>
        </html>
        """
    )


def _css_property(name: str) -> str:
    return re.sub(r"([a-z0-9])([A-Z])", r"\1-\2", name).replace("_", "-").lower()


def _css_declarations(values: Any) -> list[str]:
    if not isinstance(values, dict):
        return []
    rows: list[str] = []
    for name, value in values.items():
        if not re.fullmatch(r"[A-Za-z][A-Za-z0-9_-]*", str(name)) or isinstance(value, (dict, list)) or value is None:
            continue
        rendered = css_value(value, unit="px" if name in {"width", "height", "minWidth", "maxWidth", "minHeight", "maxHeight", "gap", "padding", "margin"} else "")
        rows.append(f"{_css_property(str(name))}:{rendered};")
    return rows


def _viewport_media(profile: dict[str, Any], viewport: dict[str, Any]) -> str:
    if viewport.get("minWidth") is not None or viewport.get("maxWidth") is not None:
        parts = []
        if viewport.get("minWidth") is not None:
            parts.append(f"(min-width:{viewport['minWidth']}px)")
        if viewport.get("maxWidth") is not None:
            parts.append(f"(max-width:{viewport['maxWidth']}px)")
        return " and ".join(parts)
    viewports = sorted(profile.get("viewports", []), key=lambda item: NumberLike(item.get("width")))
    if len(viewports) <= 1:
        return ""
    index = next((i for i, item in enumerate(viewports) if item.get("id") == viewport.get("id")), 0)
    breakpoints = sorted(
        [NumberLike(item.get("maxWidth")) for item in profile.get("breakpoints", []) if item.get("maxWidth") is not None]
    )
    if len(breakpoints) == len(viewports) - 1:
        lower = None if index == 0 else breakpoints[index - 1] + 1
        upper = None if index == len(viewports) - 1 else breakpoints[index]
        parts = ([f"(min-width:{lower}px)"] if lower is not None else []) + ([f"(max-width:{upper}px)"] if upper is not None else [])
        return " and ".join(parts)
    lower = None if index == 0 else (NumberLike(viewports[index - 1].get("width")) + NumberLike(viewport.get("width"))) // 2 + 1
    upper = None if index == len(viewports) - 1 else (NumberLike(viewport.get("width")) + NumberLike(viewports[index + 1].get("width"))) // 2
    parts = ([f"(min-width:{lower}px)"] if lower is not None else []) + ([f"(max-width:{upper}px)"] if upper is not None else [])
    return " and ".join(parts)


def NumberLike(value: Any) -> int:
    try:
        return int(float(value))
    except (TypeError, ValueError):
        return 0


def render_universal_layout_css(design: dict[str, Any], layout_model: dict[str, Any]) -> str:
    rows = [
        "/* Layout generated only from confirmed DESIGN layout profiles. */",
        "*,*::before,*::after{box-sizing:border-box;}",
        "html,body{margin:0;min-height:100%;}",
    ]
    for profile in layout_model.get("profiles", []):
        viewports = profile.get("viewports", [])
        root = next((item for item in profile.get("regions", []) if item.get("id") == profile.get("rootRegion")), None)
        if root and any(owner != "body" for owner in profile.get("scrollOwner", {}).values()):
            rows.append(f"{root.get('selector')}{{height:100vh;overflow:hidden;}}")
        for region in profile.get("regions", []):
            base = _css_declarations(region.get("styles", {}).get("base"))
            if base:
                rows.append(f"{region.get('selector')}{{{''.join(base)}}}")
        for viewport in viewports:
            viewport_id = str(viewport.get("id"))
            rules: list[str] = []
            for region in profile.get("regions", []):
                declarations = _css_declarations(region.get("styles", {}).get(viewport_id))
                declarations.extend(_css_declarations(region.get("geometry", {}).get(viewport_id)))
                presence = region.get("presence", {}).get(viewport_id)
                if presence == "absent":
                    declarations.append("display:none!important;")
                if profile.get("scrollOwner", {}).get(viewport_id) == region.get("id"):
                    declarations.extend(["overflow:auto;", "min-height:0;"])
                if declarations:
                    rules.append(f"{region.get('selector')}{{{''.join(declarations)}}}")
            media = _viewport_media(profile, viewport)
            rows.append(f"@media {media}{{{''.join(rules)}}}" if media else "".join(rules))
    return "\n".join(row for row in rows if row) + "\n"


def render_layout_contract(
    design: dict[str, Any],
    source_hash: str,
    runtime_hash: str,
    *,
    layout_model: dict[str, Any] | None = None,
) -> str:
    model = layout_model or normalize_layout_model(design)
    profiles: dict[str, Any] = {}
    for profile in model.get("profiles", []):
        viewport_ids = [str(item.get("id")) for item in profile.get("viewports", [])]
        regions = {}
        for region in profile.get("regions", []):
            regions[str(region.get("id"))] = {
                "role": region.get("role"),
                "selector": region.get("selector"),
                "parent": region.get("parent"),
                "before": region.get("before"),
                "after": region.get("after"),
                "domCount": dom_count(region, viewport_ids),
                "counts": {viewport_id: region_count(region, viewport_id) for viewport_id in viewport_ids},
                "geometry": region.get("geometry", {}),
            }
        profiles[str(profile.get("id"))] = {
            "productForm": profile.get("productForm"),
            "rootRegion": profile.get("rootRegion"),
            "viewports": {str(item.get("id")): item for item in profile.get("viewports", [])},
            "breakpoints": profile.get("breakpoints", []),
            "regions": regions,
            "scrollOwner": profile.get("scrollOwner", {}),
        }
    pages = {
        f"design-system-preview-{kebab(str(item.get('id')))}": {"templateId": item.get("id"), "layoutProfile": item.get("layoutProfile")}
        for item in model.get("pageTemplates", [])
        if item.get("representative") is True
    }
    contract = {
        "version": 2,
        "designSourceSha256": source_hash,
        "designRuntimeSha256": runtime_hash,
        "tolerancePx": 2,
        "source": model.get("source"),
        "profiles": profiles,
        "pages": pages,
        "forbiddenInsideProductRoot": [
            ".preview-switcher",
            ".prototype-preview-switcher",
            ".layout-audit-controls",
            "[data-developer-control]",
        ],
    }
    if model.get("source") == "legacy" and profiles:
        first_profile = next(iter(profiles.values()))
        route_region = next((item for item in first_profile.get("regions", {}).values() if item.get("role") == "route-tabs"), None)
        contract["counts"] = {"routeTags": route_region.get("domCount") if route_region else {"min": 0, "max": 0}}
        legacy_scroll = mapping(design, "layout").get("scrollOwner")
        contract["scrollOwner"] = legacy_scroll
    return json.dumps(contract, ensure_ascii=False, indent=2) + "\n"


def render_representative_previews(
    skill_dir: Path,
    design: dict[str, Any],
    project_name: str,
    framework: str,
    source_hash: str,
    runtime_hash: str,
    *,
    layout_model: dict[str, Any] | None = None,
) -> dict[str, str]:
    model = layout_model or normalize_layout_model(design)
    if is_layout_v2(design):
        profiles = {str(item.get("id")): item for item in model.get("profiles", [])}
        pending_ids = {str(item.get("templateId")) for item in model.get("pendingAuthoring", [])}
        pages: dict[str, str] = {}
        for template in model.get("pageTemplates", []):
            if template.get("representative") is not True:
                continue
            profile = profiles.get(str(template.get("layoutProfile")))
            if not profile:
                continue
            slug = kebab(str(template.get("id")))
            pages[f"design-system/preview/{slug}.html"] = render_universal_preview_page(
                design,
                template,
                profile,
                source_hash,
                runtime_hash,
                pending=str(template.get("id")) in pending_ids,
            )
        return pages
    if framework != "html":
        return {}
    pages: dict[str, str] = {}
    templates = design.get("pageTemplates") if isinstance(design.get("pageTemplates"), list) else []
    for template in templates:
        if not isinstance(template, dict) or template.get("representative") is not True:
            continue
        local_design = dict(design)
        local_templates = []
        for candidate in templates:
            if isinstance(candidate, dict):
                copied = dict(candidate)
                copied["representative"] = candidate is template
                local_templates.append(copied)
        local_design["pageTemplates"] = local_templates
        template_id = str(template.get("id"))
        slug = kebab(template_id)
        content = template_replacements(local_design, project_name, framework, source_hash, runtime_hash)
        content.update(
            {
                "{{PAGE_TITLE}}": html.escape(str(template.get("name"))),
                "{{FEATURE_NAME}}": html.escape(str(template.get("name"))),
                "{{FEATURE_SLUG}}": f"design-system-preview-{slug}",
                "{{PAGE_KEY}}": f"design-system-preview-{slug}",
                "{{PAGE_KIND}}": "page",
                "{{PARENT_PAGE_KEY}}": "",
                "{{SURFACE}}": "page",
                "{{REQUIREMENT_STATUS}}": "confirmed",
                "{{GENERATION_MODE}}": "design-system-preview",
                "{{DESIGN_DOMAINS}}": "tokens,shell,components,patterns,rules",
                "{{SHARED_REFS}}": "",
                "{{DESIGN_PROFILE_SHA}}": hashlib.sha256((runtime_hash + template_id).encode("utf-8")).hexdigest(),
                "{{SCENARIO_SURFACE}}": "",
            }
        )
        page = render_template(skill_dir, "prototype-page.template.html", content)
        page = page.replace('  <link rel="stylesheet" href="./assets/prototype.css">\n', "")
        page = page.replace('  <script src="./assets/prototype.js"></script>\n', "")
        page = page.replace('href="../shared/', 'href="../../shared/')
        page = page.replace('src="../shared/', 'src="../../shared/')
        page = page.replace('href="../index.html"', 'href="../../index.html"')
        pages[f"design-system/preview/{slug}.html"] = page
    return pages


def render_preview_launcher(preview_pages: dict[str, str], design: dict[str, Any]) -> str:
    links = []
    templates = [item for item in design.get("pageTemplates", []) if isinstance(item, dict) and item.get("representative") is True]
    for template in templates:
        slug = kebab(str(template.get("id")))
        target = f"./{slug}.html" if f"design-system/preview/{slug}.html" in preview_pages else "../../index.html"
        links.append(f'<li><a href="{target}">{html.escape(str(template.get("name")))}</a></li>')
    return clean_block(
        f"""
        <!doctype html>
        <html lang="{html.escape(str(design.get('language')))}">
        <head><meta charset="utf-8"><meta name="viewport" content="width=device-width,initial-scale=1"><title>Design-system previews</title></head>
        <body data-developer-control="preview-launcher">
          <h1>Design-system previews</h1>
          <p>本页是产品 Shell 外部的开发入口；截图和布局审计必须针对下列独立页面。</p>
          <ul>{''.join(links)}</ul>
          <p><a href="../layout-audit.html">打开布局审计</a></p>
        </body></html>
        """
    )


def render_root_preview_launcher(preview_pages: dict[str, str], design: dict[str, Any]) -> str:
    links = []
    for template in [item for item in design.get("pageTemplates", []) if isinstance(item, dict) and item.get("representative") is True]:
        slug = kebab(str(template.get("id")))
        if f"design-system/preview/{slug}.html" in preview_pages:
            links.append(f'<li><a href="./design-system/preview/{slug}.html">{html.escape(str(template.get("name")))}</a></li>')
    return clean_block(
        f"""
        <!doctype html><html lang="{html.escape(str(design.get('language') or ''))}"><head><meta charset="utf-8"><meta name="viewport" content="width=device-width,initial-scale=1"><title>{html.escape(str(design.get('name')))} previews</title></head>
        <body data-developer-control="preview-launcher"><main><h1>{html.escape(str(design.get('name')))} previews</h1><ul>{''.join(links)}</ul><p><a href="./design-system/layout-audit.html">布局审计</a></p></main></body></html>
        """
    )


def render_preview_manifest(
    preview_pages: dict[str, str],
    design: dict[str, Any],
    framework: str,
    *,
    layout_model: dict[str, Any] | None = None,
) -> str:
    model = layout_model or normalize_layout_model(design)
    template_by_slug = {
        kebab(str(item.get("id"))): item
        for item in model.get("pageTemplates", [])
        if isinstance(item, dict) and item.get("representative") is True
    }
    profiles = {str(item.get("id")): item for item in model.get("profiles", [])}
    pages = []
    for relative, content in preview_pages.items():
        slug = Path(relative).stem
        template = template_by_slug[slug]
        profile_id = str(template.get("layoutProfile"))
        profile = profiles.get(profile_id, {})
        viewports = {
            str(viewport.get("id")): {
                "width": viewport.get("width"),
                "height": viewport.get("height"),
                "category": viewport.get("category"),
                "claim": viewport.get("claim"),
                "screenshot": f"design-system/evidence/{slug}-{kebab(str(viewport.get('id')))}.png",
            }
            for viewport in profile.get("viewports", [])
        }
        page = {
            "pageKey": f"design-system-preview-{slug}",
            "templateId": str(template.get("id")),
            "layoutProfile": profile_id,
            "path": relative,
            "pageSha256": hashlib.sha256(content.encode("utf-8")).hexdigest(),
            "viewports": viewports,
        }
        pages.append(page)
    if not pages and framework in {"react", "vue"}:
        templates = list(template_by_slug.values())
        if templates:
            template = templates[0]
            pages.append(
                {
                    "pageKey": f"design-system-preview-{kebab(str(template.get('id')))}",
                    "templateId": str(template.get("id")),
                    "layoutProfile": str(template.get("layoutProfile")),
                    "path": "index.html",
                    "pageSha256": "pending-prepare-layout-audit",
                    "viewports": {
                        str(viewport.get("id")): {
                            "width": viewport.get("width"),
                            "height": viewport.get("height"),
                            "category": viewport.get("category"),
                            "claim": viewport.get("claim"),
                            "screenshot": f"design-system/evidence/{kebab(str(template.get('id')))}-{kebab(str(viewport.get('id')))}.png",
                        }
                        for viewport in profiles.get(str(template.get("layoutProfile")), {}).get("viewports", [])
                    },
                }
            )
    manifest = {
        "version": 2,
        "layoutReport": "design-system/layout-report.json",
        "layoutContract": "design-system/layout-contract.json",
        "pages": pages,
        "resources": {},
    }
    return json.dumps(manifest, ensure_ascii=False, indent=2) + "\n"


def _get_design_value(design: dict[str, Any], dotted: str) -> Any:
    current: Any = design
    for part in dotted.split("."):
        if not isinstance(current, dict):
            return None
        current = current.get(part)
    return current


def render_layout_audit_html() -> str:
    return clean_block(
        r"""
        <!doctype html>
        <html lang="zh-CN">
        <head>
          <meta charset="utf-8"><meta name="viewport" content="width=device-width,initial-scale=1">
          <title>Prototype layout audit</title>
          <style>body{font:14px system-ui;margin:20px;color:#1f2329}.layout-audit-controls{position:sticky;top:0;background:#fff;padding:12px 0;z-index:2}iframe{border:1px solid #ccd2da;display:block;margin:12px 0;transform-origin:top left}.pass{color:#07883d}.fail{color:#c32222}pre{white-space:pre-wrap;background:#f5f7fa;padding:12px}</style>
        </head>
        <body data-developer-control="layout-audit">
          <h1>布局审计（不属于产品页面）</h1>
          <div class="layout-audit-controls"><button id="run">运行审计</button> <button id="download" disabled>导出 layout-report.json</button></div>
          <div id="frames"></div><pre id="result">请通过本地 HTTP 服务打开本页，然后运行审计。</pre>
          <script>
          let latestReport = null;
          const sleep = (ms) => new Promise((resolve) => setTimeout(resolve, ms));
          const rect = (node) => node ? Object.fromEntries(["x","y","width","height"].map((key) => [key, Math.round(node.getBoundingClientRect()[key] * 100) / 100])) : null;
          const check = (name, passed, actual, expected) => ({ name, passed: Boolean(passed), actual, expected });
          async function shaText(text) { const bytes = new TextEncoder().encode(text); const digest = await crypto.subtle.digest("SHA-256", bytes); return Array.from(new Uint8Array(digest)).map((v)=>v.toString(16).padStart(2,"0")).join(""); }
          const visible = (node) => { if (!node) return false; const style=getComputedStyle(node),box=node.getBoundingClientRect(); return style.display!=="none"&&style.visibility!=="hidden"&&box.width>0&&box.height>0; };
          const within = (value, rule, tolerance) => {
            if (typeof rule === "number") return Math.abs(Number(value)-rule)<=tolerance;
            if (!rule || typeof rule !== "object") return true;
            if (rule.exact!==undefined && Math.abs(Number(value)-Number(rule.exact))>Number(rule.tolerance??tolerance)) return false;
            if (rule.min!==undefined && Number(value)<Number(rule.min)-tolerance) return false;
            if (rule.max!==undefined && Number(value)>Number(rule.max)+tolerance) return false;
            return true;
          };
          async function auditViewport(page, viewport, contract, expectationViewportId) {
            const holder = document.createElement("section");
            holder.innerHTML = `<h2>${page.templateId} · ${viewport.width}×${viewport.height}</h2>`;
            const frame = document.createElement("iframe"); frame.width=viewport.width; frame.height=viewport.height; frame.src=`../${page.path}?audit=${Date.now()}`; holder.append(frame); document.querySelector("#frames").append(holder);
            await new Promise((resolve,reject)=>{frame.onload=resolve;frame.onerror=reject}); await sleep(50);
            const doc=frame.contentDocument,profile=contract.profiles[page.layoutProfile],viewportId=expectationViewportId||viewport.id,tolerance=Number(contract.tolerancePx||2),checks=[],measurements={};
            const regionNodes={};
            for(const [regionId,region] of Object.entries(profile.regions||{})){
              const all=[...doc.querySelectorAll(region.selector)],shown=all.filter(visible),count=region.counts[viewportId]||{min:0,max:0};regionNodes[regionId]=shown;measurements[regionId]=shown.map(rect);
              checks.push(check(`${regionId} visible count`,shown.length>=count.min&&shown.length<=count.max,shown.length,count));
              for(const node of shown){
                if(region.parent){const parents=regionNodes[region.parent]||[...doc.querySelectorAll(profile.regions[region.parent].selector)].filter(visible);checks.push(check(`${regionId} parent`,parents.some((parent)=>parent.contains(node)),parents.some((parent)=>parent.contains(node)),region.parent));}
                if(region.before){const target=doc.querySelector(profile.regions[region.before].selector);checks.push(check(`${regionId} before ${region.before}`,target&&Boolean(node.compareDocumentPosition(target)&Node.DOCUMENT_POSITION_FOLLOWING),Boolean(target&&Boolean(node.compareDocumentPosition(target)&Node.DOCUMENT_POSITION_FOLLOWING)),true));}
                if(region.after){const target=doc.querySelector(profile.regions[region.after].selector);checks.push(check(`${regionId} after ${region.after}`,target&&Boolean(node.compareDocumentPosition(target)&Node.DOCUMENT_POSITION_PRECEDING),Boolean(target&&Boolean(node.compareDocumentPosition(target)&Node.DOCUMENT_POSITION_PRECEDING)),true));}
                const geometry=(region.geometry||{})[viewportId]||{},box=rect(node);for(const property of ["width","height"]){if(geometry[property]!==undefined)checks.push(check(`${regionId} ${property}`,within(box[property],geometry[property],tolerance),box[property],geometry[property]));}
              }
            }
            const rootRegion=profile.regions[profile.rootRegion],root=rootRegion&&doc.querySelector(rootRegion.selector);for(const selector of contract.forbiddenInsideProductRoot||[])checks.push(check(`no developer control ${selector}`,!root||root.querySelectorAll(selector).length===0,root?root.querySelectorAll(selector).length:0,0));
            const owner=profile.scrollOwner[viewportId];if(owner&&owner!=="body")checks.push(check("body has no extra scroll",doc.documentElement.scrollHeight<=viewport.height+tolerance&&doc.body.scrollHeight<=viewport.height+tolerance,Math.max(doc.documentElement.scrollHeight,doc.body.scrollHeight),viewport.height));
            return {width:viewport.width,height:viewport.height,expectationViewportId:viewportId,checks,measurements:{regions:measurements,bodyScrollHeight:Math.max(doc.documentElement.scrollHeight,doc.body.scrollHeight)},passed:checks.every((item)=>item.passed)};
          }
          async function run() {
            document.querySelector("#frames").innerHTML=""; document.querySelector("#result").textContent="运行中…";
            const manifestText=await fetch("preview-manifest.json",{cache:"no-store"}).then(r=>r.text()); const manifest=JSON.parse(manifestText); const contractText=await fetch("layout-contract.json",{cache:"no-store"}).then(r=>r.text()); const contract=JSON.parse(contractText); const pages=[];
            for (const page of manifest.pages) { const viewports={},breakpointProbes=[]; for (const [name,viewport] of Object.entries(page.viewports)) viewports[name]=await auditViewport(page,{...viewport,id:name},contract,name);const profile=contract.profiles[page.layoutProfile],ordered=Object.entries(profile.viewports).sort((a,b)=>Number(a[1].width)-Number(b[1].width));for(const point of profile.breakpoints||[]){const boundary=Number(point.maxWidth??point.minWidth);if(!Number.isFinite(boundary))continue;const lower=[...ordered].reverse().find(([,item])=>Number(item.width)<=boundary)||ordered[0],upper=ordered.find(([,item])=>Number(item.width)>boundary)||ordered[ordered.length-1];for(const [width,expected] of [[boundary-1,lower],[boundary,lower],[boundary+1,upper]]){if(width>0)breakpointProbes.push(await auditViewport(page,{width,height:Number(expected[1].height),id:`${point.id}-${width}`},contract,expected[0]));}}pages.push({pageKey:page.pageKey,path:page.path,pageSha256:page.pageSha256,layoutProfile:page.layoutProfile,viewports,breakpointProbes,passed:Object.values(viewports).every((item)=>item.passed)&&breakpointProbes.every((item)=>item.passed)}); }
            latestReport={version:2,generatedAt:new Date().toISOString(),manifestSha256:await shaText(manifestText),contractSha256:await shaText(contractText),pages,overallPassed:pages.every((page)=>page.passed)};
            document.querySelector("#result").textContent=JSON.stringify(latestReport,null,2); document.querySelector("#result").className=latestReport.overallPassed?"pass":"fail"; document.querySelector("#download").disabled=false;
          }
          document.querySelector("#run").onclick=()=>run().catch((error)=>{document.querySelector("#result").textContent=String(error);document.querySelector("#result").className="fail"});
          document.querySelector("#download").onclick=()=>{const blob=new Blob([JSON.stringify(latestReport,null,2)+"\n"],{type:"application/json"});const a=document.createElement("a");a.href=URL.createObjectURL(blob);a.download="layout-report.json";a.click();setTimeout(()=>URL.revokeObjectURL(a.href),1000)};
          </script>
        </body></html>
        """
    )


def prepare_layout_audit_script() -> str:
    return clean_block(
        r"""
        #!/usr/bin/env node
        const fs=require("fs"),path=require("path"),crypto=require("crypto"); const root=path.resolve(__dirname,"..");
        const manifestPath=path.join(root,"design-system/preview-manifest.json"); const manifest=JSON.parse(fs.readFileSync(manifestPath,"utf8"));
        const sha=(file)=>crypto.createHash("sha256").update(fs.readFileSync(file)).digest("hex");
        const inside=(relative)=>{const absolute=path.resolve(root,relative);const rel=path.relative(root,absolute);if(rel.startsWith("..")||path.isAbsolute(rel)||!fs.existsSync(absolute))throw new Error(`Missing project file: ${relative}`);return absolute};
        for(const page of manifest.pages||[]) page.pageSha256=sha(inside(page.path));
        const config=JSON.parse(fs.readFileSync(path.join(root,"design-system/prototype-config.json"),"utf8"));
        const resources=["shared/css/tokens.css","shared/css/product-shell.css","shared/css/product-components.css","shared/css/product-patterns.css","shared/css/prototype-meta.css","shared/js/product-icons.js","shared/js/product-shell.js","design-system/layout-model.json","design-system/layout-contract.json"];
        if(config.framework==="react")resources.push("src/App.jsx","src/styles.css"); else if(config.framework==="vue")resources.push("src/App.vue","src/styles.css"); else if(fs.existsSync(path.join(root,"templates/prototype-page.html")))resources.push("templates/prototype-page.html");
        manifest.resources=Object.fromEntries(resources.map((relative)=>[relative,sha(inside(relative))]));
        fs.writeFileSync(manifestPath,JSON.stringify(manifest,null,2)+"\n");
        console.log(`Prepared ${manifest.pages.length} representative pages. Serve the project and open design-system/layout-audit.html.`);
        """
    )


def finalize_design_system_script() -> str:
    return clean_block(
        r"""
        #!/usr/bin/env node
        const fs=require("fs"),path=require("path"),crypto=require("crypto"),zlib=require("zlib"); const root=path.resolve(__dirname,"..");
        const args=process.argv.slice(2),options={}; for(let i=0;i<args.length;i+=1){if(args[i].startsWith("--")){options[args[i].slice(2)]=args[i+1];i+=1}}
        const errors=[]; const readJson=(relative,fallback)=>{try{return JSON.parse(fs.readFileSync(path.join(root,relative),"utf8"))}catch(_){return fallback}}; const sha=(file)=>crypto.createHash("sha256").update(fs.readFileSync(file)).digest("hex");
        const inside=(relative,label)=>{if(!relative){errors.push(`missing ${label}`);return null}const absolute=path.resolve(root,relative),rel=path.relative(root,absolute).replaceAll(path.sep,"/");if(rel.startsWith("../")||path.isAbsolute(rel)||!fs.existsSync(absolute)||!fs.statSync(absolute).isFile()){errors.push(`${label} must be an existing file inside the project: ${relative}`);return null}return {absolute,relative:rel}};
        const paeth=(a,b,c)=>{const p=a+b-c,pa=Math.abs(p-a),pb=Math.abs(p-b),pc=Math.abs(p-c);return pa<=pb&&pa<=pc?a:pb<=pc?b:c};
        const pngInfo=(bytes)=>{if(!bytes.subarray(0,8).equals(Buffer.from([137,80,78,71,13,10,26,10])))return null;let offset=8,width=0,height=0,colorType=-1,bitDepth=0,idat=[];while(offset+12<=bytes.length){const length=bytes.readUInt32BE(offset),type=bytes.subarray(offset+4,offset+8).toString(),data=bytes.subarray(offset+8,offset+8+length);if(type==="IHDR"){width=data.readUInt32BE(0);height=data.readUInt32BE(4);bitDepth=data[8];colorType=data[9]}if(type==="IDAT")idat.push(data);offset+=12+length}let distinct=null;if(bitDepth===8&&[0,2,4,6].includes(colorType)){const bpp={0:1,2:3,4:2,6:4}[colorType],stride=width*bpp,raw=zlib.inflateSync(Buffer.concat(idat)),colors=new Set();let prior=Buffer.alloc(stride),cursor=0;for(let y=0;y<height;y+=1){const filter=raw[cursor++],row=Buffer.from(raw.subarray(cursor,cursor+stride));cursor+=stride;for(let x=0;x<stride;x+=1){const left=x>=bpp?row[x-bpp]:0,up=prior[x],upperLeft=x>=bpp?prior[x-bpp]:0;if(filter===1)row[x]=(row[x]+left)&255;else if(filter===2)row[x]=(row[x]+up)&255;else if(filter===3)row[x]=(row[x]+Math.floor((left+up)/2))&255;else if(filter===4)row[x]=(row[x]+paeth(left,up,upperLeft))&255}const step=Math.max(bpp,Math.floor(stride/64/bpp)*bpp);for(let x=0;x<stride&&colors.size<3;x+=step)colors.add(row.subarray(x,Math.min(x+bpp,stride)).toString("hex"));prior=row}distinct=colors.size}return {width,height,distinct}};
        const evidence=(relative,label,viewport)=>{const file=inside(relative,`${label} screenshot`);if(!file)return null;const bytes=fs.readFileSync(file.absolute),png=pngInfo(bytes),jpeg=bytes[0]===0xff&&bytes[1]===0xd8&&bytes[2]===0xff,webp=bytes.subarray(0,4).toString()==="RIFF"&&bytes.subarray(8,12).toString()==="WEBP";if(!png&&!jpeg&&!webp)errors.push(`${label} screenshot must be PNG, JPEG, or WebP`);if(png&&(png.width!==Number(viewport.width)||png.height!==Number(viewport.height)))errors.push(`${label} screenshot ${png.width}x${png.height} does not match viewport ${viewport.width}x${viewport.height}`);if(png&&png.distinct!==null&&png.distinct<2)errors.push(`${label} screenshot is a solid-color placeholder`);return {path:file.relative,sha256:sha(file.absolute),width:png&&png.width,height:png&&png.height}};
        if(!options.manifest){if(options.desktop||options.mobile)errors.push("legacy --desktop/--mobile evidence cannot produce ready status; use --manifest design-system/preview-manifest.json");else errors.push("finalization requires --manifest design-system/preview-manifest.json")}
        const manifestFile=options.manifest&&inside(options.manifest,"preview manifest"),manifest=manifestFile?readJson(manifestFile.relative,null):null; if(!manifest||!Array.isArray(manifest.pages)||!manifest.pages.length)errors.push("preview manifest must declare at least one representative page");
        const contractFile=manifest&&inside(manifest.layoutContract,"layout contract"),layoutContract=contractFile?readJson(contractFile.relative,{}):{},reportFile=manifest&&inside(manifest.layoutReport,"layout report"),report=reportFile?readJson(reportFile.relative,null):null;
        const selectorCount=(source,selector)=>{selector=String(selector||"");if(selector.startsWith("#"))return [...source.matchAll(new RegExp(`id=["']${selector.slice(1)}["']`,"g"))].length;if(selector.startsWith("[")){const name=selector.slice(1,-1).split("=")[0];return [...source.matchAll(new RegExp(`${name}(?:=|\\s|>)`,"g"))].length}const classes=selector.split(".").filter(Boolean);if(!classes.length)return 0;let count=0;for(const match of source.matchAll(/class=["']([^"']*)["']/g)){const values=new Set(match[1].split(/\s+/));if(classes.every((name)=>values.has(name)))count+=1}return count};
        if(report&&!report.overallPassed)errors.push("layout report did not pass"); if(report&&manifestFile&&report.manifestSha256!==sha(manifestFile.absolute))errors.push("layout report is stale for the current preview manifest"); if(report&&contractFile&&report.contractSha256!==sha(contractFile.absolute))errors.push("layout report is stale for the current layout contract");
        const config=readJson("design-system/prototype-config.json",{framework:"html",authoringMode:"llm"}); const files={},visualEvidence={pages:{}}; const reportPages=new Map(((report&&report.pages)||[]).map((item)=>[item.path,item]));
        for(const [relative,expected] of Object.entries((manifest&&manifest.resources)||{})){const file=inside(relative,`manifest resource ${relative}`);if(file&&sha(file.absolute)!==expected)errors.push(`manifest resource changed after layout preparation: ${relative}`);if(file)files[relative]=sha(file.absolute)}
        for(const page of (manifest&&manifest.pages)||[]){const file=inside(page.path,`representative page ${page.path}`);if(!file)continue;const currentSha=sha(file.absolute),source=fs.readFileSync(file.absolute,"utf8"),profile=layoutContract.profiles&&layoutContract.profiles[page.layoutProfile];if(!profile)errors.push(`missing layout profile ${page.layoutProfile} for ${page.path}`);if(source.includes("data-authoring-pending")||source.includes('data-authoring-slot="pending"'))errors.push(`representative page still has pending authoring slots: ${page.path}`);if(config.framework==="html"&&profile)for(const [regionId,region] of Object.entries(profile.regions||{})){const count=selectorCount(source,region.selector),expected=region.domCount||{min:0,max:1};if(count<expected.min||count>expected.max){if(region.role==="route-tabs"&&expected.min===1&&expected.max===1)errors.push(`representative page must contain exactly one route tags bar: ${page.path}`);else errors.push(`region ${regionId} count ${count} violates ${expected.min}..${expected.max}: ${page.path}`)}}if(config.framework==="html")for(const selector of layoutContract.forbiddenInsideProductRoot||[]){if(selectorCount(source,selector)>0)errors.push(`developer control ${selector} is forbidden in representative product page ${page.path}`)}if(page.pageSha256!==currentSha)errors.push(`representative page changed after layout preparation: ${page.path}`);files[file.relative]=currentSha;const audited=reportPages.get(page.path);if(!audited||audited.pageSha256!==currentSha||!audited.passed)errors.push(`missing passing current layout audit for ${page.path}`);if(audited&&Array.isArray(audited.breakpointProbes)&&audited.breakpointProbes.some((item)=>!item.passed))errors.push(`breakpoint probes failed for ${page.path}`);if(profile&&Array.isArray(profile.breakpoints)&&profile.breakpoints.length&&(!audited||!Array.isArray(audited.breakpointProbes)||audited.breakpointProbes.length<profile.breakpoints.length*3))errors.push(`missing breakpoint boundary audit for ${page.path}`);visualEvidence.pages[page.pageKey]={page:page.path,pageSha256:currentSha,layoutProfile:page.layoutProfile,viewports:{}};for(const [name,viewport] of Object.entries(page.viewports||{})){const auditedViewport=audited&&audited.viewports&&audited.viewports[name];if(!auditedViewport||!auditedViewport.passed||Number(auditedViewport.width)!==Number(viewport.width)||Number(auditedViewport.height)!==Number(viewport.height))errors.push(`missing passing ${name} layout audit for ${page.path}`);visualEvidence.pages[page.pageKey].viewports[name]={...evidence(viewport.screenshot,`${page.pageKey} ${name}`,viewport),claim:viewport.claim||"fidelity"}}}
        const designContract=readJson("design-system/design-contract.json",{}),sourceSha=designContract.sourceSha256||(designContract.meta&&designContract.meta.sourceSha256)||"",runtimeSha=designContract.designRuntimeSha256||(designContract.meta&&designContract.meta.designRuntimeSha256)||"";
        for(const relative of ["shared/css/tokens.css","shared/css/product-shell.css","shared/css/product-components.css","shared/css/product-patterns.css","shared/css/prototype-meta.css","shared/js/product-icons.js","shared/js/product-shell.js","design-system/shared-registry.json"]){const file=inside(relative,`authored design-system file ${relative}`);if(file)files[relative]=sha(file.absolute)}
        if(errors.length){for(const error of errors)console.error(`ERROR ${error}`);process.exit(1)}
        const status={version:3,mode:config.authoringMode||"llm",status:"ready",designSourceSha256:sourceSha,designRuntimeSha256:runtimeSha,authoredAt:new Date().toISOString(),manifest:{path:manifestFile.relative,sha256:sha(manifestFile.absolute)},layoutReport:{path:reportFile.relative,sha256:sha(reportFile.absolute)},files,visualEvidence};fs.writeFileSync(path.join(root,"design-system/authoring-status.json"),JSON.stringify(status,null,2)+"\n");console.log(`Design-system finalized with ${manifest.pages.length} layout-audited representative page(s).`);
        """
    )


def manage_shared_registry_script() -> str:
    return clean_block(
        r"""
        #!/usr/bin/env node
        const fs = require("fs");
        const path = require("path");

        const root = path.resolve(__dirname, "..");
        const file = path.join(root, "design-system", "shared-registry.json");
        const args = process.argv.slice(2);
        const command = args.shift();
        const options = {};
        for (let i = 0; i < args.length; i += 1) {
          const value = args[i];
          if (value.startsWith("--")) { options[value.slice(2)] = args[i + 1]; i += 1; }
        }
        const registry = JSON.parse(fs.readFileSync(file, "utf8"));
        const sections = new Set(["components", "patterns", "interactions"]);

        if (command === "list") {
          for (const section of sections) {
            for (const [name, entry] of Object.entries(registry[section] || {})) {
              console.log(`${section}\t${name}\t${(entry.usedBy || []).join(",")}`);
            }
          }
          process.exit(0);
        }

        if (command !== "upsert" || !sections.has(options.section) || !options.name) {
          console.error("Usage: node scripts/manage-shared-registry.cjs list");
          console.error("   or: node scripts/manage-shared-registry.cjs upsert --section components|patterns|interactions --name NAME --description TEXT --files a.css,b.js --selectors .a,[data-x] --used-by feature-a,feature-b");
          process.exit(1);
        }

        const split = (value) => String(value || "").split(",").map((item) => item.trim()).filter(Boolean);
        const current = registry[options.section][options.name] || {};
        registry[options.section][options.name] = {
          description: options.description || current.description || "",
          files: split(options.files).length ? split(options.files) : (current.files || []),
          selectors: split(options.selectors).length ? split(options.selectors) : (current.selectors || []),
          usedBy: [...new Set([...(current.usedBy || []), ...split(options["used-by"])])],
          originGapId: options["origin-gap-id"] || current.originGapId || "",
          status: options.status || current.status || "stable",
          updatedAt: new Date().toISOString(),
        };
        fs.writeFileSync(file, JSON.stringify(registry, null, 2) + "\n");
        console.log(`Updated ${options.section}.${options.name}`);
        """
    )


def record_fidelity_review_script() -> str:
    return clean_block(
        r"""
        #!/usr/bin/env node
        const fs = require("fs");
        const path = require("path");
        const crypto = require("crypto");

        const root = path.resolve(__dirname, "..");
        const args = process.argv.slice(2);
        const options = {};
        const pages = [];

        for (let index = 0; index < args.length; index += 1) {
          const value = args[index];
          if (value.startsWith("--")) {
            const name = value.slice(2);
            if (["viewport", "baseline-viewport", "reference-viewport"].includes(name)) {
              options[name] = options[name] || [];
              options[name].push(args[index + 1]);
            } else options[name] = args[index + 1];
            index += 1;
          } else {
            pages.push(value);
          }
        }

        if (pages.length === 0) {
          console.error("Usage: node scripts/record-fidelity-review.cjs <page> --viewport id,image,width,height[,dpr] [--baseline-viewport id,image --diff-report ...] [--reference-viewport id,image --comparison-report ...]");
          process.exit(1);
        }

        function readJson(relative, fallback) {
          const file = path.join(root, relative);
          if (!fs.existsSync(file)) return fallback;
          return JSON.parse(fs.readFileSync(file, "utf8"));
        }

        function sha256File(file) {
          return crypto.createHash("sha256").update(fs.readFileSync(file)).digest("hex");
        }

        function walk(dir) {
          if (!fs.existsSync(dir)) return [];
          return fs.readdirSync(dir, { withFileTypes: true }).flatMap((entry) => {
            const target = path.join(dir, entry.name);
            return entry.isDirectory() ? walk(target) : [target];
          });
        }

        function runtimeFiles(pageFile, sharedRefs = []) {
          const config = readJson("design-system/prototype-config.json", { framework: "html" });
          let files = [...(config.sharedCss || []), ...(config.sharedJs || [])];
          if (sharedRefs.length) {
            const registry = readJson("design-system/shared-registry.json", {});
            files = ["shared/css/tokens.css", "shared/css/product-shell.css", "shared/css/prototype-meta.css", "shared/js/product-icons.js", "shared/js/product-shell.js"];
            for (const ref of sharedRefs) {
              const [section, name] = String(ref).split(".", 2);
              const entry = registry[section] && registry[section][name];
              if (entry && Array.isArray(entry.files)) files.push(...entry.files);
            }
          }
          if (config.framework === "react") files.push("src/App.jsx");
          if (config.framework === "vue") files.push("src/App.vue");
          let current = path.dirname(pageFile);
          while (current.startsWith(root) && current !== root) {
            const assets = path.join(current, "assets");
            if (fs.existsSync(assets)) {
              for (const file of walk(assets)) files.push(path.relative(root, file).replaceAll(path.sep, "/"));
              break;
            }
            current = path.dirname(current);
          }
          return files.filter((relative) => fs.existsSync(path.join(root, relative)));
        }

        function hashRuntime(pageFile, sharedRefs = []) {
          const hash = crypto.createHash("sha256");
          for (const relative of [...new Set(runtimeFiles(pageFile, sharedRefs))].sort()) {
            hash.update(relative);
            hash.update(fs.readFileSync(path.join(root, relative)));
          }
          return hash.digest("hex");
        }

        function evidence(value, label, kind = "image") {
          if (!value) {
            console.error(`Missing --${label} evidence`);
            process.exit(1);
          }
          const absolute = path.resolve(root, value);
          const relative = path.relative(root, absolute).replaceAll(path.sep, "/");
          if (relative.startsWith("../") || path.isAbsolute(relative) || !fs.existsSync(absolute) || !fs.statSync(absolute).isFile()) {
            console.error(`Evidence must be an existing project file: ${value}`);
            process.exit(1);
          }
          let metadata = {};
          if (kind === "image") {
            const bytes = fs.readFileSync(absolute);
            const header = bytes.subarray(0, 12);
            const png = header.length >= 8 && header.subarray(0, 8).equals(Buffer.from([137,80,78,71,13,10,26,10]));
            const jpeg = header.length >= 3 && header[0] === 0xff && header[1] === 0xd8 && header[2] === 0xff;
            const webp = header.length >= 12 && header.subarray(0, 4).toString() === "RIFF" && header.subarray(8, 12).toString() === "WEBP";
            if (!png && !jpeg && !webp) {
              console.error(`Evidence must be PNG, JPEG, or WebP: ${value}`);
              process.exit(1);
            }
            if (png) {
              const width = bytes.readUInt32BE(16);
              const height = bytes.readUInt32BE(20);
              metadata = { width, height };
            }
          } else {
            try {
              const report = JSON.parse(fs.readFileSync(absolute, "utf8"));
              if (report.unchangedRegionsMatch !== true) throw new Error("unchangedRegionsMatch must be true");
              if (!Array.isArray(report.reviewedViewports) || report.reviewedViewports.length === 0) throw new Error("reviewedViewports must contain at least one viewport");
              if (report.generator !== "compare-prototype-screenshots.py") throw new Error("report must be generated by compare-prototype-screenshots.py");
              for (const viewport of report.reviewedViewports) {
                const metrics = (report.viewports && report.viewports[viewport]) || report[viewport] || {};
                if (!(Number(metrics.comparedPixels) > 0) || !Number.isFinite(Number(metrics.diffRatio))) {
                  throw new Error(`${viewport} metrics must include comparedPixels and diffRatio`);
                }
                if (Number(metrics.diffRatio) > Number(report.maxDiffRatio)) throw new Error(`${viewport} diffRatio exceeds maxDiffRatio`);
              }
            } catch (error) {
              console.error(`Invalid visual diff report ${value}: ${error.message}`);
              process.exit(1);
            }
          }
          return { path: relative, sha256: sha256File(absolute), ...metadata };
        }

        function incrementalContractFor(pageFile) {
          let current = path.dirname(pageFile);
          while (current.startsWith(root) && current !== root) {
            const contractFile = path.join(current, "incremental-contract.json");
            if (fs.existsSync(contractFile)) return contractFile;
            current = path.dirname(current);
          }
          return null;
        }

        function reconstructionContractFor(pageFile) {
          let current = path.dirname(pageFile);
          while (current.startsWith(root) && current !== root) {
            const contractFile = path.join(current, "reconstruction-contract.json");
            if (fs.existsSync(contractFile)) return contractFile;
            current = path.dirname(current);
          }
          return null;
        }

        function dataAttr(text, name) {
          const match = text.match(new RegExp(`data-${name}=["']([^"']*)["']`, "i"));
          return match ? match[1] : "";
        }

        function splitOption(value) {
          return String(value || "").split(",").map((item) => item.trim()).filter(Boolean);
        }

        const contract = readJson("design-system/design-contract.json", {});
        const sourceSha = contract.sourceSha256 || (contract.meta && contract.meta.sourceSha256) || "";
        const runtimeSha = contract.designRuntimeSha256 || (contract.meta && contract.meta.designRuntimeSha256) || "";
        const reviewFile = path.join(root, "design-system", "fidelity-reviews.json");
        const data = readJson("design-system/fidelity-reviews.json", {
          version: 1,
          designSourceSha256: sourceSha,
          designRuntimeSha256: runtimeSha,
          reviews: {},
        });
        data.version = 1;
        data.designSourceSha256 = sourceSha;
        data.designRuntimeSha256 = runtimeSha;
        data.reviews = data.reviews || {};

        const viewportSpecs = {};
        for (const spec of options.viewport || []) {
          const [id, image, width, height, dpr] = String(spec || "").split(",");
          if (!id || !image || !(Number(width) > 0) || !(Number(height) > 0)) {
            console.error("--viewport format is id,image,width,height[,dpr]"); process.exit(1);
          }
          viewportSpecs[id] = { image, width: Number(width), height: Number(height), dpr: Number(dpr || 1) };
        }
        if (!Object.keys(viewportSpecs).length && (options.desktop || options.mobile)) {
          console.warn("WARN --desktop/--mobile are compatibility arguments; prefer repeatable --viewport id,image,width,height[,dpr]");
          if (options.desktop) viewportSpecs.desktop = { image: options.desktop, width: Number(options["desktop-width"] || 1440), height: Number(options["desktop-height"] || 900), dpr: Number(options["desktop-dpr"] || 1) };
          if (options.mobile) viewportSpecs.mobile = { image: options.mobile, width: Number(options["mobile-width"] || 390), height: Number(options["mobile-height"] || 844), dpr: Number(options["mobile-dpr"] || 1) };
        }
        const viewports = Object.keys(viewportSpecs);
        if (!viewports.length) { console.error("At least one --viewport id,image,width,height[,dpr] is required"); process.exit(1); }
        const evidenceMap = (specs) => Object.fromEntries((specs || []).map((spec) => { const [id,image] = String(spec || "").split(",",2); return [id,evidence(image,`${id}`)]; }));
        for (const page of pages) {
          const file = path.resolve(root, page);
          const relative = path.relative(root, file).replaceAll(path.sep, "/");
          if (relative.startsWith("../") || path.isAbsolute(relative) || !fs.existsSync(file) || !fs.statSync(file).isFile()) {
            console.error(`Invalid page or component path: ${page}`);
            process.exit(1);
          }
          if (!/\.(html|jsx|vue)$/.test(relative)) {
            console.error(`Fidelity review only supports HTML, JSX, or Vue page files: ${relative}`);
            process.exit(1);
          }
          const incrementalContract = incrementalContractFor(file);
          const reconstructionContract = reconstructionContractFor(file);
          const pageText = fs.readFileSync(file, "utf8");
          const designDomains = splitOption(options["design-domains"] || dataAttr(pageText, "design-domains"));
          const safeDomains = designDomains.length ? [...new Set(["tokens", "shell", ...designDomains])] : ["tokens", "shell", "components", "patterns", "rules"];
          const sharedRefs = splitOption(options["shared-refs"] || dataAttr(pageText, "shared-refs"));
          const selectedHashes = {};
          for (const domain of safeDomains) selectedHashes[domain] = (contract.runtimeHashes || {})[domain] || runtimeSha;
          const profileSha = crypto.createHash("sha256").update(JSON.stringify(selectedHashes)).digest("hex");
          const visualEvidence = { viewports: Object.fromEntries(Object.entries(viewportSpecs).map(([id,item]) => {const captured=evidence(item.image,id);if(captured.width&&captured.height&&(captured.width!==item.width||captured.height!==item.height)){console.error(`${id} evidence ${captured.width}x${captured.height} does not match ${item.width}x${item.height}`);process.exit(1)}return [id,{...captured,width:item.width,height:item.height,dpr:item.dpr}]})) };
          if (visualEvidence.viewports.desktop) visualEvidence.desktop = visualEvidence.viewports.desktop;
          if (visualEvidence.viewports.mobile) visualEvidence.mobile = visualEvidence.viewports.mobile;
          if (incrementalContract) {
            visualEvidence.baselineViewports = evidenceMap(options["baseline-viewport"]);
            if (!Object.keys(visualEvidence.baselineViewports).length && (options["baseline-desktop"] || options["baseline-mobile"])) {
              if (options["baseline-desktop"]) visualEvidence.baselineViewports.desktop = evidence(options["baseline-desktop"], "baseline-desktop");
              if (options["baseline-mobile"]) visualEvidence.baselineViewports.mobile = evidence(options["baseline-mobile"], "baseline-mobile");
            }
            if (visualEvidence.baselineViewports.desktop) visualEvidence.baselineDesktop = visualEvidence.baselineViewports.desktop;
            if (visualEvidence.baselineViewports.mobile) visualEvidence.baselineMobile = visualEvidence.baselineViewports.mobile;
            visualEvidence.diffReport = evidence(options["diff-report"], "diff-report", "json");
          }
          if (reconstructionContract) {
            visualEvidence.referenceViewports = evidenceMap(options["reference-viewport"]);
            if (!Object.keys(visualEvidence.referenceViewports).length && (options["reference-desktop"] || options["reference-mobile"])) {
              if (options["reference-desktop"]) visualEvidence.referenceViewports.desktop = evidence(options["reference-desktop"], "reference-desktop");
              if (options["reference-mobile"]) visualEvidence.referenceViewports.mobile = evidence(options["reference-mobile"], "reference-mobile");
            }
            if (visualEvidence.referenceViewports.desktop) visualEvidence.referenceDesktop = visualEvidence.referenceViewports.desktop;
            if (visualEvidence.referenceViewports.mobile) visualEvidence.referenceMobile = visualEvidence.referenceViewports.mobile;
            visualEvidence.comparisonReport = evidence(options["comparison-report"], "comparison-report", "json");
            const report = JSON.parse(fs.readFileSync(path.join(root, visualEvidence.comparisonReport.path), "utf8"));
            if (report.mode !== "reconstruction") {
              console.error("Reconstruction comparison report must use --mode reconstruction");
              process.exit(1);
            }
          }
          data.reviews[relative] = {
            status: "approved",
            path: relative,
            pageKey: dataAttr(pageText, "page-key"),
            designSourceSha256: sourceSha,
            designRuntimeSha256: runtimeSha,
            designDomains: safeDomains,
            sharedRefs,
            designProfileSha256: profileSha,
            fileSha256: sha256File(file),
            runtimeSha256: hashRuntime(file, sharedRefs),
            viewports,
            evidence: visualEvidence,
            browser: {
              name: String(options.browser || "unspecified"),
              viewports: Object.fromEntries(Object.entries(viewportSpecs).map(([id,item]) => [id,{width:item.width,height:item.height,dpr:item.dpr}])),
              ...(viewportSpecs.desktop ? {desktop:{width:viewportSpecs.desktop.width,height:viewportSpecs.desktop.height,dpr:viewportSpecs.desktop.dpr}} : {}),
              ...(viewportSpecs.mobile ? {mobile:{width:viewportSpecs.mobile.width,height:viewportSpecs.mobile.height,dpr:viewportSpecs.mobile.dpr}} : {}),
            },
            reviewer: String(options.reviewer || "agent"),
            note: String(options.note || ""),
            reviewedAt: new Date().toISOString(),
          };
          console.log(`Recorded fidelity review for ${relative}`);
        }

        fs.writeFileSync(reviewFile, JSON.stringify(data, null, 2) + "\n");
        """
    )


def add_fidelity_role_rules(check_rules: dict[str, Any], design: dict[str, Any]) -> None:
    fidelity = check_rules.setdefault("productFidelity", {})
    metadata = fidelity.setdefault("requiredPageMetadata", [])
    if "data-design-contract-version" not in metadata:
        metadata.insert(1, "data-design-contract-version")
    if is_layout_v2(design):
        model = normalize_layout_model(design)
        fidelity["layoutProfiles"] = {
            str(profile.get("id")): {
                "rootRegion": profile.get("rootRegion"),
                "regions": {str(region.get("id")): region.get("selector") for region in profile.get("regions", [])},
            }
            for profile in model.get("profiles", [])
        }
        fidelity["roleRequirements"] = {"projectShell": {}, "listPage": {}}
        return
    classes = shell_classes(design)
    fidelity["roleRequirements"] = {
        "projectShell": {
            "shell-root": [classes["root_base"]],
            "header": [classes["header"]],
            "layout": [classes["layout"]],
            "sidebar": [classes["sidebar"]],
            "main": [classes["main"]],
            "tabs": [classes["tabs"]],
            "view": [classes["view"]],
        },
        "listPage": {
            "panel": [classes["panel"]],
            "section-heading": [classes["section_header"]],
            "filter": [classes["filter"]],
        },
    }


def render_package_json(project_name: str, framework: str) -> str:
    package_name = kebab(project_name)
    if framework == "react":
        dependencies = {"react": "^18.2.0", "react-dom": "^18.2.0"}
        dev_dependencies = {"@vitejs/plugin-react": "^4.2.0", "vite": "^5.0.0"}
    else:
        dependencies = {"vue": "^3.4.0"}
        dev_dependencies = {"@vitejs/plugin-vue": "^5.0.0", "vite": "^5.0.0"}
    package = {
        "name": package_name,
        "version": "0.1.0",
        "private": True,
        "type": "module",
        "scripts": {
            "dev": "vite",
            "build": "vite build",
            "preview": "vite preview",
            "check": "node scripts/check-prototype-compliance.cjs",
            "check:release": "node scripts/check-prototype-compliance.cjs --release",
        },
        "dependencies": dependencies,
        "devDependencies": dev_dependencies,
    }
    return json.dumps(package, ensure_ascii=False, indent=2) + "\n"


def render_vite_config(framework: str) -> str:
    plugin = "react from '@vitejs/plugin-react'" if framework == "react" else "vue from '@vitejs/plugin-vue'"
    plugin_name = "react" if framework == "react" else "vue"
    return clean_block(
        f"""
        import {{ defineConfig }} from 'vite';
        import {plugin};

        export default defineConfig({{
          plugins: [{plugin_name}()],
        }});
        """
    )


def render_framework_index_html(project_name: str, framework: str, language: str) -> str:
    entry = "/src/main.jsx" if framework == "react" else "/src/main.js"
    return clean_block(
        f"""
        <!doctype html>
        <html lang="{html.escape(language)}">
        <head>
          <meta charset="utf-8">
          <meta name="viewport" content="width=device-width, initial-scale=1">
          <title>{html.escape(project_name)}原型</title>
        </head>
        <body>
          <div id="root"></div>
          <script type="module" src="{entry}"></script>
        </body>
        </html>
        """
    )


def render_framework_registry() -> str:
    return clean_block(
        """
        /* Generated prototype registry. Use scripts/new-feature.cjs to add entries. */
        // IMPORTS_START
        // IMPORTS_END

        export const features = [
          // FEATURES_START
          // FEATURES_END
        ];
        """
    )


def render_framework_styles() -> str:
    return clean_block(
        """
        #root {
          min-height: 100vh;
        }
        """
    )


def render_react_main() -> str:
    return clean_block(
        """
        import React from 'react';
        import { createRoot } from 'react-dom/client';
        import '../shared/css/tokens.css';
        import '../shared/css/product-shell.css';
        import '../shared/css/product-components.css';
        import '../shared/css/product-patterns.css';
        import '../shared/css/prototype-meta.css';
        import '../shared/js/product-icons.js';
        import '../shared/js/product-shell.js';
        import './styles.css';
        import { App } from './App.jsx';
        import { features } from './prototype-registry.js';

        createRoot(document.getElementById('root')).render(
          <React.StrictMode>
            <App features={features} />
          </React.StrictMode>
        );
        """
    )


def render_react_app(project_name: str, design: dict[str, Any]) -> str:
    if is_layout_v2(design):
        pages = [item for item in normalize_layout_model(design).get("pageTemplates", []) if item.get("representative") is True]
        links = json.dumps([{"id": item.get("id"), "name": item.get("name"), "path": f"/design-system/preview/{kebab(str(item.get('id')))}.html"} for item in pages], ensure_ascii=False)
        return clean_block(
            f"""
            import React, {{ useState }} from 'react';
            const previews = {links};
            export function App() {{
              const [active, setActive] = useState(previews[0] || null);
              return <main className="framework-preview-launcher" data-developer-control="preview-launcher">
                <h1>{html.escape(project_name)} previews</h1>
                <nav>{{previews.map((item) => <button type="button" key={{item.id}} onClick={{() => setActive(item)}}>{{item.name}}</button>)}}</nav>
                {{active ? <iframe title={{active.name}} src={{active.path}} style={{{{width:'100%',height:'80vh',border:0}}}} /> : null}}
              </main>;
            }}
            """
        )
    escaped_project = json.dumps(project_name, ensure_ascii=False)
    classes = shell_classes(design)
    c = {key: json.dumps(value, ensure_ascii=False) for key, value in classes.items()}
    return clean_block(
        f"""
        import React, {{ useMemo, useState }} from 'react';

        const PRODUCT_NAME = {escaped_project};

        function parseRoute() {{
          const hash = window.location.hash.replace(/^#\\/?/, '');
          const [kind, featureSlug, pagePath] = hash.split('/');
          if (kind === 'feature' && featureSlug) {{
            return {{ featureSlug, pagePath: pagePath || '' }};
          }}
          return {{ featureSlug: '', pagePath: '' }};
        }}

        function useHashRoute() {{
          const [route, setRoute] = useState(parseRoute);
          React.useEffect(() => {{
            const onHashChange = () => setRoute(parseRoute());
            window.addEventListener('hashchange', onHashChange);
            return () => window.removeEventListener('hashchange', onHashChange);
          }}, []);
          return route;
        }}

        function Library({{ features }}) {{
          return (
            <main className="proto-library">
              <header className="proto-library-header">
                <p className="proto-kicker">原型库</p>
                <h1>{{PRODUCT_NAME}}原型库</h1>
                <p>请选择一个功能迭代查看 React 原型页面。</p>
              </header>
              <section className="proto-library-section" aria-labelledby="feature-list-title">
                <div className="proto-section-title">
                  <h2 id="feature-list-title">功能迭代</h2>
                  <span>React 入口</span>
                </div>
                <div className="proto-feature-list">
                  {{features.map((feature) => (
                    <a className="proto-feature-card" href={{`#/feature/${{feature.slug}}`}} key={{feature.slug}}>
                      <strong>{{feature.name}}</strong>
                      <small>更新时间：{{feature.updatedAt}}｜所属迭代：{{feature.iterationName}}｜{{feature.summary}}</small>
                    </a>
                  ))}}
                </div>
              </section>
            </main>
          );
        }}

        function FeatureShell({{ feature, page }}) {{
          const PageComponent = page?.component;
          const activePageTitle = page?.title || feature.name;
          return (
            <div className={c["root"]} data-feature={{feature.slug}}>
              <header className={c["header"]}>
                <div className={c["logo"]}>{{PRODUCT_NAME}}</div>
                <button className={c["toggle"]} type="button" aria-label="展开侧栏" title="展开侧栏"><span className="product-icon" data-icon="menu"></span></button>
                <nav className={c["top_menu"]} aria-label="一级导航">
                  {{feature.pages.map((item) => (
                    <a className={{item === page ? {c["top_menu_item"]} + ' is-active' : {c["top_menu_item"]}}} href={{`#/feature/${{feature.slug}}/${{item.path}}`}} key={{item.path}}>{{item.title}}</a>
                  ))}}
                </nav>
                <div className={c["header_right"]}>
                  <span className="product-icon" data-icon="help" aria-label="帮助中心" title="帮助中心"></span>
                  <span className="product-icon" data-icon="bell" aria-label="通知" title="通知"></span>
                  <span className="user-entry"><span className="product-icon" data-icon="user"></span>当前用户<span className="product-icon" data-icon="down"></span></span>
                </div>
              </header>
              <div className={c["layout"]}>
                <aside className={c["sidebar"]} aria-label="功能导航">
                  <nav className={c["sidebar_nav"]}>
                    {{feature.pages.map((item) => (
                      <a className={{item === page ? {c["sidebar_item"]} + ' is-active' : {c["sidebar_item"]}}} href={{`#/feature/${{feature.slug}}/${{item.path}}`}} key={{item.path}}><span className="product-icon" data-icon="file"></span>{{item.title}}</a>
                    ))}}
                  </nav>
                </aside>
                <main className={c["main"]}>
                  <div className={c["tabs"]} aria-label="页面标签">
                    <a className={c["tab_item"]} href="#">原型库</a>
                    <a className={c["tab_item"]} href={{`#/feature/${{feature.slug}}`}}>{{feature.name}}</a>
                    <span className={{ {c["tab_item"]} + ' is-active' }}>{{activePageTitle}}</span>
                  </div>
                  <div className={c["view"]}>
                  {{PageComponent ? <PageComponent /> : (
                    <section className={c["panel"]}>
                      <header className={c["section_header"]}>
                        <div>
                          <p className="proto-kicker">功能原型</p>
                          <h1 className={c["section_title"]}>{{feature.name}}</h1>
                          <p className="proto-page-summary">{{feature.summary}}</p>
                        </div>
                      </header>
                      <div className="proto-page-list">
                        {{feature.pages.map((item) => (
                          <a className="proto-page-card" href={{`#/feature/${{feature.slug}}/${{item.path}}`}} key={{item.path}}>
                            <strong>{{item.title}}</strong>
                            <span>{{item.generationMode === 'placeholder' ? '尚未设计｜查看缺失材料' : '查看该页面的 React 原型。'}}</span>
                          </a>
                        ))}}
                      </div>
                    </section>
                  )}}
                  </div>
                </main>
              </div>
            </div>
          );
        }}

        export function App({{ features }}) {{
          const route = useHashRoute();
          const feature = useMemo(() => features.find((item) => item.slug === route.featureSlug), [features, route.featureSlug]);
          const page = feature?.pages.find((item) => item.path === route.pagePath) || null;
          if (!feature) return <Library features={{features}} />;
          return <FeatureShell feature={{feature}} page={{page}} />;
        }}
        """
    )


def render_vue_main() -> str:
    return clean_block(
        """
        import { createApp } from 'vue';
        import '../shared/css/tokens.css';
        import '../shared/css/product-shell.css';
        import '../shared/css/product-components.css';
        import '../shared/css/product-patterns.css';
        import '../shared/css/prototype-meta.css';
        import '../shared/js/product-icons.js';
        import '../shared/js/product-shell.js';
        import './styles.css';
        import App from './App.vue';
        import { features } from './prototype-registry.js';

        createApp(App, { features }).mount('#root');
        """
    )


def render_vue_app(project_name: str, design: dict[str, Any]) -> str:
    if is_layout_v2(design):
        pages = [item for item in normalize_layout_model(design).get("pageTemplates", []) if item.get("representative") is True]
        links = json.dumps([{"id": item.get("id"), "name": item.get("name"), "path": f"/design-system/preview/{kebab(str(item.get('id')))}.html"} for item in pages], ensure_ascii=False)
        return clean_block(
            f"""
            <template>
              <main class="framework-preview-launcher" data-developer-control="preview-launcher">
                <h1>{html.escape(project_name)} previews</h1>
                <nav><button v-for="item in previews" :key="item.id" type="button" @click="active = item">{{{{ item.name }}}}</button></nav>
                <iframe v-if="active" :title="active.name" :src="active.path" style="width:100%;height:80vh;border:0"></iframe>
              </main>
            </template>
            <script setup>
            import {{ ref }} from 'vue';
            const previews = {links};
            const active = ref(previews[0] || null);
            </script>
            """
        )
    escaped_project = html.escape(project_name)
    classes = {key: html.escape(value) for key, value in shell_classes(design).items()}
    return clean_block(
        f"""
        <template>
          <main v-if="!activeFeature" class="proto-library">
            <header class="proto-library-header">
              <p class="proto-kicker">原型库</p>
              <h1>{escaped_project}原型库</h1>
              <p>请选择一个功能迭代查看 Vue 原型页面。</p>
            </header>
            <section class="proto-library-section" aria-labelledby="feature-list-title">
              <div class="proto-section-title">
                <h2 id="feature-list-title">功能迭代</h2>
                <span>Vue 入口</span>
              </div>
              <div class="proto-feature-list">
                <a v-for="feature in features" :key="feature.slug" class="proto-feature-card" :href="`#/feature/${{feature.slug}}`">
                  <strong>{{{{ feature.name }}}}</strong>
                  <small>更新时间：{{{{ feature.updatedAt }}}}｜所属迭代：{{{{ feature.iterationName }}}}｜{{{{ feature.summary }}}}</small>
                </a>
              </div>
            </section>
          </main>

          <div v-else class="{classes["root"]}" :data-feature="activeFeature.slug">
            <header class="{classes["header"]}">
              <div class="{classes["logo"]}">{escaped_project}</div>
              <button class="{classes["toggle"]}" type="button" aria-label="展开侧栏" title="展开侧栏"><span class="product-icon" data-icon="menu"></span></button>
              <nav class="{classes["top_menu"]}" aria-label="一级导航">
                <a v-for="page in activeFeature.pages" :key="page.path" :class="page === activePage ? '{classes["top_menu_item"]} is-active' : '{classes["top_menu_item"]}'" :href="`#/feature/${{activeFeature.slug}}/${{page.path}}`">{{{{ page.title }}}}</a>
              </nav>
              <div class="{classes["header_right"]}">
                <span class="product-icon" data-icon="help" aria-label="帮助中心" title="帮助中心"></span>
                <span class="product-icon" data-icon="bell" aria-label="通知" title="通知"></span>
                <span class="user-entry"><span class="product-icon" data-icon="user"></span>当前用户<span class="product-icon" data-icon="down"></span></span>
              </div>
            </header>
            <div class="{classes["layout"]}">
              <aside class="{classes["sidebar"]}" aria-label="功能导航">
                <nav class="{classes["sidebar_nav"]}">
                  <a v-for="page in activeFeature.pages" :key="page.path" :class="page === activePage ? '{classes["sidebar_item"]} is-active' : '{classes["sidebar_item"]}'" :href="`#/feature/${{activeFeature.slug}}/${{page.path}}`"><span class="product-icon" data-icon="file"></span>{{{{ page.title }}}}</a>
                </nav>
              </aside>
              <main class="{classes["main"]}">
                <div class="{classes["tabs"]}" aria-label="页面标签">
                  <a class="{classes["tab_item"]}" href="#">原型库</a>
                  <a class="{classes["tab_item"]}" :href="`#/feature/${{activeFeature.slug}}`">{{{{ activeFeature.name }}}}</a>
                  <span class="{classes["tab_item"]} is-active">{{{{ activePage ? activePage.title : activeFeature.name }}}}</span>
                </div>
                <div class="{classes["view"]}">
                <component v-if="activePage" :is="activePage.component" />
                <section v-else class="{classes["panel"]}">
                  <header class="{classes["section_header"]}">
                    <div>
                      <p class="proto-kicker">功能原型</p>
                      <h1 class="{classes["section_title"]}">{{{{ activeFeature.name }}}}</h1>
                      <p class="proto-page-summary">{{{{ activeFeature.summary }}}}</p>
                    </div>
                  </header>
                  <div class="proto-page-list">
                    <a v-for="page in activeFeature.pages" :key="page.path" class="proto-page-card" :href="`#/feature/${{activeFeature.slug}}/${{page.path}}`">
                      <strong>{{{{ page.title }}}}</strong>
                      <span>{{{{ page.generationMode === 'placeholder' ? '尚未设计｜查看缺失材料' : '查看该页面的 Vue 原型。' }}}}</span>
                    </a>
                  </div>
                </section>
                </div>
              </main>
            </div>
          </div>
        </template>

        <script setup>
        import {{ computed, onBeforeUnmount, onMounted, ref }} from 'vue';

        const props = defineProps({{
          features: {{
            type: Array,
            default: () => [],
          }},
        }});

        function parseRoute() {{
          const hash = window.location.hash.replace(/^#\\/?/, '');
          const [kind, featureSlug, pagePath] = hash.split('/');
          if (kind === 'feature' && featureSlug) {{
            return {{ featureSlug, pagePath: pagePath || '' }};
          }}
          return {{ featureSlug: '', pagePath: '' }};
        }}

        const route = ref(parseRoute());
        const onHashChange = () => {{
          route.value = parseRoute();
        }};

        onMounted(() => window.addEventListener('hashchange', onHashChange));
        onBeforeUnmount(() => window.removeEventListener('hashchange', onHashChange));

        const activeFeature = computed(() => props.features.find((feature) => feature.slug === route.value.featureSlug));
        const activePage = computed(() => activeFeature.value?.pages.find((page) => page.path === route.value.pagePath) || null);
        </script>
        """
    )


def new_feature_universal_script(source_hash: str, runtime_hash: str) -> str:
    return clean_block(
        f"""
        #!/usr/bin/env node
        const fs=require("fs"),path=require("path");const root=path.resolve(__dirname,"..");
        const args=process.argv.slice(2),options={{}},positional=[];for(let i=0;i<args.length;i+=1){{if(args[i].startsWith("--")){{options[args[i].slice(2)]=args[i+1];i+=1}}else positional.push(args[i])}}
        const feature=options.feature||positional[0],pageName=options.page||positional[1],profileId=options["layout-profile"],templateId=options.template;
        const fail=(message)=>{{console.error(`ERROR ${{message}}`);process.exit(1)}};
        if(!feature||!pageName||!profileId||!templateId)fail("usage: new-feature.cjs --feature NAME --page NAME --layout-profile PROFILE --template TEMPLATE");
        const model=JSON.parse(fs.readFileSync(path.join(root,"design-system/layout-model.json"),"utf8")),profile=(model.profiles||[]).find((item)=>item.id===profileId),template=(model.pageTemplates||[]).find((item)=>item.id===templateId);
        if(!profile)fail(`unknown layout profile ${{profileId}}`);if(!template||template.layoutProfile!==profileId)fail(`template ${{templateId}} is not bound to profile ${{profileId}}`);
        const slug=String(feature).normalize("NFKD").replace(/[^A-Za-z0-9]+/g,"-").replace(/^-|-$/g,"").toLowerCase()||"feature";
        const existing=fs.readdirSync(root).map((name)=>/^(\d+)-/.exec(name)).filter(Boolean).map((match)=>Number(match[1]));const number=String((existing.length?Math.max(...existing):0)+1).padStart(2,"0"),dir=path.join(root,`${{number}}-${{slug}}`);fs.mkdirSync(dir,{{recursive:true}});
        const rootRegion=(profile.regions||[]).find((item)=>item.id===profile.rootRegion),selector=String(rootRegion.selector||""),className=selector.startsWith(".")?selector.split(".").filter(Boolean).join(" "):"",id=selector.startsWith("#")?selector.slice(1):"";
        const attributes=[className?`class="${{className}}"`:"",id?`id="${{id}}"`:"",`data-layout-region="${{profile.rootRegion}}"`,`data-layout-profile="${{profileId}}"`,`data-page-template="${{templateId}}"`,`data-design-source-sha="{source_hash}"`,`data-design-runtime-sha="{runtime_hash}"`,`data-authoring-pending="true"`].filter(Boolean).join(" ");
        const page=`<!doctype html>\n<html><head><meta charset="utf-8"><meta name="viewport" content="width=device-width,initial-scale=1"><link rel="stylesheet" href="../shared/css/tokens.css"><link rel="stylesheet" href="../shared/css/product-shell.css"></head><body><div ${{attributes}} data-authoring-slot="pending"></div></body></html>\n`;
        const pagePath=path.join(dir,`${{slug}}.html`);if(!fs.existsSync(pagePath))fs.writeFileSync(pagePath,page);
        fs.writeFileSync(path.join(dir,"feature-manifest.json"),JSON.stringify({{version:2,feature,layoutProfile:profileId,templateId,pages:[{{name:pageName,path:path.basename(pagePath),status:"pending-authoring"}}]}},null,2)+"\n");
        console.log(`Created ${{path.relative(root,dir)}}. Complete the confirmed authoring slot before review.`);
        """
    )


def new_feature_script(design: dict[str, Any], source_hash: str, runtime_hash: str) -> str:
    if is_layout_v2(design):
        return new_feature_universal_script(source_hash, runtime_hash)
    script = clean_block(
        r"""
        #!/usr/bin/env node
        const fs = require("fs");
        const path = require("path");
        const childProcess = require("child_process");
        const crypto = require("crypto");

        const root = path.resolve(__dirname, "..");
        const shellClasses = __SHELL_CLASSES_JSON__;
        const designSourceSha = "__DESIGN_SOURCE_SHA__";
        const designRuntimeSha = "__DESIGN_RUNTIME_SHA__";
        const designContractVersion = "__DESIGN_CONTRACT_VERSION__";
        const args = process.argv.slice(2);
        const options = {};
        const positional = [];

        for (let i = 0; i < args.length; i += 1) {
          const arg = args[i];
          if (arg.startsWith("--")) {
            const key = arg.slice(2);
            if (key === "force") {
              options.force = true;
            } else {
              options[key] = args[i + 1];
              i += 1;
            }
          } else {
            positional.push(arg);
          }
        }

        function readFeatureManifest() {
          if (!options.manifest) return {};
          const manifestPath = path.resolve(root, options.manifest);
          if (!fs.existsSync(manifestPath)) {
            console.error(`Missing feature manifest: ${path.relative(root, manifestPath)}`);
            process.exit(1);
          }
          try {
            return JSON.parse(fs.readFileSync(manifestPath, "utf8"));
          } catch (error) {
            console.error(`Invalid feature manifest: ${path.relative(root, manifestPath)}`);
            console.error(error.message);
            process.exit(1);
          }
        }

        const manifest = readFeatureManifest();
        const featureMode = String(manifest.mode || "new-feature").trim().toLowerCase();
        if (!["new-feature", "incremental", "reconstruction"].includes(featureMode)) {
          console.error(`Unsupported manifest mode: ${featureMode}`);
          process.exit(1);
        }
        const rawSlug = options.slug || manifest.featureSlug || manifest.slug || positional[0];
        const featureName = options.name || manifest.featureName || manifest.name || positional.slice(1).join(" ") || rawSlug;
        const updatedAt = options.updated || manifest.updatedAt || manifest.updated || new Date().toISOString().slice(0, 10);
        const iterationName = options.iteration || manifest.iterationName || manifest.iteration || "未指定";
        const featureSummary = options.summary || manifest.summary || `${featureName}功能原型，包含本次迭代的页面入口、页面清单和独立功能场景。`;

        if (!rawSlug || !featureName) {
          console.error('Usage: node scripts/new-feature.cjs <slug> "功能名称" --updated YYYY-MM-DD --iteration V1 --pages "页面一:page-a.html,页面二:page-b.html"');
          console.error('   or: node scripts/new-feature.cjs --manifest feature-manifest.json');
          process.exit(1);
        }

        function readProjectConfig() {
          const configFile = path.join(root, "design-system", "prototype-config.json");
          if (!fs.existsSync(configFile)) return { framework: "html" };
          try {
            return JSON.parse(fs.readFileSync(configFile, "utf8"));
          } catch (error) {
            console.error(`Invalid prototype config: ${path.relative(root, configFile)}`);
            console.error(error.message);
            process.exit(1);
          }
        }

        function requireAuthoredDesignSystem() {
          const config = readProjectConfig();
          if (config.authoringMode !== "llm") return;
          const statusFile = path.join(root, "design-system", "authoring-status.json");
          if (!fs.existsSync(statusFile)) {
            console.error("Missing design-system/authoring-status.json. Author shared assets and run node scripts/finalize-design-system.cjs first.");
            process.exit(1);
          }
          const status = JSON.parse(fs.readFileSync(statusFile, "utf8"));
          const evidencePages = Object.values((status.visualEvidence && status.visualEvidence.pages) || {});
          const evidenceReady = evidencePages.length > 0 && evidencePages.every((page) => page.viewports && page.viewports.desktop && page.viewports.desktop.path && page.viewports.mobile && page.viewports.mobile.path);
          const designReady = status.designRuntimeSha256
            ? status.designRuntimeSha256 === designRuntimeSha
            : status.designSourceSha256 === designSourceSha;
          if (status.status !== "ready" || !designReady || !evidenceReady) {
            console.error("The LLM-authored design system is pending or stale. Read DESIGN.md, reconcile shared assets, then run node scripts/finalize-design-system.cjs.");
            process.exit(1);
          }
        }

        requireAuthoredDesignSystem();

        function runComplianceCheck() {
          const checkScript = path.join(root, "scripts", "check-prototype-compliance.cjs");
          if (!fs.existsSync(checkScript)) {
            console.error("Missing compliance script: scripts/check-prototype-compliance.cjs");
            process.exit(1);
          }
          const result = childProcess.spawnSync(process.execPath, [checkScript], {
            cwd: root,
            stdio: "inherit",
          });
          if (result.status !== 0) {
            console.error("Generated feature failed DESIGN.md compliance checks.");
            process.exit(result.status || 1);
          }
        }

        function existingFeatureDirs() {
          const config = readProjectConfig();
          const featureRoot = config.framework === "react" || config.framework === "vue"
            ? path.join(root, "src", "features")
            : root;
          if (!fs.existsSync(featureRoot)) return [];
          return fs.readdirSync(featureRoot, { withFileTypes: true })
            .filter((entry) => entry.isDirectory() && /^\d{2}-[a-z0-9-]+$/.test(entry.name))
            .map((entry) => entry.name)
            .sort();
        }

        function nextPrefix() {
          const max = existingFeatureDirs()
            .map((name) => Number(name.slice(0, 2)))
            .filter((value) => Number.isFinite(value))
            .reduce((acc, value) => Math.max(acc, value), 0);
          return String(max + 1).padStart(2, "0");
        }

        function normalizeFeatureSlug(value) {
          let slug = value.trim().toLowerCase();
          if (/^\d{2}-/.test(slug)) {
            const rest = slug.slice(3);
            if (!/^[a-z0-9][a-z0-9-]*$/.test(rest)) {
              throw new Error(`Invalid feature slug: ${value}`);
            }
            return slug;
          }
          if (!/^[a-z0-9][a-z0-9-]*$/.test(slug)) {
            throw new Error(`Invalid feature slug: ${value}`);
          }
          return `${nextPrefix()}-${slug}`;
        }

        function fallbackPageFile(index, prefix = "page") {
          return `${prefix}-${index + 1}.html`;
        }

        function normalizePageFile(file, index, fallback) {
          const value = (file || fallback || fallbackPageFile(index)).trim().toLowerCase();
          const withExt = value.endsWith(".html") ? value : `${value}.html`;
          if (!/^[a-z0-9][a-z0-9-]*\.html$/.test(withExt) || withExt === "index.html") {
            return fallback || fallbackPageFile(index);
          }
          return withExt;
        }

        function pagePathFromFile(file) {
          return file.replace(/\.html$/i, "");
        }

        function normalizePageKey(value, fallback) {
          const normalized = String(value || fallback || "")
            .trim()
            .toLowerCase()
            .replace(/\.html$/i, "")
            .replace(/[^a-z0-9]+/g, "-")
            .replace(/^-+|-+$/g, "");
          return normalized || fallback || "page";
        }

        function normalizeSurface(value) {
          const raw = String(value || "").trim().toLowerCase();
          const aliases = {
            dialog: "modal",
            popup: "modal",
            popover: "modal",
            panel: "side-panel",
            sidepanel: "side-panel",
            confirmdialog: "confirm",
            confirmation: "confirm",
          };
          const normalized = aliases[raw] || raw;
          if (["page", "drawer", "modal", "side-panel", "confirm"].includes(normalized)) {
            return normalized;
          }
          return "page";
        }

        function scenarioDefaultFile(parentPage, scenario, index) {
          const surface = normalizeSurface(scenario && scenario.surface ? scenario.surface : "drawer");
          const key = scenario && (scenario.pageKey || scenario.key || scenario.path || scenario.slug);
          if (key) return `${normalizePageKey(key, `${parentPage.path}-${surface}-${index + 1}`)}.html`;
          return `${parentPage.path}-${surface}-${index + 1}.html`;
        }

        function normalizePageDescriptor(input, index, parentPage = null) {
          const source = typeof input === "string" ? { title: input } : (input || {});
          const title = String(source.title || source.name || source.label || (parentPage ? `功能场景${index + 1}` : `页面${index + 1}`)).trim();
          const fallback = parentPage ? scenarioDefaultFile(parentPage, source, index) : fallbackPageFile(index);
          const file = normalizePageFile(source.file || source.path || source.slug || source.pageKey || source.key, index, fallback);
          const pagePath = pagePathFromFile(file);
          const surface = parentPage ? normalizeSurface(source.surface || "drawer") : normalizeSurface(source.surface || "page");
          const requestedStatus = String(source.requirementStatus || "").trim().toLowerCase();
          const description = String(source.description || "").trim();
          const confirmed = requestedStatus === "confirmed" && description.length > 0;
          const baseline = source.baseline && typeof source.baseline === "object" ? source.baseline : {};
          const changes = source.changes && typeof source.changes === "object" ? source.changes : {};
          const preserve = Array.isArray(source.preserve) ? source.preserve.map(String).filter(Boolean) : [];
          const allowedFiles = Array.isArray(source.allowedFiles) ? source.allowedFiles.map(String).filter(Boolean) : [];
          const requestedDesignDomains = Array.isArray(source.designDomains) && source.designDomains.length
            ? source.designDomains.map(String).filter((item) => ["tokens", "shell", "components", "patterns", "rules"].includes(item))
            : ["tokens", "shell", "components", "patterns", "rules"];
          const designDomains = [...new Set(["tokens", "shell", ...requestedDesignDomains])];
          const sharedRefs = Array.isArray(source.sharedRefs) ? source.sharedRefs.map(String).filter(Boolean) : [];
          const evidenceRefs = Array.isArray(source.evidenceRefs) ? source.evidenceRefs.map(String).filter(Boolean) : [];
          return {
            title,
            file,
            path: pagePath,
            pageKey: normalizePageKey(source.pageKey || source.key || pagePath, pagePath),
            kind: parentPage ? "scenario" : String(source.kind || "page"),
            parentPageKey: parentPage ? normalizePageKey(source.parentPageKey || parentPage.pageKey, parentPage.pageKey) : "",
            parentTitle: parentPage ? parentPage.title : "",
            surface,
            summary: String(source.summary || description || ""),
            description,
            requestedRequirementStatus: requestedStatus,
            requirementStatus: confirmed ? "confirmed" : "needs-input",
            generationMode: confirmed ? (featureMode === "incremental" ? "incremental-baseline" : (featureMode === "reconstruction" ? "reconstruction-scaffold" : "scaffold")) : "placeholder",
            baselinePath: String(baseline.path || source.baselinePath || "").trim(),
            changes,
            preserve,
            allowedFiles,
            designDomains,
            sharedRefs,
            evidenceRefs,
          };
        }

        function assertUniquePages(pages) {
          for (const field of ["file", "path", "pageKey"]) {
            const seen = new Map();
            for (const page of pages) {
              const value = page[field];
              if (!value) continue;
              if (seen.has(value)) {
                console.error(`Duplicate page ${field}: ${value} (${seen.get(value)} and ${page.title})`);
                process.exit(1);
              }
              seen.set(value, page.title);
            }
          }
        }

        function parsePages(raw) {
          if (Array.isArray(manifest.pages) && manifest.pages.length > 0) {
            const flattened = [];
            manifest.pages.forEach((item, index) => {
              const page = normalizePageDescriptor(item, index);
              flattened.push(page);
              const scenarios = Array.isArray(item.scenarios) ? item.scenarios : [];
              scenarios.forEach((scenario, scenarioIndex) => {
                flattened.push(normalizePageDescriptor(scenario, scenarioIndex, page));
              });
            });
            assertUniquePages(flattened);
            return flattened;
          }

          const text = raw || `${featureName}:page-1.html`;
          const pages = text.split(",")
            .map((part) => part.trim())
            .filter(Boolean)
            .map((part, index) => {
              const [titlePart, filePart] = part.split(":");
              const title = (titlePart || `页面${index + 1}`).trim();
              return normalizePageDescriptor({ title, file: filePart }, index);
            });
          assertUniquePages(pages);
          return pages;
        }

        function readTemplate(name) {
          const file = path.join(root, "templates", name);
          if (!fs.existsSync(file)) {
            console.error(`Missing template: ${path.relative(root, file)}`);
            process.exit(1);
          }
          return fs.readFileSync(file, "utf8");
        }

        function replaceAll(text, replacements) {
          let output = text;
          for (const [key, value] of Object.entries(replacements)) {
            output = output.split(key).join(String(value));
          }
          return output;
        }

        function escapeHtml(value) {
          return String(value)
            .replaceAll("&", "&amp;")
            .replaceAll("<", "&lt;")
            .replaceAll(">", "&gt;");
        }

        function jsString(value) {
          return JSON.stringify(String(value));
        }

        function sha256File(file) {
          return crypto.createHash("sha256").update(fs.readFileSync(file)).digest("hex");
        }

        const runtimeHashes = (() => {
          try { return JSON.parse(fs.readFileSync(path.join(root, "design-system", "design-contract.json"), "utf8")).runtimeHashes || {}; }
          catch (_) { return {}; }
        })();

        function designProfileSha(page) {
          const selected = {};
          for (const domain of page.designDomains) selected[domain] = runtimeHashes[domain] || designRuntimeSha;
          return crypto.createHash("sha256").update(JSON.stringify(selected)).digest("hex");
        }

        function projectFile(relative, extensions) {
          const absolute = path.resolve(root, relative);
          const inside = path.relative(root, absolute);
          if (inside.startsWith("..") || path.isAbsolute(inside) || !fs.existsSync(absolute) || !fs.statSync(absolute).isFile()) {
            console.error(`Invalid baseline path: ${relative}`);
            process.exit(1);
          }
          if (extensions && !extensions.includes(path.extname(absolute).toLowerCase())) {
            console.error(`Baseline ${relative} must use ${extensions.join(", ")}`);
            process.exit(1);
          }
          return absolute;
        }

        function copyDirectoryContents(source, target, excludedExtensions = []) {
          if (!fs.existsSync(source)) return;
          fs.mkdirSync(target, { recursive: true });
          for (const entry of fs.readdirSync(source, { withFileTypes: true })) {
            if (entry.name === "incremental-contract.json") continue;
            const from = path.join(source, entry.name);
            const to = path.join(target, entry.name);
            if (entry.isDirectory()) copyDirectoryContents(from, to, excludedExtensions);
            else if (!excludedExtensions.includes(path.extname(entry.name).toLowerCase())) {
              if (!fs.existsSync(to)) fs.copyFileSync(from, to);
              else if (sha256File(from) !== sha256File(to)) {
                console.error(`Incremental baselines contain conflicting supporting file ${path.relative(root, from)}`);
                process.exit(1);
              }
            }
          }
        }

        function setDataAttribute(text, name, value) {
          const pattern = new RegExp(`(\\bdata-${name}=["'])[^"']*(["'])`, "i");
          if (pattern.test(text)) return text.replace(pattern, `$1${value}$2`);
          const anchor = /\bdata-page-key=["'][^"']*["']/i;
          if (anchor.test(text)) return text.replace(anchor, (match) => `${match} data-${name}="${value}"`);
          return text;
        }

        function adaptBaseline(text, page, featureSlug, componentName, framework) {
          let output = text;
          for (const [name, value] of Object.entries({
            "feature": featureSlug,
            "page-key": page.pageKey,
            "page-kind": page.kind,
            "parent-page-key": page.parentPageKey,
            "surface": page.surface,
            "requirement-status": "confirmed",
            "generation-mode": "incremental-baseline",
            "design-source-sha": designSourceSha,
            "design-runtime-sha": designRuntimeSha,
            "design-domains": page.designDomains.join(","),
            "shared-refs": page.sharedRefs.join(","),
            "design-profile-sha": designProfileSha(page),
          })) output = setDataAttribute(output, name, value);
          if (framework === "react") output = output.replace(/export function\s+[A-Za-z_$][\w$]*\s*\(/, `export function ${componentName}(`);
          if (framework === "vue") output = output.replace(/name:\s*["'][^"']+["']/, `name: ${jsString(componentName)}`);
          return output;
        }

        function treeHashes(dir) {
          const hashes = {};
          const visit = (current) => {
            for (const entry of fs.readdirSync(current, { withFileTypes: true })) {
              if (entry.name === "incremental-contract.json") continue;
              if (entry.isDirectory() && entry.name === "fidelity-evidence") continue;
              const file = path.join(current, entry.name);
              if (entry.isDirectory()) visit(file);
              else hashes[path.relative(dir, file).replaceAll(path.sep, "/")] = sha256File(file);
            }
          };
          visit(dir);
          return hashes;
        }

        function supportingHashes(dir, excludedExtensions = []) {
          const hashes = {};
          if (!fs.existsSync(dir)) return hashes;
          const visit = (current) => {
            for (const entry of fs.readdirSync(current, { withFileTypes: true })) {
              if (entry.name === "incremental-contract.json" || entry.name === "fidelity-evidence") continue;
              const file = path.join(current, entry.name);
              if (entry.isDirectory()) visit(file);
              else if (!excludedExtensions.includes(path.extname(entry.name).toLowerCase())) {
                hashes[path.relative(root, file).replaceAll(path.sep, "/")] = sha256File(file);
              }
            }
          };
          visit(dir);
          return hashes;
        }

        function writeIncrementalContract(featureDir, pages) {
          if (featureMode !== "incremental") return;
          const confirmedPages = pages.filter((page) => page.generationMode !== "placeholder");
          if (confirmedPages.length === 0) return;
          const preparedFiles = treeHashes(featureDir);
          const contract = {
            version: 1,
            mode: "incremental",
            featureSlug,
            designSourceSha256: designSourceSha,
            designRuntimeSha256: designRuntimeSha,
            createdAt: new Date().toISOString(),
            pages: confirmedPages.map((page) => ({
              pageKey: page.pageKey,
              target: page.targetRelative,
              baseline: page.baselineRelative,
              baselineSha256: page.baselineSha256,
              baselineSupportingFiles: page.baselineSupportingFiles || {},
              preparedSha256: preparedFiles[page.targetRelative],
              changes: page.changes,
              preserve: page.preserve,
              allowedFiles: [...new Set(page.allowedFiles.map((file) => file === "$page" ? page.targetRelative : file))],
            })),
            preparedFiles,
          };
          fs.writeFileSync(path.join(featureDir, "incremental-contract.json"), JSON.stringify(contract, null, 2) + "\n");
        }

        function writeReconstructionContract(featureDir, pages) {
          if (featureMode !== "reconstruction") return;
          const confirmedPages = pages.filter((page) => page.generationMode !== "placeholder");
          if (confirmedPages.length === 0) return;
          const contract = {
            version: 1,
            mode: "reconstruction",
            featureSlug,
            designSourceSha256: designSourceSha,
            designRuntimeSha256: designRuntimeSha,
            createdAt: new Date().toISOString(),
            pages: confirmedPages.map((page) => ({
              pageKey: page.pageKey,
              target: page.targetRelative,
              evidenceRefs: page.evidenceRefs,
              designDomains: page.designDomains,
              sharedRefs: page.sharedRefs,
              designProfileSha256: designProfileSha(page),
            })),
          };
          fs.writeFileSync(path.join(featureDir, "reconstruction-contract.json"), JSON.stringify(contract, null, 2) + "\n");
        }

        function pascalIdentifier(value, fallback) {
          const parts = String(value).split(/[^a-zA-Z0-9]+/).filter(Boolean);
          const name = parts.map((part) => part.charAt(0).toUpperCase() + part.slice(1)).join("") || fallback;
          return /^[A-Za-z]/.test(name) ? name : `Feature${name}`;
        }

        function componentNameFromFile(featureSlug, file, index) {
          const featurePart = pascalIdentifier(featureSlug, "Feature");
          const pagePart = pascalIdentifier(pagePathFromFile(file), `Page${index + 1}`);
          return `${featurePart}${pagePart}`;
        }

        function surfaceName(surface) {
          return {
            page: "页面",
            drawer: "抽屉",
            modal: "弹窗",
            "side-panel": "侧滑面板",
            confirm: "确认弹窗",
          }[surface] || "承载面";
        }

        function scenarioSurfaceHtml(page) {
          if (page.kind !== "scenario") return "";
          const isConfirm = page.surface === "confirm";
          const primaryText = isConfirm ? "确认" : "保存";
          if (isConfirm) {
            return [
              '          <div class="confirm-mask is-open"></div>',
              `          <section class="confirm-dialog is-open" role="dialog" aria-modal="true" aria-labelledby="scenario-title" data-scenario-page-key="${page.pageKey}" data-parent-page-key="${page.parentPageKey}" data-surface="${page.surface}">`,
              '            <div class="confirm-dialog__body">',
              `              <h2 id="scenario-title">${escapeHtml(page.title)}</h2>`,
              `              <p>${surfaceName(page.surface)}场景，父页面：${escapeHtml(page.parentTitle || page.parentPageKey)}</p>`,
              '            </div>',
              '            <footer class="confirm-dialog__footer">',
              '              <button class="btn" type="button">取消</button>',
              `              <button class="btn btn--primary" type="button"><span class="product-icon" data-icon="success"></span>${primaryText}</button>`,
              '            </footer>',
              '          </section>',
            ].join("\n");
          }
          return [
            '          <div class="drawer-mask is-open"></div>',
            `          <section class="drawer-panel drawer-panel--60 is-open" role="dialog" aria-modal="true" aria-labelledby="scenario-title" data-scenario-page-key="${page.pageKey}" data-parent-page-key="${page.parentPageKey}" data-surface="${page.surface}">`,
            '              <header class="drawer-panel__header">',
            '                <div>',
            `                  <h2 id="scenario-title">${escapeHtml(page.title)}</h2>`,
            `                  <p>${surfaceName(page.surface)}场景，父页面：${escapeHtml(page.parentTitle || page.parentPageKey)}</p>`,
            '                </div>',
            '                <button class="btn btn--icon" type="button" aria-label="关闭" title="关闭" data-close-drawer><span class="product-icon" data-icon="close"></span></button>',
            '              </header>',
            '              <div class="drawer-panel__body">',
              `                <label class="${shellClasses.filter_field} form-row">`,
              `                  <span class="${shellClasses.filter_label} form-label is-required">名称</span>`,
              `                  <input class="${shellClasses.filter_input}" type="text" placeholder="请输入名称">`,
              '                </label>',
              `                <label class="${shellClasses.filter_field} form-row">`,
              `                  <span class="${shellClasses.filter_label} form-label">说明</span>`,
              `                  <textarea class="${shellClasses.filter_input}" rows="4" placeholder="请输入说明"></textarea>`,
            '                </label>',
            '              </div>',
            '              <footer class="drawer-panel__footer">',
            '                <button class="btn" type="button">取消</button>',
            `                <button class="btn btn--primary" type="button"><span class="product-icon" data-icon="success"></span>${primaryText}</button>`,
            '              </footer>',
            '            </section>',
          ].join("\n");
        }

        function reactScenarioSurface(page) {
          if (page.kind !== "scenario") return "";
          const isConfirm = page.surface === "confirm";
          const primaryText = isConfirm ? "确认" : "保存";
          return `      <div className="drawer-mask is-open" data-scenario-page-key="${page.pageKey}" data-parent-page-key="${page.parentPageKey}" data-surface="${page.surface}">
        <section className="drawer-panel drawer-panel--60 is-open" role="dialog" aria-modal="true" aria-labelledby="scenario-title">
          <header className="drawer-panel__header">
            <div>
              <h2 id="scenario-title">${escapeHtml(page.title)}</h2>
              <p>${surfaceName(page.surface)}场景，父页面：${escapeHtml(page.parentTitle || page.parentPageKey)}</p>
            </div>
            <button className="btn btn--icon" type="button" aria-label="关闭" title="关闭"><span className="product-icon" data-icon="close"></span></button>
          </header>
          <div className="drawer-panel__body">
            <label className="${shellClasses.filter_field} form-row">
              <span className="${shellClasses.filter_label} form-label is-required">名称</span>
              <input className="${shellClasses.filter_input}" type="text" placeholder="请输入名称" />
            </label>
            <label className="${shellClasses.filter_field} form-row">
              <span className="${shellClasses.filter_label} form-label">说明</span>
              <textarea className="${shellClasses.filter_input}" rows="4" placeholder="请输入说明" />
            </label>
          </div>
          <footer className="drawer-panel__footer">
            <button className="btn" type="button">取消</button>
            <button className="btn btn--primary" type="button"><span className="product-icon" data-icon="success"></span>${primaryText}</button>
          </footer>
        </section>
      </div>`;
        }

        function vueScenarioSurface(page) {
          if (page.kind !== "scenario") return "";
          const isConfirm = page.surface === "confirm";
          const primaryText = isConfirm ? "确认" : "保存";
          return `    <div class="drawer-mask is-open" data-scenario-page-key="${page.pageKey}" data-parent-page-key="${page.parentPageKey}" data-surface="${page.surface}">
      <section class="drawer-panel drawer-panel--60 is-open" role="dialog" aria-modal="true" aria-labelledby="scenario-title">
        <header class="drawer-panel__header">
          <div>
            <h2 id="scenario-title">${escapeHtml(page.title)}</h2>
            <p>${surfaceName(page.surface)}场景，父页面：${escapeHtml(page.parentTitle || page.parentPageKey)}</p>
          </div>
          <button class="btn btn--icon" type="button" aria-label="关闭" title="关闭"><span class="product-icon" data-icon="close"></span></button>
        </header>
        <div class="drawer-panel__body">
          <label class="${shellClasses.filter_field} form-row">
            <span class="${shellClasses.filter_label} form-label is-required">名称</span>
            <input class="${shellClasses.filter_input}" type="text" placeholder="请输入名称">
          </label>
          <label class="${shellClasses.filter_field} form-row">
            <span class="${shellClasses.filter_label} form-label">说明</span>
            <textarea class="${shellClasses.filter_input}" rows="4" placeholder="请输入说明"></textarea>
          </label>
        </div>
        <footer class="drawer-panel__footer">
          <button class="btn" type="button">取消</button>
          <button class="btn btn--primary" type="button"><span class="product-icon" data-icon="success"></span>${primaryText}</button>
        </footer>
      </section>
    </div>`;
        }

        function reactPlaceholderTemplate(componentName, page, featureName) {
          return `export function ${componentName}() {
  return (
    <section className="${shellClasses.panel}" data-page-key="${page.pageKey}" data-page-kind="${page.kind}" data-parent-page-key="${page.parentPageKey}" data-surface="${page.surface}" data-requirement-status="needs-input" data-generation-mode="placeholder" data-design-source-sha="${designSourceSha}" data-design-runtime-sha="${designRuntimeSha}" data-design-contract-version="${designContractVersion}">
      <header className="${shellClasses.section_header}">
        <div>
          <p className="proto-kicker">需求待补充</p>
          <h1 className="${shellClasses.section_title}">${escapeHtml(page.title)}</h1>
          <p className="proto-page-summary">该页面尚未设计</p>
        </div>
      </header>
      <div className="proto-page-summary">
        <p>请补充以下材料后再生成正式业务原型：</p>
        <ul><li>本次升级功能描述</li><li>现有产品截图或可访问的网站 URL</li><li>明确保持不变的页面范围</li><li>验收要求</li></ul>
        <p><a href="#/feature/${featureSlug}">返回功能入口</a></p>
      </div>
    </section>
  );
}
`;
        }

        function vuePlaceholderTemplate(componentName, page, featureName) {
          return `<template>
  <section class="${shellClasses.panel}" data-page-key="${page.pageKey}" data-page-kind="${page.kind}" data-parent-page-key="${page.parentPageKey}" data-surface="${page.surface}" data-requirement-status="needs-input" data-generation-mode="placeholder" data-design-source-sha="${designSourceSha}" data-design-runtime-sha="${designRuntimeSha}" data-design-contract-version="${designContractVersion}">
    <header class="${shellClasses.section_header}">
      <div><p class="proto-kicker">需求待补充</p><h1 class="${shellClasses.section_title}">${escapeHtml(page.title)}</h1><p class="proto-page-summary">该页面尚未设计</p></div>
    </header>
    <div class="proto-page-summary">
      <p>请补充以下材料后再生成正式业务原型：</p>
      <ul><li>本次升级功能描述</li><li>现有产品截图或可访问的网站 URL</li><li>明确保持不变的页面范围</li><li>验收要求</li></ul>
      <p><a href="#/feature/${featureSlug}">返回功能入口</a></p>
    </div>
  </section>
</template>
<script>export default { name: ${jsString(componentName)} };</script>
`;
        }

        function reactPageTemplate(componentName, page, featureName) {
          if (page.generationMode === "placeholder") return reactPlaceholderTemplate(componentName, page, featureName);
          const pageTitle = escapeHtml(page.title);
          const feature = escapeHtml(featureName);
          const scenario = reactScenarioSurface(page);
          const description = escapeHtml(page.description || "");
          // Framework scaffolds deliberately stop at facts supplied by the feature
          // manifest. Fields, filters, actions and sample rows require authoring;
          // generating a generic admin table here would fabricate product behavior.
          return `export function ${componentName}() {
  return (
    <section className="list-container ${shellClasses.panel}" data-prototype-role="content-region" data-page-template="filter-table-list" data-page-key="${page.pageKey}" data-page-kind="${page.kind}" data-parent-page-key="${page.parentPageKey}" data-surface="${page.surface}" data-requirement-status="confirmed" data-generation-mode="${page.generationMode}" data-design-source-sha="${designSourceSha}" data-design-runtime-sha="${designRuntimeSha}" data-design-contract-version="${designContractVersion}" data-design-domains="${page.designDomains.join(",")}" data-shared-refs="${page.sharedRefs.join(",")}" data-design-profile-sha="${designProfileSha(page)}">
      <header className="${shellClasses.section_header}"><div><p className="proto-kicker">${feature}</p><h1 className="${shellClasses.section_title}">${pageTitle}</h1><p className="proto-page-summary">${description}</p></div></header>
      <section className="search-container ${shellClasses.filter}" data-prototype-role="search-region"><div className="${shellClasses.filter_grid}"></div></section>
      <section className="data-table-wrap"><table className="data-table"><thead></thead><tbody></tbody></table><footer className="pagination-bar" data-prototype-role="pagination"></footer></section>
${scenario}
    </section>
  );
}
`;
        }

        function vuePageTemplate(componentName, page, featureName) {
          if (page.generationMode === "placeholder") return vuePlaceholderTemplate(componentName, page, featureName);
          const pageTitle = escapeHtml(page.title);
          const feature = escapeHtml(featureName);
          const scenario = vueScenarioSurface(page);
          const description = escapeHtml(page.description || "");
          return `<template>
  <section class="list-container ${shellClasses.panel}" data-prototype-role="content-region" data-page-template="filter-table-list" data-page-key="${page.pageKey}" data-page-kind="${page.kind}" data-parent-page-key="${page.parentPageKey}" data-surface="${page.surface}" data-requirement-status="confirmed" data-generation-mode="${page.generationMode}" data-design-source-sha="${designSourceSha}" data-design-runtime-sha="${designRuntimeSha}" data-design-contract-version="${designContractVersion}" data-design-domains="${page.designDomains.join(",")}" data-shared-refs="${page.sharedRefs.join(",")}" data-design-profile-sha="${designProfileSha(page)}">
    <header class="${shellClasses.section_header}"><div><p class="proto-kicker">${feature}</p><h1 class="${shellClasses.section_title}">${pageTitle}</h1><p class="proto-page-summary">${description}</p></div></header>
    <section class="search-container ${shellClasses.filter}" data-prototype-role="search-region"><div class="${shellClasses.filter_grid}"></div></section>
    <section class="data-table-wrap"><table class="data-table"><thead></thead><tbody></tbody></table><footer class="pagination-bar" data-prototype-role="pagination"></footer></section>
${scenario}
  </section>
</template>
<script>export default { name: ${jsString(componentName)} };</script>
`;
        }

        function updateRegistry({ framework, featureSlug, featureName, updatedAt, iterationName, featureSummary, pages }) {
          const registryPath = path.join(root, "src", "prototype-registry.js");
          if (!fs.existsSync(registryPath)) {
            console.error("Missing framework registry: src/prototype-registry.js");
            process.exit(1);
          }
          let registry = fs.readFileSync(registryPath, "utf8");
          if (registry.includes(`slug: ${jsString(featureSlug)}`)) {
            if (!options.force) {
              console.error(`Registry already contains feature: ${featureSlug}`);
              process.exit(1);
            }
            console.warn(`WARN registry already contains ${featureSlug}; component files were refreshed but registry was not duplicated.`);
            return;
          }

          const extension = framework === "react" ? "jsx" : "vue";
          const imports = pages
            .map((page) => `import ${framework === "react" ? `{ ${page.componentName} }` : page.componentName} from "./features/${featureSlug}/${page.componentName}.${extension}";`)
            .join("\n");
          const pageEntries = pages
            .map((page) => `      { title: ${jsString(page.title)}, path: ${jsString(page.path)}, pageKey: ${jsString(page.pageKey)}, kind: ${jsString(page.kind)}, surface: ${jsString(page.surface)}, parentPageKey: ${jsString(page.parentPageKey)}, requirementStatus: ${jsString(page.requirementStatus)}, generationMode: ${jsString(page.generationMode)}, designDomains: ${JSON.stringify(page.designDomains)}, sharedRefs: ${JSON.stringify(page.sharedRefs)}, component: ${page.componentName} },`)
            .join("\n");
          const featureEntry = [
            "  {",
            `    slug: ${jsString(featureSlug)},`,
            `    name: ${jsString(featureName)},`,
            `    updatedAt: ${jsString(updatedAt)},`,
            `    iterationName: ${jsString(iterationName)},`,
            `    summary: ${jsString(featureSummary)},`,
            "    pages: [",
            pageEntries,
            "    ],",
            "  },",
          ].join("\n");

          registry = registry.replace("// IMPORTS_END", `${imports}\n// IMPORTS_END`);
          registry = registry.replace("  // FEATURES_END", `${featureEntry}\n  // FEATURES_END`);
          fs.writeFileSync(registryPath, registry);
        }

        const featureSlug = normalizeFeatureSlug(rawSlug);
        const projectConfig = readProjectConfig();
        const framework = projectConfig.framework || "html";
        const pages = parsePages(options.pages);
        if (featureMode === "reconstruction") {
          if (!options.manifest) {
            console.error("Reconstruction mode requires --manifest and registered evidence sources.");
            process.exit(1);
          }
          let sources = {};
          try { sources = JSON.parse(fs.readFileSync(path.join(root, "design-system", "evidence-sources.json"), "utf8")).sources || {}; }
          catch (_) { console.error("Missing or invalid design-system/evidence-sources.json"); process.exit(1); }
          for (const page of pages) {
            if (page.generationMode === "placeholder") continue;
            if (page.evidenceRefs.length === 0) {
              console.error(`${page.title}: reconstruction page requires evidenceRefs`);
              process.exit(1);
            }
            for (const ref of page.evidenceRefs) {
              const source = sources[ref];
              if (!source || !source.viewports || !source.viewports.desktop || !source.viewports.mobile) {
                console.error(`${page.title}: invalid reconstruction evidence source ${ref}`);
                process.exit(1);
              }
            }
          }
        }
        if (featureMode === "incremental") {
          if (!options.manifest) {
            console.error("Incremental mode requires --manifest so baseline and preservation rules are explicit.");
            process.exit(1);
          }
          if (options.force) {
            console.error("Incremental mode refuses --force. Create a new numbered iteration so the prior baseline remains intact.");
            process.exit(1);
          }
          for (const page of pages) {
            if (page.generationMode === "placeholder") continue;
            const changeCount = ["add", "modify", "delete"]
              .flatMap((key) => Array.isArray(page.changes[key]) ? page.changes[key] : [])
              .filter(Boolean).length;
            if (!page.baselinePath) {
              console.error(`${page.title}: incremental page requires baseline.path`);
              process.exit(1);
            }
            if (changeCount === 0) {
              console.error(`${page.title}: incremental page requires at least one changes.add/modify/delete item`);
              process.exit(1);
            }
            if (page.preserve.length === 0) {
              console.error(`${page.title}: incremental page requires a non-empty preserve list`);
              process.exit(1);
            }
            if (page.allowedFiles.length === 0) {
              console.error(`${page.title}: incremental page requires allowedFiles; use $page for the target page`);
              process.exit(1);
            }
            for (const allowed of page.allowedFiles) {
              const normalized = String(allowed).replaceAll("\\", "/");
              if (normalized !== "$page" && (normalized.startsWith("../") || normalized.startsWith("/") || normalized.includes("/../"))) {
                console.error(`${page.title}: allowedFiles must stay inside the new feature directory: ${allowed}`);
                process.exit(1);
              }
            }
          }
        }
        for (const page of pages) {
          if (page.generationMode !== "placeholder") continue;
          if (page.requestedRequirementStatus === "confirmed" && !page.description) {
            console.warn(`WARN ${page.title}: requirementStatus 为 confirmed，但 description 为空，已安全降级为占位页。`);
          } else {
            console.warn(`WARN ${page.title}: 缺少 confirmed 状态或升级描述，已生成“尚未设计”占位页。`);
          }
        }

        if (framework === "react" || framework === "vue") {
          const featureDir = path.join(root, "src", "features", featureSlug);
          if (fs.existsSync(featureDir) && !options.force) {
            console.error(`Refusing to overwrite existing feature folder: src/features/${featureSlug}`);
            process.exit(1);
          }
          fs.mkdirSync(featureDir, { recursive: true });
          if (featureMode === "incremental") {
            for (const page of pages.filter((item) => item.generationMode !== "placeholder")) {
              const baselineFile = projectFile(page.baselinePath, framework === "react" ? [".jsx"] : [".vue"]);
              copyDirectoryContents(path.dirname(baselineFile), featureDir, [".jsx", ".vue", ".html"]);
            }
          }
          const usedNames = new Set();
          const frameworkPages = pages.map((page, index) => {
            let componentName = componentNameFromFile(featureSlug, page.file, index);
            while (usedNames.has(componentName)) componentName = `${componentName}${index + 1}`;
            usedNames.add(componentName);
            const pagePath = pagePathFromFile(page.file);
            const componentPath = path.join(featureDir, `${componentName}.${framework === "react" ? "jsx" : "vue"}`);
            let content;
            if (featureMode === "incremental" && page.generationMode !== "placeholder") {
              const baselineFile = projectFile(page.baselinePath, framework === "react" ? [".jsx"] : [".vue"]);
              content = adaptBaseline(fs.readFileSync(baselineFile, "utf8"), page, featureSlug, componentName, framework);
              page.baselineRelative = path.relative(root, baselineFile).replaceAll(path.sep, "/");
              page.baselineSha256 = sha256File(baselineFile);
              page.baselineSupportingFiles = supportingHashes(path.dirname(baselineFile), [".jsx", ".vue", ".html"]);
            } else {
              content = framework === "react"
                ? reactPageTemplate(componentName, page, featureName)
                : vuePageTemplate(componentName, page, featureName);
            }
            fs.writeFileSync(componentPath, content);
            return { ...page, path: pagePath, componentName, targetRelative: path.basename(componentPath) };
          });

          updateRegistry({
            framework,
            featureSlug,
            featureName,
            updatedAt,
            iterationName,
            featureSummary,
            pages: frameworkPages,
          });

          writeIncrementalContract(featureDir, frameworkPages);
          writeReconstructionContract(featureDir, frameworkPages);
          runComplianceCheck();
          console.log(`Created src/features/${featureSlug}`);
          console.log(`Components: ${frameworkPages.map((page) => `${page.componentName}.${framework === "react" ? "jsx" : "vue"}`).join(", ")}`);
          process.exit(0);
        }

        const featureDir = path.join(root, featureSlug);
        if (fs.existsSync(featureDir) && !options.force) {
          console.error(`Refusing to overwrite existing feature folder: ${featureSlug}`);
          process.exit(1);
        }

        fs.mkdirSync(path.join(featureDir, "assets"), { recursive: true });
        if (featureMode === "incremental") {
          for (const page of pages.filter((item) => item.generationMode !== "placeholder")) {
            const baselineFile = projectFile(page.baselinePath, [".html"]);
            copyDirectoryContents(path.join(path.dirname(baselineFile), "assets"), path.join(featureDir, "assets"));
          }
        }

        const pageCards = pages.map((page) => [
          `        <a class="proto-page-card" href="./${page.file}">`,
          `          <strong>${page.title}</strong>`,
          `          <span>${page.generationMode === "placeholder" ? "尚未设计｜" : ""}${page.kind === "scenario" ? `${surfaceName(page.surface)}场景` : "页面"}｜pageKey：${page.pageKey}</span>`,
          "        </a>",
        ].join("\n")).join("\n");

        const common = {
          "{{FEATURE_SLUG}}": featureSlug,
          "{{FEATURE_NAME}}": featureName,
          "{{FEATURE_SUMMARY}}": featureSummary,
          "{{UPDATED_AT}}": updatedAt,
          "{{ITERATION_NAME}}": iterationName,
          "{{PAGE_CARDS}}": pageCards,
        };

        const featureIndex = replaceAll(readTemplate("feature-index.html"), common);
        fs.writeFileSync(path.join(featureDir, "index.html"), featureIndex);

        for (const page of pages) {
          let pageHtml;
          if (featureMode === "incremental" && page.generationMode !== "placeholder") {
            const baselineFile = projectFile(page.baselinePath, [".html"]);
            pageHtml = adaptBaseline(fs.readFileSync(baselineFile, "utf8"), page, featureSlug, "", "html");
            page.baselineRelative = path.relative(root, baselineFile).replaceAll(path.sep, "/");
            page.baselineSha256 = sha256File(baselineFile);
            page.baselineSupportingFiles = supportingHashes(path.join(path.dirname(baselineFile), "assets"));
          } else {
            const pageTemplate = readTemplate(page.generationMode === "placeholder" ? "placeholder-page.html" : "prototype-page.html");
            pageHtml = replaceAll(pageTemplate, {
              ...common,
              "{{PAGE_TITLE}}": page.title,
              "{{PAGE_KEY}}": page.pageKey,
              "{{PAGE_KIND}}": page.kind,
              "{{PARENT_PAGE_KEY}}": page.parentPageKey,
              "{{SURFACE}}": page.surface,
              "{{REQUIREMENT_STATUS}}": page.requirementStatus,
              "{{GENERATION_MODE}}": page.generationMode,
              "{{DESIGN_DOMAINS}}": page.designDomains.join(","),
              "{{SHARED_REFS}}": page.sharedRefs.join(","),
              "{{DESIGN_PROFILE_SHA}}": designProfileSha(page),
              "{{SCENARIO_SURFACE}}": scenarioSurfaceHtml(page),
            });
          }
          fs.writeFileSync(path.join(featureDir, page.file), pageHtml);
          page.targetRelative = page.file;
        }

        const localCss = path.join(featureDir, "assets", "prototype.css");
        if (!fs.existsSync(localCss) || options.force) {
          fs.writeFileSync(localCss, "/* Feature-local styles. Prefer shared CSS variables and product design classes. */\n");
        }

        const localJs = path.join(featureDir, "assets", "prototype.js");
        if (!fs.existsSync(localJs) || options.force) {
          fs.writeFileSync(localJs, "document.documentElement.dataset.prototypeReady = 'true';\n");
        }

        const rootIndexPath = path.join(root, "index.html");
        if (!fs.existsSync(rootIndexPath)) {
          fs.writeFileSync(rootIndexPath, readTemplate("root-index.html"));
        }

        const rootIndex = fs.readFileSync(rootIndexPath, "utf8");
        const featureHref = `./${featureSlug}/index.html`;
        if (!rootIndex.includes(featureHref)) {
          const card = [
            `        <a class="proto-feature-card" href="${featureHref}" data-feature="${featureSlug}">`,
            `          <strong>${featureName}</strong>`,
            `          <small>更新时间：${updatedAt}｜所属迭代：${iterationName}｜${featureSummary}</small>`,
            "        </a>",
          ].join("\n");
          const marker = "        <!-- FEATURES_END -->";
          const updated = rootIndex.includes(marker)
            ? rootIndex.replace(marker, `${card}\n${marker}`)
            : rootIndex.replace("</body>", `${card}\n</body>`);
          fs.writeFileSync(rootIndexPath, updated);
        }

        writeIncrementalContract(featureDir, pages);
        writeReconstructionContract(featureDir, pages);
        runComplianceCheck();
        console.log(`Created ${featureSlug}`);
        console.log(`Pages: ${pages.map((page) => page.file).join(", ")}`);
        """
    )
    return (
        script.replace("__SHELL_CLASSES_JSON__", json.dumps(shell_classes(design), ensure_ascii=False, indent=2))
        .replace("__DESIGN_SOURCE_SHA__", source_hash)
        .replace("__DESIGN_RUNTIME_SHA__", runtime_hash)
        .replace("__DESIGN_CONTRACT_VERSION__", "4")
    )


def compliance_script(design: dict[str, Any]) -> str:
    script = clean_block(
        r"""
        #!/usr/bin/env node
        const fs = require("fs");
        const path = require("path");
        const crypto = require("crypto");

        const root = path.resolve(__dirname, "..");
        const shellClasses = __SHELL_CLASSES_JSON__;
        const releaseMode = process.argv.includes("--release");
        const errors = [];
        const warnings = [];
        const ignoredDirs = new Set([
          ".git",
          ".netlify",
          "node_modules",
          "shared",
          "templates",
          "scripts",
          "design-system",
          "prototype-specs",
          "DESIGN",
        ]);

        function exists(relative) {
          return fs.existsSync(path.join(root, relative));
        }

        function rel(file) {
          return path.relative(root, file).replaceAll(path.sep, "/");
        }

        function walk(dir) {
          if (!fs.existsSync(dir)) return [];
          const entries = fs.readdirSync(dir, { withFileTypes: true });
          return entries.flatMap((entry) => {
            const full = path.join(dir, entry.name);
            if (entry.isDirectory()) return walk(full);
            return [full];
          });
        }

        function stripScriptsAndStyles(text) {
          return text
            .replace(/<script[\s\S]*?<\/script>/gi, "")
            .replace(/<style[\s\S]*?<\/style>/gi, "");
        }

        function stripHtml(text) {
          return stripScriptsAndStyles(text)
            .replace(/<!--[\s\S]*?-->/g, "")
            .replace(/<[^>]+>/g, "")
            .replace(/\s+/g, "");
        }

        function dataAttr(text, name) {
          const pattern = new RegExp(`\\bdata-${escapeRegExp(name)}=["']([^"']*)["']`, "i");
          const match = text.match(pattern);
          return match ? match[1].trim() : "";
        }

        function isPlaceholder(text) {
          return dataAttr(text, "generation-mode") === "placeholder" || dataAttr(text, "requirement-status") === "needs-input";
        }

        function reportPlaceholder(relative) {
          const message = `${relative}: 页面尚未设计，缺少已确认的升级描述`;
          if (releaseMode) errors.push(`${message}；占位页禁止发布`);
          else warnings.push(message);
        }

        function rawColorMatches(text) {
          return text.match(/#[0-9a-fA-F]{3,8}\b|\b(?:rgb|rgba|hsl|hsla)\s*\(/g) || [];
        }

        function readProjectConfig() {
          const configFile = path.join(root, "design-system", "prototype-config.json");
          if (!fs.existsSync(configFile)) return { framework: "html" };
          try {
            return JSON.parse(fs.readFileSync(configFile, "utf8"));
          } catch (error) {
            errors.push(`design-system/prototype-config.json is invalid JSON: ${error.message}`);
            return { framework: "html" };
          }
        }

        function readJson(relative, fallback) {
          const file = path.join(root, relative);
          if (!fs.existsSync(file)) return fallback;
          try {
            return JSON.parse(fs.readFileSync(file, "utf8"));
          } catch (error) {
            errors.push(`${relative} is invalid JSON: ${error.message}`);
            return fallback;
          }
        }

        function escapeRegExp(value) {
          return String(value).replace(/[.*+?^${}()|[\]\\]/g, "\\$&");
        }

        function hasClass(text, classNames) {
          return String(classNames || "")
            .split(/\s+/)
            .filter(Boolean)
            .some((className) => {
              const pattern = new RegExp(`\\bclass(?:Name)?=(?:["'][^"']*\\b${escapeRegExp(className)}\\b|\\{["'][^"']*\\b${escapeRegExp(className)}\\b)`, "s");
              return pattern.test(text);
            });
        }

        function textLength(value) {
          return Array.from(String(value || "").trim()).length;
        }

        function parseRange(value) {
          const match = String(value || "").match(/(\d+)\s*[-~至]\s*(\d+)/);
          if (!match) return null;
          return { min: Number(match[1]), max: Number(match[2]) };
        }

        function uniqueStrings(values) {
          return [...new Set(values.filter(Boolean).map(String))];
        }

        function extractMessageCandidates(text) {
          const candidates = [];
          const direct = /(?:(?:this\.)?\$message|Message|ElMessage|message)\s*\.\s*(success|error|warning|info)\s*\(\s*["'`]([^"'`]{1,120})["'`]/g;
          let match;
          while ((match = direct.exec(text)) !== null) {
            candidates.push({ type: match[1], text: match[2] });
          }

          const objectCall = /(?:(?:this\.)?\$message|Message|ElMessage|message)\s*\(\s*\{([\s\S]{0,700}?)\}\s*\)/g;
          while ((match = objectCall.exec(text)) !== null) {
            const body = match[1];
            const messageMatch = body.match(/\bmessage\s*:\s*["'`]([^"'`]{1,120})["'`]/);
            if (!messageMatch) continue;
            const typeMatch = body.match(/\btype\s*:\s*["'`](success|error|warning|info)["'`]/);
            candidates.push({ type: typeMatch ? typeMatch[1] : "info", text: messageMatch[1] });
          }
          return candidates;
        }

        function checkMessageCopy(text, relative) {
          const messageRules = checkRules.copywriting && checkRules.copywriting.message;
          if (!messageRules) return;
          const candidates = extractMessageCandidates(text);
          if (candidates.length === 0) return;

          const lengthRule = messageRules.length || {};
          const minLength = Number(lengthRule.min);
          const maxLength = Number(lengthRule.max);
          const success = messageRules.success || {};
          const successTexts = new Set((success.templates || []).map((item) => item && item.text).filter(Boolean));
          const successRange = parseRange(success.charLength);
          const successNoPunctuation = success.punctuation === "none";

          for (const candidate of candidates) {
            const value = candidate.text.trim();
            const length = textLength(value);
            if (Number.isFinite(minLength) && length < minLength) {
              warnings.push(`${relative}: message "${value}" is shorter than copywriting.message.length.min ${minLength}`);
            }
            if (Number.isFinite(maxLength) && length > maxLength) {
              warnings.push(`${relative}: message "${value}" is longer than copywriting.message.length.max ${maxLength}`);
            }
            if (candidate.type === "success") {
              if (successNoPunctuation && /[。.!！；;，,：:]$/.test(value)) {
                warnings.push(`${relative}: success message "${value}" should not end with punctuation`);
              }
              if (success.format && String(success.format).includes("成功") && !successTexts.has(value) && !value.endsWith("成功")) {
                warnings.push(`${relative}: success message "${value}" does not match configured success format ${success.format}`);
              }
              if (successRange && !success.allowBusinessPrefix && (length < successRange.min || length > successRange.max)) {
                warnings.push(`${relative}: success message "${value}" should be ${successRange.min}-${successRange.max} characters`);
              }
            }
          }
        }

        function checkDisallowedDesignValues(text, relative, context) {
          const legacyRules = checkRules.legacyTokens && checkRules.legacyTokens.disallowedRawValues;
          if (!Array.isArray(legacyRules) || legacyRules.length === 0) return;
          const reportedValues = new Set();
          for (const rule of legacyRules) {
            if (!rule || !rule.value) continue;
            const valueKey = String(rule.value).toLowerCase();
            if (reportedValues.has(valueKey)) continue;
            const pattern = new RegExp(escapeRegExp(rule.value), "i");
            if (pattern.test(text)) {
              reportedValues.add(valueKey);
              const note = rule.note ? ` (${rule.note})` : "";
              warnings.push(`${relative}: ${context} uses legacy token value ${rule.value}${note}`);
            }
          }
        }

        function collectDesignClassNames(value, output = new Set()) {
          if (!value) return output;
          if (Array.isArray(value)) {
            for (const item of value) collectDesignClassNames(item, output);
            return output;
          }
          if (typeof value === "object") {
            for (const [key, item] of Object.entries(value)) {
              if (/^(classNames?|classes|selector|source)$/i.test(key)) {
                collectDesignClassNames(item && typeof item === "object" && !Array.isArray(item) ? Object.values(item) : item, output);
              }
              else if (typeof item === "object") collectDesignClassNames(item, output);
            }
            return output;
          }
          if (typeof value === "string") {
            const matches = value.match(/\.?[A-Za-z][A-Za-z0-9_-]{2,}/g) || [];
            for (const match of matches) {
              const cleaned = match.replace(/^\./, "");
              if (!/^(div|span|button|input|select|table|thead|tbody|header|footer|section|main|aside)$/.test(cleaned)) {
                output.add(cleaned);
              }
            }
          }
          return output;
        }

        function productClassFingerprints() {
          const design = designContract && designContract.design ? designContract.design : {};
          return [...collectDesignClassNames({
            layout: design.layout,
            components: design.components,
            pageTemplates: design.pageTemplates,
            generationRules: design.generationRules,
          })];
        }

        function checkLocalIconRuntime(text, relative, isProductPage) {
          if (/unpkg\.com\/lucide|cdn\.jsdelivr\.net\/npm\/lucide|data-lucide/i.test(text)) {
            errors.push(`${relative}: icon rendering must use local shared/js/product-icons.js, not external lucide/CDN dependencies`);
          }
          if (/[☰↻×]/.test(stripHtml(text)) || />\s*(AI)\s*</.test(text)) {
            warnings.push(`${relative}: text-symbol icon fallback found; prefer <span class="product-icon" data-icon="..."></span>`);
          }
          if (isProductPage && !text.includes("../shared/js/product-icons.js") && !/from ['"]\.\.\/shared\/js\/product-icons\.js['"]/.test(text)) {
            errors.push(`${relative}: product page must load shared/js/product-icons.js for offline icon rendering`);
          }
        }

        function checkProductRoles(text, relative) {
          const isListTemplate = /data-page-template=["'](filter-table-list|table-list|admin-list|list)["']/.test(text);
          if (!isListTemplate) return;
          const requiredRoles = [
            ["search-region", (value) => /data-prototype-role=["']search-region["']|filter-bar|search-bar/.test(value) || value.includes(shellClasses.filter)],
            ["list-region", (value) => /data-prototype-role=["']list-region["']|list-container|table-card|content-list/.test(value) || value.includes(shellClasses.panel)],
            ["table", /data-table|<table\b|grid-table/],
            ["pagination", /pagination-bar|pagination|pager/],
          ];
          for (const [name, pattern] of requiredRoles) {
            const matched = typeof pattern === "function" ? pattern(text) : pattern.test(text);
            if (!matched) errors.push(`${relative}: list page missing product role ${name}`);
          }
          if (!/(data-icon=["']search["']|class=["'][^"']*search[^"']*icon|搜索|查询)/.test(text)) {
            warnings.push(`${relative}: list page search action should include a search affordance or product icon`);
          }
        }

        function checkDesignFingerprints(text, relative) {
          const fidelityRules = checkRules.productFidelity || {};
          const configured = Array.isArray(fidelityRules.classFingerprints) ? fidelityRules.classFingerprints : [];
          const fingerprints = (configured.length > 0 ? configured : productClassFingerprints()).filter((name) => name && name.length >= 3);
          if (fingerprints.length === 0) return;
          const relevant = fingerprints.filter((name) => !/^proto-/.test(name)).slice(0, 24);
          if (relevant.length === 0) return;
          const matched = relevant.filter((name) => text.includes(name));
          if (matched.length === 0) {
            const message = `${relative}: no DESIGN.md product class fingerprint found; this page appears to have fallen back to a generic prototype structure`;
            if (fidelityRules.requireProductFingerprint) errors.push(message);
            else warnings.push(message);
          }
        }

        function recordedSourceSha() {
          return (designContract && (designContract.sourceSha256 || (designContract.meta && designContract.meta.sourceSha256)))
            || (fidelityGuardrails && fidelityGuardrails.sourceSha256)
            || "";
        }

        function recordedRuntimeSha() {
          return (designContract && (designContract.designRuntimeSha256 || (designContract.meta && designContract.meta.designRuntimeSha256)))
            || (fidelityGuardrails && fidelityGuardrails.designRuntimeSha256)
            || "";
        }

        function checkGuardrailsSource() {
          const sourceSha = recordedSourceSha();
          if (!fidelityGuardrails || Object.keys(fidelityGuardrails).length === 0) return;
          if (sourceSha && fidelityGuardrails.sourceSha256 && fidelityGuardrails.sourceSha256 !== sourceSha) {
            errors.push("design-system/fidelity-guardrails.json sourceSha256 does not match design contract");
          }
        }

        function checkDesignSourceAnchor(text, relative, isProductPage) {
          if (!isProductPage) return;
          const expected = recordedSourceSha();
          const actual = dataAttr(text, "design-source-sha");
          const runtimeActual = dataAttr(text, "design-runtime-sha");
          const runtimeExpected = recordedRuntimeSha();
          const declaredDomains = String(dataAttr(text, "design-domains") || "").split(",").map((item) => item.trim()).filter(Boolean);
          const domains = declaredDomains.length ? [...new Set(["tokens", "shell", ...declaredDomains])] : [];
          const profileActual = dataAttr(text, "design-profile-sha");
          const selected = {};
          for (const domain of domains) selected[domain] = (designContract.runtimeHashes || {})[domain] || runtimeExpected;
          const profileExpected = domains.length ? crypto.createHash("sha256").update(JSON.stringify(selected)).digest("hex") : "";
          const profileCurrent = profileActual && profileExpected && profileActual === profileExpected;
          if (!actual) {
            errors.push(`${relative}: product page missing data-design-source-sha; regenerate it from the current template or add the current DESIGN.md source hash`);
          } else if (expected && actual !== expected) {
            const message = `${relative}: data-design-source-sha does not match current DESIGN.md source hash`;
            if ((runtimeExpected && runtimeActual === runtimeExpected) || profileCurrent) warnings.push(`${message}; referenced design domains are unchanged`);
            else errors.push(message);
          }
          if (!runtimeActual) {
            errors.push(`${relative}: product page missing data-design-runtime-sha`);
          } else if (runtimeExpected && runtimeActual !== runtimeExpected) {
            if (profileCurrent) warnings.push(`${relative}: aggregate design runtime changed but the page design profile is current`);
            else errors.push(`${relative}: data-design-runtime-sha does not match rendered design contract or page design profile`);
          }
        }

        function checkGenerationMode(text, relative, placeholder) {
          if (placeholder || !releaseMode) return;
          const mode = dataAttr(text, "generation-mode");
          if (["scaffold", "incremental-baseline", "reconstruction-scaffold"].includes(mode)) {
            const completed = mode === "scaffold" ? "authored" : (mode === "incremental-baseline" ? "incremental-authored" : "reconstruction-authored");
            errors.push(`${relative}: generation mode ${mode} is an unfinished skeleton; author the real page and change it to ${completed}`);
          }
          if (!mode) errors.push(`${relative}: missing data-generation-mode`);
        }

        function checkRequiredPageMetadata(text, relative, isProductPage) {
          if (!isProductPage) return;
          const fidelityRules = checkRules.productFidelity || {};
          const required = Array.isArray(fidelityRules.requiredPageMetadata) ? fidelityRules.requiredPageMetadata : [];
          const legacyContract = Number(dataAttr(text, "design-contract-version") || 0) < 4;
          for (const attribute of required) {
            if (legacyContract && ["data-design-domains", "data-design-profile-sha"].includes(attribute)) {
              warnings.push(`${relative}: legacy contract page has conservative all-domain design dependency`);
              continue;
            }
            const name = String(attribute).replace(/^data-/, "");
            if (!dataAttr(text, name)) {
              errors.push(`${relative}: product page missing required ${attribute}`);
            }
          }
        }

        function checkPageTemplateContract(text, relative) {
          const templateId = dataAttr(text, "page-template");
          if (!templateId) return;
          const fidelityRules = checkRules.productFidelity || {};
          const allowed = Array.isArray(fidelityRules.pageTemplateIds) ? fidelityRules.pageTemplateIds : [];
          if (allowed.length > 0 && !allowed.includes(templateId)) {
            errors.push(`${relative}: data-page-template ${templateId} is not declared by DESIGN.md`);
          }
        }

        function checkRoleRequirements(text, relative, scope) {
          const fidelityRules = checkRules.productFidelity || {};
          const scopes = fidelityRules.roleRequirements || {};
          const requirements = scopes[scope] || {};
          for (const [role, candidates] of Object.entries(requirements)) {
            const classNames = Array.isArray(candidates) ? candidates.filter(Boolean) : [];
            if (classNames.length > 0 && !classNames.some((className) => hasClass(text, className))) {
              errors.push(`${relative}: missing DESIGN.md ${scope} role ${role}; expected one of ${classNames.join(", ")}`);
            }
          }
        }

        function sha256File(file) {
          return crypto.createHash("sha256").update(fs.readFileSync(file)).digest("hex");
        }

        function reviewRuntimeFiles(pageFile, sharedRefs = []) {
          const config = readProjectConfig();
          let files = [...(config.sharedCss || []), ...(config.sharedJs || [])];
          if (sharedRefs.length) {
            files = ["shared/css/tokens.css", "shared/css/product-shell.css", "shared/css/prototype-meta.css", "shared/js/product-icons.js", "shared/js/product-shell.js"];
            for (const ref of sharedRefs) {
              const [section, name] = String(ref).split(".", 2);
              const entry = sharedRegistry[section] && sharedRegistry[section][name];
              if (entry && Array.isArray(entry.files)) files.push(...entry.files);
            }
          }
          if (config.framework === "react") files.push("src/App.jsx");
          if (config.framework === "vue") files.push("src/App.vue");
          let current = path.dirname(pageFile);
          while (current.startsWith(root) && current !== root) {
            const assets = path.join(current, "assets");
            if (fs.existsSync(assets)) {
              for (const file of walk(assets)) files.push(rel(file));
              break;
            }
            current = path.dirname(current);
          }
          return files.filter((relative) => exists(relative)).sort();
        }

        function reviewRuntimeSha256(pageFile, sharedRefs = []) {
          const hash = crypto.createHash("sha256");
          for (const relative of [...new Set(reviewRuntimeFiles(pageFile, sharedRefs))]) {
            hash.update(relative);
            hash.update(fs.readFileSync(path.join(root, relative)));
          }
          return hash.digest("hex");
        }

        function verifyEvidence(entry, relative, label, jsonReport = false) {
          if (!entry || !entry.path || !entry.sha256) {
            errors.push(`${relative}: fidelity review missing ${label} evidence`);
            return;
          }
          const absolute = path.join(root, entry.path);
          if (!fs.existsSync(absolute) || !fs.statSync(absolute).isFile()) {
            errors.push(`${relative}: fidelity evidence file missing ${entry.path}`);
            return;
          }
          if (sha256File(absolute) !== entry.sha256) errors.push(`${relative}: fidelity evidence changed after review: ${entry.path}`);
          if (jsonReport) {
            try {
              const report = JSON.parse(fs.readFileSync(absolute, "utf8"));
              if (report.unchangedRegionsMatch !== true) errors.push(`${relative}: visual diff report does not approve unchanged regions`);
              if (report.generator !== "compare-prototype-screenshots.py") errors.push(`${relative}: visual diff report was not generated by the bundled pixel comparator`);
              for (const viewport of ["desktop", "mobile"]) {
                const metrics = report[viewport] || {};
                if (!(Number(metrics.comparedPixels) > 0) || !Number.isFinite(Number(metrics.diffRatio))) errors.push(`${relative}: visual diff report missing ${viewport} pixel metrics`);
                else if (Number(metrics.diffRatio) > Number(report.maxDiffRatio)) errors.push(`${relative}: visual diff ${viewport} ratio exceeds threshold`);
              }
            } catch (error) {
              errors.push(`${relative}: invalid visual diff report ${entry.path}: ${error.message}`);
            }
          }
        }

        function verifyViewportDimensions(entry, expected, relative, label) {
          if (!entry || !entry.path || !expected) return;
          const absolute = path.join(root, entry.path);
          if (!fs.existsSync(absolute)) return;
          const bytes = fs.readFileSync(absolute);
          if (bytes.length >= 24 && bytes.subarray(0, 8).equals(Buffer.from([137,80,78,71,13,10,26,10]))) {
            const width = bytes.readUInt32BE(16);
            const height = bytes.readUInt32BE(20);
            if (width !== Number(expected.width) || height !== Number(expected.height)) errors.push(`${relative}: ${label} screenshot ${width}x${height} does not match recorded viewport ${expected.width}x${expected.height}`);
          }
        }

        function incrementalContractFor(file) {
          let current = path.dirname(file);
          while (current.startsWith(root) && current !== root) {
            const candidate = path.join(current, "incremental-contract.json");
            if (fs.existsSync(candidate)) return candidate;
            current = path.dirname(current);
          }
          return null;
        }

        function reconstructionContractFor(file) {
          let current = path.dirname(file);
          while (current.startsWith(root) && current !== root) {
            const candidate = path.join(current, "reconstruction-contract.json");
            if (fs.existsSync(candidate)) return candidate;
            current = path.dirname(current);
          }
          return null;
        }

        function checkDesignGaps(pageKey, relative) {
          const gaps = designGaps && designGaps.gaps ? Object.values(designGaps.gaps) : [];
          for (const gap of gaps) {
            const pages = Array.isArray(gap.affectedPageKeys) ? gap.affectedPageKeys : [];
            const global = pages.length === 0 && ["shared", "design-system"].includes(gap.scope);
            if (!global && (!pageKey || !pages.includes(pageKey))) continue;
            const message = `${relative}: design gap ${gap.id} is ${gap.status} (${gap.classification || "unclassified"})`;
            if (releaseMode && ["confirmed", "applied"].includes(gap.status)) errors.push(message);
            else if (["observed", "classified", "confirmed", "applied"].includes(gap.status)) warnings.push(message);
          }
        }

        function checkFidelityReview(file, relative) {
          if (!releaseMode) return;
          const reviews = fidelityReviews && fidelityReviews.reviews ? fidelityReviews.reviews : {};
          const review = reviews[relative];
          if (!review || review.status !== "approved") {
            errors.push(`${relative}: missing approved fidelity review; inspect the layout profile's declared viewports and run scripts/record-fidelity-review.cjs`);
            return;
          }
          const sourceSha = recordedSourceSha();
          const reviewDomains = Array.isArray(review.designDomains) && review.designDomains.length ? review.designDomains : ["tokens", "shell", "components", "patterns", "rules"];
          const selectedHashes = {};
          for (const domain of reviewDomains) selectedHashes[domain] = (designContract.runtimeHashes || {})[domain] || recordedRuntimeSha();
          const currentProfileSha = crypto.createHash("sha256").update(JSON.stringify(selectedHashes)).digest("hex");
          const reviewProfileCurrent = review.designProfileSha256 && review.designProfileSha256 === currentProfileSha;
          if (sourceSha && review.designSourceSha256 !== sourceSha) {
            if ((recordedRuntimeSha() && review.designRuntimeSha256 === recordedRuntimeSha()) || reviewProfileCurrent) {
              warnings.push(`${relative}: fidelity review source changed but referenced design domains are unchanged`);
            } else {
              errors.push(`${relative}: fidelity review was recorded for a different DESIGN.md source`);
            }
          }
          if (review.fileSha256 !== sha256File(file)) {
            errors.push(`${relative}: page changed after fidelity review`);
          }
          if (review.runtimeSha256 !== reviewRuntimeSha256(file, Array.isArray(review.sharedRefs) ? review.sharedRefs : [])) {
            errors.push(`${relative}: shared CSS/JS or framework shell changed after fidelity review`);
          }
          const viewports = Array.isArray(review.viewports) ? review.viewports : [];
          const pageText = fs.readFileSync(file, "utf8");
          const profileId = dataAttr(pageText, "layout-profile");
          const profile = layoutContract.profiles && layoutContract.profiles[profileId];
          const requiredViewports = profile ? Object.keys(profile.viewports || {}) : (layoutContract.source === "legacy" ? ["desktop", "mobile"] : viewports);
          for (const required of requiredViewports) {
            if (!viewports.includes(required)) {
              errors.push(`${relative}: fidelity review missing ${required} viewport verification`);
            }
          }
          const evidence = review.evidence || {};
          const viewportEvidence = evidence.viewports || Object.fromEntries([["desktop",evidence.desktop],["mobile",evidence.mobile]].filter(([,value])=>value));
          const browserViewports = (review.browser && review.browser.viewports) || Object.fromEntries([["desktop",review.browser&&review.browser.desktop],["mobile",review.browser&&review.browser.mobile]].filter(([,value])=>value));
          for (const viewport of requiredViewports) {
            verifyEvidence(viewportEvidence[viewport], relative, `${viewport} screenshot`);
            verifyViewportDimensions(viewportEvidence[viewport], browserViewports[viewport], relative, viewport);
          }
          if (incrementalContractFor(file)) {
            const baselines = evidence.baselineViewports || Object.fromEntries([["desktop",evidence.baselineDesktop],["mobile",evidence.baselineMobile]].filter(([,value])=>value));
            for (const viewport of requiredViewports) verifyEvidence(baselines[viewport], relative, `baseline ${viewport} screenshot`);
            verifyEvidence(evidence.diffReport, relative, "visual diff report", true);
          }
          if (reconstructionContractFor(file)) {
            const references = evidence.referenceViewports || Object.fromEntries([["desktop",evidence.referenceDesktop],["mobile",evidence.referenceMobile]].filter(([,value])=>value));
            for (const viewport of requiredViewports) verifyEvidence(references[viewport], relative, `reference ${viewport} screenshot`);
            verifyEvidence(evidence.comparisonReport, relative, "reconstruction comparison report", true);
            try {
              const report = JSON.parse(fs.readFileSync(path.join(root, evidence.comparisonReport.path), "utf8"));
              if (report.mode !== "reconstruction") errors.push(`${relative}: reconstruction comparison report has wrong mode`);
            } catch (_) {}
            try {
              const contractFile = reconstructionContractFor(file);
              const reconstruction = JSON.parse(fs.readFileSync(contractFile, "utf8"));
              const target = path.relative(path.dirname(contractFile), file).replaceAll(path.sep, "/");
              const pageContract = (reconstruction.pages || []).find((page) => page.target === target);
              for (const ref of pageContract ? pageContract.evidenceRefs || [] : []) {
                const source = evidenceSources.sources && evidenceSources.sources[ref];
                if (!source) continue;
                for (const viewport of requiredViewports) if (source.viewports && source.viewports[viewport] && (!references[viewport] || source.viewports[viewport].sha256 !== references[viewport].sha256)) errors.push(`${relative}: reference ${viewport} does not match evidence source ${ref}`);
                if (source.browser && source.browser !== "unspecified" && review.browser && review.browser.name !== "unspecified" && source.browser !== review.browser.name) errors.push(`${relative}: reconstruction browser ${review.browser.name} does not match source browser ${source.browser}`);
              }
            } catch (error) {
              errors.push(`${relative}: cannot validate reconstruction evidence provenance: ${error.message}`);
            }
          }
        }

        function checkIncrementalContract(featureDir) {
          const contractFile = path.join(featureDir, "incremental-contract.json");
          if (!fs.existsSync(contractFile)) return;
          let contract;
          try { contract = JSON.parse(fs.readFileSync(contractFile, "utf8")); }
          catch (error) { errors.push(`${rel(contractFile)} is invalid JSON: ${error.message}`); return; }
          if (contract.mode !== "incremental" || !Array.isArray(contract.pages) || contract.pages.length === 0) {
            errors.push(`${rel(contractFile)} must declare incremental pages`);
            return;
          }
          if (!releaseMode) return;
          const allowed = new Set();
          for (const page of contract.pages) {
            const target = path.join(featureDir, page.target || "");
            const baseline = path.join(root, page.baseline || "");
            if (!Array.isArray(page.preserve) || page.preserve.length === 0) errors.push(`${rel(contractFile)}: ${page.pageKey} missing preserve rules`);
            const changeCount = ["add", "modify", "delete"].flatMap((key) => Array.isArray(page.changes && page.changes[key]) ? page.changes[key] : []).length;
            if (changeCount === 0) errors.push(`${rel(contractFile)}: ${page.pageKey} missing declared changes`);
            if (!fs.existsSync(baseline) || sha256File(baseline) !== page.baselineSha256) errors.push(`${rel(contractFile)}: baseline changed or is missing for ${page.pageKey}`);
            for (const [supportingPath, supportingSha] of Object.entries(page.baselineSupportingFiles || {})) {
              const supportingFile = path.join(root, supportingPath);
              if (!fs.existsSync(supportingFile) || sha256File(supportingFile) !== supportingSha) errors.push(`${rel(contractFile)}: baseline supporting file changed or is missing: ${supportingPath}`);
            }
            if (!fs.existsSync(target)) errors.push(`${rel(contractFile)}: target missing for ${page.pageKey}`);
            else if (sha256File(target) === page.preparedSha256) errors.push(`${rel(target)}: incremental baseline was never authored`);
            for (const file of page.allowedFiles || []) allowed.add(file);
          }
          const prepared = contract.preparedFiles || {};
          const currentFiles = walk(featureDir).filter((file) => path.basename(file) !== "incremental-contract.json" && !rel(file).includes("/fidelity-evidence/"));
          for (const file of currentFiles) {
            const relative = path.relative(featureDir, file).replaceAll(path.sep, "/");
            const before = prepared[relative];
            const changed = !before || sha256File(file) !== before;
            if (changed && !allowed.has(relative)) errors.push(`${rel(file)} changed outside incremental allowedFiles`);
          }
          for (const [relative, before] of Object.entries(prepared)) {
            const file = path.join(featureDir, relative);
            if (!fs.existsSync(file) && !allowed.has(relative)) errors.push(`${rel(file)} was deleted outside incremental allowedFiles`);
          }
        }

        function checkReconstructionContract(featureDir) {
          const contractFile = path.join(featureDir, "reconstruction-contract.json");
          if (!fs.existsSync(contractFile)) return;
          let contract;
          try { contract = JSON.parse(fs.readFileSync(contractFile, "utf8")); }
          catch (error) { errors.push(`${rel(contractFile)} is invalid JSON: ${error.message}`); return; }
          if (contract.mode !== "reconstruction" || !Array.isArray(contract.pages) || contract.pages.length === 0) {
            errors.push(`${rel(contractFile)} must declare reconstruction pages`);
            return;
          }
          const sources = evidenceSources && evidenceSources.sources ? evidenceSources.sources : {};
          for (const page of contract.pages) {
            if (!Array.isArray(page.evidenceRefs) || page.evidenceRefs.length === 0) errors.push(`${rel(contractFile)}: ${page.pageKey} missing evidenceRefs`);
            for (const ref of page.evidenceRefs || []) if (!sources[ref]) errors.push(`${rel(contractFile)}: unknown evidence source ${ref}`);
            if (releaseMode) {
              const target = path.join(featureDir, page.target || "");
              if (!fs.existsSync(target)) errors.push(`${rel(contractFile)}: target missing for ${page.pageKey}`);
            }
          }
        }

        function checkFrameworkProject(framework) {
          const required = [
            "package.json",
            "index.html",
            "vite.config.js",
            "src/prototype-registry.js",
            "src/styles.css",
            framework === "react" ? "src/main.jsx" : "src/main.js",
            framework === "react" ? "src/App.jsx" : "src/App.vue",
          ];
          for (const file of required) {
            if (!exists(file)) errors.push(`missing ${framework} project file ${file}`);
          }

          const packagePath = path.join(root, "package.json");
          if (fs.existsSync(packagePath)) {
            try {
              const pkg = JSON.parse(fs.readFileSync(packagePath, "utf8"));
              const deps = { ...(pkg.dependencies || {}), ...(pkg.devDependencies || {}) };
              if (!deps.vite) warnings.push("package.json does not list vite");
              if (framework === "react" && (!deps.react || !deps["react-dom"])) {
                errors.push("package.json missing react/react-dom dependencies");
              }
              if (framework === "vue" && !deps.vue) {
                errors.push("package.json missing vue dependency");
              }
            } catch (error) {
              errors.push(`package.json is invalid JSON: ${error.message}`);
            }
          }

          const entry = framework === "react" ? "src/main.jsx" : "src/main.js";
          const entryPath = path.join(root, entry);
          if (fs.existsSync(entryPath)) {
            const entryText = fs.readFileSync(entryPath, "utf8");
            for (const css of sharedCss) {
              if (!entryText.includes(`../${css}`)) {
                errors.push(`${entry}: missing shared stylesheet import ../${css}`);
              }
            }
            for (const js of ["shared/js/product-icons.js", "shared/js/product-shell.js"]) {
              if (!entryText.includes(`../${js}`)) {
                errors.push(`${entry}: missing shared script import ../${js}`);
              }
            }
          }

          const appEntry = framework === "react" ? "src/App.jsx" : "src/App.vue";
          const appPath = path.join(root, appEntry);
          if (fs.existsSync(appPath)) {
            const appText = fs.readFileSync(appPath, "utf8");
            checkRoleRequirements(appText, appEntry, "projectShell");
          }

          const indexText = exists("index.html") ? fs.readFileSync(path.join(root, "index.html"), "utf8") : "";
          const expectedEntry = framework === "react" ? "/src/main.jsx" : "/src/main.js";
          if (indexText && !indexText.includes(expectedEntry)) {
            errors.push(`index.html: missing Vite entry ${expectedEntry}`);
          }

          const registryPath = path.join(root, "src", "prototype-registry.js");
          const registry = fs.existsSync(registryPath) ? fs.readFileSync(registryPath, "utf8") : "";
          if (registry && (!registry.includes("// IMPORTS_START") || !registry.includes("// FEATURES_START"))) {
            errors.push("src/prototype-registry.js missing generated registry markers");
          }
          if (registry) {
            const pageKeys = [...registry.matchAll(/\bpageKey:\s*"([^"]+)"/g)].map((match) => match[1]);
            const seenPageKeys = new Set();
            for (const pageKey of pageKeys) {
              if (seenPageKeys.has(pageKey)) errors.push(`src/prototype-registry.js: duplicate pageKey ${pageKey}`);
              seenPageKeys.add(pageKey);
            }
            if (registry.includes("kind: \"scenario\"")) {
              const scenarioEntries = [...registry.matchAll(/\{[^{}]*kind:\s*"scenario"[^{}]*\}/g)];
              for (const [index, match] of scenarioEntries.entries()) {
                const entry = match[0];
                if (!/\bparentPageKey:\s*"[^"]+"/.test(entry)) {
                  errors.push(`src/prototype-registry.js: scenario entry ${index + 1} missing parentPageKey`);
                }
                if (!/\bsurface:\s*"(drawer|modal|side-panel|confirm)"/.test(entry)) {
                  errors.push(`src/prototype-registry.js: scenario entry ${index + 1} must use drawer, modal, side-panel, or confirm surface`);
                }
              }
            }
          }

          const featureRoot = path.join(root, "src", "features");
          if (!fs.existsSync(featureRoot)) {
            warnings.push("No src/features folder found yet.");
            return;
          }
          const featureDirs = fs.readdirSync(featureRoot, { withFileTypes: true })
            .filter((entry) => entry.isDirectory())
            .map((entry) => entry.name)
            .sort();
          const badFeatureDirs = featureDirs.filter((name) => !/^\d{2}-[a-z0-9-]+$/.test(name));
          for (const name of badFeatureDirs) {
            errors.push(`src/features/${name}: feature folder must use two digits, lowercase letters, numbers, and hyphens`);
          }
          const validFeatureDirs = featureDirs.filter((name) => /^\d{2}-[a-z0-9-]+$/.test(name));
          if (validFeatureDirs.length === 0) {
            warnings.push("No numbered framework feature folders found yet.");
          }

          const componentExt = framework === "react" ? ".jsx" : ".vue";
          for (const dir of validFeatureDirs) {
            checkIncrementalContract(path.join(featureRoot, dir));
            checkReconstructionContract(path.join(featureRoot, dir));
            if (registry && !registry.includes(`slug: "${dir}"`)) {
              errors.push(`src/prototype-registry.js: missing feature registration for ${dir}`);
            }
            const componentFiles = walk(path.join(featureRoot, dir)).filter((file) => file.endsWith(componentExt));
            if (componentFiles.length === 0) {
              errors.push(`src/features/${dir}: missing ${componentExt} page component`);
            }
            for (const file of componentFiles) {
              const relative = rel(file);
              const text = fs.readFileSync(file, "utf8");
              const placeholder = isPlaceholder(text);
              if (releaseMode && (text.includes("data-authoring-pending") || text.includes('data-authoring-slot="pending"'))) errors.push(`${relative}: pending authoring slot cannot be released`);
              checkGenerationMode(text, relative, placeholder);
              if (!/[\u4e00-\u9fff]/.test(text)) {
                warnings.push(`${relative}: component text does not appear to contain Chinese copy`);
              }
              if (/(href|src)=["']file:\/\//i.test(text) || /(href|src)=["']\/Users\//i.test(text)) {
                errors.push(`${relative}: contains local absolute file link`);
              }
              if (/(href|src)=["']\/(?!\/)/i.test(text)) {
                warnings.push(`${relative}: contains root-absolute path; prefer relative paths or app routes`);
              }
              if (placeholder) reportPlaceholder(relative);
              checkLocalIconRuntime(text, relative, false);
              checkRequiredPageMetadata(text, relative, true);
              checkDesignSourceAnchor(text, relative, true);
              if (!placeholder) {
                checkProductRoles(text, relative);
                checkPageTemplateContract(text, relative);
                if (/data-page-template=["'](filter-table-list|table-list|admin-list|list)["']/.test(text)) {
                  checkRoleRequirements(text, relative, "listPage");
                }
                checkDesignFingerprints(text, relative);
              }
              const colors = rawColorMatches(text.replace(/\/\*[\s\S]*?\*\//g, ""));
              if (colors.length > 0) {
                warnings.push(`${relative}: raw colors found (${[...new Set(colors)].join(", ")}); prefer shared CSS variables for new work`);
              }
              checkDisallowedDesignValues(text, relative, "component");
              if (!placeholder) {
                checkMessageCopy(text, relative);
                checkFidelityReview(file, relative);
              }
              const pageKey = dataAttr(text, "page-key");
              checkDesignGaps(pageKey, relative);
              const pageKind = dataAttr(text, "page-kind");
              const parentPageKey = dataAttr(text, "parent-page-key");
              const surface = dataAttr(text, "surface");
              if (!pageKey) {
                warnings.push(`${relative}: missing data-page-key; add a stable pageKey for prototype-spec-annotator`);
              }
              if (pageKind === "scenario" && !placeholder) {
                if (!parentPageKey) errors.push(`${relative}: scenario component missing data-parent-page-key`);
                if (!["drawer", "modal", "side-panel", "confirm"].includes(surface)) {
                  errors.push(`${relative}: scenario component must set data-surface to drawer, modal, side-panel, or confirm`);
                }
                if (!/(drawer-panel|confirm-dialog)/.test(text)) {
                  errors.push(`${relative}: scenario component missing visible drawer/modal/confirm surface`);
                }
              }
            }
          }
        }

        for (const required of ["DESIGN.md", "AGENTS.md", "index.html", "docs/prototype-workflows.md", "design-system/context-index.json", "design-system/authoring-context.json", "design-system/design-contract.json", "design-system/design-readiness.json", "design-system/layout-model.json", "design-system/layout-contract.json", "design-system/preview-manifest.json", "design-system/layout-audit.html", "design-system/design-change-plan.json", "design-system/check-rules.json", "design-system/fidelity-guardrails.json", "design-system/fidelity-reviews.json", "design-system/evidence-sources.json", "design-system/design-gaps.json", "design-system/shared-registry.json", "design-system/authoring-status.json", "design-system/authoring-brief.md"]) {
          if (!exists(required)) errors.push(`missing required file ${required}`);
        }

        const sharedCss = [
          "shared/css/tokens.css",
          "shared/css/product-shell.css",
          "shared/css/product-components.css",
          "shared/css/product-patterns.css",
          "shared/css/prototype-meta.css",
        ];
        for (const file of sharedCss) {
          if (!exists(file)) errors.push(`missing shared stylesheet ${file}`);
        }
        if (!exists("shared/js/product-icons.js")) errors.push("missing product icon script shared/js/product-icons.js");
        if (!exists("shared/js/product-shell.js")) errors.push("missing product shell script shared/js/product-shell.js");

        const designContract = readJson("design-system/design-contract.json", null);
        const checkRules = readJson("design-system/check-rules.json", {});
        const fidelityGuardrails = readJson("design-system/fidelity-guardrails.json", {});
        const layoutContract = readJson("design-system/layout-contract.json", { source: "legacy", profiles: {} });
        const fidelityReviews = readJson("design-system/fidelity-reviews.json", { reviews: {} });
        const sharedRegistry = readJson("design-system/shared-registry.json", {});
        const evidenceSources = readJson("design-system/evidence-sources.json", { sources: {} });
        const designGaps = readJson("design-system/design-gaps.json", { gaps: {} });
        checkGuardrailsSource();
        if (releaseMode && fidelityReviews.designSourceSha256 && fidelityReviews.designSourceSha256 !== recordedSourceSha()) {
          if (fidelityReviews.designRuntimeSha256 === recordedRuntimeSha()) warnings.push("fidelity review ledger source changed but rendered design runtime is unchanged");
          else warnings.push("fidelity review ledger source changed; page-level design profiles determine which reviews must be repeated");
        }

        if (exists("DESIGN.md") && exists("design-system/design-contract.json")) {
          const designText = fs.readFileSync(path.join(root, "DESIGN.md"), "utf8");
          const actualHash = crypto.createHash("sha256").update(designText).digest("hex");
          const recordedHash = designContract && (designContract.sourceSha256 || (designContract.meta && designContract.meta.sourceSha256));
          if (recordedHash && recordedHash !== actualHash) {
            errors.push("design-system/design-contract.json sourceSha256 does not match DESIGN.md");
          }
        }

        const config = readProjectConfig();
        const authoringStatus = readJson("design-system/authoring-status.json", {});
        if (config.authoringMode === "llm") {
          if (authoringStatus.status !== "ready") {
            errors.push("LLM-authored shared design system is not finalized; run node scripts/finalize-design-system.cjs after authoring shared assets");
          }
          if (authoringStatus.designSourceSha256 && authoringStatus.designSourceSha256 !== recordedSourceSha()) {
            if (authoringStatus.designRuntimeSha256 === recordedRuntimeSha()) warnings.push("design-system authoring source changed but rendered design runtime is unchanged");
            else errors.push("design-system/authoring-status.json belongs to a different DESIGN.md source; reconcile and finalize shared assets again");
          }
          if (authoringStatus.designRuntimeSha256 && authoringStatus.designRuntimeSha256 !== recordedRuntimeSha()) {
            errors.push("design-system/authoring-status.json belongs to a different rendered design runtime");
          }
          const evidencePages = Object.values((authoringStatus.visualEvidence && authoringStatus.visualEvidence.pages) || {});
          if (!evidencePages.length) errors.push("design-system authoring has no layout-audited representative page evidence");
          for (const page of evidencePages) {
            const entries = Object.entries(page.viewports || {});
            if (!entries.length) errors.push(`design-system authoring has no viewport evidence for ${page.page || "representative page"}`);
            for (const [viewport, entry] of entries) {
              if (!entry || !entry.path || !entry.sha256 || !exists(entry.path)) errors.push(`design-system authoring is missing ${viewport} browser screenshot evidence for ${page.page || "representative page"}`);
              else if (sha256File(path.join(root, entry.path)) !== entry.sha256) errors.push(`design-system ${viewport} screenshot evidence changed after finalization`);
            }
          }
          for (const evidence of [authoringStatus.manifest, authoringStatus.layoutReport]) {
            if (!evidence || !evidence.path || !evidence.sha256 || !exists(evidence.path)) errors.push("design-system authoring is missing bound manifest/layout report evidence");
            else if (sha256File(path.join(root, evidence.path)) !== evidence.sha256) errors.push(`design-system evidence changed after finalization: ${evidence.path}`);
          }
        }
        const framework = config.framework === "react" || config.framework === "vue" ? config.framework : "html";
        if (framework === "react" || framework === "vue") {
          checkFrameworkProject(framework);
          for (const warning of warnings) console.warn(`WARN ${warning}`);
          for (const error of errors) console.error(`ERROR ${error}`);
          if (errors.length > 0) {
            process.exit(1);
          }
          console.log(`Prototype compliance check passed for ${framework}${releaseMode ? " in release mode" : ""} with ${warnings.length} warning(s).`);
          process.exit(0);
        }

        const topDirs = fs.readdirSync(root, { withFileTypes: true })
          .filter((entry) => entry.isDirectory())
          .map((entry) => entry.name)
          .filter((name) => !ignoredDirs.has(name) && !name.startsWith("."));

        const badFeatureDirs = topDirs.filter((name) => /^\d{2}-/.test(name) && !/^\d{2}-[a-z0-9-]+$/.test(name));
        for (const name of badFeatureDirs) {
          errors.push(`${name}: feature folder must use two digits, lowercase letters, numbers, and hyphens`);
        }

        const featureDirs = topDirs.filter((name) => /^\d{2}-[a-z0-9-]+$/.test(name)).sort();
        if (featureDirs.length === 0) {
          warnings.push("No numbered feature folders found yet.");
        }

        const rootIndex = exists("index.html") ? fs.readFileSync(path.join(root, "index.html"), "utf8") : "";
        const htmlPageKeys = new Map();
        for (const dir of featureDirs) {
          checkIncrementalContract(path.join(root, dir));
          checkReconstructionContract(path.join(root, dir));
          const featureIndexPath = path.join(root, dir, "index.html");
          if (!fs.existsSync(featureIndexPath)) {
            errors.push(`${dir}: missing feature index.html`);
            continue;
          }
          const featureIndex = fs.readFileSync(featureIndexPath, "utf8");
          if (!rootIndex.includes(`./${dir}/index.html`) && !rootIndex.includes(`${dir}/index.html`)) {
            errors.push(`index.html: missing root link to ${dir}/index.html`);
          }
          for (const requiredText of ["更新时间", "所属迭代"]) {
            if (!featureIndex.includes(requiredText)) {
              errors.push(`${dir}/index.html: missing ${requiredText}`);
            }
          }
          if (!featureIndex.includes("../index.html")) {
            errors.push(`${dir}/index.html: missing return link to ../index.html`);
          }

          const htmlFiles = walk(path.join(root, dir)).filter((file) => file.endsWith(".html"));
          for (const file of htmlFiles) {
            const relative = rel(file);
            const text = fs.readFileSync(file, "utf8");
            const visible = stripHtml(text);
            if (visible && !/[\u4e00-\u9fff]/.test(visible)) {
              warnings.push(`${relative}: visible text does not appear to contain Chinese copy`);
            }
            const missingSharedCss = sharedCss
              .map((css) => "../" + css)
              .filter((expected) => !text.includes(expected));
            if (missingSharedCss.length > 0) {
              warnings.push(`${relative}: legacy page missing shared stylesheet(s): ${missingSharedCss.join(", ")}`);
            }
            if (/(href|src)=["']file:\/\//i.test(text) || /(href|src)=["']\/Users\//i.test(text)) {
              errors.push(`${relative}: contains local absolute file link`);
            }
            if (/(href|src)=["']\/(?!\/)/i.test(text)) {
              warnings.push(`${relative}: contains root-absolute path; prefer relative paths`);
            }
            const hasShellRoot = hasClass(text, shellClasses.root_base);
            const isActualProductPage = Boolean(text.includes("data-page-key") || hasShellRoot);
            const placeholder = isPlaceholder(text);
            if (releaseMode && (text.includes("data-authoring-pending") || text.includes('data-authoring-slot="pending"'))) errors.push(`${relative}: pending authoring slot cannot be released`);
            if (isActualProductPage && missingSharedCss.length > 0) {
              errors.push(`${relative}: product page missing shared stylesheet(s): ${missingSharedCss.join(", ")}`);
            }
            if (placeholder) reportPlaceholder(relative);
            if (isActualProductPage) checkGenerationMode(text, relative, placeholder);
            checkLocalIconRuntime(text, relative, isActualProductPage);
            checkRequiredPageMetadata(text, relative, isActualProductPage);
            checkDesignSourceAnchor(text, relative, isActualProductPage);
            if (isActualProductPage && !placeholder) {
              checkProductRoles(text, relative);
              checkPageTemplateContract(text, relative);
              checkRoleRequirements(text, relative, "projectShell");
              if (/data-page-template=["'](filter-table-list|table-list|admin-list|list)["']/.test(text)) {
                checkRoleRequirements(text, relative, "listPage");
              }
              checkDesignFingerprints(text, relative);
            }
            if (!placeholder) checkMessageCopy(text, relative);
            if (isActualProductPage && !placeholder) checkFidelityReview(file, relative);
            if (text.includes("proto-app-shell")) {
              errors.push(`${relative}: product prototype pages must use product shell classes instead of proto-app-shell`);
            }
            if (hasShellRoot || text.includes("data-page-key")) {
              const pageKey = dataAttr(text, "page-key");
              checkDesignGaps(pageKey, relative);
              const pageKind = dataAttr(text, "page-kind");
              const parentPageKey = dataAttr(text, "parent-page-key");
              const surface = dataAttr(text, "surface");
              if (!pageKey) {
                warnings.push(`${relative}: missing data-page-key; add a stable pageKey for prototype-spec-annotator`);
              } else if (htmlPageKeys.has(pageKey)) {
                errors.push(`${relative}: duplicate data-page-key ${pageKey}; already used by ${htmlPageKeys.get(pageKey)}`);
              } else {
                htmlPageKeys.set(pageKey, relative);
              }
              if (pageKind === "scenario" && !placeholder) {
                if (!parentPageKey) errors.push(`${relative}: scenario page missing data-parent-page-key`);
                if (!["drawer", "modal", "side-panel", "confirm"].includes(surface)) {
                  errors.push(`${relative}: scenario page must set data-surface to drawer, modal, side-panel, or confirm`);
                }
                if (!/(drawer-panel|confirm-dialog)/.test(text)) {
                  errors.push(`${relative}: scenario page missing visible product drawer/confirm surface`);
                }
              }
            }

            const shellCandidates = [shellClasses.root_base, shellClasses.main, shellClasses.panel, "app-shell", "app-layout", "main-layout", "page-shell"];
            if (relative.endsWith("index.html") === false && !shellCandidates.some((candidate) => candidate && hasClass(text, candidate))) {
              warnings.push(`${relative}: product page should use product shell classes from DESIGN.md or the starter's generic product shell roles`);
            }
            const hasConfiguredListShape = text.includes(shellClasses.filter) && text.includes(shellClasses.section_header) && /(data-table|grid-table|<table\b)/.test(text);
            if (!placeholder && /data-page-template=["']filter-table-list["']/.test(text) && !hasConfiguredListShape && !/(filter-bar|search-bar).*(section-heading|list-toolbar).*(data-table|grid-table|<table\b)/s.test(text)) {
              errors.push(`${relative}: filter-table-list page must include search, toolbar/title, and table product roles`);
            }

            const styleBlocks = text.match(/<style[\s\S]*?<\/style>/gi) || [];
            const styleAttrs = text.match(/\sstyle\s*=\s*["'][^"']*["']/gi) || [];
            const inlineColors = rawColorMatches(styleBlocks.join("\n") + "\n" + styleAttrs.join("\n"));
            if (inlineColors.length > 0) {
              warnings.push(`${relative}: raw colors found in inline styles (${[...new Set(inlineColors)].join(", ")}); prefer shared CSS variables for new work`);
            }
            checkDisallowedDesignValues(styleBlocks.join("\n") + "\n" + styleAttrs.join("\n"), relative, "inline style");
          }

          const localCssFiles = walk(path.join(root, dir)).filter((file) => file.endsWith(".css"));
          for (const file of localCssFiles) {
            const relative = rel(file);
            const css = fs.readFileSync(file, "utf8").replace(/\/\*[\s\S]*?\*\//g, "");
            const colors = rawColorMatches(css);
            if (colors.length > 0) {
              warnings.push(`${relative}: legacy/local raw colors found (${[...new Set(colors)].join(", ")}); prefer shared CSS variables for new work`);
            }
            checkDisallowedDesignValues(css, relative, "local CSS");
          }
        }

        for (const warning of warnings) console.warn(`WARN ${warning}`);
        for (const error of errors) console.error(`ERROR ${error}`);

        if (errors.length > 0) {
          process.exit(1);
        }
        console.log(`Prototype compliance check passed${releaseMode ? " in release mode" : ""} with ${warnings.length} warning(s).`);
        """
    )
    return script.replace("__SHELL_CLASSES_JSON__", json.dumps(shell_classes(design), ensure_ascii=False, indent=2))


def validate_design(design: dict[str, Any]) -> list[str]:
    warnings = []
    for key in ("tokens", "layout", "components", "pageTemplates", "generationRules"):
        if key not in design or design.get(key) in ({}, [], None, ""):
            warnings.append(f"DESIGN.md front matter is missing or has empty `{key}`")
    return warnings


def validate_design_schema(design: dict[str, Any]) -> tuple[list[str], list[str]]:
    errors: list[str] = []
    warnings: list[str] = []
    expected_types: dict[str, type] = {
        "tokens": dict,
        "layout": dict,
        "components": dict,
        "pageTemplates": list,
        "generationRules": dict,
    }
    for key, expected_type in expected_types.items():
        value = design.get(key)
        if value in ({}, [], None, ""):
            if not (is_layout_v2(design) and key in {"tokens", "components"} and isinstance(value, expected_type)):
                warnings.append(f"DESIGN.md front matter is missing or has empty `{key}`")
            continue
        if not isinstance(value, expected_type):
            errors.append(f"DESIGN.md front matter field `{key}` must be {expected_type.__name__}")

    optional_types: dict[str, tuple[type, ...]] = {
        "copywriting": (dict,),
        "legacyTokens": (dict,),
        "knownLimits": (dict, list),
        "assumptions": (list, dict),
    }
    for key, expected in optional_types.items():
        if key in design and not isinstance(design[key], expected):
            type_names = " or ".join(item.__name__ for item in expected)
            errors.append(f"DESIGN.md front matter field `{key}` must be {type_names} when present")
    return errors, warnings


def backup_existing_file(path: Path) -> str:
    if WRITE_BACKUP_DIR is None or not path.exists() or not path.is_file():
        return ""
    try:
        source_root = WRITE_BACKUP_SOURCE_ROOT or Path.cwd()
        relative = path.resolve().relative_to(source_root.resolve())
    except ValueError:
        relative = Path(path.name)
    backup_path = WRITE_BACKUP_DIR / relative
    backup_path.parent.mkdir(parents=True, exist_ok=True)
    shutil.copy2(path, backup_path)
    return f" backed up to {backup_path}"


def write_file(path: Path, content: str, *, force: bool, executable: bool = False) -> str:
    if path.exists() and not force:
        return f"skipped existing {path}"
    action = "overwrite" if path.exists() else "write"
    if WRITE_PLAN_ONLY:
        return f"would {action} {path}"
    path.parent.mkdir(parents=True, exist_ok=True)
    backup_note = backup_existing_file(path) if path.exists() and force else ""
    path.write_text(content, encoding="utf-8")
    if executable:
        path.chmod(0o755)
    return f"wrote {path}{backup_note}"


def copy_file(source: Path, target: Path, *, force: bool, executable: bool = False) -> str:
    if target.exists() and not force:
        return f"skipped existing {target}"
    action = "overwrite" if target.exists() else "copy"
    if WRITE_PLAN_ONLY:
        return f"would {action} {source} -> {target}"
    target.parent.mkdir(parents=True, exist_ok=True)
    backup_note = backup_existing_file(target) if target.exists() and force else ""
    shutil.copyfile(source, target)
    if executable:
        target.chmod(0o755)
    return f"copied {source} -> {target}{backup_note}"


def build_project(args: argparse.Namespace) -> int:
    global WRITE_PLAN_ONLY, WRITE_BACKUP_DIR, WRITE_BACKUP_SOURCE_ROOT

    WRITE_PLAN_ONLY = bool(args.plan_only)
    design_path = Path(args.design_md).expanduser().resolve()
    output = Path(args.output).expanduser().resolve()
    WRITE_BACKUP_DIR = (output / ".prototype-starter-backups" / _dt.datetime.now().strftime("%Y%m%d-%H%M%S")) if args.backup_managed else None
    WRITE_BACKUP_SOURCE_ROOT = output
    if not design_path.exists():
        raise SystemExit(f"Design file does not exist: {design_path}")

    design, design_text, source_hash = load_design(design_path)
    schema_errors, warnings = validate_design_schema(design)
    if schema_errors:
        for error in schema_errors:
            print(f"ERROR {error}", file=sys.stderr)
        return 1
    readiness = validate_design_readiness(design)
    if readiness["status"] != "ready":
        print(format_readiness_text(readiness), file=sys.stderr)
        print("Initialization blocked before creating or updating the output directory.", file=sys.stderr)
        return 2
    if args.strict:
        print("INFO --strict is retained as a compatibility alias; readiness validation is now always strict.", file=sys.stderr)
    project_name = args.name or str(design.get("name") or output.name)
    framework = normalize_framework(args.framework) if args.framework else "html"
    authoring_mode = "deterministic" if args.deterministic_shared else "llm"
    generated_at = _dt.datetime.now(_dt.timezone.utc).isoformat()
    skill_dir = Path(__file__).resolve().parents[1]
    runtime_hash = design_runtime_sha256(design, design_text)
    runtime_hashes = design_runtime_hashes(design, design_text)
    layout_model = normalize_layout_model(design)
    replacements = template_replacements(design, project_name, framework, source_hash, runtime_hash)
    preview_pages = render_representative_previews(skill_dir, design, project_name, framework, source_hash, runtime_hash, layout_model=layout_model)
    preview_manifest = render_preview_manifest(preview_pages, design, framework, layout_model=layout_model)

    previous_contract_path = output / "design-system" / "design-contract.json"
    try:
        previous_contract = json.loads(previous_contract_path.read_text(encoding="utf-8"))
    except (OSError, json.JSONDecodeError):
        previous_contract = {}

    contract = build_design_contract(
        design,
        source_path=design_path,
        source_hash=source_hash,
        generated_at=generated_at,
        project_name=project_name,
        source_text=design_text,
    )
    contract["prototypeFramework"] = framework
    contract["runtimeHashes"] = runtime_hashes
    check_rules = build_check_rules(design, design_text)
    add_fidelity_role_rules(check_rules, design)
    change_plan_text, changed_domains, affected_pages = render_design_change_plan(
        previous_contract,
        contract,
        output / "design-system" / "fidelity-reviews.json",
        output / "design-system" / "shared-registry.json",
        generated_at,
    )

    if not args.plan_only:
        output.mkdir(parents=True, exist_ok=True)
    actions = [
        write_file(output / "DESIGN.md", design_text, force=args.force),
        write_file(output / "AGENTS.md", render_template(skill_dir, "AGENTS.template.md", replacements), force=args.force),
        write_file(output / "design-system" / "design-contract.json", contract_json(contract), force=args.force),
        write_file(output / "design-system" / "design-readiness.json", json.dumps(readiness, ensure_ascii=False, indent=2) + "\n", force=args.force),
        write_file(output / "design-system" / "layout-model.json", json.dumps(layout_model, ensure_ascii=False, indent=2) + "\n", force=args.force),
        write_file(output / "design-system" / "authoring-context.json", render_authoring_context(design, source_hash, runtime_hash), force=args.force),
        write_file(output / "design-system" / "layout-contract.json", render_layout_contract(design, source_hash, runtime_hash, layout_model=layout_model), force=args.force),
        write_file(output / "design-system" / "preview-manifest.json", preview_manifest, force=False),
        write_file(output / "design-system" / "layout-audit.html", render_layout_audit_html(), force=args.force),
        write_file(output / "design-system" / "preview" / "index.html", render_preview_launcher(preview_pages, design), force=False),
        write_file(output / "design-system" / "design-change-plan.json", change_plan_text, force=args.force),
        write_file(output / "design-system" / "check-rules.json", check_rules_json(check_rules), force=args.force),
        write_file(output / "design-system" / "prototype-config.json", render_prototype_config(framework, project_name, authoring_mode), force=args.force),
        write_file(output / "design-system" / "context-index.json", render_context_index(design, source_hash=source_hash, runtime_hash=runtime_hash, framework=framework, check_rules=check_rules, runtime_hashes=runtime_hashes), force=args.force),
        write_file(output / "design-system" / "fidelity-guardrails.json", render_fidelity_guardrails(design, source_hash=source_hash, runtime_hash=runtime_hash, framework=framework, check_rules=check_rules), force=args.force),
        write_file(output / "design-system" / "fidelity-reviews.json", render_fidelity_reviews(source_hash, runtime_hash), force=False),
        write_file(output / "design-system" / "evidence-sources.json", render_persistent_ledger(output / "design-system" / "evidence-sources.json", "sources"), force=False),
        write_file(output / "design-system" / "design-gaps.json", render_persistent_ledger(output / "design-system" / "design-gaps.json", "gaps"), force=False),
        write_file(output / "design-system" / "shared-registry.json", render_shared_registry(source_hash, output / "design-system" / "shared-registry.json"), force=args.force),
        write_file(output / "design-system" / "authoring-status.json", render_authoring_status(source_hash, runtime_hash, authoring_mode, output / "design-system" / "authoring-status.json"), force=args.force),
        write_file(output / "design-system" / "authoring-brief.md", render_authoring_brief(project_name, framework, source_hash), force=args.force),
        write_file(output / "shared" / "css" / "tokens.css", render_tokens_css(design, source_hash), force=args.force if authoring_mode == "deterministic" else False),
        write_file(output / "shared" / "css" / "product-shell.css", render_universal_layout_css(design, layout_model) if is_layout_v2(design) else render_layout_css(design), force=args.force if authoring_mode == "deterministic" else False),
        write_file(output / "shared" / "css" / "product-components.css", render_universal_components_css(design) if is_layout_v2(design) else render_components_css(design), force=args.force if authoring_mode == "deterministic" else False),
        write_file(output / "shared" / "css" / "product-patterns.css", render_universal_patterns_css(design) if is_layout_v2(design) else render_patterns_css(design), force=args.force if authoring_mode == "deterministic" else False),
        write_file(output / "shared" / "css" / "prototype-meta.css", render_prototype_meta_css(design), force=args.force if authoring_mode == "deterministic" else False),
        write_file(output / "shared" / "js" / "product-icons.js", render_product_icons_js(), force=args.force if authoring_mode == "deterministic" else False),
        write_file(output / "shared" / "js" / "product-shell.js", render_universal_shell_js() if is_layout_v2(design) else render_product_shell_js(design), force=args.force if authoring_mode == "deterministic" else False),
        write_file(output / "shared" / "images" / ".gitkeep", "", force=args.force),
        write_file(output / "scripts" / "new-feature.cjs", new_feature_script(design, source_hash, runtime_hash), force=args.force, executable=True),
        write_file(output / "scripts" / "check-prototype-compliance.cjs", compliance_script(design), force=args.force, executable=True),
        write_file(output / "scripts" / "record-fidelity-review.cjs", record_fidelity_review_script(), force=args.force, executable=True),
        write_file(output / "scripts" / "finalize-design-system.cjs", finalize_design_system_script(), force=args.force, executable=True),
        write_file(output / "scripts" / "prepare-layout-audit.cjs", prepare_layout_audit_script(), force=args.force, executable=True),
        write_file(output / "scripts" / "manage-shared-registry.cjs", manage_shared_registry_script(), force=args.force, executable=True),
        copy_file(skill_dir / "scripts" / "manage_evidence_sources.cjs", output / "scripts" / "manage-evidence-sources.cjs", force=args.force, executable=True),
        copy_file(skill_dir / "scripts" / "manage_design_gaps.cjs", output / "scripts" / "manage-design-gaps.cjs", force=args.force, executable=True),
        copy_file(skill_dir / "scripts" / "extract_design_contract.py", output / "scripts" / "extract-design-contract.py", force=args.force, executable=True),
        copy_file(skill_dir / "scripts" / "compare_prototype_screenshots.py", output / "scripts" / "compare-prototype-screenshots.py", force=args.force, executable=True),
        write_file(output / "README.md", render_project_readme(project_name, source_hash, framework, design), force=args.force),
        write_file(output / "docs" / "prototype-workflows.md", render_template(skill_dir, "prototype-workflows.template.md", replacements), force=args.force),
    ]
    actions.extend(
        write_file(output / relative, content, force=False)
        for relative, content in preview_pages.items()
    )
    actions.extend(
        write_file(output / relative, content, force=args.force)
        for relative, content in render_profile_contexts(design, source_hash, runtime_hash).items()
    )

    if framework == "html":
        if is_layout_v2(design):
            actions.append(write_file(output / "index.html", render_root_preview_launcher(preview_pages, design), force=False))
        else:
            actions.extend(
                [
                    write_file(output / "templates" / "root-index.html", render_template(skill_dir, "root-index.template.html", replacements), force=args.force if authoring_mode == "deterministic" else False),
                    write_file(output / "templates" / "feature-index.html", render_template(skill_dir, "feature-index.template.html", replacements), force=args.force if authoring_mode == "deterministic" else False),
                    write_file(output / "templates" / "prototype-page.html", render_template(skill_dir, "prototype-page.template.html", replacements), force=args.force if authoring_mode == "deterministic" else False),
                    write_file(output / "templates" / "placeholder-page.html", render_template(skill_dir, "placeholder-page.template.html", replacements), force=args.force if authoring_mode == "deterministic" else False),
                    write_file(output / "index.html", render_template(skill_dir, "root-index.template.html", replacements), force=False),
                ]
            )
    else:
        language = str(design.get("language") or "zh-CN")
        actions.extend(
            [
                write_file(output / "package.json", render_package_json(project_name, framework), force=args.force),
                write_file(output / "vite.config.js", render_vite_config(framework), force=args.force),
                write_file(output / "index.html", render_framework_index_html(project_name, framework, language), force=args.force),
                write_file(output / "src" / "prototype-registry.js", render_framework_registry(), force=False),
                write_file(output / "src" / "styles.css", render_framework_styles(), force=args.force if authoring_mode == "deterministic" else False),
                write_file(output / "src" / "main.jsx", render_react_main(), force=args.force) if framework == "react" else write_file(output / "src" / "main.js", render_vue_main(), force=args.force),
                write_file(output / "src" / "App.jsx", render_react_app(project_name, design), force=args.force if authoring_mode == "deterministic" else False) if framework == "react" else write_file(output / "src" / "App.vue", render_vue_app(project_name, design), force=args.force if authoring_mode == "deterministic" else False),
                write_file(output / "src" / "features" / ".gitkeep", "", force=args.force),
            ]
        )

    for warning in warnings:
        print(f"WARN {warning}", file=sys.stderr)
    for action in actions:
        print(action)
    print(f"Design change domains: {', '.join(changed_domains) if changed_domains else 'none'}")
    print(f"Affected reviewed pages: {', '.join(affected_pages) if affected_pages else 'none'}")
    if args.plan_only:
        print(f"Prototype starter plan complete: {output} ({framework})")
        return 0
    print(f"Prototype starter ready: {output} ({framework})")
    if warnings:
        print("Review warnings before relying on the starter as a strict code contract.", file=sys.stderr)
    return 0


def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("design_md", help="Path to confirmed DESIGN.md or design.md")
    parser.add_argument("--output", required=True, help="Output prototype project directory")
    parser.add_argument("--name", help="Prototype project name")
    parser.add_argument("--framework", choices=sorted(SUPPORTED_FRAMEWORKS), help="Prototype output framework. Defaults to html. This is selected only from user input, never inferred from DESIGN.md.")
    parser.add_argument("--force", action="store_true", help="Overwrite managed starter files. Existing numbered feature folders/components are not modified.")
    parser.add_argument("--strict", action="store_true", help="Deprecated compatibility alias. DESIGN readiness is always enforced before any output is written.")
    parser.add_argument("--plan-only", action="store_true", help="Print the files that would be written, skipped, or overwritten without changing the filesystem.")
    parser.add_argument("--backup-managed", action="store_true", help="Back up existing managed files before overwriting them with --force.")
    parser.add_argument("--deterministic-shared", action="store_true", help="Keep the legacy mode where Python owns and refreshes shared CSS/JS/templates. Default mode assigns those product assets to LLM authoring.")
    args = parser.parse_args()
    return build_project(args)


if __name__ == "__main__":
    raise SystemExit(main())
