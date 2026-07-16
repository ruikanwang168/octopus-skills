#!/usr/bin/env python3
"""Generate Page Specs Lite Markdown files from a scanned prototype."""

from __future__ import annotations

import argparse
import re
from pathlib import Path

from page_specs import (
    annotation_root,
    current_dir,
    default_candidates,
    default_page_map,
    default_product_context,
    default_spec_root,
    discover_doc_paths,
    format_frontmatter,
    is_protected_spec,
    load_docs,
    now_iso,
    read_json,
    snapshot_before_overwrite,
    spec_path_for,
    write_registry,
)


FILTER_RE = re.compile(r"搜索|筛选|查询|过滤|filter|search|query|状态", re.I)
ACTION_RE = re.compile(
    r"提交|保存|创建|新建|新增|编辑|删除|导入|导出|上传|下载|确认|审批|审核|通过|驳回|启用|停用|发布|生成|运行|"
    r"submit|save|create|edit|delete|import|export|upload|download|confirm|approve|reject|generate|run",
    re.I,
)
STATE_RE = re.compile(r"状态|加载|失败|错误|异常|为空|无数据|无权限|禁用|处理中|生成中|loading|failed|error|empty|disabled", re.I)
RISK_RE = re.compile(r"删除|移除|停用|禁用|驳回|清空|取消授权|重置|delete|disable|reject|clear|reset", re.I)
COMMON_TEXT_RE = re.compile(r"^(首页|设置|帮助|返回|菜单|通知|个人中心|Home|Settings|Help|Back|Menu)$", re.I)


def normalize(value: str) -> str:
    return re.sub(r"\s+", " ", value or "").strip()


def compact(value: str, limit: int = 42) -> str:
    text = normalize(value)
    if len(text) <= limit:
        return text
    return text[: limit - 1] + "…"


def unique(items: list[str], limit: int = 8) -> list[str]:
    result: list[str] = []
    seen: set[str] = set()
    for item in items:
        text = normalize(item)
        key = re.sub(r"\s+", "", text).lower()
        if not text or key in seen:
            continue
        seen.add(key)
        result.append(text)
        if len(result) >= limit:
            break
    return result


def attrs_text(element: dict) -> str:
    attrs = element.get("attrs") if isinstance(element.get("attrs"), dict) else {}
    return " ".join(str(value) for value in attrs.values() if value)


def element_label(element: dict, fallback: str = "") -> str:
    attrs = element.get("attrs") if isinstance(element.get("attrs"), dict) else {}
    for value in (
        element.get("text"),
        attrs.get("aria-label"),
        attrs.get("title"),
        attrs.get("placeholder"),
        attrs.get("name"),
        attrs.get("id"),
        fallback,
    ):
        text = compact(str(value or ""), 42)
        if text and not COMMON_TEXT_RE.fullmatch(text):
            return text
    return ""


def candidates_by_page(payload: dict) -> dict[str, list[dict]]:
    result: dict[str, list[dict]] = {}
    for page in payload.get("pages", []) or []:
        page_key = str(page.get("pageKey") or "")
        if page_key:
            result[page_key] = list(page.get("candidates") or [])
    return result


def context_page(product_context: dict, page_key: str) -> dict:
    for page in product_context.get("pages") or []:
        if str(page.get("pageKey") or "") == page_key:
            return page if isinstance(page, dict) else {}
    return {}


def page_surfaces(page_map: dict, page: dict) -> list[dict]:
    page_key = str(page.get("pageKey") or "")
    seen: set[str] = set()
    surfaces: list[dict] = []
    for source in (page.get("surfaces") or [], page_map.get("surfaces") or []):
        if not isinstance(source, dict) or str(source.get("pageKey") or page_key) != page_key:
            continue
        surface_id = str(source.get("id") or source.get("name") or "")
        if surface_id in seen:
            continue
        seen.add(surface_id)
        surfaces.append(source)
    return surfaces


def classify_page(page: dict, elements: list[dict], surfaces: list[dict]) -> tuple[str, str]:
    text = "\n".join(
        " ".join([str(item.get("tag") or ""), str(item.get("type") or ""), str(item.get("text") or ""), attrs_text(item)])
        for item in elements
    )
    table_count = sum(1 for item in elements if item.get("tag") == "table" or item.get("type") == "table")
    form_count = sum(1 for item in elements if item.get("tag") in {"form", "input", "select", "textarea"} or item.get("type") == "form")
    action_count = sum(1 for item in elements if item.get("tag") in {"button", "a"} and ACTION_RE.search(str(item.get("text") or "") + " " + attrs_text(item)))
    if re.search(r"提示词|生成|模型|AI|智能体|prompt|generate", text, re.I):
        return "工具页", "AIGC 页面"
    if form_count >= max(2, table_count + 1):
        return "表单页", "桌面端页面"
    if table_count or re.search(r"列表|表格|分页|筛选|查询|搜索", text, re.I):
        return "列表页", "桌面端页面"
    if action_count >= 2 or surfaces:
        return "工具页", "桌面端页面"
    return "通用页面", "桌面端页面"


def doc_matches(page_name: str, route: str, docs: list[dict]) -> list[str]:
    tokens = unique([page_name, route, *re.findall(r"[\u4e00-\u9fff]{2,}|[A-Za-z][A-Za-z0-9_-]{2,}", page_name + " " + route)], 8)
    matches: list[str] = []
    for doc in docs:
        text = str(doc.get("text") or "")
        lowered = text.lower()
        hit = [token for token in tokens if token and token.lower() in lowered]
        if hit:
            matches.append(f"{Path(str(doc.get('path'))).name}：匹配 {'、'.join(hit[:3])}")
        if len(matches) >= 3:
            break
    return matches


def selected_candidates(candidates: list[dict]) -> list[dict]:
    return [item for item in candidates if item.get("selected")]


def labels_for_dimension(candidates: list[dict], dimensions: set[str], fallback: str) -> list[str]:
    labels = [
        str(item.get("fallbackText") or item.get("title") or item.get("reason") or fallback)
        for item in selected_candidates(candidates)
        if str(item.get("dimension") or "") in dimensions
    ]
    return unique([compact(item, 36) for item in labels], 6)


def page_elements(page: dict) -> list[dict]:
    return [item for item in page.get("elements", []) or [] if isinstance(item, dict)]


def filter_elements(elements: list[dict]) -> list[str]:
    labels = []
    for element in elements:
        tag = str(element.get("tag") or "")
        combined = " ".join([str(element.get("text") or ""), attrs_text(element)])
        if tag in {"input", "select", "textarea", "form"} and FILTER_RE.search(combined):
            labels.append(element_label(element, "筛选条件"))
    return unique(labels, 6)


def action_elements(elements: list[dict]) -> list[str]:
    labels = []
    for element in elements:
        tag = str(element.get("tag") or "")
        combined = " ".join([str(element.get("text") or ""), attrs_text(element)])
        if tag in {"button", "a"} and ACTION_RE.search(combined):
            labels.append(element_label(element, "操作入口"))
    return unique(labels, 8)


def state_elements(elements: list[dict]) -> list[str]:
    labels = []
    for element in elements:
        combined = " ".join([str(element.get("text") or ""), attrs_text(element)])
        if STATE_RE.search(combined):
            labels.append(element_label(element, "状态信息"))
    return unique(labels, 6)


def table_or_list_labels(elements: list[dict], candidates: list[dict]) -> list[str]:
    labels = labels_for_dimension(candidates, {"Table and list", "Table row actions", "Data explanation"}, "结果区")
    for element in elements:
        if element.get("tag") == "table" or element.get("type") == "table":
            labels.append(element_label(element, "表格结果区"))
    return unique(labels, 6)


def bullets(items: list[str]) -> str:
    return "\n".join(f"- {item}" for item in items if item)


def section(title: str, body: str) -> str:
    body = body.strip()
    if not body:
        return ""
    return f"## {title}\n\n{body}\n"


def spec_body(page_map: dict, page: dict, candidates: list[dict], product_context: dict, docs: list[dict]) -> tuple[str, dict]:
    page_key = str(page.get("pageKey") or "")
    page_name = normalize(str(page.get("title") or page.get("pageName") or page.get("route") or page_key))
    route = normalize(str(page.get("route") or ""))
    elements = page_elements(page)
    surfaces = page_surfaces(page_map, page)
    page_type, page_shape = classify_page(page, elements, surfaces)
    ctx = context_page(product_context, page_key)
    purpose = normalize(str(ctx.get("purpose") or ""))
    if not purpose:
        purpose = f"本页面用于帮助用户完成与「{page_name}」相关的业务查看、处理和确认。"
    primary_tasks = [normalize(str(item)) for item in (ctx.get("primaryTasks") or []) if normalize(str(item))]
    if not primary_tasks:
        primary_tasks = labels_for_dimension(candidates, {"Primary action", "Form and validation", "Table and list"}, "关键任务")
    if not primary_tasks:
        primary_tasks = action_elements(elements)[:5]
    if not primary_tasks:
        primary_tasks = [f"围绕「{page_name}」确认页面职责、主要对象和关键操作边界。"]

    filters = filter_elements(elements) or labels_for_dimension(candidates, {"Form and validation"}, "筛选条件")
    actions = action_elements(elements) or labels_for_dimension(candidates, {"Primary action", "Flow and navigation"}, "关键操作")
    states = state_elements(elements) or labels_for_dimension(candidates, {"State and exception", "Permission and risk"}, "状态信息")
    result_labels = table_or_list_labels(elements, candidates)
    doc_refs = doc_matches(page_name, route, docs)

    core_items = [
        f"页面类型：{page_type}；页面形态：{page_shape}。",
        f"页面目标：{purpose}",
    ]
    if result_labels:
        core_items.append("结果/数据区域：" + "、".join(result_labels[:4]) + "。")
    if filters:
        core_items.append("筛选或输入区域：" + "、".join(filters[:4]) + "。")
    if actions:
        core_items.append("关键操作入口：" + "、".join(actions[:5]) + "。")
    if doc_refs:
        core_items.append("参考资料：" + "；".join(doc_refs) + "。")

    flow_items = [
        f"用户进入「{page_name}」后，先识别页面对象、当前状态和可处理事项。",
        "用户根据页面结构完成查询、查看、填写或操作，系统应给出成功、失败、空状态或待确认反馈。",
        "任务完成后，用户返回上级页面、进入下一步流程，或继续处理同页其他对象。",
    ]
    if surfaces:
        flow_items.append("涉及二级承载面时，用户从页面入口打开弹窗/抽屉，完成子任务后返回当前页面。")

    sections = [
        f"# {page_name}\n",
        section("页面摘要", purpose),
        section("核心内容", bullets(core_items)),
    ]
    if surfaces:
        surface_items = [
            f"{surface.get('name') or surface.get('titleText') or surface.get('id')}：{surface.get('description') or '用于承载当前页面中的独立子任务，需确认打开、关闭、保存和返回路径。'}"
            for surface in surfaces
        ]
        sections.append(section("二级承载面", bullets(surface_items)))
    if filters:
        sections.append(
            section(
                "【筛选条件】交互规则说明",
                bullets(
                    [
                        f"筛选/输入项包括：{'、'.join(filters[:6])}。",
                        "用户变更查询条件后，系统应按页面交互设计刷新或等待用户触发查询。",
                        "清空筛选条件后，应恢复默认结果范围或默认输入状态。",
                    ]
                ),
            )
        )
    if result_labels:
        sections.append(
            section(
                "【结果区】显示规则说明",
                bullets(
                    [
                        f"结果区重点对象包括：{'、'.join(result_labels[:6])}。",
                        "结果为空、加载失败或查询无结果时，应提供明确空状态或异常反馈。",
                        "存在分页、排序、批量处理或行级操作时，需在评审中确认具体规则。",
                    ]
                ),
            )
        )
    if actions:
        action_rules = [f"主要操作包括：{'、'.join(actions[:8])}。"]
        risk_actions = [item for item in actions if RISK_RE.search(item)]
        if risk_actions:
            action_rules.append(f"高风险操作包括：{'、'.join(risk_actions[:4])}，需确认二次确认、权限和撤销路径。")
        action_rules.append("操作完成后，系统应反馈成功、失败或需要用户继续完善的信息，并明确是否刷新当前页面。")
        sections.append(section("【功能操作】交互规则说明", bullets(action_rules)))
    sections.append(section("业务流程", bullets(flow_items)))
    state_rules = []
    if states:
        state_rules.append(f"页面可见状态或异常线索包括：{'、'.join(states[:6])}。")
    state_rules.extend(
        [
            "加载中、无数据、无权限、失败重试等状态如未在原型中明确展示，需要产品侧确认是否补充。",
            "涉及状态切换的操作，应明确触发条件、反馈文案和后续可执行操作。",
        ]
    )
    sections.append(section("状态与异常", bullets(state_rules)))
    questions = [
        "页面说明是否需要补充不同角色下的展示和操作差异？",
        "加载、空状态、失败重试和无权限状态是否需要在原型中补齐？",
    ]
    if not doc_refs:
        questions.insert(0, "当前说明主要基于原型结构推断，需结合 PRD、产品说明书、用户故事或业务资料复核。")
    sections.append(section("待确认", bullets(questions)))
    return "\n".join(part for part in sections if part).rstrip() + "\n", {
        "pageType": page_type,
        "pageShape": page_shape,
        "sourceType": "generated" if docs else "local-rule-draft",
    }


def build_spec_markdown(page_map: dict, page: dict, candidates: list[dict], product_context: dict, docs: list[dict]) -> str:
    body, meta = spec_body(page_map, page, candidates, product_context, docs)
    page_key = str(page.get("pageKey") or "")
    page_name = normalize(str(page.get("title") or page.get("pageName") or page.get("route") or page_key))
    source_type = str(meta.get("sourceType") or "generated")
    frontmatter = {
        "specSchemaVersion": 1,
        "storageFormat": "markdown",
        "pageKey": page_key,
        "version": 1,
        "pageName": page_name,
        "pageType": str(meta.get("pageType") or "通用页面"),
        "pageShape": str(meta.get("pageShape") or "桌面端页面"),
        "path": str(page.get("path") or ""),
        "route": str(page.get("route") or ""),
        "sourceType": source_type,
        "overwriteProtected": False,
        "lastGeneratedAt": now_iso(),
        "lastManualEditedAt": None,
    }
    if source_type == "local-rule-draft":
        frontmatter["aiReviewRequired"] = True
        frontmatter["aiReviewStatus"] = "pending"
    return format_frontmatter(frontmatter) + body


def main() -> int:
    parser = argparse.ArgumentParser(description="Generate Prototype Annotator Page Specs Lite Markdown files.")
    parser.add_argument("prototype_path", help="HTML file, static directory, or project root")
    parser.add_argument("--docs", action="append", default=[], help="PRD, product spec, user story, business brief, Markdown file, or directory. Repeatable.")
    parser.add_argument("--page-map", help="Path to prototype-annotator/page-map.json")
    parser.add_argument("--product-context", help="Path to product-context.json")
    parser.add_argument("--candidates", help="Path to annotation-candidates.json")
    parser.add_argument("--spec-root", help="Output specs root. Defaults to prototype-annotator/specs")
    parser.add_argument("--force", action="store_true", help="Overwrite protected or manually edited specs")
    parser.add_argument("--history-limit", type=int, default=1, help="Snapshots to keep per page. 1 keeps latest.before-overwrite.md; 0 disables snapshots.")
    args = parser.parse_args()

    target = Path(args.prototype_path).resolve()
    if not target.exists():
        parser.error(f"Path does not exist: {target}")
    root = annotation_root(target)
    page_map_path = Path(args.page_map).resolve() if args.page_map else default_page_map(target)
    if not page_map_path.exists():
        parser.error(f"Page map does not exist: {page_map_path}. Run scripts/scan_prototype.py first.")
    page_map = read_json(page_map_path)
    candidates_payload = read_json(Path(args.candidates).resolve() if args.candidates else default_candidates(target))
    product_context = read_json(Path(args.product_context).resolve() if args.product_context else default_product_context(target))
    docs = load_docs(discover_doc_paths(root, args.docs))
    by_page = candidates_by_page(candidates_payload)
    spec_root = Path(args.spec_root).resolve() if args.spec_root else default_spec_root(target)
    current_dir(spec_root).mkdir(parents=True, exist_ok=True)

    created = 0
    updated = 0
    skipped = 0
    generated_pages: list[dict] = []
    for page in page_map.get("pages", []) or []:
        page_key = str(page.get("pageKey") or "")
        if not page_key:
            continue
        output = spec_path_for(spec_root, page_key)
        next_markdown = build_spec_markdown(page_map, page, by_page.get(page_key, []), product_context, docs)
        if output.exists():
            current = output.read_text(encoding="utf-8")
            if is_protected_spec(current) and not args.force:
                skipped += 1
                continue
            if current == next_markdown:
                generated_pages.append(page)
                continue
            snapshot_before_overwrite(output, spec_root, page_key, args.history_limit)
            updated += 1
        else:
            created += 1
        output.write_text(next_markdown, encoding="utf-8")
        generated_pages.append(page)

    write_registry(spec_root, [page for page in page_map.get("pages", []) or [] if page.get("pageKey")], root, "generated" if docs else "local-rule-draft")
    print(f"Wrote page specs: {spec_root}")
    print(f"Created: {created}; updated: {updated}; skipped protected: {skipped}; pages: {len(generated_pages)}")
    if not docs:
        print("No product docs were found or provided; generated specs are marked local-rule-draft.")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
