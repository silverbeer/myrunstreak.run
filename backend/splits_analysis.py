"""Per-mile split analysis — pure functions over stored splits.

Splits are stored cumulatively (``cumulative_distance_km`` / ``cumulative_seconds``
at each mile boundary). These functions difference them into per-mile paces and
derive negative-split / fade stats. No I/O — trivially unit-testable.

Paces are min/mile (the runner's unit), computed from canonical km.
"""

from __future__ import annotations

from statistics import mean
from typing import Any

KM_TO_MILES = 0.621371


def per_mile_splits(rows: list[dict[str, Any]]) -> list[dict[str, Any]]:
    """Difference cumulative split rows into per-mile pieces (pace in min/mile).

    Rows need ``split_number``, ``cumulative_distance_km``, ``cumulative_seconds``.
    Degenerate pieces (non-positive distance/time) are dropped. The final partial
    mile is kept but its pace is still per-mile-normalized.
    """
    ordered = sorted(rows, key=lambda r: r["split_number"])
    out: list[dict[str, Any]] = []
    prev_km = 0.0
    prev_s = 0.0
    for r in ordered:
        cum_km = float(r["cumulative_distance_km"])
        cum_s = float(r["cumulative_seconds"])
        dist_mi = (cum_km - prev_km) * KM_TO_MILES
        secs = cum_s - prev_s
        prev_km, prev_s = cum_km, cum_s
        if dist_mi <= 0 or secs <= 0:
            continue
        out.append(
            {
                "split_number": r["split_number"],
                "distance_mi": round(dist_mi, 3),
                "seconds": round(secs, 1),
                "pace_min_per_mi": round((secs / dist_mi) / 60.0, 2),
                "heart_rate": r.get("heart_rate"),
            }
        )
    return out


def analyze_run(rows: list[dict[str, Any]]) -> dict[str, Any] | None:
    """Per-run split stats, or None when there aren't ≥2 usable splits."""
    splits = per_mile_splits(rows)
    if len(splits) < 2:
        return None
    paces = [s["pace_min_per_mi"] for s in splits]
    n = len(paces)
    half = n // 2
    first_half = mean(paces[:half]) if half else paces[0]
    second_half = mean(paces[half:])
    return {
        "n_splits": n,
        "first_mile_pace": paces[0],
        "last_mile_pace": paces[-1],
        "first_half_pace": round(first_half, 2),
        "second_half_pace": round(second_half, 2),
        # Negative split = second half faster (lower pace) than first.
        "negative_split": second_half < first_half,
        "fastest_mile_pace": min(paces),
        "slowest_mile_pace": max(paces),
        # +% = slowed down over the run (fade); −% = sped up (negative split).
        "fade_pct": round((paces[-1] - paces[0]) / paces[0] * 100, 1),
        "splits": splits,
    }


def summarize(run_analyses: list[dict[str, Any] | None]) -> dict[str, Any]:
    """Aggregate per-run analyses into a headline summary."""
    analyses = [a for a in run_analyses if a]
    if not analyses:
        return {"runs_analyzed": 0}
    neg = sum(1 for a in analyses if a["negative_split"])
    return {
        "runs_analyzed": len(analyses),
        "negative_split_rate_pct": round(neg / len(analyses) * 100, 1),
        "avg_first_mile_pace": round(mean(a["first_mile_pace"] for a in analyses), 2),
        "avg_last_mile_pace": round(mean(a["last_mile_pace"] for a in analyses), 2),
        "avg_fade_pct": round(mean(a["fade_pct"] for a in analyses), 1),
    }


def format_pace(min_per_mi: float | None) -> str | None:
    """9.51 → '9:31 /mi'."""
    if min_per_mi is None:
        return None
    minutes = int(min_per_mi)
    seconds = round((min_per_mi - minutes) * 60)
    if seconds == 60:
        minutes, seconds = minutes + 1, 0
    return f"{minutes}:{seconds:02d} /mi"
