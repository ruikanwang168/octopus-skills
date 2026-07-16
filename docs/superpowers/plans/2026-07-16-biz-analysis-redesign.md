# Biz Analysis Skill Redesign Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** Rebuild `biz-analysis` around a four-layer, 16-point business-analysis framework that uncovers real needs without drifting into PRD, prototype, or technical implementation details.

**Architecture:** Keep `SKILL.md` as the checkpoint-driven conversation controller. Move the full applicability matrix, depth rules, and analysis boundaries to `references/analysis-framework.md`; keep final document structures in `references/document-template.md`. A local validation script provides repeatable structural and regression checks for the three project types.

**Tech Stack:** Markdown, YAML, Python 3, the existing `skill-creator` validation scripts.

---

### Task 1: Establish the failing behavior contract

**Files:**
- Create: `01product/01demand/biz-analysis/tests/validate_skill.py`
- Reference: `docs/superpowers/specs/2026-07-16-biz-analysis-redesign.md`

- [ ] **Step 1: Write the failing validation test**

Create a Python test that asserts:

```python
from pathlib import Path
import re
import sys

ROOT = Path(__file__).resolve().parents[1]

EXPECTED_POINTS = [
    "名词解释", "业务背景", "业务痛点", "涉及角色", "解决方案", "实现边界",
    "核心流程", "功能清单", "业务实体", "业务状态", "数据权限", "异常兜底",
    "外部依赖", "老数据兼容", "非功能指标", "审计可观测",
]


def read(relative: str) -> str:
    path = ROOT / relative
    if not path.exists():
        raise AssertionError(f"missing required file: {relative}")
    return path.read_text(encoding="utf-8")


def require(text: str, pattern: str, label: str) -> None:
    if not re.search(pattern, text, re.MULTILINE):
        raise AssertionError(f"missing {label}: {pattern}")


def main() -> int:
    skill = read("SKILL.md")
    framework = read("references/analysis-framework.md")
    template = read("references/document-template.md")
    readme = read("README.md")
    metadata = read("agents/openai.yaml")

    require(skill, r"(?m)^description:\s*\|\n\s+Use when", "trigger-focused description")
    for point in EXPECTED_POINTS:
        if point not in framework or point not in template:
            raise AssertionError(f"16-point coverage missing: {point}")

    for phrase in [
        "每轮只问 2 到 4 个问题",
        "表面诉求",
        "必要性检验",
        "不按 16 个考量点逐项提问",
        "references/analysis-framework.md",
        "references/document-template.md",
    ]:
        if phrase not in skill:
            raise AssertionError(f"conversation guard missing: {phrase}")

    for phrase in [
        "页面布局", "按钮放在哪里", "数据库字段", "技术状态机", "监控实现",
    ]:
        if phrase not in framework:
            raise AssertionError(f"detail boundary missing: {phrase}")

    expected_tables = [
        "| 业务模块 | 一级能力 | 二级能力 | 使用角色 | 触发场景 | 业务动作 | 业务对象 | 业务结果 | 版本边界 |",
        "| 变更类型 | 现有能力 | 新增、调整或废弃内容 | 受影响角色 | 流程位置 | 影响对象 | 业务结果 | 兼容要求 |",
        "| 动作点 | 输入 | 处理规则 | 输出 | 异常处理 |",
    ]
    for table in expected_tables:
        if table not in template:
            raise AssertionError(f"project-specific function table missing: {table}")

    if "16 个核心考量点" not in readme:
        raise AssertionError("README does not describe the 16-point framework")
    if '$biz-analysis' not in metadata:
        raise AssertionError("openai metadata default prompt must mention $biz-analysis")

    print("OK: biz-analysis structural and behavior contract passed")
    return 0


if __name__ == "__main__":
    sys.exit(main())
```

- [ ] **Step 2: Run the test and verify RED**

Run:

```bash
python3 01product/01demand/biz-analysis/tests/validate_skill.py
```

Expected: fail with `missing required file: references/analysis-framework.md`. This proves the current Skill does not implement the approved 16-point analysis controller.

### Task 2: Add the reusable 16-point analysis framework

**Files:**
- Create: `01product/01demand/biz-analysis/references/analysis-framework.md`

- [ ] **Step 1: Write the four-layer applicability matrix**

Include all 16 points and the exact depth for full product, incremental iteration, and small tool projects.

- [ ] **Step 2: Write the real-needs and question-admission rules**

Include the causal chain:

```text
表面诉求 → 触发场景 → 当前做法 → 真正障碍 → 业务影响 → 期望结果 → 必要能力
```

Require evidence-first extraction, necessity testing, 2–4 questions per round, and explicit stop conditions.

- [ ] **Step 3: Define each point's business-level boundary**

For every point, specify its analysis target, applicable project types, useful evidence, allowed questions, stop condition, and prohibited PRD/technical details.

### Task 3: Rebuild the conversation controller

**Files:**
- Modify: `01product/01demand/biz-analysis/SKILL.md`

- [ ] **Step 1: Replace the frontmatter description**

Use a third-person trigger-only description beginning with `Use when`, covering new business systems, incremental features, small tools, and requirements clarification.

- [ ] **Step 2: Replace the workflow with checkpoint-driven behavior**

Implement four checkpoints: project routing, real-needs validation, 16-point baseline lock, and final user confirmation.

- [ ] **Step 3: Add reference routing and stop conditions**

Read `analysis-framework.md` after project type confirmation. Read `document-template.md` only after the final consensus summary is confirmed.

### Task 4: Rebuild the delivery adapter

**Files:**
- Modify: `01product/01demand/biz-analysis/references/document-template.md`

- [ ] **Step 1: Replace the nine-chapter template with four layers and 16 points**

Allow omission of inapplicable sections; append pending questions without treating them as a seventeenth point.

- [ ] **Step 2: Add project-specific function tables**

Use the exact three schemas asserted in `tests/validate_skill.py`.

- [ ] **Step 3: Add business-level tables for entities, states, permissions, defense, and observability**

Keep the tables implementation-neutral and preserve `已确认 / 当前推测 / 待确认` markers.

### Task 5: Align user-facing metadata and documentation

**Files:**
- Modify: `01product/01demand/biz-analysis/README.md`
- Modify: `01product/01demand/biz-analysis/agents/openai.yaml`

- [ ] **Step 1: Update README**

Describe the four layers, 16 points, three project routes, real-needs causal chain, and non-PRD boundary.

- [ ] **Step 2: Update metadata**

Set a 25–64 character short description and a one-sentence default prompt that explicitly contains `$biz-analysis`.

### Task 6: Verify GREEN and validate the Skill package

**Files:**
- Test: `01product/01demand/biz-analysis/tests/validate_skill.py`
- Validate: `01product/01demand/biz-analysis/SKILL.md`
- Validate: `01product/01demand/biz-analysis/agents/openai.yaml`

- [ ] **Step 1: Run the behavior contract**

```bash
python3 01product/01demand/biz-analysis/tests/validate_skill.py
```

Expected: `OK: biz-analysis structural and behavior contract passed`.

- [ ] **Step 2: Run the official Skill validator**

```bash
python3 /Users/ruikanwang/.codex/skills/.system/skill-creator/scripts/quick_validate.py \
  01product/01demand/biz-analysis
```

Expected: successful validation with no frontmatter or naming errors.

- [ ] **Step 3: Run consistency checks**

```bash
rg -n "TBD|TODO|为了更好地|全面提升|有效赋能|综上所述" \
  01product/01demand/biz-analysis
```

Expected: no matches.

```bash
git diff --check
```

Expected: no whitespace errors.

- [ ] **Step 4: Review the three behavior scenarios**

Confirm from the instructions that:

- Full product prompts uncover real needs and cover all applicable points without UI questions.
- Increment prompts focus on new/changed/removed behavior, differences, defense, and old-data compatibility.
- Small-tool prompts focus on pain, solution, boundary, input-processing-output, function actions, and exceptions.

- [ ] **Step 5: Inspect the final diff without reverting pre-existing user changes**

```bash
git diff -- 01product/01demand/biz-analysis
```

Expected: only the approved redesign layered on top of the existing working-tree changes.

### Task 7: Flatten and continuously renumber final document headings

**Files:**
- Modify: `01product/01demand/biz-analysis/tests/validate_skill.py`
- Modify: `01product/01demand/biz-analysis/references/document-template.md`
- Modify: `01product/01demand/biz-analysis/SKILL.md`
- Modify: `01product/01demand/biz-analysis/README.md`

- [ ] **Step 1: Add a failing heading regression test**

Assert that the delivery template contains no `## 一、认知层`、`## 二、边界层`、`## 三、交付层` or `## 四、防御层` heading. Assert that reference sections are unnumbered, and that the output rule requires selecting applicable sections first and then numbering the retained sections continuously from 1 without gaps.

- [ ] **Step 2: Run the regression test and verify RED**

```bash
python3 01product/01demand/biz-analysis/tests/validate_skill.py
```

Expected: fail because the current template still requires fixed 1–16 headings and explicitly permits number gaps.

- [ ] **Step 3: Flatten the delivery template**

Keep the four layer headings out of the formal document. Use unnumbered headings for the 16 reference definitions so they cannot be copied as fixed output numbers. Require the generator to remove inapplicable sections first, preserve the remaining business order, and then number output headings from 1 continuously without gaps.

- [ ] **Step 4: Align controller and README wording**

Clarify that the four layers and fixed 16 point IDs are internal only; final document numbers express reading order and must be regenerated after project-specific pruning.

- [ ] **Step 5: Verify GREEN**

```bash
python3 01product/01demand/biz-analysis/tests/validate_skill.py
uv run --with pyyaml python /Users/ruikanwang/.codex/skills/.system/skill-creator/scripts/quick_validate.py \
  01product/01demand/biz-analysis
git diff --check
```

Expected: the behavior contract and official Skill validator pass, with no whitespace errors.
