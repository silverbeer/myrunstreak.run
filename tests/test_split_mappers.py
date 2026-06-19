"""Tests for split_to_dict — the mile→km conversion is the correctness-critical bit."""

from __future__ import annotations

from uuid import uuid4

import pytest

from src.shared.models import Split
from src.shared.supabase_ops.mappers import MILES_TO_KM, split_to_dict

RUN_ID = uuid4()


def _split(distance: float, seconds: float) -> Split:
    # alias fields: distance, seconds, speed, heartRate
    return Split(distance=distance, seconds=seconds, speed=10.0, heartRate=150)


def test_mile_split_distance_converted_to_km() -> None:
    # A mile-boundary split reports distance in miles; the column is km.
    s = _split(distance=2.0, seconds=900.0)  # 2 miles in
    row = split_to_dict(s, RUN_ID, split_number=2, unit="mi")
    assert row["split_unit"] == "mi"
    assert row["split_number"] == 2
    assert row["cumulative_distance_km"] == pytest.approx(2.0 * MILES_TO_KM, abs=1e-6)
    assert row["cumulative_seconds"] == 900.0


def test_km_split_distance_not_converted() -> None:
    s = _split(distance=3.0, seconds=900.0)  # already km
    row = split_to_dict(s, RUN_ID, split_number=3, unit="km")
    assert row["split_unit"] == "km"
    assert row["cumulative_distance_km"] == pytest.approx(3.0, abs=1e-6)


def test_falls_back_to_model_values_when_args_omitted() -> None:
    s = Split(distance=1.0, seconds=480.0, split_number=1, split_unit="km")
    row = split_to_dict(s, RUN_ID)
    assert row["split_number"] == 1
    assert row["split_unit"] == "km"
    assert row["cumulative_distance_km"] == pytest.approx(1.0, abs=1e-6)
