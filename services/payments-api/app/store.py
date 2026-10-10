"""SQLite storage for payments-api. Holds vault tokens and last-4 digits only; never a full card number."""
import sqlite3
import uuid
from contextlib import contextmanager
from datetime import datetime, timezone

SCHEMA = """
CREATE TABLE IF NOT EXISTS payments (
    id           TEXT PRIMARY KEY,
    card_token   TEXT NOT NULL,
    last4        TEXT NOT NULL,
    brand        TEXT NOT NULL,
    amount_cents INTEGER NOT NULL,
    currency     TEXT NOT NULL,
    merchant_ref TEXT NOT NULL,
    status       TEXT NOT NULL,
    created_by   TEXT NOT NULL,
    created_at   TEXT NOT NULL
);
CREATE TABLE IF NOT EXISTS notes (
    id            INTEGER PRIMARY KEY AUTOINCREMENT,
    payment_id    TEXT NOT NULL REFERENCES payments(id),
    text_redacted TEXT NOT NULL,
    created_by    TEXT NOT NULL,
    created_at    TEXT NOT NULL
);
"""

PAYMENT_COLUMNS = ("id", "card_token", "last4", "brand", "amount_cents", "currency", "merchant_ref", "status",
                   "created_by", "created_at")
INSERT_PAYMENT = "INSERT INTO payments VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?)"
SELECT_PAYMENT = ("SELECT id, card_token, last4, brand, amount_cents, currency, merchant_ref, status, created_by, "
                  "created_at FROM payments WHERE id = ?")


def _now() -> str:
    return datetime.now(timezone.utc).isoformat()


class PaymentStore:
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

    def create_payment(self, card_token: str, last4: str, brand: str, amount_cents: int, currency: str,
                       merchant_ref: str, created_by: str) -> dict:
        row = (f"pay_{uuid.uuid4().hex[:20]}", card_token, last4, brand, amount_cents, currency, merchant_ref,
               "authorized", created_by, _now())
        with self._connect() as db:
            db.execute(INSERT_PAYMENT, row)
        return dict(zip(PAYMENT_COLUMNS, row))

    def get_payment(self, payment_id: str) -> dict | None:
        with self._connect() as db:
            row = db.execute(SELECT_PAYMENT, (payment_id,)).fetchone()
        return dict(zip(PAYMENT_COLUMNS, row)) if row else None

    def add_note(self, payment_id: str, text_redacted: str, created_by: str) -> None:
        with self._connect() as db:
            db.execute(
                "INSERT INTO notes (payment_id, text_redacted, created_by, created_at) VALUES (?, ?, ?, ?)",
                (payment_id, text_redacted, created_by, _now()),
            )

    def list_notes(self, payment_id: str) -> list[str]:
        with self._connect() as db:
            rows = db.execute("SELECT text_redacted FROM notes WHERE payment_id = ? ORDER BY id", (payment_id,)).fetchall()
        return [r[0] for r in rows]
