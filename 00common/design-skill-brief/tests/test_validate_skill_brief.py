from __future__ import annotations

import json
import subprocess
import sys
import tempfile
import unittest
from pathlib import Path


ROOT = Path(__file__).resolve().parents[1]
SCRIPTS = ROOT / "scripts"
sys.path.insert(0, str(SCRIPTS))

from validate_skill_brief import validate  # noqa: E402


def make_brief(mode: str = "契约型") -> str:
    checkpoints = "不适用"
    sop = "不适用"
    mapping = "不适用"

    if mode in {"检查点型", "混合型"}:
        checkpoints = (
            "- 检查点 1：进入条件为输入齐全；必须产物为边界清单；"
            "退出条件为边界已确认。"
        )
    if mode in {"SOP 型", "混合型"}:
        sop = (
            "1. 步骤、命令或工具：运行确定性脚本。\n"
            "2. 判断条件：退出码必须为 0。\n"
            "3. 失败处理：停止执行并保留日志。\n"
            "4. 回滚或停止条件：恢复执行前的文件。"
        )
    if mode == "混合型":
        mapping = (
            "| 阶段 | 执行约束模式 | 必须产物 | 进入下一阶段的条件 |\n"
            "|---|---|---|---|\n"
            "| 需求澄清 | 契约型 | 任务契约 | 用户确认 |\n"
            "| 发布执行 | SOP 型 | 发布记录 | 校验通过 |"
        )

    return f"""# Skill 需求文档：demo-skill

## 结论

- 推荐动作：新建 Skill
- 推荐名称：demo-skill
- 推荐执行约束模式：{mode}
- 选择依据：任务可变性和错误成本已经明确。
- 推荐资源：仅 SKILL.md
- 目标路径：/tmp/demo-skill

## 这个 Skill 只解决什么问题

为一个明确任务生成稳定结果。

## 触发场景

- 用户可能会说：帮我设计这个 Skill。
- 用户可能会说：把这个想法整理成 Skill 需求。

## 不适用场景

- 不处理：普通领域知识问答。

## 任务契约

### 输入

- 必需输入：目标和真实示例。

### 输出

- 输出形式：Markdown 需求文档。

### 红线

- 禁止：编造用户未提供的业务事实。

### 验收标准

- 可以检查：触发边界和输出要求完整。

## 执行约束设计

- 推荐模式：{mode}
- 模型可自主决定：阶段内的分析方式。
- 必须遵守：任务契约和已确认边界。
- 升级条件：出现不可逆外部操作时升级为 SOP 型。

### 必经检查点

{checkpoints}

### SOP 与异常处理

{sop}

### 阶段映射

{mapping}

## 核心流程

1. 确认任务契约。
2. 生成并校验需求文档。

## 固定分支选项

- 开发方式：新建 Skill。

## references 设计

- 不需要 references：规则足够短。

## scripts 设计

- 不需要脚本：没有重复的确定性操作。

## assets 设计

- 不需要 assets：不生成视觉资源。

## 容易跑偏的点

- 不要扩大为万能 Skill。

## 创建前检查清单

- [x] 任务契约完整。

## 待确认问题

- 无，需求已经确认。
"""


class ValidateSkillBriefTests(unittest.TestCase):
    def test_all_four_modes_accept_complete_briefs(self) -> None:
        for mode in ("契约型", "检查点型", "SOP 型", "混合型"):
            with self.subTest(mode=mode):
                self.assertEqual(validate(make_brief(mode)), [])

    def test_requires_two_trigger_examples(self) -> None:
        brief = make_brief().replace(
            "- 用户可能会说：把这个想法整理成 Skill 需求。\n", ""
        )
        self.assertIn("触发场景至少需要 2 条“用户可能会说”", validate(brief))

    def test_requires_each_contract_section(self) -> None:
        brief = make_brief().replace("### 红线", "### 风险")
        self.assertIn("任务契约缺少三级标题：### 红线", validate(brief))

    def test_rejects_not_applicable_contract_content(self) -> None:
        brief = make_brief().replace(
            "- 禁止：编造用户未提供的业务事实。", "不适用"
        )
        self.assertIn("任务契约内容不能为空或写成不适用：红线", validate(brief))

    def test_rejects_template_placeholders(self) -> None:
        brief = make_brief().replace("demo-skill", "{skill-name}", 1)
        self.assertIn("文档仍包含未替换的模板占位符", validate(brief))

    def test_rejects_parallel_legacy_type(self) -> None:
        brief = make_brief().replace(
            "- 推荐资源：仅 SKILL.md", "- 推荐类型：流程型\n- 推荐资源：仅 SKILL.md"
        )
        self.assertIn(
            "不要并列维护“推荐类型”；统一使用执行约束模式", validate(brief)
        )

    def test_rejects_mode_mismatch(self) -> None:
        brief = make_brief().replace("- 推荐模式：契约型", "- 推荐模式：检查点型")
        self.assertIn("结论与执行约束设计中的推荐模式不一致", validate(brief))

    def test_checkpoint_mode_requires_real_checkpoint(self) -> None:
        brief = make_brief("检查点型").replace(
            "- 检查点 1：进入条件为输入齐全；必须产物为边界清单；退出条件为边界已确认。",
            "不适用",
        )
        self.assertIn("检查点型必须定义必经检查点", validate(brief))

    def test_sop_mode_requires_failure_and_rollback(self) -> None:
        brief = make_brief("SOP 型").replace("失败处理", "异常记录").replace(
            "回滚或停止条件", "完成条件"
        )
        errors = validate(brief)
        self.assertIn("SOP 型必须写明失败处理", errors)
        self.assertIn("SOP 型必须写明回滚或停止条件", errors)

    def test_mixed_mode_requires_two_distinct_modes(self) -> None:
        brief = make_brief("混合型").replace("| 发布执行 | SOP 型 |", "| 发布执行 | 契约型 |")
        self.assertIn(
            "混合型阶段映射至少需要两个阶段且使用两种不同模式",
            validate(brief),
        )

    def test_cli_supports_json_and_stdin(self) -> None:
        result = subprocess.run(
            [sys.executable, str(SCRIPTS / "validate_skill_brief.py"), "-", "--json"],
            input=make_brief(),
            text=True,
            capture_output=True,
            check=False,
        )
        self.assertEqual(result.returncode, 0, result.stderr)
        self.assertEqual(json.loads(result.stdout), {"valid": True, "errors": []})

    def test_cli_returns_nonzero_for_invalid_brief(self) -> None:
        result = subprocess.run(
            [sys.executable, str(SCRIPTS / "validate_skill_brief.py"), "-"],
            input="# invalid\n",
            text=True,
            capture_output=True,
            check=False,
        )
        self.assertEqual(result.returncode, 1)
        self.assertIn("ERROR:", result.stdout)

    def test_cli_validates_a_file_path(self) -> None:
        with tempfile.TemporaryDirectory() as tmpdir:
            brief_path = Path(tmpdir) / "skill-brief.md"
            brief_path.write_text(make_brief("混合型"), encoding="utf-8")
            result = subprocess.run(
                [sys.executable, str(SCRIPTS / "validate_skill_brief.py"), str(brief_path)],
                text=True,
                capture_output=True,
                check=False,
            )
        self.assertEqual(result.returncode, 0, result.stderr)
        self.assertEqual(result.stdout.strip(), "OK: skill brief is valid")

    def test_cli_returns_two_for_missing_file(self) -> None:
        result = subprocess.run(
            [
                sys.executable,
                str(SCRIPTS / "validate_skill_brief.py"),
                "/path/that/does/not/exist/skill-brief.md",
                "--json",
            ],
            text=True,
            capture_output=True,
            check=False,
        )
        self.assertEqual(result.returncode, 2)
        payload = json.loads(result.stdout)
        self.assertFalse(payload["valid"])
        self.assertTrue(payload["errors"])


if __name__ == "__main__":
    unittest.main()
