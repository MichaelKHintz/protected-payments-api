"""Phase 2: every way a token can be wrong should fail, and fail for the right reason."""
import pytest

from conftest import OTHER_KEY, PAYMENT_BODY, bearer, forge, mint

URL = "/v1/payments"


def test_valid_token_with_scope_is_accepted(client):
    assert client.post(URL, json=PAYMENT_BODY, headers=bearer("payments:write")).status_code == 201


def test_missing_token_is_401(client):
    r = client.post(URL, json=PAYMENT_BODY)
    assert r.status_code == 401 and r.headers["www-authenticate"].startswith("Bearer")


def test_expired_token_is_401(client):
    r = client.post(URL, json=PAYMENT_BODY, headers=bearer("payments:write", expires_in=-120))
    assert r.status_code == 401 and r.json()["detail"] == "token expired"


def test_wrong_audience_is_401(client):
    r = client.post(URL, json=PAYMENT_BODY, headers=bearer("payments:write", aud="api://some-other-api"))
    assert r.status_code == 401 and r.json()["detail"] == "wrong audience"


def test_wrong_issuer_is_401(client):
    r = client.post(URL, json=PAYMENT_BODY, headers=bearer("payments:write", iss="https://evil.example/oauth2/x"))
    assert r.status_code == 401 and r.json()["detail"] == "wrong issuer"


def test_missing_scope_is_403(client):
    r = client.post(URL, json=PAYMENT_BODY, headers=bearer("payments:read"))
    assert r.status_code == 403 and "insufficient_scope" in r.headers["www-authenticate"]


def test_token_signed_by_another_key_is_401(client):
    r = client.post(URL, json=PAYMENT_BODY, headers={"Authorization": f"Bearer {mint(['payments:write'], key=OTHER_KEY)}"})
    assert r.status_code == 401


def test_unknown_key_id_is_401(client):
    r = client.post(URL, json=PAYMENT_BODY, headers={"Authorization": f"Bearer {mint(['payments:write'], kid='rogue')}"})
    assert r.status_code == 401


@pytest.mark.parametrize("alg", ["none", "HS256"])
def test_algorithm_confusion_attacks_are_401(client, alg):
    r = client.post(URL, json=PAYMENT_BODY, headers={"Authorization": f"Bearer {forge(alg)}"})
    assert r.status_code == 401
