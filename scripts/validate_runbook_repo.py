"""Validate Markdown links, index coverage, code fences, and public hygiene."""

from __future__ import annotations

import os
from pathlib import Path
import re
import sys
from typing import List, Set

ROOT = Path(__file__).resolve().parent.parent

LINK_RE = re.compile(r"\[[^\]]+\]\(([^)]+)\)")


def get_extra_blocklist() -> List[str]:
    raw = os.environ.get("RUNBOOK_EXTRA_BLOCKLIST", "")
    return [term.strip().lower() for term in raw.split(",") if term.strip()]


SECRET_PATTERNS: List[re.Pattern] = [
    re.compile(r"AKIA[0-9A-Z]{16}"),
    re.compile(r"-----BEGIN (?:[A-Z0-9 ]+ )?PRIVATE KEY-----"),
    re.compile(r"xox[baprs]-[0-9A-Za-z-]{10,}"),
    re.compile(r"gh[pousr]_[0-9A-Za-z]{20,}"),
]


def iter_markdown_files(root: Path) -> List[Path]:
    return sorted(
        path
        for path in root.rglob("*.md")
        if ".git" not in path.parts
    )


def validate_file(path: Path, root: Path, errors: List[str], extra_blocklist: List[str]) -> Set[str]:
    text = path.read_text(encoding="utf-8")
    lowered = text.lower()
    rel = path.relative_to(root).as_posix()

    for term in extra_blocklist:
        if re.search(rf"\b{re.escape(term)}\b", lowered):
            errors.append(f"{rel}: forbidden non-sanitized term '{term}' found")

    for pattern in SECRET_PATTERNS:
        if pattern.search(text):
            errors.append(f"{rel}: potential credential pattern '{pattern.pattern}' found")

    fence_count = 0
    for line in text.splitlines():
        stripped = line.strip()
        if stripped.startswith("```"):
            fence_count += 1
    if fence_count % 2 != 0:
        errors.append(f"{rel}: unbalanced code fence count ({fence_count})")

    referenced_targets: Set[str] = set()
    for raw_target in LINK_RE.findall(text):
        target = raw_target.strip()
        if not target or target.startswith(("http://", "https://", "mailto:", "#")):
            continue
        target_no_anchor = target.split("#", 1)[0]
        if not target_no_anchor:
            continue
        resolved = (path.parent / target_no_anchor).resolve()
        try:
            rel_resolved = resolved.relative_to(root.resolve()).as_posix()
        except ValueError:
            errors.append(f"{rel}: link escapes repository root: '{target}'")
            continue
        if not resolved.exists():
            errors.append(f"{rel}: broken relative link '{target}'")
        else:
            referenced_targets.add(rel_resolved)

    return referenced_targets


def main() -> int:
    errors: List[str] = []
    md_files = iter_markdown_files(ROOT)
    if not md_files:
        print("No markdown files found.", file=sys.stderr)
        return 1

    readme_path = ROOT / "README.md"
    readme_refs: Set[str] = set()
    extra_blocklist = get_extra_blocklist()

    for md in md_files:
        refs = validate_file(md, ROOT, errors, extra_blocklist)
        if md == readme_path:
            readme_refs = refs

    for section in ("runbooks", "diagnosis", "post-mortem"):
        section_dir = ROOT / section
        if not section_dir.is_dir():
            errors.append(f"Missing expected directory: {section}/")
            continue
        for doc in sorted(section_dir.glob("*.md")):
            if doc.name == "template.md":
                rel_doc = doc.relative_to(ROOT).as_posix()
                if rel_doc not in readme_refs:
                    errors.append(f"README.md missing reference to {rel_doc}")
                continue
            rel_doc = doc.relative_to(ROOT).as_posix()
            if rel_doc not in readme_refs:
                errors.append(f"README.md missing reference to {rel_doc}")

    if errors:
        print("Validation failed:", file=sys.stderr)
        for err in errors:
            print(f"  - {err}", file=sys.stderr)
        return 1

    print(f"Validated {len(md_files)} markdown files cleanly (links, fences, README coverage, hygiene).")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
