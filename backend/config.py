"""Runtime configuration loaded from env vars."""

from pydantic_settings import BaseSettings, SettingsConfigDict


class Settings(BaseSettings):
    """All env-driven config in one place."""

    model_config = SettingsConfigDict(env_file=".env", extra="ignore")

    environment: str = "dev"
    log_level: str = "INFO"
    cors_allow_origins: str = "*"

    supabase_url: str
    supabase_anon_key: str
    supabase_service_role_key: str
    supabase_jwt_secret: str

    smashrun_client_id: str = ""
    smashrun_client_secret: str = ""
    smashrun_redirect_uri: str = "urn:ietf:wg:oauth:2.0:oob"

    redis_url: str = "redis://localhost:6379/0"
    cache_enabled: bool = True
    cache_default_ttl_seconds: int = 60

    goal_yearly_staleness_days: int = 14
    goal_monthly_staleness_days: int = 3

    # Comma-separated user UUIDs allowed to issue invites (SB-188). Empty = no
    # admins (invite issuance disabled). Set in the deployed env, not committed.
    admin_user_ids: str = ""

    def admin_ids(self) -> set[str]:
        """Parsed set of admin user UUIDs (lowercased, whitespace-trimmed)."""
        return {p.strip().lower() for p in self.admin_user_ids.split(",") if p.strip()}


_settings: Settings | None = None


def get_settings() -> Settings:
    """Singleton accessor — initialize once at first call."""
    global _settings
    if _settings is None:
        _settings = Settings()
    return _settings
