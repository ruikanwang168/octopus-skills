#!/usr/bin/env python3
"""Regression tests for the execution-ready tracker contract."""

from __future__ import annotations

import csv
import hashlib
import json
import subprocess
import tempfile
import unittest
from pathlib import Path


SCRIPT = Path(__file__).with_name("tracker.py")
CONFIRMATION_MD = "confirmation_status: confirmed\ncatalog_revision: CAT-001\n"
CONFIRMATION_HASH = "sha256:" + hashlib.sha256(CONFIRMATION_MD.encode("utf-8")).hexdigest()
CSV_HEADER = [
    "case_id", "story_id", "acceptance_criterion_id", "requirement_ref",
    "implementation_refs", "test_level", "test_type", "title", "priority",
    "preconditions", "steps", "test_data", "expected_result",
    "automation_candidate", "environment", "status",
]


def table(headers: list[str], rows: list[list[str]]) -> str:
    return "\n".join([
        "| " + " | ".join(headers) + " |",
        "| " + " | ".join("---" for _ in headers) + " |",
        *["| " + " | ".join(row) + " |" for row in rows],
    ])


def story(ui_required: bool = True, has_api: bool = True) -> dict:
    stem = "US-001-创建记录"
    return {
        "sequence": 1,
        "id": "US-001",
        "name": "创建记录",
        "file_stem": stem,
        "user_story": "作为操作员，我希望创建记录，以便保存业务信息。",
        "priority": "P0",
        "ui_required": ui_required,
        "story_split_rationale": "同一业务对象的创建流程在一个故事内独立验收。",
        "operation_refs": ["OP-REQ-001-01"],
        "interface_capability_refs": ["INT-REQ-001-01"],
        "ui_surfaces": ([{
            "surface_id": "record-create",
            "name": "创建记录",
            "surface_type": "page",
            "source_refs": ["REQ-001", "AC-US-001-01"],
            "operation_refs": ["OP-REQ-001-01"],
        }] if ui_required else []),
        "prd_refs": [{"requirement_id": "REQ-001", "source_id": "PRD-001", "locator": "3.1"}],
        "scope": {"in": ["创建"], "out": ["批量创建"]},
        "acceptance_criteria": [{
            "id": "AC-US-001-01",
            "operation_refs": ["OP-REQ-001-01"],
            "text": "Given 操作员已填写合法名称，When 提交创建表单，Then 系统保存记录并返回记录标识。",
        }],
        "depends_on": [],
        "risks": [],
        "plan_generated": True,
        "development_completed": False,
        "self_test_completed": False,
        "plan_stale": False,
        "blocked_reason": None,
        "artifacts": {
            "contract": f"stories/{stem}/{stem}接口契约.json",
            "implementation": f"stories/{stem}/{stem}AI执行明细.md",
            "tests": f"stories/{stem}/{stem}测试用例.csv",
        },
        "last_updated_at": "2026-08-12T10:00:00+08:00",
    }


def tracker(stories: list[dict]) -> dict:
    return {
        "schema_version": "1.6",
        "project": {
            "name": "测试项目",
            "output_root": ".",
            "baseline_id": "BL-001",
            "material_manifest": "AI执行计划物料清单.md",
            "technical_selection": None,
        },
        "catalog_confirmed": True,
        "catalog_confirmed_at": "2026-08-12T10:00:00+08:00",
        "generated_at": "2026-08-12T10:00:00+08:00",
        "catalog_confirmation_document": "AI执行清单确认.md",
        "catalog_confirmation_hash": CONFIRMATION_HASH,
        "prd_operation_catalog": [{
            "operation_id": "OP-REQ-001-01",
            "name": "创建记录",
            "operation_type": "create",
            "source_refs": ["REQ-001"],
            "source_locator": "PRD-001#3.1 创建按钮",
            "story_id": stories[0]["id"],
            "ui_surface_refs": ["record-create"] if stories[0].get("ui_required") else [],
            "coverage_status": "covered",
            **({} if stories[0].get("ui_required") else {"no_ui_reason": "纯技术流程"}),
        }],
        "interface_capability_catalog": [{
            "interface_capability_id": "INT-REQ-001-01",
            "name": "创建记录",
            "source_refs": ["REQ-001"],
            "source_locator": "PRD-001#3.1 创建按钮",
            "story_id": stories[0]["id"],
            "operation_refs": ["OP-REQ-001-01"],
            "business_api_need": "required",
        }],
        "stories": stories,
    }


def openapi(has_api: bool = True) -> dict:
    doc = {
        "openapi": "3.1.0",
        "info": {"title": "Records", "version": "1.0.0", "x-story-id": "US-001"},
        "x-source-references": [{
            "source_id": "PRD-001", "locator": "3.1", "requirement_id": "REQ-001",
            "acceptance_criterion_id": "AC-US-001-01",
        }],
        "paths": {},
        "components": {},
    }
    if has_api:
        doc["paths"] = {
            "/records": {
                "post": {
                    "operationId": "createRecord",
                    "x-operation-refs": ["OP-REQ-001-01"],
                    "security": [{"session": []}],
                    "requestBody": {"required": True},
                    "responses": {"201": {"description": "created"}, "400": {"description": "invalid"}},
                }
            }
        }
    else:
        doc["x-no-api-change"] = "无接口变更；核实依据：本故事只调整本地静态说明页。"
    return doc


def implementation(ui: bool = True, has_api: bool = True) -> str:
    learning_rows = [[
        "PRD-01", "prd", "PRD-001", "PRD-001#3.1", "确认创建记录的范围和验收结果",
        "已确认仅支持单条创建且名称必填", "作为业务权威依据", "REQ-001;AC-US-001-01",
    ], [
        "FE-01" if ui else "BE-01", "frontend" if ui else "backend", "main",
        "src/pages/records/CreatePage.tsx" if ui else "src/jobs/record_sync.py:sync_records",
        "先理解现有页面表单和请求封装" if ui else "先理解批处理调用入口和错误处理",
        "已确认页面使用 RecordForm 与 recordsApi.create" if ui else "已确认任务通过 sync_records 调用仓储层",
        "复用并修改现有入口",
        "创建记录页面" if ui else "批处理创建流程",
    ]]
    if ui and has_api:
        learning_rows.append([
            "BE-01", "backend", "main", "src/records/RecordController.java:create",
            "确认接口入口、服务调用链和错误码约定",
            "已确认 create 委托 RecordService 并统一映射领域错误",
            "修改并复用现有 create 链路",
            "createRecord 接口",
        ])
    task_learning_refs = ";".join(row[0] for row in learning_rows)
    task_files = ";".join(row[3] for row in learning_rows if row[1] in {"frontend", "backend"})
    operation_ref = "createRecord" if has_api else "FRONTEND:saveDraft"
    page = ""
    if ui:
        page = "\n\n".join([
            "### 页面 [record-create] 创建记录\n\n"
            "- 变更类型：modify\n"
            "- 交互载体类型：page\n"
            "- 页面类型：form\n"
            "- 路由或入口：/records/new\n"
            "- 开发前学习：PRD-01；FE-01\n"
            "- 可复用组件：RecordForm；TextInput；ActionFooter\n\n"
            "- 操作引用：OP-REQ-001-01\n\n"
            "页面用于录入单条记录。布局从上到下为标题区、单列表单区和底部操作区；"
            "需要覆盖初始、校验失败、提交中、成功和接口失败状态。",
            "#### 表单字段\n\n" + table(
                ["order", "area", "field", "component", "source_and_mapping", "default_display_edit", "validation_and_linkage", "error_and_permission"],
                [["1", "创建表单", "name", "TextInput", "form.name 映射 CreateRecordRequest.name", "默认空字符串，可编辑，普通文本显示", "失焦和提交时 trim 后校验必填且最长 50 字，无跨字段联动", "字段下显示错误；无创建权限不可进入页面"]],
            ),
            "#### 按钮与操作\n\n" + table(
                ["action", "location", "visible_enabled_guard", "confirmation", "contract_id", "request_mapping", "success_behavior", "failure_behavior"],
                [["提交", "表单底部右侧", "有创建权限时显示；字段合法且未提交时可用", "无需确认，创建后可在详情撤销", operation_ref, "trim 后的 form.name 写入 request.name", "提示成功并进入详情，刷新列表缓存", "400 回填字段错误；其他错误保留输入并显示重试"]],
            ),
            "#### 提交过程\n\n" + table(
                ["flow", "trigger", "steps_and_validation", "success", "failure_or_branch"],
                [["创建记录", "点击提交", "trim name，校验必填和长度，通过后锁定按钮并发起操作", "提示成功并进入详情", "校验失败定位字段；请求失败保留输入并允许重试"]],
            ),
        ])

    interface = ""
    if has_api:
        consumer = "record-create 提交按钮" if ui else "sync_records 批处理任务"
        interface = "\n\n".join([
            "### 接口 [createRecord] 创建记录\n\n"
            "- 变更类型：modify\n"
            "- Method/Path：POST /records\n"
            f"- 服务对象：{consumer}，在提交或同步时调用并使用返回 id\n"
            "- 操作引用：OP-REQ-001-01\n"
            "- 需求与验收：REQ-001；AC-US-001-01\n"
            "- 开发前学习：PRD-01；BE-01\n"
            "- 代码入口与调用链：BE-01：RecordController.create -> RecordService.create -> RecordRepository.insert\n"
            "- 契约位置：#/paths/~1records/post",
            "#### 内部业务逻辑\n\n"
            "1. 校验当前租户的创建权限。\n"
            "2. trim 名称并校验必填和最长 50 字。\n"
            "3. 按 tenant_id 查询重名记录；冲突时返回 409。\n"
            "4. 在单事务内向 records 写入 name、tenant_id 和审计字段。\n"
            "5. 返回 id 和名称供调用方刷新或进入详情。\n\n"
            "数据访问以 tenant_id 隔离，校验失败不启动事务；写入异常时回滚，领域错误映射为稳定错误码。",
            "#### 字段映射\n\n" + table(
                ["direction", "schema_path", "page_field_or_caller", "transform_validation", "error_empty_behavior"],
                [["request", "requestBody.application/json.name", "record-create.name 或 sync_records", "trim 后必填且最长 50 字", "为空返回 400 VALIDATION_ERROR"],
                 ["response", "responses.201.application/json", "提交成功处理或同步任务结果", "记录 id 原样返回", "无结果视为服务异常并回滚"]],
            ),
        ])

    blocks = [
        "# US-001 创建记录 AI执行明细\n\n## 为什么要改\n\n"
        "US-001 解决操作员无法创建记录的问题。范围对应 REQ-001，"
        "完成结果以 AC-US-001-01 为准；不包含批量创建。",
        "## 开工前先读这些代码\n\n" + table(
            ["learning_ref", "source_type", "source_or_repository", "location", "why_read", "verified_finding", "planned_use", "related_scope"],
            learning_rows,
        ),
    ]
    if page:
        blocks.append("## 前端实现\n\n" + page)
    if interface:
        blocks.append("## 后端实现\n\n" + interface)
    task_refs = f"{task_learning_refs};REQ-001;AC-US-001-01;OP-REQ-001-01;INT-REQ-001-01"
    if has_api:
        task_refs += ";createRecord"
    blocks.append(
        "## 开发顺序与验收\n\n"
        + table(
            ["task_id", "depends_on", "files_or_symbols", "change", "related_refs", "done_when", "verification"],
            [["TASK-US-001-01", "无", task_files, "实现本故事已定义的页面或服务规则", task_refs, "合法输入创建成功，非法输入得到约定反馈", "运行本故事相关组件测试、集成测试和 CSV 用例"]],
        )
        + "\n\n"
        + table(
            ["operation_id", "implementation_kind", "ui_surface_refs", "contract_ids", "implementation_refs", "decision_basis"],
            [["OP-REQ-001-01", "mixed" if has_api else "frontend_only", "record-create" if ui else "NONE", "createRecord" if has_api else "NONE", "TASK-US-001-01;" + ("record-create;createRecord" if has_api else "record-create"), "页面提交动作需要后端持久化并由接口返回记录标识" if has_api else "仅在前端保存草稿，不产生 HTTP 请求"]],
        )
        + "\n\n"
        + table(
            ["acceptance_criterion_id", "implementation_refs", "test_case_ids", "observable_result"],
            [["AC-US-001-01", "TASK-US-001-01" + (";createRecord" if has_api else ""), "TC-US-001-001;TC-US-001-002", "合法名称保存并返回结果；空名称不保存并提示错误"]],
        )
    )
    return "\n\n".join(blocks) + "\n"


def test_rows() -> list[dict[str, str]]:
    base = {
        "story_id": "US-001", "acceptance_criterion_id": "AC-US-001-01",
        "requirement_ref": "REQ-001", "implementation_refs": "TASK-US-001-01;createRecord;OP-REQ-001-01",
        "test_level": "integration", "priority": "P0", "preconditions": "具备创建权限",
        "test_data": "独立租户内的记录名称", "automation_candidate": "yes",
        "environment": "test", "status": "not_run",
    }
    return [
        {**base, "case_id": "TC-US-001-001", "test_type": "positive", "title": "合法名称创建成功", "steps": "输入合法名称并提交", "expected_result": "返回 id 且记录可查询"},
        {**base, "case_id": "TC-US-001-002", "test_type": "boundary", "title": "空名称被拒绝", "steps": "输入空白名称并提交", "expected_result": "提示名称必填且不写库"},
    ]


class TrackerTests(unittest.TestCase):
    def setUp(self) -> None:
        self.temp = tempfile.TemporaryDirectory()
        self.root = Path(self.temp.name)
        self.tracker_path = self.root / "AI执行清单.json"
        (self.root / "AI执行清单确认.md").write_text(CONFIRMATION_MD, encoding="utf-8")

    def tearDown(self) -> None:
        self.temp.cleanup()

    def run_tracker(self, *args: str) -> subprocess.CompletedProcess[str]:
        return subprocess.run(["python3", str(SCRIPT), *args], text=True, capture_output=True, check=False)

    def write_package(self, *, ui: bool = True, has_api: bool = True) -> dict:
        item = story(ui, has_api)
        self.root.joinpath("AI执行计划物料清单.md").write_text(
            "confirmation_status: confirmed\nbaseline_id: BL-001\n", encoding="utf-8"
        )
        folder = self.root / Path(item["artifacts"]["implementation"]).parent
        folder.mkdir(parents=True)
        (self.root / item["artifacts"]["contract"]).write_text(json.dumps(openapi(has_api), ensure_ascii=False), encoding="utf-8")
        (self.root / item["artifacts"]["implementation"]).write_text(implementation(ui, has_api), encoding="utf-8")
        with (self.root / item["artifacts"]["tests"]).open("w", encoding="utf-8", newline="") as handle:
            writer = csv.DictWriter(handle, fieldnames=CSV_HEADER)
            writer.writeheader()
            writer.writerows(test_rows())
        self.tracker_path.write_text(json.dumps(tracker([item]), ensure_ascii=False, indent=2), encoding="utf-8")
        return item

    def validate(self) -> subprocess.CompletedProcess[str]:
        return self.run_tracker("validate", str(self.tracker_path), "--check-artifacts")

    def test_valid_ui_api_package_with_story_specific_headings(self) -> None:
        item = self.write_package()
        text = (self.root / item["artifacts"]["implementation"]).read_text(encoding="utf-8")
        self.assertIn("## 为什么要改", text)
        self.assertIn("### 页面 [record-create] 创建记录", text)
        self.assertIn("### 接口 [createRecord] 创建记录", text)
        self.assertNotIn("## 用户故事背景与范围", text)
        self.assertNotIn("## 数据与数据库变更", text)
        self.assertNotIn("| page_ref | change_type |", text)
        self.assertNotIn("| contract_id | change_type |", text)
        result = self.validate()
        self.assertEqual(result.returncode, 0, result.stderr)

    def test_valid_backend_only_package(self) -> None:
        self.write_package(ui=False, has_api=True)
        result = self.validate()
        self.assertEqual(result.returncode, 0, result.stderr)

    def test_valid_no_api_package(self) -> None:
        item = self.write_package(ui=False, has_api=False)
        text = (self.root / item["artifacts"]["implementation"]).read_text(encoding="utf-8")
        self.assertNotIn("无 HTTP 接口变更", text)
        self.assertNotIn("无数据库变更", text)
        self.assertNotIn("页面概览", text)
        result = self.validate()
        self.assertEqual(result.returncode, 0, result.stderr)

    def test_rejects_vague_code_target(self) -> None:
        item = self.write_package()
        path = self.root / item["artifacts"]["implementation"]
        path.write_text(path.read_text(encoding="utf-8").replace("src/pages/records/CreatePage.tsx", "相关代码"), encoding="utf-8")
        result = self.validate()
        self.assertNotEqual(result.returncode, 0)
        self.assertIn("未给出可检索位置", result.stderr)

    def test_rejects_missing_interface_logic(self) -> None:
        item = self.write_package()
        path = self.root / item["artifacts"]["implementation"]
        text = path.read_text(encoding="utf-8")
        text = text.replace("RecordController.create -> RecordService.create -> RecordRepository.insert", "查询相关数据")
        path.write_text(text, encoding="utf-8")
        result = self.validate()
        self.assertNotEqual(result.returncode, 0)
        self.assertIn("不可执行的模糊表述", result.stderr)

    def test_rejects_unknown_button_operation(self) -> None:
        item = self.write_package()
        path = self.root / item["artifacts"]["implementation"]
        path.write_text(path.read_text(encoding="utf-8").replace("| createRecord | trim 后的 form.name", "| missingOperation | trim 后的 form.name", 1), encoding="utf-8")
        result = self.validate()
        self.assertNotEqual(result.returncode, 0)
        self.assertIn("引用未知 contract_id", result.stderr)

    def test_rejects_list_page_without_pagination_and_columns(self) -> None:
        item = self.write_package()
        path = self.root / item["artifacts"]["implementation"]
        text = path.read_text(encoding="utf-8").replace(
            "- 页面类型：form",
            "- 页面类型：list",
            1,
        )
        path.write_text(text, encoding="utf-8")
        result = self.validate()
        self.assertNotEqual(result.returncode, 0)
        self.assertIn("页面 record-create 列表行为 缺少必要信息表", result.stderr)
        self.assertIn("页面 record-create 列表列 缺少必要信息表", result.stderr)

    def test_rejects_page_without_independent_entity_heading(self) -> None:
        item = self.write_package()
        path = self.root / item["artifacts"]["implementation"]
        text = path.read_text(encoding="utf-8").replace(
            "### 页面 [record-create] 创建记录",
            "### 创建记录页面",
            1,
        )
        path.write_text(text, encoding="utf-8")
        result = self.validate()
        self.assertNotEqual(result.returncode, 0)
        self.assertIn("缺少独立页面标题块", result.stderr)

    def test_rejects_interface_without_independent_entity_heading(self) -> None:
        item = self.write_package()
        path = self.root / item["artifacts"]["implementation"]
        text = path.read_text(encoding="utf-8").replace(
            "### 接口 [createRecord] 创建记录",
            "### createRecord 服务链路",
            1,
        )
        path.write_text(text, encoding="utf-8")
        result = self.validate()
        self.assertNotEqual(result.returncode, 0)
        self.assertIn("缺少独立接口标题块", result.stderr)

    def test_rejects_page_missing_from_confirmed_impact_baseline(self) -> None:
        self.write_package()
        data = json.loads(self.tracker_path.read_text(encoding="utf-8"))
        data["stories"][0]["ui_surfaces"].append({
            "surface_id": "record-detail",
            "name": "记录详情",
            "surface_type": "dialog",
            "source_refs": ["REQ-001", "AC-US-001-01"],
            "operation_refs": ["OP-REQ-001-01"],
        })
        self.tracker_path.write_text(json.dumps(data, ensure_ascii=False, indent=2), encoding="utf-8")
        result = self.validate()
        self.assertNotEqual(result.returncode, 0)
        self.assertIn("AI 执行明细缺少确认页面: record-detail", result.stderr)

    def test_rejects_interface_missing_from_openapi_and_implementation(self) -> None:
        self.write_package()
        path = self.root / "stories/US-001-创建记录/US-001-创建记录AI执行明细.md"
        text = path.read_text(encoding="utf-8").replace(
            "### 接口 [createRecord] 创建记录", "### createRecord 服务链路", 1
        )
        path.write_text(text, encoding="utf-8")
        result = self.validate()
        self.assertNotEqual(result.returncode, 0)
        self.assertIn("缺少独立接口标题块", result.stderr)

    def test_rejects_ui_story_without_confirmed_page_baseline(self) -> None:
        item = story(ui_required=True)
        item["ui_surfaces"] = []
        self.tracker_path.write_text(json.dumps(tracker([item]), ensure_ascii=False), encoding="utf-8")
        result = self.run_tracker("validate", str(self.tracker_path))
        self.assertNotEqual(result.returncode, 0)
        self.assertIn("ui_required=true 时 ui_surfaces 不能为空", result.stderr)

    def test_rejects_learning_index_without_prd_source(self) -> None:
        item = self.write_package()
        path = self.root / item["artifacts"]["implementation"]
        text = path.read_text(encoding="utf-8").replace(
            "| PRD-01 | prd | PRD-001 |",
            "| PRD-01 | decision | PRD-001 |",
            1,
        )
        path.write_text(text, encoding="utf-8")
        result = self.validate()
        self.assertNotEqual(result.returncode, 0)
        self.assertIn("缺少 prd 来源", result.stderr)

    def test_rejects_database_change_without_sql_and_rollback(self) -> None:
        item = self.write_package()
        path = self.root / item["artifacts"]["implementation"]
        text = path.read_text(encoding="utf-8")
        anchor = (
            "| FE-01 | frontend | main | src/pages/records/CreatePage.tsx | "
            "先理解现有页面表单和请求封装 | 已确认页面使用 RecordForm 与 recordsApi.create | "
            "复用并修改现有入口 | 创建记录页面 |"
        )
        database_row = (
            "| DB-01 | database | main | db/migrations/V002__records.sql | "
            "确认 records 表字段和约束 | 已确认当前表缺少 record_type 字段 | "
            "新增字段并迁移数据 | createRecord |"
        )
        path.write_text(text.replace(anchor, anchor + "\n" + database_row, 1), encoding="utf-8")
        result = self.validate()
        self.assertNotEqual(result.returncode, 0)
        self.assertIn("缺少可执行 SQL", result.stderr)
        self.assertIn("缺少回滚 SQL", result.stderr)

    def test_rejects_unmapped_csv_reference(self) -> None:
        item = self.write_package()
        path = self.root / item["artifacts"]["tests"]
        with path.open("r", encoding="utf-8", newline="") as handle:
            rows = list(csv.DictReader(handle))
        for row in rows:
            row["implementation_refs"] = "UNKNOWN"
        with path.open("w", encoding="utf-8", newline="") as handle:
            writer = csv.DictWriter(handle, fieldnames=CSV_HEADER)
            writer.writeheader()
            writer.writerows(rows)
        result = self.validate()
        self.assertNotEqual(result.returncode, 0)
        self.assertIn("implementation_refs 未关联执行明细", result.stderr)

    def test_next_and_status_without_artifact_check(self) -> None:
        item = story()
        item["plan_generated"] = False
        self.tracker_path.write_text(json.dumps(tracker([item]), ensure_ascii=False), encoding="utf-8")
        next_result = self.run_tracker("next", str(self.tracker_path), "--phase", "plan")
        self.assertEqual(next_result.returncode, 0, next_result.stderr)
        self.assertEqual(json.loads(next_result.stdout)["next"]["id"], "US-001")
        status_result = self.run_tracker("status", str(self.tracker_path))
        self.assertEqual(status_result.returncode, 0, status_result.stderr)

    def test_rejects_full_user_story_used_as_short_name(self) -> None:
        item = story()
        item["name"] = item["user_story"]
        item["file_stem"] = f"US-001-{item['name']}"
        self.tracker_path.write_text(json.dumps(tracker([item]), ensure_ascii=False), encoding="utf-8")
        result = self.run_tracker("validate", str(self.tracker_path))
        self.assertNotEqual(result.returncode, 0)
        self.assertIn("name 应是业务短标题", result.stderr)

    def test_rejects_user_story_without_role_behavior_value_structure(self) -> None:
        item = story()
        item["user_story"] = "创建记录功能"
        self.tracker_path.write_text(json.dumps(tracker([item]), ensure_ascii=False), encoding="utf-8")
        result = self.run_tracker("validate", str(self.tracker_path))
        self.assertNotEqual(result.returncode, 0)
        self.assertIn("角色—行为—价值格式", result.stderr)

    def test_rejects_overly_generic_story_role(self) -> None:
        item = story()
        item["user_story"] = "作为用户，我想要创建记录，以便保存需要处理的业务信息。"
        self.tracker_path.write_text(json.dumps(tracker([item]), ensure_ascii=False), encoding="utf-8")
        result = self.run_tracker("validate", str(self.tracker_path))
        self.assertNotEqual(result.returncode, 0)
        self.assertIn("角色过于笼统", result.stderr)

    def test_rejects_technical_task_as_user_behavior(self) -> None:
        item = story()
        item["user_story"] = "作为操作员，我想要开发后端接口和数据库表，以便实现功能。"
        self.tracker_path.write_text(json.dumps(tracker([item]), ensure_ascii=False), encoding="utf-8")
        result = self.run_tracker("validate", str(self.tracker_path))
        self.assertNotEqual(result.returncode, 0)
        self.assertIn("行为使用了技术任务", result.stderr)
        self.assertIn("价值描述过于空泛", result.stderr)

    def test_rejects_partial_given_when_then_acceptance_criterion(self) -> None:
        item = story()
        item["acceptance_criteria"][0]["text"] = "Given 操作员已填写名称，When 提交创建表单。"
        self.tracker_path.write_text(json.dumps(tracker([item]), ensure_ascii=False), encoding="utf-8")
        result = self.run_tracker("validate", str(self.tracker_path))
        self.assertNotEqual(result.returncode, 0)
        self.assertIn("Given-When-Then 时必须三部分完整", result.stderr)

    def test_rejects_result_only_acceptance_criterion(self) -> None:
        item = story()
        item["acceptance_criteria"][0]["text"] = "记录保存成功"
        self.tracker_path.write_text(json.dumps(tracker([item]), ensure_ascii=False), encoding="utf-8")
        result = self.run_tracker("validate", str(self.tracker_path))
        self.assertNotEqual(result.returncode, 0)
        self.assertIn("不可测试的模糊验收表述", result.stderr)

    def test_accepts_technical_outcome_without_fake_user_role(self) -> None:
        item = story(ui_required=False, has_api=False)
        item.update({
            "id": "TECH-001",
            "name": "记录历史数据回填",
            "file_stem": "TECH-001-记录历史数据回填",
            "user_story": "为了后续记录查询能力，需要完成历史记录数据回填，从而保证新旧数据可以按同一规则读取。",
            "operation_refs": ["OP-REQ-001-01"],
            "acceptance_criteria": [{
                "id": "AC-TECH-001-01",
                "operation_refs": ["OP-REQ-001-01"],
                "text": "Given 历史记录已生成回填快照，When 执行迁移任务，Then 所有合法记录均可按新结构读取。",
            }],
            "ui_surfaces": [],
            "artifacts": {
                "contract": "stories/TECH-001-记录历史数据回填/TECH-001-记录历史数据回填接口契约.json",
                "implementation": "stories/TECH-001-记录历史数据回填/TECH-001-记录历史数据回填AI执行明细.md",
                "tests": "stories/TECH-001-记录历史数据回填/TECH-001-记录历史数据回填测试用例.csv",
            },
        })
        technical_tracker = tracker([item])
        technical_tracker["interface_capability_catalog"][0]["story_id"] = "TECH-001"
        technical_tracker["interface_capability_catalog"][0]["business_api_need"] = "required"
        self.tracker_path.write_text(json.dumps(technical_tracker, ensure_ascii=False), encoding="utf-8")
        result = self.run_tracker("validate", str(self.tracker_path))
        self.assertEqual(result.returncode, 0, result.stderr)

    def test_schema_1_0_requires_stage_3_confirmation(self) -> None:
        data = tracker([story()])
        data["schema_version"] = "1.0"
        self.tracker_path.write_text(json.dumps(data, ensure_ascii=False), encoding="utf-8")
        result = self.run_tracker("validate", str(self.tracker_path))
        self.assertNotEqual(result.returncode, 0)
        self.assertIn("必须回到阶段 3", result.stderr)

    def test_schema_1_1_requires_stage_3_rebuild(self) -> None:
        data = tracker([story()])
        data["schema_version"] = "1.1"
        self.tracker_path.write_text(json.dumps(data, ensure_ascii=False), encoding="utf-8")
        result = self.run_tracker("validate", str(self.tracker_path))
        self.assertNotEqual(result.returncode, 0)
        self.assertIn("PRD 操作台账和逻辑交互载体", result.stderr)

    def test_schema_1_4_with_technical_design_requires_stage_3_rebuild(self) -> None:
        data = tracker([story()])
        data["schema_version"] = "1.4"
        self.tracker_path.write_text(json.dumps(data, ensure_ascii=False), encoding="utf-8")
        result = self.run_tracker("validate", str(self.tracker_path))
        self.assertNotEqual(result.returncode, 0)
        self.assertIn("移除技术设计", result.stderr)
        self.assertIn("ui_surfaces", result.stderr)

    def test_confirmation_document_hash_must_match(self) -> None:
        data = tracker([story()])
        data["catalog_confirmation_hash"] = "sha256:" + "0" * 64
        self.tracker_path.write_text(json.dumps(data, ensure_ascii=False), encoding="utf-8")
        result = self.run_tracker("validate", str(self.tracker_path))
        self.assertNotEqual(result.returncode, 0)
        self.assertIn("已发生变化", result.stderr)

    def test_confirmation_document_is_required(self) -> None:
        data = tracker([story()])
        (self.root / "AI执行清单确认.md").unlink()
        self.tracker_path.write_text(json.dumps(data, ensure_ascii=False), encoding="utf-8")
        result = self.run_tracker("validate", str(self.tracker_path))
        self.assertNotEqual(result.returncode, 0)
        self.assertIn("缺少用户确认文件", result.stderr)

    def test_confirmation_document_must_be_confirmed(self) -> None:
        data = tracker([story()])
        pending = "confirmation_status: pending\ncatalog_revision: CAT-001\n"
        (self.root / "AI执行清单确认.md").write_text(pending, encoding="utf-8")
        data["catalog_confirmation_hash"] = "sha256:" + hashlib.sha256(pending.encode("utf-8")).hexdigest()
        self.tracker_path.write_text(json.dumps(data, ensure_ascii=False), encoding="utf-8")
        result = self.run_tracker("validate", str(self.tracker_path))
        self.assertNotEqual(result.returncode, 0)
        self.assertIn("未标记为 confirmed", result.stderr)

    def test_requires_prd_operation_catalog(self) -> None:
        data = tracker([story()])
        data.pop("prd_operation_catalog")
        self.tracker_path.write_text(json.dumps(data, ensure_ascii=False), encoding="utf-8")
        result = self.run_tracker("validate", str(self.tracker_path))
        self.assertNotEqual(result.returncode, 0)
        self.assertIn("prd_operation_catalog", result.stderr)

    def test_stage_3_rejects_technical_scope_fields(self) -> None:
        data = tracker([story()])
        data["stories"][0]["expected_interfaces"] = [{"method_path": "GET /records"}]
        self.tracker_path.write_text(json.dumps(data, ensure_ascii=False), encoding="utf-8")
        result = self.run_tracker("validate", str(self.tracker_path))
        self.assertNotEqual(result.returncode, 0)
        self.assertIn("阶段 4 技术字段", result.stderr)

    def test_rejects_page_operation_reference_drift(self) -> None:
        data = tracker([story()])
        data["stories"][0]["ui_surfaces"][0]["operation_refs"] = ["OP-REQ-001-99"]
        self.tracker_path.write_text(json.dumps(data, ensure_ascii=False), encoding="utf-8")
        result = self.run_tracker("validate", str(self.tracker_path))
        self.assertNotEqual(result.returncode, 0)
        self.assertIn("operation_refs 引用未知操作", result.stderr)


if __name__ == "__main__":
    unittest.main()
