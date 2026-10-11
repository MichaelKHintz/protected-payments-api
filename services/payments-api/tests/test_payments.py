from conftest import PAYMENT_BODY as PAYMENT, bearer


def test_create_payment_stores_token_not_pan(client, tmp_path):
    r = client.post("/v1/payments", json=PAYMENT, headers=bearer("payments:write"))
    assert r.status_code == 201
    body = r.json()
    assert body["card_token"].startswith("tok_") and body["last4"] == "1111"
    assert "4111111111111111" not in r.text
    for suffix in ("", "-wal"):
        path = tmp_path / f"payments.db{suffix}"
        if path.exists():
            assert b"4111111111111111" not in path.read_bytes()


def test_read_payment_needs_read_scope(client):
    created = client.post("/v1/payments", json=PAYMENT, headers=bearer("payments:write")).json()
    assert client.get(f"/v1/payments/{created['id']}", headers=bearer("payments:write")).status_code == 403
    r = client.get(f"/v1/payments/{created['id']}", headers=bearer("payments:read"))
    assert r.status_code == 200 and r.json()["card_token"] == created["card_token"]


def test_non_test_card_is_rejected_without_echo(client):
    r = client.post("/v1/payments", json={**PAYMENT, "card_number": "4000000000000002"},
                    headers=bearer("payments:write"))
    assert r.status_code == 422 and "4000000000000002" not in r.text


def test_validation_error_does_not_echo_card(client):
    r = client.post("/v1/payments", json={**PAYMENT, "amount_cents": -1}, headers=bearer("payments:write"))
    assert r.status_code == 422 and "4111" not in r.text
