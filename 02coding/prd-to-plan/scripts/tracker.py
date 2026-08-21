#!/usr/bin/env python3
"""Validate and update an AI execution-plan tracker without external dependencies."""

from __future__ import annotations

import argparse
import csv
import hashlib
import json
import re
import sys
from datetime import datetime, timezone
from pathlib import Path, PurePosixPath
from typing import Any


REQUIRED_ROOT_KEYS = {
    "schema_version",
    "project",
    "catalog_confirmed",
    "catalog_confirmed_at",
    "generated_at",
    "catalog_confirmation_document",
    "catalog_confirmation_hash",
    "prd_operation_catalog",
    "interface_capability_catalog",
    "stories",
}
REQUIRED_STORY_KEYS = {
    "sequence",
    "id",
    "name",
    "file_stem",
    "user_story",
    "priority",
    "ui_required",
    "operation_refs",
    "story_split_rationale",
    "ui_surfaces",
    "interface_capability_refs",
    "prd_refs",
    "scope",
    "acceptance_criteria",
    "depends_on",
    "risks",
    "plan_generated",
    "development_completed",
    "self_test_completed",
    "plan_stale",
    "blocked_reason",
    "artifacts",
    "last_updated_at",
}
REQUIRED_ARTIFACT_KEYS = {"contract", "implementation", "tests"}
CSV_HEADER = [
    "case_id",
    "story_id",
    "acceptance_criterion_id",
    "requirement_ref",
    "implementation_refs",
    "test_level",
    "test_type",
    "title",
    "priority",
    "preconditions",
    "steps",
    "test_data",
    "expected_result",
    "automation_candidate",
    "environment",
    "status",
]
STORY_ID_RE = re.compile(r"^(?:US|TECH)-\d{3}$")
OPERATION_ID_RE = re.compile(r"^OP-(?:REQ|ARCH|TECH)-\d{3}-\d{2,3}$")
INTERFACE_CAPABILITY_ID_RE = re.compile(r"^INT-(?:REQ|ARCH|TECH)-\d{3}-\d{2,3}$")
AC_ID_RE = re.compile(r"^AC-(?:US|TECH)-\d{3}-\d{2}$")
CHINESE_USER_STORY_RE = re.compile(
    r"^作为\s*(?P<role>[^，,。]+?)\s*[，,]\s*"
    r"我(?:想要|希望|需要)\s*(?P<behavior>[^，,。]+?)\s*[，,]\s*"
    r"以便\s*(?P<value>.+?)[。.]?$"
)
ENGLISH_USER_STORY_RE = re.compile(
    r"^As\s+(?:an?\s+)?(?P<role>.+?),\s*I\s+(?:want|need)\s+(?P<behavior>.+?),\s*"
    r"so\s+that\s+(?P<value>.+?)[.]?$",
    flags=re.I,
)
CHINESE_TECH_OUTCOME_RE = re.compile(
    r"^为了\s*(?P<benefit>[^，,。]+?)\s*[，,]\s*需要\s*(?P<work>[^，,。]+?)\s*[，,]\s*"
    r"从而\s*(?P<outcome>.+?)[。.]?$"
)
GENERIC_ROLE_RE = re.compile(r"^(?:用户|人员|相关人员|使用者|角色|user|person|people)$", flags=re.I)
TECHNICAL_TASK_RE = re.compile(
    r"(?:开发|实现|搭建|新增|修改|重构).*(?:前端|后端|接口|API|数据库|数据表|Redis|Kafka|缓存|微服务|脚本|容器|部署)",
    flags=re.I,
)
VAGUE_VALUE_RE = re.compile(r"^(?:完成需求|实现功能|方便使用|提升体验|满足需要|支持业务|提高效率)[。.]?$")
VAGUE_AC_RE = re.compile(
    r"(?:界面友好|响应快速|正常处理|正常显示|合理处理|相关功能|完成前后端|完成开发|"
    r"^(?:支持.+|.+(?:保存|提交|创建|更新|删除|操作)成功|.+功能可用)[。.]?$)"
)
PLACEHOLDER_RE = re.compile(
    r"(?i)(?:\bTODO\b|\bTBD\b|待补充|待完善|以后处理|\.\.\.|\[\s*具体来源与定位\s*\])"
)
VAGUE_IMPLEMENTATION_RE = re.compile(
    r"(?:按现有方式处理|实现相关逻辑|处理业务逻辑|查询相关数据|参考相关代码|"
    r"返回给前端|按条件查询数据库)"
)
ALLOWED_TEST_LEVELS = {
    "unit",
    "component",
    "visual",
    "api",
    "integration",
    "e2e",
    "security",
    "migration",
    "manual",
}
ALLOWED_TEST_TYPES = {
    "positive",
    "negative",
    "boundary",
    "validation",
    "interaction",
    "layout",
    "permission",
    "concurrency",
    "idempotency",
    "compatibility",
    "regression",
    "performance",
    "accessibility",
    "security",
}
ALLOWED_OPERATION_TYPES = {
    "query", "create", "update", "delete", "business_action", "batch", "import", "export",
    "status_transition", "async_task", "external_call", "ui_interaction", "route_navigation", "other",
}
ALLOWED_COVERAGE_STATUSES = {"covered", "excluded", "deferred", "blocked"}
ALLOWED_INTERFACE_NEEDS = {"required", "not_required", "to_verify"}
ALLOWED_UI_SURFACE_TYPES = {
    "page", "dialog", "drawer", "stage", "section", "panel", "tab", "popover", "external_page", "other",
}
# These fields belong to stage 4 implementation design. Reject them in stage 3
# instead of silently accepting a technically detailed story catalog.
STAGE_3_TECHNICAL_FIELDS = {
    "expected_pages", "expected_interfaces", "page_refs", "interface_refs",
    "contract_id", "contract_ids", "operationId", "Method/Path", "method_path",
    "route", "path", "frontend_route", "component_path", "component_refs",
    "code_refs", "db_tables", "change_type", "implementation_kind",
}
LEARNING_COLUMNS = [
    "learning_ref", "source_type", "source_or_repository", "location", "why_read",
    "verified_finding", "planned_use", "related_scope",
]
LIST_COLUMNS = [
    "pagination", "page_size", "default_sort", "data_source", "loading_empty_error",
]
LIST_FIELD_COLUMNS = [
    "order", "field", "label", "source_and_mapping", "display_format",
    "permission_and_empty", "row_interaction",
]
QUERY_COLUMNS = [
    "order", "query_field", "control", "default_value", "match_mode",
    "options_source", "validation", "request_mapping",
]
FORM_FIELD_COLUMNS = [
    "order", "area", "field", "component", "source_and_mapping",
    "default_display_edit", "validation_and_linkage", "error_and_permission",
]
ACTION_COLUMNS = [
    "action", "location", "visible_enabled_guard", "confirmation", "contract_id",
    "request_mapping", "success_behavior", "failure_behavior",
]
FLOW_COLUMNS = [
    "flow", "trigger", "steps_and_validation", "success", "failure_or_branch",
]
INTERFACE_FIELD_COLUMNS = [
    "direction", "schema_path", "page_field_or_caller",
    "transform_validation", "error_empty_behavior",
]
ALLOWED_CHANGE_TYPES = {"reuse", "new", "modify", "delete"}
TASK_COLUMNS = [
    "task_id", "depends_on", "files_or_symbols", "change", "related_refs", "done_when", "verification",
]
ACCEPTANCE_COLUMNS = [
    "acceptance_criterion_id", "implementation_refs", "test_case_ids", "observable_result",
]
OPERATION_MAPPING_COLUMNS = [
    "operation_id", "implementation_kind", "ui_surface_refs", "contract_ids",
    "implementation_refs", "decision_basis",
]
ALLOWED_IMPLEMENTATION_KINDS = {
    "frontend_only", "http_api", "async_task", "external_integration",
    "database_only", "navigation", "mixed",
}


class TrackerError(Exception):
    """A user-fixable tracker problem."""


def is_timezone_timestamp(value: Any) -> bool:
    if not isinstance(value, str) or not value.strip():
        return False
    try:
        parsed = datetime.fromisoformat(value.replace("Z", "+00:00"))
    except ValueError:
        return False
    return parsed.utcoffset() is not None


def load_tracker(path: Path) -> dict[str, Any]:
    try:
        data = json.loads(path.read_text(encoding="utf-8"))
    except FileNotFoundError as exc:
        raise TrackerError(f"跟踪文件不存在: {path}") from exc
    except json.JSONDecodeError as exc:
        raise TrackerError(f"JSON 解析失败 {path}:{exc.lineno}:{exc.colno}: {exc.msg}") from exc
    if not isinstance(data, dict):
        raise TrackerError("跟踪文件根节点必须是 JSON object")
    return data


def write_tracker(path: Path, data: dict[str, Any]) -> None:
    path.write_text(json.dumps(data, ensure_ascii=False, indent=2) + "\n", encoding="utf-8")


def safe_artifact_path(root: Path, value: Any, label: str, errors: list[str]) -> Path | None:
    if not isinstance(value, str) or not value.strip():
        errors.append(f"{label} 必须是非空相对路径")
        return None
    pure = PurePosixPath(value)
    if pure.is_absolute() or ".." in pure.parts or "\\" in value:
        errors.append(f"{label} 必须位于输出目录内并使用 /: {value!r}")
        return None
    candidate = root.joinpath(*pure.parts)
    try:
        candidate.resolve(strict=False).relative_to(root)
    except ValueError:
        errors.append(f"{label} 解析后逃出输出目录: {value!r}")
        return None
    return candidate


def validate_confirmation_document(data: dict[str, Any], root: Path, errors: list[str]) -> None:
    document = safe_artifact_path(
        root,
        data.get("catalog_confirmation_document"),
        "catalog_confirmation_document",
        errors,
    )
    expected_hash = data.get("catalog_confirmation_hash")
    if not isinstance(expected_hash, str) or not re.fullmatch(r"sha256:[0-9a-f]{64}", expected_hash):
        errors.append("catalog_confirmation_hash 必须是 sha256:<64位小写十六进制>")
    if document is None or not isinstance(expected_hash, str) or not expected_hash.startswith("sha256:"):
        return
    if not document.is_file():
        errors.append(f"缺少用户确认文件: {document}")
        return
    document_text = document.read_text(encoding="utf-8")
    if not re.search(r"(?m)^confirmation_status:\s*[\"']?confirmed[\"']?\s*$", document_text):
        errors.append(f"用户确认文件未标记为 confirmed: {document}")
    actual_hash = hashlib.sha256(document_text.encode("utf-8")).hexdigest()
    if expected_hash != f"sha256:{actual_hash}":
        errors.append(
            "AI执行清单确认.md 已发生变化；必须重新取得用户确认并重新生成 AI执行清单.json"
        )


def find_cycle(graph: dict[str, list[str]]) -> list[str] | None:
    visiting: set[str] = set()
    visited: set[str] = set()
    stack: list[str] = []

    def visit(node: str) -> list[str] | None:
        if node in visiting:
            start = stack.index(node)
            return stack[start:] + [node]
        if node in visited:
            return None
        visiting.add(node)
        stack.append(node)
        for dependency in graph.get(node, []):
            cycle = visit(dependency)
            if cycle:
                return cycle
        stack.pop()
        visiting.remove(node)
        visited.add(node)
        return None

    for candidate in graph:
        cycle = visit(candidate)
        if cycle:
            return cycle
    return None


def split_markdown_row(line: str) -> list[str]:
    value = line.strip()
    if value.startswith("|"):
        value = value[1:]
    if value.endswith("|") and not value.endswith(r"\|"):
        value = value[:-1]
    return [cell.strip().strip("`").replace(r"\|", "|") for cell in re.split(r"(?<!\\)\|", value)]


def is_markdown_separator(line: str, width: int) -> bool:
    cells = split_markdown_row(line)
    return len(cells) == width and all(re.fullmatch(r":?-{3,}:?", cell) for cell in cells)


def extract_markdown_tables(text: str) -> list[tuple[list[str], list[dict[str, str]]]]:
    lines = text.splitlines()
    tables: list[tuple[list[str], list[dict[str, str]]]] = []
    index = 0
    while index + 1 < len(lines):
        if "|" not in lines[index]:
            index += 1
            continue
        headers = split_markdown_row(lines[index])
        if not headers or not is_markdown_separator(lines[index + 1], len(headers)):
            index += 1
            continue
        index += 2
        rows: list[dict[str, str]] = []
        while index < len(lines) and "|" in lines[index]:
            cells = split_markdown_row(lines[index])
            if len(cells) != len(headers):
                break
            rows.append(dict(zip(headers, cells)))
            index += 1
        tables.append((headers, rows))
    return tables


def require_table(
    text: str,
    columns: list[str],
    story_id: str,
    label: str,
    errors: list[str],
) -> list[dict[str, str]]:
    for headers, rows in extract_markdown_tables(text):
        if headers == columns:
            if not rows:
                errors.append(f"{story_id} {label} 表格不能为空")
                return []
            for row_index, row in enumerate(rows, start=1):
                empty = [column for column in columns if not row.get(column, "").strip()]
                if empty:
                    errors.append(f"{story_id} {label} 第 {row_index} 行缺失: {', '.join(empty)}")
                unsupported_na = [
                    column
                    for column in columns
                    if row.get(column, "").strip().upper().startswith("N/A")
                    and not has_evidence_detail(row[column])
                ]
                if unsupported_na:
                    errors.append(
                        f"{story_id} {label} 第 {row_index} 行 N/A 缺少核实依据: "
                        f"{', '.join(unsupported_na)}"
                    )
            return rows
    errors.append(f"{story_id} {label} 缺少必要信息表: {' | '.join(columns)}")
    return []


def optional_table(
    text: str,
    columns: list[str],
    story_id: str,
    label: str,
    errors: list[str],
) -> list[dict[str, str]]:
    """Validate an applicable information block when its table is present."""
    if not any(headers == columns for headers, _ in extract_markdown_tables(text)):
        return []
    return require_table(text, columns, story_id, label, errors)


def split_refs(value: str) -> set[str]:
    return {part.strip() for part in re.split(r"[;；]", value) if part.strip()}


def reject_stage_3_technical_fields(item: dict[str, Any], label: str, errors: list[str]) -> None:
    leaked = sorted(STAGE_3_TECHNICAL_FIELDS.intersection(item))
    if leaked:
        errors.append(
            f"{label} 包含阶段 4 技术字段: {', '.join(leaked)}；"
            "阶段 3只允许需求操作、逻辑交互载体和验收信息"
        )


def validate_interface_capability_catalog(
    data: dict[str, Any],
    story_ids: set[str],
    catalog_operations: dict[str, dict[str, Any]],
    errors: list[str],
) -> dict[str, dict[str, Any]]:
    """Validate business-level interface needs without accepting HTTP design fields."""
    catalog = data.get("interface_capability_catalog")
    if not isinstance(catalog, list):
        errors.append("interface_capability_catalog 必须是 array；第三阶段需确认接口业务能力范围")
        return {}
    capabilities: dict[str, dict[str, Any]] = {}
    for index, item in enumerate(catalog):
        label = f"interface_capability_catalog[{index}]"
        if not isinstance(item, dict):
            errors.append(f"{label} 必须是 object")
            continue
        reject_stage_3_technical_fields(item, label, errors)
        required = (
            "interface_capability_id", "name", "source_refs", "source_locator",
            "story_id", "operation_refs", "business_api_need",
        )
        missing = [key for key in required if key not in item]
        if missing:
            errors.append(f"{label} 缺少字段: {', '.join(missing)}")
            continue
        capability_id = item.get("interface_capability_id")
        if not isinstance(capability_id, str) or not INTERFACE_CAPABILITY_ID_RE.fullmatch(capability_id):
            errors.append(f"{label}.interface_capability_id 格式错误: {capability_id!r}")
            continue
        if capability_id in capabilities:
            errors.append(f"interface_capability_id 重复: {capability_id}")
            continue
        if not isinstance(item.get("name"), str) or not item["name"].strip():
            errors.append(f"{label}.name 必须是非空业务能力名称")
        refs = item.get("source_refs")
        if not isinstance(refs, list) or not refs or not all(isinstance(ref, str) and ref.strip() for ref in refs):
            errors.append(f"{label}.source_refs 必须是非空字符串 array")
        elif not any(re.fullmatch(r"(?:REQ|ARCH|TECH)-\d{3}", ref) for ref in refs):
            errors.append(f"{label}.source_refs 至少要关联一个 REQ/ARCH/TECH 来源")
        if not isinstance(item.get("source_locator"), str) or not item["source_locator"].strip():
            errors.append(f"{label}.source_locator 必须是具体 PRD/原型定位")
        story_id = item.get("story_id")
        if not isinstance(story_id, str) or story_id not in story_ids:
            errors.append(f"{label}.story_id 必须引用已存在故事: {story_id!r}")
        op_refs = item.get("operation_refs")
        if not isinstance(op_refs, list) or not op_refs or not all(
            isinstance(ref, str) and OPERATION_ID_RE.fullmatch(ref) for ref in op_refs
        ):
            errors.append(f"{label}.operation_refs 必须是非空 OP-* 字符串 array")
        elif set(op_refs) - set(catalog_operations):
            errors.append(
                f"{label}.operation_refs 引用未登记操作: "
                f"{', '.join(sorted(set(op_refs) - set(catalog_operations)))}"
            )
        if item.get("business_api_need") not in ALLOWED_INTERFACE_NEEDS:
            errors.append(f"{label}.business_api_need 无效: {item.get('business_api_need')!r}")
        capabilities[capability_id] = item
    return capabilities


def extract_entity_blocks(text: str, kind: str) -> list[tuple[str, str, str]]:
    """Return ID, title and body for headings such as `### 页面 [page-id] 名称`."""
    lines = text.splitlines()
    entity_re = re.compile(
        rf"^(#{{2,6}})\s+{re.escape(kind)}\s+\[([^\]\s]+)\]\s+(.+?)\s*$"
    )
    heading_re = re.compile(r"^(#{1,6})\s+")
    any_entity_re = re.compile(r"^#{2,6}\s+(?:页面|接口)\s+\[[^\]\s]+\]\s+.+$")
    blocks: list[tuple[str, str, str]] = []
    for index, line in enumerate(lines):
        match = entity_re.match(line)
        if not match:
            continue
        level = len(match.group(1))
        end = len(lines)
        for cursor in range(index + 1, len(lines)):
            next_heading = heading_re.match(lines[cursor])
            if any_entity_re.match(lines[cursor]) or (
                next_heading and len(next_heading.group(1)) <= level
            ):
                end = cursor
                break
        blocks.append((match.group(2).strip(), match.group(3).strip(), "\n".join(lines[index + 1:end])))
    return blocks


def extract_entity_metadata(block: str) -> dict[str, str]:
    metadata: dict[str, str] = {}
    for line in block.splitlines():
        match = re.match(r"^\s*[-*]\s+([^:：]+?)\s*[:：]\s*(.+?)\s*$", line)
        if match:
            metadata[match.group(1).strip()] = match.group(2).strip()
    return metadata


def require_entity_metadata(
    metadata: dict[str, str],
    required: list[str],
    story_id: str,
    entity_label: str,
    errors: list[str],
) -> None:
    missing = [key for key in required if not metadata.get(key, "").strip()]
    if missing:
        errors.append(f"{story_id} {entity_label} 缺少元数据: {', '.join(missing)}")


def validate_operation_catalog(
    data: dict[str, Any],
    story_ids: set[str],
    errors: list[str],
) -> dict[str, dict[str, Any]]:
    """Validate the PRD-first operation ledger used as the omission-proof source of truth."""
    catalog = data.get("prd_operation_catalog")
    if not isinstance(catalog, list) or not catalog:
        errors.append("prd_operation_catalog 必须是非空 array；必须先逐项盘点 PRD 操作")
        return {}
    operations: dict[str, dict[str, Any]] = {}
    for index, item in enumerate(catalog):
        label = f"prd_operation_catalog[{index}]"
        if not isinstance(item, dict):
            errors.append(f"{label} 必须是 object")
            continue
        reject_stage_3_technical_fields(item, label, errors)
        required = (
            "operation_id", "name", "operation_type", "source_refs", "source_locator",
            "story_id", "ui_surface_refs", "coverage_status",
        )
        missing = [key for key in required if key not in item]
        if missing:
            errors.append(f"{label} 缺少字段: {', '.join(missing)}")
            continue
        operation_id = item.get("operation_id")
        if not isinstance(operation_id, str) or not OPERATION_ID_RE.fullmatch(operation_id):
            errors.append(f"{label}.operation_id 格式错误: {operation_id!r}")
            continue
        if operation_id in operations:
            errors.append(f"operation_id 重复: {operation_id}")
            continue
        if not isinstance(item.get("name"), str) or not item["name"].strip():
            errors.append(f"{label}.name 必须是非空字符串")
        if item.get("operation_type") not in ALLOWED_OPERATION_TYPES:
            errors.append(f"{label}.operation_type 无效: {item.get('operation_type')!r}")
        refs = item.get("source_refs")
        if not isinstance(refs, list) or not refs or not all(isinstance(ref, str) and ref.strip() for ref in refs):
            errors.append(f"{label}.source_refs 必须是非空字符串 array")
        elif not any(re.fullmatch(r"(?:REQ|ARCH|TECH)-\d{3}", ref) for ref in refs):
            errors.append(f"{label}.source_refs 至少要关联一个 REQ/ARCH/TECH 来源")
        if not isinstance(item.get("source_locator"), str) or not item["source_locator"].strip():
            errors.append(f"{label}.source_locator 必须是具体 PRD/原型定位")
        status = item.get("coverage_status")
        if status not in ALLOWED_COVERAGE_STATUSES:
            errors.append(f"{label}.coverage_status 无效: {status!r}")
        story_id = item.get("story_id")
        if status == "covered" and (not isinstance(story_id, str) or story_id not in story_ids):
            errors.append(f"{label}.covered 必须归属已存在故事: {story_id!r}")
        reason = item.get("reason")
        if status != "covered" and (not isinstance(reason, str) or not reason.strip()):
            errors.append(f"{label} 非 covered 操作必须填写 reason")
        values = item.get("ui_surface_refs")
        if not isinstance(values, list) or not all(isinstance(value, str) and value.strip() for value in values):
            errors.append(f"{label}.ui_surface_refs 必须是字符串 array")
        if not item.get("ui_surface_refs") and (
            not isinstance(item.get("no_ui_reason"), str) or not item.get("no_ui_reason", "").strip()
        ):
            errors.append(f"{label} 没有 ui_surface_refs 时必须填写 no_ui_reason")
        operations[operation_id] = item
    return operations


def validate_ui_surfaces(
    story: dict[str, Any],
    story_id: str,
    requirement_ids: set[str],
    ac_ids: set[str],
    operation_ids: set[str],
    ui_required: bool,
    errors: list[str],
) -> dict[str, dict[str, Any]]:
    """Validate logical UI surfaces without leaking routes, code locations or API design into stage 3."""
    known_trace_refs = requirement_ids | ac_ids
    surfaces: dict[str, dict[str, Any]] = {}
    items = story.get("ui_surfaces")
    if not isinstance(items, list):
        errors.append(f"{story_id}.ui_surfaces 必须是 array")
        items = []
    for index, item in enumerate(items):
        label = f"{story_id}.ui_surfaces[{index}]"
        if not isinstance(item, dict):
            errors.append(f"{label} 必须是 object")
            continue
        reject_stage_3_technical_fields(item, label, errors)
        missing = [
            key for key in ("surface_id", "name", "surface_type", "source_refs", "operation_refs")
            if key not in item
        ]
        if missing:
            errors.append(f"{label} 缺少字段: {', '.join(missing)}")
            continue
        surface_id = item.get("surface_id")
        if not isinstance(surface_id, str) or not re.fullmatch(r"[A-Za-z][A-Za-z0-9._:-]*", surface_id):
            errors.append(f"{label}.surface_id 格式错误: {surface_id!r}")
            continue
        if surface_id in surfaces:
            errors.append(f"{story_id} ui_surfaces 重复 surface_id: {surface_id}")
        if not isinstance(item.get("name"), str) or not item["name"].strip():
            errors.append(f"{label}.name 必须是非空字符串")
        surface_type = item.get("surface_type")
        if surface_type not in ALLOWED_UI_SURFACE_TYPES:
            errors.append(f"{label}.surface_type 无效: {surface_type!r}")
        refs = item.get("source_refs")
        if not isinstance(refs, list) or not refs or not all(isinstance(ref, str) and ref.strip() for ref in refs):
            errors.append(f"{label}.source_refs 必须是非空字符串 array")
        else:
            refs_set = set(refs)
            unknown = refs_set - known_trace_refs
            if unknown:
                errors.append(f"{label}.source_refs 引用未知 REQ/AC: {', '.join(sorted(unknown))}")
            if not refs_set.intersection(requirement_ids) or not refs_set.intersection(ac_ids):
                errors.append(f"{label}.source_refs 必须同时关联至少一个 REQ 和 AC")
        op_refs = item.get("operation_refs")
        if not isinstance(op_refs, list) or not op_refs or not all(isinstance(ref, str) and ref.strip() for ref in op_refs):
            errors.append(f"{label}.operation_refs 必须是非空字符串 array")
        elif set(op_refs) - operation_ids:
            errors.append(f"{label}.operation_refs 引用未知操作: {', '.join(sorted(set(op_refs) - operation_ids))}")
        surfaces[surface_id] = {
            "surface_type": surface_type,
            "operation_refs": op_refs if isinstance(op_refs, list) else [],
        }

    if ui_required and not surfaces:
        errors.append(f"{story_id} ui_required=true 时 ui_surfaces 不能为空")
    if not ui_required and surfaces:
        errors.append(f"{story_id} ui_required=false 时 ui_surfaces 必须为空")
    return surfaces


def validate_story_card(
    story_id: str,
    name: Any,
    user_story: Any,
    errors: list[str],
) -> None:
    """Validate short-title vs full-card semantics without pretending to judge INVEST mechanically."""
    if not isinstance(name, str) or not name.strip():
        errors.append(f"{story_id}.name 必须是非空业务短标题")
        return
    title = name.strip()
    if re.search(r"(?:^作为|我(?:想要|希望|需要)|以便|^As\s+.+\bI\s+(?:want|need)\b)", title, flags=re.I):
        errors.append(f"{story_id}.name 应是业务短标题，不能填写完整三段式用户故事")
    if re.fullmatch(r"(?:用户故事|功能|模块)[-_ ]*\d*", title, flags=re.I):
        errors.append(f"{story_id}.name 不能使用无业务含义的占位名称: {title!r}")
    if story_id.startswith("US-") and TECHNICAL_TASK_RE.search(title):
        errors.append(f"{story_id}.name 是技术任务名，不是用户价值短标题: {title!r}")

    if not isinstance(user_story, str) or not user_story.strip():
        errors.append(f"{story_id}.user_story 必须是非空字符串")
        return
    card = user_story.strip()
    if story_id.startswith("TECH-"):
        if not CHINESE_TECH_OUTCOME_RE.fullmatch(card):
            errors.append(
                f"{story_id}.user_story 必须使用技术结果格式："
                "为了 <受益故事或业务能力>，需要 <技术前置>，从而 <支持结果>。"
            )
        return

    match = CHINESE_USER_STORY_RE.fullmatch(card) or ENGLISH_USER_STORY_RE.fullmatch(card)
    if not match:
        errors.append(
            f"{story_id}.user_story 必须使用角色—行为—价值格式："
            "作为 <具体角色>，我想要/希望 <业务行为>，以便 <明确价值>。"
        )
        return
    role = match.group("role").strip()
    behavior = match.group("behavior").strip()
    value = match.group("value").strip()
    if GENERIC_ROLE_RE.fullmatch(role):
        errors.append(f"{story_id}.user_story 角色过于笼统: {role!r}")
    if TECHNICAL_TASK_RE.search(behavior):
        errors.append(f"{story_id}.user_story 行为使用了技术任务而非业务语言: {behavior!r}")
    if VAGUE_VALUE_RE.fullmatch(value):
        errors.append(f"{story_id}.user_story 价值描述过于空泛: {value!r}")


def has_evidence_detail(value: str) -> bool:
    match = re.search(r"(?:核实依据|依据|核实)(?:是|为)?\s*[:：]?\s*(.+)", value, flags=re.DOTALL)
    if not match:
        return False
    detail = match.group(1).strip(" \t\r\n:：,，.;。")
    return bool(detail) and detail != "[具体来源与定位]"


def validate_openapi(
    path: Path,
    story_id: str,
    ac_ids: set[str],
    requirement_ids: set[str],
    story_operation_ids: set[str],
    errors: list[str],
) -> dict[str, dict[str, Any]]:
    """Validate the external contract without forcing implementation-detail extensions."""
    try:
        doc = json.loads(path.read_text(encoding="utf-8"))
    except (OSError, json.JSONDecodeError) as exc:
        errors.append(f"{story_id} 接口契约无法解析: {path}: {exc}")
        return {}
    if not isinstance(doc, dict):
        errors.append(f"{story_id} 接口契约根节点必须是 object")
        return {}
    if not str(doc.get("openapi", "")).startswith("3.1."):
        errors.append(f"{story_id} 接口契约必须使用 OpenAPI 3.1.x")
    for key in ("info", "paths", "components"):
        if not isinstance(doc.get(key), dict):
            errors.append(f"{story_id} 接口契约缺少 object 字段 {key}")
    if isinstance(doc.get("info"), dict) and doc["info"].get("x-story-id") != story_id:
        errors.append(f"{story_id} 接口契约 info.x-story-id 不匹配")

    references = doc.get("x-source-references")
    if not isinstance(references, list) or not references:
        errors.append(f"{story_id} 接口契约缺少非空 x-source-references")
        references = []
    referenced_acs: set[str] = set()
    referenced_requirements: set[str] = set()
    for index, reference in enumerate(references):
        if not isinstance(reference, dict):
            errors.append(f"{story_id} x-source-references[{index}] 必须是 object")
            continue
        missing = [
            field for field in ("source_id", "locator", "requirement_id", "acceptance_criterion_id")
            if not isinstance(reference.get(field), str) or not reference[field].strip()
        ]
        if missing:
            errors.append(f"{story_id} x-source-references[{index}] 缺少非空字段: {', '.join(missing)}")
            continue
        referenced_requirements.add(reference["requirement_id"].strip())
        referenced_acs.add(reference["acceptance_criterion_id"].strip())
    if requirement_ids - referenced_requirements:
        errors.append(f"{story_id} 接口契约未引用需求: {', '.join(sorted(requirement_ids - referenced_requirements))}")
    if ac_ids - referenced_acs:
        errors.append(f"{story_id} 接口契约未引用 AC: {', '.join(sorted(ac_ids - referenced_acs))}")

    paths = doc.get("paths", {})
    if not isinstance(paths, dict):
        return {}
    if not paths:
        reason = doc.get("x-no-api-change")
        if not isinstance(reason, str) or not has_evidence_detail(reason):
            errors.append(f"{story_id} paths 为空时 x-no-api-change 必须写明核实依据")
        return {}
    if doc.get("x-no-api-change"):
        errors.append(f"{story_id} paths 非空时不能同时声明 x-no-api-change")

    operations: dict[str, dict[str, Any]] = {}
    methods = {"get", "put", "post", "delete", "options", "head", "patch", "trace"}
    for api_path, path_item in paths.items():
        if not isinstance(path_item, dict):
            errors.append(f"{story_id} path item 不是 object: {api_path}")
            continue
        for method, operation in path_item.items():
            if method.lower() not in methods:
                continue
            if not isinstance(operation, dict):
                errors.append(f"{story_id} operation 不是 object: {method.upper()} {api_path}")
                continue
            operation_id = operation.get("operationId")
            if not isinstance(operation_id, str) or not operation_id.strip():
                errors.append(f"{story_id} operation 缺少 operationId: {method.upper()} {api_path}")
                continue
            operation_id = operation_id.strip()
            if operation_id in operations:
                errors.append(f"{story_id} operationId 重复: {operation_id}")
                continue
            if "security" not in operation and "security" not in doc:
                errors.append(f"{story_id} operation 未声明鉴权语义: {operation_id}")
            responses = operation.get("responses")
            if not isinstance(responses, dict):
                errors.append(f"{story_id} operation 缺少 responses: {operation_id}")
            else:
                codes = {str(code) for code in responses}
                if not any(code.startswith("2") for code in codes):
                    errors.append(f"{story_id} operation 缺少成功响应: {operation_id}")
                if not any(code == "default" or code.startswith(("4", "5")) for code in codes):
                    errors.append(f"{story_id} operation 缺少错误响应: {operation_id}")
            operation_refs = operation.get("x-operation-refs")
            if not isinstance(operation_refs, list) or not operation_refs or not all(
                isinstance(ref, str) and ref.strip() for ref in operation_refs
            ):
                errors.append(f"{story_id} OpenAPI operation {operation_id} 缺少非空 x-operation-refs")
                operation_refs = []
            elif set(operation_refs) - story_operation_ids:
                errors.append(
                    f"{story_id} OpenAPI operation {operation_id} 引用未知操作: "
                    f"{', '.join(sorted(set(operation_refs) - story_operation_ids))}"
                )
            operations[operation_id] = {
                "method_path": f"{method.upper()} {api_path}",
                "deprecated": "true" if operation.get("deprecated") is True else "false",
                "operation_refs": operation_refs,
            }
    return operations


def _is_concrete_code_target(value: str) -> bool:
    value = value.strip()
    if len(value) < 4 or VAGUE_IMPLEMENTATION_RE.search(value):
        return False
    return not re.search(r"(?:相关代码|对应代码|某文件|待查找|待确认|path/to|example)", value, flags=re.I)


def validate_implementation(
    path: Path,
    story_id: str,
    ac_ids: set[str],
    requirement_ids: set[str],
    operation_ids: set[str],
    interface_capability_ids: set[str],
    ui_required: bool,
    operations: dict[str, dict[str, Any]],
    ui_surfaces: dict[str, dict[str, Any]],
    errors: list[str],
) -> tuple[set[str], set[str]]:
    """Validate applicable execution information without prescribing document chapters."""
    try:
        text = path.read_text(encoding="utf-8")
    except OSError as exc:
        errors.append(f"{story_id} AI 执行明细无法读取: {path}: {exc}")
        return set(), set()

    if story_id not in text:
        errors.append(f"{story_id} AI 执行明细缺少故事 ID")
    for reference in sorted(ac_ids | requirement_ids | operation_ids | interface_capability_ids):
        if reference not in text:
            errors.append(f"{story_id} AI 执行明细缺少追溯引用: {reference}")

    known_refs: set[str] = set(operations) | operation_ids | interface_capability_ids
    learning_rows = require_table(text, LEARNING_COLUMNS, story_id, "背景和学习索引", errors)
    learning_refs: set[str] = set()
    refs_by_type: dict[str, set[str]] = {}
    database_change = False
    for row in learning_rows:
        learning_ref = row["learning_ref"]
        if learning_ref in learning_refs:
            errors.append(f"{story_id} learning_ref 重复: {learning_ref}")
        learning_refs.add(learning_ref)
        source_type = row["source_type"].strip().lower()
        if not re.fullmatch(r"[a-z][a-z0-9_-]*", source_type):
            errors.append(
                f"{story_id} 学习索引 {learning_ref} 的 source_type 应为英文标识: "
                f"{row['source_type']!r}"
            )
        refs_by_type.setdefault(source_type, set()).add(learning_ref)
        if source_type == "database" and re.search(
            r"(?:\bnew\b|\bmodify\b|\bdelete\b|新增|修改|删除|迁移)",
            row["planned_use"],
            flags=re.I,
        ):
            database_change = True
        if not _is_concrete_code_target(row["location"]):
            errors.append(
                f"{story_id} 学习索引 {learning_ref} 未给出可检索位置: {row['location']!r}"
            )
        if len(row["verified_finding"].strip()) < 8:
            errors.append(f"{story_id} 学习索引 {learning_ref} 的 verified_finding 过于空泛")
    known_refs.update(learning_refs)
    if not refs_by_type.get("prd"):
        errors.append(f"{story_id} 背景和学习索引缺少 prd 来源")
    if ui_required and not (refs_by_type.get("frontend") or refs_by_type.get("architecture")):
        errors.append(f"{story_id} 涉及页面但学习索引缺少 frontend 或 architecture 入口")
    if operations and not (
        refs_by_type.get("backend")
        or refs_by_type.get("contract")
        or refs_by_type.get("architecture")
    ):
        errors.append(f"{story_id} 涉及接口但学习索引缺少 backend、contract 或 architecture 入口")
    if database_change:
        if "```sql" not in text.lower():
            errors.append(f"{story_id} 数据库变更缺少可执行 SQL 代码块")
        if not re.search(r"(?:回滚\s*SQL|rollback\s+sql)", text, flags=re.I):
            errors.append(f"{story_id} 数据库变更缺少回滚 SQL 或回滚说明")

    ui_contracts: set[str] = set()
    page_refs: set[str] = set()
    page_blocks = extract_entity_blocks(text, "页面")
    if ui_required or page_blocks:
        if not page_blocks:
            errors.append(f"{story_id} 缺少独立页面标题块，格式应为：### 页面 [page_ref] 页面名称")
        for page_ref, page_title, block in page_blocks:
            if page_ref in page_refs:
                errors.append(f"{story_id} page_ref 重复: {page_ref}")
            page_refs.add(page_ref)
            metadata = extract_entity_metadata(block)
            entity_label = f"页面 [{page_ref}] {page_title}"
            require_entity_metadata(
                metadata,
                ["变更类型", "交互载体类型", "页面类型", "路由或入口", "开发前学习", "可复用组件", "操作引用"],
                story_id,
                entity_label,
                errors,
            )
            change_type = metadata.get("变更类型", "").lower()
            if change_type not in ALLOWED_CHANGE_TYPES:
                errors.append(f"{story_id} 页面 {page_ref} 的 change_type 无效: {change_type!r}")
            if page_ref not in ui_surfaces:
                errors.append(f"{story_id} 页面标题块存在未进入确认清单的 surface_id: {page_ref}")
            elif metadata.get("交互载体类型", "").lower() != ui_surfaces[page_ref]["surface_type"]:
                errors.append(f"{story_id} 交互载体 {page_ref} 的类型与阶段 3 清单不一致")
            page_operation_refs = split_refs(metadata.get("操作引用", ""))
            expected_operation_refs = set(ui_surfaces.get(page_ref, {}).get("operation_refs", []))
            if page_operation_refs != expected_operation_refs:
                errors.append(f"{story_id} 页面 {page_ref} 的操作引用与确认基线不一致")
            known_refs.update(page_operation_refs)
            refs = split_refs(metadata.get("开发前学习", ""))
            unknown_refs = refs - learning_refs
            if not refs or unknown_refs:
                errors.append(
                    f"{story_id} 页面 {page_ref} 的 learning_refs 无效: "
                    f"{', '.join(sorted(unknown_refs)) or 'empty'}"
                )
            if change_type != "delete" and not re.search(r"(?:布局|区域|layout)", block, flags=re.I):
                errors.append(f"{story_id} 页面 {page_ref} 未说明页面布局或区域顺序")

            normalized_page_type = metadata.get("页面类型", "").lower()
            is_list = "list" in normalized_page_type or "列表" in metadata.get("页面类型", "")
            is_form = "form" in normalized_page_type or "表单" in metadata.get("页面类型", "")
            if change_type != "delete" and is_list:
                require_table(block, LIST_COLUMNS, story_id, f"页面 {page_ref} 列表行为", errors)
                list_field_rows = require_table(
                    block, LIST_FIELD_COLUMNS, story_id, f"页面 {page_ref} 列表列", errors
                )
                for row in list_field_rows:
                    known_refs.add(row["field"])
            else:
                for row in optional_table(block, LIST_FIELD_COLUMNS, story_id, f"页面 {page_ref} 列表列", errors):
                    known_refs.add(row["field"])

            for row in optional_table(block, QUERY_COLUMNS, story_id, f"页面 {page_ref} 查询条件", errors):
                known_refs.add(row["query_field"])

            if change_type != "delete" and is_form:
                form_rows = require_table(
                    block, FORM_FIELD_COLUMNS, story_id, f"页面 {page_ref} 表单字段", errors
                )
            else:
                form_rows = optional_table(
                    block, FORM_FIELD_COLUMNS, story_id, f"页面 {page_ref} 表单字段", errors
                )
            for row in form_rows:
                known_refs.add(row["field"])

            action_rows = optional_table(block, ACTION_COLUMNS, story_id, f"页面 {page_ref} 页面操作", errors)
            for row in action_rows:
                contract_id = row["contract_id"]
                if not contract_id.startswith("FRONTEND:"):
                    ui_contracts.add(contract_id)
                    if contract_id not in operations:
                        errors.append(f"{story_id} 操作 {row['action']} 引用未知 contract_id: {contract_id}")
                known_refs.add(row["action"])

            for row in optional_table(block, FLOW_COLUMNS, story_id, f"页面 {page_ref} 页面交互流程", errors):
                known_refs.add(row["flow"])
    missing_pages = set(ui_surfaces) - page_refs
    if missing_pages:
        errors.append(f"{story_id} AI 执行明细缺少确认页面: {', '.join(sorted(missing_pages))}")
    known_refs.update(page_refs)

    interface_blocks = extract_entity_blocks(text, "接口")
    if operations or interface_blocks:
        if not interface_blocks:
            errors.append(f"{story_id} 缺少独立接口标题块，格式应为：### 接口 [contract_id] 接口名称")
        described: set[str] = set()
        for contract_id, interface_title, block in interface_blocks:
            if contract_id in described:
                errors.append(f"{story_id} 接口重复描述 contract_id: {contract_id}")
            described.add(contract_id)
            if contract_id not in operations:
                errors.append(f"{story_id} 接口标题引用未知 contract_id: {contract_id}")
                continue
            metadata = extract_entity_metadata(block)
            entity_label = f"接口 [{contract_id}] {interface_title}"
            require_entity_metadata(
                metadata,
                ["变更类型", "Method/Path", "服务对象", "需求与验收", "开发前学习", "代码入口与调用链", "契约位置", "操作引用"],
                story_id,
                entity_label,
                errors,
            )
            change_type = metadata.get("变更类型", "").lower()
            if change_type not in ALLOWED_CHANGE_TYPES:
                errors.append(f"{story_id} 接口 {contract_id} 的 change_type 无效: {change_type!r}")
            interface_operation_refs = split_refs(metadata.get("操作引用", ""))
            expected_operation_refs = set(operations.get(contract_id, {}).get("operation_refs", []))
            if interface_operation_refs != expected_operation_refs:
                errors.append(f"{story_id} 接口 {contract_id} 的操作引用与确认基线不一致")
            known_refs.update(interface_operation_refs)
            if change_type == "delete" and operations[contract_id].get("deprecated") != "true":
                errors.append(f"{story_id} 删除接口 {contract_id} 必须在 OpenAPI 标记 deprecated=true")
            if metadata.get("Method/Path", "").upper() != operations[contract_id]["method_path"].upper():
                errors.append(f"{story_id} 接口 {contract_id} 的 method_path 与 OpenAPI 不一致")
            trace_refs = metadata.get("需求与验收", "")
            if not any(ref in trace_refs for ref in requirement_ids):
                errors.append(f"{story_id} 接口 {contract_id} 未说明对应需求")
            if not any(ref in trace_refs for ref in ac_ids):
                errors.append(f"{story_id} 接口 {contract_id} 未说明对应验收标准")
            refs = split_refs(metadata.get("开发前学习", ""))
            unknown_refs = refs - learning_refs
            if not refs or unknown_refs:
                errors.append(
                    f"{story_id} 接口 {contract_id} 的 learning_refs 无效: "
                    f"{', '.join(sorted(unknown_refs)) or 'empty'}"
                )
            code_chain = metadata.get("代码入口与调用链", "")
            if not _is_concrete_code_target(code_chain):
                errors.append(f"{story_id} 接口 {contract_id} 未给出具体代码入口与调用链")
            if not refs.intersection(set(re.findall(r"[A-Za-z][A-Za-z0-9_-]*", code_chain))):
                errors.append(f"{story_id} 接口 {contract_id} 的调用链未引用 learning_ref")
            if not re.search(r"(?:业务逻辑|处理流程|执行流程|实现步骤|内部流程)", block) or len(block.strip()) < 160:
                errors.append(f"{story_id} 接口 {contract_id} 缺少可执行的内部业务逻辑")
            if not re.search(r"(?:数据访问|数据读写|数据来源|持久化)", block):
                errors.append(f"{story_id} 接口 {contract_id} 未说明数据访问或数据来源")
            if not re.search(r"(?:失败|异常|错误|回滚|补偿)", block):
                errors.append(f"{story_id} 接口 {contract_id} 未说明失败或异常语义")

            mapping_rows = require_table(
                block, INTERFACE_FIELD_COLUMNS, story_id, f"接口 {contract_id} 字段映射", errors
            )
            if not mapping_rows:
                continue
        missing_contracts = set(operations) - described
        if missing_contracts:
            errors.append(f"{story_id} 缺少接口业务逻辑: {', '.join(sorted(missing_contracts))}")
        if ui_contracts - described:
            errors.append(f"{story_id} 页面操作缺少接口业务逻辑: {', '.join(sorted(ui_contracts - described))}")

    task_rows = require_table(text, TASK_COLUMNS, story_id, "AI 执行任务", errors)
    task_ids: set[str] = set()
    for row in task_rows:
        task_id = row["task_id"]
        if not re.fullmatch(rf"TASK-{re.escape(story_id)}-\d{{2,3}}", task_id):
            errors.append(f"{story_id} task_id 格式错误: {task_id}")
        if task_id in task_ids:
            errors.append(f"{story_id} task_id 重复: {task_id}")
        task_ids.add(task_id)
        if not _is_concrete_code_target(row["files_or_symbols"]):
            errors.append(f"{story_id} 任务 {task_id} 未给出具体文件或符号")
        if not split_refs(row["related_refs"]).intersection(learning_refs):
            errors.append(f"{story_id} 任务 {task_id} 未关联背景和学习索引 learning_ref")
    known_refs.update(task_ids)

    mapping_rows = require_table(text, OPERATION_MAPPING_COLUMNS, story_id, "操作实现映射", errors)
    mapped_operations: set[str] = set()
    mapped_contracts: set[str] = set()
    for row in mapping_rows:
        operation_id = row["operation_id"]
        if operation_id not in operation_ids:
            errors.append(f"{story_id} 操作实现映射引用未知 operation_id: {operation_id}")
        if operation_id in mapped_operations:
            errors.append(f"{story_id} 操作实现映射重复 operation_id: {operation_id}")
        mapped_operations.add(operation_id)
        kind = row["implementation_kind"].lower()
        if kind not in ALLOWED_IMPLEMENTATION_KINDS:
            errors.append(f"{story_id} 操作 {operation_id} implementation_kind 无效: {kind!r}")
        surface_refs = set() if row["ui_surface_refs"].upper() == "NONE" else split_refs(row["ui_surface_refs"])
        contract_refs = set() if row["contract_ids"].upper() == "NONE" else split_refs(row["contract_ids"])
        implementation_refs = split_refs(row["implementation_refs"])
        if surface_refs - set(ui_surfaces):
            errors.append(f"{story_id} 操作 {operation_id} 引用未知 ui_surface: {', '.join(sorted(surface_refs - set(ui_surfaces)))}")
        if contract_refs - set(operations):
            errors.append(f"{story_id} 操作 {operation_id} 引用未知 contract_id: {', '.join(sorted(contract_refs - set(operations)))}")
        for contract_id in contract_refs & set(operations):
            if operation_id not in set(operations[contract_id].get("operation_refs", [])):
                errors.append(f"{story_id} 接口 {contract_id} 未在 x-operation-refs 中反向引用 {operation_id}")
        if kind in {"http_api", "mixed"} and not contract_refs:
            errors.append(f"{story_id} 操作 {operation_id} 的 {kind} 必须关联 contract_id")
        if kind in {"frontend_only", "navigation", "database_only"} and contract_refs:
            errors.append(f"{story_id} 操作 {operation_id} 的 {kind} 不应关联 HTTP contract_id")
        if not implementation_refs.intersection(known_refs):
            errors.append(f"{story_id} 操作 {operation_id} 未关联已知页面、接口、学习资料或任务")
        if len(row["decision_basis"].strip()) < 8:
            errors.append(f"{story_id} 操作 {operation_id} 的 decision_basis 过于空泛")
        mapped_contracts.update(contract_refs)
    if operation_ids - mapped_operations:
        errors.append(f"{story_id} 操作实现映射未覆盖操作: {', '.join(sorted(operation_ids - mapped_operations))}")
    if mapped_operations - operation_ids:
        errors.append(f"{story_id} 操作实现映射存在范围外操作: {', '.join(sorted(mapped_operations - operation_ids))}")
    if set(operations) - mapped_contracts:
        errors.append(f"{story_id} OpenAPI 接口未被操作实现映射引用: {', '.join(sorted(set(operations) - mapped_contracts))}")

    acceptance_rows = require_table(text, ACCEPTANCE_COLUMNS, story_id, "验收映射", errors)
    mapped_acs: set[str] = set()
    expected_cases: set[str] = set()
    for row in acceptance_rows:
        ac_id = row["acceptance_criterion_id"]
        if ac_id not in ac_ids:
            errors.append(f"{story_id} 验收映射引用未知 AC: {ac_id}")
        if ac_id in mapped_acs:
            errors.append(f"{story_id} 验收映射重复 AC: {ac_id}")
        mapped_acs.add(ac_id)
        refs = split_refs(row["implementation_refs"])
        if not refs.intersection(known_refs):
            errors.append(f"{story_id} 的 {ac_id} 未关联已知页面、接口、学习资料或任务")
        for case_id in split_refs(row["test_case_ids"]):
            if not re.fullmatch(rf"TC-{re.escape(story_id)}-\d{{3}}", case_id):
                errors.append(f"{story_id} 验收映射 test_case_id 格式错误: {case_id}")
            expected_cases.add(case_id)
    if ac_ids - mapped_acs:
        errors.append(f"{story_id} 验收映射未覆盖 AC: {', '.join(sorted(ac_ids - mapped_acs))}")

    placeholder = PLACEHOLDER_RE.search(text)
    if placeholder:
        errors.append(f"{story_id} AI 执行明细包含占位符: {placeholder.group(0)!r}")
    vague = VAGUE_IMPLEMENTATION_RE.search(text)
    if vague:
        errors.append(f"{story_id} AI 执行明细包含不可执行的模糊表述: {vague.group(0)!r}")
    return known_refs, expected_cases


def validate_tests(
    path: Path,
    story_id: str,
    ac_ids: set[str],
    requirement_ids: set[str],
    operation_ids: set[str],
    known_refs: set[str],
    expected_case_ids: set[str],
    errors: list[str],
) -> None:
    try:
        with path.open("r", encoding="utf-8-sig", newline="") as handle:
            reader = csv.DictReader(handle)
            if reader.fieldnames != CSV_HEADER:
                errors.append(f"{story_id} 测试 CSV 表头不符合规范: {reader.fieldnames}")
                return
            rows = list(reader)
    except (OSError, csv.Error) as exc:
        errors.append(f"{story_id} 测试 CSV 无法解析: {path}: {exc}")
        return
    if not rows:
        errors.append(f"{story_id} 测试 CSV 不能为空")
        return
    seen_cases: set[str] = set()
    covered_acs: set[str] = set()
    covered_operations: set[str] = set()
    types_by_ac: dict[str, set[str]] = {ac_id: set() for ac_id in ac_ids}
    allowed_statuses = {"not_run", "passed", "failed", "blocked", "skipped"}
    for line_no, row in enumerate(rows, start=2):
        missing = [field for field in CSV_HEADER if not (row.get(field) or "").strip()]
        if missing:
            errors.append(f"{story_id} 测试 CSV 第 {line_no} 行缺失字段: {', '.join(missing)}")
        case_id = row.get("case_id", "")
        if not re.fullmatch(rf"TC-{re.escape(story_id)}-\d{{3}}", case_id):
            errors.append(f"{story_id} 测试第 {line_no} 行 case_id 格式错误: {case_id!r}")
        if case_id in seen_cases:
            errors.append(f"{story_id} 测试 case_id 重复: {case_id}")
        seen_cases.add(case_id)
        if row.get("story_id") != story_id:
            errors.append(f"{story_id} 测试第 {line_no} 行 story_id 不匹配")
        ac_id = row.get("acceptance_criterion_id", "")
        if ac_id not in ac_ids:
            errors.append(f"{story_id} 测试第 {line_no} 行引用未知 AC: {ac_id}")
        else:
            covered_acs.add(ac_id)
            types_by_ac[ac_id].add(row.get("test_type", ""))
        reqs = split_refs(row.get("requirement_ref", ""))
        if not reqs or not reqs.issubset(requirement_ids):
            errors.append(f"{story_id} 测试第 {line_no} 行 requirement_ref 无效: {row.get('requirement_ref')!r}")
        refs = split_refs(row.get("implementation_refs", ""))
        if not refs or not refs.intersection(known_refs):
            errors.append(f"{story_id} 测试第 {line_no} 行 implementation_refs 未关联执行明细")
        covered_operations.update(refs & operation_ids)
        if row.get("automation_candidate") not in {"yes", "no"}:
            errors.append(f"{story_id} 测试第 {line_no} 行 automation_candidate 必须为 yes/no")
        if row.get("test_level") not in ALLOWED_TEST_LEVELS:
            errors.append(f"{story_id} 测试第 {line_no} 行 test_level 无效: {row.get('test_level')!r}")
        if row.get("test_type") not in ALLOWED_TEST_TYPES:
            errors.append(f"{story_id} 测试第 {line_no} 行 test_type 无效: {row.get('test_type')!r}")
        if row.get("status") not in allowed_statuses:
            errors.append(f"{story_id} 测试第 {line_no} 行 status 无效: {row.get('status')!r}")
    if ac_ids - covered_acs:
        errors.append(f"{story_id} 测试未覆盖 AC: {', '.join(sorted(ac_ids - covered_acs))}")
    if operation_ids - covered_operations:
        errors.append(f"{story_id} 测试未引用操作: {', '.join(sorted(operation_ids - covered_operations))}")
    if expected_case_ids != seen_cases:
        missing = expected_case_ids - seen_cases
        extra = seen_cases - expected_case_ids
        if missing:
            errors.append(f"{story_id} CSV 缺少执行明细声明的用例: {', '.join(sorted(missing))}")
        if extra:
            errors.append(f"{story_id} CSV 含执行明细未声明的用例: {', '.join(sorted(extra))}")
    for ac_id, test_types in sorted(types_by_ac.items()):
        if "positive" not in test_types:
            errors.append(f"{story_id} 的 {ac_id} 缺少 positive 用例")


def validate_tracker(data: dict[str, Any], tracker_path: Path, check_artifacts: bool) -> list[str]:
    errors: list[str] = []
    missing_root = sorted(REQUIRED_ROOT_KEYS - data.keys())
    if missing_root:
        errors.append(f"根节点缺少字段: {', '.join(missing_root)}")
    if data.get("schema_version") != "1.6":
        if data.get("schema_version") in {"1.0", "1.1"}:
            errors.append(
                f"schema_version {data.get('schema_version')} 缺少稳定的 PRD 操作台账和逻辑交互载体；"
                "必须回到阶段 3逐故事重建确认 MD，并由用户确认后升级为 '1.6'"
            )
        elif data.get("schema_version") == "1.2":
            errors.append(
                "schema_version 1.2 缺少 PRD 功能点覆盖台账；"
                "必须回到阶段 3重建操作台账和确认 MD，并由用户确认后升级为 '1.6'"
            )
        elif data.get("schema_version") == "1.3":
            errors.append(
                "schema_version 1.3 的功能点 ID 随故事变化且缺少稳定 PRD 操作台账；"
                "必须回到阶段 3建立 prd_operation_catalog、interface_capability_catalog 和确认 MD，"
                "并由用户确认后升级为 '1.6'"
            )
        elif data.get("schema_version") == "1.4":
            errors.append(
                "schema_version 1.4 将接口 Method/Path 与技术变更类型提前放入阶段 3；"
                "必须回到阶段 3移除技术设计，改用 ui_surfaces 和确认 MD 后由用户确认升级为 '1.6'"
            )
        elif data.get("schema_version") == "1.5":
            errors.append(
                "schema_version 1.5 缺少确认 Markdown hash、接口业务能力目录或故事接口能力引用；"
                "必须回到阶段 3补齐 AI执行清单确认.md 并由用户确认后升级为 '1.6'"
            )
        else:
            errors.append("schema_version 必须为 '1.6'")
    project = data.get("project")
    if not isinstance(project, dict):
        errors.append("project 必须是 object")
        project = {}
    else:
        for field in ("name", "output_root", "baseline_id", "material_manifest"):
            if not isinstance(project.get(field), str) or not project.get(field, "").strip():
                errors.append(f"project.{field} 必须是非空字符串")
        if project.get("technical_selection") is not None and (
            not isinstance(project.get("technical_selection"), str)
            or not project.get("technical_selection", "").strip()
        ):
            errors.append("project.technical_selection 必须是 null 或非空字符串")
        if project.get("output_root") != ".":
            errors.append("project.output_root 必须为 '.'，产物路径相对于跟踪文件所在目录")
    if not isinstance(data.get("catalog_confirmed"), bool):
        errors.append("catalog_confirmed 必须是 boolean")
    elif not data.get("catalog_confirmed"):
        errors.append("正式 AI执行清单.json 的 catalog_confirmed 必须为 true")
    if not is_timezone_timestamp(data.get("catalog_confirmed_at")):
        errors.append("catalog_confirmed_at 必须是带时区的 ISO 8601 时间")
    if not is_timezone_timestamp(data.get("generated_at")):
        errors.append("generated_at 必须是带时区的 ISO 8601 时间")
    root = tracker_path.parent.resolve()
    validate_confirmation_document(data, root, errors)
    stories = data.get("stories")
    if not isinstance(stories, list) or not stories:
        errors.append("stories 必须是非空 array")
        return errors

    catalog_operations = validate_operation_catalog(
        data,
        {item.get("id") for item in stories if isinstance(item, dict) and isinstance(item.get("id"), str)},
        errors,
    )
    interface_capabilities = validate_interface_capability_catalog(
        data,
        {item.get("id") for item in stories if isinstance(item, dict) and isinstance(item.get("id"), str)},
        catalog_operations,
        errors,
    )

    ids: set[str] = set()
    sequences: set[int] = set()
    graph: dict[str, list[str]] = {}
    normalized: list[tuple[int, dict[str, Any]]] = []
    if check_artifacts and project:
        manifest = safe_artifact_path(root, project.get("material_manifest"), "project.material_manifest", errors)
        if manifest is not None:
            if not manifest.is_file():
                errors.append(f"缺少已确认物料清单: {manifest}")
            elif not re.search(
                r"(?m)^confirmation_status:\s*[\"']?confirmed[\"']?\s*$",
                manifest.read_text(encoding="utf-8"),
            ):
                errors.append(f"物料清单未标记为 confirmed: {manifest}")
            else:
                manifest_text = manifest.read_text(encoding="utf-8")
                baseline_match = re.search(
                    r"(?m)^baseline_id:\s*[\"']?([^\"'\s]+)[\"']?\s*$", manifest_text
                )
                if not baseline_match or baseline_match.group(1) != project.get("baseline_id"):
                    errors.append(f"物料清单 baseline_id 与跟踪文件不一致: {manifest}")
        selection_value = project.get("technical_selection")
        if selection_value is not None:
            selection = safe_artifact_path(root, selection_value, "project.technical_selection", errors)
            if selection is not None:
                if not selection.is_file():
                    errors.append(f"缺少已确认技术选型清单: {selection}")
                elif not re.search(
                    r"(?m)^confirmation_status:\s*[\"']?confirmed[\"']?\s*$",
                    selection.read_text(encoding="utf-8"),
                ):
                    errors.append(f"技术选型清单未标记为 confirmed: {selection}")

    for index, story in enumerate(stories):
        label = f"stories[{index}]"
        if not isinstance(story, dict):
            errors.append(f"{label} 必须是 object")
            continue
        reject_stage_3_technical_fields(story, label, errors)
        missing = sorted(REQUIRED_STORY_KEYS - story.keys())
        if missing:
            errors.append(f"{label} 缺少字段: {', '.join(missing)}")
        story_id = story.get("id")
        if not isinstance(story_id, str) or not STORY_ID_RE.fullmatch(story_id):
            errors.append(f"{label}.id 格式错误: {story_id!r}")
            story_id = str(story_id)
        elif story_id in ids:
            errors.append(f"故事 ID 重复: {story_id}")
        ids.add(story_id)
        sequence = story.get("sequence")
        if not isinstance(sequence, int) or isinstance(sequence, bool) or sequence < 1:
            errors.append(f"{story_id}.sequence 必须是正整数")
            sequence = index + 1
        elif sequence in sequences:
            errors.append(f"sequence 重复: {sequence}")
        sequences.add(sequence)
        normalized.append((sequence, story))
        if story.get("priority") not in {"P0", "P1", "P2", "P3"}:
            errors.append(f"{story_id}.priority 必须为 P0/P1/P2/P3")
        ui_required_value = story.get("ui_required")
        if not isinstance(ui_required_value, bool):
            errors.append(f"{story_id}.ui_required 必须是 boolean")
            ui_required = False
        else:
            ui_required = ui_required_value
        validate_story_card(story_id, story.get("name"), story.get("user_story"), errors)
        file_stem = story.get("file_stem")
        if not isinstance(file_stem, str) or not file_stem.strip() or re.search(r"[/\\:*?\"<>|\x00-\x1f]", file_stem):
            errors.append(f"{story_id}.file_stem 为空或包含不安全字符")
            file_stem = str(file_stem)
        elif not file_stem.startswith(f"{story_id}-"):
            errors.append(f"{story_id}.file_stem 必须以 {story_id}- 开头")
        elif len(file_stem) > 80:
            errors.append(f"{story_id}.file_stem 不能超过 80 个字符")
        elif isinstance(story.get("name"), str) and file_stem != f"{story_id}-{story['name'].strip()}":
            errors.append(f"{story_id}.file_stem 必须等于故事 ID 与 name 的组合: {story_id}-{story['name'].strip()}")
        if not isinstance(story.get("prd_refs"), list) or not story.get("prd_refs"):
            errors.append(f"{story_id}.prd_refs 必须是非空 array")
        if not isinstance(story.get("acceptance_criteria"), list) or not story.get("acceptance_criteria"):
            errors.append(f"{story_id}.acceptance_criteria 必须是非空 array")
        scope = story.get("scope")
        if not isinstance(scope, dict) or not all(
            isinstance(scope.get(key), list) and all(isinstance(value, str) and value.strip() for value in scope[key])
            for key in ("in", "out")
        ):
            errors.append(f"{story_id}.scope 必须包含字符串 array: in/out")
        if not isinstance(story.get("risks"), list):
            errors.append(f"{story_id}.risks 必须是 array")
        for field in ("plan_generated", "development_completed", "self_test_completed", "plan_stale"):
            if not isinstance(story.get(field), bool):
                errors.append(f"{story_id}.{field} 必须是 boolean")
        if story.get("development_completed") and not story.get("plan_generated"):
            errors.append(f"{story_id} 研发完成要求计划已生成")
        if story.get("self_test_completed") and not story.get("development_completed"):
            errors.append(f"{story_id} 自测完成要求研发已完成")
        if story.get("plan_stale") and not story.get("plan_generated"):
            errors.append(f"{story_id} 只有已生成过的计划才能标记 plan_stale=true")
        if not is_timezone_timestamp(story.get("last_updated_at")):
            errors.append(f"{story_id}.last_updated_at 必须是带时区的 ISO 8601 时间")
        blocked = story.get("blocked_reason")
        if blocked is not None and (not isinstance(blocked, str) or not blocked.strip()):
            errors.append(f"{story_id}.blocked_reason 必须为 null 或非空字符串")
        if blocked and story.get("plan_generated"):
            errors.append(f"{story_id} 有阻塞原因时不能标记 plan_generated=true")
        dependencies = story.get("depends_on")
        if not isinstance(dependencies, list) or not all(isinstance(value, str) for value in dependencies):
            errors.append(f"{story_id}.depends_on 必须是字符串 array")
            dependencies = []
        elif len(set(dependencies)) != len(dependencies):
            errors.append(f"{story_id}.depends_on 不能包含重复项")
        graph[story_id] = dependencies

        ac_ids: set[str] = set()
        for ac in story.get("acceptance_criteria", []) if isinstance(story.get("acceptance_criteria"), list) else []:
            if not isinstance(ac, dict) or not AC_ID_RE.fullmatch(str(ac.get("id", ""))) or not str(ac.get("text", "")).strip():
                errors.append(f"{story_id} acceptance_criteria 项必须含合法 id 和非空 text")
                continue
            if not ac["id"].startswith(f"AC-{story_id}-"):
                errors.append(f"{story_id} AC ID 必须以 AC-{story_id}- 开头: {ac['id']}")
            if ac["id"] in ac_ids:
                errors.append(f"{story_id} AC ID 重复: {ac['id']}")
            ac_ids.add(ac["id"])
            ac_text = str(ac["text"]).strip()
            if VAGUE_AC_RE.search(ac_text):
                errors.append(f"{story_id} {ac['id']} 包含不可测试的模糊验收表述")
            gwt_tokens = {token for token in ("given", "when", "then") if re.search(rf"\b{token}\b", ac_text, flags=re.I)}
            if gwt_tokens and gwt_tokens != {"given", "when", "then"}:
                errors.append(f"{story_id} {ac['id']} 使用 Given-When-Then 时必须三部分完整")
            op_refs = ac.get("operation_refs")
            if not isinstance(op_refs, list) or not op_refs or not all(isinstance(ref, str) for ref in op_refs):
                errors.append(f"{story_id} {ac.get('id')} 必须含非空 operation_refs")

        requirement_ids = {
            str(ref.get("requirement_id"))
            for ref in story.get("prd_refs", [])
            if isinstance(ref, dict) and ref.get("requirement_id") and ref.get("source_id") and ref.get("locator")
        }
        if len(requirement_ids) != len(story.get("prd_refs", [])):
            errors.append(f"{story_id}.prd_refs 每项必须含 requirement_id/source_id/locator")

        operation_refs = story.get("operation_refs")
        if not isinstance(operation_refs, list) or not operation_refs or not all(
            isinstance(ref, str) and OPERATION_ID_RE.fullmatch(ref) for ref in operation_refs
        ):
            errors.append(f"{story_id}.operation_refs 必须是非空 OP-* 字符串 array")
            operation_refs = []
        if len(set(operation_refs)) != len(operation_refs):
            errors.append(f"{story_id}.operation_refs 不能重复")
        story_operations = {ref: catalog_operations.get(ref) for ref in operation_refs}
        unknown_operations = set(operation_refs) - set(catalog_operations)
        if unknown_operations:
            errors.append(f"{story_id}.operation_refs 引用未登记操作: {', '.join(sorted(unknown_operations))}")
        for operation_id, operation in story_operations.items():
            if operation and operation.get("story_id") != story_id:
                errors.append(f"{story_id} operation {operation_id} 的 catalog story_id 不一致")
        covered_for_story = {
            operation_id for operation_id, operation in catalog_operations.items()
            if operation.get("coverage_status") == "covered" and operation.get("story_id") == story_id
        }
        if covered_for_story != set(operation_refs):
            errors.append(
                f"{story_id} operation_refs 必须完整覆盖本故事 catalog 操作；"
                f"缺少 {', '.join(sorted(covered_for_story - set(operation_refs))) or '无'}，"
                f"多出 {', '.join(sorted(set(operation_refs) - covered_for_story)) or '无'}"
            )
        capability_refs = story.get("interface_capability_refs")
        if not isinstance(capability_refs, list) or not all(
            isinstance(ref, str) and INTERFACE_CAPABILITY_ID_RE.fullmatch(ref) for ref in capability_refs
        ):
            errors.append(f"{story_id}.interface_capability_refs 必须是接口能力 ID 字符串 array")
            capability_refs = []
        if len(set(capability_refs)) != len(capability_refs):
            errors.append(f"{story_id}.interface_capability_refs 不能重复")
        unknown_capabilities = set(capability_refs) - set(interface_capabilities)
        if unknown_capabilities:
            errors.append(
                f"{story_id}.interface_capability_refs 引用未登记接口能力: "
                f"{', '.join(sorted(unknown_capabilities))}"
            )
        for capability_id in set(capability_refs) & set(interface_capabilities):
            capability = interface_capabilities[capability_id]
            if capability.get("story_id") != story_id:
                errors.append(f"{story_id} 接口能力 {capability_id} 的 story_id 不一致")
            if set(capability.get("operation_refs", [])) - set(operation_refs):
                errors.append(
                    f"{story_id} 接口能力 {capability_id} 引用了其他故事操作: "
                    f"{', '.join(sorted(set(capability.get('operation_refs', [])) - set(operation_refs)))}"
                )
        story_capabilities = {
            capability_id for capability_id, capability in interface_capabilities.items()
            if capability.get("story_id") == story_id
        }
        if story_capabilities != set(capability_refs):
            errors.append(
                f"{story_id} interface_capability_refs 必须完整覆盖本故事接口能力；"
                f"缺少 {', '.join(sorted(story_capabilities - set(capability_refs))) or '无'}，"
                f"多出 {', '.join(sorted(set(capability_refs) - story_capabilities)) or '无'}"
            )
        ac_operation_refs: set[str] = set()
        for ac in story.get("acceptance_criteria", []) if isinstance(story.get("acceptance_criteria"), list) else []:
            if isinstance(ac, dict) and isinstance(ac.get("operation_refs"), list):
                ac_operation_refs.update(ref for ref in ac["operation_refs"] if isinstance(ref, str))
                unknown = set(ac["operation_refs"]) - set(operation_refs)
                if unknown:
                    errors.append(f"{story_id} {ac.get('id')} operation_refs 引用其他故事或未知操作: {', '.join(sorted(unknown))}")
        if set(operation_refs) - ac_operation_refs:
            errors.append(f"{story_id} acceptance_criteria 未覆盖操作: {', '.join(sorted(set(operation_refs) - ac_operation_refs))}")

        ui_surfaces = validate_ui_surfaces(
            story,
            story_id,
            requirement_ids,
            ac_ids,
            set(operation_refs),
            ui_required,
            errors,
        )
        for operation_id in operation_refs:
            operation = catalog_operations.get(operation_id)
            if not operation:
                continue
            surface_refs = set(operation.get("ui_surface_refs", []))
            if surface_refs - set(ui_surfaces):
                errors.append(
                    f"{story_id} 操作 {operation_id} 引用未进入 ui_surfaces: "
                    f"{', '.join(sorted(surface_refs - set(ui_surfaces)))}"
                )
            for surface_id in surface_refs & set(ui_surfaces):
                if operation_id not in set(ui_surfaces[surface_id].get("operation_refs", [])):
                    errors.append(f"{story_id} 交互载体 {surface_id} 未反向引用操作 {operation_id}")

        artifacts = story.get("artifacts")
        if not isinstance(artifacts, dict):
            errors.append(f"{story_id}.artifacts 必须是 object")
            artifacts = {}
        else:
            missing_artifacts = sorted(REQUIRED_ARTIFACT_KEYS - artifacts.keys())
            if missing_artifacts:
                errors.append(f"{story_id}.artifacts 缺少: {', '.join(missing_artifacts)}")

        artifact_paths: dict[str, Path | None] = {
            key: safe_artifact_path(root, artifacts.get(key), f"{story_id}.artifacts.{key}", errors)
            for key in REQUIRED_ARTIFACT_KEYS
        }
        suffixes = {"contract": "接口契约.json", "implementation": "AI执行明细.md", "tests": "测试用例.csv"}
        for key, artifact_path in artifact_paths.items():
            if artifact_path is not None:
                expected_name = f"{file_stem}{suffixes[key]}"
                if artifact_path.name != expected_name or artifact_path.parent.name != file_stem:
                    errors.append(
                        f"{story_id}.artifacts.{key} 应位于 {file_stem}/ 且文件名为 {expected_name}"
                    )
        has_any_artifact = any(path is not None and path.is_file() for path in artifact_paths.values())
        if check_artifacts and (story.get("plan_generated") or has_any_artifact):
            for key, artifact_path in artifact_paths.items():
                if artifact_path is not None and not artifact_path.is_file():
                    errors.append(f"{story_id} 已标记计划生成但缺少 {key}: {artifact_path}")
            contract = artifact_paths.get("contract")
            implementation = artifact_paths.get("implementation")
            tests = artifact_paths.get("tests")
            operations: dict[str, dict[str, Any]] = {}
            if contract and contract.is_file():
                operations = validate_openapi(
                    contract, story_id, ac_ids, requirement_ids, set(operation_refs), errors
                )
            design_ids: set[str] = set()
            required_ui_test_types: set[str] = set()
            if implementation and implementation.is_file():
                design_ids, required_ui_test_types = validate_implementation(
                    implementation,
                    story_id,
                    ac_ids,
                    requirement_ids,
                    set(operation_refs),
                    set(capability_refs),
                    ui_required,
                    operations,
                    ui_surfaces,
                    errors,
                )
            if tests and tests.is_file():
                validate_tests(
                    tests,
                    story_id,
                    ac_ids,
                    requirement_ids,
                    set(operation_refs),
                    design_ids,
                    required_ui_test_types,
                    errors,
                )

    for story_id, dependencies in graph.items():
        for dependency in dependencies:
            if dependency not in ids:
                errors.append(f"{story_id} 引用不存在的依赖: {dependency}")
            if dependency == story_id:
                errors.append(f"{story_id} 不能依赖自身")
            dependency_sequence = next(
                (sequence for sequence, story in normalized if story.get("id") == dependency), None
            )
            story_sequence = next((sequence for sequence, story in normalized if story.get("id") == story_id), None)
            if dependency_sequence is not None and story_sequence is not None and dependency_sequence >= story_sequence:
                errors.append(f"{story_id} 的依赖 {dependency} 必须排在它之前")
    cycle = find_cycle(graph)
    if cycle:
        errors.append(f"故事依赖存在环: {' -> '.join(cycle)}")
    ordered_sequences = sorted(sequences)
    if ordered_sequences != list(range(1, len(ordered_sequences) + 1)):
        errors.append(f"sequence 必须从 1 连续递增，当前为 {ordered_sequences}")

    return errors


def ordered_stories(data: dict[str, Any]) -> list[dict[str, Any]]:
    stories = data.get("stories")
    if not isinstance(stories, list):
        return []
    return sorted((story for story in stories if isinstance(story, dict)), key=lambda item: item.get("sequence", 10**9))


def command_validate(args: argparse.Namespace) -> int:
    path = Path(args.tracker).resolve()
    try:
        data = load_tracker(path)
    except TrackerError as exc:
        print(f"ERROR: {exc}", file=sys.stderr)
        return 1
    errors = validate_tracker(data, path, args.check_artifacts)
    if errors:
        for error in errors:
            print(f"ERROR: {error}", file=sys.stderr)
        print(f"INVALID: {len(errors)} error(s)", file=sys.stderr)
        return 1
    print(f"VALID: {path}")
    return 0


def select_next(data: dict[str, Any], phase: str) -> dict[str, Any] | None:
    stories = ordered_stories(data)
    if phase == "plan":
        candidates = [story for story in stories if not story.get("plan_generated") or story.get("plan_stale")]
    elif phase == "development":
        candidates = [story for story in stories if story.get("plan_generated") and not story.get("plan_stale") and not story.get("development_completed")]
    else:
        candidates = [
            story
            for story in stories
            if story.get("plan_generated")
            and not story.get("plan_stale")
            and story.get("development_completed")
            and not story.get("self_test_completed")
        ]
    return candidates[0] if candidates else None


def command_next(args: argparse.Namespace) -> int:
    path = Path(args.tracker).resolve()
    try:
        data = load_tracker(path)
    except TrackerError as exc:
        print(f"ERROR: {exc}", file=sys.stderr)
        return 1
    errors = validate_tracker(data, path, False)
    if errors:
        for error in errors:
            print(f"ERROR: {error}", file=sys.stderr)
        return 1
    story = select_next(data, args.phase)
    if story is None:
        print(json.dumps({"phase": args.phase, "next": None}, ensure_ascii=False, indent=2))
    else:
        print(json.dumps({"phase": args.phase, "next": story}, ensure_ascii=False, indent=2))
    return 0


def command_status(args: argparse.Namespace) -> int:
    path = Path(args.tracker).resolve()
    try:
        data = load_tracker(path)
    except TrackerError as exc:
        print(f"ERROR: {exc}", file=sys.stderr)
        return 1
    errors = validate_tracker(data, path, False)
    if errors:
        for error in errors:
            print(f"ERROR: {error}", file=sys.stderr)
        return 1
    stories = ordered_stories(data)
    summary = {
        "total": len(stories),
        "plan_generated": sum(bool(story.get("plan_generated")) and not bool(story.get("plan_stale")) for story in stories),
        "plan_stale": sum(bool(story.get("plan_stale")) for story in stories),
        "development_completed": sum(bool(story.get("development_completed")) for story in stories),
        "self_test_completed": sum(bool(story.get("self_test_completed")) for story in stories),
        "downstream_revalidation_required": sum(
            bool(story.get("plan_stale"))
            and (bool(story.get("development_completed")) or bool(story.get("self_test_completed")))
            for story in stories
        ),
        "blocked": sum(bool(story.get("blocked_reason")) for story in stories),
        "next_plan": (select_next(data, "plan") or {}).get("id"),
        "next_development": (select_next(data, "development") or {}).get("id"),
        "next_self_test": (select_next(data, "self-test") or {}).get("id"),
    }
    print(json.dumps(summary, ensure_ascii=False, indent=2))
    return 0


def parse_bool(value: str) -> bool:
    return value.lower() == "true"


def command_set(args: argparse.Namespace) -> int:
    path = Path(args.tracker).resolve()
    try:
        data = load_tracker(path)
    except TrackerError as exc:
        print(f"ERROR: {exc}", file=sys.stderr)
        return 1
    stories = data.get("stories", [])
    story = next((item for item in stories if isinstance(item, dict) and item.get("id") == args.story_id), None)
    if story is None:
        print(f"ERROR: 未找到故事 {args.story_id}", file=sys.stderr)
        return 1
    if args.field == "plan_generated" and parse_bool(args.value) and not args.check_artifacts:
        print("ERROR: 将 plan_generated 设为 true 时必须传入 --check-artifacts", file=sys.stderr)
        return 1
    if (
        args.field == "plan_generated"
        and parse_bool(args.value)
        and story.get("plan_stale")
        and (story.get("development_completed") or story.get("self_test_completed"))
        and not args.acknowledge_downstream_status
    ):
        print(
            "ERROR: 该故事的旧研发/自测状态仍为 true；请先由用户确认这些状态在新基线下仍有效，"
            "或重置它们。确认保留时传入 --acknowledge-downstream-status",
            file=sys.stderr,
        )
        return 1
    old_value = story.get(args.field)
    story[args.field] = parse_bool(args.value)
    if args.field == "plan_generated" and story[args.field]:
        story["plan_stale"] = False
    story["last_updated_at"] = datetime.now(timezone.utc).astimezone().isoformat(timespec="seconds")
    errors = validate_tracker(data, path, args.check_artifacts)
    if errors:
        for error in errors:
            print(f"ERROR: {error}", file=sys.stderr)
        print("未写入：修改会导致跟踪文件无效", file=sys.stderr)
        return 1
    write_tracker(path, data)
    print(json.dumps({"story_id": args.story_id, "field": args.field, "old": old_value, "new": story[args.field]}, ensure_ascii=False))
    return 0


def build_parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(description=__doc__)
    subparsers = parser.add_subparsers(dest="command", required=True)

    validate = subparsers.add_parser("validate", help="校验跟踪文件和可选产物")
    validate.add_argument("tracker")
    validate.add_argument("--check-artifacts", action="store_true")
    validate.set_defaults(func=command_validate)

    next_parser = subparsers.add_parser("next", help="查找下一条待处理故事")
    next_parser.add_argument("tracker")
    next_parser.add_argument("--phase", choices=["plan", "development", "self-test"], default="plan")
    next_parser.set_defaults(func=command_next)

    status = subparsers.add_parser("status", help="输出状态统计")
    status.add_argument("tracker")
    status.set_defaults(func=command_status)

    set_parser = subparsers.add_parser("set", help="安全修改布尔状态")
    set_parser.add_argument("tracker")
    set_parser.add_argument("story_id")
    set_parser.add_argument("--field", choices=["plan_generated", "development_completed", "self_test_completed"], required=True)
    set_parser.add_argument("--value", choices=["true", "false"], required=True)
    set_parser.add_argument("--check-artifacts", action="store_true")
    set_parser.add_argument("--acknowledge-downstream-status", action="store_true")
    set_parser.set_defaults(func=command_set)

    return parser


def main() -> int:
    args = build_parser().parse_args()
    return args.func(args)


if __name__ == "__main__":
    sys.exit(main())
