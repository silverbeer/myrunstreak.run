"""Local response cache for stk (SQLite).

The CLI re-reads immutable data — your run history never changes; only the tail
grows when a new run is synced. So instead of an arbitrary time-based TTL, this
cache is *version-gated*: large read payloads are stored keyed by a cheap version
token (``GET /runs/head`` → ``count:latest_run_date``). Unchanged token → serve
from disk; changed token → a run was added/removed → the old key misses and the
data is refetched. See ``cli.api.get_run_version`` for the token source.

Stored at ``~/.config/stk/cache.db`` alongside ``config.json`` / ``session.json``.
Everything here fails *open*: any SQLite error is swallowed and treated as a miss,
so the cache can never break a command. Bypass entirely with ``--no-cache`` or
``STK_NO_CACHE=1``.
"""

from __future__ import annotations

import hashlib
import json
import os
import sqlite3
import time
from pathlib import Path
from typing import Any, Literal

from cli import config as config_mod

CACHE_DB: Path = config_mod.CONFIG_DIR / "cache.db"


def db_path() -> Path:
    """Resolve where the cache DB lives.

    Precedence: ``$STK_CACHE_DB`` (one-off override) → the path persisted by
    ``stk cache path`` → the default ``~/.config/stk/cache.db``. Lets the DB be
    parked on a synced volume (iCloud/Dropbox) to share across machines — see
    the ``stk cache path`` warning about SQLite on sync services.
    """
    override = os.getenv("STK_CACHE_DB") or config_mod.get_cache_db()
    return Path(override).expanduser() if override else CACHE_DB


# The literal token stored on reference-class rows (no run-version link).
REFERENCE_TOKEN = "ref"

PolicyClass = Literal["versioned", "reference"]

# Endpoint classification (prefixes match a full path segment).
# Order matters: NEVER is checked before VERSIONED so "runs/head" (the token
# endpoint itself) is never cached even though it starts with "runs".
_NEVER_PREFIXES = ("runs/head", "plan", "auth", "sync-splits")
_VERSIONED_PREFIXES = ("runs", "stats")
_REFERENCE_PREFIXES = ("workouts/exercises", "workouts/templates", "me/roles", "athletes")

# --no-cache flag (set from the root Typer callback in main.py).
_no_cache = False


def set_no_cache(value: bool) -> None:
    global _no_cache
    _no_cache = value


def bypassed() -> bool:
    """True when caching is off for this invocation (flag or env)."""
    return _no_cache or bool(os.getenv("STK_NO_CACHE"))


def _matches(endpoint: str, prefixes: tuple[str, ...]) -> bool:
    e = endpoint.lstrip("/")
    return any(e == p or e.startswith(f"{p}/") for p in prefixes)


def policy(endpoint: str) -> PolicyClass | None:
    """How an endpoint may be cached: version-gated, reference, or not at all."""
    if _matches(endpoint, _NEVER_PREFIXES):
        return None
    if _matches(endpoint, _VERSIONED_PREFIXES):
        return "versioned"
    if _matches(endpoint, _REFERENCE_PREFIXES):
        return "reference"
    return None


# ---------------------------------------------------------------------------
# Storage
# ---------------------------------------------------------------------------

_SCHEMA = """
CREATE TABLE IF NOT EXISTS cache (
    key        TEXT PRIMARY KEY,
    endpoint   TEXT NOT NULL,
    scope      TEXT,
    token      TEXT,
    body       TEXT NOT NULL,
    fetched_at REAL NOT NULL
);
CREATE INDEX IF NOT EXISTS idx_cache_endpoint ON cache(endpoint);
CREATE INDEX IF NOT EXISTS idx_cache_scope    ON cache(scope);
"""


def _connect() -> sqlite3.Connection:
    path = db_path()
    path.parent.mkdir(parents=True, exist_ok=True)
    conn = sqlite3.connect(path)
    # DELETE (rollback) journal, not WAL: WAL's persistent -wal/-shm sidecars
    # sync independently on iCloud/Dropbox and can tear the DB. A single-file
    # rollback journal is far safer when the DB lives on a synced volume, and
    # WAL buys nothing for this tiny single-process workload.
    conn.execute("PRAGMA journal_mode=DELETE")
    conn.executescript(_SCHEMA)
    return conn


def _make_key(endpoint: str, params: dict[str, Any] | None, scope: str, token: str) -> str:
    params_norm = json.dumps(params or {}, sort_keys=True, default=str)
    raw = "|".join([endpoint.lstrip("/"), params_norm, scope, token])
    return hashlib.sha256(raw.encode()).hexdigest()


def get(
    endpoint: str, params: dict[str, Any] | None, scope: str, token: str
) -> dict[str, Any] | list[Any] | None:
    """Return the cached body for this (endpoint, params, scope, token), or None."""
    key = _make_key(endpoint, params, scope, token)
    try:
        with _connect() as conn:
            row = conn.execute("SELECT body FROM cache WHERE key = ?", (key,)).fetchone()
        if row is None:
            return None
        return json.loads(row[0])  # type: ignore[no-any-return]
    except (sqlite3.Error, ValueError, OSError):
        return None


def set(
    endpoint: str,
    params: dict[str, Any] | None,
    scope: str,
    token: str,
    body: dict[str, Any] | list[Any],
) -> None:
    """Store a response body. Silently no-ops on any storage error (fail-open)."""
    key = _make_key(endpoint, params, scope, token)
    try:
        with _connect() as conn:
            conn.execute(
                "INSERT OR REPLACE INTO cache "
                "(key, endpoint, scope, token, body, fetched_at) VALUES (?, ?, ?, ?, ?, ?)",
                (
                    key,
                    endpoint.lstrip("/"),
                    scope,
                    token,
                    json.dumps(body, default=str),
                    time.time(),
                ),
            )
    except (sqlite3.Error, ValueError, OSError):
        return


def sweep_stale(scope: str, current_token: str) -> int:
    """Drop version-gated rows for ``scope`` whose token isn't ``current_token``.

    Reference rows (``token = 'ref'``) are preserved. Housekeeping only —
    correctness already comes from the token being part of the key.
    """
    try:
        with _connect() as conn:
            cur = conn.execute(
                "DELETE FROM cache WHERE scope = ? AND token NOT IN (?, ?)",
                (scope, current_token, REFERENCE_TOKEN),
            )
            return cur.rowcount or 0
    except (sqlite3.Error, OSError):
        return 0


def invalidate_scope(scope: str) -> int:
    """Delete every cached row for a scope — called after a successful write."""
    try:
        with _connect() as conn:
            cur = conn.execute("DELETE FROM cache WHERE scope = ?", (scope,))
            return cur.rowcount or 0
    except (sqlite3.Error, OSError):
        return 0


def clear_all() -> int:
    try:
        with _connect() as conn:
            cur = conn.execute("DELETE FROM cache")
            return cur.rowcount or 0
    except (sqlite3.Error, OSError):
        return 0


def stats() -> dict[str, Any]:
    """Summary for ``stk cache stats``: row count, db size, per-endpoint breakdown."""
    try:
        with _connect() as conn:
            rows = conn.execute("SELECT COUNT(*) FROM cache").fetchone()[0]
            by_endpoint = dict(
                conn.execute(
                    "SELECT endpoint, COUNT(*) FROM cache GROUP BY endpoint ORDER BY 2 DESC"
                ).fetchall()
            )
        path = db_path()
        size_bytes = path.stat().st_size if path.exists() else 0
        return {"rows": rows, "size_bytes": size_bytes, "by_endpoint": by_endpoint}
    except (sqlite3.Error, OSError):
        return {"rows": 0, "size_bytes": 0, "by_endpoint": {}}
