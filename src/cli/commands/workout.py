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
workout_app.command(name="sessions")(sessions)
workout_app.command(name="add-template")(add_template)
workout_app.command(name="log")(log)
