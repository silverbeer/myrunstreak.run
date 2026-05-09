"""Tests for GoalsRepository staleness logic."""

from datetime import UTC, datetime, timedelta
from unittest.mock import MagicMock

import pytest
from src.shared.models import Goal
from src.shared.supabase_ops import GoalsRepository


@pytest.fixture
def repo() -> GoalsRepository:
    """GoalsRepository with a MagicMock Supabase client."""
    return GoalsRepository(MagicMock())


def test_is_stale_missing_row(repo: GoalsRepository) -> None:
    """Missing row is always stale."""
    assert repo.is_stale(None, timedelta(days=14)) is True


def test_is_stale_no_fetched_at(repo: GoalsRepository) -> None:
    """Row without fetched_at is treated as stale."""
    assert repo.is_stale({"id": "x"}, timedelta(days=14)) is True


def test_is_stale_recent_row_is_fresh(repo: GoalsRepository) -> None:
    """Row fetched within TTL is fresh."""
    now = datetime(2026, 4, 23, 12, 0, tzinfo=UTC)
    row = {"fetched_at": (now - timedelta(days=1)).isoformat()}

    assert repo.is_stale(row, timedelta(days=3), now=now) is False


def test_is_stale_old_row_is_stale(repo: GoalsRepository) -> None:
    """Row older than TTL is stale."""
    now = datetime(2026, 4, 23, 12, 0, tzinfo=UTC)
    row = {"fetched_at": (now - timedelta(days=5)).isoformat()}

    assert repo.is_stale(row, timedelta(days=3), now=now) is True


def test_is_stale_boundary_exact_ttl(repo: GoalsRepository) -> None:
    """Row exactly at TTL is not yet stale (strict >)."""
    now = datetime(2026, 4, 23, 12, 0, tzinfo=UTC)
    row = {"fetched_at": (now - timedelta(days=3)).isoformat()}

    assert repo.is_stale(row, timedelta(days=3), now=now) is False


def test_is_stale_handles_z_suffix(repo: GoalsRepository) -> None:
    """Supabase sometimes returns timestamps with a Z suffix; parser handles it."""
    now = datetime(2026, 4, 23, 12, 0, tzinfo=UTC)
    row = {"fetched_at": "2026-04-20T12:00:00Z"}

    # 3-day-old row, TTL 3d → not stale (exactly at boundary)
    assert repo.is_stale(row, timedelta(days=3), now=now) is False


def test_yearly_vs_monthly_differ() -> None:
    """Yearly goal has month=None, monthly has 1-12."""
    yearly = Goal(year=2026)
    monthly = Goal(year=2026, month=4)

    assert yearly.is_yearly is True
    assert monthly.is_yearly is False
