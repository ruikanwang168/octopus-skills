#!/usr/bin/env python3
"""
根据内置模板创建设计系统目录。

默认格式是统一可执行设计系统（10 章 DESIGN.md + DESIGN_GAPS.md）。
历史格式只在 validate_design_folder.py 中保留校验能力；新脚手架仅生成 v3。
"""

from __future__ import annotations

import argparse
import json
import re
import sys
from pathlib import Path


TEMPLATE_MAP = {
    "ai-design-system-v3": {
        "preview.html": "preview.template.html",
        "preview-dark.html": "preview-dark.template.html",
        "example.html": "example.template.html",
        "DESIGN_GAPS.md": "DESIGN_GAPS.template.md",
    },
}


def slugify(value: str) -> str:
    slug = value.strip().lower()
    slug = re.sub(r"[^a-z0-9]+", "-", slug)
    slug = re.sub(r"-{2,}", "-", slug).strip("-")
    return slug or "design-system"


def load_template(template_name: str) -> str:
    assets_dir = Path(__file__).resolve().parent.parent / "assets"
    template_path = assets_dir / template_name
    return template_path.read_text(encoding="utf-8")


def write_file(path: Path, content: str, force: bool) -> None:
    if path.exists() and not force:
        raise FileExistsError(f"{path} 已存在。请使用 --force 覆盖。")
    path.write_text(content, encoding="utf-8")


def main() -> int:
    parser = argparse.ArgumentParser(description="根据模板生成设计系统目录。")
    parser.add_argument(
        "--output",
        default=None,
        help=(
            "显式输出目录。该参数会覆盖 --project-root。"
            "未提供时，如果有 --project-root，则使用 <project-root>/DESIGN，否则使用 ./DESIGN。"
        ),
    )
    parser.add_argument(
        "--project-root",
        default=None,
        help="被分析项目根目录。未提供 --output 时用于创建 <project-root>/DESIGN。",
    )
    parser.add_argument(
        "--name",
        default="MUST_REPLACE_PRODUCT_NAME",
        help="模板中使用的产品或站点名称。已知真实目标名称时应传入真实名称。",
    )
    parser.add_argument(
        "--force",
        action="store_true",
        help="当输出文件已存在时覆盖它们。",
    )
    parser.add_argument(
        "--markdown-name",
        choices=("DESIGN.md", "design.md"),
        default="DESIGN.md",
        help="Markdown 设计文件名。默认 DESIGN.md。",
    )
    parser.add_argument(
        "--language",
        default="auto",
        help="输出文档语言提示，例如 auto、zh-CN 或 en。默认 auto。",
    )
    parser.add_argument(
        "--format",
        choices=("ai-design-system-v3",),
        default="ai-design-system-v3",
        help=(
            "输出格式。新脚手架仅支持 'ai-design-system-v3'。"
            "该格式会生成统一可执行 schema、10 章 DESIGN.md、DESIGN_GAPS.md、"
            "preview.html、preview-dark.html 和 example.html。"
        ),
    )
    args = parser.parse_args()

    if args.output:
        output_dir = Path(args.output).expanduser().resolve()
    elif args.project_root:
        output_dir = Path(args.project_root).expanduser().resolve() / "DESIGN"
    else:
        output_dir = Path("DESIGN").resolve()

    output_dir.mkdir(parents=True, exist_ok=True)

    replacements = {
        "{{PROJECT_NAME}}": args.name,
        "{{PROJECT_NAME_YAML}}": json.dumps(args.name, ensure_ascii=False),
        "{{PROJECT_SLUG}}": slugify(args.name),
        "{{LANGUAGE}}": args.language,
    }

    template_set = TEMPLATE_MAP[args.format]
    # TEMPLATE_MAP 只覆盖非 Markdown 产物。统一 DESIGN.md 模板在这里单独注入，
    # 这样用户可通过 --markdown-name 切换 DESIGN.md / design.md，
    # 不需要修改模板注册表。
    output_map: dict[str, str] = dict(template_set)
    output_map[args.markdown_name] = "DESIGN.template.md"

    for output_name, template_name in output_map.items():
        content = load_template(template_name)
        for key, value in replacements.items():
            content = content.replace(key, value)
        write_file(output_dir / output_name, content, args.force)

    print(f"[完成] 已生成设计系统目录：{output_dir}")
    for output_name in output_map:
        print(f" - {output_dir / output_name}")
    return 0


if __name__ == "__main__":
    try:
        raise SystemExit(main())
    except FileExistsError as exc:
        print(f"[错误] {exc}", file=sys.stderr)
        raise SystemExit(1)
