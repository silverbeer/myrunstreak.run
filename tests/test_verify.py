"""Reconciliation of stored runs against the source of record (SB-477).

The December 2024 numbers here are real: that month is known-good, every run
agreeing with SmashRun to the decimal, and it sums to 99.97998 mi — 32 metres
under 100. It makes a good fixture precisely because a naive check would call
those runs wrong.
"""

from src.shared.verify import LOW_PRECISION_DECIMALS, decimals, reconcile


def _stored(activity_id: str, day: str, km: float | str, seconds: float = 1800.0) -> dict:
    return {
        "id": f"run-{activity_id}",
        "source_activity_id": activity_id,
        "start_date": day,
        "distance_km": km,
        "duration_seconds": seconds,
    }


def _source(activity_id: str, day: str, km: float, seconds: float = 1800.0) -> dict:
    return {
        "activity_id": activity_id,
        "date": day,
        "distance_km": km,
        "duration_seconds": seconds,
    }


def test_identical_sides_are_clean() -> None:
    stored = [
        _stored("40316850", "2024-12-01", 5.55113),
        _stored("40328247", "2024-12-02", 5.57253),
    ]
    source = [
        _source("40316850", "2024-12-01", 5.55113),
        _source("40328247", "2024-12-02", 5.57253),
    ]

    report = reconcile(stored, source)

    assert report["clean"]
    assert report["matched"] == 2
    assert report["missing_from_stk"] == []
    assert report["missing_from_source"] == []
    assert report["distance_mismatches"] == []
    assert report["totals"]["delta_km"] == 0


def test_run_missing_locally_is_reported() -> None:
    report = reconcile(
        [_stored("1", "2024-12-01", 5.0)],
        [_source("1", "2024-12-01", 5.0), _source("2", "2024-12-02", 6.5)],
    )

    assert not report["clean"]
    assert [r["activity_id"] for r in report["missing_from_stk"]] == ["2"]
    assert report["missing_from_stk"][0]["distance_km"] == 6.5
    assert report["missing_from_source"] == []


def test_run_deleted_upstream_is_reported() -> None:
    """Still counting toward a streak total here, gone from the source."""
    report = reconcile(
        [_stored("1", "2024-12-01", 5.0), _stored("2", "2024-12-02", 6.5)],
        [_source("1", "2024-12-01", 5.0)],
    )

    assert not report["clean"]
    assert [r["activity_id"] for r in report["missing_from_source"]] == ["2"]


def test_distance_drift_is_reported_in_metres() -> None:
    """The upstream-correction case: sync never re-reads, so this is invisible."""
    report = reconcile([_stored("1", "2024-12-01", 5.551)], [_source("1", "2024-12-01", 5.55113)])

    assert not report["clean"]
    (mismatch,) = report["distance_mismatches"]
    assert mismatch["stored_km"] == 5.551
    assert mismatch["source_km"] == 5.55113
    assert round(mismatch["delta_m"], 3) == 0.13


def test_tolerance_absorbs_float_noise_but_not_a_real_change() -> None:
    assert reconcile(
        [_stored("1", "2024-12-01", 5.55113)], [_source("1", "2024-12-01", 5.5511300001)]
    )["clean"]
    assert not reconcile(
        [_stored("1", "2024-12-01", 5.55113)], [_source("1", "2024-12-01", 5.55115)]
    )["clean"]


def test_duration_drift_ignores_a_single_second() -> None:
    assert reconcile(
        [_stored("1", "2024-12-01", 5.0, seconds=1800.0)],
        [_source("1", "2024-12-01", 5.0, seconds=1801.0)],
    )["clean"]
    report = reconcile(
        [_stored("1", "2024-12-01", 5.0, seconds=1800.0)],
        [_source("1", "2024-12-01", 5.0, seconds=1830.0)],
    )
    assert not report["clean"]
    assert report["duration_mismatches"][0]["delta_seconds"] == 30.0


def test_low_precision_is_advisory_not_a_failure() -> None:
    """A 3-decimal distance is either pre-migration truncation or a round manual
    entry. Worth surfacing, not worth failing a build over."""
    stored = [_stored("1", "2024-12-01", "5.551"), _stored("2", "2024-12-02", "5.57253")]
    source = [_source("1", "2024-12-01", 5.551), _source("2", "2024-12-02", 5.57253)]

    report = reconcile(stored, source)

    assert report["clean"]  # <- the whole point
    assert [r["activity_id"] for r in report["low_precision"]] == ["1"]
    assert report["low_precision"][0]["decimals"] == 3


def test_totals_carry_the_real_december_shortfall() -> None:
    """99.97998 mi is the true December 2024 total; the report must not round it
    away — SmashRun's display rounds, the reconciliation does not."""
    km = [5.55113, 5.57253, 5.62981]
    report = reconcile(
        [_stored(str(i), f"2024-12-0{i + 1}", v) for i, v in enumerate(km)],
        [_source(str(i), f"2024-12-0{i + 1}", v) for i, v in enumerate(km)],
    )

    assert report["totals"]["stored_km"] == sum(km)
    assert report["totals"]["source_km"] == sum(km)


def test_empty_range_is_clean() -> None:
    report = reconcile([], [])
    assert report["clean"]
    assert report["stored_count"] == 0
    assert report["totals"]["stored_km"] == 0


class TestDecimals:
    def test_counts_stored_precision(self) -> None:
        assert decimals("5.55113") == 5
        assert decimals("5.551") == 3
        assert decimals("5.5") == 1
        assert decimals("5") == 0

    def test_ignores_trailing_zeros(self) -> None:
        """PostgREST returns NUMERIC(10,5) padded; 5.55000 is a 2-decimal value."""
        assert decimals("5.55000") == 2
        assert decimals("5.00000") == 0

    def test_threshold_matches_the_old_column_width(self) -> None:
        assert LOW_PRECISION_DECIMALS == 3
