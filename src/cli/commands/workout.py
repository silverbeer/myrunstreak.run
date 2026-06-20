"""Workout commands for stk CLI — the deterministic interface the log-workout skill drives.

Templates and sessions have nested children (items / sets), so the create
commands take a JSON file (or stdin via '-') rather than a wall of flags. The
skill builds the JSON, calls these, and reads the result back.
"""

from __future__ import annotations

import json
import sys
from typing import Any

import typer

from cli import api, display

workout_app = typer.Typer(help="Athlete workout tracker — templates, sessions, progress.")


def _load(path: str) -> dict[str, Any]:
    raw = sys.stdin.read() if path == "-" else open(path).read()
    data: dict[str, Any] = json.loads(raw)
    return data


def _dump(data: Any) -> None:
    print(json.dumps(data, indent=2, default=str))


def exercises(
    json_output: bool = typer.Option(False, "--json", "-j", help="Output raw JSON"),
) -> None:
    """List the exercise catalog (valid exercise keys + their measures)."""
    data = api.request("workouts/exercises")
    if json_output:
        _dump(data)
        return
    for e in data:
        flag = " [test]" if e.get("is_benchmark") else ""
        display.console.print(
            f"  {e['key']:<16} {e['display_name']}{flag}  ({', '.join(e['measures'])})"
        )


def templates(
    json_output: bool = typer.Option(False, "--json", "-j", help="Output raw JSON"),
) -> None:
    """List your workout templates."""
    data = api.request("workouts/templates")
    if json_output:
        _dump(data)
        return
    for t in data:
        display.console.print(
            f"  [bold]{t['name']}[/bold]  ({t['type']}, x{t['rounds']})  id={t['id'][:8]}  "
            f"{len(t.get('items', []))} exercises"
        )


def _fmt_target(item: dict[str, Any]) -> str:
    parts = []
    if item.get("target_reps") is not None:
        parts.append(f"{item['target_reps']} reps")
    if item.get("target_duration_seconds") is not None:
        parts.append(f"{item['target_duration_seconds']}s")
    if item.get("target_load_kg") is not None:
        parts.append(f"{item['target_load_kg'] * 2.20462:.0f}lb")
    if item.get("target_distance_m") is not None:
        parts.append(f"{item['target_distance_m'] / 0.9144:.0f}yd")
    return " · ".join(parts) if parts else "—"


def show(
    template_id: str = typer.Argument(
        ..., help="Template id (full or 8-char prefix from `templates`)"
    ),
    json_output: bool = typer.Option(False, "--json", "-j", help="Output raw JSON"),
) -> None:
    """Show a template's exercises (the workout card, pre-workout)."""
    tid = template_id
    if len(template_id) < 36:  # prefix → resolve against the list
        match = [t for t in api.request("workouts/templates") if t["id"].startswith(template_id)]
        if not match:
            display.console.print(f"[red]No template id starting {template_id}[/red]")
            raise typer.Exit(1)
        tid = match[0]["id"]
    t = api.request(f"workouts/templates/{tid}")
    if json_output:
        _dump(t)
        return
    display.console.print(
        f"\n[bold]{t['name']}[/bold]  ({t['type']}, x{t['rounds']} rounds)  — {t['source']}"
    )
    for item in sorted(t.get("items", []), key=lambda i: i["position"]):
        display.console.print(
            f"  {item['position'] + 1}. {item['exercise_key']:<16} {_fmt_target(item)}"
        )
    if t.get("notes"):
        display.console.print(f"  [dim]{t['notes']}[/dim]")
    display.console.print("")


def sessions(
    since: str = typer.Option(None, "--since", "-s", help="Only sessions on/after YYYY-MM-DD"),
    limit: int = typer.Option(30, "--limit", "-l"),
    json_output: bool = typer.Option(False, "--json", "-j", help="Output raw JSON"),
) -> None:
    """List logged sessions (newest first)."""
    params: dict[str, Any] = {"limit": limit}
    if since is not None:
        params["since"] = since
    data = api.request("workouts/sessions", params)
    if json_output:
        _dump(data)
        return
    for s in data:
        display.console.print(
            f"  {s['session_date']}  {s['type']}  {len(s.get('sets', []))} sets  id={s['id'][:8]}"
        )


def add_template(
    file: str = typer.Option(..., "--file", "-f", help="JSON file (or '-' for stdin)"),
    json_output: bool = typer.Option(False, "--json", "-j", help="Output raw JSON"),
) -> None:
    """Create a template from a JSON file (the coach's plan)."""
    result = api.post_request("workouts/templates", _load(file))
    if json_output:
        _dump(result)
    else:
        display.console.print(
            f"[green]Template created[/green] '{result['name']}' "
            f"({len(result.get('items', []))} exercises)  id={result['id']}"
        )


def log(
    file: str = typer.Option(..., "--file", "-f", help="JSON file (or '-' for stdin)"),
    json_output: bool = typer.Option(False, "--json", "-j", help="Output raw JSON"),
) -> None:
    """Log a session from a JSON file (the actuals)."""
    result = api.post_request("workouts/sessions", _load(file))
    if json_output:
        _dump(result)
    else:
        display.console.print(
            f"[green]Session logged[/green] {result['session_date']} "
            f"({len(result.get('sets', []))} sets)  id={result['id']}"
        )


workout_app.command(name="exercises")(exercises)
workout_app.command(name="templates")(templates)
workout_app.command(name="show")(show)
workout_app.command(name="sessions")(sessions)
workout_app.command(name="add-template")(add_template)
workout_app.command(name="log")(log)
