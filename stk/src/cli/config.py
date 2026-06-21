"""Local stk config (non-secret) — currently the active athlete context.

Stored at ``~/.config/stk/config.json``, separate from the auth session.
"""

from __future__ import annotations

import json
from pathlib import Path
from typing import Any

CONFIG_DIR = Path.home() / ".config" / "stk"
CONFIG_FILE = CONFIG_DIR / "config.json"


def _load() -> dict[str, Any]:
    if not CONFIG_FILE.exists():
        return {}
    try:
        data: dict[str, Any] = json.loads(CONFIG_FILE.read_text())
        return data
    except (ValueError, OSError):
        return {}


def _save(data: dict[str, Any]) -> None:
    CONFIG_DIR.mkdir(parents=True, exist_ok=True)
    CONFIG_FILE.write_text(json.dumps(data, indent=2))


def get_active_athlete() -> dict[str, str] | None:
    """Returns {'id':..., 'name':...} or None."""
    return _load().get("active_athlete")


def set_active_athlete(athlete_id: str, name: str) -> None:
    data = _load()
    data["active_athlete"] = {"id": athlete_id, "name": name}
    _save(data)


def clear_active_athlete() -> None:
    data = _load()
    data.pop("active_athlete", None)
    _save(data)
