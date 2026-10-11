"""Start payments-api over HTTPS with a certificate from the lab's private CA (Phase 2 and later)."""
import ssl

import uvicorn

from app.config import Settings


def tls12_plus(config, default_factory) -> ssl.SSLContext:
    context = default_factory()
    context.minimum_version = ssl.TLSVersion.TLSv1_2
    return context


def main() -> None:
    settings = Settings.from_env()
    if not (settings.tls_cert_file and settings.tls_key_file):
        raise SystemExit("payments-api requires TLS_CERT_FILE and TLS_KEY_FILE")
    uvicorn.run(
        "app.main:create_app",
        factory=True,
        host="0.0.0.0",
        port=settings.port,
        ssl_certfile=settings.tls_cert_file,
        ssl_keyfile=settings.tls_key_file,
        ssl_context_factory=tls12_plus,
        proxy_headers=False,
        server_header=False,
    )


if __name__ == "__main__":
    main()
