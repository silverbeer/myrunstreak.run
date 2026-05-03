"""Smoke tests against the FastAPI app — health endpoint + 401 on protected
routes when no token is provided.
"""

from fastapi.testclient import TestClient


def _client() -> TestClient:
    from backend.app import create_app

    return TestClient(create_app())


def test_health_returns_ok() -> None:
    r = _client().get("/health")
    assert r.status_code == 200
    assert r.json() == {"status": "ok"}


def test_protected_route_401_without_token() -> None:
    r = _client().get("/stats/overall")
    assert r.status_code == 401


def test_protected_route_401_with_garbage_token() -> None:
    r = _client().get(
        "/stats/overall",
        headers={"Authorization": "Bearer garbage.token.here"},
    )
    assert r.status_code == 401


def test_cors_preflight_returns_2xx() -> None:
    r = _client().options(
        "/stats/overall",
        headers={
            "Origin": "https://myrunstreak.run",
            "Access-Control-Request-Method": "GET",
            "Access-Control-Request-Headers": "authorization,content-type",
        },
    )
    assert r.status_code == 200
    assert r.headers.get("access-control-allow-origin") == "*"
