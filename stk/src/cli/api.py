"""API client for stk CLI.

Talks only to api.myrunstreak.run. Bearer JWTs come from cli.session;
the CLI never knows the underlying auth provider's URL or anon key.
"""

from __future__ import annotations

import os
import sys
from typing import Any

import httpx

from cli import cache as cache_mod
from cli import config as config_mod
from cli import session as session_mod
from cli.display import display_error, display_info

DEFAULT_API_URL = "https://api.myrunstreak.run"
TIMEOUT = 30.0

# Per-process memo of the run-version token, keyed by session scope. One
# ``GET /runs/head`` per CLI invocation gates every version-cached read.
_run_version: dict[str, str | None] = {}
# Scopes whose stale cache rows have already been swept this invocation.
_swept: set[str] = set()


def get_api_url() -> str:
    """Base URL for the myrunstreak API.

    Precedence: ``$STK_API_URL`` / ``$API_BASE_URL`` (one-off dev override) →
    the env persisted by ``stk auth login --env`` → prod default.
    """
    override = os.getenv("STK_API_URL") or os.getenv("API_BASE_URL")
    if override:
        return override
    return config_mod.get_api_url_override() or DEFAULT_API_URL


# ---------------------------------------------------------------------------
# Unauthenticated calls — login/signup/refresh use these.
# ---------------------------------------------------------------------------


def post_unauth(
    endpoint: str,
    data: dict[str, Any] | None = None,
    timeout: float | None = None,
) -> dict[str, Any]:
    """POST without injecting auth — for /auth/login, /auth/signup, /auth/refresh."""
    url = f"{get_api_url()}/{endpoint.lstrip('/')}"
    try:
        response = httpx.post(url, json=data, timeout=timeout or TIMEOUT)
        response.raise_for_status()
        result: dict[str, Any] = response.json()
        return result
    except httpx.HTTPStatusError as e:
        _exit_with_error(e.response)
    except httpx.TimeoutException:
        display_error(f"Request timed out after {timeout or TIMEOUT}s")
        sys.exit(1)
    except httpx.RequestError as e:
        display_error(f"Request failed: {e}")
        sys.exit(1)


# ---------------------------------------------------------------------------
# Authenticated calls — load session, attach Bearer, refresh on 401.
# ---------------------------------------------------------------------------


def _require_session() -> session_mod.Session:
    s = session_mod.load()
    if s is None:
        display_error("Not logged in")
        display_info("Run 'stk auth login' to authenticate")
        sys.exit(1)
    return s


def _refresh_session(s: session_mod.Session) -> session_mod.Session | None:
    """Try to refresh; return new session or None if refresh failed."""
    try:
        data = post_unauth("auth/refresh", {"refresh_token": s.refresh_token})
    except SystemExit:
        return None
    return session_mod.save(
        access_token=data["access_token"],
        refresh_token=data["refresh_token"],
        expires_in=data.get("expires_in"),
        email=s.email,
    )


def _ensure_fresh(s: session_mod.Session) -> session_mod.Session:
    if not s.is_expired():
        return s
    refreshed = _refresh_session(s)
    if refreshed is None:
        display_error("Session expired and refresh failed")
        display_info("Run 'stk auth login' to sign in again")
        sys.exit(1)
    return refreshed


def _auth_headers(s: session_mod.Session) -> dict[str, str]:
    headers = {"Authorization": f"Bearer {s.access_token}"}
    # Act-as: when an active athlete is set, workout calls target them (SB-198).
    # Other endpoints ignore the header.
    active = config_mod.get_active_athlete()
    if active:
        headers["X-Act-As-Athlete"] = active["id"]
    return headers


def _exit_with_error(response: httpx.Response) -> None:
    """Print a useful message from a non-2xx response, then exit."""
    detail = response.text
    try:
        body = response.json()
        if isinstance(body, dict):
            detail = body.get("detail") or body.get("message") or detail
    except ValueError:
        pass
    display_error(f"HTTP {response.status_code}: {detail}")
    sys.exit(1)


def get_run_version(s: session_mod.Session, scope: str) -> str | None:
    """Run-history version token (``count:latest_run_date``) for local-cache gating.

    One tiny live ``GET /runs/head`` per process (memoized by scope). Returns
    None on any failure — endpoint missing (backend not yet deployed), network
    error, or non-2xx — so the caller falls back to a live, uncached read. We
    never serve possibly-stale data we couldn't verify.
    """
    if scope in _run_version:
        return _run_version[scope]
    token: str | None = None
    try:
        response = httpx.get(
            f"{get_api_url()}/runs/head", headers=_auth_headers(s), timeout=TIMEOUT
        )
        if response.status_code == 200:
            data = response.json()
            token = f"{data.get('count')}:{data.get('latest_run_date')}"
    except (httpx.HTTPError, ValueError):
        token = None
    _run_version[scope] = token
    return token


def request(endpoint: str, params: dict[str, Any] | None = None) -> dict[str, Any]:
    """Authenticated GET. Refreshes the access token transparently on expiry/401.

    Read-through the local cache (``cli.cache``) for cacheable endpoints: a hit
    returns immediately with no network round-trip; a miss fetches live and
    stores the result. Gated by a run-version token so a newly-synced run busts
    the cache automatically. Bypass with ``--no-cache`` / ``STK_NO_CACHE``.
    """
    s = _ensure_fresh(_require_session())
    scope = s.email or "anon"

    cls = cache_mod.policy(endpoint)
    token: str | None = None
    use_cache = cls is not None and not cache_mod.bypassed()
    if use_cache:
        if cls == "versioned":
            token = get_run_version(s, scope)
            if token is None:
                use_cache = False  # can't verify freshness → go live, don't cache
            elif scope not in _swept:
                cache_mod.sweep_stale(scope, token)
                _swept.add(scope)
        else:  # reference
            token = cache_mod.REFERENCE_TOKEN
    if use_cache and token is not None:
        hit = cache_mod.get(endpoint, params, scope, token)
        if hit is not None:
            return hit  # type: ignore[return-value]

    url = f"{get_api_url()}/{endpoint.lstrip('/')}"
    try:
        response = httpx.get(url, params=params, headers=_auth_headers(s), timeout=TIMEOUT)
    except httpx.TimeoutException:
        display_error(f"Request timed out after {TIMEOUT}s")
        sys.exit(1)
    except httpx.RequestError as e:
        display_error(f"Request failed: {e}")
        sys.exit(1)

    if response.status_code == 401:
        refreshed = _refresh_session(s)
        if refreshed is None:
            display_error("Session expired")
            display_info("Run 'stk auth login' to sign in again")
            sys.exit(1)
        response = httpx.get(url, params=params, headers=_auth_headers(refreshed), timeout=TIMEOUT)

    if response.status_code >= 400:
        _exit_with_error(response)

    result: dict[str, Any] = response.json()
    if use_cache and token is not None:
        cache_mod.set(endpoint, params, scope, token, result)
    return result


def delete_request(endpoint: str, timeout: float | None = None) -> None:
    """Authenticated DELETE. Same auto-refresh behavior; expects a 2xx/204."""
    s = _ensure_fresh(_require_session())
    url = f"{get_api_url()}/{endpoint.lstrip('/')}"
    request_timeout = timeout if timeout else TIMEOUT
    try:
        response = httpx.delete(url, headers=_auth_headers(s), timeout=request_timeout)
    except httpx.TimeoutException:
        display_error(f"Request timed out after {request_timeout}s")
        sys.exit(1)
    except httpx.RequestError as e:
        display_error(f"Request failed: {e}")
        sys.exit(1)

    if response.status_code == 401:
        refreshed = _refresh_session(s)
        if refreshed is None:
            display_error("Session expired")
            display_info("Run 'stk auth login' to sign in again")
            sys.exit(1)
        response = httpx.delete(url, headers=_auth_headers(refreshed), timeout=request_timeout)

    if response.status_code >= 400:
        _exit_with_error(response)

    # A write may change reference data (version-gating only covers run data);
    # drop this scope's local cache so the next read refetches.
    cache_mod.invalidate_scope(s.email or "anon")


def _write_request(
    method: str,
    endpoint: str,
    data: dict[str, Any] | None = None,
    params: dict[str, Any] | None = None,
    timeout: float | None = None,
) -> dict[str, Any]:
    """Authenticated write (POST/PATCH/...). Same auto-refresh behavior as request()."""
    s = _ensure_fresh(_require_session())
    url = f"{get_api_url()}/{endpoint.lstrip('/')}"
    request_timeout = timeout if timeout else TIMEOUT

    def _send(sess: Any) -> httpx.Response:
        return httpx.request(
            method,
            url,
            json=data,
            params=params,
            headers=_auth_headers(sess),
            timeout=request_timeout,
        )

    try:
        response = _send(s)
    except httpx.TimeoutException:
        display_error(f"Request timed out after {request_timeout}s")
        sys.exit(1)
    except httpx.RequestError as e:
        display_error(f"Request failed: {e}")
        sys.exit(1)

    if response.status_code == 401:
        refreshed = _refresh_session(s)
        if refreshed is None:
            display_error("Session expired")
            display_info("Run 'stk auth login' to sign in again")
            sys.exit(1)
        response = _send(refreshed)

    if response.status_code >= 400:
        _exit_with_error(response)

    cache_mod.invalidate_scope(s.email or "anon")
    result: dict[str, Any] = response.json()
    return result


def post_request(
    endpoint: str,
    data: dict[str, Any] | None = None,
    params: dict[str, Any] | None = None,
    timeout: float | None = None,
) -> dict[str, Any]:
    """Authenticated POST. Same auto-refresh behavior as request()."""
    return _write_request("POST", endpoint, data, params, timeout)


def patch_request(
    endpoint: str,
    data: dict[str, Any] | None = None,
    params: dict[str, Any] | None = None,
    timeout: float | None = None,
) -> dict[str, Any]:
    """Authenticated PATCH. Same auto-refresh behavior as request()."""
    return _write_request("PATCH", endpoint, data, params, timeout)
