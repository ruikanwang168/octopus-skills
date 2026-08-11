# Team Specification

`team-spec.json` is the confirmed design source of truth. The initialization script validates and normalizes it before creating project files.

## Top-level schema

```json
{
  "schema_version": 1,
  "spec_version": 1,
  "team_id": "customer-feedback-delivery",
  "team_name": "客户反馈系统交付团队",
  "mission": "交付可验收的客户反馈分析系统",
  "scope": "project",
  "entry_role": "product_lead",
  "completion_role": "release_reviewer",
  "approval": {
    "status": "confirmed",
    "confirmed_at": "2026-08-11T10:00:00+08:00"
  },
  "assumptions": ["首期不包含移动端"],
  "project_rules": ["生产发布必须获得用户确认"],
  "completion_criteria": ["全部验收标准通过", "残余风险已向用户披露"],
  "roles": [],
  "workflow": [],
  "human_gates": []
}
```

Required top-level fields:

- `schema_version`: integer `1`.
- `spec_version`: positive integer. Increment when a confirmed design changes.
- `team_id`: stable slug using lowercase letters, digits, hyphens, or underscores.
- `team_name`: user-facing name.
- `mission`: concrete team mission.
- `scope`: `task`, `phase`, or `project`.
- `entry_role`: role receiving new user work.
- `completion_role`: role authorized to report completion to the user.
- `approval.status`: must equal `confirmed` before materialization.
- `approval.confirmed_at`: ISO 8601 timestamp with timezone.
- `completion_criteria`: non-empty list.
- `roles`: non-empty role list.
- `workflow`: directed edge list.

Optional top-level lists default to empty: `assumptions`, `project_rules`, and `human_gates`.

## Role schema

```json
{
  "role_id": "fullstack_developer",
  "display_name": "全栈开发",
  "purpose": "实现确认后的产品需求",
  "responsibilities": ["修改业务代码", "完成开发验证"],
  "non_responsibilities": ["重新定义产品目标", "宣布最终验收通过"],
  "accepted_sources": ["product_lead", "release_reviewer"],
  "may_modify_business_code": true,
  "allowed_paths": ["src/", "tests/"],
  "prohibited_actions": ["未经确认执行生产发布"],
  "outputs": ["实现代码", "验证结果", "验收交接"],
  "escalation_to": "product_lead"
}
```

All fields are required. `role_id` uses lowercase letters, digits, hyphens, or underscores and becomes the workspace directory name. `accepted_sources` and `escalation_to` may reference another role or `user`. `allowed_paths` must contain project-relative paths; use an empty list when the role may not edit files.

## Workflow edge schema

```json
{
  "from": "product_lead",
  "to": "fullstack_developer",
  "trigger": "plan_confirmed",
  "condition": "任务包含需要实现的交付物",
  "required_payload": ["目标", "产物路径", "验收标准"]
}
```

Required fields are `from`, `to`, `trigger`, and `required_payload`. `condition` is optional and defaults to an empty string. Endpoints must be a declared role or `user`.

Every non-entry role must have an incoming edge. Every role except the completion role must have an outgoing edge. The entry role must be reachable from `user`; the completion role must be able to reach `user`. Cycles are allowed for rework.

## Human gate schema

```json
{
  "gate_id": "production-release",
  "when": "准备向生产环境发布",
  "decision": "用户确认发布范围和时间",
  "blocking": true
}
```

All fields are required. Use human gates for external side effects, material scope changes, production data, spending, public communication, legal acceptance, and other decisions that must not be inferred.

## Audit message schema

`messages.jsonl` contains one JSON object per successful or failed real handoff. The helper script records:

- `message_id`
- `created_at`
- `spec_version`
- `task_id`
- `from_role`
- `from_thread_id`
- `to_role`
- `to_thread_id`
- `type`
- `title`
- `status`
- `artifacts`

Do not place full business secrets or message bodies in the audit file. The receiving thread message remains the authoritative work channel.
