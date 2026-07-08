---
sop_id: API-002
title: 5xx Error Surge Following a Deploy
target_system:
  - checkout-api
  - payments-service
category: API
severity: P1
symptoms:
  - "5xx error rate > 5% sustained for 2+ minutes immediately after a deployment"
  - "Prometheus alert: HighErrorRate (sum(rate(http_requests_total{status=~\"5..\"}[2m])) / sum(rate(http_requests_total[2m])) > 0.05)"
  - "Logs show repeated 500 / 502 / 503 with a stack trace or NullPointer/panic introduced in the new build"
  - "CrashLoopBackOff or failing readiness probes on newly rolled-out pods"
verification_metrics:
  - metric: 5xx error rate
    threshold: "< 0.5"
    unit: "%"
  - metric: readiness probe success
    threshold: "= 100"
    unit: "%"
  - metric: pod restart count (10m)
    threshold: "= 0"
    unit: restarts
escalation:
  l1: "API On-Call (PagerDuty: api-oncall) — P1 page, acknowledge within 5 min"
  l2: "Service owning team + Incident Commander; declare SEV if customer-facing checkout is down"
related_sops:
  - API-001
  - INFRA-002
version: 1.0
owner: API Platform Team
updated: "2026-07-08"
tags:
  - 5xx
  - deploy
  - rollback
  - incident
---

## 1. Situation

A recent deployment to `checkout-api` (or a shared dependency such as `payments-service`) has introduced a regression causing a surge in server errors. This is a **P1**: customers are seeing failed checkouts. The fastest path to recovery is almost always to roll back to the last known-good release, then diagnose offline.

## 2. Symptoms

- 5xx error rate > 5% sustained for 2+ minutes.
- Onset correlates tightly with a deploy timestamp.
- Logs show a new, repeating exception / stack trace not present before the deploy.
- New pods in `CrashLoopBackOff` or failing readiness probes.

## 3. Diagnosis

Confirm the surge, correlate it to the deploy, and capture evidence before rolling back.

```bash
# 1. Confirm 5xx ratio (last 2m)
curl -sG 'http://prometheus:9090/api/v1/query' \
  --data-urlencode 'query=sum(rate(http_requests_total{service="checkout-api",status=~"5.."}[2m])) / sum(rate(http_requests_total{service="checkout-api"}[2m]))' \
  | jq '.data.result[0].value[1]'

# 2. Correlate with rollout history — is there a deploy in the last ~15m?
kubectl -n checkout rollout history deploy/checkout-api

# 3. Capture the error signature from the new pods before rolling back
kubectl -n checkout logs -l app=checkout-api --since=5m | grep -iE 'ERROR|Exception|panic|500|502|503' | tail -n 30
```

## 4. Action (Step-by-Step)

1. Acknowledge the P1 page immediately and post in the incident channel that you are investigating.
2. Confirm the surge is real (Section 3) and note the offending deploy revision from `rollout history`.
3. Capture logs / a sample stack trace to an incident note so the rollback does not destroy evidence.
4. **Roll back** to the previous revision: `kubectl -n checkout rollout undo deploy/checkout-api`.
5. Watch the rollback complete: `kubectl -n checkout rollout status deploy/checkout-api --timeout=180s`.
6. Confirm the 5xx rate is falling and readiness probes pass on the restored pods (Section 5).
7. If rollback does **not** restore service, the cause is not the deploy — check downstream dependencies and infrastructure (**INFRA-002**), and escalate to L2 / declare a SEV.
8. Freeze further deploys to the service until root cause is understood; mark the bad revision in the CI/CD pipeline.

## 5. Verification

- [ ] 5xx error rate `< 0.5%`
- [ ] readiness probe success `= 100%`
- [ ] pod restart count over last 10m `= 0`
- [ ] Prometheus alert `HighErrorRate` resolved
- [ ] Rollback completed and `rollout status` reports the deployment successfully rolled out

## 6. Escalation

- **L1:** API On-Call (PagerDuty: `api-oncall`) — P1 page, acknowledge within 5 minutes.
- **L2:** Service-owning team plus an Incident Commander. Declare a SEV incident if customer-facing checkout is down or rollback does not recover service within 10 minutes.

## 7. Prevention / Follow-up

- Enforce progressive delivery (canary / blue-green) with automatic rollback on error-rate SLO breach.
- Require readiness probes and a smoke-test gate in the deploy pipeline before shifting production traffic.
- Add a deploy-annotation overlay in Grafana so error surges are visually tied to releases.
- Run a blameless postmortem; add a regression test covering the failure and link it to the bad revision.
