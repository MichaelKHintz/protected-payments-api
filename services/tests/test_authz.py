"""Phase 2: the vault decides what each caller may do from its certificate identity."""


def test_tokenize_requires_an_allowed_identity(anonymous):
    r = anonymous.post("/v1/tokenize", json={"pan": "4111111111111111"})
    assert r.status_code == 403


def test_payments_api_can_tokenize_but_not_detokenize(as_payments_api):
    token = as_payments_api.post("/v1/tokenize", json={"pan": "4111111111111111"}).json()["token"]
    r = as_payments_api.post("/v1/detokenize", json={"token": token})
    assert r.status_code == 403
    assert "4111" not in r.text


def test_settlement_can_detokenize_but_not_tokenize(as_settlement):
    r = as_settlement.post("/v1/tokenize", json={"pan": "4111111111111111"})
    assert r.status_code == 403
