"""SB-307: `stk last` fetches the most recent run and renders its route card."""

from __future__ import annotations

from typing import Any

from cli.commands import runs as runs_cmd


def test_last_calls_track_for_most_recent(monkeypatch: Any) -> None:
    calls: list[str] = []

    def fake_request(endpoint: str, params: dict[str, Any] | None = None) -> dict[str, Any]:
        calls.append(endpoint)
        if endpoint == "runs/recent":
            assert params == {"limit": 1}
            return {"runs": [{"activity_id": "46444589"}]}
        return {"activity_id": "46444589", "has_track": True, "lat": [1, 2], "lon": [1, 2]}

    rendered: list[dict[str, Any]] = []
    monkeypatch.setattr(runs_cmd.api, "request", fake_request)
    monkeypatch.setattr(runs_cmd.display, "display_route_card", lambda d: rendered.append(d))

    runs_cmd.last(json_output=False)

    assert calls == ["runs/recent", "runs/46444589/track"]
    assert rendered and rendered[0]["activity_id"] == "46444589"


def test_last_handles_no_runs(monkeypatch: Any) -> None:
    infos: list[str] = []
    monkeypatch.setattr(runs_cmd.api, "request", lambda *_a, **_k: {"runs": []})
    monkeypatch.setattr(runs_cmd.display, "display_info", lambda m: infos.append(m))
    # Should not raise or try to render a card.
    monkeypatch.setattr(
        runs_cmd.display,
        "display_route_card",
        lambda _d: (_ for _ in ()).throw(AssertionError("should not render")),
    )

    runs_cmd.last(json_output=False)
    assert infos and "No runs" in infos[0]
