# init-multi-agent-team

为 Codex 项目初始化一个长期协作的三人 AI 团队：

- 规划 Agent：理解老板需求、拆解任务、定义验收标准、统一汇报
- 开发 Agent：接收合法开发交接、修改业务代码、提交 QA
- 验收 Agent：独立验收、失败退回开发、通过后通知规划

这个 Skill 只负责“创建公司和员工入职”，不会自动创建或执行任何业务任务。初始化完成后，由用户作为老板，在规划 Agent 对话中下达第一个任务。

## 工作流程

```text
老板 -> 规划 Agent -> 开发 Agent -> 验收 Agent -> 规划 Agent -> 老板
```

验收失败时：

```text
验收 Agent -> 开发 Agent -> 验收 Agent
```

三名 Agent 共享同一个项目目录，但拥有各自的内部工作区：

```text
项目根目录
├── 业务代码和正式产物
└── agents/
    ├── registry.json
    ├── messages.jsonl
    ├── TEAM_RULES.md
    ├── USAGE.md
    ├── plan/log.md
    ├── dev/log.md
    └── qa/log.md
```

## 核心特性

- 创建三个独立、长期保留的 Codex 对话
- 自动写入真实线程 ID，不伪造 `conv_id`
- 对话消息承担实际交接，`messages.jsonl` 负责审计留痕
- 幂等初始化：重复运行只补齐缺失内容
- 保留已有日志、交接历史和有效线程
- 强制角色门禁，防止规划或 QA Agent 越权修改业务代码
- 自动生成项目内的团队使用说明

## 角色门禁

`registry.json` 会记录：

```json
{
  "role": "product_planner",
  "may_modify_business_code": false
}
```

只有开发 Agent 的 `may_modify_business_code` 为 `true`，并且写权限仍需由合法交接激活。

任何被触发的 Skill 都只能提供方法和质量标准，不能扩大 Agent 的角色权限。例如规划 Agent 收到“实现、制作、重设计、修复”等请求时，只能整理需求并派发开发，不能亲自修改业务代码。

## 环境要求

- Codex Desktop
- Python 3.9+
- 当前目录已保存为 Codex 本地项目
- 可使用以下 Codex 线程工具：
  - `list_projects`
  - `create_thread`
  - `read_thread`
  - `send_message_to_thread`
  - `set_thread_title`

## 安装

克隆到个人 Skills 目录：

```bash
git clone https://github.com/jinxingtaire/init-multi-agent-team.git \
  ~/.agents/skills/init-multi-agent-team
```

如果目录已经存在：

```bash
cd ~/.agents/skills/init-multi-agent-team
git pull
```

## 使用

在需要初始化团队的项目对话中显式调用：

```text
$init-multi-agent-team
```

也可以使用自然语言：

```text
为当前项目初始化一个规划、开发、验收组成的多 Agent 团队
```

Skill 将：

1. 创建团队目录和协作文件。
2. 检查是否已有有效员工线程。
3. 只创建缺失的规划、开发和验收线程。
4. 写入真实线程 ID 和角色权限。
5. 向三名 Agent 发送完整团队规则。
6. 验证初始化结果。
7. 停止并等待老板下达业务任务。

## 初始化后如何派活

1. 打开 Codex 侧边栏中的“规划Agent”。
2. 说明业务目标、约束和期望结果。
3. 规划 Agent 整理任务并自动交给开发 Agent。
4. 开发完成后自动交给验收 Agent。
5. 验收通过后，规划 Agent 在原对话向老板汇报。

不要直接向开发或验收 Agent 派发新业务任务。它们会引导你回到规划 Agent。

## 仓库结构

```text
init-multi-agent-team/
├── SKILL.md
├── agents/
│   └── openai.yaml
├── references/
│   └── role-prompts.md
└── scripts/
    └── team_files.py
```

- `SKILL.md`：初始化流程、幂等策略和线程工具要求
- `role-prompts.md`：三名 Agent 的入职提示词与长期职责
- `team_files.py`：确定性生成目录、注册表、团队规则和使用说明
- `openai.yaml`：Codex Skill 界面元数据

## 本地验证

```bash
python3 scripts/team_files.py prepare --root /path/to/project
python3 scripts/team_files.py status --root /path/to/project
```

`finalize` 需要三个真实线程 ID：

```bash
python3 scripts/team_files.py finalize \
  --root /path/to/project \
  --planner-id "<planner-thread-id>" \
  --developer-id "<developer-thread-id>" \
  --reviewer-id "<reviewer-thread-id>"
```

脚本只负责文件和注册表。真实对话必须由 Codex 线程工具创建。

## License

[MIT](LICENSE)
