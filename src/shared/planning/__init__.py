"""Adaptive monthly planning engine (SB-163).

Pure functions that turn monthly goals + actuals + constraints + readiness into a
day-by-day plan. **No I/O, no LLM** — every number originates here so the result
is reproducible and testable. The LLM coaching layer (P2) only narrates this
output; it never computes.
"""

from .engine import RUNNING_KEY, check_feasibility, generate_plan, recompute

__all__ = [
    "generate_plan",
    "recompute",
    "check_feasibility",
    "RUNNING_KEY",
]
