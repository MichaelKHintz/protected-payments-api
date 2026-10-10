from conftest import PAYMENT_BODY as PAYMENT


def test_create_payment_stores_token_not_pan(client, tmp_path):
    r = client.post("/v1/payments", json=PAYMENT)
    assert r.status_code == 201
    body = r.json()
    assert body["card_token"].startswith("tok_") and body["last4"] == "1111"
    assert "4111111111111111" not in r.text
    for suffix in ("", "-wal"):
        path = tmp_path / f"payments.db{suffix}"
        if path.exists():
            assert b"4111111111111111" not in path.read_bytes()


def test_non_test_card_is_rejected_without_echo(client):
    r = client.post("/v1/payments", json={**PAYMENT, "card_number": "4000000000000002"})
    assert r.status_code == 422 and "4000000000000002" not in r.text


def test_validation_error_does_not_echo_card(client):
    r = client.post("/v1/payments", json={**PAYMENT, "amount_cents": -1})
    assert r.status_code == 422 and "4111" not in r.text
