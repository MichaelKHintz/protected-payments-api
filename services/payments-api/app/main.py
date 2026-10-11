"""payments-api: creates payments and stores only vault tokens; adds an LLM support-summary gateway.

Phase 3 version: OAuth scopes on every endpoint, mTLS to the vault, and redaction before Claude.
"""
import hashlib
import json
import logging
import time
import uuid

from fastapi import Depends, FastAPI, HTTPException, Request
from fastapi.exceptions import RequestValidationError
from fastapi.responses import JSONResponse
from pydantic import BaseModel, Field

from app.auth import Principal, TokenValidator, require_scopes
from app.config import Settings
from app.llm import Summarizer
from app.redact import Redactor, UnsafePayload, assert_no_card_data
from app.store import PaymentStore
from app.vault_client import CardRejected, VaultClient, VaultUnavailable

logging.basicConfig(level=logging.INFO, format="%(message)s")
log = logging.getLogger("payments-api")
audit = logging.getLogger("payments-api.llm-audit")
for noisy in ("httpx", "httpcore", "anthropic"):
    # These libraries can log request details at DEBUG; keep them quiet so nothing sensitive is written.
    logging.getLogger(noisy).setLevel(logging.WARNING)


class CreatePayment(BaseModel):
    card_number: str = Field(min_length=13, max_length=23)
    amount_cents: int = Field(gt=0, le=10_000_000)
    currency: str = Field(default="USD", pattern=r"^[A-Z]{3}$")
    merchant_ref: str = Field(min_length=1, max_length=64, pattern=r"^[A-Za-z0-9_-]+$")


class NoteIn(BaseModel):
    text: str = Field(min_length=1, max_length=2000)


class SummaryIn(BaseModel):
    payment_id: str | None = Field(default=None, pattern=r"^pay_[a-f0-9]{20}$")
    notes: str | None = Field(default=None, max_length=4000)


def create_app(settings: Settings | None = None, vault: VaultClient | None = None,
               validator: TokenValidator | None = None, summarizer: Summarizer | None = None) -> FastAPI:
    settings = settings or Settings.from_env()
    vault = vault or VaultClient(settings.vault_url, settings.vault_ca_file, settings.vault_cert_file,
                                 settings.vault_key_file)
    validator = validator or TokenValidator(settings.oauth_issuer, settings.oauth_audience)
    summarizer = summarizer or Summarizer(settings)
    store = PaymentStore(settings.db_path)

    def tokenize_or_none(pan: str) -> str | None:
        try:
            return vault.tokenize(pan)["token"]
        except (CardRejected, VaultUnavailable):
            return None  # still redacted, just without a token

    redactor = Redactor(tokenize_pan=tokenize_or_none)
    can_write = require_scopes(validator, "payments:write")
    can_read = require_scopes(validator, "payments:read")
    can_summarize = require_scopes(validator, "support:summarize")

    app = FastAPI(title="payments-api", version="3.0")

    @app.exception_handler(RequestValidationError)
    async def validation_error(request: Request, exc: RequestValidationError):
        # Don't echo submitted values (FastAPI's default does), or a card number would be reflected back.
        fields = [".".join(str(p) for p in err["loc"]) for err in exc.errors()]
        return JSONResponse(status_code=422, content={"detail": "invalid request", "fields": fields})

    @app.get("/healthz")
    def healthz():
        return {"status": "ok"}

    @app.post("/v1/payments", status_code=201)
    def create_payment(body: CreatePayment, principal: Principal = Depends(can_write)):
        try:
            card = vault.tokenize(body.card_number)  # the PAN goes to the vault and is never stored here
        except CardRejected as exc:
            raise HTTPException(status_code=422, detail=str(exc))
        except VaultUnavailable:
            raise HTTPException(status_code=502, detail="tokenization service unavailable")
        payment = store.create_payment(card["token"], card["last4"], card["brand"], body.amount_cents,
                                       body.currency, body.merchant_ref, principal.client_id)
        log.info(json.dumps({"event": "payment_created", "payment_id": payment["id"], "card_token": card["token"],
                             "client_id": principal.client_id}))
        return payment

    @app.get("/v1/payments/{payment_id}")
    def get_payment(payment_id: str, principal: Principal = Depends(can_read)):
        payment = store.get_payment(payment_id)
        if payment is None:
            raise HTTPException(status_code=404, detail="payment not found")
        return payment

    @app.post("/v1/payments/{payment_id}/notes", status_code=201)
    def add_note(payment_id: str, body: NoteIn, principal: Principal = Depends(can_write)):
        if store.get_payment(payment_id) is None:
            raise HTTPException(status_code=404, detail="payment not found")
        # Redact on the way in, so a card number typed into a note never reaches the database.
        result = redactor.redact(body.text)
        store.add_note(payment_id, result.text, principal.client_id)
        return {"payment_id": payment_id, "stored_text": result.text, "redactions": result.counts}

    @app.post("/v1/support/summary")
    def support_summary(body: SummaryIn, principal: Principal = Depends(can_summarize)):
        parts = []
        if body.payment_id:
            payment = store.get_payment(body.payment_id)
            if payment is None:
                raise HTTPException(status_code=404, detail="payment not found")
            parts.append(
                f"Payment {payment['id']}: {payment['amount_cents'] / 100:.2f} {payment['currency']}, "
                f"{payment['brand']} card ending {payment['last4']} ([CARD {payment['card_token']}]), "
                f"status {payment['status']}."
            )
            parts.extend(store.list_notes(body.payment_id))
        if body.notes:
            parts.append(body.notes)
        if not parts:
            raise HTTPException(status_code=422, detail="provide payment_id, notes, or both")

        request_id = str(uuid.uuid4())
        # Redact everything again: stored notes were cleaned on the way in, ad-hoc notes were not.
        result = redactor.redact("\n".join(parts))
        try:
            assert_no_card_data(result.text)
        except UnsafePayload:
            audit.warning(json.dumps({"event": "llm_request_blocked", "request_id": request_id,
                                      "client_id": principal.client_id, "reason": "card data after redaction"}))
            raise HTTPException(status_code=422, detail="request blocked: possible card data after redaction")

        record = {
            "event": "llm_request",
            "request_id": request_id,
            "client_id": principal.client_id,
            "payment_id": body.payment_id,
            "model": settings.claude_model,
            "redactions": result.counts,
            "prompt_sha256": hashlib.sha256(result.text.encode()).hexdigest(),
            "redacted_prompt": result.text,  # safe to log: this is exactly what leaves the environment
        }
        started = time.monotonic()
        try:
            summary = summarizer.summarize(result.text)
        except Exception as exc:  # provider outage, timeout, bad key, rate limit
            record.update(outcome="error", error_type=type(exc).__name__,
                          latency_ms=round((time.monotonic() - started) * 1000))
            audit.error(json.dumps(record))
            raise HTTPException(status_code=502, detail="LLM provider error")

        # Treat model output as untrusted too: mask anything card-shaped before returning it.
        output = Redactor().redact(summary.text)
        record.update(
            outcome="ok",
            latency_ms=round((time.monotonic() - started) * 1000),
            model=summary.model,
            input_tokens=summary.input_tokens,
            output_tokens=summary.output_tokens,
            provider_request_id=summary.provider_request_id,
            output_redactions=output.counts,
        )
        audit.info(json.dumps(record))
        return {"request_id": request_id, "summary": output.text, "model": summary.model,
                "redactions": result.counts}

    return app
