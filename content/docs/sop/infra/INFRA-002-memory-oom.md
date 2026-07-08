---
sop_id: INFRA-002
title: "Out-Of-Memory (OOM) Kills on Node and Pods"
target_system:
  - prod-k8s-worker-04
  - prod-k8s-worker-09
  - checkout-api
  - recommendation-svc
category: INFRA
severity: P1
symptoms:
  - "dmesg / kernel log: 'Out of memory: Killed process <pid> (<name>)'"
  - "Pod terminated with reason OOMKilled (kubectl describe pod shows Last State: Terminated, Reason: OOMKilled, Exit Code: 137)"
  - "Node condition MemoryPressure=True in kubectl describe node"
  - "Prometheus alert: container_memory_working_set_bytes / kube_pod_container_resource_limits_memory > 0.95"
  - "Application HTTP 5xx spike coinciding with pod restarts"
verification_metrics:
  - metric: "node available memory"
    threshold: "> 15"
    unit: "%"
  - metric: "node MemoryPressure condition"
    threshold: "False"
  - metric: "target pod OOMKill events (5m)"
    threshold: "0"
    unit: "count"
  - metric: "container working set vs limit"
    threshold: "< 0.85"
    unit: "ratio"
escalation:
  l1: "On-call SRE (PagerDuty schedule: infra-primary)"
  l2: "Owning service team + Infrastructure Platform lead (#infra-platform Slack)"
related_sops:
  - INFRA-003
  - API-002
version: 1.0
owner: "Infrastructure Platform"
updated: "2026-07-08"
tags:
  - memory
  - oom
  - oomkilled
  - memorypressure
---

## 1. Situation

Processes are being killed by the Linux OOM killer, or containers are being
`OOMKilled` by the kubelet for exceeding their memory limits. This causes
request failures, pod restarts, and — under node-level memory pressure — pod
evictions and node instability.

This is a **P1**: an OOM condition typically produces active request failures
(HTTP 5xx) and can cascade across replicas, threatening a customer-facing
outage.

## 2. Symptoms

- `dmesg` shows `Out of memory: Killed process ...` entries.
- `kubectl describe pod` shows `Reason: OOMKilled`, `Exit Code: 137`.
- Container restart count climbing; pods flap between `Running` and
  `CrashLoopBackOff`.
- `kubectl describe node` shows `MemoryPressure=True`.
- 5xx error rate and latency spike correlated with the restarts.

## 3. Diagnosis

```bash
# Confirm kernel OOM kills on the node
sudo dmesg -T | grep -i -E "out of memory|oom-kill|killed process" | tail -20

# Identify OOMKilled containers and exit codes
kubectl get pods -n prod -o wide | grep -E "OOMKilled|CrashLoop|Error"
kubectl describe pod checkout-api-7d9f8-abcde -n prod | grep -A6 "Last State"

# Live memory usage vs limits
kubectl top pods -n prod --sort-by=memory | head
kubectl top nodes

# Inspect the container's configured requests/limits
kubectl get pod checkout-api-7d9f8-abcde -n prod \
  -o jsonpath='{.spec.containers[*].resources}' | python3 -m json.tool
```

## 4. Action (Step-by-Step)

1. Confirm scope: is this a **single container** exceeding its limit, or
   **node-level** memory pressure affecting many pods? Use `dmesg`,
   `kubectl top nodes`, and node conditions.
2. If node-level pressure: cordon the node — `kubectl cordon prod-k8s-worker-04`
   — to stop new scheduling while you stabilize it.
3. Identify the top memory consumer(s) with `kubectl top pods --sort-by=memory`.
4. For an immediate outage, restore capacity: scale the affected Deployment
   out to spread load, or (if a leak) roll the pods —
   `kubectl rollout restart deploy/checkout-api -n prod`.
5. If the container is legitimately under-provisioned, raise its memory limit
   in the Deployment/HPA manifest and apply — verify `requests <= limits`.
6. If a memory **leak** is suspected (steadily rising working set with stable
   load), capture a heap/pprof dump before restarting for post-mortem, then
   restart the pod.
7. Once the node is stable (MemoryPressure False, available memory > 15%),
   uncordon — `kubectl uncordon prod-k8s-worker-04`.
8. Confirm 5xx rate and pod restart count return to baseline.

## 5. Verification

- [ ] Node available memory `> 15%` (`kubectl top nodes` / node_memory metrics).
- [ ] Node `MemoryPressure` condition is `False`.
- [ ] Zero new `OOMKilled` events on target pods over the last 5 minutes.
- [ ] Container working-set-to-limit ratio `< 0.85`.

## 6. Escalation

- **L1:** On-call SRE (PagerDuty schedule: `infra-primary`). Engage immediately
  for any P1 OOM affecting a customer-facing service.
- **L2:** Owning service team (for suspected application memory leaks) plus
  Infrastructure Platform lead (`#infra-platform` Slack) for node capacity or
  cluster autoscaler issues.

## 7. Prevention / Follow-up

- Set realistic memory `requests`/`limits` on every container; avoid limitless
  pods that can starve the node.
- Alert on `container_memory_working_set_bytes / limit > 0.85` (warning) and
  on `OOMKilled` events.
- Enable and tune the cluster autoscaler / vertical pod autoscaler for
  right-sizing.
- File a bug and attach the heap dump for any confirmed leak; if the OOM
  triggered a crash loop, follow **INFRA-003**. For app-level 5xx handling,
  see **API-002**.
