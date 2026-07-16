#!/usr/bin/env python3
"""Extract the machine-readable design contract from DESIGN.md front matter."""

from __future__ import annotations

import argparse
import datetime as _dt
import hashlib
import json
from pathlib import Path
import re
from typing import Any


FRONT_MATTER_RE = re.compile(r"\A---\s*\n(.*?)\n---\s*(?:\n|\Z)", re.S)
CLASS_NAME_EXCLUDES = {
    "body",
    "button",
    "css",
    "div",
    "footer",
    "header",
    "html",
    "input",
    "json",
    "main",
    "md",
    "png",
    "section",
    "select",
    "span",
    "svg",
    "table",
    "tbody",
    "td",
    "textarea",
    "th",
    "thead",
    "tr",
}


def parse_simple_yaml(text: str) -> dict[str, Any]:
    """Parse the small YAML subset used by generated DESIGN.md front matter."""

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
            line[content_indent:] if line.strip() else "" for line in block_lines
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


def load_design(path: Path) -> tuple[dict[str, Any], str, str]:
    text = path.read_text(encoding="utf-8")
    match = FRONT_MATTER_RE.search(text)
    if not match:
        raise SystemExit(f"No YAML front matter found in {path}")
    front_matter = match.group(1)
    try:
        import yaml  # type: ignore

        data = yaml.safe_load(front_matter) or {}
    except Exception:
        data = parse_simple_yaml(front_matter)
    if not isinstance(data, dict):
        raise SystemExit(f"Front matter in {path} did not parse to a mapping")
    source_hash = hashlib.sha256(text.encode("utf-8")).hexdigest()
    return data, text, source_hash


def design_body(text: str) -> str:
    match = FRONT_MATTER_RE.search(text)
    return text[match.end() :] if match else text


DESIGN_RUNTIME_FIELDS = (
    "name",
    "summary",
    "tokens",
    "layout",
    "components",
    "pageTemplates",
    "generationRules",
    "copywriting",
    "legacyTokens",
    "technology",
    "runtime",
    "language",
)

DESIGN_RUNTIME_DOMAINS: dict[str, tuple[str, ...]] = {
    "tokens": ("tokens",),
    "shell": ("layout",),
    "components": ("components",),
    "patterns": ("pageTemplates",),
    "rules": (
        "generationRules",
        "copywriting",
        "legacyTokens",
        "technology",
        "runtime",
        "language",
        "name",
        "summary",
    ),
}


def design_runtime_hashes(design: dict[str, Any], source_text: str = "") -> dict[str, str]:
    """Return stable hashes for independently reviewable design domains."""
    hashes: dict[str, str] = {}
    body_hash = (
        hashlib.sha256(design_body(source_text).encode("utf-8")).hexdigest()
        if source_text
        else ""
    )
    for domain, fields in DESIGN_RUNTIME_DOMAINS.items():
        payload: dict[str, Any] = {
            "design": {
                key: make_json_safe(design[key])
                for key in fields
                if key in design
            }
        }
        if domain == "rules":
            payload["bodySha256"] = body_hash
        hashes[domain] = hashlib.sha256(
            json.dumps(payload, ensure_ascii=False, sort_keys=True, separators=(",", ":")).encode("utf-8")
        ).hexdigest()
    return hashes


def design_runtime_sha256(design: dict[str, Any], source_text: str = "") -> str:
    """Aggregate the independently reviewable rendered-design domains."""
    payload = design_runtime_hashes(design, source_text)
    return hashlib.sha256(
        json.dumps(payload, ensure_ascii=False, sort_keys=True, separators=(",", ":")).encode("utf-8")
    ).hexdigest()


def markdown_headings(text: str) -> list[str]:
    return [
        match.group(1).strip()
        for match in re.finditer(r"^#{1,4}\s+(.+)$", design_body(text), re.M)
        if match.group(1).strip()
    ][:40]


def collect_design_class_names(value: Any, output: set[str] | None = None, *, allow_string: bool = False) -> set[str]:
    if output is None:
        output = set()
    if not value:
        return output
    if isinstance(value, list):
        for item in value:
            collect_design_class_names(item, output, allow_string=allow_string)
        return output
    if isinstance(value, dict):
        for key, item in value.items():
            if re.fullmatch(r"classNames?|classes|selector|source", str(key), re.I):
                if isinstance(item, dict):
                    collect_design_class_names(list(item.values()), output, allow_string=True)
                else:
                    collect_design_class_names(item, output, allow_string=True)
            elif isinstance(item, (dict, list)):
                collect_design_class_names(item, output, allow_string=False)
        return output
    if allow_string and isinstance(value, str):
        for match in re.findall(r"\.?[A-Za-z][A-Za-z0-9_-]{2,}", value):
            cleaned = match.lstrip(".")
            if cleaned not in CLASS_NAME_EXCLUDES:
                output.add(cleaned)
    return output


def extract_body_class_names(text: str) -> list[str]:
    body = design_body(text)
    names: set[str] = set()
    for attr in re.findall(r"\bclass(?:Name)?\s*=\s*[\"']([^\"']+)[\"']", body):
        for name in re.split(r"\s+", attr.strip()):
            cleaned = name.strip().lstrip(".")
            if cleaned and cleaned not in CLASS_NAME_EXCLUDES:
                names.add(cleaned)
    for selector in re.findall(r"(?<![A-Za-z0-9_-])\.([A-Za-z][A-Za-z0-9_-]{2,})", body):
        if selector not in CLASS_NAME_EXCLUDES:
            names.add(selector)
    return sorted(names)


def extract_body_data_attrs(text: str) -> list[str]:
    return sorted(set(re.findall(r"\bdata-[a-zA-Z0-9_-]+", design_body(text))))[:80]


def make_json_safe(value: Any) -> Any:
    if isinstance(value, dict):
        return {str(key): make_json_safe(item) for key, item in value.items()}
    if isinstance(value, list):
        return [make_json_safe(item) for item in value]
    if isinstance(value, tuple):
        return [make_json_safe(item) for item in value]
    if isinstance(value, (_dt.datetime, _dt.date)):
        return value.isoformat()
    if isinstance(value, (str, int, float, bool)) or value is None:
        return value
    return str(value)


def build_design_contract(
    design: dict[str, Any],
    *,
    source_path: Path,
    source_hash: str,
    generated_at: str,
    project_name: str,
    source_text: str = "",
) -> dict[str, Any]:
    design_contract = make_json_safe(design)
    body_text = design_body(source_text) if source_text else ""
    front_matter_hash = hashlib.sha256(
        json.dumps(design_contract, ensure_ascii=False, sort_keys=True).encode("utf-8")
    ).hexdigest()
    body_hash = hashlib.sha256(body_text.encode("utf-8")).hexdigest() if body_text else ""
    runtime_hash = design_runtime_sha256(design, source_text)
    runtime_hashes = design_runtime_hashes(design, source_text)
    meta = {
        "generatedAt": generated_at,
        "projectName": project_name,
        "sourcePath": str(source_path),
        "sourceSha256": source_hash,
        "frontMatterSha256": front_matter_hash,
        "bodySha256": body_hash,
        "designRuntimeSha256": runtime_hash,
        "runtimeHashes": runtime_hashes,
    }
    contract: dict[str, Any] = {
        "contractVersion": 4,
        "meta": meta,
        "source": {
            "path": str(source_path),
            "sha256": source_hash,
            "frontMatterSha256": front_matter_hash,
            "bodySha256": body_hash,
            "runtimeSha256": runtime_hash,
            "runtimeHashes": runtime_hashes,
        },
        "design": design_contract,
        "designBody": {
            "sha256": body_hash,
            "headings": markdown_headings(source_text) if source_text else [],
            "classNameHints": extract_body_class_names(source_text) if source_text else [],
            "dataAttributeHints": extract_body_data_attrs(source_text) if source_text else [],
        },
        **meta,
    }
    for key, value in design_contract.items():
        if key not in contract:
            contract[key] = value
    return contract


RAW_COLOR_RE = re.compile(r"#(?:[0-9a-fA-F]{3,8})\b|\b(?:rgb|rgba|hsl|hsla)\s*\(")


def collect_legacy_raw_values(value: Any, path: str = "legacyTokens") -> list[dict[str, Any]]:
    rows: list[dict[str, Any]] = []
    if isinstance(value, dict):
        raw_value = value.get("value")
        if isinstance(raw_value, str) and RAW_COLOR_RE.search(raw_value):
            row: dict[str, Any] = {"path": f"{path}.value", "value": raw_value}
            if value.get("note"):
                row["note"] = str(value.get("note"))
            rows.append(row)
        for key, item in value.items():
            if key == "value":
                continue
            rows.extend(collect_legacy_raw_values(item, f"{path}.{key}"))
    elif isinstance(value, list):
        for index, item in enumerate(value):
            rows.extend(collect_legacy_raw_values(item, f"{path}[{index}]"))
    return rows


def compact_message_rules(message: dict[str, Any]) -> dict[str, Any]:
    rules: dict[str, Any] = {}
    for key in ("source", "use", "length"):
        if key in message:
            rules[key] = make_json_safe(message[key])

    success = message.get("success")
    if isinstance(success, dict):
        success_rules: dict[str, Any] = {}
        for key in ("format", "charLength", "punctuation", "allowBusinessPrefix"):
            if key in success:
                success_rules[key] = make_json_safe(success[key])
        templates = success.get("templates")
        if isinstance(templates, list):
            success_rules["templates"] = [
                make_json_safe(item)
                for item in templates
                if isinstance(item, dict) and item.get("text")
            ]
        if success_rules:
            rules["success"] = success_rules

    error = message.get("error")
    if isinstance(error, dict):
        error_rules: dict[str, Any] = {}
        if "priority" in error:
            error_rules["priority"] = make_json_safe(error["priority"])
        fallback_templates = error.get("fallbackTemplates")
        if isinstance(fallback_templates, list):
            error_rules["fallbackTemplates"] = [
                make_json_safe(item)
                for item in fallback_templates
                if isinstance(item, dict) and item.get("text")
            ]
        if error_rules:
            rules["error"] = error_rules
    return rules


def build_check_rules(design: dict[str, Any], source_text: str = "") -> dict[str, Any]:
    rules: dict[str, Any] = {"version": 1}

    product_classes = sorted(
        collect_design_class_names(
            {
                "layout": design.get("layout"),
                "components": design.get("components"),
                "pageTemplates": design.get("pageTemplates"),
                "generationRules": design.get("generationRules"),
            }
        ).union(extract_body_class_names(source_text) if source_text else [])
    )
    page_templates = design.get("pageTemplates")
    template_ids = [
        str(item.get("id") or item.get("name"))
        for item in page_templates
        if isinstance(page_templates, list) and isinstance(item, dict) and (item.get("id") or item.get("name"))
    ] if isinstance(page_templates, list) else []
    product_fidelity: dict[str, Any] = {
        "requiredPageMetadata": [
            "data-design-source-sha",
            "data-design-runtime-sha",
            "data-design-contract-version",
            "data-design-domains",
            "data-design-profile-sha",
            "data-page-key",
            "data-page-kind",
            "data-surface",
        ],
        "pageTemplateIds": template_ids,
    }
    if product_classes:
        product_fidelity["classFingerprints"] = product_classes
        product_fidelity["requireProductFingerprint"] = True
    if source_text:
        product_fidelity["bodyClassNameHints"] = extract_body_class_names(source_text)
        product_fidelity["bodyDataAttributeHints"] = extract_body_data_attrs(source_text)
    rules["productFidelity"] = product_fidelity

    copywriting = design.get("copywriting")
    if isinstance(copywriting, dict):
        copywriting_rules: dict[str, Any] = {}
        message = copywriting.get("message")
        if isinstance(message, dict):
            message_rules = compact_message_rules(message)
            if message_rules:
                copywriting_rules["message"] = message_rules
        for key in ("contentDialog", "formValidation", "punctuation"):
            value = copywriting.get(key)
            if isinstance(value, dict):
                copywriting_rules[key] = make_json_safe(value)
        if copywriting_rules:
            rules["copywriting"] = copywriting_rules

    legacy_tokens = design.get("legacyTokens")
    if isinstance(legacy_tokens, dict):
        disallowed = collect_legacy_raw_values(legacy_tokens)
        if disallowed:
            rules["legacyTokens"] = {"disallowedRawValues": disallowed}

    return rules


def contract_json(contract: dict[str, Any]) -> str:
    return json.dumps(contract, ensure_ascii=False, indent=2) + "\n"


def check_rules_json(rules: dict[str, Any]) -> str:
    return json.dumps(make_json_safe(rules), ensure_ascii=False, indent=2) + "\n"


def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("design_md", help="Path to DESIGN.md or design.md")
    parser.add_argument("--output", required=True, help="Output design-contract.json path")
    parser.add_argument("--check-rules-output", help="Optional output check-rules.json path")
    parser.add_argument("--name", help="Project name override")
    args = parser.parse_args()

    design_path = Path(args.design_md).expanduser().resolve()
    output = Path(args.output).expanduser().resolve()
    design, text, source_hash = load_design(design_path)
    generated_at = _dt.datetime.now(_dt.timezone.utc).isoformat()
    project_name = args.name or str(design.get("name") or output.parent.parent.name)
    contract = build_design_contract(
        design,
        source_path=design_path,
        source_hash=source_hash,
        generated_at=generated_at,
        project_name=project_name,
        source_text=text,
    )
    output.parent.mkdir(parents=True, exist_ok=True)
    output.write_text(contract_json(contract), encoding="utf-8")
    print(f"Wrote {output}")
    if args.check_rules_output:
        check_rules_output = Path(args.check_rules_output).expanduser().resolve()
        check_rules_output.parent.mkdir(parents=True, exist_ok=True)
        check_rules_output.write_text(check_rules_json(build_check_rules(design, text)), encoding="utf-8")
        print(f"Wrote {check_rules_output}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
