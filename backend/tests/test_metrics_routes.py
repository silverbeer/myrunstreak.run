"""Route-handler tests for /metrics/* with mocked repositories.

Handlers are invoked directly (passing user_id), so no ASGI client or real
Supabase is needed. CACHE_ENABLED=false (conftest) makes invalidate_user a
no-op, so cache isn't patched.
"""

from __future__ import annotations

from datetime import date
from unittest.mock import MagicMock, patch
from uuid import uuid4

import pytest
from fastapi import HTTPException
from src.shared.models.metric import GoalKind, GoalPeriod, MetricEntryCreate, MetricGoalCreate


def _patch(types=None, entries=None, goals=None):
    """Patch get_supabase_client + the three repo classes in the route module."""
    patches = [patch("backend.routes.metrics.get_supabase_client", return_value=MagicMock())]
    if types is not None:
        patches.append(patch("backend.routes.metrics.MetricTypesRepository", return_value=types))
    if entries is not None:
        patches.append(
            patch("backend.routes.metrics.MetricEntriesRepository", return_value=entries)
        )
    if goals is not None:
        patches.append(patch("backend.routes.metrics.MetricGoalsRepository", return_value=goals))
    return patches


def _enter(patches):
    for p in patches:
        p.start()


def _exit(patches):
    for p in patches:
        p.stop()


@pytest.mark.asyncio
async def test_create_entry_rejects_unknown_metric():
    from backend.routes.metrics import create_entry

    types = MagicMock()
    types.get.return_value = None  # unknown metric
    patches = _patch(types=types)
    _enter(patches)
    try:
        with pytest.raises(HTTPException) as exc:
            await create_entry(MetricEntryCreate(metric_key="nope", value=10), user_id=uuid4())
        assert exc.value.status_code == 400
    finally:
        _exit(patches)


@pytest.mark.asyncio
async def test_create_entry_defaults_occurred_on_and_inserts():
    from backend.routes.metrics import create_entry

    uid = uuid4()
    types = MagicMock()
    types.get.return_value = {
        "key": "pushups",
        "display_name": "Push-ups",
        "unit": "reps",
        "aggregation": "sum",
    }
    entries = MagicMock()

    def _insert(user_id, payload):
        # echo back a stored row
        return {"id": str(uuid4()), "user_id": str(user_id), **payload}

    entries.insert.side_effect = _insert

    patches = _patch(types=types, entries=entries)
    _enter(patches)
    try:
        res = await create_entry(MetricEntryCreate(metric_key="pushups", value=25), user_id=uid)
    finally:
        _exit(patches)

    # occurred_on defaulted to today (server) and an insert happened.
    assert entries.insert.called
    inserted_payload = entries.insert.call_args.args[1]
    assert "occurred_on" in inserted_payload
    assert res.value == 25.0
    assert res.metric_key == "pushups"


@pytest.mark.asyncio
async def test_delete_entry_404_when_missing():
    from backend.routes.metrics import delete_entry

    entries = MagicMock()
    entries.delete.return_value = False
    patches = _patch(entries=entries)
    _enter(patches)
    try:
        with pytest.raises(HTTPException) as exc:
            await delete_entry(uuid4(), user_id=uuid4())
        assert exc.value.status_code == 404
    finally:
        _exit(patches)


def test_list_goals_computes_progress():
    from backend.routes.metrics import list_goals

    uid = uuid4()
    goal_row = {
        "id": str(uuid4()),
        "user_id": str(uid),
        "metric_key": "pushups",
        "kind": "volume",
        "period": "month",
        "target": 100.0,
        "comparator": "gte",
        "rest_budget": 0,
        "status": "active",
    }
    goals = MagicMock()
    goals.list.return_value = [goal_row]

    types = MagicMock()
    types.get.return_value = {
        "key": "pushups",
        "display_name": "Push-ups",
        "unit": "reps",
        "aggregation": "sum",
    }

    entries = MagicMock()
    today = date.today()
    entries.list.return_value = [
        {
            "id": str(uuid4()),
            "user_id": str(uid),
            "metric_key": "pushups",
            "occurred_on": today.replace(day=1).isoformat(),
            "value": 40.0,
        },
    ]

    patches = _patch(types=types, entries=entries, goals=goals)
    _enter(patches)
    try:
        result = list_goals(user_id=uid, status_filter="active")
    finally:
        _exit(patches)

    assert len(result) == 1
    assert result[0].progress == 40.0
    assert result[0].goal.metric_key == "pushups"
    goals.list.assert_called_once_with(uid, status="active")


def test_create_goal_custom_period_requires_bounds():
    # Model-level validation: custom without bounds is rejected before any I/O.
    with pytest.raises(ValueError):
        MetricGoalCreate(
            metric_key="pushups", kind=GoalKind.volume, period=GoalPeriod.custom, target=100
        )
