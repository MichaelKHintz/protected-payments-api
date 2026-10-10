# Protected Payments API with an LLM Gateway

A payments-style API that never stores a card number: cards are swapped for random tokens by a vault that
encrypts them with AWS KMS envelope encryption. Services trust each other through mTLS from a private CA,
callers authenticate with Okta-issued OAuth tokens, and a support-summary endpoint redacts card and personal
data before anything is sent to the Claude API. Controls are mapped to PCI DSS v4.0.1 Requirements 3 and 4.

> **Test data only.** The vault refuses every card number except published test numbers such as
> 4111 1111 1111 1111, and a pre-commit hook blocks any other card-shaped number from being committed.

## Architecture

```
 caller (curl)                         k3s on EC2 (no inbound ports, reached via SSM)
 ─────────────                         ─────────────────────────────────────────────────────────────
 Okta client credentials ──token──▶  payments-api ──mTLS (private CA)──▶ token-vault ──▶ AWS KMS
   (custom auth server)               │  OAuth: iss, aud, exp, scopes       │  identity allowlist   (data key + HMAC key)
                                      │  stores tokens + last 4 only        │  AES-256-GCM, SQLite
                                      └──redacted text only──▶ Claude API
```

<!-- Replace with a diagram image in docs/ once the lab is running -->

## What each control does

| Layer | Control | Where |
| --- | --- | --- |
| Data at rest | Tokenization; envelope encryption (KMS data key per card, AES-256-GCM); keyed HMAC-SHA256 for duplicates | `services/token-vault/app/crypto.py` |
| Key management | Least-privilege key policies, separation of duties (admins can't decrypt), source-IP condition, automatic rotation | `infra/terraform/kms.tf` |
| Service-to-service | mTLS (TLS 1.3) through a cert-manager private CA; vault authorizes by certificate URI SAN | `services/token-vault/app/serve.py`, `k8s/platform/pki.yaml` |
| API access | OAuth 2.0 client credentials (Okta); issuer, audience, expiry, signature, and per-endpoint scopes | `services/payments-api/app/auth.py` |
| LLM gateway | Card numbers tokenized, PII redacted, fail-closed check, metadata-only audit log, key as a mounted Secret | `services/payments-api/app/redact.py`, `main.py` |
| Platform | PSA restricted, default-deny NetworkPolicies, Kyverno signed-image and registry policies, Secrets encrypted at rest | `k8s/` |
| Supply chain | Gitleaks, Semgrep, Checkov, Trivy, Syft SBOM, keyless cosign signing, SHA-pinned actions | `.github/workflows/build.yml` |

## Evidence

<!-- Link sanitized test output and screenshots in docs/evidence/ -->

## Workload credentials: the design problem

<!-- Summarize docs/credentials-design.md -->

## Shared responsibility when sending data to an LLM API

<!-- Your comparison table: Anthropic API vs OpenAI API / ChatGPT Enterprise vs Amazon Bedrock -->

## PCI DSS mapping

See [docs/pci-dss-mapping.md](docs/pci-dss-mapping.md).

## Run it yourself

See the build guide phases: Terraform in `infra/terraform`, manifests in `k8s/`, helper scripts in `scripts/`.
