#!/usr/bin/env python3
"""Check whether a skill named skill-creator is present in common Codex skill roots."""

from __future__ import annotations

import argparse
import json
import os
import re
import sys
from pathlib import Path


def candidate_roots(extra_roots: list[str]) -> list[Path]:
    home = Path.home()
    roots: list[Path] = []

    codex_home = os.environ.get("CODEX_HOME")
    if codex_home:
        roots.append(Path(codex_home) / "skills")
        roots.append(Path(codex_home) / "skills" / ".system")

    roots.extend(
        [
            home / ".codex" / "skills",
            home / ".codex" / "skills" / ".system",
            home / ".agents" / "skills",
            Path.cwd(),
        ]
    )
    roots.extend(Path(item).expanduser() for item in extra_roots)

    deduped: list[Path] = []
    seen: set[str] = set()
    for root in roots:
        resolved = str(root.expanduser())
        if resolved not in seen:
            deduped.append(root.expanduser())
            seen.add(resolved)
    return deduped


def frontmatter_name(skill_md: Path) -> str | None:
    try:
        text = skill_md.read_text(encoding="utf-8", errors="ignore")[:4096]
    except OSError:
        return None

    match = re.match(r"^---\s*\n(.*?)\n---", text, re.DOTALL)
    if not match:
        return None

    for line in match.group(1).splitlines():
        name_match = re.match(r"\s*name\s*:\s*['\"]?([^'\"\n#]+)", line)
        if name_match:
            return name_match.group(1).strip()
    return None


def find_skill_creator(roots: list[Path]) -> list[dict[str, str]]:
    matches: list[dict[str, str]] = []
    for root in roots:
        if not root.exists():
            continue

        direct = root / "skill-creator" / "SKILL.md"
        if direct.exists():
            matches.append({"path": str(direct), "reason": "folder-name"})
            continue

        try:
            skill_files = list(root.rglob("SKILL.md"))
        except OSError:
            continue

        for skill_md in skill_files:
            if frontmatter_name(skill_md) == "skill-creator":
                matches.append({"path": str(skill_md), "reason": "frontmatter-name"})

    unique: list[dict[str, str]] = []
    seen: set[str] = set()
    for match in matches:
        if match["path"] not in seen:
            unique.append(match)
            seen.add(match["path"])
    return unique


def main() -> int:
    parser = argparse.ArgumentParser(
        description="Check whether skill-creator exists in common local skill roots."
    )
    parser.add_argument(
        "--root",
        action="append",
        default=[],
        help="Additional skill root to search. Can be repeated.",
    )
    args = parser.parse_args()

    roots = candidate_roots(args.root)
    matches = find_skill_creator(roots)
    payload = {
        "found": bool(matches),
        "matches": matches,
        "searched": [str(root) for root in roots],
    }
    print(json.dumps(payload, ensure_ascii=False, indent=2))
    return 0 if matches else 2


if __name__ == "__main__":
    sys.exit(main())
