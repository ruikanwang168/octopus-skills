#!/usr/bin/env python3
"""Sync Page Specs Lite Markdown files into page-level P annotations."""

from __future__ import annotations

import argparse
import re
import shutil
from pathlib import Path

from page_specs import (
    annotation_root,
    default_annotations,
    default_page_map,
    default_spec_root,
    markdown_sections,
    parse_frontmatter,
    read_json,
    relative_to_root,
    spec_files,
    write_json,
    now_iso,
)


def normalize(value: str) -> str:
    return re.sub(r"\s+", " ", value or "").strip()


def compact(value: str, limit: int = 140) -> str:
    text = normalize(value)
    if len(text) <= limit:
        return text
    return text[: limit - 1] + "…"


def strip_markdown(value: str) -> str:
    text = re.sub(r"```.*?```", "", value, flags=re.S)
    text = re.sub(r"!\[[^\]]*\]\([^)]+\)", "", text)
    text = re.sub(r"\[[^\]]+\]\([^)]+\)", lambda match: match.group(0).split("]", 1)[0].lstrip("["), text)
    text = re.sub(r"^[#>\-\*\d.\s]+", "", text, flags=re.M)
    text = re.sub(r"[*_`=|]", "", text)
    return normalize(text)


def first_content(sections: dict[str, str], names: list[str], fallback: str = "") -> str:
    for name in names:
        for key, value in sections.items():
            if name == key or name in key:
                text = strip_markdown(value)
                if text:
                    return text
    return fallback


def bullets_from_section(sections: dict[str, str], names: list[str], limit: int = 5) -> list[str]:
    text = first_content(sections, names)
    if not text:
        return []
    candidates = []
    for line in re.split(r"\n+|。|；|;", text):
        line = compact(line, 96)
        if line:
            candidates.append(line.rstrip("。") + "。")
    return candidates[:limit]


def bullet_list(items: list[str]) -> str:
    return "\n".join(f"- {item}" for item in items if item)


def section(title: str, body: str) -> str:
    body = body.strip()
    if not body:
        return ""
    return f"### {title}\n\n{body}\n"


def page_title_from_body(body: str, frontmatter: dict, page_key: str) -> str:
    match = re.search(r"^#\s+(.+?)\s*$", body, re.M)
    if match:
        return normalize(match.group(1))
    return normalize(str(frontmatter.get("pageName") or page_key))


def summary_content(markdown: str, page_key: str) -> tuple[str, str]:
    frontmatter, body = parse_frontmatter(markdown)
    sections = markdown_sections(markdown)
    page_title = page_title_from_body(body, frontmatter, page_key)
    summary = first_content(sections, ["页面摘要", "页面功能介绍"], f"本页面用于完成与「{page_title}」相关的核心业务任务。")
    core_items = bullets_from_section(sections, ["核心内容", "结果区", "筛选条件"], 5)
    if not core_items:
        core_items = [f"围绕「{page_title}」呈现核心业务对象、状态和可执行操作。"]
    flow_items = bullets_from_section(sections, ["业务流程", "流程说明"], 4)
    if not flow_items:
        flow_items = [
            f"用户进入「{page_title}」后识别当前对象和可处理事项。",
            "用户完成查询、查看、填写或操作后，系统反馈处理结果。",
        ]
    action_items = bullets_from_section(sections, ["功能操作", "主要操作", "提交规则"], 5)
    if not action_items:
        action_items = ["阅读页面说明并确认关键操作、状态、规则和待确认问题。"]
    questions = bullets_from_section(sections, ["待确认"], 5)
    if not questions:
        questions = ["页面需求说明是否已被产品、业务和研发共同确认？"]
    content = "\n".join(
        [
            section("页面功能介绍", summary),
            section("核心内容", bullet_list(core_items)),
            section("业务流程", bullet_list(flow_items)),
            section("主要操作", bullet_list(action_items)),
            section("待确认", bullet_list(questions)),
        ]
    ).rstrip() + "\n"
    return page_title, content


def pages_from_page_map(page_map: dict) -> list[dict]:
    return [page for page in page_map.get("pages", []) or [] if page.get("pageKey")]


def next_id(page_key: str, annotations: list[dict]) -> str:
    prefix = f"ANN-{page_key}-"
    max_num = 0
    for ann in annotations:
        ann_id = str(ann.get("id") or "")
        if ann_id.startswith(prefix):
            try:
                max_num = max(max_num, int(ann_id[len(prefix) :]))
            except ValueError:
                pass
    return f"{prefix}{max_num + 1:03d}"


def page_level_p_annotation(annotations: list[dict], page_key: str) -> dict | None:
    for ann in annotations:
        if str(ann.get("pageKey") or "") != page_key:
            continue
        if str(ann.get("annotationType") or "") == "P" and not str(ann.get("surfaceId") or "").strip():
            return ann
    return None


def best_target(page_map: dict, page_key: str) -> dict:
    for page in pages_from_page_map(page_map):
        if str(page.get("pageKey") or "") != page_key:
            continue
        elements = page.get("elements") or []
        for wanted in ("h1", "h2", "main", "header", "section"):
            for element in elements:
                if str(element.get("tag") or "") != wanted or not element.get("selector"):
                    continue
                return {
                    "selector": element.get("selector"),
                    "fallbackText": element.get("text") or page.get("title") or page_key,
                    "strategy": element.get("strategy") or "path",
                    "sourceElementId": element.get("elementId"),
                    "boundsHint": {"text": element.get("text") or "", "tag": element.get("tag") or ""},
                }
        break
    return {
        "selector": "body",
        "fallbackText": page_key,
        "strategy": "path",
        "sourceElementId": None,
        "boundsHint": {"text": page_key, "tag": "body"},
    }


def protected_annotation(ann: dict) -> bool:
    if str(ann.get("createdBy") or "") == "manual":
        return True
    target = ann.get("target") if isinstance(ann.get("target"), dict) else {}
    if str(target.get("strategy") or "") == "manual":
        return True
    review = ann.get("review") if isinstance(ann.get("review"), dict) else {}
    return str(review.get("status") or "") in {"approved", "completed"} and str(ann.get("createdBy") or "") == "manual"


def ensure_pages(data: dict, page_map: dict) -> None:
    existing = {str(page.get("pageKey") or "") for page in data.get("pages") or []}
    for page in pages_from_page_map(page_map):
        page_key = str(page.get("pageKey") or "")
        if page_key and page_key not in existing:
            data.setdefault("pages", []).append(
                {
                    "pageKey": page_key,
                    "title": page.get("title") or page_key,
                    "path": page.get("path") or "",
                    "route": page.get("route") or "",
                }
            )
            existing.add(page_key)


def detect_framework(root: Path) -> bool:
    package_json = root / "package.json"
    if not package_json.exists():
        return False
    data = read_json(package_json)
    deps = {}
    deps.update(data.get("dependencies") or {})
    deps.update(data.get("devDependencies") or {})
    return any(name in deps for name in ("react", "vue", "vite"))


def sync_public_annotations(root: Path, annotations_path: Path) -> Path | None:
    if not detect_framework(root):
        return None
    destination = root / "public" / "prototype-annotator" / "annotations.json"
    destination.parent.mkdir(parents=True, exist_ok=True)
    shutil.copy2(annotations_path, destination)
    specs_source = annotations_path.parent / "specs"
    specs_dest = root / "public" / "prototype-annotator" / "specs"
    if specs_source.exists():
        if specs_dest.exists():
            shutil.rmtree(specs_dest)
        shutil.copytree(specs_source, specs_dest)
    return destination


def main() -> int:
    parser = argparse.ArgumentParser(description="Sync Prototype Annotator Page Specs Lite into page-level P annotations.")
    parser.add_argument("prototype_path", help="HTML file, static directory, or project root")
    parser.add_argument("--spec-root", help="Specs root. Defaults to prototype-annotator/specs")
    parser.add_argument("--annotations", help="Path to annotations.json")
    parser.add_argument("--page-map", help="Path to page-map.json")
    parser.add_argument("--out", help="Output annotations.json path. Defaults to in-place annotations file.")
    parser.add_argument("--force", action="store_true", help="Update manual or approved page-level P annotations")
    args = parser.parse_args()

    target = Path(args.prototype_path).resolve()
    if not target.exists():
        parser.error(f"Path does not exist: {target}")
    root = annotation_root(target)
    spec_root = Path(args.spec_root).resolve() if args.spec_root else default_spec_root(target)
    files = spec_files(spec_root)
    if not files:
        parser.error(f"No page specs found under {spec_root / 'current'}")
    annotations_path = Path(args.annotations).resolve() if args.annotations else default_annotations(target)
    output = Path(args.out).resolve() if args.out else annotations_path
    page_map = read_json(Path(args.page_map).resolve() if args.page_map else default_page_map(target), {"pages": []})
    data = read_json(annotations_path, {"version": 1, "pages": [], "annotations": []})
    data["version"] = data.get("version") or 1
    data.setdefault("project", {"id": "prototype", "name": "Prototype", "source": "local"})
    data.setdefault("pages", [])
    data.setdefault("annotations", [])
    ensure_pages(data, page_map)

    created = 0
    updated = 0
    skipped = 0
    for spec_file in files:
        markdown = spec_file.read_text(encoding="utf-8")
        frontmatter, _ = parse_frontmatter(markdown)
        page_key = str(frontmatter.get("pageKey") or spec_file.stem)
        page_title, _content = summary_content(markdown, page_key)
        ann = page_level_p_annotation(data["annotations"], page_key)
        spec_ref = relative_to_root(spec_file, root)
        source = {"type": "page-spec", "ref": spec_ref}
        if ann and protected_annotation(ann) and not args.force:
            skipped += 1
            continue
        if ann is None:
            ann = {
                "id": next_id(page_key, data["annotations"]),
                "pageKey": page_key,
                "target": best_target(page_map, page_key),
                "title": f"{page_title} · 页面介绍",
                "kind": "note",
                "dimension": "Page overview",
                "priority": "high",
                "visible": True,
                "createdBy": "ai",
                "review": {
                    "required": True,
                    "status": "pending",
                    "reason": "页面级说明标注由 Page Specs Lite 同步生成，需要人工复核。",
                },
            }
            data["annotations"].append(ann)
            created += 1
        else:
            updated += 1
        ann["annotationType"] = "P"
        ann["title"] = ann.get("title") or f"{page_title} · 页面介绍"
        ann["source"] = source
        ann["specRef"] = spec_ref
        ann["contentSource"] = {
            "type": "markdown-file",
            "ref": spec_ref,
            "format": "markdown",
        }
        ann["maintenancePolicy"] = "spec-owned"
        ann.pop("contentMarkdown", None)
        evidence = list(ann.get("evidence") or [])
        marker = f"页面说明文档：{spec_ref}"
        if marker not in evidence:
            evidence.insert(0, marker)
        ann["evidence"] = evidence[:8]
        ann["topics"] = ["source", "business", "flow"]
        ann["updatedAt"] = now_iso()
        if "target" not in ann or not isinstance(ann.get("target"), dict) or not ann["target"].get("selector"):
            ann["target"] = best_target(page_map, page_key)

    data["annotations"] = sorted(data["annotations"], key=lambda item: (str(item.get("pageKey")), str(item.get("id"))))
    write_json(output, data)
    public_copy = sync_public_annotations(root, output)
    print(f"Synced page specs to annotations: {output}")
    if public_copy:
        print(f"Synced public annotations: {public_copy}")
    print(f"Created: {created}; updated: {updated}; skipped protected: {skipped}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
