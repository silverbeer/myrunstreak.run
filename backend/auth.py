"""Supabase JWT verification middleware.

Replaces the API Gateway TOKEN authorizer. Verifies HS256 (legacy) and ES256
(newer Supabase signing keys via JWKS) tokens, injects ``user_id`` into
``request.state``, and raises 401 on anything malformed.
"""

from functools import lru_cache
from typing import Any
from uuid import UUID

import jwt
from fastapi import HTTPException, Request, status
from jwt import PyJWKClient

from backend.config import get_settings


@lru_cache(maxsize=1)
def _jwks_client() -> PyJWKClient:
    settings = get_settings()
    jwks_url = f"{settings.supabase_url}/auth/v1/.well-known/jwks.json"
    return PyJWKClient(jwks_url, cache_keys=True)


def _decode(token: str) -> dict[str, Any]:
    """Decode a Supabase JWT. Tries ES256/JWKS first, falls back to HS256."""
    settings = get_settings()
    header = jwt.get_unverified_header(token)
    alg = header.get("alg", "HS256")

    if alg == "ES256":
        signing_key = _jwks_client().get_signing_key_from_jwt(token)
        return jwt.decode(  # type: ignore[no-any-return]
            token,
            signing_key.key,
            algorithms=["ES256"],
            audience="authenticated",
            leeway=10,
        )

    return jwt.decode(  # type: ignore[no-any-return]
        token,
        settings.supabase_jwt_secret,
        algorithms=["HS256"],
        audience="authenticated",
        leeway=10,
    )


def authenticate_request(request: Request) -> UUID:
    """FastAPI dependency: extracts and verifies the bearer token.

    Returns:
        Authenticated user UUID (Supabase ``sub`` claim).

    Raises:
        HTTPException 401 on missing, malformed, or invalid tokens.
    """
    auth_header = request.headers.get("authorization", "")
    if not auth_header.lower().startswith("bearer "):
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail="Missing or malformed Authorization header",
        )
    token = auth_header[7:].strip()
    if not token:
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail="Empty bearer token",
        )

    try:
        payload = _decode(token)
    except jwt.ExpiredSignatureError as exc:
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail="Token expired",
        ) from exc
    except jwt.InvalidTokenError as exc:
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail=f"Invalid token: {exc}",
        ) from exc

    sub = payload.get("sub")
    if not sub:
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail="Token missing sub claim",
        )

    try:
        user_id = UUID(str(sub))
    except ValueError as exc:
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail="sub claim is not a valid UUID",
        ) from exc

    request.state.user_id = user_id
    return user_id
