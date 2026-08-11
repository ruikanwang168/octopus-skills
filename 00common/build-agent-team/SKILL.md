---
name: build-agent-team
description: Design and initialize a task-specific persistent Codex multi-agent team by inspecting the current project, conducting a convergent user interview, proposing only the roles and workflow the mission needs, obtaining explicit confirmation, and then creating project-scoped threads, dynamic role rules, workspaces, registry, audit log, and usage guide. Use when the user explicitly asks to create, assemble, initialize, or design a multi-agent team for a described task or project, or invokes $build-agent-team. Do not use merely to discuss multi-agent architecture, dispatch work to an existing team, or execute the business mission during team initialization.
---

# Initialize a Dynamic Multi-Agent Team

Design the smallest useful team for the user's mission, confirm it, initialize it, and stop. Do not execute the mission during this workflow.

## Non-negotiable boundaries

- Treat team design and team initialization as separate phases.
- Do not create threads or official `agents/` artifacts before the user confirms the proposal.
- Do not create multiple agents when one agent is sufficient.
- Keep the safety kernel fixed: real thread IDs, persistent role identity, least privilege, verified handoffs, append-only audit, explicit completion gates, and human escalation for material decisions.
- Generate project-specific roles, permissions, workflow, rules, workspaces, and usage guidance from the confirmed specification.
- Stop after onboarding and verification. Leave the team waiting for its first mission message.

## Required tools

Use Codex project and thread tools, not generic subagents:

- `list_projects`
- `create_thread`
- `wait_threads`
- `read_thread`
- `send_message_to_thread`
- `set_thread_title`

Discover unavailable thread tools before proceeding. Match the saved local project by exact resolved path. Never substitute projectless threads or fabricate IDs.

## Phase 1: Discover and design

Read [team-design.md](references/team-design.md) completely.

1. Inspect the current project read-only when a project exists.
2. Extract the mission, deliverables, constraints, risks, expected lifetime, human decision points, and definition of done.
3. Ask only questions whose answers can materially change roles, permissions, routing, or completion gates. Ask one to three at a time and explain important defaults.
4. Prefer assumptions for low-risk details and disclose them in the proposal.
5. Choose the smallest team that creates genuine value through specialization, independent verification, parallelism, or permission separation.
6. Model the workflow as conditional directed edges. Do not force every team into a linear planner/developer/QA chain.
7. Present the proposal in user-facing language: team scope, roles, workflow, permission boundaries, user gates, success criteria, assumptions, and unresolved decisions.
8. Obtain explicit user confirmation. Treat requested changes as another design iteration.

If one agent is sufficient, recommend not initializing a multi-agent team unless the user explicitly chooses otherwise.

## Phase 2: Materialize the confirmed specification

Read [team-spec.md](references/team-spec.md) completely. Use [example-team-spec.json](references/example-team-spec.json) as a structural example when useful. Create a JSON specification that follows the schema and records `approval.status` as `confirmed`. Save the draft outside the target project's `agents/` directory until validation succeeds.

Run:

```bash
python3 <skill-dir>/scripts/team_files.py validate --spec <draft-spec.json>
python3 <skill-dir>/scripts/team_files.py prepare --root "$PWD" --spec <draft-spec.json>
python3 <skill-dir>/scripts/team_files.py status --root "$PWD"
```

`prepare` creates or updates the specification-derived files and only creates missing role logs. It must not erase existing logs or `messages.jsonl`.

The generated layout is dynamic:

```text
agents/
  team-spec.json
  registry.json
  messages.jsonl
  TEAM_RULES.md
  USAGE.md
  <role-id>/
    log.md
```

`team-spec.json` is the confirmed design source of truth. `registry.json` contains runtime thread IDs and a specification hash. Do not hand-write either file in the target project.

## Phase 3: Resolve and validate the project

1. Call `list_projects` and select the project whose resolved path exactly matches the current root.
2. If no exact project exists, stop before creating threads and report that file preparation is incomplete.
3. For every non-empty existing thread ID in `registry.json`, call `read_thread` and verify that it exists, belongs to the current project, and represents the same role.
4. Reuse a thread only when all checks pass.
5. If an ID is missing, inaccessible, duplicated, belongs to another project, or conflicts with the current role, stop and ask before repairing it.
6. If the registry is complete and every thread and onboarding protocol is valid, create and send nothing.

Do not silently migrate a live team to a changed specification. The script intentionally rejects a new specification once any registered thread exists.

## Phase 4: Create only missing roles

Generate bootstrap prompts:

```bash
python3 <skill-dir>/scripts/team_files.py prompts --root "$PWD" --phase bootstrap
```

For each missing role in specification order:

1. Call `create_thread` with the matched project ID and `{ "type": "local" }`.
2. Use that role's generated bootstrap prompt. Do not assign mission work.
3. Do not specify a model unless the user explicitly requested one.
4. Wait for the created thread to become readable before continuing.
5. Capture its real ID exactly and set its generated title.

Finalize all newly created IDs in one command; omit preserved IDs:

```bash
python3 <skill-dir>/scripts/team_files.py finalize \
  --root "$PWD" \
  --agent-id '<role-id>=<new-thread-id>' \
  --agent-id '<role-id>=<new-thread-id>'
```

The command must return `complete: true`. It rejects missing, duplicate, unknown, or conflicting IDs.

## Phase 5: Onboard the roster

Generate complete onboarding prompts:

```bash
python3 <skill-dir>/scripts/team_files.py prompts --root "$PWD" --phase onboarding
```

Send each rendered prompt to its real thread with `send_message_to_thread`.

- For a fresh initialization, onboard every role.
- For a partial repair, resend the current roster and specification version to every role.
- For a verified complete no-op rerun, send nothing.
- These messages establish identity, permissions, workflow, and waiting state; they are not mission handoffs.

## Phase 6: Verify and stop

Confirm:

- `status` reports `complete: true`, `spec_consistent: true`, and unique non-empty IDs;
- every role thread is readable in the exact project and has the generated title;
- every role received the same specification version and safety kernel;
- `TEAM_RULES.md` contains the generated role and workflow gates;
- `USAGE.md` accurately describes how the user starts, participates in, and completes work;
- no mission work was planned, implemented, tested, or dispatched.

Report completion and link `agents/USAGE.md`, `agents/team-spec.json`, and `agents/registry.json`. Tell the user which role/thread is the entry point. Emit one `::created-thread{threadId="..."}` directive per newly created user-owned thread and none for reused threads.

## Runtime audit protocol

Actual handoffs use thread messages. After a send succeeds, the sending role records the audit event with:

```bash
python3 <skill-dir>/scripts/team_files.py record-handoff \
  --root <project-root> \
  --from-role <role-id> \
  --to-role <role-id-or-user> \
  --type <message-type> \
  --title <title> \
  --task-id <task-id> \
  --status sent \
  --artifact <relative-path>
```

The audit file never replaces the real message channel.
