---
name: init-multi-agent-team
description: Initialize a persistent three-person AI team for the current project, with separate planner, developer, and QA reviewer Codex threads, enforced role locks, role workspaces, registry, logs, handoff audit file, and usage guide. Use when the user explicitly asks to initialize a multi-agent team, create planning/development/QA AI employees, set up a three-agent company for a project, or invokes $init-multi-agent-team. Do not use merely to discuss multi-agent design, dispatch a business task, or run an already initialized team.
---

# Initialize Multi-Agent Team

Create the company and onboard its three AI employees. Stop after initialization. Do not invent, accept, plan, implement, or test a business task during this workflow.

## Fixed Team Model

Create these long-lived roles:

- `product_planner` / 规划Agent / private station `./agents/plan/`
- `developer` / 开发Agent / private station `./agents/dev/`
- `qa_reviewer` / 验收Agent / private station `./agents/qa/`

Treat the current project root as the shared office. Keep internal notes in each role's station. Put official business artifacts and application code in the project root or its normal project directories.

Use this delivery loop after onboarding:

`老板 -> 规划 -> 开发 -> QA -> 规划 -> 老板`

On rejection, use:

`QA -> 开发 -> QA`

The role threads perform that future workflow. This initialization skill does not run it.

## Required Files

Create or preserve:

```text
agents/
  registry.json
  messages.jsonl
  TEAM_RULES.md
  USAGE.md
  plan/
    log.md
  dev/
    log.md
  qa/
    log.md
```

Use `scripts/team_files.py` for deterministic file creation and registry updates. Do not hand-write thread IDs.

## Thread Tool Setup

Use Codex thread tools, not generic subagents:

- `list_projects`
- `create_thread`
- `list_threads` and/or `read_thread`
- `send_message_to_thread`
- `set_thread_title`

If these tools are not active, discover them before proceeding. If project-scoped thread creation is unavailable, stop and explain that initialization is incomplete. Never substitute projectless threads or fabricate `conv_id` values.

## Initialization Workflow

### 1. Prepare the shared office

Run:

```bash
python3 <skill-dir>/scripts/team_files.py prepare --root "$PWD"
python3 <skill-dir>/scripts/team_files.py status --root "$PWD"
```

Use the exact current project root. Read the JSON status output.

### 2. Resolve the current project

Call `list_projects`. Select the saved local project whose path matches the current project root. If no exact project is available, stop without creating projectless threads.

### 3. Validate existing employees

For every non-empty `conv_id` in `agents/registry.json`, call `read_thread`; use `list_threads` only as a lookup aid.

- Reuse a thread only when it exists and belongs to the current project.
- Never overwrite a valid existing `conv_id`.
- If a non-empty ID is missing, inaccessible, or points to another project, report the conflict and ask before repairing it.
- If all three valid employees and required files already exist, report that the company is initialized and create nothing.

### 4. Create only missing employees

Read `references/role-prompts.md` completely.

Create missing threads in this order:

1. 规划Agent
2. 开发Agent
3. 验收Agent

For each employee:

- Use `create_thread` with the matched project ID.
- Use `{ "type": "local" }`; do not create a worktree.
- Use the matching bootstrap prompt from `references/role-prompts.md`.
- Do not specify a model unless the user explicitly requested one.
- Capture the returned thread ID exactly.
- Rename the thread with `set_thread_title`.

Do not assign a business task in the creation prompt.

### 5. Finalize the registry and guide

Pass all newly created IDs to the script. Omit IDs already preserved in the registry:

```bash
python3 <skill-dir>/scripts/team_files.py finalize \
  --root "$PWD" \
  --planner-id "<new-planner-id-if-any>" \
  --developer-id "<new-developer-id-if-any>" \
  --reviewer-id "<new-reviewer-id-if-any>"
```

The command must end with `complete: true`. On an ID conflict, stop; do not replace it automatically.

The final registry relationship is fixed:

- planner `next_role`: `developer`
- developer `next_role`: `qa_reviewer`
- QA `fallback_role`: `developer`
- only developer has `may_modify_business_code: true`
- `team_policy_file` points to `./agents/TEAM_RULES.md`

### 6. Complete onboarding

Render the full prompt for each role from `references/role-prompts.md`, replacing every placeholder with the current project root and all three real thread IDs.

Send the rendered prompt to each role with `send_message_to_thread`.

- For a fresh initialization, send all three prompts.
- When repairing a partial initialization, resend the full roster to all three employees.
- For a complete no-op rerun, send nothing.

These are onboarding messages, not business handoffs. Leave all employees waiting for the boss.

### 7. Verify

Confirm:

- all required files exist;
- `registry.json` parses and contains three non-empty real thread IDs;
- each thread can be read;
- each title matches its role;
- each employee has received the role-lock protocol;
- `agents/TEAM_RULES.md` defines the mandatory preflight gate;
- `agents/USAGE.md` explains how the boss starts work;
- no business task was created or executed.

## Role-Lock Safety Requirement

The onboarding prompts must make role identity persistent across future turns.

- A newer business request does not replace the employee's role.
- A triggered skill supplies methods and quality guidance; it never grants permissions outside the current role.
- Before using an editing tool or changing a project file, every employee must identify its role, verify the request source, and verify that the target file is allowed.
- The planner must interpret words such as "制作", "实现", "开发", "重设计", or "修复" as a request to prepare and send a developer handoff, not as permission to implement.
- The planner completes a dispatch only after all three actions succeed: write the plan log, send the real thread message, and append the audit record.
- On any conflict, stop before editing and follow `agents/TEAM_RULES.md`.

## Idempotency

- Create missing directories and files only.
- Preserve existing log content and `messages.jsonl`.
- Preserve valid thread IDs.
- Create only missing role threads.
- Do not rebuild the whole company unless the user explicitly requests it.
- Do not archive, replace, or delete an existing employee automatically.

## Completion Response

Report that initialization is complete, link `agents/USAGE.md` and `agents/registry.json`, and tell the boss to open 规划Agent to assign the first task.

For each newly created user-owned thread, emit its `::created-thread{threadId="..."}` directive on a separate line. Emit no directive for reused threads.
