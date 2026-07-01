"""CORS preflight must allow the headers browser clients actually send.

The coach web view (SB-211) reads an athlete's workouts with the
`X-Act-As-Athlete` header; if the CORS preflight rejects it, the browser blocks
the call and the athlete detail page fails to load. This guards that.
"""

from __future__ import annotations

from backend.app import create_app
from fastapi.testclient import TestClient


def _preflight(request_headers: str) -> str:
    client = TestClient(create_app())
    resp = client.options(
        "/workouts/sessions",
        headers={
            "Origin": "http://localhost:5174",
            "Access-Control-Request-Method": "GET",
            "Access-Control-Request-Headers": request_headers,
        },
    )
    assert resp.status_code == 200, resp.status_code
    return resp.headers.get("access-control-allow-headers", "").lower()


def test_preflight_allows_act_as_athlete_header() -> None:
    allowed = _preflight("authorization,x-act-as-athlete")
    assert "x-act-as-athlete" in allowed


def test_preflight_still_allows_authorization() -> None:
    allowed = _preflight("authorization,content-type")
    assert "authorization" in allowed
    assert "content-type" in allowed
