# AIOps Agent

Turns a production error log into a **SOP-grounded five-line incident report**,
using the SOP wiki as its knowledge base. Implements Phase 2/3 of the roadmap in
[`../content/docs/agent.md`](../content/docs/agent.md).

```
error log ──▶ retrieve candidate SOPs ──▶ Claude (Opus 4.8) ──▶ 5-line report
              (lexical match on           reasons over the        + SOP-compliance
               `symptoms` field)          SOP's Action steps       flag
```

## How it works

- **`sop_index.py`** — loads every SOP under `../content/docs/sop/`, parses the
  YAML frontmatter, and ranks SOPs against an incoming log with a dependency-light
  lexical scorer weighted toward the `symptoms` field. No embedding provider
  needed; the raw Markdown *is* the index (a `git pull` refreshes it). Has **no
  Anthropic dependency** and is unit-tested offline.
- **`agent.py`** — retrieves the top-3 candidate SOPs, hands them plus the log to
  Claude, and returns a structured `IncidentReport` (Pydantic) via the Anthropic
  SDK's structured-outputs support. Claude picks the best SOP, cites its `sop_id`,
  derives the verification line from the SOP's `verification_metrics`, and flags
  `compliant` / `non_compliant` / `sop_missing`.

## Setup

```bash
pip install -r requirements.txt
export ANTHROPIC_API_KEY=...        # or run `ant auth login`
```

## Run

```bash
# Analyze a sample incident
python agent.py samples/incident-db.log

# Or pipe a live log
echo "connection pool exhausted; login-api p95 1200ms" | python agent.py
```

Example output:

```
┌─ Incident Report ───────────────────────────────
│ 1. Incident    : [login-api] login latency spike, pool saturation (10:00)
│ 2. Root cause  : DB connection pool exhausted (#DB #resource)
│ 3. Action      : Per SOP DB-001 — tune pool max, rolling restart
│ 4. Verification: api_p95_latency_ms < 200; db_active_connections < 80% of max
│ 5. Prevention  : Raise max pool size; add autoscale follow-up
├─────────────────────────────────────────────────
│ Matched SOP    : DB-001
│ SOP coverage   : compliant
└─────────────────────────────────────────────────
```

## Test (offline — no API key)

```bash
python tests/test_index.py
```

## Model

Uses `claude-opus-4-8` with adaptive thinking and structured outputs. The model
is centralized in `agent.py` (`MODEL`).
