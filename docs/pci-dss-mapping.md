# PCI DSS v4.0.1 mapping: Requirements 3 and 4

Scope note: this is a lab with test card numbers only. "Meets intent" means the lab control
demonstrates the requirement's technical intent; it is not a compliance claim.

## Requirement 3: Protect stored account data

| Req | What it asks | Lab control | Evidence | Production gap |
| --- | --- | --- | --- | --- |
| 3.2.1 | Keep stored account data to the minimum, with retention limits | payments-api stores token + last 4 only; the vault is the only PAN store | `store.py` schemas | Retention and secure-deletion policy for vault records |
| 3.3.1.2 | Don't store the card verification code after authorization | The API has no CVV field; the redactor strips CVV from notes before storage | `test_redact.py` | Same control on every intake channel (chat, email, call recordings) |
| 3.4.1 | Mask PAN when displayed (BIN and last 4 at most) | Responses show last 4 and a token only | API responses | Role-based unmasking with approvals |
| 3.5.1 | Render PAN unreadable wherever stored | Index tokens (payments-api); AES-256-GCM with KMS-wrapped data keys (vault) | DB dump with no PAN | Same for backups, replicas, logs |
| 3.5.1.1 | Hashes of PAN must be keyed cryptographic hashes | HMAC-SHA256 computed inside KMS; key never leaves KMS | `crypto.py`, key policy | HMAC key rotation procedure |
| 3.5.1.2 | Disk-level encryption alone isn't enough | EBS encryption is in addition to application-level encryption | `node.tf` | n/a |
| 3.6.1 | Protect keys: fewest custodians, KEKs at least as strong as DEKs, stored separately | KMS key (KEK) in KMS; data keys stored only wrapped; key policy names one admin and one user | `kms.tf` | Named custodians and access reviews |
| 3.6.1.1 | Service providers document the cryptographic architecture | `docs/kms-key-management.md` | doc | Full inventory incl. algorithms, protocols, expiry |
| 3.6.1.2 | Secret keys stored encrypted with a KEK, in an HSM, or as key components | Data keys wrapped by a KMS key held in KMS HSMs | `crypto.py` | Single-tenant HSM if policy requires it |
| 3.7.1-3.7.3 | Strong key generation, secure distribution and storage | KMS `GenerateDataKey`; keys never leave KMS unwrapped except in vault memory | code | Formal procedures |
| 3.7.4 | Change keys at the end of their cryptoperiod | Automatic KMS rotation (365 days); one data key per record | rotation status | Documented cryptoperiods; re-wrap with `ReEncrypt` |
| 3.7.5 | Retire or replace keys when integrity is weakened | Alias swap + re-encryption runbook (not exercised) | doc | Tested compromise runbook |
| 3.7.6 | Split knowledge and dual control for manual cleartext key operations | No manual cleartext key operations exist in KMS | design | Dual control for policy changes and key deletion |
| 3.7.7 | Prevent unauthorized key substitution | Key policy limits `PutKeyPolicy`; the app pins the key ARN on decrypt | `kms.tf`, `crypto.py` | Alerting on `PutKeyPolicy`, SCP guardrail |
| 3.7.8 | Custodians formally acknowledge responsibilities | Not in lab | n/a | Signed custodian acknowledgments |

## Requirement 4: Protect cardholder data with strong cryptography during transmission

Requirement 4 applies to open, public networks. The lab also encrypts internal hops (mTLS), which goes
beyond Requirement 4 and supports the segmentation story.

| Req | What it asks | Lab control | Evidence | Production gap |
| --- | --- | --- | --- | --- |
| 4.2.1 | Strong cryptography for PAN over public networks; only trusted keys and certificates; certificates valid and not expired or revoked | payments-api serves HTTPS; payments-api to vault is TLS 1.3 mTLS from a private CA; KMS calls use AWS TLS endpoints | test output | Public ingress with a publicly trusted certificate; revocation checking |
| 4.2.1.1 | Keep an inventory of trusted keys and certificates | `k8s/base/certificates.yaml` and `k8s/platform/pki.yaml` are the inventory | manifests | Automated inventory with expiry alerts |
| 4.2.2 | Secure PAN sent through end-user messaging | Card numbers in support notes are tokenized; nothing card-shaped reaches the LLM | `test_llm_gateway.py` | DLP on email and chat channels |

## What a real deployment would still need

<!-- Expand each item into 1-2 sentences in your own words -->

- HSM decisions: KMS keys already live in FIPS 140-3 Level 3 validated HSMs, but they are multi-tenant and AWS-operated. Some programs require a single-tenant HSM (CloudHSM, or a KMS custom key store backed by it) or AWS Payment Cryptography for card-specific operations.
- Key custody procedures: named custodians, acknowledgments, access reviews, a dual-control path for key-policy changes and deletion.
- CDE segmentation: the vault in its own account, VPC, and cluster (or node pool), with segmentation testing.
- Workload identity with no static keys, and KMS through a VPC endpoint with `aws:SourceVpce` conditions.
- Centralized logging (Requirement 10): CloudTrail data events for KMS, alerts on unusual `Decrypt` volume.
- Edge tokenization (hosted fields) so the merchant backend never receives a PAN at all.
- The LLM vendor managed as a third-party service provider (Requirement 12.8), even though no account data is sent.
