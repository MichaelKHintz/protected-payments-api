"""Envelope encryption (AWS KMS + AES-256-GCM) and keyed PAN fingerprints (KMS HMAC key).

Envelope encryption: KMS generates a fresh 256-bit data key for every card. We encrypt the card
locally with that data key, then keep only the *encrypted* copy of the data key next to the
ciphertext. Reading a card back requires a KMS Decrypt call, which IAM, the key policy, and
CloudTrail all see.
"""
import os
from dataclasses import dataclass

from cryptography.hazmat.primitives.ciphers.aead import AESGCM

ENCRYPTION_CONTEXT_APP = "token-vault"


@dataclass(frozen=True)
class SealedPan:
    ciphertext: bytes          # AES-GCM output, including the 16-byte authentication tag
    nonce: bytes               # 96-bit random nonce, never reused with the same data key
    encrypted_data_key: bytes  # data key encrypted under the KMS key; useless without KMS
    kms_key_arn: str           # which KMS key wrapped the data key


class EnvelopeCipher:
    def __init__(self, kms_client, key_id: str):
        self._kms = kms_client
        self._key_id = key_id

    @staticmethod
    def _context(token: str) -> dict[str, str]:
        # The encryption context binds each wrapped data key to one record: KMS refuses to decrypt
        # it under any other token. It is logged in CloudTrail, so it carries the token, never the PAN.
        return {"app": ENCRYPTION_CONTEXT_APP, "token": token}

    def seal(self, token: str, pan: str) -> SealedPan:
        resp = self._kms.generate_data_key(
            KeyId=self._key_id, KeySpec="AES_256", EncryptionContext=self._context(token)
        )
        data_key = resp["Plaintext"]
        nonce = os.urandom(12)
        # The token is also the AES-GCM associated data, so a ciphertext copied onto another row fails to decrypt.
        ciphertext = AESGCM(data_key).encrypt(nonce, pan.encode(), token.encode())
        del data_key  # drop our reference; Python can't guarantee the bytes are wiped from memory
        return SealedPan(ciphertext, nonce, resp["CiphertextBlob"], resp["KeyId"])

    def open(self, token: str, sealed: SealedPan) -> str:
        resp = self._kms.decrypt(
            CiphertextBlob=sealed.encrypted_data_key,
            KeyId=sealed.kms_key_arn,  # pin the expected key instead of trusting the blob's metadata
            EncryptionContext=self._context(token),
        )
        data_key = resp["Plaintext"]
        pan = AESGCM(data_key).decrypt(sealed.nonce, sealed.ciphertext, token.encode()).decode()
        del data_key
        return pan


class PanFingerprinter:
    """HMAC-SHA256 of the PAN, computed inside KMS so the HMAC key never leaves it.

    A plain SHA-256 of a card number can be brute-forced (known BIN, Luhn digit, small search
    space). A keyed hash can't be reversed without the key, which is why PCI DSS 4.0 requirement
    3.5.1.1 requires keyed cryptographic hashes when PANs are hashed.
    """

    def __init__(self, kms_client, key_id: str):
        self._kms = kms_client
        self._key_id = key_id

    def fingerprint(self, pan: str) -> str:
        resp = self._kms.generate_mac(KeyId=self._key_id, Message=pan.encode(), MacAlgorithm="HMAC_SHA_256")
        return resp["Mac"].hex()
