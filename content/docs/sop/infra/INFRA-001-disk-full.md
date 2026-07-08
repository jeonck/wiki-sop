---
sop_id: INFRA-001
title: "Disk Full / Filesystem Exhaustion on Node"
target_system:
  - prod-node-app-07
  - prod-k8s-worker-12
  - prod-db-primary-01
category: INFRA
severity: P2
symptoms:
  - "kubelet log: 'no space left on device' (ENOSPC) on write/exec"
  - "df reports a mounted filesystem at >= 90% used"
  - "Node condition DiskPressure=True in kubectl describe node"
  - "Application logs: 'write /var/log/app.log: no space left on device'"
  - "Prometheus alert: node_filesystem_avail_bytes / node_filesystem_size_bytes < 0.10"
verification_metrics:
  - metric: "root filesystem usage"
    threshold: "< 80"
    unit: "%"
  - metric: "node DiskPressure condition"
    threshold: "False"
  - metric: "inode usage on affected mount"
    threshold: "< 85"
    unit: "%"
escalation:
  l1: "On-call SRE (PagerDuty schedule: infra-primary)"
  l2: "Infrastructure Platform team lead (#infra-platform Slack)"
related_sops:
  - INFRA-003
  - DB-002
version: 1.0
owner: "Infrastructure Platform"
updated: "2026-07-08"
tags:
  - disk
  - filesystem
  - node
  - diskpressure
---

## 1. Situation

A node or host has run out of usable disk space (or inodes) on one or more
filesystems. On a Kubernetes node this triggers the `DiskPressure` condition,
which causes the kubelet to stop accepting new pods and to begin evicting
existing ones. On a standalone host, applications fail to write logs, temp
files, or database data, often resulting in crashes or corrupted writes.

This is a **P2**: service is degraded or at imminent risk, but not yet a full
outage on all replicas.

## 2. Symptoms

- `no space left on device` (ENOSPC) errors in kubelet, container, or app logs.
- `df -h` shows a filesystem at >= 90% used.
- `kubectl describe node` shows `DiskPressure=True` and eviction events.
- Pods stuck in `Evicted` or `Pending` state on the affected node.
- Prometheus: `node_filesystem_avail_bytes` trending toward zero.

## 3. Diagnosis

```bash
# Identify which filesystem is full (space and inodes)
df -h
df -i

# On a K8s node, confirm the node condition
kubectl describe node prod-k8s-worker-12 | grep -A5 Conditions

# Find the largest space consumers on the affected mount (e.g. /var)
sudo du -x -h --max-depth=1 /var 2>/dev/null | sort -rh | head -20

# Common K8s offenders: container logs and unused images
sudo du -sh /var/lib/docker/containers/* 2>/dev/null | sort -rh | head
sudo du -sh /var/log/pods/* 2>/dev/null | sort -rh | head

# Find deleted-but-open files still holding space
sudo lsof +L1 2>/dev/null | awk '$7+0 > 100000000'
```

## 4. Action (Step-by-Step)

1. Confirm the affected mount and whether the pressure is **space** or
   **inodes** using `df -h` and `df -i`. Record the mount point.
2. If a K8s node: cordon it to stop new scheduling — `kubectl cordon prod-k8s-worker-12`.
3. Identify the top consumer with the `du` command in section 3.
4. Reclaim container image space safely — `sudo crictl rmi --prune`
   (or `docker image prune -a -f` on Docker runtimes).
5. Truncate or rotate oversized logs. Do **not** `rm` an open logfile;
   truncate it instead — `sudo truncate -s 0 /var/log/app.log`.
6. If a deleted-but-open file holds the space (from `lsof +L1`), restart the
   holding process to release the inode.
7. Re-check `df -h`; confirm usage has dropped below 80%.
8. Wait for the kubelet to clear `DiskPressure` (typically < 60s), then
   uncordon — `kubectl uncordon prod-k8s-worker-12`.
9. Confirm evicted pods reschedule successfully.

## 5. Verification

- [ ] Root/affected filesystem usage `< 80%` (`df -h`).
- [ ] Node `DiskPressure` condition is `False` (`kubectl describe node`).
- [ ] Inode usage on affected mount `< 85%` (`df -i`).
- [ ] No new ENOSPC errors in the last 5 minutes of logs.

## 6. Escalation

- **L1:** On-call SRE (PagerDuty schedule: `infra-primary`). Engage if space
  cannot be reclaimed within 15 minutes or the mount refills immediately.
- **L2:** Infrastructure Platform team lead (`#infra-platform` Slack). Engage
  for volume resize, hardware provisioning, or suspected runaway data growth.

## 7. Prevention / Follow-up

- Add/verify Prometheus alerts at 80% (warning) and 90% (critical) for
  `node_filesystem_avail_bytes` and inode usage.
- Enforce container log rotation (`containerLogMaxSize`, `containerLogMaxFiles`
  in the kubelet config) and application-level `logrotate`.
- Schedule periodic `crictl rmi --prune` via a DaemonSet or node cron.
- If a database volume is the culprit, follow **DB-002** for data growth
  investigation. If pods flap after recovery, see **INFRA-003**.
