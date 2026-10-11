"""OAuth 2.0 access-token validation for tokens from an Okta custom authorization server (Phase 2)."""
import json
import logging
from dataclasses import dataclass

import jwt
from fastapi import Depends, HTTPException
from fastapi.security import HTTPAuthorizationCredentials, HTTPBearer

log = logging.getLogger("payments-api.auth")


@dataclass(frozen=True)
class Principal:
    client_id: str
    scopes: frozenset[str]


class TokenValidator:
    def __init__(self, issuer: str, audience: str, jwks_client=None, leeway_seconds: int = 30):
        if not issuer:
            raise ValueError("OAUTH_ISSUER must be set")
        self.issuer = issuer  # keep exactly as configured: Auth0 iss ends with "/" and must match
        self.audience = audience
        self.leeway = leeway_seconds
        # Okta publishes each authorization server's signing keys at <issuer>/v1/keys. PyJWKClient caches
        # them and refetches when a token carries an unknown key ID, which is how Okta key rotation is picked up.
        self._jwks = jwks_client or jwt.PyJWKClient(f"{self.issuer.rstrip('/')}/.well-known/jwks.json", cache_keys=True, lifespan=3600, timeout=5)

    def validate(self, token: str) -> dict:
        signing_key = self._jwks.get_signing_key_from_jwt(token)
        return jwt.decode(
            token,
            signing_key.key,
            algorithms=["RS256"],  # fixed list: never let the token's own "alg" header choose
            audience=self.audience,
            issuer=self.issuer,
            leeway=self.leeway,
            options={"require": ["exp", "iat", "iss", "aud", "sub"]},
        )


_bearer = HTTPBearer(auto_error=False)


def _granted_scopes(claims: dict) -> frozenset[str]:
    if isinstance(claims.get("scp"), list):  # Okta's format
        return frozenset(claims["scp"])
    return frozenset(str(claims.get("scope", "")).split())  # RFC 9068 format


def _reject(status: int, reason: str, header: str) -> HTTPException:
    log.warning(json.dumps({"event": "auth_rejected", "status": status, "reason": reason}))
    return HTTPException(status_code=status, detail=reason, headers={"WWW-Authenticate": header})


def require_scopes(validator: TokenValidator, *required: str):
    """FastAPI dependency: valid token from our issuer, for our audience, carrying every required scope."""

    def dependency(credentials: HTTPAuthorizationCredentials | None = Depends(_bearer)) -> Principal:
        if credentials is None:
            raise _reject(401, "missing bearer token", "Bearer")
        try:
            claims = validator.validate(credentials.credentials)
        except jwt.ExpiredSignatureError:
            raise _reject(401, "token expired", 'Bearer error="invalid_token"')
        except jwt.InvalidAudienceError:
            raise _reject(401, "wrong audience", 'Bearer error="invalid_token"')
        except jwt.InvalidIssuerError:
            raise _reject(401, "wrong issuer", 'Bearer error="invalid_token"')
        except jwt.PyJWTError:
            raise _reject(401, "invalid token", 'Bearer error="invalid_token"')

        granted = _granted_scopes(claims)
        if not set(required) <= granted:
            raise _reject(403, "insufficient scope", f'Bearer error="insufficient_scope", scope="{" ".join(required)}"')
        return Principal(client_id=claims.get("cid") or claims.get("azp") or claims["sub"], scopes=granted)

    return dependency
