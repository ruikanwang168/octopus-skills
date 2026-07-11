#!/usr/bin/env python3
"""Validate a Markdown brief produced by the design-skill-brief skill."""

from __future__ import annotations

import argparse
import json
import re
import sys
from pathlib import Path


REQUIRED_HEADINGS = (
    "结论",
    "这个 Skill 只解决什么问题",
    "触发场景",
    "不适用场景",
    "任务契约",
    "执行约束设计",
    "核心流程",
    "固定分支选项",
    "references 设计",
    "scripts 设计",
    "assets 设计",
    "容易跑偏的点",
    "创建前检查清单",
    "待确认问题",
)

CONTRACT_HEADINGS = ("输入", "输出", "红线", "验收标准")
VALID_MODES = ("契约型", "检查点型", "SOP 型", "SOP型", "混合型")
REQUIRED_CONCLUSION_KEYS = (
    "推荐动作",
    "推荐名称",
    "推荐执行约束模式",
    "选择依据",
    "推荐资源",
    "目标路径",
)


def heading_exists(text: str, heading: str, level: str = "##") -> bool:
    pattern = rf"(?m)^{re.escape(level)}\s+{re.escape(heading)}\s*$"
    return re.search(pattern, text) is not None


def section_body(text: str, heading: str, level: int = 2) -> str:
    marker = "#" * level
    match = re.search(
        rf"(?m)^{re.escape(marker)}\s+{re.escape(heading)}\s*$", text
    )
    if not match:
        return ""
    body_start = match.end()
    next_heading = re.search(
        rf"(?m)^#{{1,{level}}}\s+.+$", text[body_start:]
    )
    body_end = body_start + next_heading.start() if next_heading else len(text)
    return text[body_start:body_end].strip()


def recommended_mode(text: str) -> str | None:
    match = re.search(
        r"(?m)^-\s*推荐执行约束模式[：:]\s*(契约型|检查点型|SOP\s*型|混合型)\s*$",
        text,
    )
    if not match:
        return None
    value = re.sub(r"\s+", " ", match.group(1)).strip()
    return "SOP 型" if value in {"SOP 型", "SOP型"} else value


def is_not_applicable(body: str) -> bool:
    normalized = re.sub(r"[\s\-_*`。；;：:]", "", body)
    return normalized in {"", "不适用", "无"}


def has_template_placeholder(text: str) -> bool:
    if re.search(r"\{[^{}\n]+\}", text):
        return True
    if re.search(
        r"(?m)^\s*(?:[-*]|\d+\.)?\s*(?:[^：:\n]+[：:])?\s*(?:\.{3}|…+)\s*$",
        text,
    ):
        return True
    return re.search(r"(?m)^\|.*\|\s*(?:\.{3}|…+)\s*\|", text) is not None


def normalize_mode(value: str) -> str:
    normalized = re.sub(r"\s+", " ", value).strip()
    return "SOP 型" if normalized in {"SOP 型", "SOP型"} else normalized


def validate(text: str) -> list[str]:
    errors: list[str] = []

    if not re.search(r"(?m)^#\s+Skill 需求文档：\S.+$", text):
        errors.append("缺少标题：# Skill 需求文档：{skill-name}")

    for heading in REQUIRED_HEADINGS:
        if not heading_exists(text, heading):
            errors.append(f"缺少二级标题：## {heading}")
        elif not section_body(text, heading):
            errors.append(f"章节内容不能为空：{heading}")

    for heading in CONTRACT_HEADINGS:
        if not heading_exists(text, heading, "###"):
            errors.append(f"任务契约缺少三级标题：### {heading}")
        elif is_not_applicable(section_body(text, heading, level=3)):
            errors.append(f"任务契约内容不能为空或写成不适用：{heading}")

    conclusion = section_body(text, "结论")
    for key in REQUIRED_CONCLUSION_KEYS:
        if not re.search(rf"(?m)^-\s*{re.escape(key)}[：:]\s*\S.+$", conclusion):
            errors.append(f"结论缺少具体字段：{key}")

    trigger_count = len(
        re.findall(r"(?m)^\s*-\s*用户可能会说[：:]\s*\S.+$", text)
    )
    if trigger_count < 2:
        errors.append("触发场景至少需要 2 条“用户可能会说”")

    if not re.search(r"(?m)^-\s*(不处理|不负责|遇到这些情况应改用)[：:]\s*\S.+$", text):
        errors.append("不适用场景至少需要 1 条具体边界")

    mode = recommended_mode(text)
    if mode is None:
        expected = " / ".join(VALID_MODES[:3] + (VALID_MODES[-1],))
        errors.append(f"结论缺少有效的推荐执行约束模式：{expected}")

    if not re.search(r"(?m)^-\s*选择依据[：:]\s*\S.+$", text):
        errors.append("结论缺少具体的模式选择依据")

    if re.search(r"(?m)^-\s*推荐类型[：:]", text):
        errors.append("不要并列维护“推荐类型”；统一使用执行约束模式")

    if has_template_placeholder(text):
        errors.append("文档仍包含未替换的模板占位符")

    execution_section = section_body(text, "执行约束设计")
    if execution_section and "模型可自主决定" not in execution_section:
        errors.append("执行约束设计缺少模型自主范围")

    execution_mode_match = re.search(
        r"(?m)^-\s*推荐模式[：:]\s*(契约型|检查点型|SOP\s*型|混合型)\s*$",
        execution_section,
    )
    if not execution_mode_match:
        errors.append("执行约束设计缺少有效的推荐模式")
    elif mode and normalize_mode(execution_mode_match.group(1)) != mode:
        errors.append("结论与执行约束设计中的推荐模式不一致")

    if mode == "检查点型":
        checkpoint_body = section_body(text, "必经检查点", level=3)
        if is_not_applicable(checkpoint_body):
            errors.append("检查点型必须定义必经检查点")
        elif "进入条件" not in checkpoint_body or "退出条件" not in checkpoint_body:
            errors.append("检查点型必须写明检查点的进入条件和退出条件")
    if mode == "SOP 型":
        sop_body = section_body(text, "SOP 与异常处理", level=3)
        if is_not_applicable(sop_body):
            errors.append("SOP 型必须定义 SOP 与异常处理")
        if "失败处理" not in sop_body:
            errors.append("SOP 型必须写明失败处理")
        if "回滚" not in sop_body and "停止条件" not in sop_body:
            errors.append("SOP 型必须写明回滚或停止条件")
    if mode == "混合型":
        mapping_body = section_body(text, "阶段映射", level=3)
        if is_not_applicable(mapping_body):
            errors.append("混合型必须定义阶段映射")
        else:
            mapped_modes = {
                normalize_mode(item)
                for item in re.findall(
                    r"(?m)^\|\s*[^|\n]+\s*\|\s*(契约型|检查点型|SOP\s*型)\s*\|",
                    mapping_body,
                )
            }
            if len(mapped_modes) < 2:
                errors.append("混合型阶段映射至少需要两个阶段且使用两种不同模式")

    return errors


def read_input(path: str) -> str:
    if path == "-":
        return sys.stdin.read()
    return Path(path).read_text(encoding="utf-8")


def main() -> int:
    parser = argparse.ArgumentParser(
        description="Validate a Markdown Skill requirements brief."
    )
    parser.add_argument("brief", help="Path to skill-brief.md, or - for stdin")
    parser.add_argument("--json", action="store_true", help="Print JSON output")
    args = parser.parse_args()

    try:
        content = read_input(args.brief)
    except OSError as exc:
        payload = {"valid": False, "errors": [str(exc)]}
        if args.json:
            print(json.dumps(payload, ensure_ascii=False, indent=2))
        else:
            print(f"ERROR: {exc}", file=sys.stderr)
        return 2

    errors = validate(content)
    payload = {"valid": not errors, "errors": errors}
    if args.json:
        print(json.dumps(payload, ensure_ascii=False, indent=2))
    elif errors:
        for error in errors:
            print(f"ERROR: {error}")
    else:
        print("OK: skill brief is valid")
    return 1 if errors else 0


if __name__ == "__main__":
    sys.exit(main())
