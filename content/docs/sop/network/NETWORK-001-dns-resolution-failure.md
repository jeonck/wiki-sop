---
sop_id: NETWORK-001
title: DNS Resolution Failure for Internal and External Services
target_system:
  - coredns.kube-system
  - resolver.internal.corp
  - api.payments.svc.cluster.local
category: NETWORK
severity: P1
symptoms:
  - "getaddrinfo ENOTFOUND api.payments.svc.cluster.local"
  - "dial tcp: lookup <host> on 10.96.0.10:53: no such host"
  - "CoreDNS SERVFAIL rate > 5% over 5m (coredns_dns_responses_total{rcode=\"SERVFAIL\"})"
  - "DNS query latency p99 > 2s (coredns_dns_request_duration_seconds)"
verification_metrics:
  - metric: coredns_servfail_ratio
    threshold: "< 0.5"
    unit: "%"
  - metric: dns_query_latency_p99
    threshold: "< 100"
    unit: "ms"
  - metric: coredns_ready_replicas
    threshold: ">= 2"
    unit: "pods"
escalation:
  l1: "Network On-Call (PagerDuty: network-oncall)"
  l2: "Platform SRE Lead + Cloud DNS vendor support ticket"
related_sops:
  - NETWORK-003
  - API-002
version: 1.0
owner: Network SRE
updated: "2026-07-08"
tags:
  - dns
  - coredns
  - resolution
  - p1
---

## 1. Situation

Applications across one or more clusters are failing to resolve internal
(`*.svc.cluster.local`) or external hostnames. Because nearly every request
depends on name resolution, a DNS outage cascades into widespread connection
failures and elevated 5xx rates. Treat this as a P1 whenever more than one
service reports resolution errors simultaneously.

## 2. Symptoms

- Application logs show `getaddrinfo ENOTFOUND` or `no such host`.
- CoreDNS `SERVFAIL` response ratio exceeds 5% over a 5-minute window.
- DNS query latency p99 climbs above 2 seconds.
- Intermittent errors correlate with a specific CoreDNS pod or upstream resolver.

## 3. Diagnosis

Confirm whether the failure is internal (CoreDNS/kube-dns) or upstream
(corporate/cloud resolver), and isolate the affected layer.

```bash
# Resolve an internal service via the cluster DNS VIP
dig +short api.payments.svc.cluster.local @10.96.0.10

# Test an external name through the same resolver
dig +short example.com @10.96.0.10

# Query upstream resolver directly to rule out CoreDNS
dig +short example.com @1.1.1.1

# Inspect CoreDNS health and recent logs
kubectl -n kube-system get pods -l k8s-app=kube-dns -o wide
kubectl -n kube-system logs -l k8s-app=kube-dns --tail=100 | grep -Ei 'SERVFAIL|timeout|error'

# Check the ConfigMap for a broken forward/upstream block
kubectl -n kube-system get configmap coredns -o yaml
```

## 4. Action (Step-by-Step)

1. Run the `dig` internal, external, and upstream queries above and record which layer fails.
2. If only internal names fail, verify CoreDNS pods are `Ready` and at least 2 replicas exist: `kubectl -n kube-system get deploy coredns`.
3. If a single CoreDNS pod is unhealthy, delete it to force reschedule: `kubectl -n kube-system delete pod <coredns-pod>`.
4. If the `forward` block points at an unreachable upstream, revert the `coredns` ConfigMap to the last known-good revision and roll pods.
5. If upstream resolvers are down (external queries fail via `@1.1.1.1` too), open an L2 ticket and temporarily point `forward` at a healthy secondary resolver.
6. If NodeLocal DNSCache is deployed, check its DaemonSet: `kubectl -n kube-system get ds node-local-dns` and restart affected nodes' cache pods.
7. Once queries succeed from a debug pod, confirm application error rates recover before closing.

## 5. Verification

- [ ] `coredns_servfail_ratio` back below 0.5%
- [ ] `dns_query_latency_p99` below 100 ms
- [ ] `coredns_ready_replicas` at 2 or more
- [ ] Application `ENOTFOUND` / `no such host` log lines have stopped

## 6. Escalation

- **L1:** Network On-Call (PagerDuty: `network-oncall`) — engage immediately on P1.
- **L2:** Platform SRE Lead and, if the upstream/cloud resolver is implicated,
  open a Cloud DNS vendor support ticket with query traces attached.

## 7. Prevention / Follow-up

- Deploy NodeLocal DNSCache to reduce load on central CoreDNS and add resilience.
- Alert on `coredns_dns_responses_total{rcode="SERVFAIL"}` ratio, not just pod liveness.
- Pin CoreDNS at 2+ replicas with a PodDisruptionBudget and anti-affinity.
- Gate `coredns` ConfigMap changes behind review; keep last-good revision handy for fast rollback.
- If this outage drove a 5xx surge downstream, cross-reference API-002.
