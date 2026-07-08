---
sop_id: DB-001
title: PostgreSQL Connection Pool Exhaustion
target_system:
  - orders-postgres-primary
  - pgbouncer-orders
category: DB
severity: P2
symptoms:
  - "FATAL: sorry, too many clients already"
  - "PgBouncer: no more connections allowed (max_client_conn)"
  - "remaining connection slots are reserved for non-replication superuser connections"
  - "Application logs: TimeoutError: QueuePool limit of size 20 overflow 10 reached, connection timed out"
  - "pg_stat_activity count approaching max_connections for > 5 minutes"
verification_metrics:
  - metric: active_backends_vs_max
    threshold: "< 80%"
    unit: percent
  - metric: pgbouncer_cl_waiting
    threshold: "0"
    unit: connections
  - metric: app_connection_acquire_timeouts
    threshold: "0 in 5m"
    unit: count
escalation:
  l1: "@db-oncall (PagerDuty: Database Primary)"
  l2: "@platform-data-eng (Slack: #data-eng-escalation)"
related_sops:
  - DB-003
  - API-001
version: 1.0
owner: Data Platform Team
updated: "2026-07-08"
tags:
  - postgresql
  - pgbouncer
  - connections
  - saturation
---

## 1. Situation

The `orders-postgres-primary` cluster is refusing new connections. Application
services fronting the database (via `pgbouncer-orders`) report connection
acquisition timeouts, causing cascading request failures and elevated API
latency. This is almost always caused by connection leaks in the application,
a traffic spike outpacing the pool, or long-running transactions holding
backends open.

## 2. Symptoms

- `FATAL: sorry, too many clients already` in PostgreSQL logs.
- PgBouncer rejecting clients: `no more connections allowed (max_client_conn)`.
- Application `QueuePool limit ... reached, connection timed out` errors.
- `pg_stat_activity` backend count sitting at or near `max_connections`.
- Rising API p99 latency and 5xx surge downstream (see API-001).

## 3. Diagnosis

Inspect current connection usage, grouping by state and application, and look
for idle-in-transaction backends holding slots:

```sql
-- Backends vs. configured limit
SELECT count(*) AS backends,
       (SELECT setting::int FROM pg_settings WHERE name = 'max_connections') AS max_conn
FROM pg_stat_activity;

-- Connections grouped by state and client app
SELECT state, application_name, count(*)
FROM pg_stat_activity
GROUP BY state, application_name
ORDER BY count(*) DESC;

-- Long "idle in transaction" backends (leak suspects)
SELECT pid, usename, application_name, state,
       now() - state_change AS idle_duration, left(query, 80) AS last_query
FROM pg_stat_activity
WHERE state = 'idle in transaction'
  AND now() - state_change > interval '2 minutes'
ORDER BY idle_duration DESC;
```

Also check PgBouncer: `psql -h pgbouncer-orders -p 6432 pgbouncer -c 'SHOW POOLS;'`
and inspect `cl_waiting` and `sv_active`.

## 4. Action (Step-by-Step)

1. Confirm the incident: run the "backends vs. max_conn" query; proceed if backends are `>= 90%` of `max_connections`.
2. Identify the top offender from the "grouped by application" query — note whether it is one service or broad saturation.
3. If `idle in transaction` backends older than 2 minutes exist, capture their PIDs, then terminate them: `SELECT pg_terminate_backend(pid) FROM pg_stat_activity WHERE state = 'idle in transaction' AND now() - state_change > interval '5 minutes';`
4. Verify PgBouncer pool mode is `transaction` and `default_pool_size` is sane; if `cl_waiting > 0` persists, raise `default_pool_size` by 20% via config reload (`RELOAD;`) — do NOT exceed 80% of Postgres `max_connections`.
5. If saturation is driven by a single leaking service, coordinate with its owner to roll/restart that service to drop its stale connections.
6. If traffic-driven (all apps saturated), engage capacity: scale read traffic to replicas and confirm connection limits on new app replicas.
7. Re-run the diagnosis queries and confirm backends dropped below 80% of max.
8. Do NOT raise Postgres `max_connections` live — that requires a restart and more memory; escalate if a permanent bump is needed.

## 5. Verification

- [ ] active_backends_vs_max < 80% of `max_connections`
- [ ] pgbouncer_cl_waiting == 0 connections
- [ ] app_connection_acquire_timeouts == 0 over a 5-minute window
- [ ] No new `too many clients already` entries in the last 5 minutes
- [ ] Downstream API p99 latency returned to baseline (cross-check API-001)

## 6. Escalation

- L1: `@db-oncall` (PagerDuty: Database Primary). Page if backends stay above 80% for 10+ minutes after remediation.
- L2: `@platform-data-eng` (Slack: `#data-eng-escalation`) for permanent `max_connections` / instance-size changes or a suspected app-side connection leak needing a code fix.

## 7. Prevention / Follow-up

- Enforce `idle_in_transaction_session_timeout` (e.g. 60s) on application roles.
- Ensure every service uses PgBouncer in `transaction` pooling mode, not direct connections.
- Add alerting at 70% of `max_connections` so on-call reacts before exhaustion.
- File a follow-up ticket to fix any confirmed connection leak; a repeated slow-query storm (DB-003) can also exhaust pools by holding backends open.
