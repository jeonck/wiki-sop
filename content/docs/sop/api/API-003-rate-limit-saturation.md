---
sop_id: API-003
title: API Rate Limit Saturation (429 Surge)
target_system:
  - public-api-gateway
  - orders-gateway
category: API
severity: P3
symptoms:
  - "429 Too Many Requests rate > 2% of total requests sustained for 10+ minutes"
  - "Prometheus alert: RateLimitSaturation (sum(rate(http_requests_total{status=\"429\"}[5m])) rising)"
  - "Gateway logs show ratelimit_remaining=0 and X-RateLimit-Exceeded headers for a specific API key / client_id"
  - "A single api_key or source IP accounts for a disproportionate share of throttled requests"
verification_metrics:
  - metric: 429 response rate
    threshold: "< 0.5"
    unit: "%"
  - metric: rate-limiter store latency (Redis)
    threshold: "< 5"
    unit: ms
  - metric: legitimate client throttling
    threshold: "= 0"
    unit: clients
escalation:
  l1: "API On-Call (PagerDuty: api-oncall) — acknowledge within 30 min (business hours)"
  l2: "API Product / Partnerships team for quota changes; Security team if abuse or credential leak suspected"
related_sops:
  - API-001
  - SECURITY-002
version: 1.0
owner: API Platform Team
updated: "2026-07-08"
tags:
  - rate-limit
  - "429"
  - throttling
  - quota
---

## 1. Situation

The `public-api-gateway` is returning an elevated volume of HTTP 429 (Too Many Requests). Either a client is exceeding its assigned quota (legitimate growth, a misbehaving integration, or a retry loop), or the rate-limiter backing store is degraded and over-throttling. This is **P3**: throttling is working as designed, but legitimate traffic may be impacted and needs triage.

## 2. Symptoms

- 429 rate > 2% of total requests for 10+ minutes.
- Prometheus alert `RateLimitSaturation` firing.
- Gateway logs show `ratelimit_remaining=0` concentrated on one `api_key` / `client_id` or source IP.
- Optionally: Redis (limiter store) latency elevated, causing broad over-throttling.

## 3. Diagnosis

Determine whether this is a single noisy client, organic quota exhaustion, or a limiter-store problem.

```bash
# 1. Top offending API keys by 429 count in the last 15m
kubectl -n gateway logs -l app=public-api-gateway --since=15m \
  | grep 'status=429' \
  | grep -oE 'api_key=[A-Za-z0-9]+' \
  | sort | uniq -c | sort -rn | head

# 2. Check the rate-limiter backing store (Redis) health & latency
redis-cli -h ratelimit-redis --latency-history -i 1

# 3. Confirm the 429 ratio from Prometheus (last 5m)
curl -sG 'http://prometheus:9090/api/v1/query' \
  --data-urlencode 'query=sum(rate(http_requests_total{service="public-api-gateway",status="429"}[5m])) / sum(rate(http_requests_total{service="public-api-gateway"}[5m]))' \
  | jq '.data.result[0].value[1]'
```

## 4. Action (Step-by-Step)

1. Acknowledge the alert and confirm the 429 ratio (Section 3).
2. Identify whether one `api_key` / IP dominates the throttled requests, or if it is spread across many clients.
3. **Single noisy client:** contact the client owner / partner; if it is an unauthenticated abusive IP, apply a WAF/edge block and evaluate for abuse (**SECURITY-002**).
4. **Legitimate growth on a known partner:** escalate to L2 (API Product) to raise the quota; apply a temporary limit increase for that key if the platform supports it.
5. **Retry storm:** if a client is hammering after 429s, confirm they honor `Retry-After`; if not, tighten their limit and notify them.
6. **Limiter-store degraded (Redis slow/down):** if 429s are broad and Redis latency is high, this is over-throttling — restore/fail over the Redis limiter store; do not raise per-client quotas.
7. Verify legitimate traffic is no longer throttled (Section 5).

## 5. Verification

- [ ] 429 response rate `< 0.5%`
- [ ] rate-limiter store (Redis) latency `< 5ms`
- [ ] legitimate clients being throttled `= 0`
- [ ] Prometheus alert `RateLimitSaturation` resolved
- [ ] Offending client identified and either quota-adjusted, blocked, or notified

## 6. Escalation

- **L1:** API On-Call (PagerDuty: `api-oncall`) — acknowledge within 30 minutes during business hours.
- **L2:** API Product / Partnerships team for quota changes; Security team (**SECURITY-002**) if abuse, scraping, or a leaked credential is suspected.

## 7. Prevention / Follow-up

- Review per-tier quota defaults against real partner usage; publish limits and `Retry-After` guidance in developer docs.
- Add per-client 429 dashboards and alerting so noisy clients surface before saturation.
- Ensure the rate-limiter store is highly available (replica + failover) to avoid over-throttling incidents.
- If sudden quota exhaustion coincides with latency (slow clients holding connections), cross-check **API-001**.
