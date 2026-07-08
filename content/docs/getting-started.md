---
title: Getting Started
weight: 1
---

This page explains how to **read**, **write**, and **validate** an SOP.

## Reading an SOP

Every SOP has two layers:

- **Frontmatter** (the YAML block at the top) — structured metadata for agents.
- **Body** — the human runbook, in a fixed seven-section order.

## The seven-section body

| # | Section | Purpose |
|---|---|---|
| 1 | Situation | When the SOP applies and its impact |
| 2 | Symptoms | Observable signals (mirror the `symptoms` frontmatter) |
| 3 | Diagnosis | Confirm root cause, rule out look-alikes |
| 4 | Action | Numbered, atomic steps — the agent's response logic |
| 5 | Verification | Confirm resolution (mirror `verification_metrics`) |
| 6 | Escalation | Who to page if unresolved |
| 7 | Prevention | Root-cause fixes and follow-ups |

## Writing a new SOP

1. Copy [`templates/SOP-TEMPLATE.md`](https://github.com/jeonck/wiki-sop/blob/main/templates/SOP-TEMPLATE.md).
2. Place it under `content/docs/sop/<category>/<SOP-ID>-<slug>.md`.
3. Assign the next free `sop_id` in that category (`DB-001`, `DB-002`, …).
4. Fill **every required frontmatter field** — CI will reject the PR otherwise.
5. Keep `symptoms` and `verification_metrics` precise: these directly drive agent matching and report generation.

## Required frontmatter fields

`sop_id`, `title`, `target_system`, `category`, `severity`, `symptoms`,
`verification_metrics`, `escalation`, `version`, `owner`, `updated`.

The full contract is enforced by [`schema/sop.schema.json`](https://github.com/jeonck/wiki-sop/blob/main/schema/sop.schema.json).

## Validating locally

```bash
# Validate all SOP frontmatter against the schema
npm run validate      # or: python scripts/validate_sops.py
```

CI runs the same check on every pull request, so an SOP with a missing or
malformed field never reaches the agent's index.

## Severity levels

| Severity | Meaning | Response |
|---|---|---|
| <span class="sev-p1">P1</span> | Critical — customer-facing outage | Immediate, page on-call |
| <span class="sev-p2">P2</span> | High — degraded service | Within SLA, notify owner |
| <span class="sev-p3">P3</span> | Moderate — limited impact | Business hours |
| <span class="sev-p4">P4</span> | Low — cosmetic / preventive | Backlog |
