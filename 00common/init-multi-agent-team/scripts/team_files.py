#!/usr/bin/env python3
"""Prepare and finalize the shared files for a three-role AI project team."""

from __future__ import annotations

import argparse
import json
import sys
from pathlib import Path
from typing import Any


ROLE_SPECS = (
    {
        "name": "规划Agent",
        "role": "product_planner",
        "workspace": "./agents/plan/",
        "next_role": "developer",
        "may_modify_business_code": False,
    },
    {
        "name": "开发Agent",
        "role": "developer",
        "workspace": "./agents/dev/",
        "next_role": "qa_reviewer",
        "may_modify_business_code": True,
    },
    {
        "name": "验收Agent",
        "role": "qa_reviewer",
        "workspace": "./agents/qa/",
        "fallback_role": "developer",
        "may_modify_business_code": False,
    },
)

LOG_FILES = {
    "plan/log.md": "# Plan Log\n",
    "dev/log.md": "# Dev Log\n",
    "qa/log.md": "# QA Log\n",
}


class TeamFileError(RuntimeError):
    pass


def project_root(raw: str) -> Path:
    root = Path(raw).expanduser().resolve()
    if not root.exists() or not root.is_dir():
        raise TeamFileError(f"Project root is not a directory: {root}")
    return root


def read_registry(path: Path) -> dict[str, Any]:
    if not path.exists():
        return {"agents": []}
    try:
        data = json.loads(path.read_text(encoding="utf-8"))
    except (OSError, json.JSONDecodeError) as exc:
        raise TeamFileError(f"Cannot parse existing registry: {exc}") from exc
    if not isinstance(data, dict) or not isinstance(data.get("agents"), list):
        raise TeamFileError("Existing registry must contain an 'agents' array")
    return data


def ordered_entry(spec: dict[str, Any], current: dict[str, Any], conv_id: str) -> dict[str, Any]:
    relationship_key = "next_role" if "next_role" in spec else "fallback_role"
    entry: dict[str, Any] = {
        "name": spec["name"],
        "role": spec["role"],
        "conv_id": conv_id,
        relationship_key: spec[relationship_key],
        "workspace": spec["workspace"],
        "may_modify_business_code": spec["may_modify_business_code"],
    }
    managed = {
        "name",
        "role",
        "conv_id",
        "next_role",
        "fallback_role",
        "workspace",
        "may_modify_business_code",
    }
    for key, value in current.items():
        if key not in managed:
            entry[key] = value
    return entry


def merge_registry(
    data: dict[str, Any],
    supplied_ids: dict[str, str] | None = None,
    require_complete: bool = False,
) -> dict[str, Any]:
    supplied_ids = supplied_ids or {}
    existing: dict[str, dict[str, Any]] = {}
    extras: list[Any] = []

    for item in data.get("agents", []):
        if isinstance(item, dict) and item.get("role") in {spec["role"] for spec in ROLE_SPECS}:
            existing[str(item["role"])] = item
        else:
            extras.append(item)

    merged: list[Any] = []
    missing: list[str] = []
    for spec in ROLE_SPECS:
        role = spec["role"]
        current = existing.get(role, {})
        existing_id = current.get("conv_id", "")
        existing_id = existing_id if isinstance(existing_id, str) else ""
        candidate = supplied_ids.get(role, "")

        if existing_id and candidate and existing_id != candidate:
            raise TeamFileError(
                f"Refusing to replace existing conv_id for {role}: "
                f"{existing_id} != {candidate}"
            )

        conv_id = existing_id or candidate
        if not conv_id:
            missing.append(role)
        merged.append(ordered_entry(spec, current, conv_id))

    if require_complete and missing:
        raise TeamFileError(f"Missing thread IDs for: {', '.join(missing)}")

    result = dict(data)
    result["team_policy_file"] = "./agents/TEAM_RULES.md"
    result["team_policy_version"] = "2026-06-25"
    result["task_entry_role"] = "product_planner"
    result["agents"] = merged + extras
    return result


def write_json_if_changed(path: Path, data: dict[str, Any]) -> bool:
    rendered = json.dumps(data, ensure_ascii=False, indent=2) + "\n"
    if path.exists() and path.read_text(encoding="utf-8") == rendered:
        return False
    temporary = path.with_suffix(path.suffix + ".tmp")
    temporary.write_text(rendered, encoding="utf-8")
    temporary.replace(path)
    return True


def write_if_missing(path: Path, content: str) -> bool:
    if path.exists():
        return False
    path.write_text(content, encoding="utf-8")
    return True


def usage_document() -> str:
    return """# 多 Agent 团队使用说明

## 团队成员

- **规划Agent**：老板的业务入口，负责理解任务、制定计划、定义验收标准和最终汇报。
- **开发Agent**：根据规划交接完成代码或正式业务产物，并提交验收。
- **验收Agent**：独立验证开发结果；不通过则退回开发，通过则通知规划。

## 如何开始工作

1. 在 Codex 侧边栏打开 **规划Agent** 对话。
2. 由老板在该对话中说明第一个业务任务、目标和约束。
3. 规划Agent 会把任务自动交给开发Agent。
4. 开发完成后会自动交给验收Agent。
5. 验收不通过时由验收Agent退回开发Agent；通过后交回规划Agent。
6. 规划Agent最终在原对话中向老板汇报。

正常流程：

`老板 -> 规划 -> 开发 -> QA -> 规划 -> 老板`

返工流程：

`QA -> 开发 -> QA`

## 办公区规则

- 项目根目录是三名 Agent 共用的公共办公区。
- `agents/plan/`、`agents/dev/`、`agents/qa/` 是各自工位，只保存内部日志和过程文件。
- 正式业务产物、应用代码和项目文档放在项目原有目录中。
- 对话消息负责真实交接；`agents/messages.jsonl` 只记录交接历史。
- 请不要绕过规划Agent直接向开发Agent或验收Agent派发业务任务。
- 每名 Agent 在处理新任务前必须先读取 `agents/TEAM_RULES.md`。
- 新任务和被触发的 Skill 都不能改变 Agent 的长期角色权限。
- 规划Agent不会亲自修改业务代码；“制作、实现、重设计、修复”等请求会被整理成开发交接。

## 文件说明

- `agents/registry.json`：团队名册、线程 ID、工作目录和流转关系。
- `agents/TEAM_RULES.md`：所有 Agent 必须遵守的角色门禁和防越权规则。
- `agents/messages.jsonl`：跨 Agent 交接审计记录。
- `agents/plan/log.md`：规划过程日志。
- `agents/dev/log.md`：开发过程日志。
- `agents/qa/log.md`：验收过程日志。

重复运行初始化 Skill 时，会保留有效线程和已有日志，只补齐缺失内容。
"""


def team_rules_document() -> str:
    return """# 多 Agent 团队强制规则

## 规则优先级

1. 长期角色身份不会被后续业务指令替换。
2. Skill 只能提供方法和质量标准，不能扩大当前角色权限。
3. 在修改任何文件前，必须完成角色门禁检查。
4. 发生冲突时，先停止修改，再按角色流程交接。

## 每次任务的角色门禁

执行任何工具前先确认：

1. 我的 `role` 是什么？
2. 消息来自老板还是合法的上游 Agent？
3. 这项工作属于规划、开发还是验收？
4. 我准备修改哪些文件？
5. `registry.json` 中的 `may_modify_business_code` 是否允许该操作？

任一答案不明确时，不得编辑业务文件。

## 规划 Agent

- 老板的唯一业务入口。
- 只负责需求理解、项目现状调查、任务拆解、验收标准、派单和最终汇报。
- 不修改 `public/`、`src/`、服务端、构建配置或其他业务代码。
- “制作、实现、开发、重设计、修复”必须解释为整理开发任务并派发。
- 编码、设计或测试 Skill 只能用于提高任务说明和验收标准质量。
- 派单完成必须同时满足：
  1. 更新 `agents/plan/log.md`；
  2. 使用真实对话消息发送给开发 Agent；
  3. 成功后追加 `agents/messages.jsonl`。

## 开发 Agent

- 只有规划 Agent 的开发交接或 QA Agent 的返工交接可以授权修改业务代码。
- 老板直接派活时，引导老板前往规划 Agent，不直接开工。
- 完成后必须交给 QA，不自行宣布最终完成。

## 验收 Agent

- 只有开发 Agent 的验收交接可以启动正式验收。
- 默认不修改业务代码；测试发现问题时退回开发 Agent。
- 测试或诊断 Skill 即使建议自动修复，也不能扩大 QA 权限。
- 通过后通知规划 Agent，由规划 Agent 向老板统一汇报。

## 越权处理

一旦发现自己正在执行不属于当前角色的工作：

1. 立即停止新增修改；
2. 不以“已经开始”为理由继续完成；
3. 在本角色日志记录事实和影响；
4. 通知老板或合法上游 Agent；
5. 将后续处理交给有权限的角色。
"""


def status_payload(root: Path) -> dict[str, Any]:
    agents_dir = root / "agents"
    registry_path = agents_dir / "registry.json"
    data = read_registry(registry_path)
    entries = {
        item.get("role"): item
        for item in data.get("agents", [])
        if isinstance(item, dict) and isinstance(item.get("role"), str)
    }
    roles: dict[str, Any] = {}
    for spec in ROLE_SPECS:
        entry = entries.get(spec["role"], {})
        conv_id = entry.get("conv_id", "")
        roles[spec["role"]] = {
            "name": spec["name"],
            "conv_id": conv_id if isinstance(conv_id, str) else "",
            "workspace": spec["workspace"],
            "needs_thread": not bool(conv_id),
        }

    required = [
        agents_dir / "registry.json",
        agents_dir / "messages.jsonl",
        agents_dir / "TEAM_RULES.md",
        agents_dir / "USAGE.md",
        agents_dir / "plan/log.md",
        agents_dir / "dev/log.md",
        agents_dir / "qa/log.md",
    ]
    missing_files = [str(path.relative_to(root)) for path in required if not path.exists()]
    return {
        "project_root": str(root),
        "complete": (
            all(not role["needs_thread"] for role in roles.values())
            and not missing_files
        ),
        "roles": roles,
        "missing_files": missing_files,
        "usage_exists": (agents_dir / "USAGE.md").exists(),
        "team_rules_exists": (agents_dir / "TEAM_RULES.md").exists(),
    }


def prepare(root: Path) -> dict[str, Any]:
    agents_dir = root / "agents"
    created: list[str] = []
    agents_dir.mkdir(parents=True, exist_ok=True)
    for relative in ("plan", "dev", "qa"):
        path = agents_dir / relative
        if not path.exists():
            path.mkdir(parents=True)
            created.append(str(path.relative_to(root)))

    for relative, heading in LOG_FILES.items():
        path = agents_dir / relative
        if write_if_missing(path, heading):
            created.append(str(path.relative_to(root)))

    messages_path = agents_dir / "messages.jsonl"
    if write_if_missing(messages_path, ""):
        created.append(str(messages_path.relative_to(root)))

    team_rules_path = agents_dir / "TEAM_RULES.md"
    if write_if_missing(team_rules_path, team_rules_document()):
        created.append(str(team_rules_path.relative_to(root)))

    registry_path = agents_dir / "registry.json"
    merged = merge_registry(read_registry(registry_path))
    if write_json_if_changed(registry_path, merged):
        created.append(str(registry_path.relative_to(root)))

    payload = status_payload(root)
    payload["created_or_updated"] = created
    return payload


def finalize(root: Path, supplied_ids: dict[str, str]) -> dict[str, Any]:
    agents_dir = root / "agents"
    registry_path = agents_dir / "registry.json"
    if not registry_path.exists():
        raise TeamFileError("Run prepare before finalize")

    merged = merge_registry(
        read_registry(registry_path),
        supplied_ids=supplied_ids,
        require_complete=True,
    )
    registry_changed = write_json_if_changed(registry_path, merged)
    usage_created = write_if_missing(agents_dir / "USAGE.md", usage_document())
    team_rules_created = write_if_missing(agents_dir / "TEAM_RULES.md", team_rules_document())
    payload = status_payload(root)
    payload["registry_changed"] = registry_changed
    payload["usage_created"] = usage_created
    payload["team_rules_created"] = team_rules_created
    return payload


def build_parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(description=__doc__)
    subparsers = parser.add_subparsers(dest="command", required=True)

    for command in ("prepare", "status"):
        subparser = subparsers.add_parser(command)
        subparser.add_argument("--root", required=True)

    finalizer = subparsers.add_parser("finalize")
    finalizer.add_argument("--root", required=True)
    finalizer.add_argument("--planner-id", default="")
    finalizer.add_argument("--developer-id", default="")
    finalizer.add_argument("--reviewer-id", default="")
    return parser


def main() -> int:
    args = build_parser().parse_args()
    try:
        root = project_root(args.root)
        if args.command == "prepare":
            payload = prepare(root)
        elif args.command == "status":
            payload = status_payload(root)
        else:
            supplied_ids = {
                "product_planner": args.planner_id,
                "developer": args.developer_id,
                "qa_reviewer": args.reviewer_id,
            }
            payload = finalize(root, supplied_ids)
        print(json.dumps(payload, ensure_ascii=False, indent=2))
        return 0
    except TeamFileError as exc:
        print(f"error: {exc}", file=sys.stderr)
        return 2


if __name__ == "__main__":
    raise SystemExit(main())
