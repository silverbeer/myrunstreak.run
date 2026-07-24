"""SB-308: the incremental-sync watermark only moves forward, never back."""

from __future__ import annotations

import json
from datetime import date
from pathlib import Path
from typing import Any

import pytest
from cli.commands import sync as sync_mod


@pytest.fixture(autouse=True)
def _tmp_state(monkeypatch: Any, tmp_path: Path) -> Path:
    state = tmp_path / "sync_state.json"
    monkeypatch.setattr(sync_mod, "CONFIG_DIR", tmp_path)
    monkeypatch.setattr(sync_mod, "SYNC_STATE_FILE", state)
    return state


def _written(state: Path) -> str:
    return json.loads(state.read_text())["last_sync_date"]


def test_first_sync_writes_the_date(_tmp_state: Path) -> None:
    sync_mod.update_sync_state(date(2026, 7, 24), 5)
    assert _written(_tmp_state) == "2026-07-24"


def test_forward_sync_advances_watermark(_tmp_state: Path) -> None:
    sync_mod.update_sync_state(date(2026, 6, 1), 3)
    sync_mod.update_sync_state(date(2026, 7, 24), 3)
    assert _written(_tmp_state) == "2026-07-24"


def test_historical_backfill_does_not_regress_watermark(_tmp_state: Path) -> None:
    # Bare sync gets us current...
    sync_mod.update_sync_state(date(2026, 7, 24), 3)
    # ...then a `--year 2022` backfill (until = 2022-12-31) must NOT drag it back.
    sync_mod.update_sync_state(date(2022, 12, 31), 370)
    assert _written(_tmp_state) == "2026-07-24"


def test_get_last_sync_defaults_to_30_days_ago_without_file(_tmp_state: Path) -> None:
    assert not _tmp_state.exists()
    got = sync_mod.get_last_sync_date()
    assert (date.today() - got).days == 30


def test_corrupt_state_is_ignored(_tmp_state: Path) -> None:
    _tmp_state.write_text("{ not json")
    sync_mod.update_sync_state(date(2026, 7, 24), 1)
    assert _written(_tmp_state) == "2026-07-24"
