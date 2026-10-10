"""Start token-vault with mandatory mTLS (Phase 2)."""
import ssl

import uvicorn

from app.config import Settings
from app.tls_protocol import ClientCertH11Protocol


def tls13_only(config, default_factory) -> ssl.SSLContext:
    context = default_factory()
    context.minimum_version = ssl.TLSVersion.TLSv1_3
    return context


def main() -> None:
    settings = Settings.from_env()
    if not (settings.tls_cert_file and settings.tls_key_file and settings.tls_ca_file):
        raise SystemExit("token-vault requires TLS_CERT_FILE, TLS_KEY_FILE and TLS_CA_FILE: mTLS is mandatory")
    uvicorn.run(
        "app.main:create_app",
        factory=True,
        host="0.0.0.0",
        port=settings.port,
        ssl_certfile=settings.tls_cert_file,
        ssl_keyfile=settings.tls_key_file,
        ssl_ca_certs=settings.tls_ca_file,       # only this CA's certificates are trusted
        ssl_cert_reqs=ssl.CERT_REQUIRED,         # no client certificate, no connection
        ssl_context_factory=tls13_only,
        http=ClientCertH11Protocol,
        proxy_headers=False,
        server_header=False,
    )


if __name__ == "__main__":
    main()
