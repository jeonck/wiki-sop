#!/usr/bin/env python3
"""Validate SOP frontmatter against schema/sop.schema.json.

Usage: python scripts/validate_sops.py
Exits non-zero if any SOP under content/docs/sop/ has invalid frontmatter,
or if sop_id / filename collisions exist. Run in CI on every pull request.

Dependencies: pyyaml, jsonschema  (pip install pyyaml jsonschema)
"""
from __future__ import annotations

import json
import sys
from pathlib import Path

try:
    import yaml
    from jsonschema import Draft7Validator
except ImportError:
    sys.exit("Missing deps. Run: pip install pyyaml jsonschema")

ROOT = Path(__file__).resolve().parent.parent
SOP_DIR = ROOT / "content" / "docs" / "sop"
SCHEMA_PATH = ROOT / "schema" / "sop.schema.json"


def extract_frontmatter(text: str):
    """Return the YAML frontmatter block from a Markdown file, or None."""
    if not text.startswith("---"):
        return None
    end = text.find("\n---", 3)
    if end == -1:
        return None
    return yaml.safe_load(text[3:end])


def main() -> int:
    schema = json.loads(SCHEMA_PATH.read_text())
    validator = Draft7Validator(schema)

    errors: list[str] = []
    seen_ids: dict[str, str] = {}
    checked = 0

    for md in sorted(SOP_DIR.rglob("*.md")):
        if md.name == "_index.md":
            continue
        checked += 1
        rel = md.relative_to(ROOT)
        fm = extract_frontmatter(md.read_text(encoding="utf-8"))
        if fm is None:
            errors.append(f"{rel}: missing or malformed frontmatter")
            continue

        for err in sorted(validator.iter_errors(fm), key=lambda e: e.path):
            loc = ".".join(str(p) for p in err.path) or "(root)"
            errors.append(f"{rel}: [{loc}] {err.message}")

        sid = fm.get("sop_id")
        if sid:
            if sid in seen_ids:
                errors.append(f"{rel}: duplicate sop_id '{sid}' (also in {seen_ids[sid]})")
            else:
                seen_ids[sid] = str(rel)

    if errors:
        print(f"✗ {len(errors)} problem(s) across {checked} SOP file(s):\n")
        for e in errors:
            print(f"  - {e}")
        return 1

    print(f"✓ All {checked} SOP file(s) valid. {len(seen_ids)} unique sop_id(s).")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
