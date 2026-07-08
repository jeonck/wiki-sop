---
title: Network
weight: 4
---

This category covers incidents in the connectivity and edge layer: DNS resolution failures, TLS/certificate expiry, load-balancer and target-group health, and general connectivity loss. Because almost every request depends on name resolution, valid certificates, and a healthy path to backends, failures here rarely stay contained — they cascade into widespread connection errors and elevated 5xx rates across otherwise-healthy services. The runbooks below cover triage, diagnosis, and remediation for each failure mode.

## SOPs in this category

| SOP | Severity | When to use |
| --- | --- | --- |
| [NETWORK-001](network-001-dns-resolution-failure) | P1 | Internal (`*.svc.cluster.local`) or external names fail to resolve; CoreDNS SERVFAIL/latency spikes causing broad connection failures. |
| [NETWORK-002](network-002-tls-cert-expiry) | P2 | A public endpoint serves an expired or soon-to-expire (<7 days) TLS certificate and clients reject the HTTPS connection. |
| [NETWORK-003](network-003-load-balancer-unhealthy) | P2 | A load balancer marks backend targets unhealthy and returns 503s because healthy host count dropped below desired. |

## Common signals

- `getaddrinfo ENOTFOUND` / `no such host` in application logs, and CoreDNS SERVFAIL ratio above 5% over 5 minutes.
- DNS query latency p99 climbing above 2 seconds.
- `curl: (60) certificate has expired` or `x509: certificate has expired or is not yet valid` from clients.
- Blackbox exporter `probe_ssl_earliest_cert_expiry` within 7 days; browser `NET::ERR_CERT_DATE_INVALID` reported by users.
- ALB `HealthyHostCount` below `DesiredCount`, or `UnHealthyHostCount > 0` sustained over 3 minutes.
- `HTTP 503 Service Unavailable` from the load balancer with no healthy targets.
- Target health check failures: `Target.Timeout` or `Target.ResponseCodeMismatch`.
- Connection timeouts and elevated 5xx rates fanning out across multiple downstream services.

## Escalation & agent use

Each SOP declares its own L1/L2 escalation path in its frontmatter — L1 is typically Network On-Call (PagerDuty: `network-oncall`), with L2 escalating to the Platform SRE Lead, Security/PKI team, or the relevant cloud vendor (DNS, CA, or ELB) support. The AIOps agent matches incoming log lines and metrics against each SOP's `symptoms` list to identify the most likely runbook, then produces a five-line report citing the matched `sop_id` so responders can jump straight to the correct procedure.
