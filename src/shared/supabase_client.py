"""Supabase client connection utilities for MyRunStreak.com."""

import logging
from functools import lru_cache
from typing import Any

from pydantic import Field
from pydantic_settings import BaseSettings, SettingsConfigDict
from supabase import Client, create_client

logger = logging.getLogger(__name__)


class SupabaseSettings(BaseSettings):
    """
    Supabase connection settings loaded from environment variables.

    Attributes:
        supabase_url: Supabase project URL (local or production)
        supabase_key: Supabase service role key (bypasses RLS for Lambda)
    """

    model_config = SettingsConfigDict(
        env_file=".env",
        env_file_encoding="utf-8",
        case_sensitive=False,
        extra="ignore",
    )

    supabase_url: str = Field(
        description="Supabase project URL",
        examples=["http://127.0.0.1:54321", "https://xxx.supabase.co"],
    )

    supabase_key: str = Field(
        description="Supabase service role key (for Lambda/backend access)",
    )


@lru_cache
def get_supabase_settings() -> SupabaseSettings:
    """
    Get Supabase settings (cached singleton pattern).

    Returns:
        SupabaseSettings instance loaded from environment

    Raises:
        ValidationError: If required environment variables are missing
    """
    return SupabaseSettings()  # type: ignore[call-arg]


def get_supabase_client() -> Client:
    """
    Get authenticated Supabase client.

    Uses service role key to bypass Row Level Security (RLS).
    This is safe for backend Lambda functions that enforce their own authorization.

    Returns:
        Supabase client instance

    Example:
        ```python
        supabase = get_supabase_client()
        result = supabase.table("runs").select("*").eq("user_id", user_id).execute()
        ```
    """
    settings = get_supabase_settings()

    logger.debug(f"Connecting to Supabase at {settings.supabase_url}")

    return create_client(settings.supabase_url, settings.supabase_key)


def test_connection() -> dict[str, Any]:
    """
    Test Supabase connection by querying a simple table.

    Returns:
        Dict with connection status and user count

    Raises:
        Exception: If connection fails
    """
    try:
        supabase = get_supabase_client()

        # Query users table to verify connection
        result = supabase.table("users").select("count", count="exact").execute()

        return {
            "status": "connected",
            "user_count": result.count,
            "supabase_url": get_supabase_settings().supabase_url,
        }

    except Exception as e:
        logger.error(f"Supabase connection test failed: {e}")
        raise
