"""JWT verification (V07). Signature, expiry, issuer and audience are ALL enforced.

HS256 (shared JWT secret) or asymmetric via JWKS (Supabase signing keys). `alg=none` is never accepted.
Identity attributes come from `app_metadata` (writable only by the admin API, not by the end user):
  app_metadata.app_role in {technician, supervisor, administrator};  app_metadata.plants = ["PLANT-A"]
"""

from __future__ import annotations

from typing import Any

import jwt
from jwt import PyJWKClient

from app.config import Settings
from app.models import Principal
from app.security.errors import AuthError

_JWKS: dict[str, PyJWKClient] = {}


def _signing_key(token: str, s: Settings) -> tuple[Any, list[str]]:
    """Key + algorithm allowlist come from SERVER config. The token's `alg` header only selects among configured options,
    and an HS256 token is verified ONLY with the configured shared secret (never with a public key => no key confusion)."""
    alg = jwt.get_unverified_header(token).get("alg")
    if alg == "HS256" and s.jwt_secret:
        return s.jwt_secret, ["HS256"]
    if alg in ("RS256", "ES256") and s.jwt_jwks_url:
        client = _JWKS.setdefault(s.jwt_jwks_url, PyJWKClient(s.jwt_jwks_url, cache_keys=True))
        return client.get_signing_key_from_jwt(token).key, ["RS256", "ES256"]
    raise AuthError("token algorithm not accepted by this server")


def verify_token(token: str, s: Settings) -> Principal:
    try:
        key, algs = _signing_key(token, s)
        opts: dict[str, Any] = {"require": ["exp", "sub", "aud"], "verify_aud": True}
        claims = jwt.decode(token, key, algorithms=algs, audience=s.jwt_audience or None,
                            issuer=s.jwt_issuer or None, options=opts)
    except AuthError:
        raise
    except jwt.PyJWTError as e:  # expired, bad signature, wrong aud/iss, malformed, wrong alg
        raise AuthError(f"invalid token: {type(e).__name__}") from e
    meta = claims.get("app_metadata") or {}
    role = meta.get("app_role") or claims.get("app_role")
    plants = meta.get("plants", claims.get("plants"))
    if not role or not isinstance(plants, list) or not all(isinstance(p, str) for p in plants):
        raise AuthError("token lacks app_role/plants claims")
    return Principal(user_id=str(claims["sub"]), role=str(role), plants=tuple(plants))
