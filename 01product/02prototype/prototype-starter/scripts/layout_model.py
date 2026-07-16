#!/usr/bin/env python3
"""Normalize DESIGN layout facts into the prototype-starter layout model v2.

This module is deliberately free of file writes.  Readiness validation,
generation and verification import it so they cannot drift into different
interpretations of the same DESIGN document.
"""

from __future__ import annotations

from copy import deepcopy
import re
from typing import Any


PRESENCE_VALUES = {"required", "optional", "absent"}
CLAIM_VALUES = {"fidelity", "degradation"}
PRODUCT_FORMS = {
    "desktop-web",
    "responsive-web",
    "mobile-web",
    "tablet-web",
    "portal",
    "content-web",
    "admin-web",
    "large-screen",
    "multi-surface-web",
    "custom-web",
}
STANDARD_BLOCK_TYPES = {
    "heading",
    "text",
    "navigation",
    "actions",
    "form",
    "table",
    "list",
    "cards",
    "media",
    "detail",
    "component",
}


def present(value: Any) -> bool:
    return value not in (None, "", {}, [])


def _mapping(value: Any, key: str) -> dict[str, Any]:
    return value.get(key) if isinstance(value, dict) and isinstance(value.get(key), dict) else {}


def _class_selector(value: Any) -> str:
    if not isinstance(value, str) or not value.strip():
        return ""
    classes = [part.lstrip(".") for part in value.split() if part.strip()]
    return "." + ".".join(classes) if classes else ""


def is_layout_v2(design: dict[str, Any]) -> bool:
    layout = design.get("layout")
    return isinstance(layout, dict) and (
        layout.get("contractVersion") == 2 or isinstance(layout.get("profiles"), list)
    )


def _legacy_viewports(layout: dict[str, Any]) -> list[dict[str, Any]]:
    declared = layout.get("viewports")
    if isinstance(declared, list):
        return [deepcopy(item) for item in declared if isinstance(item, dict)]
    return []


def _legacy_profile(design: dict[str, Any]) -> dict[str, Any]:
    layout = _mapping(design, "layout")
    shell = _mapping(layout, "appShell")
    if not shell:
        return {
            "id": "legacy-unresolved",
            "productForm": "",
            "rootRegion": "",
            "viewports": _legacy_viewports(layout),
            "breakpoints": [],
            "regions": [],
            "scrollOwner": {},
            "legacy": True,
        }
    class_names = _mapping(shell, "classNames")
    responsive = _mapping(layout, "responsive")
    viewports = _legacy_viewports(layout)
    viewport_ids = [str(item.get("id") or "") for item in viewports if item.get("id")]

    def presence(*, mobile_absent: bool = False) -> dict[str, str]:
        result: dict[str, str] = {}
        for viewport in viewports:
            viewport_id = str(viewport.get("id") or "")
            category = str(viewport.get("category") or viewport_id).lower()
            result[viewport_id] = "absent" if mobile_absent and category == "mobile" else "required"
        return result

    def region(
        region_id: str,
        role: str,
        selector: str,
        parent: str | None,
        *,
        before: str | None = None,
        geometry: dict[str, Any] | None = None,
        mobile_absent: bool = False,
    ) -> dict[str, Any]:
        return {
            "id": region_id,
            "role": role,
            "selector": selector,
            "parent": parent,
            "before": before,
            "presence": presence(mobile_absent=mobile_absent),
            "geometry": geometry or {},
            "styles": {},
        }

    def geometry_for(property_name: str, value: Any) -> dict[str, Any]:
        if not present(value):
            return {}
        return {viewport_id: {property_name: value} for viewport_id in viewport_ids}

    root_selector = _class_selector(class_names.get("root"))
    header_selector = _class_selector(class_names.get("header"))
    layout_selector = _class_selector(class_names.get("layout"))
    sidebar_selector = _class_selector(class_names.get("sidebar"))
    main_selector = _class_selector(class_names.get("main"))
    tabs_selector = _class_selector(class_names.get("tabs") or class_names.get("routeTagsBar"))
    view_selector = _class_selector(class_names.get("view"))

    topbar = _mapping(shell, "topbar")
    sidebar = _mapping(shell, "sidebar")
    route_tags = _mapping(shell, "routeTagsBar")
    regions = [
        region("root", "root", root_selector, None),
        region("header", "header", header_selector, "root", before="layout", geometry=geometry_for("height", topbar.get("height"))),
        region("layout", "container", layout_selector, "root"),
        region("sidebar", "navigation-secondary", sidebar_selector, "layout", before="main", geometry=geometry_for("width", sidebar.get("width")), mobile_absent=str(responsive.get("mode") or "") == "responsive"),
        region("main", "main", main_selector, "layout"),
        region("route-tabs", "route-tabs", tabs_selector, "main", before="content", geometry=geometry_for("height", route_tags.get("height"))),
        region("content", "content", view_selector, "main"),
    ]
    breakpoints: list[dict[str, Any]] = []
    if present(responsive.get("breakpoint")):
        breakpoints.append({"id": "primary", "maxWidth": responsive.get("breakpoint")})
    scroll = layout.get("scrollOwner")
    scroll_owner = {viewport_id: ("content" if scroll in {"view", "pageCanvas"} else str(scroll)) for viewport_id in viewport_ids}
    return {
        "id": "legacy-app-shell",
        "productForm": "responsive-web" if str(responsive.get("mode") or "") == "responsive" else "admin-web",
        "rootRegion": "root",
        "viewports": viewports,
        "breakpoints": breakpoints,
        "regions": regions,
        "scrollOwner": scroll_owner,
        "legacy": True,
    }


def normalize_layout_model(design: dict[str, Any]) -> dict[str, Any]:
    layout = design.get("layout") if isinstance(design.get("layout"), dict) else {}
    source = "v2" if is_layout_v2(design) else "legacy"
    if source == "v2":
        profiles = [deepcopy(item) for item in layout.get("profiles", []) if isinstance(item, dict)]
    else:
        profiles = [_legacy_profile(design)]

    normalized_profiles: list[dict[str, Any]] = []
    for raw in profiles:
        profile = deepcopy(raw)
        profile_id = str(profile.get("id") or "")
        viewports = [deepcopy(item) for item in profile.get("viewports", []) if isinstance(item, dict)]
        viewport_ids = [str(item.get("id") or "") for item in viewports if item.get("id")]
        regions: list[dict[str, Any]] = []
        for raw_region in profile.get("regions", []) if isinstance(profile.get("regions"), list) else []:
            if not isinstance(raw_region, dict):
                continue
            region = deepcopy(raw_region)
            region["id"] = str(region.get("id") or "")
            region["role"] = str(region.get("role") or "custom")
            region["selector"] = str(region.get("selector") or "")
            region["parent"] = region.get("parent") if region.get("parent") not in ("", None) else None
            declared_presence = region.get("presence") if isinstance(region.get("presence"), dict) else {}
            region["presence"] = {viewport_id: declared_presence.get(viewport_id) for viewport_id in viewport_ids}
            region["geometry"] = region.get("geometry") if isinstance(region.get("geometry"), dict) else {}
            region["styles"] = region.get("styles") if isinstance(region.get("styles"), dict) else {}
            regions.append(region)
        profile["id"] = profile_id
        profile["productForm"] = str(profile.get("productForm") or "")
        profile["rootRegion"] = str(profile.get("rootRegion") or "")
        profile["viewports"] = viewports
        profile["breakpoints"] = [deepcopy(item) for item in profile.get("breakpoints", []) if isinstance(item, dict)]
        profile["regions"] = regions
        raw_scroll = profile.get("scrollOwner")
        if isinstance(raw_scroll, str):
            profile["scrollOwner"] = {viewport_id: raw_scroll for viewport_id in viewport_ids}
        elif isinstance(raw_scroll, dict):
            profile["scrollOwner"] = {viewport_id: raw_scroll.get(viewport_id) for viewport_id in viewport_ids}
        else:
            profile["scrollOwner"] = {}
        normalized_profiles.append(profile)

    templates: list[dict[str, Any]] = []
    for raw in design.get("pageTemplates", []) if isinstance(design.get("pageTemplates"), list) else []:
        if not isinstance(raw, dict):
            continue
        item = deepcopy(raw)
        if source == "legacy" and not item.get("layoutProfile"):
            item["layoutProfile"] = normalized_profiles[0]["id"] if normalized_profiles else ""
        templates.append(item)

    pending: list[dict[str, str]] = []
    for template in templates:
        if template.get("representative") is not True:
            continue
        preview = template.get("previewContent") if isinstance(template.get("previewContent"), dict) else {}
        blocks = preview.get("blocks") if isinstance(preview.get("blocks"), list) else []
        unknown = [str(block.get("type")) for block in blocks if isinstance(block, dict) and block.get("type") not in STANDARD_BLOCK_TYPES]
        if source == "v2" and (unknown or (not blocks and not isinstance(preview.get("regions"), dict))):
            pending.append({
                "templateId": str(template.get("id") or ""),
                "reason": "unknown-blocks" if unknown else "custom-authoring-required",
                "details": ", ".join(unknown),
            })

    return {
        "version": 2,
        "source": source,
        "profiles": normalized_profiles,
        "pageTemplates": templates,
        "pendingAuthoring": pending,
    }


def _selector_renderable(selector: str) -> bool:
    return bool(
        re.fullmatch(r"\.[A-Za-z_][A-Za-z0-9_-]*(?:\.[A-Za-z_][A-Za-z0-9_-]*)*", selector)
        or re.fullmatch(r"#[A-Za-z_][A-Za-z0-9_-]*", selector)
        or re.fullmatch(r"\[data-[A-Za-z0-9_-]+(?:=[\"'][^\"']+[\"'])?\]", selector)
    )


def validate_layout_model(model: dict[str, Any]) -> list[dict[str, str]]:
    """Return structural issues independent of user-facing wording."""
    issues: list[dict[str, str]] = []

    def add(path: str, reason: str, accepted: str) -> None:
        issues.append({"path": path, "reason": reason, "accepted": accepted})

    profiles = model.get("profiles") if isinstance(model.get("profiles"), list) else []
    if not profiles:
        add("layout.profiles", "没有声明任何布局 profile。", "至少一个完整 layout profile")
        return issues
    profile_ids = [str(item.get("id") or "") for item in profiles]
    if any(not value for value in profile_ids) or len(set(profile_ids)) != len(profile_ids):
        add("layout.profiles[].id", "布局 profile 标识缺失或重复。", "非空且唯一的 profile id")

    for p_index, profile in enumerate(profiles):
        base = f"layout.profiles[{p_index}]" if model.get("source") == "v2" else "layout"
        profile_id = str(profile.get("id") or "")
        if not profile.get("productForm"):
            add(f"{base}.productForm", "缺少产品形态分类。", "desktop-web、responsive-web、mobile-web、tablet-web、portal、content-web、admin-web、large-screen、multi-surface-web 或 custom-web")
        elif profile.get("productForm") not in PRODUCT_FORMS:
            add(f"{base}.productForm", f"不支持的产品形态 `{profile.get('productForm')}`。", "受支持的 Web 产品形态")
        viewports = profile.get("viewports") if isinstance(profile.get("viewports"), list) else []
        if not viewports:
            add(f"{base}.viewports", "没有声明验收视口；初始化器不能自行选择桌面或移动尺寸。", "至少一个包含 id/category/width/height/claim 的视口")
        viewport_ids = [str(item.get("id") or "") for item in viewports]
        if any(not value for value in viewport_ids) or len(set(viewport_ids)) != len(viewport_ids):
            add(f"{base}.viewports[].id", "视口标识缺失或重复。", "非空且唯一的 viewport id")
        for v_index, viewport in enumerate(viewports):
            vbase = f"{base}.viewports[{v_index}]"
            if not viewport.get("category"):
                add(f"{vbase}.category", "缺少视口类别。", "desktop、tablet、mobile、large-screen 或 custom")
            for key in ("width", "height"):
                value = viewport.get(key)
                if not isinstance(value, (int, float)) or isinstance(value, bool) or value <= 0:
                    add(f"{vbase}.{key}", f"视口 {key} 必须是正数。", "用户确认的像素尺寸")
            if viewport.get("claim") not in CLAIM_VALUES:
                add(f"{vbase}.claim", "视口必须声明 fidelity 或 degradation。", "fidelity 或 degradation")

        regions = profile.get("regions") if isinstance(profile.get("regions"), list) else []
        region_ids = [str(item.get("id") or "") for item in regions]
        if not regions:
            add(f"{base}.regions", "没有声明布局区域。", "包含根节点和页面结构的区域列表")
        if any(not value for value in region_ids) or len(set(region_ids)) != len(region_ids):
            add(f"{base}.regions[].id", "区域标识缺失或重复。", "非空且唯一的 region id")
        region_map = {str(item.get("id") or ""): item for item in regions if item.get("id")}
        root_id = str(profile.get("rootRegion") or "")
        if root_id not in region_map:
            add(f"{base}.rootRegion", "根区域未声明或不存在。", "指向 role: root 的区域 id")
        elif region_map[root_id].get("role") != "root":
            add(f"{base}.rootRegion", "rootRegion 指向的区域角色不是 root。", "role: root 的区域")

        region_index_by_id = {
            str(item.get("id")): item_index
            for item_index, item in enumerate(regions)
            if item.get("id")
        }
        for r_index, region in enumerate(regions):
            rbase = f"{base}.regions[{r_index}]"
            region_id = str(region.get("id") or "")
            selector = str(region.get("selector") or "")
            if not selector:
                add(f"{rbase}.selector", "区域缺少审计选择器。", "产品真实且可渲染的 class、id 或 data 属性选择器")
            elif not _selector_renderable(selector):
                add(f"{rbase}.selector", f"选择器 `{selector}` 不能由通用区域渲染器安全生成。", "单一 class、多 class、id 或 data 属性选择器")
            parent = region.get("parent")
            if region_id == root_id:
                if parent is not None:
                    add(f"{rbase}.parent", "根区域 parent 必须为 null。", "null")
            elif not parent or str(parent) not in region_map:
                add(f"{rbase}.parent", "非根区域必须引用同 profile 内存在的父区域。", "有效 region id")
            for relation in ("before", "after"):
                target = region.get(relation)
                if target and str(target) not in region_map:
                    add(f"{rbase}.{relation}", f"顺序目标 `{target}` 不存在。", "同 profile 内的 region id")
            presence = region.get("presence") if isinstance(region.get("presence"), dict) else {}
            for viewport_id in viewport_ids:
                value = presence.get(viewport_id)
                if value not in PRESENCE_VALUES:
                    add(f"{rbase}.presence.{viewport_id}", "区域在该视口的存在性未明确。", "required、optional 或 absent")
            if parent and str(parent) in region_map:
                parent_presence = region_map[str(parent)].get("presence") if isinstance(region_map[str(parent)].get("presence"), dict) else {}
                for viewport_id in viewport_ids:
                    if presence.get(viewport_id) == "required" and parent_presence.get(viewport_id) == "absent":
                        add(f"{rbase}.presence.{viewport_id}", "必需区域的父区域在同一视口被声明为 absent。", "一致的父子存在性")

        # Cycle check.
        for region_id in region_map:
            seen: set[str] = set()
            current = region_id
            while current in region_map and region_map[current].get("parent"):
                current = str(region_map[current].get("parent"))
                if current in seen or current == region_id:
                    add(f"{base}.regions", f"区域父子关系存在循环，涉及 `{region_id}`。", "无环区域树")
                    break
                seen.add(current)

        # `flex` only has layout meaning when the immediate parent is a flex
        # container with an explicit axis.  The initializer emits only the
        # declared styles, so letting this through would silently produce a
        # broken shell instead of asking for the missing layout fact.
        for r_index, region in enumerate(regions):
            styles = region.get("styles") if isinstance(region.get("styles"), dict) else {}
            base_styles = styles.get("base") if isinstance(styles.get("base"), dict) else {}
            if "flex" not in base_styles:
                continue
            parent_id = region.get("parent")
            parent = region_map.get(str(parent_id)) if parent_id else None
            parent_styles = parent.get("styles") if isinstance(parent, dict) and isinstance(parent.get("styles"), dict) else {}
            parent_base = parent_styles.get("base") if isinstance(parent_styles.get("base"), dict) else {}
            missing_parent_facts: list[str] = []
            if parent_base.get("display") != "flex":
                missing_parent_facts.append("styles.base.display: flex")
            if parent_base.get("flexDirection") not in {"row", "column", "row-reverse", "column-reverse"}:
                missing_parent_facts.append("styles.base.flexDirection")
            if missing_parent_facts:
                missing_text = "、".join(missing_parent_facts)
                direct_children = [item for item in regions if item.get("parent") == parent_id]
                child_roles = {str(item.get("role") or "") for item in direct_children}
                if child_roles & {"header", "footer", "route-tabs", "bottom-navigation"}:
                    direction = "column"
                elif "navigation-secondary" in child_roles and child_roles & {"main", "content"}:
                    direction = "row"
                else:
                    direction = "请确认 row 或 column"
                suggestion = f"建议（按当前子区域角色）：`{parent_id}.styles.base` 至少补充 `display: flex`、`flexDirection: {direction}`"
                parent_index = region_index_by_id.get(str(parent_id))
                parent_path = (
                    f"{base}.regions[{parent_index}].styles.base"
                    if parent_index is not None
                    else f"{base}.regions"
                )
                add(
                    parent_path,
                    f"区域 `{region.get('id')}` 使用 flex，但父区域 `{parent_id}` 未明确声明 {missing_text}；初始化器不能猜测其布局上下文。",
                    f"{suggestion}；请确认后写入，或移除 `{region.get('id')}` 的 flex 依赖",
                )

        scroll = profile.get("scrollOwner") if isinstance(profile.get("scrollOwner"), dict) else {}
        for viewport_id in viewport_ids:
            owner = scroll.get(viewport_id)
            if owner != "body" and owner not in region_map:
                add(f"{base}.scrollOwner.{viewport_id}", "滚动容器未声明或不存在。", "body 或同 profile 内的 region id")
            elif owner in region_map and region_map[owner].get("presence", {}).get(viewport_id) == "absent":
                add(f"{base}.scrollOwner.{viewport_id}", "滚动容器在该视口被声明为 absent。", "该视口存在的 region id")

        breakpoints = profile.get("breakpoints") if isinstance(profile.get("breakpoints"), list) else []
        seen_breakpoint_ids: set[str] = set()
        boundaries: list[float] = []
        for b_index, breakpoint in enumerate(breakpoints):
            bbase = f"{base}.breakpoints[{b_index}]"
            breakpoint_id = str(breakpoint.get("id") or "")
            if not breakpoint_id or breakpoint_id in seen_breakpoint_ids:
                add(f"{bbase}.id", "断点标识缺失或重复。", "非空且唯一的 breakpoint id")
            seen_breakpoint_ids.add(breakpoint_id)
            if not any(isinstance(breakpoint.get(key), (int, float)) and not isinstance(breakpoint.get(key), bool) for key in ("minWidth", "maxWidth")):
                add(bbase, "断点没有声明 minWidth 或 maxWidth。", "至少一个明确的像素边界")
            boundary = breakpoint.get("maxWidth")
            if isinstance(boundary, (int, float)) and not isinstance(boundary, bool):
                boundaries.append(float(boundary))
        if len(boundaries) != len(set(boundaries)):
            add(f"{base}.breakpoints", "存在重复或冲突的 maxWidth 断点。", "严格递增且唯一的断点边界")
        structural_variants = any(len(set(region.get("presence", {}).values())) > 1 for region in regions)
        explicit_ranges = all(viewport.get("minWidth") is not None or viewport.get("maxWidth") is not None for viewport in viewports)
        if len(viewports) > 1 and structural_variants and not explicit_ranges and len(boundaries) != len(viewports) - 1:
            add(f"{base}.breakpoints", "存在跨视口结构切换，但断点数量不足以映射所有视口状态。", "按视口宽度顺序提供 N-1 个唯一 maxWidth 断点，或为每个视口声明 minWidth/maxWidth")

    profile_id_set = set(profile_ids)
    representatives = [item for item in model.get("pageTemplates", []) if item.get("representative") is True]
    for index, template in enumerate(representatives):
        ref = str(template.get("layoutProfile") or "")
        if ref not in profile_id_set:
            add(f"pageTemplates[{index}].layoutProfile", f"代表模板引用的 layout profile `{ref}` 不存在。", "已声明的 profile id")
    return issues


def region_count(region: dict[str, Any], viewport_id: str) -> dict[str, int]:
    value = region.get("presence", {}).get(viewport_id)
    if value == "required":
        return {"min": 1, "max": 1}
    if value == "optional":
        return {"min": 0, "max": 1}
    return {"min": 0, "max": 0}


def dom_count(region: dict[str, Any], viewport_ids: list[str]) -> dict[str, int]:
    values = [region.get("presence", {}).get(viewport_id) for viewport_id in viewport_ids]
    if all(value == "absent" for value in values):
        return {"min": 0, "max": 0}
    if any(value == "required" for value in values):
        return {"min": 1, "max": 1}
    return {"min": 0, "max": 1}
