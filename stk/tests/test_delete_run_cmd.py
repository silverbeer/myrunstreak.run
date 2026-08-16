"""Tests for `stk delete` — removing an imported run (SB-621)."""

from __future__ import annotations

from typing import Any

import pytest
import typer

from cli.commands import delete_run as cmd

IMPORTED = {
    "activity_id": "gpx-abc123",
    "date": "2026-08-08T10:50:35-04:00",
    "distance_km": 3.24,
    "is_imported": True,
}


def _wire(monkeypatch: Any, run: dict[str, Any]) -> list[str]:
    """Stub the API; returns the list of endpoints DELETEd."""
    deleted: list[str] = []
    monkeypatch.setattr(cmd, "request", lambda _endpoint: run)
    monkeypatch.setattr(cmd, "delete_request", lambda endpoint: deleted.append(endpoint))
    return deleted


def test_deletes_an_imported_run_when_confirmed(monkeypatch: Any) -> None:
    deleted = _wire(monkeypatch, IMPORTED)
    monkeypatch.setattr(typer, "confirm", lambda *_a, **_k: True)

    cmd.delete_run(activity_id="gpx-abc123", yes=False)

    assert deleted == ["runs/gpx-abc123"]


def test_yes_flag_skips_the_prompt(monkeypatch: Any) -> None:
    deleted = _wire(monkeypatch, IMPORTED)

    def _no_prompt(*_a: Any, **_k: Any) -> bool:
        raise AssertionError("should not prompt when --yes is passed")

    monkeypatch.setattr(typer, "confirm", _no_prompt)

    cmd.delete_run(activity_id="gpx-abc123", yes=True)

    assert deleted == ["runs/gpx-abc123"]


def test_declining_the_prompt_deletes_nothing(monkeypatch: Any) -> None:
    deleted = _wire(monkeypatch, IMPORTED)

    def _abort(*_a: Any, **_k: Any) -> bool:
        raise typer.Abort()

    monkeypatch.setattr(typer, "confirm", _abort)

    with pytest.raises(typer.Abort):
        cmd.delete_run(activity_id="gpx-abc123", yes=False)

    assert deleted == []


def test_synced_run_is_refused_before_any_delete(monkeypatch: Any) -> None:
    deleted = _wire(monkeypatch, {**IMPORTED, "is_imported": False})
    monkeypatch.setattr(typer, "confirm", lambda *_a, **_k: True)

    with pytest.raises(typer.Exit):
        cmd.delete_run(activity_id="act-42", yes=True)

    assert deleted == []
