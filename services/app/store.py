"""SQLite storage for the vault. Holds tokens, ciphertext, wrapped data keys, and HMAC fingerprints; never a PAN."""
import sqlite3
from contextlib import contextmanager
from dataclasses import dataclass
from datetime import datetime, timezone

from app.crypto import SealedPan

SCHEMA = """
CREATE TABLE IF NOT EXISTS vault (
    token              TEXT PRIMARY KEY,
    pan_fingerprint    TEXT NOT NULL UNIQUE,  -- HMAC-SHA256 from KMS, used to detect duplicates
    ciphertext         BLOB NOT NULL,
    nonce              BLOB NOT NULL,
    encrypted_data_key BLOB NOT NULL,
    kms_key_arn        TEXT NOT NULL,
    last4              TEXT NOT NULL,
    brand              TEXT NOT NULL,
    created_at         TEXT NOT NULL
);
"""


@dataclass(frozen=True)
class VaultRecord:
    token: str
    last4: str
    brand: str
    sealed: SealedPan


class VaultStore:
    def __init__(self, path: str):
        self._path = path
        with self._connect() as db:
            db.execute("PRAGMA journal_mode=WAL")
            db.executescript(SCHEMA)

    @contextmanager
    def _connect(self):
        db = sqlite3.connect(self._path, timeout=5)
        try:
            yield db
            db.commit()
        finally:
            db.close()

    def find_by_fingerprint(self, fingerprint: str) -> VaultRecord | None:
        with self._connect() as db:
            row = db.execute(
                "SELECT token, last4, brand, ciphertext, nonce, encrypted_data_key, kms_key_arn "
                "FROM vault WHERE pan_fingerprint = ?",
                (fingerprint,),
            ).fetchone()
        return self._record(row)

    def get(self, token: str) -> VaultRecord | None:
        with self._connect() as db:
            row = db.execute(
                "SELECT token, last4, brand, ciphertext, nonce, encrypted_data_key, kms_key_arn "
                "FROM vault WHERE token = ?",
                (token,),
            ).fetchone()
        return self._record(row)

    def insert(self, token: str, fingerprint: str, last4: str, brand: str, sealed: SealedPan) -> None:
        """Raises sqlite3.IntegrityError if the fingerprint already exists (a concurrent duplicate)."""
        with self._connect() as db:
            db.execute(
                "INSERT INTO vault VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?)",
                (
                    token,
                    fingerprint,
                    sealed.ciphertext,
                    sealed.nonce,
                    sealed.encrypted_data_key,
                    sealed.kms_key_arn,
                    last4,
                    brand,
                    datetime.now(timezone.utc).isoformat(),
                ),
            )

    @staticmethod
    def _record(row) -> VaultRecord | None:
        if row is None:
            return None
        token, last4, brand, ciphertext, nonce, edk, arn = row
        return VaultRecord(token, last4, brand, SealedPan(ciphertext, nonce, edk, arn))
