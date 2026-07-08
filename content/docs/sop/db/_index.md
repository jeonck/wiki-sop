---
title: Database (DB)
weight: 1
---

This category covers operational runbooks for the PostgreSQL fleet backing our order, login, and reporting services — the primary, its streaming replicas, and the PgBouncer layer in front of them. Database incidents here rarely stay contained: connection exhaustion, replication lag, slow-query storms, and primary loss all surface to customers as elevated API latency, 5xx errors, stale reads, or failed writes at checkout and sign-in. Each SOP below is designed to move an on-call responder from symptom to verified recovery quickly and safely.

## SOPs in this category

| SOP | Severity | When to use |
| --- | --- | --- |
| [DB-001](db-001-connection-pool-exhaustion) | P2 | Postgres/PgBouncer refusing new connections ("too many clients"), app connection-acquire timeouts, backends near `max_connections`. |
| [DB-002](db-002-replication-lag) | P2 | Read replicas falling behind the primary WAL, stale reads served, or `pg_replication_lag_seconds` alerting. |
| [DB-003](db-003-slow-query-storm) | P3 | A surge of long-running queries saturating DB CPU/I/O and causing read-endpoint timeouts without a traffic spike. |
| [DB-004](db-004-primary-failover) | P1 | Primary node unreachable and writes failing fleet-wide; promote a replica and repoint traffic. |

## Common signals

- `FATAL: sorry, too many clients already` / `PgBouncer: no more connections allowed (max_client_conn)`.
- App-side `QueuePool limit ... reached, connection timed out`; `active_backends_vs_max` sustained above ~80% of `max_connections`.
- `pg_stat_replication.replay_lag` above 30s, or Prometheus `pg_replication_lag_seconds > 60`, with reads returning rows missing on the replica.
- WAL receiver drops: `could not receive data from WAL stream`; replication slot retained WAL growing (disk-fill risk).
- Many `active` backends with `query_start` older than 30s; `log_min_duration_statement` firing repeated multi-second `duration:` lines.
- DB host CPU sustained above 85% with a rising run-queue; `pg_stat_activity_max_tx_duration_seconds > 60`.
- `FATAL: could not connect to primary` / primary unreachable with writes failing across services.
- Application read/write timeouts and downstream API p99 latency spikes with no matching increase in request volume.

## Escalation & agent use

Each SOP declares its own escalation path — an L1 on-call rotation (PagerDuty / `#db-oncall`) and, where defined, an L2 owner (`@platform-data-eng`, `#data-eng-escalation`) for permanent fixes such as instance resizing, replica re-seeding, or code changes. Follow the specific SOP's escalation section rather than a generic rule, since the paging thresholds differ per incident. The AIOps agent matches incoming logs and metrics against these SOPs' `symptoms` frontmatter to identify the most likely runbook, then emits a five-line report citing the matching `sop_id` so responders can jump straight to the relevant procedure.
