---
sop_id: SECURITY-002
title: Brute-Force / Credential-Stuffing Login Response
target_system:
  - Okta
  - Auth0
  - Cloudflare WAF
  - nginx-ingress
category: SECURITY
severity: P2
symptoms:
  - "Auth logs show >100 failed logins/min from a single source IP or /24 with status 'INVALID_CREDENTIALS'"
  - "High ratio of failed:successful auth (>20:1) across many distinct usernames from few IPs (credential-stuffing signature)"
  - "Okta ThreatInsight / Auth0 'blocked_ip_address' events firing; SIEM rule 'auth.bruteforce' triggered"
  - "nginx access log 4xx spike on POST /login or /oauth/token from a rotating set of residential-proxy IPs"
verification_metrics:
  - metric: failed_login_rate_per_source
    threshold: "< 10"
    unit: attempts/min
  - metric: attacker_ip_block_coverage
    threshold: "100"
    unit: percent
  - metric: compromised_account_successful_logins
    threshold: "0"
    unit: logins
escalation:
  l1: security-oncall (PagerDuty SEC-ONCALL, ack within 30m)
  l2: IAM platform team + Incident Commander if any account confirmed compromised
related_sops:
  - SECURITY-001
  - SECURITY-003
  - NETWORK-003
version: 1.0
owner: security-oncall
updated: "2026-07-08"
tags:
  - authentication
  - brute-force
  - credential-stuffing
  - p2
---

## 1. Situation

An automated attacker is attempting to guess or replay credentials against the login/token endpoints. This may be a targeted brute-force (many attempts, one account) or credential-stuffing (breach-corpus passwords sprayed across many accounts). Objective: throttle and block the attack traffic, then confirm whether any account was actually compromised.

## 2. Symptoms

- Sustained failed-login spike from a small number of source IPs or subnets.
- Many distinct usernames tried from few IPs (stuffing) or many attempts on one username (brute-force).
- Okta ThreatInsight / Auth0 anomaly detection or SIEM `auth.bruteforce` rule firing.
- WAF / ingress 4xx spike on `/login` or `/oauth/token`.

## 3. Diagnosis

Quantify the attack, identify source IPs, and check for any successful login mixed into the noise.

```bash
# Top source IPs hitting the login endpoint with failures (last hour)
grep 'POST /login' /var/log/nginx/access.log \
  | awk '$9 ~ /^40[13]$/ {print $1}' \
  | sort | uniq -c | sort -rn | head -20

# Any SUCCESS from an attacking IP = potential compromise (Okta System Log via CLI)
okta-cli logs list --filter 'eventType eq "user.session.start"' --since 1h \
  --output json | jq -r 'select(.outcome.result=="SUCCESS")
    | "\(.published) \(.actor.alternateId) \(.client.ipAddress)"'

# Confirm failed:success ratio to classify brute-force vs stuffing
```

## 4. Action (Step-by-Step)

1. Acknowledge the page and open `#sec-incident`; note attack start time and target endpoint.
2. Block the top offending source IPs/subnets at the WAF/edge (Cloudflare firewall rule or nginx `deny`), starting with the highest-volume sources.
3. Enable or tighten rate-limiting on the auth endpoint (e.g., Cloudflare rate-limit rule: 5 req / IP / min on `/login`) and turn on Okta/Auth0 adaptive-MFA/brute-force lockout if not already active.
4. Identify any username that received a SUCCESS from an attacking IP; treat those accounts as compromised.
5. For each compromised account: force session revocation, require password reset, and enforce MFA re-enrollment.
6. If stuffing is confirmed, cross-reference targeted usernames against known-breach corpora and pre-emptively force resets for reused passwords.
7. Monitor block effectiveness; expand blocks to new attacker IPs as they rotate (feed IOCs to NETWORK-003 for edge blocking).
8. Once failed-login rate returns to baseline and no active compromise remains, downgrade and begin follow-up.

## 5. Verification

- [ ] failed_login_rate_per_source < 10 attempts/min (per remaining source)
- [ ] attacker_ip_block_coverage == 100 percent (all identified IOCs blocked)
- [ ] compromised_account_successful_logins == 0 logins after remediation
- [ ] Rate-limiting / adaptive-MFA confirmed active on all auth endpoints

## 6. Escalation

- **L1:** security-oncall (PagerDuty SEC-ONCALL, ack within 30m).
- **L2:** IAM platform team + Incident Commander if any account is confirmed compromised (follow SECURITY-003 for post-compromise access review; SECURITY-001 if credentials/keys were retrieved).

## 7. Prevention / Follow-up

- Require MFA on all accounts and enable ThreatInsight / breached-credential detection.
- Deploy managed rate-limiting and bot-management rules on all auth endpoints by default.
- Add SIEM alerting on failed:success ratio, not just raw failure count, to catch low-and-slow stuffing.
- Publish IOC IPs to the shared blocklist and review lockout thresholds quarterly.
