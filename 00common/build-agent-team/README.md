# build-agent-team

根据用户的任务描述和当前项目，动态设计并初始化一支长期协作的 Codex 多 Agent 团队。

它不是固定的“规划、开发、验收”三人模板。Skill 会先调查项目并进行收敛式访谈，判断是否真的需要多 Agent，再动态生成角色、权限、工作流、用户决策门禁、完成标准和使用说明。只有用户明确确认团队方案后，才会创建真实 Codex 任务。

## 核心能力

- 根据任务复杂度选择最小可用团队，支持单 Agent、串行、分支、并行、汇合和返工流程。
- 为每个角色生成职责、非职责、合法消息来源、文件权限、禁止操作、交付物和升级目标。
- 使用有向工作流描述条件交接，不强制套用固定角色链。
- 动态生成项目专属 `TEAM_RULES.md` 和 `USAGE.md`。
- 固定保留身份锁、最小权限、真实线程 ID、交接审计、完成门禁和人工升级等安全内核。
- 初始化具有幂等性，保留角色日志和审计历史，拒绝冲突 ID、重复 ID 和静默迁移运行中团队。
- 初始化阶段只组建团队并完成入职，不执行用户的实际业务任务。

## 工作过程

```text
任务描述
  -> 项目只读调查
  -> 收敛式访谈
  -> 判断是否需要多 Agent
  -> 设计最小团队和条件工作流
  -> 用户确认
  -> 生成并校验团队规格
  -> 创建项目内真实 Codex 任务
  -> 写入线程 ID 并动态入职
  -> 验证后待命
```

访谈每轮只询问真正会改变角色、权限、路由或完成门禁的问题。能够从项目中读取的事实不会重复询问，低风险细节会采用明确披露的默认假设。

## 生成的项目文件

```text
agents/
├── team-spec.json
├── registry.json
├── messages.jsonl
├── TEAM_RULES.md
├── USAGE.md
└── <role-id>/
    └── log.md
```

- `team-spec.json`：用户确认的团队设计源，包括角色、工作流、完成标准和人工门禁。
- `registry.json`：真实线程 ID、规格版本、规格哈希、工作目录和运行状态。
- `TEAM_RULES.md`：固定安全内核与根据本项目生成的动态角色规则。
- `USAGE.md`：根据实际团队生成的入口、流程、用户参与点和完成方式。
- `messages.jsonl`：真实线程消息发送后的追加式交接审计，不是任务队列。
- `agents/<role-id>/log.md`：每个角色独立维护的过程日志。

## 使用

在需要组建团队的项目任务中调用：

```text
$build-agent-team

我想开发一个需要产品设计、前后端实现、安全审查和发布验收的 SaaS，请根据任务为我设计并初始化团队。
```

也可以直接说明：

```text
根据这个项目和我的目标，设计一支合适的多 Agent 团队。先向我询问关键问题，确认方案后再初始化。
```

如果任务简单到单 Agent 更合适，Skill 会明确说明原因，不会为了形式强行创建多个角色。

## 文件修改规则

初始化后，不同文件的修改方式不同：

| 文件 | 是否建议手工修改 | 行为 |
| --- | --- | --- |
| `agents/<role-id>/log.md` | 可以 | 角色过程日志，会被保留 |
| `agents/team-spec.json` | 仅限受控修改 | 未创建线程时必须递增 `spec_version`；运行中团队禁止直接迁移 |
| `agents/registry.json` | 不要 | 由脚本维护，手改会破坏线程 ID 和规格哈希一致性 |
| `agents/TEAM_RULES.md` | 不要 | 派生文件，下次 `prepare` 会根据规格重新生成 |
| `agents/USAGE.md` | 不要 | 派生文件，下次 `prepare` 会根据规格重新生成 |
| `agents/messages.jsonl` | 不要覆盖 | 只能在真实交接后通过辅助命令追加 |

检测到 `team-spec.json` 与注册表哈希不一致时：

- 已存在真实角色线程：拒绝继续，防止运行中团队被静默改写。
- 尚未创建角色线程：只有新规格版本高于注册表版本时才允许重新生成。

推荐先修改项目外的规格草稿、递增 `spec_version`、运行验证，再执行 `prepare`。

## 环境要求

- Codex Desktop
- Python 3.9+
- 当前目录已经保存为 Codex 本地项目
- 可使用 `list_projects`、`create_thread`、`wait_threads`、`read_thread`、`send_message_to_thread` 和 `set_thread_title`

## 团队规格命令

验证规格：

```bash
python3 scripts/team_files.py validate \
  --spec references/example-team-spec.json
```

根据用户确认的规格准备目标项目：

```bash
python3 scripts/team_files.py prepare \
  --root /path/to/project \
  --spec /path/to/confirmed-team-spec.json
```

写入每个角色的真实线程 ID：

```bash
python3 scripts/team_files.py finalize \
  --root /path/to/project \
  --agent-id 'product_lead=<thread-id>' \
  --agent-id 'fullstack_developer=<thread-id>' \
  --agent-id 'release_reviewer=<thread-id>'
```

生成启动或完整入职提示词：

```bash
python3 scripts/team_files.py prompts \
  --root /path/to/project \
  --phase bootstrap

python3 scripts/team_files.py prompts \
  --root /path/to/project \
  --phase onboarding
```

查看团队状态：

```bash
python3 scripts/team_files.py status \
  --root /path/to/project
```

真实发送交接消息后追加审计：

```bash
python3 scripts/team_files.py record-handoff \
  --root /path/to/project \
  --from-role product_lead \
  --to-role fullstack_developer \
  --type plan_confirmed \
  --title '实现确认范围' \
  --task-id task-001 \
  --status sent \
  --artifact agents/product_lead/log.md
```

完整字段约束见 [`references/team-spec.md`](references/team-spec.md)，有效示例见 [`references/example-team-spec.json`](references/example-team-spec.json)。

## 安全与迁移边界

- 不伪造、猜测或手写线程 ID。
- 不创建无项目归属的线程。
- 不允许新请求或其他 Skill 隐式替换角色身份。
- 不把 `messages.jsonl` 当作轮询接活机制。
- 不允许未通过完成门禁的角色宣布团队任务完成。
- 不自动迁移已经存在真实线程的团队；角色或流程发生实质变化时，需要显式设计迁移方案并重新入职受影响角色。
- 遇到旧版注册表或其他系统的同名文件时停止，不直接覆盖。

## 开发验证

```bash
python3 -m unittest discover -s tests -v
uvx ruff check scripts tests
```
