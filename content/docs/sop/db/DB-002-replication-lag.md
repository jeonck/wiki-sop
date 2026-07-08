---
sop_id: DB-002
title: PostgreSQL Streaming Replication Lag
target_system:
  - orders-postgres-primary
  - orders-postgres-replica-1
  - orders-postgres-replica-2
category: DB
severity: P2
symptoms:
  - "pg_stat_replication replay_lag exceeding 30s on a replica"
  - "Application reads returning stale data: row visible on primary but missing on replica"
  - "Prometheus alert: pg_replication_lag_seconds > 60"
  - "LOG: recovery restart point ... falling behind; standby cannot keep up with primary WAL"
  - "replica WAL receiver disconnected: could not receive data from WAL stream"
verification_metrics:
  - metric: replay_lag_seconds
    threshold: "< 10"
    unit: seconds
  - metric: write_to_replica_wal_receiver_status
    threshold: "streaming"
    unit: state
  - metric: replication_slot_retained_wal
    threshold: "< 5"
    unit: GB
escalation:
  l1: "@db-oncall (PagerDuty: Database Primary)"
  l2: "@platform-data-eng (Slack: #data-eng-escalation)"
related_sops:
  - DB-003
  - INFRA-002
version: 1.0
owner: Data Platform Team
updated: "2026-07-08"
tags:
  - postgresql
  - replication
  - streaming
  - lag
---

## 1. Situation

One or more read replicas of `orders-postgres-primary` are falling behind the
primary's write-ahead log (WAL). Services reading from replicas observe stale
data. Common causes: a heavy write burst on the primary, disk/network I/O
saturation on the replica, a long-running query on the replica blocking WAL
replay (with `hot_standby_feedback`), or a stalled WAL receiver.

## 2. Symptoms

- `pg_stat_replication.replay_lag` above 30s for one or more replicas.
- Reads return stale rows: a record committed on the primary is absent on the replica.
- Prometheus alert `pg_replication_lag_seconds > 60`.
- Replica logs show the WAL receiver disconnecting or unable to keep up.
- `replication_slot` retained WAL growing on the primary (disk pressure risk).

## 3. Diagnosis

From the primary, measure per-replica lag; from the replica, confirm the WAL
receiver is live and find any query blocking replay:

```sql
-- Run on PRIMARY: per-replica lag
SELECT client_addr, application_name, state,
       write_lag, flush_lag, replay_lag,
       pg_wal_lsn_diff(pg_current_wal_lsn(), replay_lsn) AS bytes_behind
FROM pg_stat_replication;

-- Run on REPLICA: is streaming active and how far behind (in seconds)?
SELECT status, last_msg_receipt_time, latest_end_lsn
FROM pg_stat_wal_receiver;
SELECT now() - pg_last_xact_replay_timestamp() AS replay_delay;

-- Run on REPLICA: queries potentially blocking WAL replay
SELECT pid, now() - query_start AS runtime, left(query, 80)
FROM pg_stat_activity
WHERE state = 'active'
ORDER BY runtime DESC;
```

## 4. Action (Step-by-Step)

1. Confirm lag: on the primary, run the `pg_stat_replication` query and note `replay_lag` and `bytes_behind` per replica.
2. Determine scope — is it one replica (localized) or all replicas (primary-side write burst)?
3. Single replica: on that replica check `pg_stat_wal_receiver.status`. If not `streaming`, the WAL receiver stalled — check replica disk (`df -h`) and network to primary.
4. If a long-running query on the replica is pinning replay, capture its PID and, if non-critical, cancel it: `SELECT pg_cancel_backend(<pid>);`.
5. If the replica is I/O-bound, temporarily remove it from the read load-balancer pool so lagging reads stop serving stale data.
6. All replicas lagging: check the primary for a bulk write/backfill job or a slow-query storm (DB-003) generating excess WAL; throttle or pause that workload.
7. Watch `replication_slot` retained WAL on the primary — if it exceeds 5 GB and disk is filling, this is an escalation trigger (never drop an active slot without approval).
8. Once `replay_lag` falls below 10s and status is `streaming`, return the replica to the read pool.

## 5. Verification

- [ ] replay_lag_seconds < 10 on every replica
- [ ] write_to_replica_wal_receiver_status == streaming
- [ ] replication_slot_retained_wal < 5 GB on the primary
- [ ] No stale-read reports from application teams for 10 minutes
- [ ] Prometheus `pg_replication_lag_seconds` alert cleared

## 6. Escalation

- L1: `@db-oncall` (PagerDuty: Database Primary). Page if lag exceeds 60s and is still climbing after remediation.
- L2: `@platform-data-eng` (Slack: `#data-eng-escalation`) if a replica must be re-seeded (base backup), a replication slot needs dropping, or primary disk is threatened by retained WAL (coordinate with INFRA-002 for storage).

## 7. Prevention / Follow-up

- Set `max_standby_streaming_delay` deliberately and monitor conflict cancellations.
- Reconsider `hot_standby_feedback = on` if replica queries frequently stall replay.
- Schedule bulk backfills off-peak and throttle WAL generation.
- Alert on `replication_slot` retained WAL size, not just lag seconds, to catch disk-fill risk early.
