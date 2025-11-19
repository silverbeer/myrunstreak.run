"""Configuration management for MyRunStreak.com."""

from pydantic import Field
from pydantic_settings import BaseSettings, SettingsConfigDict


class Settings(BaseSettings):
    """
    Application settings loaded from environment variables.

    These settings are used across Lambda functions and local development.
    """

    model_config = SettingsConfigDict(
        env_file=".env",
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
        default="http://localhost:8000/callback",
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
