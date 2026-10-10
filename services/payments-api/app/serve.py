"""Start payments-api over plain HTTP (Phase 1 only; Phase 2 replaces this file with an HTTPS version)."""
import uvicorn

from app.config import Settings


def main() -> None:
    settings = Settings.from_env()
    uvicorn.run(
        "app.main:create_app",
        factory=True,
        host="0.0.0.0",
        port=settings.port,
        proxy_headers=False,
        server_header=False,
    )


if __name__ == "__main__":
    main()
