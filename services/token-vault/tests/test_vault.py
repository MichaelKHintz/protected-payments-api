import sqlite3

import pytest
from cryptography.exceptions import InvalidTag

from app.crypto import EnvelopeCipher, SealedPan

VISA = "4111 1111 1111 1111"


def test_tokenize_returns_random_token_and_last4(as_payments_api):
    r = as_payments_api.post("/v1/tokenize", json={"pan": VISA})
    assert r.status_code == 201
    body = r.json()
    assert body["token"].startswith("tok_") and body["last4"] == "1111" and body["brand"] == "visa"
    assert body["duplicate"] is False
    assert "4111111111111111" not in r.text


def test_same_card_is_detected_as_duplicate_via_hmac(as_payments_api):
    first = as_payments_api.post("/v1/tokenize", json={"pan": VISA}).json()
    second = as_payments_api.post("/v1/tokenize", json={"pan": "4111-1111-1111-1111"})
    assert second.status_code == 200
    assert second.json()["duplicate"] is True and second.json()["token"] == first["token"]


def test_database_file_never_contains_the_pan(app, as_payments_api):
    as_payments_api.post("/v1/tokenize", json={"pan": VISA})
    for suffix in ("", "-wal"):
        try:
            raw = open(app.state.db_path + suffix, "rb").read()
        except FileNotFoundError:
            continue
        assert b"4111111111111111" not in raw


def test_real_looking_card_is_refused_and_not_echoed(as_payments_api):
    # Luhn-valid but not on the published test-card list.
    r = as_payments_api.post("/v1/tokenize", json={"pan": "4000000000000002"})
    assert r.status_code == 422
    assert "4000000000000002" not in r.text


def test_validation_errors_do_not_echo_input(as_payments_api):
    r = as_payments_api.post("/v1/tokenize", json={"pan": "4111111111111111111111111"})
    assert r.status_code == 422
    assert "4111111111111111" not in r.text


def test_round_trip_through_detokenize(as_payments_api, as_settlement):
    token = as_payments_api.post("/v1/tokenize", json={"pan": VISA}).json()["token"]
    r = as_settlement.post("/v1/detokenize", json={"token": token})
    assert r.status_code == 200 and r.json()["pan"] == "4111111111111111"


def test_ciphertext_moved_to_another_record_fails_to_decrypt(app, kms, as_payments_api):
    """The encryption context and AES-GCM associated data bind each ciphertext to its token."""
    a = as_payments_api.post("/v1/tokenize", json={"pan": VISA}).json()["token"]
    b = as_payments_api.post("/v1/tokenize", json={"pan": "5555555555554444"}).json()["token"]
    db = sqlite3.connect(app.state.db_path)
    row_a = db.execute(
        "SELECT ciphertext, nonce, encrypted_data_key, kms_key_arn FROM vault WHERE token=?", (a,)
    ).fetchone()
    db.close()
    cipher = EnvelopeCipher(kms, row_a[3])
    with pytest.raises((InvalidTag, kms.exceptions.InvalidCiphertextException)):
        cipher.open(b, SealedPan(*row_a))
