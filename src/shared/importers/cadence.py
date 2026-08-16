"""Normalize imported cadence to steps per minute (SB-623).

Sources disagree about what "cadence" counts:

* **Garmin GPX** (`<gpxtpx:cad>`) and **Garmin TCX** (`<RunCadence>`, and
  `<Cadence>` on a running activity) report **strides** per minute — one foot,
  so a normal running cadence reads ~85–95.
* **SmashRun**, and therefore the `cadence_average` column and everything that
  reads it, stores **steps** per minute — both feet, ~170–190 for the same run.

Left alone, an imported run sits next to a synced one showing half its
cadence, with nothing on screen to explain the discontinuity.
"""

from __future__ import annotations

# Above this, a value is already steps per minute. Running cadence lives at
# 150–200 steps/min and stride rates at 75–100, so the gap is wide. The
# threshold sits above brisk walking in *strides* (~65) and below the slowest
# plausible running cadence in *steps*, which is where the two ranges could
# otherwise be confused.
STRIDE_RATE_CEILING = 130.0


def to_steps_per_minute(
    average: float | None,
    minimum: float | None,
    maximum: float | None,
) -> tuple[float | None, float | None, float | None]:
    """Convert a stride-rate cadence triple to steps per minute.

    The decision is made once, from the average, and applied to all three
    values — deciding per value would let a doubled average sit beside an
    untouched maximum, which is worse than either unit consistently.

    A file that already states steps per minute is returned unchanged.

    Args:
        average: Mean cadence over the run
        minimum: Lowest recorded cadence
        maximum: Highest recorded cadence

    Returns:
        The same triple, in steps per minute.
    """
    if average is None or average <= 0 or average >= STRIDE_RATE_CEILING:
        return average, minimum, maximum

    return (
        average * 2,
        minimum * 2 if minimum is not None else None,
        maximum * 2 if maximum is not None else None,
    )
