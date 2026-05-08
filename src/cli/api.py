"""API client for stk CLI.

Talks only to api.myrunstreak.run. Bearer JWTs come from cli.session;
the CLI never knows the underlying auth provider's URL or anon key.
"""

from __future__ import annotations

import os
import sys
from typing import Any

import httpx

from cli import session as session_mod
from cli.display import display_error, display_info

DEFAULT_API_URL = "https://api.myrunstreak.run"
TIMEOUT = 30.0


def get_api_url() -> str:
    """Base URL for the myrunstreak API. Override with $STK_API_URL for dev."""
    return os.getenv("STK_API_URL", os.getenv("API_BASE_URL", DEFAULT_API_URL))


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
    return {"Authorization": f"Bearer {s.access_token}"}


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


def request(endpoint: str, params: dict[str, Any] | None = None) -> dict[str, Any]:
    """Authenticated GET. Refreshes the access token transparently on expiry/401."""
    s = _ensure_fresh(_require_session())
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
    return result


def post_request(
    endpoint: str,
    data: dict[str, Any] | None = None,
    params: dict[str, Any] | None = None,
    timeout: float | None = None,
) -> dict[str, Any]:
    """Authenticated POST. Same auto-refresh behavior as request()."""
    s = _ensure_fresh(_require_session())
    url = f"{get_api_url()}/{endpoint.lstrip('/')}"
    request_timeout = timeout if timeout else TIMEOUT
    try:
        response = httpx.post(
            url,
            json=data,
            params=params,
            headers=_auth_headers(s),
            timeout=request_timeout,
        )
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
        response = httpx.post(
            url,
            json=data,
            params=params,
            headers=_auth_headers(refreshed),
            timeout=request_timeout,
        )

    if response.status_code >= 400:
        _exit_with_error(response)

    result: dict[str, Any] = response.json()
    return result
