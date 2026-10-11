"""token-vault: swaps card numbers for random tokens and keeps the card numbers encrypted.

Phase 2 version: every request arrives over mTLS, and each endpoint checks the caller's
certificate identity (a SPIFFE-style URI SAN) against an allowlist.
"""
import json
import logging
import secrets
import sqlite3

import boto3
from fastapi import FastAPI, HTTPException, Request, Response
from fastapi.exceptions import RequestValidationError
from fastapi.responses import JSONResponse
from pydantic import BaseModel, Field

from app import cards
from app.config import Settings
from app.crypto import EnvelopeCipher, PanFingerprinter
from app.store import VaultStore

log = logging.getLogger("token-vault")
logging.basicConfig(level=logging.INFO, format="%(message)s")


class TokenizeRequest(BaseModel):
    pan: str = Field(min_length=13, max_length=23)


class TokenizeResponse(BaseModel):
    token: str
    last4: str
    brand: str
    duplicate: bool


class DetokenizeRequest(BaseModel):
    token: str = Field(pattern=r"^tok_[A-Za-z0-9_-]{24}$")


def new_token() -> str:
    # Random, not derived from the PAN: there is no math that turns a token back into a card number.
    return "tok_" + secrets.token_urlsafe(18)


def caller_identity(request: Request) -> str | None:
    """Return the SPIFFE URI from the verified client certificate, if there is one."""
    peer = request.scope.get("extensions", {}).get("tls", {}).get("peer_cert") or {}
    for kind, value in peer.get("subjectAltName", ()):
        if kind == "URI" and value.startswith("spiffe://"):
            return value
    return None


def authorize(request: Request, allowed: frozenset[str], action: str) -> str:
    caller = caller_identity(request)
    if caller is None or caller not in allowed:
        log.warning(json.dumps({"event": "authz_denied", "action": action, "caller": caller}))
        raise HTTPException(status_code=403, detail="caller is not allowed to perform this action")
    return caller


def create_app(settings: Settings | None = None, kms_client=None) -> FastAPI:
    settings = settings or Settings.from_env()
    kms = kms_client or boto3.client("kms", region_name=settings.aws_region)
    cipher = EnvelopeCipher(kms, settings.kms_key_id)
    fingerprinter = PanFingerprinter(kms, settings.hmac_key_id)
    store = VaultStore(settings.db_path)

    # Internal service: no interactive docs or OpenAPI schema.
    app = FastAPI(title="token-vault", docs_url=None, redoc_url=None, openapi_url=None)

    @app.exception_handler(RequestValidationError)
    async def validation_error(request: Request, exc: RequestValidationError):
        # FastAPI's default 422 body echoes the submitted value, which would reflect a card number
        # back to the caller and into any log that captures responses. Return field names only.
        fields = [".".join(str(p) for p in err["loc"]) for err in exc.errors()]
        return JSONResponse(status_code=422, content={"detail": "invalid request", "fields": fields})

    @app.get("/healthz")
    def healthz():
        return {"status": "ok"}

    @app.post("/v1/tokenize", status_code=201, response_model=TokenizeResponse)
    def tokenize(body: TokenizeRequest, request: Request, response: Response):
        caller = authorize(request, settings.tokenize_callers, "tokenize")
        try:
            pan = cards.normalize(body.pan)
        except ValueError:
            raise HTTPException(status_code=422, detail="card number must be 13-19 digits")
        if not cards.luhn_valid(pan):
            raise HTTPException(status_code=422, detail="card number failed the Luhn check")
        if settings.test_cards_only and pan not in cards.TEST_CARDS:
            raise HTTPException(status_code=422, detail="only published test card numbers are accepted in this lab")

        fingerprint = fingerprinter.fingerprint(pan)
        existing = store.find_by_fingerprint(fingerprint)
        if existing is None:
            token = new_token()
            sealed = cipher.seal(token, pan)
            try:
                store.insert(token, fingerprint, pan[-4:], cards.brand(pan), sealed)
            except sqlite3.IntegrityError:  # the same card was tokenized concurrently
                existing = store.find_by_fingerprint(fingerprint)

        if existing is not None:
            response.status_code = 200
            log.info(json.dumps({"event": "tokenize", "token": existing.token, "duplicate": True, "caller": caller}))
            return TokenizeResponse(token=existing.token, last4=existing.last4, brand=existing.brand, duplicate=True)

        record = store.get(token)
        log.info(json.dumps({"event": "tokenize", "token": token, "duplicate": False, "caller": caller}))
        return TokenizeResponse(token=token, last4=record.last4, brand=record.brand, duplicate=False)

    @app.post("/v1/detokenize")
    def detokenize(body: DetokenizeRequest, request: Request):
        caller = authorize(request, settings.detokenize_callers, "detokenize")
        record = store.get(body.token)
        if record is None:
            raise HTTPException(status_code=404, detail="unknown token")
        pan = cipher.open(record.token, record.sealed)
        log.info(json.dumps({"event": "detokenize", "token": record.token, "caller": caller}))
        return {"pan": pan}

    return app
