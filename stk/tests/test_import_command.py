"""Tests for `stk import` — single activity file upload (SB-99)."""

from __future__ import annotations

from pathlib import Path
from typing import Any

import pytest
import typer

from cli.commands import import_file

IMPORTED = {
    "status": "imported",
    "activity_id": "gpx-abc123",
    "run_id": "3f0d0f6e-0000-0000-0000-000000000000",
    "distance_km": 8.05,
    "duration_seconds": 2700.0,
    "start_date_time_local": "2026-08-10T07:15:00-04:00",
    "has_track": True,
}


def _capture(monkeypatch: Any, result: dict[str, Any]) -> list[dict[str, Any]]:
    """Swap the HTTP call for a recorder; returns the list of calls made."""
    calls: list[dict[str, Any]] = []

    def _post_file(
        endpoint: str,
        filename: str,
        content: bytes,
        form: dict[str, str] | None = None,
        timeout: float | None = None,
    ) -> dict[str, Any]:
        calls.append({"endpoint": endpoint, "filename": filename, "content": content, "form": form})
        return result

    monkeypatch.setattr(import_file, "post_file", _post_file)
    return calls


def test_import_uploads_the_file_and_timezone(tmp_path: Path, monkeypatch: Any) -> None:
    calls = _capture(monkeypatch, IMPORTED)
    gpx = tmp_path / "run.gpx"
    gpx.write_bytes(b"<gpx/>")

    import_file.import_activity(path=gpx, timezone="America/Denver", json_output=False)

    assert calls == [
        {
            "endpoint": "import/activity",
            "filename": "run.gpx",
            "content": b"<gpx/>",
            "form": {"timezone": "America/Denver"},
        }
    ]


def test_import_reports_a_duplicate_without_erroring(tmp_path: Path, monkeypatch: Any) -> None:
    _capture(monkeypatch, {**IMPORTED, "status": "duplicate"})
    gpx = tmp_path / "run.gpx"
    gpx.write_bytes(b"<gpx/>")

    # A re-upload is a normal outcome, so it must not exit non-zero.
    import_file.import_activity(path=gpx, timezone="America/New_York", json_output=False)


def test_missing_file_exits_before_uploading(tmp_path: Path, monkeypatch: Any) -> None:
    calls = _capture(monkeypatch, IMPORTED)
    with pytest.raises(typer.Exit):
        import_file.import_activity(
            path=tmp_path / "nope.gpx", timezone="America/New_York", json_output=False
        )
    assert calls == []


def test_unsupported_extension_exits_before_uploading(tmp_path: Path, monkeypatch: Any) -> None:
    calls = _capture(monkeypatch, IMPORTED)
    fit = tmp_path / "run.fit"
    fit.write_bytes(b"\x0e\x10")

    with pytest.raises(typer.Exit):
        import_file.import_activity(path=fit, timezone="America/New_York", json_output=False)
    assert calls == []
