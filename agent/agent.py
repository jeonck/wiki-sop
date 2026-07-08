"""AIOps agent: error log -> SOP-grounded five-line incident report.

Pipeline (see content/docs/agent.md):
  1. Retrieve candidate SOPs by lexical match against the `symptoms` field.
  2. Ask Claude to pick the best-matching SOP and produce a structured
     five-line report, judged against the SOP's Action + verification_metrics.
  3. Flag SOP non-compliance / missing-SOP so documentation gaps surface.

Usage:
    export ANTHROPIC_API_KEY=...            # or `ant auth login`
    python agent.py samples/incident-db.log
    echo "connection pool exhausted ..." | python agent.py
"""
from __future__ import annotations

import sys
from pathlib import Path

from pydantic import BaseModel, Field

import anthropic

from sop_index import SOPIndex, ScoredSOP

MODEL = "claude-opus-4-8"

SYSTEM_PROMPT = """\
You are an IT operations (AIOps) analysis agent. You receive a raw production \
error log and a shortlist of candidate Standard Operating Procedures (SOPs) \
retrieved from the team wiki. Each SOP has an id, symptoms, step-by-step Action, \
verification_metrics, and an escalation path.

Your job:
1. Choose the single SOP whose `symptoms` best match the incoming log. If none \
   of the candidates genuinely match, set matched_sop_id to "NONE".
2. Produce a five-line incident report grounded in the chosen SOP. Cite the \
   sop_id in the action line. The verification line MUST reference the SOP's \
   verification_metrics (the quantitative "healthy" thresholds).
3. Assess SOP coverage:
   - "compliant"      : a matching SOP exists and its Action steps address the incident.
   - "non_compliant"  : a matching SOP exists but the log shows steps were skipped/violated.
   - "sop_missing"    : no candidate SOP covers this incident (documentation gap).
   When coverage is "non_compliant" or "sop_missing", state the gap plainly in \
   the prevention line (e.g. "SOP 미준수/수정 필요" or "신규 SOP 작성 필요").

Be precise and terse. Do not invent metrics or steps that are not in the SOP."""


class IncidentReport(BaseModel):
    incident: str = Field(description="Service, symptom, and time. One line.")
    root_cause: str = Field(description="Root cause with #category #resource tags.")
    action: str = Field(description="Remediation per SOP; cite the sop_id.")
    verification: str = Field(description="Post-fix healthy criteria from verification_metrics.")
    prevention: str = Field(description="Recurrence prevention; note SOP gaps if any.")
    matched_sop_id: str = Field(description='Chosen SOP id, or "NONE".')
    coverage: str = Field(description='"compliant" | "non_compliant" | "sop_missing".')


def _candidate_block(hits: list[ScoredSOP]) -> str:
    parts = []
    for h in hits:
        parts.append(
            f"### Candidate {h.sop.sop_id} (retrieval score {h.score:.1f})\n"
            f"{h.sop.full_text()}"
        )
    return "\n\n".join(parts)


def analyze(log: str, *, index: SOPIndex | None = None, client: anthropic.Anthropic | None = None) -> IncidentReport:
    index = index or SOPIndex()
    client = client or anthropic.Anthropic()

    hits = index.retrieve(log, top_k=3)
    candidates = _candidate_block(hits) if hits else "(no candidate SOPs retrieved)"

    user = (
        f"# Incoming error log\n```\n{log.strip()}\n```\n\n"
        f"# Candidate SOPs (most relevant first)\n{candidates}\n\n"
        "Select the best SOP and produce the structured incident report."
    )

    resp = client.messages.parse(
        model=MODEL,
        max_tokens=4096,
        thinking={"type": "adaptive"},
        output_config={"effort": "medium"},
        system=SYSTEM_PROMPT,
        messages=[{"role": "user", "content": user}],
        output_format=IncidentReport,
    )
    return resp.parsed_output


def format_report(r: IncidentReport) -> str:
    lines = [
        "┌─ Incident Report ───────────────────────────────",
        f"│ 1. Incident    : {r.incident}",
        f"│ 2. Root cause  : {r.root_cause}",
        f"│ 3. Action      : {r.action}",
        f"│ 4. Verification: {r.verification}",
        f"│ 5. Prevention  : {r.prevention}",
        "├─────────────────────────────────────────────────",
        f"│ Matched SOP    : {r.matched_sop_id}",
        f"│ SOP coverage   : {r.coverage}",
        "└─────────────────────────────────────────────────",
    ]
    return "\n".join(lines)


def main() -> int:
    if len(sys.argv) > 1:
        log = Path(sys.argv[1]).read_text(encoding="utf-8")
    elif not sys.stdin.isatty():
        log = sys.stdin.read()
    else:
        print("usage: python agent.py <logfile>  (or pipe a log via stdin)", file=sys.stderr)
        return 2

    report = analyze(log)
    print(format_report(report))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
