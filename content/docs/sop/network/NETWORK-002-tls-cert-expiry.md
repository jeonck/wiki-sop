---
sop_id: NETWORK-002
title: TLS Certificate Expiry on Public Endpoint
target_system:
  - ingress-nginx.ingress
  - api.example.com
  - cert-manager.cert-manager
category: NETWORK
severity: P2
symptoms:
  - "curl: (60) SSL certificate problem: certificate has expired"
  - "x509: certificate has expired or is not yet valid"
  - "probe_ssl_earliest_cert_expiry - time() < 604800 (blackbox exporter, < 7 days)"
  - "Browser NET::ERR_CERT_DATE_INVALID reported by users"
verification_metrics:
  - metric: cert_days_until_expiry
    threshold: "> 30"
    unit: "days"
  - metric: tls_handshake_success_ratio
    threshold: ">= 99.9"
    unit: "%"
  - metric: certmanager_certificate_ready
    threshold: "== 1"
    unit: "bool"
escalation:
  l1: "Network On-Call (PagerDuty: network-oncall)"
  l2: "Security/PKI Team + Certificate Authority (ACME/DigiCert) support"
related_sops:
  - NETWORK-003
  - SECURITY-001
version: 1.0
owner: Network SRE
updated: "2026-07-08"
tags:
  - tls
  - certificate
  - cert-manager
  - p2
---

## 1. Situation

A public-facing endpoint is serving an expired (or soon-to-expire) TLS
certificate, causing clients to reject the connection. This breaks HTTPS for
end users and API consumers. Handle proactively as P2 when expiry is within
7 days, and treat an already-expired production cert with P2 urgency due to
active user impact.

## 2. Symptoms

- `curl` reports `certificate has expired` (error 60).
- Go/Java clients log `x509: certificate has expired or is not yet valid`.
- Blackbox exporter shows `probe_ssl_earliest_cert_expiry` within 7 days of now.
- Users report browser `NET::ERR_CERT_DATE_INVALID`.

## 3. Diagnosis

Inspect the certificate actually served on the wire and confirm its
`notAfter` date and chain.

```bash
# Show the served leaf certificate's validity window
echo | openssl s_client -servername api.example.com -connect api.example.com:443 2>/dev/null \
  | openssl x509 -noout -subject -issuer -dates

# One-line expiry check
echo | openssl s_client -servername api.example.com -connect api.example.com:443 2>/dev/null \
  | openssl x509 -noout -enddate

# In-cluster: inspect the cert-manager Certificate resource and its status
kubectl -n ingress get certificate api-example-com -o wide
kubectl -n ingress describe certificate api-example-com | sed -n '/Status/,$p'

# Check the secret the ingress mounts
kubectl -n ingress get secret api-example-com-tls -o jsonpath='{.data.tls\.crt}' \
  | base64 -d | openssl x509 -noout -enddate
```

## 4. Action (Step-by-Step)

1. Confirm the served `notAfter` date with `openssl s_client` — verify it is genuinely expired vs. a stale client trust store.
2. Verify the served cert matches the secret referenced by the ingress; a mismatch means the ingress cached an old cert (restart ingress controller pods to reload).
3. If cert-manager manages the cert, check `Certificate` status: `kubectl -n ingress describe certificate <name>` and look for `Ready=False` and the failure reason.
4. If renewal is stuck, delete the `CertificateRequest`/`Order` to force reissue: `kubectl -n ingress delete certificaterequest <name>` (cert-manager recreates it).
5. Validate the ACME challenge path is reachable (HTTP-01 `/.well-known/acme-challenge/` returns 200 through the ingress); fix routing if DNS-01/HTTP-01 is failing.
6. For manually managed certs, install the renewed cert/key into the TLS secret: `kubectl -n ingress create secret tls <name> --cert=fullchain.pem --key=key.pem --dry-run=client -o yaml | kubectl apply -f -`.
7. Reload/restart the ingress controller so the new cert is served, then re-run the `openssl s_client` check.

## 5. Verification

- [ ] `cert_days_until_expiry` greater than 30 days
- [ ] `tls_handshake_success_ratio` at or above 99.9%
- [ ] `certmanager_certificate_ready` equals 1 (Ready=True)
- [ ] `curl https://api.example.com` completes with no certificate error

## 6. Escalation

- **L1:** Network On-Call (PagerDuty: `network-oncall`).
- **L2:** Security/PKI Team; if issuance is blocked at the CA (ACME rate limits,
  DigiCert validation hold), open a support ticket with the CA.

## 7. Prevention / Follow-up

- Alert at 30/14/7-day thresholds on `probe_ssl_earliest_cert_expiry`.
- Automate renewal with cert-manager and monitor `Certificate` `Ready` status.
- Add a synthetic HTTPS probe per public endpoint via blackbox exporter.
- Audit ACME rate-limit headroom before bulk certificate rotations.
- If the expired cert also affected load balancer health checks, see NETWORK-003.
