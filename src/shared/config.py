"""Configuration management for MyRunStreak.com."""

import logging
import os
from pathlib import Path

from pydantic import Field
from pydantic_settings import BaseSettings, SettingsConfigDict

logger = logging.getLogger(__name__)


def find_env_file() -> Path | None:
    """Find .env file at git root (project root)."""
    # Search up for git root and use .env there
    current = Path.cwd()
    for parent in [current, *current.parents]:
        if (parent / ".git").exists():
            env_file = parent / ".env"
            if env_file.exists():
                return env_file
            break
    # Fallback to current directory
    local_env = Path.cwd() / ".env"
    if local_env.exists():
        return local_env
    return None


def is_running_in_lambda() -> bool:
    """Check if code is running in AWS Lambda environment."""
    return "AWS_LAMBDA_FUNCTION_NAME" in os.environ


# Find env file once at module load
_env_file = find_env_file()


class Settings(BaseSettings):
    """
    Application settings loaded from environment variables.

    These settings are used across Lambda functions and local development.
    In Lambda, secrets are loaded from AWS Secrets Manager.
    Locally, they come from .env file.
    """

    model_config = SettingsConfigDict(
        env_file=_env_file,
        env_file_encoding="utf-8",
        case_sensitive=False,
        extra="ignore",
    )

    # SmashRun OAuth Configuration
    smashrun_client_id: str = Field(
        default="",
        description="SmashRun OAuth Client ID",
    )
    smashrun_client_secret: str = Field(
        default="",
        description="SmashRun OAuth Client Secret",
    )
    smashrun_redirect_uri: str = Field(
        default="http://localhost:9876/callback",
        description="OAuth redirect URI for authorization code flow",
    )

    # Supabase Configuration
    supabase_url: str = Field(
        default="",
        description="Supabase project URL",
    )
    supabase_key: str = Field(
        default="",
        description="Supabase service role key (bypasses RLS)",
    )

    # DuckDB Configuration (DEPRECATED - migrating to Supabase)
    duckdb_path: str = Field(
        default="s3://myrunstreak-data/runs.duckdb",
        description="Path to DuckDB database (local or S3) - DEPRECATED",
    )

    # AWS Configuration
    aws_region: str = Field(
        default="us-east-2",
        description="AWS region for services",
    )

    # Application Settings
    environment: str = Field(
        default="dev",
        description="Environment: dev, staging, prod",
    )
    log_level: str = Field(
        default="INFO",
        description="Logging level",
    )


# Singleton instance
_settings: Settings | None = None


def _load_secrets_from_aws() -> dict[str, str]:
    """
    Load secrets from AWS Secrets Manager.

    Returns:
        Dict with secret values to overlay on settings
    """
    from .secrets import get_smashrun_oauth_credentials, get_supabase_credentials

    secrets: dict[str, str] = {}

    try:
        # Load SmashRun OAuth credentials
        smashrun_creds = get_smashrun_oauth_credentials()
        secrets["smashrun_client_id"] = smashrun_creds.get("client_id", "")
        secrets["smashrun_client_secret"] = smashrun_creds.get("client_secret", "")
        logger.debug("Loaded SmashRun credentials from Secrets Manager")
    except Exception as e:
        logger.warning(f"Failed to load SmashRun credentials from Secrets Manager: {e}")

    try:
        # Load Supabase credentials
        supabase_creds = get_supabase_credentials()
        secrets["supabase_url"] = supabase_creds.get("url", "")
        secrets["supabase_key"] = supabase_creds.get("key", "")
        logger.debug("Loaded Supabase credentials from Secrets Manager")
    except Exception as e:
        logger.warning(f"Failed to load Supabase credentials from Secrets Manager: {e}")

    return secrets


def get_settings() -> Settings:
    """
    Get application settings (singleton pattern).

    In Lambda: Loads secrets from AWS Secrets Manager
    Locally: Loads from .env file

    Returns:
        Settings instance with all configuration
    """
    global _settings
    if _settings is not None:
        return _settings

    if is_running_in_lambda():
        # In Lambda: Load base settings, then overlay secrets from Secrets Manager
        logger.info("Running in Lambda - loading secrets from AWS Secrets Manager")

        # First load base settings (non-secret env vars)
        base_settings = Settings()

        # Load secrets from AWS Secrets Manager
        secrets = _load_secrets_from_aws()

        # Create new settings with secrets overlaid
        _settings = Settings(
            smashrun_client_id=secrets.get("smashrun_client_id", base_settings.smashrun_client_id),
            smashrun_client_secret=secrets.get(
                "smashrun_client_secret", base_settings.smashrun_client_secret
            ),
            smashrun_redirect_uri=base_settings.smashrun_redirect_uri,
            supabase_url=secrets.get("supabase_url", base_settings.supabase_url),
            supabase_key=secrets.get("supabase_key", base_settings.supabase_key),
            duckdb_path=base_settings.duckdb_path,
            aws_region=base_settings.aws_region,
            environment=base_settings.environment,
            log_level=base_settings.log_level,
        )
    else:
        # Locally: Just load from .env file
        _settings = Settings()

    return _settings
