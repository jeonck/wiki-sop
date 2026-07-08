---
sop_id: DB-003
title: Slow Query Storm on Primary Database
target_system:
  - orders-postgres-primary
  - reporting-postgres-replica
category: DB
severity: P3
symptoms:
  - "pg_stat_activity shows many active queries with query_start older than 30s"
  - "LOG: duration: 8423.112 ms statement: SELECT ... (log_min_duration_statement threshold exceeded)"
  - "CPU utilization on db host sustained > 85% with rising run-queue"
  - "Prometheus: pg_stat_activity_max_tx_duration_seconds > 60"
  - "Application timeouts on read endpoints without a corresponding traffic spike"
verification_metrics:
  - metric: queries_running_over_30s
    threshold: "0"
    unit: count
  - metric: db_cpu_utilization
    threshold: "< 70%"
    unit: percent
  - metric: max_active_query_duration
    threshold: "< 30"
    unit: seconds
escalation:
  l1: "@db-oncall (PagerDuty: Database Secondary)"
  l2: "@platform-data-eng (Slack: #data-eng-escalation)"
related_sops:
  - DB-001
  - API-001
version: 1.0
owner: Data Platform Team
updated: "2026-07-08"
tags:
  - postgresql
  - slow-query
  - performance
  - cpu
---

## 1. Situation

A surge of long-running or inefficient queries is saturating CPU and I/O on
`orders-postgres-primary`, degrading response times for all workloads.
Typical triggers: a bad plan after stale statistics, a missing index newly
exposed by data growth, an unbounded analytics query hitting the primary
instead of the reporting replica, or a deploy introducing an N+1 / full-scan
query.

## 2. Symptoms

- Many `active` backends in `pg_stat_activity` with `query_start` older than 30s.
- `log_min_duration_statement` firing repeatedly with multi-second durations.
- DB host CPU sustained above 85% with a growing run-queue.
- Prometheus `pg_stat_activity_max_tx_duration_seconds > 60`.
- Application read timeouts with no matching increase in request volume.

## 3. Diagnosis

Identify the heaviest currently-running statements and the worst offenders by
total time from `pg_stat_statements`:

```sql
-- Currently long-running active queries, worst first
SELECT pid, usename, application_name,
       now() - query_start AS runtime,
       wait_event_type, wait_event,
       left(query, 120) AS query
FROM pg_stat_activity
WHERE state = 'active' AND now() - query_start > interval '5 seconds'
ORDER BY runtime DESC;

-- Aggregate worst offenders across the fleet (requires pg_stat_statements)
SELECT round(total_exec_time::numeric, 0) AS total_ms,
       calls,
       round(mean_exec_time::numeric, 1) AS mean_ms,
       left(query, 120) AS query
FROM pg_stat_statements
ORDER BY total_exec_time DESC
LIMIT 10;
```

## 4. Action (Step-by-Step)

1. Run the "long-running active queries" query and capture the top offenders' PIDs and query text.
2. Classify: is it one repeated statement (bad plan / missing index) or a single monster analytics query?
3. For a runaway analytics/ad-hoc query on the primary, cancel it: `SELECT pg_cancel_backend(<pid>);` (use `pg_terminate_backend` only if cancel does not release it).
4. If the same statement appears many times, confirm the plan with `EXPLAIN (ANALYZE, BUFFERS)` on a replica — look for a Seq Scan on a large table.
5. If stale statistics are suspected (recent data growth or bulk load), run `ANALYZE <table>;` on the affected table to refresh the planner.
6. If an ad-hoc reporting workload is the cause, redirect it to `reporting-postgres-replica` and communicate the correct endpoint to the requester.
7. Re-run the diagnosis query and confirm no queries exceed 30s and CPU is falling.
8. Watch connection count while remediating — a query storm can also exhaust the pool (DB-001); if backends spike, follow that SOP in parallel.

## 5. Verification

- [ ] queries_running_over_30s == 0
- [ ] db_cpu_utilization < 70%
- [ ] max_active_query_duration < 30 seconds
- [ ] `log_min_duration_statement` no longer firing for the offending statement
- [ ] Downstream API read-endpoint latency back to baseline (cross-check API-001)

## 6. Escalation

- L1: `@db-oncall` (PagerDuty: Database Secondary). Page if CPU stays above 85% for 15+ minutes after killing the top offenders.
- L2: `@platform-data-eng` (Slack: `#data-eng-escalation`) for a permanent fix — adding an index, rewriting a query owned by another team, or reverting a deploy that introduced the regression.

## 7. Prevention / Follow-up

- Ensure `pg_stat_statements` and `auto_explain` are enabled for post-incident analysis.
- Route all reporting/analytics traffic to `reporting-postgres-replica`, never the primary.
- Set `statement_timeout` on interactive/reporting roles to cap runaway queries.
- File a follow-up to add the missing index or fix the query, and confirm autovacuum/ANALYZE cadence keeps statistics fresh.
