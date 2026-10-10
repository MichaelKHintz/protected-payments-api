"""Runtime settings for payments-api, read from environment variables."""
import os
from dataclasses import dataclass


@dataclass(frozen=True)
class Settings:
    db_path: str = "/data/payments.db"
    port: int = 8080
    # token-vault location; Phase 2 adds the CA bundle and this service's client certificate
    vault_url: str = "http://token-vault.payments.svc:8080"
    vault_ca_file: str | None = None
    vault_cert_file: str | None = None
    vault_key_file: str | None = None
    # Phase 2: HTTPS for this API, and OAuth via an Okta custom authorization server
    tls_cert_file: str | None = None
    tls_key_file: str | None = None
    oauth_issuer: str | None = None       # https://<your-org>.okta.com/oauth2/<auth-server-id>
    oauth_audience: str = "api://payments-lab"
    # Phase 3: Claude API
    anthropic_api_key_file: str | None = None
    claude_model: str = "claude-haiku-5-5"
    claude_max_tokens: int = 400

    @classmethod
    def from_env(cls) -> "Settings":
        env = os.environ
        return cls(
            db_path=env.get("DB_PATH", cls.db_path),
            port=int(env.get("PORT", str(cls.port))),
            vault_url=env.get("VAULT_URL", cls.vault_url),
            vault_ca_file=env.get("VAULT_CA_FILE"),
            vault_cert_file=env.get("VAULT_CLIENT_CERT_FILE"),
            vault_key_file=env.get("VAULT_CLIENT_KEY_FILE"),
            tls_cert_file=env.get("TLS_CERT_FILE"),
            tls_key_file=env.get("TLS_KEY_FILE"),
            oauth_issuer=env.get("OAUTH_ISSUER"),
            oauth_audience=env.get("OAUTH_AUDIENCE", cls.oauth_audience),
            anthropic_api_key_file=env.get("ANTHROPIC_API_KEY_FILE"),
            claude_model=env.get("CLAUDE_MODEL", cls.claude_model),
            claude_max_tokens=int(env.get("CLAUDE_MAX_TOKENS", str(cls.claude_max_tokens))),
        )
