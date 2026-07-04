"""Shared Supabase env resolution for the STK backup/restore scripts (SB-224)."""

from __future__ import annotations

import os


def resolve_env() -> tuple[str, str]:
    """Return (url, service_key) from the environment.

    Accepts SUPABASE_SERVICE_KEY (matches missing-table) or the longer
    SUPABASE_SERVICE_ROLE_KEY (matches `supabase status -o env`).
    """
    url = os.environ.get("SUPABASE_URL", "").rstrip("/")
    key = os.environ.get("SUPABASE_SERVICE_KEY") or os.environ.get("SUPABASE_SERVICE_ROLE_KEY", "")
    return url, key


def require_env() -> tuple[str, str]:
    """Same as resolve_env but exits with a clear message if either is missing."""
    url, key = resolve_env()
    if not url or not key:
        raise SystemExit(
            "Missing SUPABASE_URL and/or SUPABASE_SERVICE_KEY "
            "(SUPABASE_SERVICE_ROLE_KEY also accepted)."
        )
    return url, key


def is_local(url: str) -> bool:
    """True when the URL points at a local Supabase instance."""
    return any(host in url for host in ("127.0.0.1", "localhost"))
