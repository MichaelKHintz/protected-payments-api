"""Client for token-vault. Phase 2 turns on mTLS by setting the CA bundle and client certificate."""
import ssl

import httpx


class CardRejected(Exception):
    """The vault refused the card number (bad format, failed Luhn, or not a test card)."""


class VaultUnavailable(Exception):
    """The vault could not be reached or returned an unexpected error."""


class VaultClient:
    def __init__(self, base_url: str, ca_file: str | None = None, cert_file: str | None = None,
                 key_file: str | None = None, timeout: float = 5.0, transport: httpx.BaseTransport | None = None):
        verify: bool | ssl.SSLContext = True
        if ca_file:
            # Trust only the lab's private CA for this hop, and present our own certificate.
            context = ssl.create_default_context(ssl.Purpose.SERVER_AUTH, cafile=ca_file)
            context.minimum_version = ssl.TLSVersion.TLSv1_3
            if cert_file and key_file:
                context.load_cert_chain(cert_file, key_file)
            verify = context
        self._http = httpx.Client(base_url=base_url, verify=verify, timeout=timeout, transport=transport)

    def tokenize(self, pan: str) -> dict:
        try:
            r = self._http.post("/v1/tokenize", json={"pan": pan})
        except httpx.HTTPError as exc:
            raise VaultUnavailable(type(exc).__name__) from None
        if r.status_code == 422:
            raise CardRejected(r.json().get("detail", "card rejected"))
        if r.status_code not in (200, 201):
            raise VaultUnavailable(f"vault returned HTTP {r.status_code}")
        return r.json()
