---
# ─── Machine-readable metadata (consumed by the AIOps agent) ───
sop_id: XXX-000            # Stable unique ID: <CATEGORY>-<NNN>, e.g. DB-001
title: Short imperative title of the procedure
target_system:            # Services/systems in scope
  - service-name
category: DB              # DB | API | INFRA | NETWORK | SECURITY
severity: P2             # P1 (critical) | P2 (high) | P3 (moderate) | P4 (low)
symptoms:                # Trigger phrases the agent matches against error logs
  - "exact or partial log signature"
  - "metric condition, e.g. p95_latency_ms > 1000 for 5m"
verification_metrics:    # Post-action "healthy" criteria (quantitative)
  - metric: metric_name
    threshold: "< 200"
    unit: ms
escalation:
  l1: "team channel or rotation, e.g. #db-oncall"
  l2: "named owner + contact"
related_sops:            # Optional cross-links by sop_id
  - YYY-000
version: 1.0
owner: team-name
updated: 2026-07-08
tags:
  - keyword
---

## 1. Situation

One paragraph: when does this SOP apply? What business impact does the incident cause?

## 2. Symptoms

- Concrete, observable signals (alerts, log lines, dashboards).
- Keep these in sync with the `symptoms:` frontmatter above.

## 3. Diagnosis

Ordered checks to confirm root cause and rule out look-alikes.

```bash
# Example diagnostic command(s)
```

## 4. Action (Step-by-Step)

> These numbered steps are the source of the agent's response logic. Keep each step atomic and verifiable.

1. First action.
2. Second action.
3. ...

## 5. Verification

How to confirm the incident is resolved. Mirror the `verification_metrics:` frontmatter.

- [ ] `metric_name` back within threshold
- [ ] No new alerts for N minutes

## 6. Escalation

If the steps above do not resolve within the SLA, escalate per the `escalation:` frontmatter.

## 7. Prevention / Follow-up

Root-cause fixes, config hardening, or backlog items to prevent recurrence.
