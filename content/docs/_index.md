---
title: SOPs
next: getting-started
weight: 1
---

Welcome to the **IT SOP Wiki** — a Standard Operating Procedure knowledge base built to be consumed by both operators and AIOps agents.

## How this wiki is organized

Every operational procedure is a single Markdown file with a standardized structure:

1. **YAML frontmatter** — machine-readable metadata (`sop_id`, `symptoms`, `severity`, `verification_metrics`, `escalation`). This is what an agent reads to match an incoming error log to the right SOP.
2. **Body** — the human-readable runbook: Situation → Symptoms → Diagnosis → Step-by-Step Action → Verification → Escalation → Prevention.

## Sections

{{< cards >}}
  {{< card link="getting-started" title="Getting Started" icon="book-open" subtitle="How to read, write, and validate SOPs." >}}
  {{< card link="sop" title="SOP Library" icon="collection" subtitle="All operational procedures, grouped by domain." >}}
  {{< card link="agent" title="Agent Integration" icon="chip" subtitle="How agents index SOPs and produce five-line reports." >}}
{{< /cards >}}

## Quick reference

| Field | Purpose | Consumed by |
|---|---|---|
| `sop_id` | Stable unique ID (e.g. `DB-001`) | Humans + Agent (citation) |
| `symptoms` | Trigger phrases matched against logs | Agent (retrieval) |
| `severity` | P1–P4 priority | Agent (routing) |
| `verification_metrics` | Post-action "healthy" thresholds | Agent (report line 4) |
| `escalation` | L1/L2 owners | Agent (unresolved routing) |
