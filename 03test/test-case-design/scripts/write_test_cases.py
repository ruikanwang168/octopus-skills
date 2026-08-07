#!/usr/bin/env python3
"""将标准化中文测试用例从 JSON 写入 XLSX 或 CSV。"""

from __future__ import annotations

import argparse
import csv
import json
import re
import sys
from pathlib import Path
from typing import Any


HEADERS = [
    "所属产品",
    "所属模块",
    "相关研发需求",
    "用例名称",
    "前置条件",
    "关键词",
    "优先级",
    "用例类型",
    "适用阶段",
    "用例状态",
    "步骤",
    "预期",
]

ALLOWED_PRIORITIES = {"P0", "P1", "P2"}
ALLOWED_CASE_TYPES = {"功能", "异常", "边界", "权限", "接口", "兼容", "性能", "安全", "UI"}
ALLOWED_STAGES = {"系统测试", "回归测试", "集成测试", "验收测试"}
ALLOWED_STATUSES = {"待评审"}
CONTAINER_KEYS = ("cases", "用例", "test_cases")
NUMBERED_LINE = re.compile(r"^\d+[.、)]\s*\S")
OPERATION_ID = re.compile(r"\bOP-\d{3,}\b", re.IGNORECASE)
VAGUE_EXPECTATIONS = {"正常", "正确", "成功", "符合预期"}
FORMULA_PREFIXES = ("=", "+", "-", "@")


class ChineseArgumentParser(argparse.ArgumentParser):
    def format_usage(self) -> str:
        return super().format_usage().replace("usage:", "用法:", 1)

    def format_help(self) -> str:
        return super().format_help().replace("usage:", "用法:", 1)


def normalize_text(value: str) -> str:
    text = value.strip()
    text = re.sub(r"<br\s*/?>", "\n", text, flags=re.IGNORECASE)
    return (
        text.replace("\r\n", "\n")
        .replace("\r", "\n")
        .replace("\\r\\n", "\n")
        .replace("\\n", "\n")
        .replace("\\r", "\n")
    )


def format_cell(value: Any) -> str:
    if value is None:
        return ""
    if isinstance(value, str):
        return normalize_text(value)
    if isinstance(value, (int, float, bool)):
        return str(value)
    if isinstance(value, list):
        lines: list[str] = []
        for index, item in enumerate(value, start=1):
            if isinstance(item, dict):
                text = item.get("text") or item.get("内容") or item.get("步骤") or item.get("预期") or item
                lines.append(f"{index}. {format_cell(text)}")
            else:
                text = format_cell(item)
                lines.append(text if text.startswith(f"{index}.") else f"{index}. {text}")
        return "\n".join(lines)
    if isinstance(value, dict):
        return json.dumps(value, ensure_ascii=False, separators=(",", ":"))
    return str(value)


def validate_numbered_lines(value: str, field: str, index: int, require_all: bool) -> None:
    lines = [line.strip() for line in value.splitlines() if line.strip()]
    if not lines:
        raise ValueError(f"第 {index} 条用例的“{field}”不能为空。")
    if require_all or len(lines) > 1:
        invalid = [line for line in lines if not NUMBERED_LINE.match(line)]
        if invalid:
            raise ValueError(f"第 {index} 条用例的“{field}”必须逐行编号。")


def validate_case(item: dict[str, Any], index: int) -> dict[str, str]:
    missing = [header for header in HEADERS if header not in item]
    if missing:
        raise ValueError(f"第 {index} 条用例缺少字段：{', '.join(missing)}。")

    extra = [key for key in item if key not in HEADERS]
    if extra:
        raise ValueError(f"第 {index} 条用例包含未知字段：{', '.join(extra)}。")

    case = {header: format_cell(item[header]) for header in HEADERS}
    empty = [header for header, value in case.items() if not value]
    if empty:
        raise ValueError(f"第 {index} 条用例存在空字段：{', '.join(empty)}。")

    if case["优先级"] not in ALLOWED_PRIORITIES:
        raise ValueError(f"第 {index} 条用例的“优先级”必须是 P0、P1 或 P2。")
    if case["用例类型"] not in ALLOWED_CASE_TYPES:
        allowed = "、".join(sorted(ALLOWED_CASE_TYPES))
        raise ValueError(f"第 {index} 条用例的“用例类型”必须是：{allowed}。")
    if case["适用阶段"] not in ALLOWED_STAGES:
        allowed = "、".join(sorted(ALLOWED_STAGES))
        raise ValueError(f"第 {index} 条用例的“适用阶段”必须是：{allowed}。")
    if case["用例状态"] not in ALLOWED_STATUSES:
        raise ValueError(f"第 {index} 条用例的“用例状态”必须是待评审。")
    if not OPERATION_ID.search(case["关键词"]):
        raise ValueError(f"第 {index} 条用例的“关键词”必须包含 OP-001 形式的操作标识。")

    validate_numbered_lines(case["步骤"], "步骤", index, require_all=True)
    validate_numbered_lines(case["预期"], "预期", index, require_all=False)

    expectation_texts = {
        re.sub(r"^\d+[.、)]\s*", "", line).strip()
        for line in case["预期"].splitlines()
        if line.strip()
    }
    vague = expectation_texts & VAGUE_EXPECTATIONS
    if vague:
        raise ValueError(f"第 {index} 条用例的“预期”不能只写：{'、'.join(sorted(vague))}。")

    return case


def load_cases(path: Path) -> list[dict[str, str]]:
    data = json.loads(path.read_text(encoding="utf-8"))
    if isinstance(data, dict):
        for key in CONTAINER_KEYS:
            if key in data:
                data = data[key]
                break
        else:
            raise ValueError("输入对象必须包含 cases、用例或 test_cases 数组。")
    if not isinstance(data, list):
        raise ValueError("输入 JSON 必须是列表，或是包含 cases 数组的对象。")
    if not data:
        raise ValueError("用例列表不能为空。")

    cases: list[dict[str, str]] = []
    for index, item in enumerate(data, start=1):
        if not isinstance(item, dict):
            raise ValueError(f"第 {index} 条用例必须是对象。")
        cases.append(validate_case(item, index))
    return cases


def ensure_output_available(output: Path, force: bool) -> None:
    if output.exists() and not force:
        raise FileExistsError(f"输出文件已存在：{output}。确认覆盖后使用 --force。")
    output.parent.mkdir(parents=True, exist_ok=True)


def protect_csv_formula(value: str) -> str:
    if value.lstrip().startswith(FORMULA_PREFIXES):
        return "'" + value
    return value


def write_csv(cases: list[dict[str, str]], output: Path, force: bool = False) -> Path:
    ensure_output_available(output, force)
    with output.open("w", encoding="utf-8-sig", newline="") as handle:
        writer = csv.DictWriter(handle, fieldnames=HEADERS)
        writer.writeheader()
        writer.writerows(
            {header: protect_csv_formula(case[header]) for header in HEADERS}
            for case in cases
        )
    return output


def write_xlsx(cases: list[dict[str, str]], output: Path, force: bool = False) -> Path:
    ensure_output_available(output, force)
    try:
        from openpyxl import Workbook
        from openpyxl.styles import Alignment, Font, PatternFill
        from openpyxl.utils import get_column_letter
    except ImportError:
        fallback = output.with_suffix(".csv")
        write_csv(cases, fallback, force=force)
        print(
            f"警告：未安装 openpyxl，已改为写入 CSV 文件：{fallback}",
            file=sys.stderr,
        )
        return fallback

    workbook = Workbook()
    sheet = workbook.active
    sheet.title = "测试用例"
    sheet.append(HEADERS)

    for row_index, case in enumerate(cases, start=2):
        for column_index, header in enumerate(HEADERS, start=1):
            cell = sheet.cell(row=row_index, column=column_index, value=case[header])
            cell.data_type = "s"

    header_fill = PatternFill("solid", fgColor="D9EAF7")
    for cell in sheet[1]:
        cell.font = Font(bold=True)
        cell.fill = header_fill
        cell.alignment = Alignment(horizontal="center", vertical="center", wrap_text=True)

    widths = {
        "所属产品": 16,
        "所属模块": 18,
        "相关研发需求": 28,
        "用例名称": 32,
        "前置条件": 30,
        "关键词": 18,
        "优先级": 10,
        "用例类型": 12,
        "适用阶段": 14,
        "用例状态": 12,
        "步骤": 44,
        "预期": 44,
    }
    for index, header in enumerate(HEADERS, start=1):
        sheet.column_dimensions[get_column_letter(index)].width = widths[header]

    for row in sheet.iter_rows(min_row=2):
        max_lines = 1
        for cell in row:
            cell.alignment = Alignment(vertical="top", wrap_text=True)
            if isinstance(cell.value, str):
                max_lines = max(max_lines, len(cell.value.splitlines()) or 1)
        sheet.row_dimensions[row[0].row].height = min(18 + (max_lines - 1) * 16, 180)

    sheet.freeze_panes = "A2"
    workbook.save(output)
    return output


def main() -> int:
    parser = ChineseArgumentParser(
        description="将测试用例 JSON 写入 XLSX 或 CSV。",
        add_help=False,
        usage="%(prog)s 输入文件 [--output 输出文件] [--force]",
    )
    parser._positionals.title = "位置参数"
    parser._optionals.title = "可选参数"
    parser.add_argument("input", type=Path, metavar="输入文件", help="包含生成测试用例的 JSON 文件。")
    parser.add_argument("-h", "--help", action="help", help="显示帮助信息并退出。")
    parser.add_argument(
        "--output",
        "-o",
        type=Path,
        metavar="输出文件",
        default=Path("测试用例.xlsx"),
        help="输出 .xlsx 或 .csv 路径，默认生成 测试用例.xlsx。",
    )
    parser.add_argument(
        "--force",
        action="store_true",
        help="允许覆盖已存在的输出文件。",
    )
    args = parser.parse_args()

    try:
        cases = load_cases(args.input)
        suffix = args.output.suffix.lower()
        if suffix == ".csv":
            written = write_csv(cases, args.output, force=args.force)
        elif suffix == ".xlsx":
            written = write_xlsx(cases, args.output, force=args.force)
        else:
            raise ValueError("输出路径必须以 .xlsx 或 .csv 结尾。")
    except Exception as exc:
        print(f"错误：{exc}", file=sys.stderr)
        return 1

    print(f"已写入 {len(cases)} 条用例：{written}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
