"""Tests for splits sync wiring — store_run_splits + backfill, with mocks."""

from __future__ import annotations

from unittest.mock import MagicMock
from uuid import uuid4

from backend.routes.sync import store_run_splits
from src.shared.models import Split

RUN_ID = uuid4()


def _splits() -> list[Split]:
    return [
        Split(distance=1.0, seconds=480.0, speed=12.0, heartRate=150),
        Split(distance=2.0, seconds=970.0, speed=12.1, heartRate=155),
        Split(distance=3.0, seconds=1455.0, speed=12.4, heartRate=158),
    ]


def test_store_run_splits_numbers_and_marks() -> None:
    api = MagicMock()
    api.get_activity_splits.return_value = [{"raw": "ignored by mocked parse"}]
    api.parse_splits.return_value = _splits()
    repo = MagicMock()

    count = store_run_splits(api, repo, RUN_ID, "activity-123", unit="mi")

    assert count == 3
    api.get_activity_splits.assert_called_once_with("activity-123", unit="mi")
    # one upsert per split, with 1-based split_number and unit applied
    numbers = [c.args[1]["split_number"] for c in repo.upsert_split.call_args_list]
    units = {c.args[1]["split_unit"] for c in repo.upsert_split.call_args_list}
    assert numbers == [1, 2, 3]
    assert units == {"mi"}
    # mile distances converted to km in the stored rows
    first = repo.upsert_split.call_args_list[0].args[1]
    assert first["cumulative_distance_km"] > 1.6  # 1 mi ≈ 1.609 km
    repo.set_has_splits.assert_called_once_with(RUN_ID, True)
