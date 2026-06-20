"""Planning commands for stk CLI — plan / constraint / readiness.

Deterministic, machine-readable wrappers over the /plan API. These are what the
`plan` Claude skill (P2) drives: it calls these with --json, reads the engine's
result, and narrates the coaching. No LLM here.
"""

from __future__ import annotations

import json
from datetime import date, datetime
from zoneinfo import ZoneInfo

import typer

from cli import api, display

# Canonical storage is km (matches the API). The CLI speaks miles, the runner's
# unit. Kept local to avoid the CLI<->shared import-root ambiguity.
_MILES_TO_KM = 1.609344

plan_app = typer.Typer(help="View and recompute your adaptive monthly plan.")
constraint_app = typer.Typer(help="Manage known-in-advance plan constraints (travel, injury).")
readiness_app = typer.Typer(help="Log how you feel so the plan can adapt.")


def _today() -> date:
    return datetime.now(ZoneInfo("America/New_York")).date()


def _current_period() -> str:
    t = _today()
    return f"{t.year:04d}-{t.month:02d}"


def _parse_distance_km(value: str) -> float:
    """Parse '1mi' / '5km' / '5k' / '8' (bare == miles) into canonical km."""
    s = value.strip().lower()
    try:
        if s.endswith("mi"):
            return float(s[:-2]) * _MILES_TO_KM
        if s.endswith("km"):
            return float(s[:-2])
        if s.endswith("k"):
            return float(s[:-1])
        return float(s) * _MILES_TO_KM  # bare number = miles
    except ValueError as exc:
        raise typer.BadParameter(f"can't parse distance '{value}' (try '1mi' or '5km')") from exc


def _parse_day(value: str) -> date:
    """Parse 'today' or an ISO YYYY-MM-DD date."""
    if value.strip().lower() == "today":
        return _today()
    try:
        return date.fromisoformat(value.strip())
    except ValueError as exc:
        raise typer.BadParameter(f"can't parse date '{value}' (use YYYY-MM-DD or 'today')") from exc


def _emit(data: dict, json_output: bool, render) -> None:
    if json_output:
        print(json.dumps(data, indent=2, default=str))
    else:
        render(data)


def _render_plan(data: dict) -> None:
    """A compact human summary; the rich month-grid is P3 (frontend)."""
    status = data.get("status", "?")
    icon = "✅" if status == "on_track" else "⚠️"
    display.console.print(
        f"[bold]Plan {data.get('period_start')} → {data.get('period_end')}[/bold]  {icon} {status}"
    )
    for g in data.get("goals", []):
        gicon = "✅" if g.get("status") == "on_track" else "⚠️"
        line = f"  {gicon} {g['metric_key']} ({g['kind']}): {g.get('done')}/{g.get('target')}"
        if g.get("detail"):
            line += f" — {g['detail']}"
        display.console.print(line)
    for reason in data.get("at_risk_reasons", []):
        display.console.print(f"  [yellow]at risk:[/yellow] {reason}")


# ----------------------------------------------------------------- plan show / recompute


def plan_show(
    period: str = typer.Option(None, "--period", "-p", help="YYYY-MM (default: this month)"),
    json_output: bool = typer.Option(False, "--json", "-j", help="Output raw JSON"),
) -> None:
    """Show your plan for a month (recomputed from current reality)."""
    data = api.request(f"plan/{period or _current_period()}")
    _emit(data, json_output, _render_plan)


def plan_recompute(
    period: str = typer.Option(None, "--period", "-p", help="YYYY-MM (default: this month)"),
    json_output: bool = typer.Option(False, "--json", "-j", help="Output raw JSON"),
) -> None:
    """Recompute and persist your plan for a month."""
    data = api.post_request(f"plan/{period or _current_period()}/recompute")
    _emit(data, json_output, _render_plan)


# ----------------------------------------------------------------- constraint add


def constraint_add(
    metric: str = typer.Option("running_distance", "--metric", "-m", help="Metric key"),
    date_from: str = typer.Option(..., "--from", help="Start date YYYY-MM-DD"),
    date_to: str = typer.Option(..., "--to", help="End date YYYY-MM-DD"),
    cap: str = typer.Option(None, "--cap", help="Max per day, e.g. '1mi' (distance metrics)"),
    floor: str = typer.Option(None, "--floor", help="Min still required per day, e.g. '1mi'"),
    reason: str = typer.Option(None, "--reason", help="Why, e.g. 'Chicago travel'"),
    json_output: bool = typer.Option(False, "--json", "-j", help="Output raw JSON"),
) -> None:
    """Add a known-in-advance limit (e.g. travel caps running to 1 mi/day)."""
    body: dict = {
        "metric_key": metric,
        "start_on": _parse_day(date_from).isoformat(),
        "end_on": _parse_day(date_to).isoformat(),
    }
    if cap is not None:
        body["cap"] = _parse_distance_km(cap)
    if floor is not None:
        body["floor"] = _parse_distance_km(floor)
    if reason is not None:
        body["reason"] = reason

    data = api.post_request("plan/constraints", body)
    if json_output:
        print(json.dumps(data, indent=2, default=str))
    else:
        display.console.print(
            f"[green]Added constraint[/green] {data.get('id')}: {reason or metric}"
        )


# ----------------------------------------------------------------- readiness set


def readiness_set(
    status: str = typer.Option(..., "--status", "-s", help="good | tired | sick"),
    day: str = typer.Option("today", "--date", "-d", help="YYYY-MM-DD or 'today'"),
    note: str = typer.Option(None, "--note", "-n", help="Optional note"),
    json_output: bool = typer.Option(
        False, "--json", "-j", help="Output raw JSON (recomputed plan)"
    ),
) -> None:
    """Log how you feel; the plan recomputes immediately and adapts."""
    if status not in {"good", "tired", "sick"}:
        raise typer.BadParameter("status must be good, tired, or sick")
    body: dict = {"log_on": _parse_day(day).isoformat(), "status": status}
    if note is not None:
        body["note"] = note

    data = api.post_request("plan/readiness", body)
    _emit(data, json_output, _render_plan)


plan_app.command(name="show")(plan_show)
plan_app.command(name="recompute")(plan_recompute)
constraint_app.command(name="add")(constraint_add)
readiness_app.command(name="set")(readiness_set)
