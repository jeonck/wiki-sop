---
title: Application / API
weight: 2
---

This category covers incidents in the application and API request path: p99 latency degradation, surges in 5xx server errors (frequently triggered by a bad deploy), and rate-limit (429) saturation. These failures sit directly in front of customers — slow or failed API calls translate into abandoned checkouts, retry storms, and revenue-impacting outages — so fast, consistent triage is essential.

## SOPs in this category

| SOP | Severity | When to use |
| --- | --- | --- |
| [API-001](api-001-latency-spike) | P2 | Requests still succeed (2xx) but p99 latency has crossed the alert threshold at normal traffic — slowdown in the request path (DB query, cache, or downstream call). |
| [API-002](api-002-5xx-surge-after-deploy) | P1 | A 5xx surge starts immediately after a deploy — new exceptions/stack traces or CrashLoopBackOff on rolled-out pods. Roll back first, diagnose offline. |
| [API-003](api-003-rate-limit-saturation) | P3 | Elevated 429 (Too Many Requests) — a noisy client exceeding quota, a retry storm, or a degraded rate-limiter store over-throttling legitimate traffic. |

## Common signals

- p99 request latency > 800ms sustained for 5+ minutes while request rate stays flat (`HighRequestLatency`).
- 5xx error rate > 5% sustained for 2+ minutes, onset correlating tightly with a deploy timestamp (`HighErrorRate`).
- 429 rate > 2% of total requests for 10+ minutes (`RateLimitSaturation`), often concentrated on one `api_key` / `client_id` or source IP.
- Logs show repeated `500` / `502` / `503` with a new stack trace, `NullPointer`/panic, or `CrashLoopBackOff` / failing readiness probes on new pods.
- Gateway logs show `ratelimit_remaining=0` and `X-RateLimit-Exceeded` headers for a specific client.
- APM traces dominated by a single span — a slow DB query, cache miss, or a downstream HTTP call to another service.
- Access logs show `upstream_response_time` climbing while requests-per-second is unchanged (rules out simple load).
- Rate-limiter backing store (Redis) latency elevated, causing broad over-throttling rather than a single offending client.

## Escalation & agent use

Each SOP declares its own L1/L2 escalation path — L1 is API On-Call (PagerDuty: `api-oncall`) with an acknowledgement window scaled to severity, and L2 routes to the Platform/Database, Service-owning, API Product, or Security team depending on the root cause. The AIOps agent matches incoming logs and metrics against each SOP's `symptoms` to identify the most likely runbook, then emits a concise five-line report that cites the matching `sop_id` so responders can jump straight to the correct procedure.
