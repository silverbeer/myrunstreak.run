"""Session storage for stk CLI.

A session is the access/refresh token pair returned by the backend's
/auth/login (or /auth/signup) endpoint, plus the email it belongs to and
the absolute expiry timestamp of the access token.

Stored at ``~/.config/stk/session.json``. The CLI never sees Supabase
URLs or anon keys — those stay on the backend.
"""

from __future__ import annotations

import json
import os
import time
from dataclasses import asdict, dataclass
from pathlib import Path

CONFIG_DIR = Path.home() / ".config" / "stk"
SESSION_FILE = CONFIG_DIR / "session.json"

# Refresh proactively when fewer than this many seconds remain on the access
# token, so a long-running command doesn't get a 401 mid-flight.
_REFRESH_LEEWAY_SECONDS = 60


@dataclass
class Session:
    access_token: str
    refresh_token: str
    expires_at: float
    email: str

    def is_expired(self) -> bool:
        return time.time() >= self.expires_at - _REFRESH_LEEWAY_SECONDS


def save(
    *,
    access_token: str,
    refresh_token: str,
    expires_in: int | None,
    email: str,
) -> Session:
    """Persist a fresh session, computing expires_at from expires_in."""
    expires_at = time.time() + (expires_in if expires_in else 3600)
    session = Session(
        access_token=access_token,
        refresh_token=refresh_token,
        expires_at=expires_at,
        email=email,
    )
    CONFIG_DIR.mkdir(parents=True, exist_ok=True)
    SESSION_FILE.write_text(json.dumps(asdict(session), indent=2))
    os.chmod(SESSION_FILE, 0o600)
    return session


def load() -> Session | None:
    if not SESSION_FILE.exists():
        return None
    try:
        data = json.loads(SESSION_FILE.read_text())
        return Session(**data)
    except (json.JSONDecodeError, OSError, TypeError):
        return None


def clear() -> bool:
    """Delete the session file. Returns True if a file existed."""
    if SESSION_FILE.exists():
        SESSION_FILE.unlink()
        return True
    return False
