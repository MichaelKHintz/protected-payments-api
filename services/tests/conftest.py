import os

import boto3
import pytest
from fastapi.testclient import TestClient
from moto import mock_aws

from app.config import Settings
from app.main import create_app

PAYMENTS_API = "spiffe://payments-lab/ns/payments/sa/payments-api"
SETTLEMENT = "spiffe://payments-lab/ns/payments/sa/settlement-worker"


@pytest.fixture(autouse=True)
def fake_aws_env(monkeypatch):
    # moto intercepts every AWS call; these values only keep botocore from looking for real credentials.
    for key, value in {
        "AWS_ACCESS_KEY_ID": "testing",
        "AWS_SECRET_ACCESS_KEY": "testing",
        "AWS_DEFAULT_REGION": "us-east-1",
    }.items():
        monkeypatch.setenv(key, value)


@pytest.fixture
def kms():
    with mock_aws():
        client = boto3.client("kms", region_name="us-east-1")
        yield client


@pytest.fixture
def app(kms, tmp_path):
    enc_key = kms.create_key(KeyUsage="ENCRYPT_DECRYPT", KeySpec="SYMMETRIC_DEFAULT")["KeyMetadata"]["Arn"]
    mac_key = kms.create_key(KeyUsage="GENERATE_VERIFY_MAC", KeySpec="HMAC_256")["KeyMetadata"]["Arn"]
    settings = Settings(
        kms_key_id=enc_key,
        hmac_key_id=mac_key,
        db_path=str(tmp_path / "vault.db"),
        tokenize_callers=frozenset({PAYMENTS_API}),
        detokenize_callers=frozenset({SETTLEMENT}),
    )
    application = create_app(settings, kms_client=kms)
    application.state.db_path = settings.db_path
    return application


def with_identity(app, spiffe_id):
    """Simulate the verified client certificate that ClientCertH11Protocol puts in the scope."""

    async def wrapped(scope, receive, send):
        if scope["type"] == "http" and spiffe_id:
            scope.setdefault("extensions", {})["tls"] = {"peer_cert": {"subjectAltName": (("URI", spiffe_id),)}}
        await app(scope, receive, send)

    return wrapped


@pytest.fixture
def as_payments_api(app):
    return TestClient(with_identity(app, PAYMENTS_API))


@pytest.fixture
def as_settlement(app):
    return TestClient(with_identity(app, SETTLEMENT))


@pytest.fixture
def anonymous(app):
    return TestClient(app)
