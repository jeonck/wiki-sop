---
sop_id: NETWORK-003
title: Load Balancer Target Group Reporting Unhealthy Backends
target_system:
  - alb.prod-api
  - target-group.api-backend
  - ingress-nginx.ingress
category: NETWORK
severity: P2
symptoms:
  - "ALB HealthyHostCount < DesiredCount for target-group api-backend"
  - "HTTP 503 Service Unavailable from load balancer (no healthy targets)"
  - "UnHealthyHostCount > 0 over 3m (CloudWatch TargetGroup)"
  - "Health check failed: Target.Timeout / Target.ResponseCodeMismatch"
verification_metrics:
  - metric: healthy_host_count
    threshold: ">= desired_count"
    unit: "hosts"
  - metric: lb_5xx_rate
    threshold: "< 0.1"
    unit: "%"
  - metric: target_health_check_latency
    threshold: "< 500"
    unit: "ms"
escalation:
  l1: "Network On-Call (PagerDuty: network-oncall)"
  l2: "Service-owning team + Cloud LB vendor (AWS ELB) support"
related_sops:
  - API-002
  - NETWORK-001
  - NETWORK-002
version: 1.0
owner: Network SRE
updated: "2026-07-08"
tags:
  - load-balancer
  - alb
  - health-check
  - p2
---

## 1. Situation

A load balancer (ALB/NLB or ingress) is marking backend targets unhealthy and
routing to fewer or zero instances. When `HealthyHostCount` drops below desired
capacity, the LB sheds or fails traffic, returning 503s. This commonly precedes
or accompanies an API 5xx surge (see API-002).

## 2. Symptoms

- CloudWatch shows `HealthyHostCount` below `DesiredCount` for the target group.
- LB returns `HTTP 503 Service Unavailable` with no healthy targets.
- `UnHealthyHostCount > 0` sustained over 3 minutes.
- Target health reason: `Target.Timeout` or `Target.ResponseCodeMismatch`.

## 3. Diagnosis

Determine whether targets are truly down, the health check is misconfigured, or
a network/security-group path is blocking probes.

```bash
# Inspect target health and failure reasons
aws elbv2 describe-target-health \
  --target-group-arn arn:aws:elasticloadbalancing:...:targetgroup/api-backend/abc123 \
  --query 'TargetHealthDescriptions[].{Id:Target.Id,State:TargetHealth.State,Reason:TargetHealth.Reason}'

# Confirm the health check path/port config
aws elbv2 describe-target-groups \
  --target-group-arns arn:aws:...:targetgroup/api-backend/abc123 \
  --query 'TargetGroups[].{Path:HealthCheckPath,Port:HealthCheckPort,Codes:Matcher.HttpCode}'

# Hit the backend health endpoint directly (bypassing the LB)
curl -sS -o /dev/null -w "%{http_code} %{time_total}s\n" http://10.0.12.34:8080/healthz

# Through the LB (should return 200 once healthy)
curl -sS -o /dev/null -w "%{http_code}\n" https://api.example.com/healthz
```

## 4. Action (Step-by-Step)

1. Run `describe-target-health` and record the state and `Reason` for each target.
2. `curl` the backend `/healthz` directly on the target's private IP:port to determine if the app itself is failing (app problem) or only the LB probe fails (path/SG problem).
3. If direct curl returns 200 but the LB shows unhealthy, verify the health check `Path`, `Port`, and success `Matcher` codes match the app's actual response.
4. Confirm the target's security group allows inbound from the LB's security group on the health check port; add the rule if missing.
5. If the app returns 5xx directly, this is a backend outage — page the service owner and cross-reference API-002 for the 5xx surge runbook.
6. If a recent deploy reduced healthy count, roll back or scale the deployment/ASG back to desired capacity.
7. If TLS on the target port is the issue (handshake failing on HTTPS health checks), verify the backend cert per NETWORK-002.
8. After remediation, confirm targets return to `healthy` and 503s stop at the LB.

## 5. Verification

- [ ] `healthy_host_count` at or above desired count
- [ ] `lb_5xx_rate` below 0.1%
- [ ] `target_health_check_latency` below 500 ms
- [ ] All targets report `State: healthy` in `describe-target-health`

## 6. Escalation

- **L1:** Network On-Call (PagerDuty: `network-oncall`).
- **L2:** Service-owning team for backend/app failures; open an AWS ELB support
  case if the LB control plane itself is not reflecting true target state.

## 7. Prevention / Follow-up

- Alert on `HealthyHostCount < DesiredCount`, not just total 5xx.
- Keep health check thresholds tolerant of brief GC/warmup pauses (interval, healthy/unhealthy thresholds).
- Use a dedicated lightweight `/healthz` that does not depend on downstream systems.
- Codify security-group rules (LB SG → target SG) in IaC to prevent probe blackholes.
- Add connection draining/deregistration delay so deploys don't flap health counts.
- Correlate recurring incidents with API-002 (5xx surge) and NETWORK-001 (DNS).
