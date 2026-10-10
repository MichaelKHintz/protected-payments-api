"""Runtime settings for token-vault, read from environment variables."""
import os
from dataclasses import dataclass


def _csv(value: str) -> frozenset[str]:
    return frozenset(v.strip() for v in value.split(",") if v.strip())


@dataclass(frozen=True)
class Settings:
    aws_region: str = "us-east-1"
    kms_key_id: str = "alias/payments-lab-vault"
    hmac_key_id: str = "alias/payments-lab-pan-hmac"
    db_path: str = "/data/vault.db"
    test_cards_only: bool = True
    port: int = 8080
    # Phase 2: mTLS server certificate, CA bundle, and which client identities may call what
    tls_cert_file: str | None = None
    tls_key_file: str | None = None
    tls_ca_file: str | None = None
    tokenize_callers: frozenset[str] = frozenset()
    detokenize_callers: frozenset[str] = frozenset()

    @classmethod
    def from_env(cls) -> "Settings":
        env = os.environ
        return cls(
            aws_region=env.get("AWS_REGION", cls.aws_region),
            kms_key_id=env.get("KMS_KEY_ID", cls.kms_key_id),
            hmac_key_id=env.get("HMAC_KEY_ID", cls.hmac_key_id),
            db_path=env.get("DB_PATH", cls.db_path),
            test_cards_only=env.get("TEST_CARDS_ONLY", "true").lower() == "true",
            port=int(env.get("PORT", str(cls.port))),
            tls_cert_file=env.get("TLS_CERT_FILE"),
            tls_key_file=env.get("TLS_KEY_FILE"),
            tls_ca_file=env.get("TLS_CA_FILE"),
            tokenize_callers=_csv(env.get("TOKENIZE_CALLERS", "")),
            detokenize_callers=_csv(env.get("DETOKENIZE_CALLERS", "")),
        )
