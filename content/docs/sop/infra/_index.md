---
title: Infrastructure (INFRA)
weight: 3
---

This category covers node- and pod-level infrastructure incidents: disk pressure and filesystem exhaustion, memory exhaustion and OOM kills, and pods that fail to reach a stable running state. These conditions degrade or halt customer-facing services — a full node can stop scheduling and evict pods, an OOM kill produces active 5xx failures, and a crash loop silently drains capacity. Fast, consistent triage against these runbooks limits blast radius and shortens time to recovery.

## SOPs in this category

| SOP | Severity | When to use |
| --- | --- | --- |
| [INFRA-001](infra-001-disk-full) | P2 | A node or host is out of disk space or inodes — ENOSPC errors, a filesystem at >= 90%, or `DiskPressure=True` with pods being evicted. |
| [INFRA-002](infra-002-memory-oom) | P1 | Processes or containers are being OOM-killed (exit 137), node `MemoryPressure=True`, or 5xx spikes coincide with pod restarts. |
| [INFRA-003](infra-003-pod-crashloop) | P2 | A pod repeatedly starts and fails in `CrashLoopBackOff` with rising restarts, non-zero exit codes, or probe failures below desired replicas. |

## Common signals

- `no space left on device` / ENOSPC in kubelet, container, or application logs.
- A mounted filesystem at >= 90% used (`df -h`) or inode exhaustion (`df -i`).
- Node conditions `DiskPressure=True` or `MemoryPressure=True` in `kubectl describe node`.
- Kernel OOM: `Out of memory: Killed process ...` in `dmesg`, and pods `OOMKilled` with exit code 137.
- Pods in `CrashLoopBackOff` with a climbing `RESTARTS` count and `Back-off restarting failed container` events.
- Non-zero container exit codes (1 app error, 137 OOM, 139 SIGSEGV) and liveness/readiness probe failures.
- Deployment `availableReplicas` below `desiredReplicas`, often with correlated HTTP 5xx and latency spikes.
- Prometheus thresholds crossed: filesystem availability < 10%, or working-set-to-limit ratio > 0.95.

## Escalation & agent use

Each SOP declares its own L1/L2 escalation path — L1 is the on-call SRE (PagerDuty `infra-primary`), and L2 varies by SOP between the Infrastructure Platform lead and the owning service/application team. The AIOps agent matches incoming logs and alerts against these SOPs' `symptoms` signatures to identify the most likely runbook. It then produces a concise five-line report citing the matched `sop_id`, so responders can jump straight to the relevant diagnosis and action steps.
