"""AWS Secrets Manager utilities for MyRunStreak.com.

This module provides secure access to secrets stored in AWS Secrets Manager.
Lambda functions should use these utilities instead of environment variables
for sensitive credentials.
"""

import json
import logging
import os
from functools import lru_cache
from typing import Any

logger = logging.getLogger(__name__)


def is_running_in_lambda() -> bool:
    """Check if code is running in AWS Lambda environment."""
    return "AWS_LAMBDA_FUNCTION_NAME" in os.environ


@lru_cache
def get_secret(secret_name: str) -> dict[str, Any]:
    """
    Fetch secret from AWS Secrets Manager (cached).

    Args:
        secret_name: Full secret name (e.g., 'myrunstreak/dev/supabase/credentials')

    Returns:
        Secret value as dictionary

    Raises:
        ClientError: If secret cannot be retrieved
    """
    import boto3
    from botocore.exceptions import ClientError

    client = boto3.client("secretsmanager")

    try:
        response = client.get_secret_value(SecretId=secret_name)
        secret_string = response["SecretString"]
        result: dict[str, Any] = json.loads(secret_string)
        return result
    except ClientError as e:
        logger.error(f"Failed to retrieve secret {secret_name}: {e}")
        raise


def get_supabase_credentials() -> dict[str, str]:
    """
    Get Supabase credentials from Secrets Manager.

    Returns:
        Dict with 'url', 'key', and 'jwt_secret' keys

    Example:
        ```python
        creds = get_supabase_credentials()
        client = create_client(creds['url'], creds['key'])
        ```
    """
    environment = os.environ.get("ENVIRONMENT", "dev")
    secret_name = f"myrunstreak/{environment}/supabase/credentials"
    return get_secret(secret_name)


def get_smashrun_oauth_credentials() -> dict[str, str]:
    """
    Get SmashRun OAuth client credentials from Secrets Manager.

    Returns:
        Dict with OAuth credentials including:
        - access_token
        - refresh_token
        - (future: client_id, client_secret)
    """
    environment = os.environ.get("ENVIRONMENT", "dev")
    secret_name = f"myrunstreak/{environment}/smashrun/oauth"
    return get_secret(secret_name)


def get_api_keys() -> dict[str, str]:
    """
    Get API keys from Secrets Manager.

    Returns:
        Dict with API key values
    """
    environment = os.environ.get("ENVIRONMENT", "dev")
    secret_name = f"myrunstreak/{environment}/api/keys"
    return get_secret(secret_name)
