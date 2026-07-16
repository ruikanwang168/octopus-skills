#!/usr/bin/env python3
"""Validate whether DESIGN.md contains enough confirmed facts to initialize a prototype.

Exit codes:
  0  ready
  1  unreadable or structurally invalid input
  2  valid DESIGN document that still needs user input
"""

from __future__ import annotations

import argparse
import json
from pathlib import Path
import re
import sys
from typing import Any, Iterable

from extract_design_contract import load_design
from layout_model import normalize_layout_model, validate_layout_model


PRODUCT_MODES = {"greenfield", "existing-product", "reconstruction"}
CONFIRMED_VALUES = {"confirmed", "已确认", "yes", "true"}
UNRESOLVED_RE = re.compile(r"(?:\bTBD\b|\bTODO\b|待确认|未确认|未知|推测|待补充)", re.I)
TOKEN_REF_RE = re.compile(r"\{tokens\.([A-Za-z0-9_.-]+)\}")

def _present(value: Any) -> bool:
    return value not in (None, "", {}, [])


def _get(value: Any, dotted: str) -> Any:
    current = value
    for part in dotted.split("."):
        if not isinstance(current, dict) or part not in current:
            return None
        current = current[part]
    return current


def _walk(value: Any, path: str = "") -> Iterable[tuple[str, Any]]:
    if isinstance(value, dict):
        for key, item in value.items():
            child = f"{path}.{key}" if path else str(key)
            yield from _walk(item, child)
    elif isinstance(value, list):
        for index, item in enumerate(value):
            yield from _walk(item, f"{path}[{index}]")
    else:
        yield path, value


def _issue(
    path: str,
    reason: str,
    question: str,
    accepted: str,
    *,
    category: str,
) -> dict[str, str]:
    return {
        "id": f"{category}:{path}",
        "path": path,
        "category": category,
        "reason": reason,
        "question": question,
        "acceptedEvidence": accepted,
    }


def _missing(path: str, *, category: str, label: str, accepted: str) -> dict[str, str]:
    return _issue(
        path,
        f"缺少{label}，继续执行将迫使初始化器编造信息。",
        f"请确认并补充{label}（`{path}`）。",
        accepted,
        category=category,
    )


def _token_exists(tokens: dict[str, Any], path: str) -> bool:
    return _present(_get(tokens, path))


def _evidence_flags(evidence: Any) -> tuple[bool, bool, bool]:
    """Return any/desktop/mobile evidence flags while accepting a small flexible schema."""
    if not _present(evidence):
        return False, False, False
    any_evidence = False
    desktop = False
    mobile = False
    for path, value in _walk(evidence):
        if not _present(value) or isinstance(value, bool):
            continue
        lowered = f"{path} {value}".lower()
        if any(token in lowered for token in ("screenshot", "source", "url", "code", "截图", "源码", "页面")):
            any_evidence = True
        if any(token in lowered for token in ("desktop", "1440", "1280", "桌面")):
            desktop = True
        if any(token in lowered for token in ("mobile", "390", "375", "移动")):
            mobile = True
    if isinstance(evidence, (dict, list)) and _present(evidence):
        any_evidence = True
    return any_evidence, desktop, mobile


def _evidence_viewport_ids(evidence: Any, viewport_ids: set[str]) -> set[str]:
    """Find explicit viewport evidence without assuming desktop/mobile pairs."""
    found: set[str] = set()
    if not _present(evidence):
        return found
    for path, value in _walk(evidence):
        lowered = f"{path} {value}".lower()
        for viewport_id in viewport_ids:
            if viewport_id.lower() in lowered:
                found.add(viewport_id)
    return found


def validate_design_readiness(design: dict[str, Any]) -> dict[str, Any]:
    issues: list[dict[str, str]] = []
    warnings: list[dict[str, str]] = []

    for path, label in (
        ("name", "产品名称"),
        ("language", "界面语言"),
        ("summary", "产品和原型范围摘要"),
    ):
        if not _present(_get(design, path)):
            issues.append(_missing(path, category="identity", label=label, accepted="用户明确提供的文本"))

    mode = str(_get(design, "initialization.productMode") or "").strip()
    if mode not in PRODUCT_MODES:
        issues.append(
            _issue(
                "initialization.productMode",
                "初始化模式未确认，无法决定是否必须提供现有产品证据。",
                "这是绿地设计、现有产品延续，还是按参考产品重建？",
                "greenfield、existing-product 或 reconstruction",
                category="initialization",
            )
        )
    confirmation = str(_get(design, "initialization.confirmationStatus") or "").strip().lower()
    if confirmation not in CONFIRMED_VALUES:
        issues.append(
            _issue(
                "initialization.confirmationStatus",
                "DESIGN 尚未被明确确认为初始化依据。",
                "请确认当前 DESIGN 是否已经评审并可以作为初始化事实来源。",
                "confirmed；并在 evidence.decisions 记录用户确认",
                category="initialization",
            )
        )

    tokens = design.get("tokens") if isinstance(design.get("tokens"), dict) else {}

    # Every token reference used by layout/components/templates must resolve.
    for path, value in _walk(design):
        if not isinstance(value, str):
            continue
        for ref in TOKEN_REF_RE.findall(value):
            if not _token_exists(tokens, ref):
                issues.append(
                    _issue(
                        path,
                        f"引用的 tokens.{ref} 不存在。",
                        f"请补充 `tokens.{ref}`，或把 `{path}` 改为已有的明确令牌。",
                        "可解析的 token 值或有效 token 引用",
                        category="token-reference",
                    )
                )

    layout_model = normalize_layout_model(design)
    for item in validate_layout_model(layout_model):
        issues.append(
            _issue(
                item["path"],
                item["reason"],
                f"请补充或确认 `{item['path']}`。",
                item["accepted"],
                category="layout",
            )
        )

    if layout_model.get("source") == "legacy":
        layout = design.get("layout") if isinstance(design.get("layout"), dict) else {}
        breakpoint = _get(design, "layout.responsive.breakpoint")
        conflicts = [
            (f"layout.{path}", value)
            for path, value in _walk(layout)
            if "breakpoint" in path.lower() and path != "responsive.breakpoint" and _present(value) and value != breakpoint
        ]
        if conflicts:
            detail = ", ".join(f"{path}={value}" for path, value in conflicts[:4])
            issues.append(_issue("layout.responsive.breakpoint", f"存在冲突断点：主值为 {breakpoint}；{detail}。", "请确认唯一权威断点，并统一 DESIGN 中的冲突值。", "一个经用户确认的断点值", category="layout-conflict"))

    components = design.get("components") if isinstance(design.get("components"), dict) else {}

    templates = design.get("pageTemplates") if isinstance(design.get("pageTemplates"), list) else []
    representatives = [item for item in templates if isinstance(item, dict) and item.get("representative") is True]
    if not templates:
        issues.append(_missing("pageTemplates", category="templates", label="页面模板", accepted="至少一个完整页面模板"))
    elif not representatives:
        issues.append(
            _issue(
                "pageTemplates[].representative",
                "没有明确指定用于设计系统验收的代表页面。",
                "请从已定义模板中确认至少一个主预览模板。",
                "在模板上设置 representative: true",
                category="templates",
            )
        )
    for index, template in enumerate(templates):
        if not isinstance(template, dict):
            issues.append(_issue(f"pageTemplates[{index}]", "页面模板必须是对象。", "请补充页面模板的结构化定义。", "包含 id/name/purpose/structure/components 的对象", category="templates"))
            continue
        base = f"pageTemplates[{index}]"
        for key, label in (("id", "模板标识"), ("name", "模板名称"), ("purpose", "模板用途"), ("structure", "DOM/区域结构")):
            if not _present(template.get(key)):
                issues.append(_missing(f"{base}.{key}", category="templates", label=label, accepted="DESIGN 明确内容"))
        if "components" not in template or not isinstance(template.get("components"), list):
            issues.append(_missing(f"{base}.components", category="templates", label="组件引用清单（可以为空数组）", accepted="显式组件 id 列表或 []"))
        if template.get("representative") is True and not _present(template.get("previewContent")):
            issues.append(_missing(f"{base}.previewContent", category="templates", label="代表页面的真实预览文案和示例内容", accepted="用户提供或产品证据中存在的内容；不可生成虚构业务数据"))
        if template.get("representative") is True and str(template.get("id") or "") == "filter-table-list":
            for content_path, label in (
                ("topNavigation", "代表页面一级导航"),
                ("sideNavigation", "代表页面侧栏导航"),
                ("filters", "筛选字段和选项"),
                ("filterActions", "筛选区操作"),
                ("table.columns", "表格列"),
                ("table.rows", "预览表格数据"),
                ("actions", "代表页面操作"),
                ("pagination", "分页文案和页码"),
                ("userLabel", "用户入口文案"),
            ):
                if not _present(_get(template.get("previewContent") or {}, content_path)):
                    issues.append(_missing(f"{base}.previewContent.{content_path}", category="templates", label=label, accepted="真实产品证据或用户确认的内容"))
        refs = template.get("components")
        if isinstance(refs, list):
            for ref in refs:
                if isinstance(ref, str) and ref not in components:
                    issues.append(_issue(f"{base}.components", f"引用的组件 `{ref}` 未在 components 中定义。", f"请补充组件 `{ref}` 的契约或移除该引用。", "已定义组件名", category="component-reference"))

    rules = design.get("generationRules") if isinstance(design.get("generationRules"), dict) else {}
    for key in ("noSource", "selfCheck"):
        if not _present(rules.get(key)):
            issues.append(_missing(f"generationRules.{key}", category="rules", label=f"生成规则 {key}", accepted="明确的禁止推断规则或验收规则"))

    for path, value in _walk(design):
        if isinstance(value, str) and UNRESOLVED_RE.search(value):
            issues.append(_issue(path, f"字段仍包含未决标记：{value[:80]}", "请给出明确结论，或从初始化范围中移除此项。", "用户确认的结论及 evidence.decisions 记录", category="unresolved"))

    open_questions = design.get("openQuestions")
    if isinstance(open_questions, list):
        for index, item in enumerate(open_questions):
            if isinstance(item, dict) and str(item.get("status") or "").lower() in {"resolved", "closed", "confirmed", "已确认", "已解决"}:
                continue
            if _present(item):
                issues.append(_issue(f"openQuestions[{index}]", "存在未关闭的设计问题。", "请回答并关闭该问题，或明确它不属于本次初始化范围。", "status 为 resolved/closed/confirmed 且包含 resolution", category="unresolved"))

    evidence = design.get("evidence")
    any_evidence, _, _ = _evidence_flags(evidence)
    if mode in {"existing-product", "reconstruction"}:
        fidelity_viewports = {
            str(viewport.get("id"))
            for profile in layout_model.get("profiles", [])
            for viewport in profile.get("viewports", [])
            if viewport.get("claim") == "fidelity" and viewport.get("id")
        }
        found_viewports = _evidence_viewport_ids(evidence, fidelity_viewports)
        if not any_evidence:
            issues.append(_missing("evidence.sources", category="evidence", label="现有产品或重建来源证据", accepted="可追溯的本地文件、URL 或源码路径"))
        for viewport_id in sorted(fidelity_viewports - found_viewports):
            issues.append(
                _issue(
                    f"evidence.sources.{viewport_id}",
                    f"缺少 fidelity 视口 `{viewport_id}` 的产品证据。",
                    f"请补充 `{viewport_id}` 视口的截图、页面或源码证据；若只要求降级可用，请把该视口 claim 改为 degradation 并记录用户确认。",
                    "对应视口的截图/页面/源码证据，或 user-confirmed 的 degradation 决策",
                    category="evidence",
                )
            )

    # Remove exact duplicates while keeping stable ordering for user-facing prompts.
    deduped: list[dict[str, str]] = []
    seen: set[tuple[str, str]] = set()
    for item in issues:
        key = (item["id"], item["reason"])
        if key not in seen:
            seen.add(key)
            deduped.append(item)

    return {
        "version": 1,
        "status": "ready" if not deduped else "needs-input",
        "blockingIssues": deduped,
        "warnings": warnings,
        "questionGroups": sorted({item["category"] for item in deduped})[:3],
    }


def format_text(report: dict[str, Any]) -> str:
    if report["status"] == "ready":
        return "READY DESIGN.md contains confirmed initialization facts."
    rows = [f"NEEDS INPUT ({len(report['blockingIssues'])} blocking issues)"]
    for index, item in enumerate(report["blockingIssues"], 1):
        rows.extend(
            [
                f"{index}. [{item['category']}] {item['path']}",
                f"   原因：{item['reason']}",
                f"   询问：{item['question']}",
                f"   可接受：{item['acceptedEvidence']}",
            ]
        )
    rows.append("请一次只向用户确认最多三个主题；将回答写回原始 DESIGN.md 和 evidence.decisions 后重新校验。")
    return "\n".join(rows)


def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("design_md", help="Path to DESIGN.md or design.md")
    parser.add_argument("--format", choices=("text", "json"), default="text")
    args = parser.parse_args()
    path = Path(args.design_md).expanduser().resolve()
    try:
        if not path.is_file():
            raise ValueError(f"Design file does not exist: {path}")
        design, _, _ = load_design(path)
        report = validate_design_readiness(design)
    except (OSError, ValueError, SystemExit) as error:
        message = str(error)
        if args.format == "json":
            print(json.dumps({"version": 1, "status": "error", "error": message}, ensure_ascii=False, indent=2))
        else:
            print(f"ERROR {message}", file=sys.stderr)
        return 1
    print(json.dumps(report, ensure_ascii=False, indent=2) if args.format == "json" else format_text(report))
    return 0 if report["status"] == "ready" else 2


if __name__ == "__main__":
    raise SystemExit(main())
