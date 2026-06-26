#!/usr/bin/env python3
"""
将抓取到的 URL theme-data 目录汇总为候选设计证据。

这个脚本刻意不生成 DESIGN.md。它只把 theme.json、meta.json 和截图清单
转换成紧凑证据包，供 Agent 编写权威 DESIGN.md 时参考。
"""

from __future__ import annotations

import argparse
import json
import re
import sys
from collections import defaultdict
from datetime import datetime, timezone
from pathlib import Path
from typing import Any, Dict, Iterable, List, Mapping, MutableMapping, Optional, Tuple


COLOR_RE = re.compile(
    r"^(#(?:[0-9a-fA-F]{3,4}|[0-9a-fA-F]{6}|[0-9a-fA-F]{8})|"
    r"rgba?\([^)]+\)|hsla?\([^)]+\)|"
    r"(?:transparent|currentColor|inherit))$"
)
RGB_RE = re.compile(
    r"rgba?\(\s*([0-9.]+)\s*,\s*([0-9.]+)\s*,\s*([0-9.]+)"
    r"(?:\s*,\s*([0-9.]+))?\s*\)",
    re.IGNORECASE,
)

COLOR_ROLE_PATTERNS = (
    ("primary", re.compile(r"(primary|brand|main|theme)", re.IGNORECASE)),
    ("accent", re.compile(r"(accent|highlight|link)", re.IGNORECASE)),
    ("success", re.compile(r"(success|positive|ok)", re.IGNORECASE)),
    ("warning", re.compile(r"(warning|warn|alert)", re.IGNORECASE)),
    ("danger", re.compile(r"(danger|destructive|error|fail|negative)", re.IGNORECASE)),
    ("text", re.compile(r"(text|foreground|fg|font)", re.IGNORECASE)),
    ("background", re.compile(r"(background|bg|canvas|page)", re.IGNORECASE)),
    ("surface", re.compile(r"(surface|panel|card|container)", re.IGNORECASE)),
    ("border", re.compile(r"(border|line|stroke|divider)", re.IGNORECASE)),
    ("muted", re.compile(r"(muted|subtle|secondary|placeholder|disabled)", re.IGNORECASE)),
)


def load_json(path: Path) -> Dict[str, Any]:
    try:
        return json.loads(path.read_text(encoding="utf-8"))
    except FileNotFoundError:
        raise SystemExit(f"缺少必需文件：{path}") from None
    except json.JSONDecodeError as exc:
        raise SystemExit(f"{path} 中的 JSON 无效：{exc}") from None


def normalize_color(value: Any) -> Optional[str]:
    if not isinstance(value, str):
        return None
    raw = value.strip()
    if not raw:
        return None
    lower = raw.lower()
    if lower.startswith("#"):
        hex_value = lower
        if len(hex_value) == 4:
            return "#" + "".join(ch * 2 for ch in hex_value[1:])
        if len(hex_value) == 5:
            return "#" + "".join(ch * 2 for ch in hex_value[1:])
        return hex_value
    match = RGB_RE.match(raw)
    if match:
        r, g, b = (int(float(match.group(index))) for index in (1, 2, 3))
        alpha = match.group(4)
        if alpha is not None and float(alpha) < 1:
            return f"rgba({r}, {g}, {b}, {alpha})"
        return "#{:02x}{:02x}{:02x}".format(r, g, b)
    if COLOR_RE.match(raw):
        return raw
    return None


def looks_like_color(value: Any) -> bool:
    return normalize_color(value) is not None


def as_items(value: Any) -> List[Dict[str, Any]]:
    if isinstance(value, list):
        items = value
    elif isinstance(value, dict):
        items = []
        for key, item in value.items():
            if isinstance(item, dict):
                merged = dict(item)
                merged.setdefault("name", key)
                items.append(merged)
            else:
                items.append({"name": key, "value": item})
    else:
        return []

    normalized = []
    for item in items:
        if isinstance(item, dict):
            normalized.append(dict(item))
        else:
            normalized.append({"value": item})
    return normalized


def count_of(item: Mapping[str, Any]) -> float:
    for key in ("count", "occurrences", "frequency", "usageCount"):
        value = item.get(key)
        if isinstance(value, (int, float)):
            return float(value)
        if isinstance(value, str):
            try:
                return float(value)
            except ValueError:
                pass
    return 1.0


def tags_of(item: Mapping[str, Any]) -> List[str]:
    raw = item.get("tags") or item.get("selectors") or item.get("sources") or []
    if isinstance(raw, str):
        return [raw]
    if isinstance(raw, list):
        return [str(value) for value in raw[:12]]
    return []


def compact_candidate(
    item: Mapping[str, Any],
    source: str,
    index: int,
    *,
    value_key: str = "value",
) -> Optional[Dict[str, Any]]:
    value = item.get(value_key)
    if value is None:
        return None
    candidate: Dict[str, Any] = {
        "value": str(value),
        "count": count_of(item),
        "source": source,
        "sourceIndex": index,
    }
    normalized_color = normalize_color(value)
    if normalized_color:
        candidate["normalizedValue"] = normalized_color
    name = item.get("name")
    if name:
        candidate["name"] = str(name)
    tags = tags_of(item)
    if tags:
        candidate["tags"] = tags
    return candidate


def merge_candidates(candidates: Iterable[Dict[str, Any]], limit: int) -> List[Dict[str, Any]]:
    grouped: MutableMapping[str, Dict[str, Any]] = {}
    for candidate in candidates:
        key = str(candidate.get("normalizedValue") or candidate.get("value"))
        if not key:
            continue
        current = grouped.setdefault(
            key,
            {
                "value": key,
                "count": 0.0,
                "sources": [],
                "tags": [],
            },
        )
        current["count"] = float(current["count"]) + float(candidate.get("count", 1))
        source_label = f"{candidate.get('source')}[{candidate.get('sourceIndex')}]"
        if source_label not in current["sources"]:
            current["sources"].append(source_label)
        for tag in candidate.get("tags", []):
            if tag not in current["tags"]:
                current["tags"].append(tag)
    ranked = sorted(grouped.values(), key=lambda item: (-float(item["count"]), str(item["value"])))
    for item in ranked:
        item["count"] = int(item["count"]) if float(item["count"]).is_integer() else item["count"]
        item["sources"] = item["sources"][:8]
        item["tags"] = item["tags"][:12]
        if not item["tags"]:
            item.pop("tags")
    return ranked[:limit]


def color_group(theme: Mapping[str, Any], name: str, limit: int) -> List[Dict[str, Any]]:
    colors = theme.get("colors") if isinstance(theme.get("colors"), dict) else {}
    candidates = []
    for index, item in enumerate(as_items(colors.get(name))):
        candidate = compact_candidate(item, f"theme.colors.{name}", index)
        if candidate and looks_like_color(candidate.get("value")):
            candidates.append(candidate)
    return merge_candidates(candidates, limit)


def value_group(theme: Mapping[str, Any], path: Tuple[str, ...], limit: int) -> List[Dict[str, Any]]:
    node: Any = theme
    for part in path:
        if not isinstance(node, dict):
            return []
        node = node.get(part)
    candidates = []
    for index, item in enumerate(as_items(node)):
        candidate = compact_candidate(item, ".".join(path), index)
        if candidate:
            candidates.append(candidate)
    return merge_candidates(candidates, limit)


def css_variables(theme: Mapping[str, Any], limit: int) -> Dict[str, Any]:
    raw = theme.get("cssVariables") or theme.get("css_variables") or {}
    if not isinstance(raw, dict):
        return {"all": [], "colorLike": []}

    all_vars = []
    color_like = []
    for name, value in sorted(raw.items()):
        role_hint = infer_role(str(name))
        entry = {"name": str(name), "value": str(value)}
        if role_hint:
            entry["roleHint"] = role_hint
        all_vars.append(entry)
        normalized = normalize_color(value)
        if normalized:
            color_entry = dict(entry)
            color_entry["normalizedValue"] = normalized
            color_like.append(color_entry)
    return {
        "all": all_vars[:limit],
        "colorLike": color_like[:limit],
        "total": len(all_vars),
        "colorLikeTotal": len(color_like),
    }


def infer_role(name: str) -> Optional[str]:
    for role, pattern in COLOR_ROLE_PATTERNS:
        if pattern.search(name):
            return role
    return None


def semantic_color_hints(
    colors: Mapping[str, List[Dict[str, Any]]],
    css_vars: Mapping[str, Any],
    limit: int,
) -> Dict[str, List[Dict[str, Any]]]:
    hints: Dict[str, List[Dict[str, Any]]] = defaultdict(list)

    for variable in css_vars.get("colorLike", []):
        role = variable.get("roleHint")
        if not role:
            continue
        hints[role].append(
            {
                "value": variable.get("normalizedValue") or variable.get("value"),
                "source": f"cssVariables.{variable.get('name')}",
                "confidence": "medium",
                "reason": "CSS 变量名携带语义角色提示；提升为正式 token 前需结合运行态使用确认。",
            }
        )

    fallback_map = {
        "background": ("background", 0, "提取频率最高的背景色。"),
        "text": ("text", 0, "提取频率最高的文字色。"),
        "muted": ("text", 1, "第二个文字色可能是次级文字或链接，需要确认使用场景。"),
        "border": ("border", 0, "提取频率最高的边框色。"),
        "surface": ("background", 1, "第二个背景色可能是面板或卡片表面。"),
    }
    for role, (group, index, reason) in fallback_map.items():
        group_values = colors.get(group) or []
        if len(group_values) > index:
            value = group_values[index]["value"]
            if not any(existing.get("value") == value for existing in hints[role]):
                hints[role].append(
                    {
                        "value": value,
                        "source": f"theme.colors.{group}[{index}]",
                        "confidence": "low",
                        "reason": reason,
                    }
                )

    return {role: values[:limit] for role, values in sorted(hints.items())}


def typography(theme: Mapping[str, Any], limit: int) -> Dict[str, Any]:
    raw = theme.get("typography") if isinstance(theme.get("typography"), dict) else {}
    families = value_group({"typography": raw}, ("typography", "families"), limit)
    styles = []
    for index, item in enumerate(as_items(raw.get("textStyles"))):
        style = {
            "source": f"theme.typography.textStyles[{index}]",
            "count": count_of(item),
        }
        for key in ("size", "lineHeight", "weight", "family", "letterSpacing"):
            if key in item:
                style[key] = item[key]
        styles.append(style)
    styles.sort(key=lambda item: (-float(item["count"]), str(item.get("size", ""))))
    return {"families": families, "textStyles": styles[:limit]}


def screenshot_inventory(input_dir: Path) -> Dict[str, Any]:
    inventory: Dict[str, Any] = {
        "fullPage": None,
        "responsive": [],
        "sections": [],
    }
    full_page = input_dir / "screenshot.png"
    if full_page.exists():
        inventory["fullPage"] = str(full_page)
    responsive = input_dir / "responsive"
    if responsive.exists():
        inventory["responsive"] = [str(path) for path in sorted(responsive.glob("*.png"))]
    sections = input_dir / "sections"
    if sections.exists():
        for path in sorted(sections.glob("*/screenshot.png")):
            inventory["sections"].append({"name": path.parent.name, "path": str(path)})
    inventory["counts"] = {
        "fullPage": 1 if inventory["fullPage"] else 0,
        "responsive": len(inventory["responsive"]),
        "sections": len(inventory["sections"]),
    }
    return inventory


def build_summary(input_dir: Path, *, max_values: int, url: Optional[str]) -> Dict[str, Any]:
    theme_path = input_dir / "theme.json"
    theme = load_json(theme_path)
    meta_path = input_dir / "meta.json"
    meta = load_json(meta_path) if meta_path.exists() else {}
    if url:
        meta["url"] = url

    colors = {
        "background": color_group(theme, "background", max_values),
        "text": color_group(theme, "text", max_values),
        "border": color_group(theme, "border", max_values),
        "fill": color_group(theme, "fill", max_values),
        "stroke": color_group(theme, "stroke", max_values),
    }
    colors = {key: value for key, value in colors.items() if value}
    css_vars = css_variables(theme, max_values * 2)

    return {
        "schema": "design-generator-url-theme-evidence-v1",
        "generatedAt": datetime.now(timezone.utc).isoformat(),
        "generatedBy": "scripts/extract_url_theme_evidence.py",
        "inputDir": str(input_dir),
        "sourceFiles": {
            "themeJson": str(theme_path),
            "metaJson": str(meta_path) if meta_path.exists() else None,
        },
        "recommendedUse": {
            "role": "candidate-token-frequency",
            "rule": (
                "仅把这些数据作为候选证据。写入 DESIGN.md 前，必须用 runtime computed styles、"
                "active source styles、截图或明确决策确认最终 tokens。"
            ),
            "doNot": "不要在未确认的情况下把 semanticColorHints 直接复制进 tokens。",
        },
        "meta": meta,
        "candidateEvidence": {
            "cssVariables": css_vars,
            "colors": colors,
            "semanticColorHints": semantic_color_hints(colors, css_vars, max_values),
            "typography": typography(theme, max_values),
            "spacing": value_group(theme, ("spacing",), max_values),
            "radius": value_group(theme, ("radius",), max_values),
            "shadow": {
                "box": value_group(theme, ("shadow", "box"), max_values),
                "text": value_group(theme, ("shadow", "text"), max_values),
            },
            "lineWidth": value_group(theme, ("lineWidth",), max_values),
            "motion": {
                "transitions": value_group(theme, ("transitions",), max_values),
                "animations": value_group(theme, ("animations",), max_values),
            },
        },
        "screenshotInventory": screenshot_inventory(input_dir),
        "frontMatterPlacement": {
            "runtime.runtimeSources.themeData.path": str(theme_path),
            "evidence.sources.themeData.role": "candidate-token-frequency",
            "evidence.sources.themeData.summaryPath": "可选；除非保留调试证据，否则省略",
        },
    }


def parse_args(argv: List[str]) -> argparse.Namespace:
    parser = argparse.ArgumentParser(
        description="将 URL theme-data 目录汇总为 design-generator 的候选证据。"
    )
    parser.add_argument("input_dir", help="包含 theme.json 以及可选 meta.json/screenshots 的目录。")
    parser.add_argument("-o", "--output", help="将 JSON 摘要写入该路径，而不是输出到 stdout。")
    parser.add_argument("--url", help="覆盖或补充输出元数据中的抓取 URL。")
    parser.add_argument(
        "--max-values",
        type=int,
        default=16,
        help="每个分类保留的最大排序值数量（默认：16）。",
    )
    return parser.parse_args(argv)


def main(argv: List[str]) -> int:
    args = parse_args(argv)
    input_dir = Path(args.input_dir).expanduser().resolve()
    if not input_dir.exists() or not input_dir.is_dir():
        print(f"输入目录不存在：{input_dir}", file=sys.stderr)
        return 1
    summary = build_summary(input_dir, max_values=max(1, args.max_values), url=args.url)
    output = json.dumps(summary, ensure_ascii=False, indent=2)
    if args.output:
        output_path = Path(args.output).expanduser().resolve()
        output_path.parent.mkdir(parents=True, exist_ok=True)
        output_path.write_text(output + "\n", encoding="utf-8")
        print(f"已写入 URL 主题证据摘要：{output_path}")
    else:
        print(output)
    return 0


if __name__ == "__main__":
    raise SystemExit(main(sys.argv[1:]))
