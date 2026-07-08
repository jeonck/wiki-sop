---
sop_id: API-001
title: API Latency Spike (p99 Degradation)
target_system:
  - checkout-api
  - orders-gateway
category: API
severity: P2
symptoms:
  - "p99 request latency > 800ms sustained for 5+ minutes on checkout-api"
  - "Prometheus alert: HighRequestLatency (histogram_quantile 0.99 of http_request_duration_seconds > 0.8)"
  - "Access logs show upstream_response_time climbing while request rate is flat"
  - "Grafana APM traces dominated by time spent in DB query or downstream HTTP calls"
verification_metrics:
  - metric: p99 request latency
    threshold: "< 400"
    unit: ms
  - metric: p50 request latency
    threshold: "< 120"
    unit: ms
  - metric: error rate (5xx)
    threshold: "< 0.5"
    unit: "%"
escalation:
  l1: "API On-Call (PagerDuty: api-oncall) — acknowledge within 15 min"
  l2: "Platform / Database team if root cause is downstream (DB pool, cache, or dependency)"
related_sops:
  - DB-001
  - API-003
  - INFRA-002
version: 1.0
owner: API Platform Team
updated: "2026-07-08"
tags:
  - latency
  - performance
  - p99
  - apm
---

## 1. Situation

The `checkout-api` service is serving requests successfully (2xx) but response times have degraded. p99 latency has crossed the alert threshold while traffic volume is roughly normal, indicating a slowdown in the request path rather than a demand surge. Left unaddressed this leads to client timeouts, retry storms, and eventual 5xx cascades.

## 2. Symptoms

- p99 request latency > 800ms sustained for 5+ minutes.
- Prometheus alert `HighRequestLatency` firing for `checkout-api`.
- APM traces show the bulk of request time in a single span (DB query, cache miss, or a downstream call to `orders-gateway`).
- No corresponding spike in requests-per-second (rules out simple load).

## 3. Diagnosis

Confirm the alert, identify where time is being spent, and check downstream health.

```bash
# 1. Confirm p99 from Prometheus (last 5m)
curl -sG 'http://prometheus:9090/api/v1/query' \
  --data-urlencode 'query=histogram_quantile(0.99, sum(rate(http_request_duration_seconds_bucket{service="checkout-api"}[5m])) by (le))' \
  | jq '.data.result[0].value[1]'

# 2. Check pod resource pressure / restarts / throttling
kubectl -n checkout top pods -l app=checkout-api
kubectl -n checkout get pods -l app=checkout-api

# 3. Look at where latency lives — slow DB queries are a common cause (see DB-001)
kubectl -n checkout logs -l app=checkout-api --since=10m | grep -iE 'slow query|upstream_response_time' | tail -n 20
```

If the slow span is a database query or connection acquisition, this is likely connection pool exhaustion — follow **DB-001** in parallel.

## 4. Action (Step-by-Step)

1. Acknowledge the PagerDuty alert to stop re-pages and signal ownership.
2. Open the APM trace view and identify the dominant slow span (DB, cache, or downstream HTTP).
3. If CPU throttling or memory pressure is present (`kubectl top`), scale out: `kubectl -n checkout scale deploy/checkout-api --replicas=<current+50%>`.
4. If the slow span is a **DB query / pool acquisition**, escalate to L2 (Database team) and follow **DB-001**; do not blindly restart pods.
5. If the slow span is a **downstream dependency** (`orders-gateway`), check its health and, if degraded, enable the circuit breaker / fallback for that call path.
6. If a recent deploy correlates with the onset (check deploy timeline), treat as a regression and follow **API-002** rollback procedure.
7. Verify latency recovers (Section 5) before deferring further work to follow-up.

## 5. Verification

- [ ] p99 request latency `< 400ms`
- [ ] p50 request latency `< 120ms`
- [ ] error rate (5xx) `< 0.5%`
- [ ] Prometheus alert `HighRequestLatency` resolved / no longer firing
- [ ] No pod restarts or CPU throttling in the last 10 minutes

## 6. Escalation

- **L1:** API On-Call (PagerDuty: `api-oncall`) — acknowledge within 15 minutes.
- **L2:** Platform / Database team when the root cause is downstream (DB pool exhaustion per **DB-001**, cache outage, or a degraded dependency).

Escalate to L2 immediately if latency does not improve within 20 minutes of scaling, or if the dominant span is outside the service's own code.

## 7. Prevention / Follow-up

- Add / tune p99 SLO burn-rate alerting so degradation is caught earlier.
- Ensure DB connection pool sizing and timeouts are documented and load-tested (cross-ref **DB-001**).
- Add circuit breakers and sensible client timeouts on all downstream calls.
- File a follow-up ticket with the APM trace and root cause; review in the next incident retro.
