"""payments-api: creates payments and stores only vault tokens.

Phase 1 version: no authentication yet (Phase 2 adds OAuth), plain HTTP to the vault (Phase 2 adds mTLS).
"""
import json
import logging

from fastapi import FastAPI, HTTPException, Request
from fastapi.exceptions import RequestValidationError
from fastapi.responses import JSONResponse
from pydantic import BaseModel, Field

from app.config import Settings
from app.store import PaymentStore
from app.vault_client import CardRejected, VaultClient, VaultUnavailable

logging.basicConfig(level=logging.INFO, format="%(message)s")
log = logging.getLogger("payments-api")
logging.getLogger("httpx").setLevel(logging.WARNING)


class CreatePayment(BaseModel):
    card_number: str = Field(min_length=13, max_length=23)
    amount_cents: int = Field(gt=0, le=10_000_000)
    currency: str = Field(default="USD", pattern=r"^[A-Z]{3}$")
    merchant_ref: str = Field(min_length=1, max_length=64, pattern=r"^[A-Za-z0-9_-]+$")


def create_app(settings: Settings | None = None, vault: VaultClient | None = None) -> FastAPI:
    settings = settings or Settings.from_env()
    vault = vault or VaultClient(settings.vault_url)
    store = PaymentStore(settings.db_path)

    app = FastAPI(title="payments-api", version="1.0")

    @app.exception_handler(RequestValidationError)
    async def validation_error(request: Request, exc: RequestValidationError):
        # Don't echo submitted values (FastAPI's default does), or a card number would be reflected back.
        fields = [".".join(str(p) for p in err["loc"]) for err in exc.errors()]
        return JSONResponse(status_code=422, content={"detail": "invalid request", "fields": fields})

    @app.get("/healthz")
    def healthz():
        return {"status": "ok"}

    @app.post("/v1/payments", status_code=201)
    def create_payment(body: CreatePayment):
        try:
            card = vault.tokenize(body.card_number)  # the PAN goes to the vault and is never stored here
        except CardRejected as exc:
            raise HTTPException(status_code=422, detail=str(exc))
        except VaultUnavailable:
            raise HTTPException(status_code=502, detail="tokenization service unavailable")
        payment = store.create_payment(card["token"], card["last4"], card["brand"], body.amount_cents,
                                       body.currency, body.merchant_ref, created_by="unauthenticated")
        log.info(json.dumps({"event": "payment_created", "payment_id": payment["id"], "card_token": card["token"]}))
        return payment

    @app.get("/v1/payments/{payment_id}")
    def get_payment(payment_id: str):
        payment = store.get_payment(payment_id)
        if payment is None:
            raise HTTPException(status_code=404, detail="payment not found")
        return payment

    return app
