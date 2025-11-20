"""Configuration management for MyRunStreak.com."""

from pathlib import Path

from pydantic import Field
from pydantic_settings import BaseSettings, SettingsConfigDict


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


# Find env file once at module load
_env_file = find_env_file()


class Settings(BaseSettings):
    """
    Application settings loaded from environment variables.

    These settings are used across Lambda functions and local development.
    """

    model_config = SettingsConfigDict(
        env_file=_env_file,
        env_file_encoding="utf-8",
        case_sensitive=False,
        extra="ignore",
    )

    # SmashRun OAuth Configuration
    smashrun_client_id: str = Field(
        description="SmashRun OAuth Client ID",
    )
    smashrun_client_secret: str = Field(
        description="SmashRun OAuth Client Secret",
    )
    smashrun_redirect_uri: str = Field(
        default="http://localhost:9876/callback",
        description="OAuth redirect URI for authorization code flow",
    )

    # Supabase Configuration
    supabase_url: str = Field(
        description="Supabase project URL",
    )
    supabase_key: str = Field(
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


def get_settings() -> Settings:
    """
    Get application settings (singleton pattern).

    Returns:
        Settings instance loaded from environment
    """
    global _settings
    if _settings is None:
        _settings = Settings()  # type: ignore[call-arg]
    return _settings
