---
name: prd-to-plan
description: 以软件架构师身份，把 PRD 文件或在线地址、可运行原型、现有前后端代码、现有全量数据库脚本和辅助资料，分阶段整理为经用户确认、可续跑、可追踪并可直接交给 AI 智能体开发的执行包。用于先确认资料范围，再完成技术选型和用户故事拆解；阶段 3先生成以单个用户故事为阅读主线的 AI执行清单确认.md，让用户在同一处确认该故事的页面、按钮、自动行为和业务接口能力，再派生 AI执行清单.json，不提前设计接口地址、前端路由或代码改造方式；阶段 4按故事检索现有代码，生成 OpenAPI、页面与接口实现细节、数据库设计和测试，并严格核对每个操作的实现决策。也用于再次调用时检测确认 MD 变化并安全重生成 JSON、标记过期计划。
---

# PRD 到 AI 执行计划

把产品材料转换为可实施的工程基线。按确认门逐阶段推进；不要把规划与实际研发混为一谈，也不要修改业务源码，除非用户另行明确要求实施。

## 每次调用的加载顺序

1. 确定项目根目录和输出目录。默认在项目根目录使用 `ai-execution-plan/`；尊重用户指定位置。
2. 完整读取 [references/core-rules.md](references/core-rules.md)。这是所有阶段唯一的共享业务规则来源。
3. 完整读取 [references/tracker-and-resume.md](references/tracker-and-resume.md)，发现既有产物并判定当前阶段。
4. 完整读取且只读取当前阶段的规则文件：
   - 阶段 1：[references/stage-1-materials.md](references/stage-1-materials.md)
   - 阶段 2：[references/stage-2-architecture.md](references/stage-2-architecture.md)
   - 阶段 3：[references/stage-3-story-catalog.md](references/stage-3-story-catalog.md)
   - 阶段 4：[references/stage-4-execution-package.md](references/stage-4-execution-package.md)
5. 若正在检查基线漂移，额外读取阶段 1 文件；只有漂移影响架构决策时再读取阶段 2 文件。不要为方便而预加载所有阶段规则。
6. 阶段 4 应重新读取当前故事引用的已确认物料、选型、PRD 片段、原型和代码；不要用阶段 1–3 规则文件替代真实项目产物。

## 阶段路由

按照 `tracker-and-resume.md` 的判定顺序执行：

1. 物料清单缺失、未确认、不符合当前阶段 1范围规则或发生漂移：执行阶段 1并等待确认。旧清单未明确项目类型和全量数据库基线状态时也回到阶段 1。
2. 技术选型清单缺失、未确认、仍为旧 schema，或本次需求尚未完成技术能力分析：执行阶段 2并等待确认。增量项目即使最终不新增框架，也必须完成“需求功能点 → 现有技术基线 → 沿用结论”的分析并生成确认清单；只有已经针对当前需求确认过沿用/新增结论且基线未漂移时才跳过。
3. 用户故事确认 MD 缺失、未确认或发生变化：执行阶段 3，先生成/更新以故事为主线的确认 MD 并等待确认；不得把全量操作台账或机器 ID 大表放在用户阅读主体，也不得合并多个故事的页面或业务能力。若确认 MD 已是 `confirmed` 且 hash 未变化，只是 JSON 缺失、不是当前 schema、缺少 PRD 操作台账、接口能力引用和逻辑交互载体，则从当前确认 MD 重新派生 JSON，不重复要求同一确认。阶段 3禁止输出接口 Method/Path、前端路由、代码位置和技术变更类型。
4. 目录已确认：执行阶段 4，一次默认只生成一个用户故事的实施包。
5. 所有计划均已生成且不过期：报告研发和自测状态，不替用户修改完成状态。

## 确认门

- 阶段 1、2、3 必须分别取得用户明确确认后才能进入下一阶段。
- 阶段 3例外：用户确认前先生成 `AI执行清单确认.md` 并标记 `confirmation_status: pending`，供用户逐项审阅；其他阶段仍只在对话中展示候选内容，除非用户明确要求保存 `.draft.md`。确认 MD 前不得生成或覆盖正式 JSON。
- 不静默解决 PRD 内部矛盾、关键业务歧义、法规安全冲突或会改变契约的未知项。把受影响范围标为阻塞并请求决策。
- 阶段 4 仅在三项故事产物通过结构校验和“直接开发语义核验”后设置 `plan_generated=true`。`tracker.py validate --check-artifacts` 只证明文件结构与引用关系可解析，不证明页面、接口、数据、源码落点和验证命令已经闭环。不得把计划生成等同于研发完成。

## 跟踪命令

存在 `AI执行清单.json` 时先运行：

```bash
python3 <skill-dir>/scripts/tracker.py validate <output-dir>/AI执行清单.json --check-artifacts
python3 <skill-dir>/scripts/tracker.py status <output-dir>/AI执行清单.json
python3 <skill-dir>/scripts/tracker.py next <output-dir>/AI执行清单.json --phase plan
```

生成一个故事的三项产物，完成阶段 4 的直接开发语义核验且没有阻塞后，才运行：

```bash
python3 <skill-dir>/scripts/tracker.py set <output-dir>/AI执行清单.json <story-id> \
  --field plan_generated --value true --check-artifacts
```

若基线漂移后的旧研发或自测状态仍为 `true`，严格按照 `tracker-and-resume.md` 取得用户对保留或重置的决定。

## 每轮汇报

报告当前基线、当前阶段、读取的阶段规则、本轮新增或更新文件、故事状态统计、阻塞项、需要用户确认的内容和下一次应处理的故事。
