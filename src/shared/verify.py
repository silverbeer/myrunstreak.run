"""Reconcile stored runs against the source of record (SB-477).

``stk sync`` only moves forward: once a run is stored it is never re-read, so a
correction made upstream — a reprocessed GPS track, an edited distance, a deleted
activity — leaves STK holding a stale value with nothing to surface it. This
module is the read-only diff that finds those.

Kept free of HTTP and database access so the comparison itself is unit-testable
against fixtures; the route supplies both sides.
"""

from __future__ import annotations

from decimal import Decimal
from typing import Any

__all__ = ["LOW_PRECISION_DECIMALS", "MATCH_TOLERANCE_KM", "decimals", "reconcile"]

# Stored distance is NUMERIC(10,5) and SmashRun returns 5 decimals, so anything
# above half a millimetre is a genuine disagreement rather than float noise.
MATCH_TOLERANCE_KM = 5e-6

# A duration is whole seconds on both sides; a 1-second difference is real but
# not interesting, so only flag more than that.
MATCH_TOLERANCE_SECONDS = 1.0

# distance_km was NUMERIC(10,3) until 20260301000001_increase_distance_precision,
# which truncated ~1m per run on the way in. Widening the column could not restore
# the lost digits — only a re-pull can. Rows at or below this many decimals are
# either that residue or a genuinely round manual entry; the report says which
# runs to look at, a human says which they are.
LOW_PRECISION_DECIMALS = 3


def decimals(value: Any) -> int:
    """Decimal places in a stored numeric, as PostgREST returned it.

    Reads the string form rather than the float: 5.551 arrives as the string
    "5.551" and asking a float how precise it is gets you binary noise.
    """
    text = str(value)
    if "." not in text or "e" in text.lower():
        return 0
    return len(text.split(".")[1].rstrip("0"))


def _to_float(value: Any) -> float:
    return float(Decimal(str(value)))


def reconcile(
    stored: list[dict[str, Any]],
    source: list[dict[str, Any]],
) -> dict[str, Any]:
    """Diff stored runs against source activities, both keyed by activity id.

    ``stored`` rows come from ``RunsRepository.get_runs_for_verify``; ``source``
    rows are ``{"activity_id", "date", "distance_km", "duration_seconds"}``
    normalised from the provider by the caller.
    """
    by_stored = {str(r["source_activity_id"]): r for r in stored}
    by_source = {str(a["activity_id"]): a for a in source}

    missing_from_stk = [
        {
            "activity_id": aid,
            "date": by_source[aid]["date"],
            "distance_km": _to_float(by_source[aid]["distance_km"]),
        }
        for aid in sorted(by_source.keys() - by_stored.keys(), key=lambda a: by_source[a]["date"])
    ]

    # Present locally but gone upstream. Not automatically wrong — the window is
    # bounded by what the provider was asked for — but a deleted activity still
    # counting toward a streak total is exactly the drift worth seeing.
    missing_from_source = [
        {
            "activity_id": aid,
            "date": str(by_stored[aid]["start_date"]),
            "distance_km": _to_float(by_stored[aid]["distance_km"]),
        }
        for aid in sorted(
            by_stored.keys() - by_source.keys(), key=lambda a: by_stored[a]["start_date"]
        )
    ]

    distance_mismatches: list[dict[str, Any]] = []
    duration_mismatches: list[dict[str, Any]] = []
    for aid in sorted(
        by_stored.keys() & by_source.keys(), key=lambda a: by_stored[a]["start_date"]
    ):
        row, act = by_stored[aid], by_source[aid]
        stored_km, source_km = _to_float(row["distance_km"]), _to_float(act["distance_km"])
        if abs(stored_km - source_km) > MATCH_TOLERANCE_KM:
            distance_mismatches.append(
                {
                    "activity_id": aid,
                    "date": str(row["start_date"]),
                    "stored_km": stored_km,
                    "source_km": source_km,
                    "delta_km": source_km - stored_km,
                    "delta_m": (source_km - stored_km) * 1000,
                }
            )
        stored_s, source_s = row.get("duration_seconds"), act.get("duration_seconds")
        if stored_s is not None and source_s is not None:
            stored_s, source_s = _to_float(stored_s), _to_float(source_s)
            if abs(stored_s - source_s) > MATCH_TOLERANCE_SECONDS:
                duration_mismatches.append(
                    {
                        "activity_id": aid,
                        "date": str(row["start_date"]),
                        "stored_seconds": stored_s,
                        "source_seconds": source_s,
                        "delta_seconds": source_s - stored_s,
                    }
                )

    low_precision = [
        {
            "activity_id": str(r["source_activity_id"]),
            "date": str(r["start_date"]),
            "distance_km": _to_float(r["distance_km"]),
            "decimals": decimals(r["distance_km"]),
        }
        for r in sorted(stored, key=lambda r: str(r["start_date"]))
        if decimals(r["distance_km"]) <= LOW_PRECISION_DECIMALS
    ]

    stored_total = sum(_to_float(r["distance_km"]) for r in stored)
    source_total = sum(_to_float(a["distance_km"]) for a in source)

    return {
        "stored_count": len(stored),
        "source_count": len(source),
        "matched": len(by_stored.keys() & by_source.keys()),
        "missing_from_stk": missing_from_stk,
        "missing_from_source": missing_from_source,
        "distance_mismatches": distance_mismatches,
        "duration_mismatches": duration_mismatches,
        "low_precision": low_precision,
        "totals": {
            "stored_km": stored_total,
            "source_km": source_total,
            "delta_km": source_total - stored_total,
        },
        "clean": not (
            missing_from_stk or missing_from_source or distance_mismatches or duration_mismatches
        ),
    }
