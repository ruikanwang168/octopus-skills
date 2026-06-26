#!/usr/bin/env python3
"""
根据 DESIGN.md front matter 生成 DESIGN_GAPS.md。

脚本会从 DESIGN.md front matter 中提取 evidence、conflicts、
unresolvedItems、knownLimits、assumptions 和 confidence，
生成结构化 DESIGN_GAPS.md。

DESIGN_GAPS.md 默认始终生成，不提供开关。
"""

from __future__ import annotations

import argparse
import html
import json
import sys
from datetime import datetime
from pathlib import Path
from typing import Any
import re

from front_matter_schema import (
    normalize_design_data,
    parse_simple_yaml as parse_simple_yaml_fallback,
)


# ── 缺口类型常量 ────────────────────────────────────────────────
GAP_TYPES = {
    "unconfirmed": "未确认",
    "approximate": "估算",
    "conflict": "冲突",
    "inferred": "推断",
    "recommended-default": "推荐默认",
    "legacy": "历史遗留",
    "unsupported": "未覆盖 / 暂不支持",
}

CONFIDENCE_DIMENSIONS = [
    ("overall", "整体"),
    ("tokens", "设计令牌"),
    ("components", "组件体系"),
    ("pageTemplates", "页面模板"),
    ("darkMode", "暗色模式"),
    ("mobile", "移动端"),
]

CONFIRMED_EVIDENCE_TERMS = (
    "user-provided detailed product specification",
    "explicit user brief",
    "explicit-brief",
    "user supplied exact",
    "用户明确",
    "明确提供",
)

PLACEHOLDER_RE = re.compile(r"\bMUST_REPLACE_[A-Z0-9_]+\b")

DEFAULT_UNCOVERED = [
    ("暗色模式", "未确认", "不默认生成暗色主题页面"),
    ("移动端 APP", "未确认", "不默认生成移动端页面"),
    ("数据大屏", "未确认", "不默认生成大屏风格"),
    ("国际化 i18n", "未确认", "不默认生成多语言切换"),
    ("可访问性规范", "证据不足", "仅按常规 focus / disabled 处理"),
    ("图表色板", "未完整观察", "不主动扩展图表色板"),
]


def collect_text(value: Any) -> str:
    if isinstance(value, dict):
        return " ".join(
            part for key, child in value.items() for part in (str(key), collect_text(child)) if part
        )
    if isinstance(value, list):
        return " ".join(collect_text(item) for item in value)
    if value is None:
        return ""
    return str(value)


def is_placeholder_value(value: Any) -> bool:
    """判断是否为未替换的脚手架占位符；这类值不应转成 gaps。"""
    return bool(PLACEHOLDER_RE.search(collect_text(value)))


def is_single_dark_theme(front_matter: dict[str, Any]) -> bool:
    blob = " ".join(
        [
            collect_text(front_matter.get("runtime", {})),
            collect_text(front_matter.get("knownLimits", {})),
            str(front_matter.get("description", "")),
        ]
    ).lower()
    return any(
        term in blob
        for term in (
            "dark-only",
            "dark only",
            "dark theme",
            "dark-themed",
            "dark-portfolio",
            "暗色唯一",
            "仅有暗色",
            "暗色单主题",
        )
    )


def should_skip_default_uncovered(front_matter: dict[str, Any], category: str) -> bool:
    confidence = front_matter.get("confidence", {})
    confidence_map = confidence if isinstance(confidence, dict) else {}
    normalized = category.lower()
    if "暗色" in category and (
        is_single_dark_theme(front_matter)
        or str(confidence_map.get("darkMode", "")).lower() in {"high", "medium"}
    ):
        return True
    if "移动端 app" in normalized or "移动端" in category:
        if str(confidence_map.get("mobile", "")).lower() in {"high", "medium"}:
            return True
    return False


def parse_yaml_front_matter(content: str) -> dict[str, Any] | None:
    if not content.startswith("---"):
        return None
    # 查找独立成行的 closing ---，不能把注释或正文里的 --- 当成 front matter 结束。
    # 例如 "# --- new v3 fields" 这类 YAML 注释不能被当成分隔符。
    idx = content.find("\n", 3)  # 跳过开头的 "---\n"
    while idx != -1:
        nl = content.find("\n", idx + 1)
        line = content[idx : nl if nl != -1 else len(content)].strip()
        if line == "---":
            body = content[3:idx]
            try:
                import yaml  # type: ignore
            except Exception:
                return normalize_design_data(parse_simple_yaml(body))
            try:
                parsed = yaml.safe_load(body) or {}
                return normalize_design_data(parsed if isinstance(parsed, dict) else {})
            except Exception as e:
                print(f"警告：解析 YAML front matter 失败：{e}", file=sys.stderr)
                return normalize_design_data(parse_simple_yaml(body))
        idx = nl
    return None


def parse_scalar(value: str) -> Any:
    value = value.strip()
    if not value:
        return {}
    if (value.startswith('"') and value.endswith('"')) or (
        value.startswith("'") and value.endswith("'")
    ):
        return value[1:-1]
    return value


def parse_simple_yaml(text: str) -> dict[str, Any]:
    """解析 DESIGN.md 使用的 YAML 子集的兜底解析器。

    行为与 ``render_preview_from_design_md.py`` 和 ``validate_design_folder.py``
    中支持列表的兜底解析保持一致，确保没有安装 PyYAML 时，统一 schema 中的
    ``pageTemplates`` / ``openQuestions`` / ``assumptions`` 等 YAML 列表也能正确往返。
    """
    return parse_simple_yaml_fallback(text)


def slugify(text: str) -> str:
    text = re.sub(r"[\s_]+", "-", str(text or "").strip().lower())
    text = re.sub(r"[^a-z0-9\-]+", "-", text)
    text = re.sub(r"-{2,}", "-", text).strip("-")
    return text or "template"


def guess_archetype(text: str) -> str:
    text = str(text or "").strip().lower()
    if text.startswith("custom:"):
        return text
    if any(term in text for term in ("content-resource-portal", "资源门户", "资源库", "数字资源", "文化内容", "档案", "专题展", "媒体资料库", "资源展示", "素材库")):
        return "content-resource-portal"
    if any(term in text for term in ("brand-portfolio", "作品集", "个人品牌", "creator", "portfolio", "brand-site", "brand site", "personal brand")):
        return "brand-portfolio"
    if any(term in text for term in ("marketing-site", "landing", "pricing", "cta", "营销", "落地页", "官网")):
        return "marketing-site"
    if any(term in text for term in ("mobile-app", "mobile app", "移动端", "tabbar", "ios", "android")):
        return "mobile-app"
    if any(term in text for term in ("data-screen", "大屏", "全屏", "指挥", "告警", "实时状态")):
        return "data-screen"
    if any(term in text for term in ("aigc-workbench", "aigc", "prompt", "提示词", "参数面板", "结果预览", "任务历史", "ai 生成")):
        return "aigc-workbench"
    if any(term in text for term in ("chat-agent", "copilot", "对话", "聊天", "assistant", "客服", "知识问答")):
        return "chat-agent"
    if any(term in text for term in ("docs-portal", "documentation", "开发者中心", "api 文档", "文档站", "docs")):
        return "docs-portal"
    if any(term in text for term in ("settings-admin", "设置中心", "账号", "组织", "权限", "计费", "billing")):
        return "settings-admin"
    if any(term in text for term in ("enterprise-admin", "后台", "管理", "crud", "审批", "配置", "表管理")):
        return "enterprise-admin"
    if any(term in text for term in ("analytics-dashboard", "dashboard", "analytics", "metric", "chart", "仪表盘", "指标", "趋势")):
        return "analytics-dashboard"
    return ""


def page_templates(front_matter: dict[str, Any]) -> list[dict[str, Any]]:
    raw = front_matter.get("pageTemplates")
    items: list[Any]
    if isinstance(raw, list):
        items = raw
    elif isinstance(raw, dict):
        items = list(raw.values())
    else:
        items = []
    templates: list[dict[str, Any]] = []
    for item in items:
        if isinstance(item, dict):
            templates.append(item)
    return templates


def page_template_key(item: dict[str, Any]) -> str:
    key = _first(item.get("key"), item.get("id"))
    if not key:
        key = slugify(_first(item.get("name"), item.get("title")))
    return str(key)


def representative_page_template(front_matter: dict[str, Any]) -> dict[str, Any] | None:
    templates = page_templates(front_matter)
    if not templates:
        return None
    primary = [t for t in templates if str(t.get("priority", "")).strip().lower() == "primary"]
    candidates = primary or templates
    def score(item: dict[str, Any]) -> tuple[int, int]:
        priority = 0 if str(item.get("priority", "")).strip().lower() == "primary" else 1
        sections_value = item.get("sections", item.get("structure"))
        if isinstance(sections_value, list):
            length = len(sections_value)
        elif isinstance(sections_value, str) and sections_value.strip():
            length = 1
        else:
            length = 0
        return (priority, -length)
    candidates = sorted(candidates, key=score)
    return candidates[0] if candidates else None


def read_example_metadata(design_folder: Path) -> dict[str, str]:
    example_path = design_folder / "example.html"
    if not example_path.exists():
        return {}
    raw = example_path.read_text(encoding="utf-8")
    html_tag = re.search(r"<html\b[^>]*>", raw, re.I)
    tag_text = html_tag.group(0) if html_tag else ""
    archetype = ""
    pattern = ""
    pattern_source = ""
    m = re.search(r'data-example-archetype\s*=\s*"([^"]+)"', tag_text, re.I)
    if m:
        archetype = m.group(1).strip()
    m = re.search(r'data-example-pattern\s*=\s*"([^"]+)"', tag_text, re.I)
    if m:
        pattern = m.group(1).strip()
    m = re.search(r'data-example-pattern-source\s*=\s*"([^"]+)"', tag_text, re.I)
    if m:
        pattern_source = m.group(1).strip()
    return {"archetype": archetype, "pattern": pattern, "pattern_source": pattern_source}


def read_example_generation_input(design_folder: Path) -> dict[str, Any]:
    example_path = design_folder / "example.html"
    if not example_path.exists():
        return {}
    raw = example_path.read_text(encoding="utf-8")
    match = re.search(
        r'<script\b(?=[^>]*\bid=["\']example-generation-input["\'])(?=[^>]*\btype=["\']application/json["\'])[^>]*>(.*?)</script>',
        raw,
        re.I | re.S,
    )
    if not match:
        return {}
    try:
        parsed = json.loads(html.unescape(match.group(1)).strip())
    except Exception:
        return {}
    return parsed if isinstance(parsed, dict) else {}


def markdown_body_after_front_matter(content: str) -> str:
    if not content.startswith("---"):
        return content
    match = re.search(r"^---\s*$", content[3:], re.MULTILINE)
    if not match:
        return content
    return content[3 + match.end():]


def high_impact_items_from_body(body: str) -> list[dict[str, Any]]:
    match = re.search(r"^###\s+10\.4\s+.*?(?:高影响|high impact).*?$", body, re.I | re.M)
    if not match:
        return []
    tail = body[match.end():]
    next_heading = re.search(r"^#{1,3}\s+", tail, re.M)
    section = tail[: next_heading.start()] if next_heading else tail
    gaps: list[dict[str, Any]] = []
    for line in section.splitlines():
        stripped = line.strip()
        if not stripped or stripped.startswith("|---") or stripped.startswith("| ID"):
            continue
        question = ""
        current = ""
        impact = ""
        if stripped.startswith("|") and stripped.endswith("|"):
            cells = [cell.strip() for cell in stripped.strip("|").split("|")]
            if len(cells) >= 2:
                question = cells[1]
            if len(cells) >= 3:
                current = cells[2]
            if len(cells) >= 4:
                impact = cells[3]
        else:
            numbered = re.match(r"\d+\.\s+\*\*(.+?)\*\*[:：]\s*(.+)", stripped)
            if numbered:
                question = numbered.group(1)
                current = numbered.group(2)
        if not question:
            continue
        gaps.append(
            {
                "id": f"HIGH-{len(gaps) + 1:03d}",
                "type": "unconfirmed",
                "priority": "high",
                "question": question,
                "current_judgment": current,
                "evidence_source": "DESIGN.md 第 10.4 节",
                "confidence": "",
                "impact_scope": impact or "影响页面生成准确性",
                "current_handling": "按 DESIGN.md 当前默认规则处理；确认后回写权威规则",
                "needs_confirmation": "是",
                "writeback_location": "DESIGN.md 第 10.4 节 / front matter",
            }
        )
    return gaps


def normalize_gap(gap: Any, default_type: str = "unconfirmed") -> dict[str, Any]:
    """把 gap 条目规范化为包含预期键的字典。

    统一 schema 在 openQuestions 中使用 ``id / question / currentDecision /
    fallbackRule / impact``。早期草稿使用 ``currentJudgment``、
    ``needsConfirmation`` 等名称；这里同时兼容。输入没有显式值时，
    ``needs_confirmation`` 会刻意留空，由 ``_complete_gap_defaults`` 统一补成 ``"是"``。
    """
    if isinstance(gap, str):
        return {
            "id": "",
            "type": default_type,
            "priority": "medium",
            "question": gap,
            "current_judgment": "",
            "evidence_source": "",
            "confidence": "",
            "impact_scope": "",
            "current_handling": "",
            "needs_confirmation": "",
            "writeback_location": "",
        }
    if isinstance(gap, dict):
        gap_id = gap.get("id") or gap.get("ID") or gap.get("Id") or ""
        # current_judgment：优先读取统一 schema 的 `currentDecision` /
        # `fallbackRule`，再回退到历史别名。
        current_judgment = (
            gap.get("current_judgment")
            or gap.get("currentJudgment")
            or gap.get("currentDecision")
            or gap.get("current_decision")
            or gap.get("fallbackRule")
            or gap.get("fallback_rule")
            or gap.get("current_value")
            or gap.get("current")
            or ""
        )
        return {
            "id": str(gap_id).strip(),
            "type": gap.get("type", default_type),
            "priority": gap.get("priority", "medium"),
            "question": gap.get("question", gap.get("description", gap.get("item", ""))),
            "current_judgment": current_judgment,
            "evidence_source": gap.get("evidence_source", gap.get("evidenceSource", gap.get("source", ""))),
            "confidence": gap.get("confidence", ""),
            "impact_scope": gap.get("impact_scope", gap.get("impactScope", gap.get("impact", ""))),
            "current_handling": gap.get("current_handling", gap.get("currentHandling", gap.get("handling", ""))),
            "needs_confirmation": gap.get("needs_confirmation", gap.get("needsConfirmation", "")),
            "writeback_location": gap.get("writeback_location", gap.get("writebackLocation", "")),
        }
    return normalize_gap(str(gap), default_type)


def iter_items(value: Any):
    """统一遍历 list / dict / None，产出 (key, item)。

    - list：每个元素产出 (index_str, item)
    - dict：每个键产出 (key, item)
    - None / 其它：不产出
    """
    if isinstance(value, list):
        for idx, item in enumerate(value):
            yield str(idx), item
    elif isinstance(value, dict):
        for key, item in value.items():
            yield str(key), item


def _fallback_id_from_key(prefix: str, key: Any) -> str:
    """当 YAML 条目没有显式 id 时，生成稳定兜底 ID。

    dict key 通常有含义（例如 ``openQuestions.dark-mode``），应原样复用。
    数字列表索引会转换成 ``<prefix>-<NNN>``，避免跨 section 冲突。
    """
    text = str(key) if key is not None else ""
    if text.isdigit():
        return f"{prefix}-{int(text) + 1:03d}"
    return text or f"{prefix}-?"


def _first(*values: Any) -> str:
    """返回第一个非空字符串化值。"""
    for v in values:
        if v is None:
            continue
        s = str(v).strip()
        if s:
            return s
    return ""


def _candidates_to_text(value: Any) -> str:
    if isinstance(value, list):
        return " / ".join(str(v) for v in value if str(v).strip())
    if isinstance(value, dict):
        return " / ".join(f"{k}={v}" for k, v in value.items())
    return str(value) if value is not None else ""


def _gap_key(gap: dict[str, Any]) -> str:
    text = _first(
        gap.get("id"),
        gap.get("question"),
        gap.get("current_judgment"),
        gap.get("impact_scope"),
    ).lower()
    text = text.replace(" ", "")
    text = text.replace("（", "(").replace("）", ")")
    return text


def _complete_gap_defaults(gap: dict[str, Any], evidence_source: str = "") -> dict[str, Any]:
    if evidence_source and not gap.get("evidence_source"):
        gap["evidence_source"] = evidence_source
    if not gap.get("current_handling"):
        gap["current_handling"] = "按 DESIGN.md 当前默认规则处理；确认后回写权威规则"
    if not gap.get("impact_scope"):
        gap["impact_scope"] = "影响局部原型生成准确性"
    if not gap.get("needs_confirmation"):
        gap["needs_confirmation"] = "是"
    return gap


def infer_gap_priority(gap: dict[str, Any]) -> str:
    explicit = str(gap.get("priority", "")).strip().lower()
    if explicit in {"high", "medium", "low"}:
        return explicit
    text = collect_text(gap).lower()
    high_terms = (
        "high impact",
        "高影响",
        "页面尾部",
        "导航锚点",
        "contactsection",
        "footer",
        "price/contact",
        "主视觉",
        "机构 logo",
        "专题海报",
        "背景纹样",
        "首页",
        "移动端布局",
        "暗色模式支持",
    )
    if any(term in text for term in high_terms):
        return "high"
    return explicit or "medium"


def _dedupe_gap_list(gaps: list[dict[str, Any]]) -> list[dict[str, Any]]:
    seen: set[str] = set()
    deduped: list[dict[str, Any]] = []
    for gap in gaps:
        key = _gap_key(gap)
        if key and key in seen:
            continue
        if key:
            seen.add(key)
        deduped.append(gap)
    return deduped


_CONFLICT_KEYWORDS = (
    "主题",
    "主色",
    "顶栏",
    "顶部",
    "标签页",
    "页签",
    "背景",
    "内容区",
    "侧栏",
    "折叠",
    "暗色",
    "移动端",
    "图表",
    "theme",
    "primary",
    "topbar",
    "header",
    "tags",
    "tabs",
    "background",
    "sidebar",
    "collapse",
    "dark",
    "mobile",
    "chart",
)


def _conflict_blob(item: dict[str, Any] | str) -> str:
    if isinstance(item, str):
        return item
    return " ".join(
        str(item.get(key, ""))
        for key in ("description", "candidates", "adopted", "reason")
    )


def _conflict_fingerprint(item: dict[str, Any] | str) -> dict[str, set[str]]:
    text = _conflict_blob(item).lower()
    return {
        "hex": set(re.findall(r"#[0-9a-f]{3,8}", text)),
        "vars": set(re.findall(r"\$[a-z_][a-z0-9_-]*", text)),
        "dims": set(re.findall(r"\b\d+(?:\.\d+)?px\b", text)),
        "keywords": {keyword for keyword in _CONFLICT_KEYWORDS if keyword in text},
    }


def _conflicts_overlap(left: dict[str, Any] | str, right: dict[str, Any] | str) -> bool:
    lhs = _conflict_fingerprint(left)
    rhs = _conflict_fingerprint(right)
    if lhs["vars"] & rhs["vars"]:
        return True
    if lhs["hex"] & rhs["hex"] and lhs["keywords"] & rhs["keywords"]:
        return True
    if lhs["dims"] & rhs["dims"] and lhs["keywords"] & rhs["keywords"]:
        return True
    shared_keywords = lhs["keywords"] & rhs["keywords"]
    return len(shared_keywords) >= 2


def _dedupe_conflicts(conflicts: list[dict[str, Any]]) -> list[dict[str, Any]]:
    deduped: list[dict[str, Any]] = []
    seen_descriptions: set[str] = set()
    for conflict in conflicts:
        description = conflict.get("description", "").strip()
        compact = re.sub(r"\s+", "", description.lower())
        if compact and compact in seen_descriptions:
            continue
        if any(_conflicts_overlap(conflict, existing) for existing in deduped):
            continue
        if compact:
            seen_descriptions.add(compact)
        deduped.append(conflict)
    return deduped


def extract_gaps(front_matter: dict[str, Any]) -> dict[str, Any]:
    """从 front matter 中提取所有 gap 数据并分类。

    每个字段都兼容 list-of-dict 和 dict-of-dict 形态
    （conflicts、assumptions、unresolvedItems、knownLimits.*），
    避免真实 DESIGN.md 写法稍有差异时静默丢数据。
    """
    result: dict[str, Any] = {
        "evidence_mode": "",
        "confidence_overall": "",
        "confidence_details": {},
        "evidence_summary": "",
        "default_decisions": [],
        "high_priority": [],
        "medium_priority": [],
        "low_priority": [],
        "conflicts": [],
        "uncovered": [],
        "confirmation_records": [],
    }

    # ── 证据 ──
    evidence = front_matter.get("evidence", {})
    if isinstance(evidence, dict):
        result["evidence_mode"] = str(evidence.get("mode", ""))
        confidence_raw = evidence.get("confidence", "")
        if isinstance(confidence_raw, dict):
            # evidence.confidence 是统一 schema 的 {overall, tokens, ...} 映射。
            # 页头只展示一个可读值；详细项由下方顶层 "confidence" 进入 §1 表格。
            result["confidence_overall"] = str(confidence_raw.get("overall", "")).strip()
            for dim_key, dim_label in CONFIDENCE_DIMENSIONS:
                if dim_key in confidence_raw and not result["confidence_details"].get(dim_label):
                    result["confidence_details"][dim_label] = str(confidence_raw[dim_key])
        else:
            result["confidence_overall"] = str(confidence_raw).strip()

        # inferredFrom 记录 brief 模式合成的推理基础。
        # 普通证据说明不是 unresolved question；只有带 question/confirmation
        # 字段的结构化项才会成为可执行 gap。
        sources = evidence.get("sources", {})
        if isinstance(sources, dict):
            for item in sources.get("inferredFrom", []) or []:
                if not isinstance(item, dict):
                    continue
                if not any(
                    key in item
                    for key in (
                        "question",
                        "description",
                        "needs_confirmation",
                        "needsConfirmation",
                        "impact",
                        "impact_scope",
                        "impactScope",
                    )
                ):
                    continue
                if any(term in collect_text(item).lower() for term in CONFIRMED_EVIDENCE_TERMS):
                    continue
                gap = normalize_gap(item, "inferred")
                gap["priority"] = "medium"
                gap["evidence_source"] = gap["evidence_source"] or "evidence.sources.inferredFrom"
                result["medium_priority"].append(gap)

    # ── unresolvedItems：按优先级分发（支持 list/dict/str） ──
    unresolved = front_matter.get("unresolvedItems")
    for key, item in iter_items(unresolved):
        gap = normalize_gap(item, "unconfirmed")
        if is_placeholder_value(gap.get("question")):
            continue
        if not gap.get("id"):
            gap["id"] = _fallback_id_from_key("OQ", key)
        _complete_gap_defaults(gap, "unresolvedItems")
        priority = infer_gap_priority(gap)
        gap["priority"] = priority
        if priority == "high":
            result["high_priority"].append(gap)
        elif priority == "low":
            result["low_priority"].append(gap)
        else:
            result["medium_priority"].append(gap)

    # ── conflicts：进入冲突清单（支持 list/dict/str） ──
    conflicts = front_matter.get("conflicts")
    for key, item in iter_items(conflicts):
        if isinstance(item, dict):
            desc = _first(
                item.get("item"),
                item.get("description"),
                item.get("question"),
                key,
            )
            entry = {
                "id": item.get("id") or str(key),
                "description": desc,
                "candidates": _candidates_to_text(
                    item.get("candidates", item.get("candidateValues", ""))
                ),
                "adopted": _first(item.get("adopted"), item.get("currentValue"), item.get("resolvedTo"), item.get("decision")),
                "reason": _first(item.get("reason"), item.get("rationale"), "DESIGN.md 已记录当前采用值；如证据变化需回写更新。"),
                "needs_confirmation": str(item.get("needsConfirmation", "是")),
            }
            result["conflicts"].append(entry)
        elif isinstance(item, str) and item.strip():
            result["conflicts"].append({
                "id": str(key),
                "description": item,
                "candidates": "",
                "adopted": "",
                "reason": "",
                "needs_confirmation": "是",
            })

    # evidence.knownConflicts 作为补充来源，按描述去重
    evidence_conflicts = []
    if isinstance(evidence, dict):
        evidence_conflicts = evidence.get("knownConflicts", []) or []
    existing_desc = {c.get("description", "").strip() for c in result["conflicts"]}
    for i, item in enumerate(evidence_conflicts):
        desc = item if isinstance(item, str) else str(item)
        candidate_entry = {
            "id": f"CONFLICT-{len(result['conflicts']) + 1:03d}",
            "description": desc,
            "candidates": "",
            "adopted": "",
            "reason": "",
            "needs_confirmation": "是",
        }
        if (
            not desc.strip()
            or desc.strip() in existing_desc
            or any(_conflicts_overlap(candidate_entry, existing) for existing in result["conflicts"])
        ):
            continue
        result["conflicts"].append(candidate_entry)
        existing_desc.add(desc.strip())
    result["conflicts"] = _dedupe_conflicts(result["conflicts"])

    # ── evidence.decisions：进入默认决策 / 中优先级 gaps ──
    if isinstance(evidence, dict):
        for index, decision in enumerate(evidence.get("decisions", []) or []):
            if not isinstance(decision, dict):
                continue
            source = str(decision.get("source", "")).strip().lower()
            confidence = str(decision.get("confidence", "")).strip().lower()
            field = _first(decision.get("field"), f"decision-{index + 1}")
            rationale = _first(decision.get("rationale"), decision.get("reason"))
            result["default_decisions"].append(
                {
                    "item": field,
                    "current_choice": _first(decision.get("value"), decision.get("decision"), "见 DESIGN.md 当前权威字段"),
                    "handling": rationale or "按 DESIGN.md 当前默认决策处理",
                }
            )
            if source in {"recommended-default", "inferred", "screenshot-calibrated"} or confidence == "low":
                gap = {
                    "id": f"DECISION-{index + 1:03d}",
                    "type": "recommended-default" if source == "recommended-default" else "inferred",
                    "priority": "medium" if confidence != "low" else "high",
                    "question": f"{field} 基于 {source or 'decision'} 写入，需要在有更多证据时确认。",
                    "current_judgment": _first(decision.get("value"), decision.get("decision"), "见 DESIGN.md 当前权威字段"),
                    "evidence_source": "evidence.decisions",
                    "confidence": confidence,
                    "impact_scope": _first(decision.get("impact"), "影响后续原型保真度"),
                    "current_handling": rationale or "按 DESIGN.md 当前默认决策处理",
                    "needs_confirmation": "是",
                    "writeback_location": field,
                }
                if gap["priority"] == "high":
                    result["high_priority"].append(gap)
                else:
                    result["medium_priority"].append(gap)

    # ── assumptions：低优先级推断项（支持 list/dict/str） ──
    for key, item in iter_items(front_matter.get("assumptions")):
        gap = normalize_gap(item, "inferred")
        if is_placeholder_value(gap.get("question")):
            continue
        if not gap.get("id"):
            gap["id"] = _fallback_id_from_key("ASM", key)
        gap["priority"] = "low"
        gap["evidence_source"] = gap["evidence_source"] or "assumptions"
        _complete_gap_defaults(gap, "assumptions")
        result["low_priority"].append(gap)

    # ── knownLimits：按子字段拆分（不是泛化 uncovered 倾倒区） ──
    known_limits = front_matter.get("knownLimits", {})
    if isinstance(known_limits, list):
        for item in known_limits:
            if is_placeholder_value(item):
                continue
            if isinstance(item, str) and item.strip():
                result["uncovered"].append({
                    "category": item,
                    "status": "默认处理已写入 DESIGN.md",
                    "default_handling": item,
                })
    elif isinstance(known_limits, dict):
        # evidenceSummary 是普通描述，不是 gap
        es = known_limits.get("evidenceSummary")
        if isinstance(es, str):
            result["evidence_summary"] = es

        # defaultDecisions：进入独立 section（当前生效默认值）
        for _, item in iter_items(known_limits.get("defaultDecisions")):
            if isinstance(item, dict):
                result["default_decisions"].append({
                    "item": _first(item.get("item"), item.get("name")),
                    "current_choice": _first(item.get("currentChoice"), item.get("decision"), item.get("value")),
                    "handling": _first(item.get("handling"), item.get("defaultHandling")),
                })
            elif isinstance(item, str) and item.strip():
                result["default_decisions"].append({
                    "item": item,
                    "current_choice": "见 DESIGN.md 当前默认规则",
                    "handling": "按 DESIGN.md 当前默认规则处理",
                })

        # unconfirmedCapabilities：进入未覆盖 / 未观察内容
        for _, item in iter_items(known_limits.get("unconfirmedCapabilities")):
            if isinstance(item, dict):
                result["uncovered"].append({
                    "category": _first(item.get("capability"), item.get("category"), item.get("item")),
                    "status": _first(item.get("status"), "未确认"),
                    "default_handling": _first(
                        item.get("defaultHandling"), item.get("handling")
                    ),
                })
            elif isinstance(item, str) and item.strip():
                result["uncovered"].append({
                    "category": item,
                    "status": "未确认",
                    "default_handling": "",
                })

        # highImpactPending：进入高优先级 gaps（会影响页面生成）
        for _, item in iter_items(known_limits.get("highImpactPending")):
            if isinstance(item, dict):
                result["high_priority"].append({
                    "id": _first(item.get("id")) or f"GAP-{len(result['high_priority']) + 1:03d}",
                    "type": "unconfirmed",
                    "priority": "high",
                    "question": _first(item.get("item"), item.get("question")),
                    "current_judgment": _first(
                        item.get("currentDefault"), item.get("current_judgment")
                    ),
                    "evidence_source": "knownLimits.highImpactPending",
                    "confidence": _first(item.get("confidence")),
                    "impact_scope": _first(item.get("impact"), item.get("impact_scope")),
                    "current_handling": _first(item.get("currentHandling")),
                    "needs_confirmation": _first(item.get("needsConfirmation"), "是"),
                    "writeback_location": _first(item.get("writebackLocation")),
                })
            elif isinstance(item, str) and item.strip():
                result["high_priority"].append({
                    "id": f"GAP-{len(result['high_priority']) + 1:03d}",
                    "type": "unconfirmed",
                    "priority": "high",
                    "question": item,
                    "current_judgment": "见 DESIGN.md 第 10 章当前默认决策",
                    "evidence_source": "knownLimits.highImpactPending",
                    "confidence": "",
                    "impact_scope": "影响页面生成能力边界与样例准确性",
                    "current_handling": "按 DESIGN.md 当前默认规则处理；确认后回写权威规则",
                    "needs_confirmation": "是",
                    "writeback_location": "knownLimits.highImpactPending / 第 10 章",
                })

    templates = page_templates(front_matter)
    rep_template = representative_page_template(front_matter)
    rep_sections_value: Any = {}
    if isinstance(rep_template, dict):
        rep_sections_value = rep_template.get("sections", rep_template.get("structure"))
    rep_sections_count = 0
    if isinstance(rep_sections_value, list):
        rep_sections_count = len(rep_sections_value)
    elif isinstance(rep_sections_value, str) and rep_sections_value.strip():
        rep_sections_count = 1
    page_patterns = front_matter.get("pagePatterns")
    has_page_patterns = isinstance(page_patterns, dict) and bool(page_patterns)
    components = front_matter.get("components")
    has_components = (isinstance(components, dict) or isinstance(components, list)) and bool(components)

    if not templates and not has_page_patterns and not has_components:
        result["high_priority"].append(
            {
                "type": "unsupported",
                "priority": "high",
                "question": "DESIGN.md 缺少可生成 example.html 的页面语法；请补充 pageTemplates、pagePatterns 或组件结构信息。",
                "current_judgment": "",
                "evidence_source": "pageTemplates / pagePatterns / components",
                "confidence": "",
                "impact_scope": "影响 example.html 与后续页面生成结构",
                "current_handling": "当前无法可靠模拟“用户功能描述 + DESIGN.md”生成页面；example.html 应保持诊断状态",
                "needs_confirmation": "是",
                "writeback_location": "front matter.pageTemplates / pagePatterns / components",
            }
        )
    elif templates and (not rep_template or rep_sections_count <= 0) and not has_page_patterns:
        result["medium_priority"].append(
            {
                "type": "unsupported",
                "priority": "medium",
                "question": "pageTemplates 已存在但缺少可用的代表页面（primary 或 sections/structure 不完整）；建议补全 sections/structure 以支持 agent 生成 example.html。",
                "current_judgment": "",
                "evidence_source": "pageTemplates",
                "confidence": "",
                "impact_scope": "影响 example.html 与代表页面选择",
                "current_handling": "当前只能从其他 DESIGN.md 结构推断页面",
                "needs_confirmation": "是",
                "writeback_location": "front matter.pageTemplates[*].sections",
            }
        )

    evidence_watch = {"inferred", "brief-synthesized", "screenshot-approximate"}
    for item in templates:
        if not isinstance(item, dict):
            continue
        evidence_value = str(item.get("evidence", "")).strip().lower()
        if evidence_value and evidence_value in evidence_watch:
            name = _first(item.get("name"), item.get("title"), item.get("key"), item.get("id"))
            result["medium_priority"].append(
                {
                    "type": "inferred",
                    "priority": "medium",
                    "question": f"pageTemplate「{name or page_template_key(item)}」的页面结构 evidence={evidence_value}，需要补充可验证依据或确认关键 sections/structure。",
                    "current_judgment": "",
                    "evidence_source": "pageTemplates.evidence",
                    "confidence": evidence_value,
                    "impact_scope": "影响 example.html 与后续生成的页面结构一致性",
                    "current_handling": "按 DESIGN.md 当前模板渲染；需要人工确认后回写",
                    "needs_confirmation": "是",
                    "writeback_location": "front matter.pageTemplates[*].evidence",
                }
            )

    declared = guess_archetype(
        " ".join(str(front_matter.get(key, "")) for key in ("productType", "interfaceArchetype", "description"))
    )
    rep_arch = guess_archetype(str(rep_template.get("archetype", "")) if isinstance(rep_template, dict) else "")
    if declared and rep_arch and declared != rep_arch and not declared.startswith("custom:") and not rep_arch.startswith("custom:"):
        result["conflicts"].append(
            {
                "id": f"CONFLICT-{len(result['conflicts']) + 1:03d}",
                "description": f"productType/interfaceArchetype 判断为 {declared}，但代表 pageTemplate.archetype 为 {rep_arch}",
                "candidates": f"{declared} / {rep_arch}",
                "adopted": "",
                "reason": "页面模板与产品形态需要对齐，否则 example.html 会误渲染",
                "needs_confirmation": "是",
            }
        )

    result["high_priority"] = _dedupe_gap_list(result["high_priority"])
    result["medium_priority"] = _dedupe_gap_list(result["medium_priority"])
    result["low_priority"] = _dedupe_gap_list(result["low_priority"])

    # 如果仍没有 uncovered 项，回退到默认未覆盖清单
    if not result["uncovered"]:
        for cat, status, handling in DEFAULT_UNCOVERED:
            if should_skip_default_uncovered(front_matter, cat):
                continue
            result["uncovered"].append({
                "category": cat,
                "status": status,
                "default_handling": handling,
            })

    # ── 置信度 ──
    conf = front_matter.get("confidence", {})
    if isinstance(conf, dict):
        for dim_key, dim_label in CONFIDENCE_DIMENSIONS:
            if dim_key in conf:
                result["confidence_details"][dim_label] = str(conf[dim_key])

    return result


def _cell(value: Any) -> str:
    """规范化表格单元格：空值转为 '—'，并转义竖线。"""
    s = "" if value is None else str(value).strip()
    if not s:
        return "—"
    return s.replace("|", "\\|").replace("\n", " ")


def gen_table_row(cols: list[Any]) -> str:
    return "| " + " | ".join(_cell(c) for c in cols) + " |\n"


def gen_table_header(headers: list[str]) -> str:
    lines = [gen_table_row(headers)]
    lines.append("|" + "|".join("---" for _ in headers) + "|\n")
    return "".join(lines)


def generate_gaps_markdown(gap_data: dict[str, Any], lang: str = "zh") -> str:
    """生成完整 DESIGN_GAPS.md 内容。"""
    lines: list[str] = []
    generation_time = datetime.now().strftime("%Y-%m-%d %H:%M:%S")

    # ── 标题 ──
    lines.append("# DESIGN_GAPS.md｜设计待确认项与冲突清单\n\n")
    lines.append(
        "本文件记录 design-generator 在分析产品源码、截图、URL 或产品描述时发现的"
        "不确定项、冲突项、缺失项和低置信度判断。\n\n"
    )
    lines.append(
        "这些内容不会直接作为 AI 生成页面的主规则。AI 生成页面时应以 `DESIGN.md` 为准。\n\n"
    )
    lines.append(
        "当人工确认本文件中的问题后，应将确认结果回写到 `DESIGN.md`，"
        "并重新生成 `preview.html`。\n\n"
    )
    lines.append(f"> **生成时间**：{generation_time}\n")
    lines.append(f"> **证据模式**：{gap_data['evidence_mode'] or '—'}\n")
    lines.append(f"> **置信度**：{gap_data['confidence_overall'] or '—'}\n\n")
    if gap_data.get("evidence_summary"):
        lines.append("**证据摘要**：" + gap_data["evidence_summary"].strip() + "\n\n")
    lines.append("---\n\n")

    # ── 1. 总体置信度摘要 ──
    lines.append("## 1. 总体置信度摘要\n\n")
    lines.append(gen_table_header(["维度", "置信度", "说明"]))
    conf_details = gap_data["confidence_details"]
    if conf_details:
        for dim, val in conf_details.items():
            lines.append(gen_table_row([dim, val, ""]))
    else:
        lines.append(gen_table_row(["整体", gap_data["confidence_overall"] or "未评估", ""]))
    lines.append("\n---\n\n")

    # ── 1b. 当前默认决策（来自 knownLimits.defaultDecisions） ──
    default_decisions = gap_data.get("default_decisions", [])
    if default_decisions:
        lines.append("## 1b. 当前默认决策\n\n")
        lines.append(
            "AI 在收到 DESIGN.md 后遇到以下项应直接使用下表决策，无需等待人工确认。\n\n"
        )
        lines.append(gen_table_header(["决策项", "当前选择", "处理方式"]))
        for d in default_decisions:
            lines.append(gen_table_row([
                d.get("item"),
                d.get("current_choice"),
                d.get("handling"),
            ]))
        lines.append("\n---\n\n")

    # ── 2. 高优先级待确认项 ──
    lines.append("## 2. 高优先级待确认项\n\n")
    lines.append("高优先级指会直接影响 AI 生成页面准确性的内容。\n\n")
    high = gap_data["high_priority"]
    if high:
        lines.append(gen_table_header([
            "ID", "类型", "待确认问题", "当前判断", "证据来源", "置信度",
            "影响范围", "当前处理策略", "需要确认", "回写位置",
        ]))
        for i, gap in enumerate(high, 1):
            gap_id = gap.get("id") or f"GAP-{i:03d}"
            lines.append(gen_table_row([
                gap_id,
                GAP_TYPES.get(gap.get("type", ""), gap.get("type", "")),
                gap.get("question"),
                gap.get("current_judgment"),
                gap.get("evidence_source"),
                gap.get("confidence"),
                gap.get("impact_scope"),
                gap.get("current_handling"),
                gap.get("needs_confirmation"),
                gap.get("writeback_location"),
            ]))
    else:
        lines.append("无高优先级待确认项。\n")
    lines.append("\n---\n\n")

    # ── 3. 中优先级待确认项 ──
    lines.append("## 3. 中优先级待确认项\n\n")
    lines.append("中优先级指影响局部组件或部分页面，但不影响整体生成。\n\n")
    medium = gap_data["medium_priority"]
    if medium:
        lines.append(gen_table_header([
            "ID", "类型", "待确认问题", "当前判断", "证据来源", "置信度",
            "影响范围", "当前处理策略", "需要确认", "回写位置",
        ]))
        for i, gap in enumerate(medium, 1):
            gap_id = gap.get("id") or f"GAP-{i + 100:03d}"
            lines.append(gen_table_row([
                gap_id,
                GAP_TYPES.get(gap.get("type", ""), gap.get("type", "")),
                gap.get("question"),
                gap.get("current_judgment"),
                gap.get("evidence_source"),
                gap.get("confidence"),
                gap.get("impact_scope"),
                gap.get("current_handling"),
                gap.get("needs_confirmation"),
                gap.get("writeback_location"),
            ]))
    else:
        lines.append("无中优先级待确认项。\n")
    lines.append("\n---\n\n")

    # ── 4. 低优先级待确认项 ──
    lines.append("## 4. 低优先级待确认项\n\n")
    lines.append("低优先级指不会明显影响 AI 生成页面，但可后续完善。\n\n")
    low = gap_data["low_priority"]
    if low:
        lines.append(gen_table_header([
            "ID", "类型", "待确认问题", "当前判断", "证据来源", "置信度",
            "影响范围", "当前处理策略", "需要确认", "回写位置",
        ]))
        for i, gap in enumerate(low, 1):
            gap_id = gap.get("id") or f"GAP-{i + 200:03d}"
            lines.append(gen_table_row([
                gap_id,
                GAP_TYPES.get(gap.get("type", ""), gap.get("type", "")),
                gap.get("question"),
                gap.get("current_judgment"),
                gap.get("evidence_source"),
                gap.get("confidence"),
                gap.get("impact_scope"),
                gap.get("current_handling"),
                gap.get("needs_confirmation"),
                gap.get("writeback_location"),
            ]))
    else:
        lines.append("无低优先级待确认项。\n")
    lines.append("\n---\n\n")

    # ── 5. 设计冲突清单 ──
    lines.append("## 5. 设计冲突清单\n\n")
    lines.append("冲突项必须展示候选值、当前采用值和采用原因。\n\n")
    conflicts = gap_data["conflicts"]
    if conflicts:
        lines.append(gen_table_header([
            "ID", "冲突项", "候选值 / 证据", "当前采用", "原因", "是否需要确认",
        ]))
        for c in conflicts:
            lines.append(gen_table_row([
                c.get("id"),
                c.get("description"),
                c.get("candidates"),
                c.get("adopted"),
                c.get("reason"),
                c.get("needs_confirmation"),
            ]))
    else:
        lines.append("未发现设计冲突。\n")
    lines.append("\n---\n\n")

    # ── 6. 未覆盖 / 未观察内容 ──
    lines.append("## 6. 未覆盖 / 未观察到的内容\n\n")
    lines.append("以下内容在当前输入中未观察到，默认不会作为 DESIGN.md 的主规则：\n\n")
    uncovered = gap_data["uncovered"]
    lines.append(gen_table_header(["类别", "状态", "默认处理"]))
    for u in uncovered:
        lines.append(gen_table_row([
            u.get("category"),
            u.get("status") or "未确认",
            u.get("default_handling"),
        ]))
    lines.append("\n---\n\n")

    # ── 7. 人工确认记录 ──
    lines.append("## 7. 人工确认记录\n\n")
    lines.append("用于后续迭代闭环。\n\n")
    records = gap_data["confirmation_records"]
    if records:
        lines.append(gen_table_header([
            "ID", "确认项", "确认结论", "确认人 / 来源", "确认时间", "是否已回写 DESIGN.md",
        ]))
        for r in records:
            lines.append(gen_table_row([
                r.get("id"),
                r.get("item"),
                r.get("conclusion"),
                r.get("source"),
                r.get("time"),
                r.get("written_back") or "否",
            ]))
    else:
        lines.append("暂无人工确认记录。\n")
    lines.append("\n---\n\n")

    # ── 确认流程 ──
    lines.append("## 确认流程\n\n")
    lines.append("1. 逐项确认上述待确认项\n")
    lines.append("2. 提供反馈（如「侧栏宽度确认是 240px」）\n")
    lines.append("3. AI 会自动更新 DESIGN.md\n")
    lines.append("4. AI 会更新本文档（将已确认项移到「人工确认记录」）\n")
    lines.append("5. 重新生成 preview.html\n")

    return "".join(lines)


def generate_gaps_doc(
    design_folder: Path,
    markdown_name: str = "DESIGN.md",
    output_name: str = "DESIGN_GAPS.md",
    lang: str = "zh",
) -> bool:
    design_md_path = design_folder / markdown_name
    gaps_path = design_folder / output_name

    if not design_md_path.exists():
        print(f"错误：未找到 {design_md_path}", file=sys.stderr)
        return False

    with open(design_md_path, encoding="utf-8") as f:
        content = f.read()

    front_matter = parse_yaml_front_matter(content)
    if not front_matter:
        print("警告：DESIGN.md 中未找到 YAML front matter", file=sys.stderr)
        # 创建最小 gaps 文件
        generation_time = datetime.now().strftime("%Y-%m-%d %H:%M:%S")
        with open(gaps_path, "w", encoding="utf-8") as f:
            f.write("# DESIGN_GAPS.md｜设计待确认项与冲突清单\n\n")
            f.write("> 未发现需要确认的项目。设计系统提取完整且置信度高。\n\n")
            f.write(f"**生成时间**：{generation_time}\n")
        print(f"已生成最小 DESIGN_GAPS.md：{gaps_path}")
        return True

    design_body = markdown_body_after_front_matter(content)
    gap_data = extract_gaps(front_matter)
    gap_data["high_priority"].extend(high_impact_items_from_body(design_body))
    example_meta = read_example_metadata(design_folder)
    example_input = read_example_generation_input(design_folder)
    if example_meta:
        pattern = example_meta.get("pattern", "")
        pattern_source = example_meta.get("pattern_source", "")
        archetype = example_meta.get("archetype", "")
        input_source = str(example_input.get("source", "")).strip().lower()
        user_request = str(example_input.get("userRequest", "")).strip()
        selected_template = str(example_input.get("selectedPageTemplate", "")).strip()
        if pattern_source.startswith("fallback-insufficient-design-md") or pattern_source.startswith("agent-required") or input_source == "diagnostic":
            gap_data["high_priority"].append(
                {
                    "type": "unsupported",
                    "priority": "high",
                    "question": f"example.html 仍是诊断或未完成状态（pattern={pattern}, source={pattern_source}, archetype={archetype}）；需要由 agent 根据 DESIGN.md 生成代表页面。",
                    "current_judgment": "",
                    "evidence_source": "example.html",
                    "confidence": "",
                    "impact_scope": "影响 example.html 与后续原型生成代表页面准确性",
                    "current_handling": "当前只能输出诊断页面，不能证明 DESIGN.md 可用于生成产品原型",
                    "needs_confirmation": "是",
                    "writeback_location": "example.html / front matter.pageTemplates / components",
                }
            )
        elif pattern in {"fallback-neutral", "fallback-archetype"} or pattern_source in {"fallback-neutral", "fallback-archetype"}:
            gap_data["high_priority"].append(
                {
                    "type": "unsupported",
                    "priority": "high",
                    "question": f"example.html 使用旧版硬编码 fallback（pattern={pattern}, source={pattern_source}, archetype={archetype}）；需要由 agent 根据 DESIGN.md 重新生成。",
                    "current_judgment": "",
                    "evidence_source": "example.html",
                    "confidence": "",
                    "impact_scope": "影响 example.html 对 DESIGN.md 可用性的判断",
                    "current_handling": "当前存在产品级预设模板残留",
                    "needs_confirmation": "是",
                    "writeback_location": "example.html",
                }
            )
        elif not example_input or not user_request:
            gap_data["high_priority"].append(
                {
                    "type": "unsupported",
                    "priority": "high",
                    "question": "example.html 缺少有效 example-generation-input.userRequest；无法证明样例页面来自 DESIGN.md 驱动的代表性需求。",
                    "current_judgment": "",
                    "evidence_source": "example.html#example-generation-input",
                    "confidence": "",
                    "impact_scope": "影响 example.html 可追溯性与校验",
                    "current_handling": "需要在 example.html 内嵌样例输入元数据，不得写回 DESIGN.md",
                    "needs_confirmation": "是",
                    "writeback_location": "example.html",
                }
            )
        elif selected_template:
            template_keys = {page_template_key(item) for item in page_templates(front_matter)}
            template_names = {str(item.get("name", "")).strip() for item in page_templates(front_matter) if isinstance(item, dict)}
            if selected_template not in template_keys and selected_template not in template_names:
                gap_data["high_priority"].append(
                    {
                        "type": "conflict",
                        "priority": "high",
                        "question": f"example-generation-input.selectedPageTemplate={selected_template} 与 DESIGN.md pageTemplates 不匹配。",
                        "current_judgment": "",
                        "evidence_source": "example.html#example-generation-input",
                        "confidence": "",
                        "impact_scope": "影响 example.html 与 DESIGN.md 页面语法的一致性",
                        "current_handling": "应选择现有 pageTemplates id/name，或补充对应 pageTemplate",
                        "needs_confirmation": "是",
                        "writeback_location": "example.html / front matter.pageTemplates",
                    }
                )
    else:
        gap_data["medium_priority"].append(
            {
                "type": "unsupported",
                "priority": "medium",
                "question": "未找到 example.html 或无法解析 data-example-* 元数据；请由 agent 根据 DESIGN.md 生成 example.html。",
                "current_judgment": "",
                "evidence_source": "example.html",
                "confidence": "",
                "impact_scope": "无法验证代表页面渲染来源",
                "current_handling": "example.html 是必需验证产物",
                "needs_confirmation": "是",
                "writeback_location": "example.html",
            }
        )
    gap_data["high_priority"] = _dedupe_gap_list(gap_data.get("high_priority", []))
    gap_data["medium_priority"] = _dedupe_gap_list(gap_data.get("medium_priority", []))
    gap_data["low_priority"] = _dedupe_gap_list(gap_data.get("low_priority", []))
    gap_data["conflicts"] = _dedupe_conflicts(gap_data.get("conflicts", []))
    markdown = generate_gaps_markdown(gap_data, lang)

    with open(gaps_path, "w", encoding="utf-8") as f:
        f.write(markdown)

    high_count = len(gap_data["high_priority"])
    medium_count = len(gap_data["medium_priority"])
    low_count = len(gap_data["low_priority"])
    conflict_count = len(gap_data["conflicts"])

    print(f"已生成 DESIGN_GAPS.md：{gaps_path}")
    print(f"   - 高优先级: {high_count} 项")
    print(f"   - 中优先级: {medium_count} 项")
    print(f"   - 低优先级: {low_count} 项")
    print(f"   - 冲突项: {conflict_count} 项")

    return True


def main():
    parser = argparse.ArgumentParser(
        description="根据 DESIGN.md 的证据和 front matter 生成 DESIGN_GAPS.md"
    )
    parser.add_argument(
        "design_folder",
        type=Path,
        help="包含 DESIGN.md 的 DESIGN 文件夹路径",
    )
    parser.add_argument(
        "--markdown-name",
        default="DESIGN.md",
        help="设计 Markdown 文件名（默认：DESIGN.md）",
    )
    parser.add_argument(
        "--output-name",
        default="DESIGN_GAPS.md",
        help="输出 gaps 文件名（默认：DESIGN_GAPS.md）",
    )
    parser.add_argument(
        "--language",
        choices=["zh", "en"],
        default="zh",
        help="输出语言（默认：zh）",
    )

    args = parser.parse_args()
    success = generate_gaps_doc(
        args.design_folder,
        args.markdown_name,
        args.output_name,
        args.language,
    )
    sys.exit(0 if success else 1)


if __name__ == "__main__":
    main()
