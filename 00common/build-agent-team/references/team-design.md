# Dynamic Team Design

Use this guide during the design phase. Keep the interview convergent: investigate first, ask only decision-changing questions, and stop when the team can be specified safely.

## Readiness gate

Do not propose a final team until these facts are known or explicitly assumed:

- mission and concrete deliverables;
- definition of done;
- task-bound, phase-bound, or project-long lifetime;
- important technical, business, time, and compliance constraints;
- operations that require independent review or user approval;
- expected autonomy and escalation behavior;
- whether useful work can proceed in parallel;
- where official artifacts belong.

Ask one to three questions per turn. Prefer a stated default when the downside of assuming is low. Never ask the user for facts that read-only project inspection can answer.

## Decide whether a team is warranted

Recommend a single agent when the work is small, sequential, low-risk, or dominated by one discipline. Add a role only when it provides at least one of:

- materially different expertise;
- independent verification that should not be performed by the implementer;
- a distinct permission or trust boundary;
- meaningful parallel work with a clear merge owner;
- sustained ownership across a long project phase.

Avoid ornamental managers, duplicate reviewers, and roles that only relay messages. Prefer two to six roles. Exceed six only when the mission has independently valuable workstreams and the user accepts the coordination cost.

## Design roles

Give every role:

- a stable machine-readable `role_id`;
- one primary purpose;
- explicit responsibilities and non-responsibilities;
- accepted message sources;
- allowed paths and prohibited actions;
- concrete outputs and handoff requirements;
- an escalation target;
- permission to modify business artifacts only when necessary.

Separate planning, implementation, and verification only when the mission benefits from that separation. Domain teams may instead use roles such as researcher, legal reviewer, data analyst, editor, security reviewer, release operator, or customer liaison.

## Design the workflow

Represent routing as directed edges with triggers and optional conditions. Include:

- one entry role for new user requests;
- an owner for each deliverable;
- required merge or review gates;
- failure and rework routes;
- user approval or escalation nodes;
- one completion owner and explicit completion criteria.

Use `user` as a workflow endpoint for approvals, decisions, and final reporting. A role may have multiple successors. Parallel branches must converge at a named integration or completion gate.

Do not claim automation for a route unless the receiving role can be reached through an available thread tool.

## Keep rules partly fixed

Always preserve the safety kernel:

1. Role identity persists across future requests.
2. Skills provide methods, not additional authority.
3. File edits require role, source, target, and permission checks.
4. Only real project-scoped thread IDs are valid.
5. A handoff is real only after its thread message succeeds.
6. Audit records are append-only and never serve as a work queue.
7. No role may declare completion before the configured completion gate.
8. Material scope, external side effects, and unresolved high-risk decisions escalate to the user.
9. Every message and role operates against one explicit specification version.

Generate project-specific rules for paths, tools, upstream sources, workflow triggers, approval gates, acceptance criteria, retries, and escalation.

## Present the proposal

Show the user:

1. why a multi-agent team is or is not justified;
2. team lifetime and entry role;
3. each role's purpose and authority;
4. the normal, parallel, failure, and escalation paths;
5. user decision points;
6. completion criteria;
7. assumptions and remaining uncertainties.

Ask for explicit confirmation. Do not treat silence, enthusiasm, or an earlier general request as confirmation of the final specification.
