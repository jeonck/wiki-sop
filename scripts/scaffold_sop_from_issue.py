#!/usr/bin/env python3
"""Generate a draft SOP .md from a 'New SOP request' issue-form body.

Reads the issue body (GitHub issue-form markdown) from $ISSUE_BODY, assigns the
next free sop_id for the chosen category, and writes a schema-valid draft under
content/docs/sop/<category>/. Emits sop_id / file_path / branch / slug to
$GITHUB_OUTPUT for the calling workflow.

Local test:
    ISSUE_BODY="$(cat sample-issue.md)" python scripts/scaffold_sop_from_issue.py
"""
from __future__ import annotations

import datetime as _dt
import os
import re
from pathlib import Path

import yaml

ROOT = Path(__file__).resolve().parent.parent
SOP_DIR = ROOT / "content" / "docs" / "sop"

# issue-form label  ->  internal key
FIELD_LABELS = {
    "Category": "category",
    "SOP Title": "title",
    "Target systems": "target_system",
    "Severity": "severity",
    "Owner team": "owner",
    "Symptoms": "symptoms",
    "Verification metric name": "metric_name",
    "Verification threshold": "metric_threshold",
    "Situation": "situation",
    "Diagnosis": "diagnosis",
    "Action steps": "action",
    "Escalation L1": "escalation_l1",
    "Escalation L2 (optional)": "escalation_l2",
    "Prevention / Follow-up": "prevention",
}


def parse_issue_body(body: str) -> dict[str, str]:
    """Split a GitHub issue-form body on '### <label>' headers."""
    fields: dict[str, str] = {}
    # Split keeping the header text.
    chunks = re.split(r"^###\s+(.+?)\s*$", body, flags=re.MULTILINE)
    # chunks: [pre, label1, value1, label2, value2, ...]
    for i in range(1, len(chunks) - 1, 2):
        label = chunks[i].strip()
        value = chunks[i + 1].strip()
        if value == "_No response_":
            value = ""
        key = FIELD_LABELS.get(label)
        if key:
            fields[key] = value
    return fields


def next_sop_id(category: str) -> str:
    cat_dir = SOP_DIR / category.lower()
    pat = re.compile(rf"^{re.escape(category)}-(\d{{3}})$")
    n = 0
    if cat_dir.exists():
        for md in cat_dir.rglob("*.md"):
            m = re.match(r"^---\n(.*?)\n---", md.read_text(encoding="utf-8"), re.DOTALL)
            if not m:
                continue
            fm = yaml.safe_load(m.group(1)) or {}
            mm = pat.match(str(fm.get("sop_id", "")))
            if mm:
                n = max(n, int(mm.group(1)))
    return f"{category}-{n + 1:03d}"


def slugify(text: str) -> str:
    s = re.sub(r"[^a-z0-9]+", "-", text.lower()).strip("-")
    return s or "untitled"


def _lines(text: str) -> list[str]:
    return [ln.strip() for ln in text.splitlines() if ln.strip()]


def _split_list(text: str) -> list[str]:
    parts = re.split(r"[,\n]", text)
    return [p.strip() for p in parts if p.strip()]


def build_markdown(f: dict[str, str], sop_id: str) -> str:
    category = f["category"]
    escalation = {"l1": f.get("escalation_l1", "TBD")}
    if f.get("escalation_l2"):
        escalation["l2"] = f["escalation_l2"]

    frontmatter = {
        "sop_id": sop_id,
        "title": f.get("title", "Untitled"),
        "target_system": _split_list(f.get("target_system", "")) or ["TBD"],
        "category": category,
        "severity": f.get("severity", "P3"),
        "symptoms": _lines(f.get("symptoms", "")) or ["TBD"],
        "verification_metrics": [
            {
                "metric": f.get("metric_name", "TBD"),
                "threshold": f.get("metric_threshold", "TBD"),
            }
        ],
        "escalation": escalation,
        "version": 0.1,
        "owner": f.get("owner", "TBD"),
        "updated": _dt.date.today().isoformat(),
        "tags": [category.lower()],
    }
    fm_yaml = yaml.safe_dump(frontmatter, sort_keys=False, allow_unicode=True).strip()

    action_lines = _lines(f.get("action", ""))
    action_block = "\n".join(f"{i}. {s}" for i, s in enumerate(action_lines, 1)) or "1. TBD"
    verify_line = f"- [ ] `{f.get('metric_name', 'TBD')}` {f.get('metric_threshold', 'TBD')}"

    body = f"""---
{fm_yaml}
---

> **Draft** generated from an issue request — review and refine before merging.

## 1. Situation

{f.get('situation') or 'TBD'}

## 2. Symptoms

{chr(10).join('- ' + s for s in _lines(f.get('symptoms', ''))) or '- TBD'}

## 3. Diagnosis

{f.get('diagnosis') or 'TBD'}

## 4. Action (Step-by-Step)

{action_block}

## 5. Verification

{verify_line}

## 6. Escalation

- L1: {escalation['l1']}
{('- L2: ' + escalation['l2']) if 'l2' in escalation else ''}

## 7. Prevention / Follow-up

{f.get('prevention') or 'TBD'}
"""
    return body


def main() -> int:
    body = os.environ.get("ISSUE_BODY", "")
    if not body.strip():
        raise SystemExit("ISSUE_BODY is empty")

    f = parse_issue_body(body)
    category = (f.get("category") or "").strip().upper()
    if category not in {"DB", "API", "INFRA", "NETWORK", "SECURITY"}:
        raise SystemExit(f"invalid or missing category: {category!r}")
    f["category"] = category

    sop_id = next_sop_id(category)
    slug = slugify(f.get("title", ""))
    rel_path = f"content/docs/sop/{category.lower()}/{sop_id}-{slug}.md"
    out_path = ROOT / rel_path
    out_path.parent.mkdir(parents=True, exist_ok=True)
    out_path.write_text(build_markdown(f, sop_id), encoding="utf-8")

    branch = f"sop/{sop_id.lower()}-{slug}"
    print(f"Generated {rel_path} ({sop_id})")

    gh_out = os.environ.get("GITHUB_OUTPUT")
    if gh_out:
        with open(gh_out, "a", encoding="utf-8") as fh:
            fh.write(f"sop_id={sop_id}\n")
            fh.write(f"file_path={rel_path}\n")
            fh.write(f"branch={branch}\n")
            fh.write(f"slug={slug}\n")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
