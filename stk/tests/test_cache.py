"""Tests for the stk local response cache (cli.cache) and its wiring into cli.api."""

from __future__ import annotations

import time
from typing import Any

import pytest

from cli import api, cache
from cli import session as session_mod


@pytest.fixture(autouse=True)
def _isolate_cache(tmp_path, monkeypatch):  # type: ignore[no-untyped-def]
    """Point the cache DB at a temp file and reset per-process memo state."""
    monkeypatch.setattr(cache, "CACHE_DB", tmp_path / "cache.db")
    monkeypatch.setattr(cache, "_no_cache", False)
    monkeypatch.delenv("STK_NO_CACHE", raising=False)
    # Isolate db_path() resolution from the real user config / env.
    monkeypatch.delenv("STK_CACHE_DB", raising=False)
    monkeypatch.setattr(cache.config_mod, "get_cache_db", lambda: None)
    monkeypatch.setattr(api, "_run_version", {})
    monkeypatch.setattr(api, "_swept", set())


# ---------------------------------------------------------------------------
# policy()
# ---------------------------------------------------------------------------


@pytest.mark.parametrize(
    ("endpoint", "expected"),
    [
        ("runs", "versioned"),
        ("runs/recent", "versioned"),
        ("stats/streaks", "versioned"),
        ("stats/splits", "versioned"),
        ("workouts/exercises", "reference"),
        ("workouts/templates", "reference"),
        ("workouts/templates/abc", "reference"),
        ("me/roles", "reference"),
        ("athletes", "reference"),
        ("athletes/123/coaches", "reference"),
        ("runs/head", None),
        ("plan/2026-07", None),
        ("auth/refresh", None),
        ("sync-splits/status", None),
        ("workouts/sessions", None),  # mutates independently of run token — uncached in v1
    ],
)
def test_policy_classification(endpoint: str, expected: str | None) -> None:
    assert cache.policy(endpoint) == expected


# ---------------------------------------------------------------------------
# storage round-trip
# ---------------------------------------------------------------------------


def test_get_set_round_trip() -> None:
    body = {"count": 2, "runs": [{"id": "a"}, {"id": "b"}]}
    assert cache.get("runs/recent", {"limit": 10}, "me@x.com", "842:2026-07-16") is None
    cache.set("runs/recent", {"limit": 10}, "me@x.com", "842:2026-07-16", body)
    assert cache.get("runs/recent", {"limit": 10}, "me@x.com", "842:2026-07-16") == body


def test_params_are_part_of_key() -> None:
    cache.set("runs", {"offset": 0}, "me@x.com", "t", {"page": 0})
    assert cache.get("runs", {"offset": 50}, "me@x.com", "t") is None


def test_token_change_is_a_miss_and_sweeps_old() -> None:
    cache.set("runs/recent", None, "me@x.com", "tokenA", {"v": "A"})
    # New token → miss.
    assert cache.get("runs/recent", None, "me@x.com", "tokenB") is None
    # Old row still present until swept.
    assert cache.get("runs/recent", None, "me@x.com", "tokenA") == {"v": "A"}
    removed = cache.sweep_stale("me@x.com", "tokenB")
    assert removed == 1
    assert cache.get("runs/recent", None, "me@x.com", "tokenA") is None


def test_sweep_preserves_reference_rows() -> None:
    cache.set("workouts/exercises", None, "me@x.com", cache.REFERENCE_TOKEN, {"ref": True})
    cache.set("runs", None, "me@x.com", "old", {"stale": True})
    cache.sweep_stale("me@x.com", "current")
    # Reference row survives; stale versioned row is gone.
    assert cache.get("workouts/exercises", None, "me@x.com", cache.REFERENCE_TOKEN) == {"ref": True}
    assert cache.get("runs", None, "me@x.com", "old") is None


def test_scope_isolates_entries() -> None:
    cache.set("runs/recent", None, "coach@x.com", "t", {"who": "coach"})
    assert cache.get("runs/recent", None, "athlete@x.com", "t") is None
    assert cache.get("runs/recent", None, "coach@x.com", "t") == {"who": "coach"}


def test_invalidate_scope() -> None:
    cache.set("runs", None, "a@x.com", "t", {"1": 1})
    cache.set("stats/overall", None, "a@x.com", "t", {"2": 2})
    cache.set("runs", None, "b@x.com", "t", {"3": 3})
    removed = cache.invalidate_scope("a@x.com")
    assert removed == 2
    assert cache.get("runs", None, "a@x.com", "t") is None
    assert cache.get("runs", None, "b@x.com", "t") == {"3": 3}


def test_clear_all_and_stats() -> None:
    cache.set("runs", None, "a@x.com", "t", {"1": 1})
    cache.set("stats/overall", None, "a@x.com", "t", {"2": 2})
    s = cache.stats()
    assert s["rows"] == 2
    assert s["by_endpoint"] == {"runs": 1, "stats/overall": 1}
    assert cache.clear_all() == 2
    assert cache.stats()["rows"] == 0


# ---------------------------------------------------------------------------
# db_path() resolution
# ---------------------------------------------------------------------------


def test_db_path_defaults_to_constant(monkeypatch) -> None:  # type: ignore[no-untyped-def]
    assert cache.db_path() == cache.CACHE_DB


def test_db_path_env_overrides_config(tmp_path, monkeypatch) -> None:  # type: ignore[no-untyped-def]
    monkeypatch.setattr(cache.config_mod, "get_cache_db", lambda: str(tmp_path / "cfg.db"))
    monkeypatch.setenv("STK_CACHE_DB", str(tmp_path / "env.db"))
    assert cache.db_path() == tmp_path / "env.db"


def test_db_path_uses_config_when_no_env(tmp_path, monkeypatch) -> None:  # type: ignore[no-untyped-def]
    monkeypatch.setattr(cache.config_mod, "get_cache_db", lambda: str(tmp_path / "cfg.db"))
    assert cache.db_path() == tmp_path / "cfg.db"


def test_configured_path_is_where_data_lands(tmp_path, monkeypatch) -> None:  # type: ignore[no-untyped-def]
    target = tmp_path / "synced" / "cache.db"
    monkeypatch.setattr(cache.config_mod, "get_cache_db", lambda: str(target))
    cache.set("runs", None, "me@x.com", "t", {"ok": 1})
    assert target.exists()
    assert cache.get("runs", None, "me@x.com", "t") == {"ok": 1}


# ---------------------------------------------------------------------------
# bypass
# ---------------------------------------------------------------------------


def test_bypassed_honors_flag_and_env(monkeypatch) -> None:  # type: ignore[no-untyped-def]
    assert cache.bypassed() is False
    cache.set_no_cache(True)
    assert cache.bypassed() is True
    cache.set_no_cache(False)
    assert cache.bypassed() is False
    monkeypatch.setenv("STK_NO_CACHE", "1")
    assert cache.bypassed() is True


# ---------------------------------------------------------------------------
# request() integration — the first httpx-mock in this package
# ---------------------------------------------------------------------------


class _Resp:
    def __init__(self, status_code: int, payload: Any) -> None:
        self.status_code = status_code
        self._payload = payload

    def json(self) -> Any:
        return self._payload


def _install_fakes(monkeypatch, *, head_payload: Any, head_status: int = 200):  # type: ignore[no-untyped-def]
    """Wire a fresh session, no act-as, and a counting fake httpx.get.

    Returns a dict of call counters: {"head": n, "data": n}.
    """
    fresh = session_mod.Session(
        access_token="a", refresh_token="r", expires_at=time.time() + 9999, email="me@x.com"
    )
    monkeypatch.setattr(api.session_mod, "load", lambda: fresh)
    monkeypatch.setattr(api.config_mod, "get_active_athlete", lambda: None)

    calls = {"head": 0, "data": 0}

    def fake_get(url: str, **kwargs: Any) -> _Resp:
        if url.endswith("/runs/head"):
            calls["head"] += 1
            return _Resp(head_status, head_payload)
        calls["data"] += 1
        return _Resp(200, {"count": 1, "runs": [{"id": "x"}]})

    monkeypatch.setattr(api.httpx, "get", fake_get)
    return calls


def test_request_serves_second_call_from_cache(monkeypatch) -> None:  # type: ignore[no-untyped-def]
    calls = _install_fakes(
        monkeypatch, head_payload={"count": 842, "latest_run_date": "2026-07-16"}
    )

    first = api.request("runs/recent", {"limit": 10})
    second = api.request("runs/recent", {"limit": 10})

    assert first == second == {"count": 1, "runs": [{"id": "x"}]}
    assert calls["data"] == 1  # second call hit the cache — no data round-trip
    assert calls["head"] == 1  # head fetched once per process (memoized)


def test_request_refetches_when_token_changes(monkeypatch) -> None:  # type: ignore[no-untyped-def]
    calls = _install_fakes(
        monkeypatch, head_payload={"count": 842, "latest_run_date": "2026-07-16"}
    )
    api.request("runs/recent", {"limit": 10})
    assert calls["data"] == 1

    # A new run lands → token advances. Reset the per-process memo (mimics a new
    # invocation) and bump the head count.
    monkeypatch.setattr(api, "_run_version", {})
    monkeypatch.setattr(api, "_swept", set())
    calls2 = _install_fakes(
        monkeypatch, head_payload={"count": 843, "latest_run_date": "2026-07-17"}
    )
    api.request("runs/recent", {"limit": 10})
    assert calls2["data"] == 1  # refetched under the new token


def test_request_no_cache_env_always_fetches(monkeypatch) -> None:  # type: ignore[no-untyped-def]
    monkeypatch.setenv("STK_NO_CACHE", "1")
    calls = _install_fakes(
        monkeypatch, head_payload={"count": 842, "latest_run_date": "2026-07-16"}
    )
    api.request("runs/recent", {"limit": 10})
    api.request("runs/recent", {"limit": 10})
    assert calls["data"] == 2  # never cached
    assert calls["head"] == 0  # head not even consulted when bypassed


def test_request_fails_open_when_head_unavailable(monkeypatch) -> None:  # type: ignore[no-untyped-def]
    # Backend without /runs/head yet → 500/404 → token None → go live, don't cache.
    calls = _install_fakes(monkeypatch, head_payload={}, head_status=500)
    api.request("runs/recent", {"limit": 10})
    api.request("runs/recent", {"limit": 10})
    assert calls["data"] == 2  # no caching without a verifiable token


def test_reference_endpoint_cached_without_head(monkeypatch) -> None:  # type: ignore[no-untyped-def]
    calls = _install_fakes(monkeypatch, head_payload={}, head_status=500)
    api.request("workouts/exercises")
    api.request("workouts/exercises")
    assert calls["data"] == 1  # reference class doesn't need the run token
    assert calls["head"] == 0
