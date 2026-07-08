---
sop_id: DB-004
title: Primary failover
target_system:
- login-api
- order-api
category: DB
severity: P1
symptoms:
- primary is unreachable
- replication lag > 30s
- 'FATAL: could not connect to primary'
verification_metrics:
- metric: db_primary_up
  threshold: == 1
escalation:
  l1: '#db-oncall'
version: 0.1
owner: db-platform
updated: '2026-07-08'
tags:
- db
---

> **Draft** generated from an issue request — review and refine before merging.

## 1. Situation

Primary DB node is down; writes fail across services.

## 2. Symptoms

- primary is unreachable
- replication lag > 30s
- FATAL: could not connect to primary

## 3. Diagnosis

Check pg_stat_replication on replicas; confirm primary unreachable.

## 4. Action (Step-by-Step)

1. Confirm primary is truly down
2. Promote the most up-to-date replica
3. Repoint connection string / update DNS
4. Verify writes succeed

## 5. Verification

- [ ] `db_primary_up` == 1

## 6. Escalation

- L1: #db-oncall


## 7. Prevention / Follow-up

Enable automated failover with Patroni.
