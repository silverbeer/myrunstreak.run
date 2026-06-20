"""Admin authorization for privileged actions (SB-188).

Admin status is config-driven via ADMIN_USER_IDS — a small, auditable allowlist
of user UUIDs. No role column on the users table yet; this keeps the surface
minimal until a real role system lands.
"""

from __future__ import annotations

from uuid import UUID

from backend.config import get_settings
from fastapi import HTTPException, status


def require_admin(user_id: UUID) -> None:
    """Raise 403 unless the user is in the ADMIN_USER_IDS allowlist."""
    if str(user_id).lower() not in get_settings().admin_ids():
        raise HTTPException(
            status_code=status.HTTP_403_FORBIDDEN,
            detail="Admin privileges required",
        )
