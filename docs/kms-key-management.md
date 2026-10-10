# KMS key management

## Keys

| Key | Spec | Used for | Who can use it | Who can manage it | Rotation |
| --- | --- | --- | --- | --- | --- |
| `alias/payments-lab-vault` | SYMMETRIC_DEFAULT (AES-256) | Wrapping one data key per card (envelope encryption) | token-vault principal only, with encryption context `app=token-vault` and only from the node's egress IP | Terraform admin role (cannot encrypt or decrypt) | Automatic, every 365 days |
| `alias/payments-lab-pan-hmac` | HMAC_256 | HMAC-SHA256 fingerprints for duplicate detection | token-vault principal only, `HMAC_SHA_256`, node IP only | Terraform admin role | Manual only (KMS can't auto-rotate HMAC keys) |

## How envelope encryption works here

1. The vault calls `GenerateDataKey` with encryption context `{"app": "token-vault", "token": "<token>"}`.
2. KMS returns the data key twice: plaintext, and encrypted under the KMS key.
3. The vault encrypts the PAN locally with AES-256-GCM (random 96-bit nonce, token as associated data), then discards the plaintext key.
4. It stores ciphertext, nonce, and the *encrypted* data key. Reading a card requires a `Decrypt` call with the same encryption context, which CloudTrail records.

## What automatic rotation does (and doesn't do)

<!-- Verify against https://docs.aws.amazon.com/kms/latest/developerguide/rotate-keys.html and note the date -->

- New key material is generated on the rotation schedule (365 days by default; configurable).
- The key ID, ARN, alias, and key policy stay the same, so the application needs no change.
- KMS keeps every previous version of the key material, and `Decrypt` picks the right one automatically.
- Rotation does **not** re-encrypt existing data and does **not** rotate data keys already issued.
  Old cards stay wrapped under old key material until they are re-wrapped with `ReEncrypt`.
- Rotation does not help if a *data key* was exposed; that requires re-encrypting the affected records.
- Billing: the first and second rotations each add a monthly key-storage charge; later rotations don't.

Observed in this lab: <!-- paste `aws kms get-key-rotation-status` output (account ID redacted) -->

## Rotating the HMAC key (manual)

Changing the HMAC key changes every fingerprint, so duplicates would go undetected. A real rotation:
create a new HMAC key, decrypt each card once and write a second fingerprint column under the new key,
switch lookups to the new column, then retire the old key.

## Separation of duties

The admin role can change the key policy, so it could grant itself `Decrypt`. That is a procedural
control, not a technical one. Production would add a detective control (alert on `PutKeyPolicy`) and a
preventive one (an SCP that limits `kms:PutKeyPolicy` to a break-glass role used with two-person approval).
