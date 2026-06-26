"""统一 DESIGN.md front matter schema 的辅助函数。

统一 schema 为每类设计事实保留一个权威位置：

- tokens.* 存放颜色、字体、间距、圆角、阴影和动效
- layout.* 存放 shell 和响应式规则
- components.* 存放组件来源、结构和使用规则
- pageTemplates.* 存放页面级生成结构
- generationRules.* 存放 must / mustNot / selfCheck 指南

现有渲染、校验和 gaps 脚本仍会读取若干历史顶层路径。
normalize_design_data() 会把统一 front matter 投影到这些路径，
但不会修改源 DESIGN.md 文件。
"""

from __future__ import annotations

from copy import deepcopy
import re
from typing import Any


def mapping(value: Any, key: str) -> dict[str, Any]:
    if not isinstance(value, dict):
        return {}
    child = value.get(key, {})
    return child if isinstance(child, dict) else {}


def is_unified_schema(data: dict[str, Any] | None) -> bool:
    return isinstance(data, dict) and isinstance(data.get("tokens"), dict)


def parse_simple_yaml(text: str) -> dict[str, Any]:
    """解析生成的 DESIGN.md 中使用的 YAML 子集。

    这是没有 PyYAML 环境下的零依赖兜底解析器。它刻意保持小型，
    但支持本技能最常写出的结构：嵌套映射、列表、带引号标量、
    行内列表、布尔值、数字，以及 ``summary: >`` 这类 literal/folded 块标量。
    """
    lines = text.splitlines()

    def indent_of(line: str) -> int:
        return len(line) - len(line.lstrip(" "))

    def is_ignored(line: str) -> bool:
        stripped = line.strip()
        return not stripped or stripped.startswith("#")

    def skip_ignored(index: int) -> int:
        while index < len(lines) and is_ignored(lines[index]):
            index += 1
        return index

    def parse_scalar(value: str) -> Any:
        value = value.strip()
        if not value:
            return {}
        if (value.startswith('"') and value.endswith('"')) or (
            value.startswith("'") and value.endswith("'")
        ):
            return value[1:-1]
        if value.startswith("[") and value.endswith("]"):
            inner = value[1:-1].strip()
            if not inner:
                return []
            return [parse_scalar(item.strip()) for item in inner.split(",")]
        if value in {"[]", "{}"}:
            return [] if value == "[]" else {}
        lowered = value.lower()
        if lowered in {"true", "false"}:
            return lowered == "true"
        if lowered in {"null", "none", "~"}:
            return None
        if re.fullmatch(r"-?\d+", value):
            try:
                return int(value)
            except ValueError:
                return value
        if re.fullmatch(r"-?\d+\.\d+", value):
            try:
                return float(value)
            except ValueError:
                return value
        return value

    def block_scalar_style(value: str) -> str:
        match = re.fullmatch(r"([>|])[-+]?", value.strip())
        return match.group(1) if match else ""

    def collect_block_scalar(index: int, parent_indent: int, style: str) -> tuple[str, int]:
        block_lines: list[str] = []
        while index < len(lines):
            line = lines[index]
            if line.strip() and indent_of(line) <= parent_indent:
                break
            block_lines.append(line)
            index += 1

        nonblank_indents = [indent_of(line) for line in block_lines if line.strip()]
        if not nonblank_indents:
            return "", index
        content_indent = min(nonblank_indents)
        normalized = [
            line[content_indent:] if line.strip() else ""
            for line in block_lines
        ]
        if style == "|":
            return "\n".join(normalized).rstrip("\n"), index

        paragraphs: list[str] = []
        current: list[str] = []
        for line in normalized:
            if line == "":
                if current:
                    paragraphs.append(" ".join(current))
                    current = []
                paragraphs.append("")
            else:
                current.append(line.strip())
        if current:
            paragraphs.append(" ".join(current))
        return "\n".join(paragraphs).strip(), index

    def parse_key_value(fragment: str) -> tuple[str, str]:
        key, value = fragment.split(":", 1)
        return key.strip().strip('"').strip("'"), value.strip()

    def parse_block(index: int, indent: int) -> tuple[Any, int]:
        index = skip_ignored(index)
        if index >= len(lines):
            return {}, index
        if indent_of(lines[index]) < indent:
            return {}, index
        if lines[index].strip().startswith("- "):
            return parse_list(index, indent)
        return parse_mapping(index, indent)

    def parse_mapping(index: int, indent: int) -> tuple[dict[str, Any], int]:
        result: dict[str, Any] = {}
        while index < len(lines):
            index = skip_ignored(index)
            if index >= len(lines):
                break
            line = lines[index]
            current_indent = indent_of(line)
            if current_indent < indent:
                break
            if current_indent > indent:
                break
            stripped = line.strip()
            if stripped.startswith("- ") or ":" not in stripped:
                break
            key, raw_value = parse_key_value(stripped)
            index += 1
            style = block_scalar_style(raw_value)
            if style:
                value, index = collect_block_scalar(index, current_indent, style)
            else:
                value = parse_scalar(raw_value)
                next_index = skip_ignored(index)
                if (
                    value == {}
                    and next_index < len(lines)
                    and indent_of(lines[next_index]) > current_indent
                ):
                    value, index = parse_block(next_index, indent_of(lines[next_index]))
            result[key] = value
        return result, index

    def parse_list(index: int, indent: int) -> tuple[list[Any], int]:
        result: list[Any] = []
        while index < len(lines):
            index = skip_ignored(index)
            if index >= len(lines):
                break
            line = lines[index]
            current_indent = indent_of(line)
            if current_indent < indent:
                break
            if current_indent != indent or not line.strip().startswith("- "):
                break
            item_text = line.strip()[2:].strip()
            index += 1
            if not item_text:
                item: Any = {}
            elif ":" in item_text:
                key, raw_value = parse_key_value(item_text)
                style = block_scalar_style(raw_value)
                if style:
                    value, index = collect_block_scalar(index, current_indent, style)
                else:
                    value = parse_scalar(raw_value)
                item = {key: value}
            else:
                item = parse_scalar(item_text)

            next_index = skip_ignored(index)
            if next_index < len(lines) and indent_of(lines[next_index]) > current_indent:
                child, index = parse_block(next_index, indent_of(lines[next_index]))
                if isinstance(item, dict) and isinstance(child, dict):
                    item.update(child)
                elif item in ({}, []):
                    item = child
            result.append(item)
        return result, index

    parsed, _ = parse_block(0, 0)
    return parsed if isinstance(parsed, dict) else {}


def _set_if_missing(target: dict[str, Any], key: str, value: Any) -> None:
    if key not in target and value not in (None, {}, [], ""):
        target[key] = deepcopy(value)


def _component_libraries(technology: dict[str, Any]) -> Any:
    return (
        technology.get("componentLibraries")
        or technology.get("component_libraries")
        or technology.get("libraries")
    )


def _confidence_from_evidence(evidence: dict[str, Any]) -> Any:
    confidence = evidence.get("confidence")
    if isinstance(confidence, dict):
        return confidence
    if confidence:
        return {"overall": confidence}
    return {}


def normalize_design_data(data: dict[str, Any] | None) -> dict[str, Any]:
    """返回统一 front matter 的旧版兼容投影。

    原始字典不会被修改。对于非统一 schema 文档，这基本等同于深拷贝，
    用于保持现有行为。
    """
    if not isinstance(data, dict):
        return {}

    out = deepcopy(data)
    if not is_unified_schema(out):
        return out

    product = mapping(out, "product")
    technology = mapping(out, "technology")
    tokens = mapping(out, "tokens")
    layout = mapping(out, "layout")
    generation_rules = mapping(out, "generationRules")
    evidence = mapping(out, "evidence")

    _set_if_missing(out, "description", out.get("summary"))
    _set_if_missing(out, "productType", product.get("type"))
    _set_if_missing(out, "interfaceArchetype", product.get("archetype"))
    _set_if_missing(out, "density", product.get("density"))
    _set_if_missing(out, "framework", technology.get("framework"))
    _set_if_missing(out, "componentLibraries", _component_libraries(technology))

    _set_if_missing(out, "colors", tokens.get("colors"))
    _set_if_missing(out, "typography", tokens.get("typography"))
    _set_if_missing(out, "spacing", tokens.get("spacing"))
    _set_if_missing(out, "rounded", tokens.get("radius") or tokens.get("rounded"))
    _set_if_missing(out, "shadows", tokens.get("shadow") or tokens.get("shadows"))
    _set_if_missing(out, "motion", tokens.get("motion"))

    _set_if_missing(out, "layoutRules", layout)
    _set_if_missing(out, "componentRecipes", out.get("components"))
    _set_if_missing(out, "aiGenerationRules", generation_rules)
    _set_if_missing(out, "forbiddenRules", generation_rules.get("mustNot"))
    _set_if_missing(out, "selfCheck", generation_rules.get("selfCheck"))
    _set_if_missing(out, "unresolvedItems", out.get("openQuestions"))
    _set_if_missing(out, "confidence", _confidence_from_evidence(evidence))

    if "pagePatterns" not in out and isinstance(out.get("pageTemplates"), list):
        patterns: dict[str, Any] = {}
        for index, template in enumerate(out["pageTemplates"]):
            if not isinstance(template, dict):
                continue
            key = str(template.get("id") or template.get("name") or f"template-{index + 1}")
            patterns[key] = {
                "ref": template.get("name") or key,
                "structure": template.get("structure") or template.get("sections") or [],
                "evidence": template.get("evidence", ""),
            }
        if patterns:
            out["pagePatterns"] = patterns

    return out
