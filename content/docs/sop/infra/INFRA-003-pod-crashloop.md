---
sop_id: INFRA-003
title: "Pod Stuck in CrashLoopBackOff"
target_system:
  - prod-eks-cluster
  - checkout-api
  - payments-worker
  - notification-svc
category: INFRA
severity: P2
symptoms:
  - "kubectl get pods shows STATUS CrashLoopBackOff with rising RESTARTS count"
  - "kubectl describe pod: 'Back-off restarting failed container'"
  - "Container Last State: Terminated with non-zero Exit Code (e.g. 1, 137, 139)"
  - "Readiness/liveness probe failures in pod events: 'Liveness probe failed: HTTP probe failed with statuscode: 500'"
  - "Deployment availableReplicas < desiredReplicas for > 5 minutes"
verification_metrics:
  - metric: "target pod status"
    threshold: "Running"
  - metric: "container restart count delta (5m)"
    threshold: "0"
    unit: "count"
  - metric: "deployment ready replicas"
    threshold: "== desired"
  - metric: "readiness probe success rate"
    threshold: "100"
    unit: "%"
escalation:
  l1: "On-call SRE (PagerDuty schedule: infra-primary)"
  l2: "Owning application team (service CODEOWNERS) via #app-oncall Slack"
related_sops:
  - INFRA-001
  - INFRA-002
  - API-002
version: 1.0
owner: "Infrastructure Platform"
updated: "2026-07-08"
tags:
  - kubernetes
  - crashloopbackoff
  - pod
  - probes
---

## 1. Situation

One or more pods are repeatedly starting, failing, and being restarted by the
kubelet, which applies an exponential back-off (`CrashLoopBackOff`). The
container never reaches a stable `Running`/`Ready` state, so its replicas do
not serve traffic. Common root causes: application startup errors, bad
config/secrets, failing migrations, missing dependencies, misconfigured
liveness probes, or OOM kills (see INFRA-002).

This is a **P2**: capacity is reduced but, assuming other replicas or a prior
ReplicaSet are healthy, the service is degraded rather than fully down.

## 2. Symptoms

- `kubectl get pods` shows `CrashLoopBackOff` and a climbing `RESTARTS` count.
- `kubectl describe pod` events include `Back-off restarting failed container`.
- Container `Last State: Terminated` with a non-zero exit code.
- Liveness/readiness probe failures in the pod's events.
- Deployment `availableReplicas` below `desiredReplicas`.

## 3. Diagnosis

```bash
# Locate the crashing pod and its restart count
kubectl get pods -n prod -o wide | grep -E "CrashLoop|Error|BackOff"

# Read events, exit code, probe config, and image
kubectl describe pod checkout-api-6c8b7-xyz12 -n prod

# The most important step: logs from the *previous* (crashed) container
kubectl logs checkout-api-6c8b7-xyz12 -n prod --previous --tail=100

# If it's an init container failing
kubectl logs checkout-api-6c8b7-xyz12 -n prod -c run-migrations --previous

# Check recent rollout / config changes as a suspect
kubectl rollout history deploy/checkout-api -n prod
```

## 4. Action (Step-by-Step)

1. Get the crashing pod name and note the `RESTARTS` count and container exit
   code from `kubectl describe pod`.
2. Read the previous container's logs (`--previous`). This almost always
   reveals the root cause (stack trace, missing env var, DB connection error).
3. Classify the exit code:
   - `137` (OOMKilled) -> follow **INFRA-002**.
   - `139` (SIGSEGV) -> likely a bug/bad build; plan a rollback.
   - `1`/app-specific -> read logs for the thrown error.
4. If the failure correlates with a recent deploy, roll back to the last known
   good revision — `kubectl rollout undo deploy/checkout-api -n prod`.
5. If caused by bad config/secret, fix the ConfigMap/Secret and restart —
   `kubectl rollout restart deploy/checkout-api -n prod`.
6. If a **liveness probe** is too aggressive (killing a slow-starting but
   healthy app), increase `initialDelaySeconds`/`failureThreshold` or add a
   `startupProbe`, then apply.
7. If a dependency (DB/cache/downstream API) is down, treat that as the primary
   incident and follow its SOP; the pod recovers once the dependency returns.
8. Watch the pod converge to `Running`/`Ready` — `kubectl get pods -w -n prod`.

## 5. Verification

- [ ] Target pod status is `Running` and `1/1 READY`.
- [ ] Restart count is stable (delta `0` over the last 5 minutes).
- [ ] Deployment ready replicas `== desired` (`kubectl get deploy`).
- [ ] Readiness probe success rate `100%` (no probe-failure events).

## 6. Escalation

- **L1:** On-call SRE (PagerDuty schedule: `infra-primary`). Engage if the
  cause is infra-level (node, image pull, storage) or unclear after log review.
- **L2:** Owning application team (service CODEOWNERS) via `#app-oncall` Slack
  for application bugs, failed migrations, or config owned by that team.

## 7. Prevention / Follow-up

- Add a dedicated `startupProbe` for slow-starting apps so liveness probes do
  not kill healthy pods during boot.
- Gate deploys with readiness checks and progressive rollout
  (`maxUnavailable`/`maxSurge`) so a bad build never takes down all replicas.
- Validate ConfigMaps/Secrets in CI before rollout; fail fast on missing keys.
- Ensure resource limits are sane to avoid OOM-driven crash loops
  (**INFRA-002**); rule out disk pressure (**INFRA-001**) on the node. For
  downstream 5xx handling, see **API-002**.
