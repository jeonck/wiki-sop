---
sop_id: SECURITY-003
title: Suspicious Account Access Investigation
target_system:
  - Okta
  - AWS CloudTrail
  - Google Workspace
  - Datadog SIEM
category: SECURITY
severity: P2
symptoms:
  - "Impossible-travel alert: same user authenticating from geographically distant IPs within a window that precludes physical travel"
  - "Successful login from a new device/ASN/country not previously seen for the user (Okta 'new device' + 'new geo-location')"
  - "CloudTrail shows privilege-escalation or IAM changes (AttachUserPolicy, CreateAccessKey) outside change-management hours"
  - "SIEM anomaly: user session performing bulk data reads (S3 GetObject / Drive export) far above their 30-day baseline"
verification_metrics:
  - metric: active_suspicious_sessions
    threshold: "0"
    unit: sessions
  - metric: unauthorized_privilege_changes_reverted
    threshold: "100"
    unit: percent
  - metric: anomalous_data_access_confirmed_scope
    threshold: "documented"
    unit: report
escalation:
  l1: security-oncall (PagerDuty SEC-ONCALL, ack within 30m)
  l2: Incident Commander + data-protection officer if data exfiltration or PII access is confirmed
related_sops:
  - SECURITY-001
  - SECURITY-002
version: 1.0
owner: security-oncall
updated: "2026-07-08"
tags:
  - account-takeover
  - anomaly-detection
  - investigation
  - p2
---

## 1. Situation

A user or service account is exhibiting behavior consistent with account takeover: unexpected geography/device, privilege changes, or anomalous data access. The account may be compromised (following a phishing or credential-stuffing event) or the activity may be legitimate-but-unusual. Objective: rapidly determine legitimacy, contain if malicious, and preserve evidence throughout.

## 2. Symptoms

- Impossible-travel or new-country/new-device successful logins.
- IAM/privilege changes outside approved change windows.
- Bulk data access well above the account's historical baseline.
- SIEM behavioral-anomaly rule firing for the identity.

## 3. Diagnosis

Correlate the identity's recent authentications and actions; confirm whether the activity is authorized before containing.

```bash
# Timeline of the user's auth events, IPs, and devices (Okta System Log)
okta-cli logs list \
  --filter 'actor.alternateId eq "user@example.com"' --since 24h \
  --output json | jq -r '.[] | "\(.published) \(.eventType) \(.client.ipAddress) \(.client.userAgent.rawUserAgent)"'

# CloudTrail: sensitive/privilege actions by this principal in the last 24h
aws cloudtrail lookup-events \
  --lookup-attributes AttributeKey=Username,AttributeValue=user@example.com \
  --start-time "$(date -u -v-24H '+%Y-%m-%dT%H:%M:%SZ')" \
  --query 'Events[].{t:EventTime,e:EventName}' --output table

# Compare data-access volume to baseline before deciding it is malicious
```

## 4. Action (Step-by-Step)

1. Acknowledge the page, open `#sec-incident`, and start an evidence-preservation log (do not alter source logs).
2. Out-of-band, contact the account owner (phone/known-good channel — not the possibly-compromised email) to confirm whether the activity is theirs.
3. If unconfirmed or confirmed malicious, **contain immediately:** suspend the Okta user and revoke all active sessions/tokens (`okta-cli users suspend`; clear sessions).
4. Revoke any credentials the session created or could have accessed; if access keys were generated, follow SECURITY-001.
5. Revert unauthorized privilege changes to last-known-good (detach rogue IAM policies, remove added group memberships).
6. Scope the data accessed during the suspicious window; document objects/records touched for the exposure report.
7. Block the attacker source IPs at the edge and add them to the shared blocklist.
8. If the entry vector was credential guessing/stuffing, cross-link SECURITY-002; if a compromised static credential, cross-link SECURITY-001.
9. Once contained, coordinate account recovery: password reset, MFA re-enrollment, and re-enable only after owner identity is verified.

## 5. Verification

- [ ] active_suspicious_sessions == 0 sessions (all revoked)
- [ ] unauthorized_privilege_changes_reverted == 100 percent
- [ ] anomalous_data_access_confirmed_scope == documented (exposure report attached to incident)
- [ ] Account re-enabled only after out-of-band owner verification + MFA reset

## 6. Escalation

- **L1:** security-oncall (PagerDuty SEC-ONCALL, ack within 30m).
- **L2:** Incident Commander + data-protection officer if data exfiltration or PII access is confirmed (may trigger breach-notification obligations).

## 7. Prevention / Follow-up

- Tune impossible-travel and new-device/geo detections; suppress known-VPN false positives to reduce alert fatigue.
- Enforce phishing-resistant MFA (FIDO2/WebAuthn) for privileged accounts.
- Apply least-privilege and alert on out-of-window IAM privilege changes.
- Run a post-incident review; if account takeover is confirmed, verify no persistence (added keys, OAuth grants, mail-forwarding rules) remains.
