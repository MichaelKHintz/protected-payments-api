import json

import httpx
import pytest
from fastapi.testclient import TestClient

from app.config import Settings
from app.main import create_app
from app.vault_client import VaultClient

TEST_CARDS = {"4111111111111111", "5555555555554444", "378282246310005"}
PAYMENT_BODY = {"card_number": "4111 1111 1111 1111", "amount_cents": 4200, "currency": "USD", "merchant_ref": "order-1001"}


def fake_vault() -> VaultClient:
    """Stand-in for token-vault: returns a fixed token per test card and rejects anything else."""
    tokens: dict[str, str] = {}

    def handler(request: httpx.Request) -> httpx.Response:
        pan = json.loads(request.content)["pan"].replace(" ", "").replace("-", "")
        if pan not in TEST_CARDS:
            return httpx.Response(422, json={"detail": "only published test card numbers are accepted in this lab"})
        token = tokens.setdefault(pan, f"tok_{'T' * (24 - len(pan[-4:]))}{pan[-4:]}")
        return httpx.Response(201, json={"token": token, "last4": pan[-4:], "brand": "visa", "duplicate": False})

    return VaultClient("http://token-vault.test", transport=httpx.MockTransport(handler))


@pytest.fixture
def client(tmp_path):
    app = create_app(Settings(db_path=str(tmp_path / "payments.db")), vault=fake_vault())
    return TestClient(app)
