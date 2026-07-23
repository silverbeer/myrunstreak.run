"""SB-302: PATCH /runs/{activity_id}/audio — record what was playing."""

from __future__ import annotations

import asyncio
from typing import Any
from uuid import uuid4

import pytest
from backend.routes import runs as runs_module
from backend.routes.runs import AudioLogRequest
from fastapi import HTTPException

USER = uuid4()


class _Repo:
    def __init__(self, updated: dict[str, Any] | None) -> None:
        self._updated = updated
        self.calls: list[tuple[Any, ...]] = []

    def __call__(self, _sb: Any) -> _Repo:
        return self

    def set_run_audio(
        self, user_id: Any, activity_id: str, audio_type: Any, audio_note: Any
    ) -> dict[str, Any] | None:
        self.calls.append((user_id, activity_id, audio_type, audio_note))
        return self._updated


def _patch(updated: dict[str, Any] | None, body: AudioLogRequest, monkeypatch: Any) -> Any:
    repo = _Repo(updated)
    monkeypatch.setattr(runs_module, "get_supabase_client", lambda: object())
    monkeypatch.setattr(runs_module, "RunsRepository", repo)
    monkeypatch.setattr(runs_module, "invalidate_user", _noop)
    out = asyncio.run(runs_module.set_run_audio("act-1", body, user_id=USER))
    return out, repo


async def _noop(_uid: Any) -> int:
    return 0


def test_sets_audio_type_and_note(monkeypatch: Any) -> None:
    body = AudioLogRequest(audio_type="podcast", audio_note="Noah Kahan playlist today")
    out, repo = _patch(
        {"audio_type": "podcast", "audio_note": "Noah Kahan playlist today"}, body, monkeypatch
    )
    assert out == {"audio_type": "podcast", "audio_note": "Noah Kahan playlist today"}
    # Scoped to the caller + activity.
    assert repo.calls == [(USER, "act-1", "podcast", "Noah Kahan playlist today")]


def test_clears_audio_when_type_null(monkeypatch: Any) -> None:
    body = AudioLogRequest(audio_type=None, audio_note=None)
    out, _ = _patch({"audio_type": None, "audio_note": None}, body, monkeypatch)
    assert out == {"audio_type": None, "audio_note": None}


def test_404_when_run_not_owned(monkeypatch: Any) -> None:
    body = AudioLogRequest(audio_type="music")
    with pytest.raises(HTTPException) as err:
        _patch(None, body, monkeypatch)
    assert err.value.status_code == 404


def test_rejects_unknown_audio_type() -> None:
    # Literal validation happens at the model boundary (FastAPI returns 422).
    with pytest.raises(ValueError):
        AudioLogRequest(audio_type="spotify")  # type: ignore[arg-type]


def test_note_length_capped() -> None:
    with pytest.raises(ValueError):
        AudioLogRequest(audio_type="podcast", audio_note="x" * 501)
