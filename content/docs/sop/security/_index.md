---
title: Security
weight: 5
---

This category covers defensive detection, containment, and response for identity- and credential-focused security incidents: leaked credentials, automated brute-force / credential-stuffing login attempts, and suspicious account access such as impossible-travel logins or anomalous data reads. Each runbook is written for an authorized internal on-call team and prioritizes revoking access, blocking attacker traffic, and preserving evidence. Response speed is critical here because an exposed credential or an active takeover can be leveraged within minutes, so containment begins in parallel with investigation.

## SOPs in this category

| SOP | Severity | When to use |
| --- | --- | --- |
| [SECURITY-001](security-001-leaked-credential) | P1 | A live credential (access key, token, or key) is exposed outside its trust boundary — committed to a repo, posted publicly, or leaked via logs — and must be revoked and rotated. |
| [SECURITY-002](security-002-brute-force-login) | P2 | An automated attacker is brute-forcing or credential-stuffing your login/token endpoints and the attack traffic must be throttled, blocked, and checked for any successful compromise. |
| [SECURITY-003](security-003-suspicious-access) | P2 | An account shows possible-takeover behavior — new geo/device, out-of-window privilege changes, or bulk data access above baseline — and needs rapid legitimacy triage and containment. |

## Common signals

- Secret-scanning or pre-receive hook (push protection, trufflehog, git-secrets) flags a high-entropy token committed to a repository.
- A credential is used from an unexpected IP, ASN, or geography versus its normal scope (e.g. CloudTrail calls on a CI-only key from an unrecognized source).
- Sustained failed-login spike, such as >100 failed logins/min from a single IP or /24 against the auth endpoint.
- High failed-to-successful auth ratio (>20:1) across many distinct usernames from few IPs — a credential-stuffing signature.
- Impossible-travel login: the same user authenticating from geographically distant IPs within a window that precludes physical travel.
- Successful login from a new device, ASN, or country never previously seen for that user.
- Privilege-escalation or IAM changes (policy attach, access-key creation) occurring outside change-management hours.
- SIEM / audit-log anomaly: a session performing bulk data reads (object gets, drive exports) far above the identity's 30-day baseline.

## Escalation & agent use

Each SOP declares its own L1/L2 escalation path — L1 is typically security-oncall via the PagerDuty SEC-ONCALL service, with L2 pulling in the Incident Commander, CISO, IAM platform team, or data-protection officer depending on the incident. Consult the individual runbook for its exact acknowledgement window and L2 conditions. The AIOps agent matches incoming logs and alerts against these SOPs' `symptoms` and produces a concise five-line report citing the matching `sop_id`, so responders can jump straight to the relevant runbook.
