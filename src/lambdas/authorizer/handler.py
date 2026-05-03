"""Lambda TOKEN-type authorizer — verifies Supabase JWTs via shared secret (HS256).

Wired as an API Gateway Lambda Authorizer. On success, returns an IAM Allow
policy and passes `user_id` (the JWT `sub` claim) to downstream Lambda via
`event['requestContext']['authorizer']['user_id']`.

Configuration (env vars):
  ENVIRONMENT      — dev / prod (used to locate Secrets Manager key)
  SUPABASE_JWKS_URL — optional; if set, verifies RS256 via JWKS instead of HS256
"""

import os
from functools import lru_cache
from typing import Any

import jwt
from aws_lambda_powertools import Logger

from src.shared.secrets import get_secret, is_running_in_lambda

logger = Logger(service="myrunstreak-authorizer")

# Module-level JWKS client cache — survives across warm invocations
_jwks_client: jwt.PyJWKClient | None = None


@lru_cache(maxsize=1)
def _get_jwt_secret() -> str:
    """Fetch Supabase JWT secret from Secrets Manager (cached for Lambda lifetime)."""
    environment = os.environ.get("ENVIRONMENT", "dev")
    secret_name = f"myrunstreak/{environment}/supabase/credentials"
    creds = get_secret(secret_name)
    secret: str = creds["jwt_secret"]
    return secret


def _get_jwks_client(jwks_url: str) -> jwt.PyJWKClient:
    """Return a cached JWKS client; create on first call."""
    global _jwks_client
    if _jwks_client is None:
        _jwks_client = jwt.PyJWKClient(jwks_url, cache_keys=True)
        logger.info(f"Initialised JWKS client for {jwks_url}")
    return _jwks_client


def _verify_token(token: str) -> str:
    """Verify the JWT and return the user_id (`sub` claim)."""
    jwks_url = os.environ.get("SUPABASE_JWKS_URL")

    if jwks_url:
        # RS256 path — token signed with Supabase RSA key, verified via JWKS
        client = _get_jwks_client(jwks_url)
        signing_key = client.get_signing_key_from_jwt(token)
        payload: dict[str, Any] = jwt.decode(
            token,
            signing_key.key,
            algorithms=["RS256"],
            audience="authenticated",
            leeway=10,
        )
    else:
        # HS256 path (Supabase default) — token signed with shared JWT secret
        if is_running_in_lambda():
            secret = _get_jwt_secret()
        else:
            # Local dev: read from env var directly
            secret = os.environ["SUPABASE_JWT_SECRET"]

        payload = jwt.decode(
            token,
            secret,
            algorithms=["HS256"],
            audience="authenticated",
            leeway=10,
        )

    user_id: str = str(payload["sub"])
    return user_id


def _build_policy(
    principal_id: str,
    effect: str,
    method_arn: str,
    user_id: str | None = None,
) -> dict[str, Any]:
    """Build an API Gateway IAM policy document.

    Uses a wildcard ARN so one cached authorization covers all routes in the
    API stage, avoiding repeated authorizer calls per route.
    """
    # method_arn format: arn:aws:execute-api:region:account:api-id/stage/verb/path
    # Extract arn:aws:execute-api:region:account:api-id, then append /stage/*/*
    parts = method_arn.split("/")
    stage = parts[1] if len(parts) > 1 else "*"
    api_base = method_arn.split("/")[0]
    wildcard_arn = f"{api_base}/{stage}/*/*"

    policy: dict[str, Any] = {
        "principalId": principal_id,
        "policyDocument": {
            "Version": "2012-10-17",
            "Statement": [
                {
                    "Action": "execute-api:Invoke",
                    "Effect": effect,
                    "Resource": wildcard_arn,
                }
            ],
        },
    }
    if user_id is not None:
        policy["context"] = {"user_id": user_id}
    return policy


@logger.inject_lambda_context
def lambda_handler(event: dict[str, Any], context: Any) -> dict[str, Any]:
    """TOKEN-type Lambda Authorizer entry point."""
    raw_token: str = event.get("authorizationToken", "")
    method_arn: str = event.get("methodArn", "*")

    # Strip "Bearer " prefix (case-insensitive)
    if raw_token.lower().startswith("bearer "):
        token = raw_token[7:].strip()
    else:
        token = raw_token.strip()

    if not token:
        logger.warning("Empty or missing Authorization token")
        raise Exception("Unauthorized")

    try:
        user_id = _verify_token(token)
        logger.info(f"Authorised user: {user_id}")
        return _build_policy(user_id, "Allow", method_arn, user_id)
    except jwt.ExpiredSignatureError:
        logger.warning("JWT token expired")
        raise Exception("Unauthorized") from None
    except jwt.InvalidTokenError as exc:
        logger.warning(f"Invalid JWT: {exc}")
        raise Exception("Unauthorized") from None
    except Exception as exc:
        logger.error(f"Authorizer error: {exc}")
        raise Exception("Unauthorized") from None
