# 跟踪与续跑规则

每次调用都完整读取本文件。它是阶段判定、状态含义和基线漂移处理的唯一规则来源。

## 发现既有状态

在输出目录查找：

- `AI执行计划物料清单.md`
- `系统技术选型清单.md`
- `AI执行清单确认.md`
- `AI执行清单.json`
- `stories/` 下的故事实施包

有跟踪文件时运行：

```bash
python3 <skill-dir>/scripts/tracker.py validate <output-dir>/AI执行清单.json --check-artifacts
python3 <skill-dir>/scripts/tracker.py status <output-dir>/AI执行清单.json
```

校验失败时报告具体故事和字段，不猜测修复，也不绕过无效状态继续。

当前跟踪 Schema 为 `1.6`。阶段 3先生成 `AI执行清单确认.md`，由用户确认 PRD 操作、逻辑交互载体、按钮和业务接口能力，再根据确认文件生成 JSON。JSON 必须记录确认文件路径和 SHA-256；确认文件缺失、状态不是 confirmed 或 hash 变化时，不能直接进入阶段 4，必须重新确认并重新生成 JSON。遇到旧版本时回到阶段 3；旧 `1.4` 中的接口地址、技术变更类型和页面实现信息不能自动迁移为需求范围。

技术选型清单当前使用 schema `1.1`。旧 `1.0` 清单只代表上一版技术报告格式，不能视为已经完成本次需求的技术能力分析；再次调用时回到阶段 2，按当前需求重新核实沿用或新增技术并取得用户确认，不自动升级。

已有 `1.3`、`1.5` 清单若因 `name`、`user_story`、操作台账、故事拆分或验收标准不符合故事卡质量规则而校验失败，也必须回到阶段 3展示重写、补点或拆分建议并让用户重新确认；不要只为通过正则而自动改写角色、价值或验收语义。

## 阶段判定顺序

1. 重新发现物料清单引用的所有输入，检查是否可访问和是否变化。
2. 物料清单缺失、未确认、不符合当前阶段 1范围规则或基线发生变化：进入阶段 1。物料清单仍为 schema `1.0`，或没有明确记录项目类型及全量数据库基线状态时，视为范围确认不完整，展示需要补充的内容并重新取得用户确认；不得自动升级。
3. 技术选型清单缺失、未确认、仍为 schema `1.0`，或尚未针对本次需求完成“需求功能点 → 现有技术基线 → 沿用/新增结论”：进入阶段 2。增量项目即使没有新增框架，也不能因为已有代码就跳过本阶段；必须生成并确认沿用现有技术栈的结论。
4. `AI执行清单确认.md` 缺失、未确认或 hash 变化：进入阶段 3，先生成/更新确认 MD 并等待用户确认；若确认 MD 已是 `confirmed` 且内容未变化，只是 `AI执行清单.json` 缺失、不是当前 Schema `1.6`、缺少 `prd_operation_catalog`/`interface_capability_catalog`/`operation_refs`/`interface_capability_refs`/`ui_surfaces` 或 `catalog_confirmed` 不为 `true`，则从当前确认 MD 重新派生 JSON，不重复要求同一确认。
5. 选择顺序最靠前的 `plan_generated=false` 或 `plan_stale=true` 故事：进入阶段 4。
6. 用户明确指定故事且依赖允许时，以指定故事为准。
7. 所有计划均已生成且不过期时，只报告第一条未研发完成或未自测完成的故事，不代替用户实施或改状态。

## 状态语义与维护者

| 用户可见含义 | JSON 字段 | 维护者 |
|---|---|---|
| 任务计划是否生成 | `plan_generated` | 技能在三项故事产物通过结构校验和直接开发语义核验后更新；用户可纠正 |
| 任务是否研发完成 | `development_completed` | 用户或实际研发智能体更新 |
| 任务是否自测完成 | `self_test_completed` | 用户或实际研发智能体更新 |
| 计划是否因基线变化过期 | `plan_stale` | 技能依据物料漂移影响分析更新 |

状态约束：

- `development_completed=true` 要求 `plan_generated=true`。
- `self_test_completed=true` 要求 `development_completed=true`。
- `plan_stale=true` 只用于曾生成过计划的故事，并表示当前计划不能作为新基线实施依据。
- `blocked_reason` 为 `null` 或非空字符串；存在阻塞时不得把计划标为已生成。
- `plan_generated=true` 只表示计划包已经达到可直接交给研发 AI 的完整度，不表示代码已开发或测试已通过。
- `tracker.py validate --check-artifacts` 是结构与引用校验，不是语义就绪证明；仅脚本通过时不得设置 `plan_generated=true`。
- JSON 只能由已确认的 `AI执行清单确认.md` 派生；不得只编辑 JSON 绕过需求确认。

## 基线漂移

每次调用比较：

- 本地文件内容哈希；优先使用 SHA-256。
- Git 仓库远端、分支、HEAD 和 dirty 状态。
- 在线材料规范化 URL、内容版本或更新时间、ETag 和本次访问时间；不要把抓取时间冒充内容版本。
- 原型、共享接口、现有全量数据库脚本或结构基线、数据库文档和补充决策的版本。
- `AI执行清单确认.md` 的 SHA-256 与 JSON 中 `catalog_confirmation_hash` 是否一致。

发现变化时：

1. 先展示确认 MD 的变更、证据和影响，不直接覆盖已确认 JSON。
2. 用户确认新 MD 后更新确认时间和 hash，再重新生成 JSON。
3. 保持未变化的故事、操作、页面载体和接口能力 ID；新增项生成新 ID，状态默认均为 `false`。
4. 对受影响且已经生成过计划的故事设为 `plan_stale=true`；未规划故事继续保持 `plan_generated=false`。
5. 保留用户维护的研发和自测状态，明确返工风险，不静默清除进度。删除项保留历史并标记 `excluded/deferred` 或归档，不直接抹除。
6. 若规模、合规、集成、部署或团队约束变化可能改变架构，读取阶段 2规则并重新确认选型；否则记录沿用原决策的证据。
7. 重规划完成后，如果旧研发或自测状态为 `true`，必须让用户决定保留还是重置后才能清除 `plan_stale`。

## 命令

查找下一项：

```bash
python3 <skill-dir>/scripts/tracker.py next <tracker> --phase plan
python3 <skill-dir>/scripts/tracker.py next <tracker> --phase development
python3 <skill-dir>/scripts/tracker.py next <tracker> --phase self-test
```

安全修改状态：

```bash
python3 <skill-dir>/scripts/tracker.py set <tracker> <story-id> --field plan_generated --value true --check-artifacts
python3 <skill-dir>/scripts/tracker.py set <tracker> <story-id> --field development_completed --value true
python3 <skill-dir>/scripts/tracker.py set <tracker> <story-id> --field self_test_completed --value true
```

基线漂移后的计划若要保留旧下游完成状态，只有取得用户明确确认后才给第一条命令增加 `--acknowledge-downstream-status`；否则让用户先重置受影响状态。

## 每轮汇报

报告：基线 ID、当前阶段、计划总数、有效计划数、过期计划数、研发完成数、自测完成数、阻塞数、本轮状态变化、下一条待处理故事和需要用户确认的决定。
