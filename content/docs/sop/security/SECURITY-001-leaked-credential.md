---
sop_id: SECURITY-001
title: Leaked Credential Exposure Response
target_system:
  - GitHub Enterprise
  - AWS IAM
  - HashiCorp Vault
  - Okta
category: SECURITY
severity: P1
symptoms:
  - "GitHub secret scanning alert: 'Push protection bypassed' or 'New secret detected' for aws_access_key_id / AKIA[0-9A-Z]{16}"
  - "CloudTrail shows API calls from an unrecognized IP/ASN using an access key normally scoped to CI runners"
  - "Vault audit log contains 'permission denied' spikes followed by a successful auth with a static token flagged in a public gist/paste"
  - "git-secrets / trufflehog pre-receive hook reports a high-entropy string committed to a public or forkable repository"
verification_metrics:
  - metric: exposed_credential_active_sessions
    threshold: "0"
    unit: sessions
  - metric: unauthorized_api_calls_post_rotation
    threshold: "0"
    unit: calls/5m
  - metric: credential_rotation_completion
    threshold: "100"
    unit: percent
escalation:
  l1: security-oncall (PagerDuty service SEC-ONCALL, ack within 15m)
  l2: CISO + Incident Commander bridge; legal/compliance if customer data or PII keys are involved
related_sops:
  - SECURITY-003
  - INFRA-002
version: 1.0
owner: security-oncall
updated: "2026-07-08"
tags:
  - credentials
  - secrets
  - rotation
  - p1
---

## 1. Situation

A live credential (AWS access key, service-account token, API key, or private key) has been exposed outside its trust boundary — committed to a repository, posted publicly, or leaked via logs. Treat any exposed credential as compromised. The goal is to revoke access before an attacker uses it, then rotate cleanly. This is a P1: begin containment immediately, in parallel with investigation.

## 2. Symptoms

- GitHub secret scanning or push-protection alert firing on a high-entropy token.
- CloudTrail / audit logs showing use of the credential from an unexpected IP, ASN, or geography.
- A `trufflehog` / `git-secrets` finding on a public or widely-forked repo.
- Vault or Okta audit spikes correlated with a token that appears in an external paste.

## 3. Diagnosis

Confirm the exposure and whether the credential has been used by an unauthorized party.

```bash
# 1. Identify the exposed key and where it lives in git history
trufflehog git file://./repo --only-verified --json | jq '.DetectorName, .Raw'

# 2. Check whether the AWS key has been used, and from where (last 24h)
aws cloudtrail lookup-events \
  --lookup-attributes AttributeKey=AccessKeyId,AttributeValue=AKIAEXAMPLE123456 \
  --start-time "$(date -u -v-24H '+%Y-%m-%dT%H:%M:%SZ')" \
  --query 'Events[].{time:EventTime,ip:CloudTrailEvent}' --output json \
  | jq -r '.[] | "\(.time) \(.ip | fromjson | .sourceIPAddress) \(.ip | fromjson | .eventName)"'

# 3. Cross-check source IPs against known CI/office CIDRs (anything else = suspicious)
```

## 4. Action (Step-by-Step)

1. Declare the incident in `#sec-incident` and page `security-oncall`; assign a scribe.
2. **Revoke first, investigate second.** Deactivate the exposed AWS key: `aws iam update-access-key --access-key-id AKIA... --status Inactive`.
3. Revoke all active sessions issued from the credential (STS: attach a deny policy with an `aws:TokenIssueTime` condition; Okta/Vault: revoke the token and its leases).
4. Rotate the credential: generate a replacement, distribute via Vault/secrets manager, and update consuming services/CI variables. Never re-use the old secret value.
5. Delete the exposed key entirely once the replacement is confirmed working (`--access-key-id ... delete-access-key`).
6. Purge the secret from git history if committed (BFG / `git filter-repo`) and force-rotate — history rewrite alone does NOT un-leak; rotation is mandatory.
7. Scope the blast radius: enumerate every resource the credential could reach and review CloudTrail for anomalous actions during the exposure window.
8. If unauthorized use is confirmed, escalate to L2 and follow SECURITY-003 for the accessed resources.

## 5. Verification

- [ ] exposed_credential_active_sessions == 0 sessions
- [ ] unauthorized_api_calls_post_rotation == 0 calls/5m (monitored 30m after rotation)
- [ ] credential_rotation_completion == 100 percent (all consumers on new secret)
- [ ] Old key deleted (not just disabled) and absent from all secret stores

## 6. Escalation

- **L1:** security-oncall (PagerDuty SEC-ONCALL, ack within 15m).
- **L2:** CISO + Incident Commander bridge; involve legal/compliance if PII or customer-data keys were exposed, and notify the affected credential owner's team lead.

## 7. Prevention / Follow-up

- Enforce GitHub push protection and pre-receive `trufflehog`/`git-secrets` hooks org-wide.
- Prefer short-lived, dynamically-issued credentials (Vault dynamic secrets, OIDC-federated CI) over long-lived static keys.
- Add a detective control: alert on any static key used outside approved CIDRs.
- File a post-incident review within 48h; track exposure-to-revocation time as a KPI.
