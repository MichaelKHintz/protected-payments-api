import base64
import hashlib
import hmac
import json
import time
from types import SimpleNamespace

import httpx
import jwt
import pytest
from cryptography.hazmat.primitives import serialization
from cryptography.hazmat.primitives.asymmetric import rsa
from fastapi.testclient import TestClient

from app.auth import TokenValidator
from app.config import Settings
from app.llm import Summary
from app.main import create_app
from app.vault_client import VaultClient

ISSUER = "https://example.okta.com/oauth2/aus-test"
AUDIENCE = "api://payments-lab"
SIGNING_KEY = rsa.generate_private_key(public_exponent=65537, key_size=2048)
OTHER_KEY = rsa.generate_private_key(public_exponent=65537, key_size=2048)
TEST_CARDS = {"4111111111111111", "5555555555554444", "378282246310005"}
PAYMENT_BODY = {"card_number": "4111 1111 1111 1111", "amount_cents": 4200, "currency": "USD", "merchant_ref": "order-1001"}


def mint(scopes=(), *, aud=AUDIENCE, iss=ISSUER, expires_in=300, key=SIGNING_KEY, kid="test-kid",
         client_id="0oa-checkout-test"):
    now = int(time.time())
    claims = {"iss": iss, "aud": aud, "sub": client_id, "cid": client_id, "iat": now, "exp": now + expires_in,
              "scp": list(scopes)}
    return jwt.encode(claims, key, algorithm="RS256", headers={"kid": kid})


def forge(alg: str) -> str:
    """Build tokens for classic JWT attacks: alg=none, and HS256 signed with the public key as the secret."""
    def b64(data: bytes) -> str:
        return base64.urlsafe_b64encode(data).rstrip(b"=").decode()
    now = int(time.time())
    header = b64(json.dumps({"alg": alg, "kid": "test-kid", "typ": "JWT"}).encode())
    payload = b64(json.dumps({"iss": ISSUER, "aud": AUDIENCE, "sub": "x", "iat": now, "exp": now + 300,
                              "scp": ["payments:write", "payments:read", "support:summarize"]}).encode())
    signing_input = f"{header}.{payload}".encode()
    if alg == "none":
        return f"{header}.{payload}."
    public_pem = SIGNING_KEY.public_key().public_bytes(serialization.Encoding.PEM,
                                                       serialization.PublicFormat.SubjectPublicKeyInfo)
    return f"{header}.{payload}.{b64(hmac.new(public_pem, signing_input, hashlib.sha256).digest())}"


class FakeJWKS:
    def get_signing_key_from_jwt(self, token):
        if jwt.get_unverified_header(token).get("kid") != "test-kid":
            raise jwt.PyJWKClientError("unknown key id")
        return SimpleNamespace(key=SIGNING_KEY.public_key())


def fake_vault() -> VaultClient:
    tokens: dict[str, str] = {}

    def handler(request: httpx.Request) -> httpx.Response:
        pan = json.loads(request.content)["pan"].replace(" ", "").replace("-", "")
        if pan not in TEST_CARDS:
            return httpx.Response(422, json={"detail": "only published test card numbers are accepted in this lab"})
        token = tokens.setdefault(pan, f"tok_{'T' * (24 - len(pan[-4:]))}{pan[-4:]}")
        return httpx.Response(201, json={"token": token, "last4": pan[-4:], "brand": "visa", "duplicate": False})

    return VaultClient("http://token-vault.test", transport=httpx.MockTransport(handler))


class FakeSummarizer:
    def __init__(self, reply="Customer reports a duplicate charge and wants a refund. Next step: verify and refund."):
        self.reply = reply
        self.prompts: list[str] = []

    def summarize(self, redacted_notes: str) -> Summary:
        self.prompts.append(redacted_notes)
        return Summary(text=self.reply, model="claude-haiku-5-5", input_tokens=42, output_tokens=17,
                       provider_request_id="req_test")


@pytest.fixture
def summarizer():
    return FakeSummarizer()


@pytest.fixture
def client(tmp_path, summarizer):
    settings = Settings(db_path=str(tmp_path / "payments.db"), oauth_issuer=ISSUER, oauth_audience=AUDIENCE)
    validator = TokenValidator(ISSUER, AUDIENCE, jwks_client=FakeJWKS())
    app = create_app(settings, vault=fake_vault(), validator=validator, summarizer=summarizer)
    return TestClient(app)


def bearer(*scopes, **kwargs) -> dict:
    return {"Authorization": f"Bearer {mint(scopes, **kwargs)}"}
