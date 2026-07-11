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


def _fmt_secs(value: float) -> str:
    """Seconds → compact display: 14 -> '14s', 100 -> '1:40'."""
    if value >= 60:
        return f"{int(value // 60)}:{int(value % 60):02d}"
    return f"{value:g}s"


def _fmt_goal(smin: float | None, smax: float | None) -> str:
    """A goal that may be a range: (20, 22) -> '20-22s'; (15, None) -> '15s'."""
    if smin is not None and smax is not None:
        return f"{smin:g}-{smax:g}s"
    if smin is not None:
        return _fmt_secs(smin)
    if smax is not None:
        return f"≤{_fmt_secs(smax)}"
    return "—"


def _fmt_target(item: dict[str, Any]) -> str:
    parts = []
    if item.get("target_reps") is not None:
        parts.append(f"{item['target_reps']} reps")
    smin, smax = item.get("target_duration_seconds"), item.get("target_duration_max_seconds")
    if smin is not None or smax is not None:
        parts.append(_fmt_goal(smin, smax))
    if item.get("target_load_kg") is not None:
        parts.append(f"{item['target_load_kg'] * 2.20462:.0f}lb")
    if item.get("target_distance_m") is not None:
        parts.append(_fmt_distance(item["target_distance_m"]))
    return " · ".join(parts) if parts else "—"


def _fmt_distance(meters: float) -> str:
    """Yd-native values (40yd dash -> 36.576m) render as yards; track reps as meters."""
    yards = meters / 0.9144
    if abs(yards - round(yards)) < 0.01 and abs(meters - round(meters)) > 0.01:
        return f"{round(yards)}yd"
    return f"{meters:g}m"


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
        # Broken rep (SB-264): one rep split into segments with per-segment goals.
        for seg in item.get("segments") or []:
            label = seg.get("label") or f"{seg['distance_m']:g}m"
            display.console.print(
                f"       [dim]{label:<10}[/dim] "
                f"{_fmt_goal(seg.get('target_s_min'), seg.get('target_s_max'))}"
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


def _goal_status(time_s: float, smin: float | None, smax: float | None) -> str:
    """Compare an actual segment time to its goal (range or fixed ±1s grace)."""
    if smin is None and smax is None:
        return ""
    lo = smin if smin is not None else 0.0
    hi = smax if smax is not None else lo + 1.0  # fixed goal: within a second
    if time_s <= hi:
        return "[green]hit[/green]" if time_s >= lo else "[green]fast[/green]"
    return "[red]missed[/red]"


def review(
    session_id: str = typer.Argument(
        ..., help="Session id (full or 8-char prefix from `sessions`)"
    ),
    json_output: bool = typer.Option(False, "--json", "-j", help="Output raw JSON"),
) -> None:
    """Goal vs reality for a logged session (SB-264) — the coach's debrief view."""
    sid = session_id
    if len(session_id) < 36:  # prefix → resolve against the list
        match = [
            s for s in api.request("workouts/sessions", {"limit": 100}) if s["id"].startswith(sid)
        ]
        if not match:
            display.console.print(f"[red]No session id starting {session_id}[/red]")
            raise typer.Exit(1)
        sid = match[0]["id"]
    s = api.request(f"workouts/sessions/{sid}")
    if json_output:
        _dump(s)
        return

    # Segment goals come from the template the session was logged against.
    goals_by_key: dict[str, list[dict[str, Any]]] = {}
    tpl_name = None
    if s.get("template_id"):
        tpl = api.request(f"workouts/templates/{s['template_id']}")
        tpl_name = tpl.get("name")
        for item in tpl.get("items", []):
            if item.get("segments"):
                goals_by_key.setdefault(item["exercise_key"], []).append(item)

    header = f"\n[bold]{s['session_date']}[/bold]  {s['type']}"
    if tpl_name:
        header += f"  — {tpl_name}"
    display.console.print(header)
    if s.get("how_felt"):
        display.console.print(f"  [dim]felt: {s['how_felt']}[/dim]")

    for st in s.get("sets", []):
        actual = f"{_fmt_secs(st['time_seconds'])}" if st.get("time_seconds") is not None else ""
        line = f"  {st['exercise_key']:<16}"
        if st.get("distance_m") is not None:
            line += f" {_fmt_distance(st['distance_m']):<7}"
        if actual:
            line += f" {actual}"
        if st.get("reps") is not None:
            line += f" {st['reps']} reps"
        display.console.print(line.rstrip())

        # Broken rep: goal vs reality per segment.
        segments = (st.get("extra") or {}).get("segments") or []
        if segments:
            goal_items = goals_by_key.get(st["exercise_key"], [])
            goal_segs = goal_items[0]["segments"] if goal_items else []
            display.console.print(f"       [dim]{'segment':<10} {'goal':<9} {'reality':<9}[/dim]")
            for i, seg in enumerate(segments):
                goal = goal_segs[i] if i < len(goal_segs) else {}
                label = seg.get("label") or goal.get("label") or f"#{i + 1}"
                goal_txt = _fmt_goal(goal.get("target_s_min"), goal.get("target_s_max"))
                reality = _fmt_secs(seg["time_s"]) if seg.get("time_s") is not None else "—"
                status = (
                    _goal_status(seg["time_s"], goal.get("target_s_min"), goal.get("target_s_max"))
                    if seg.get("time_s") is not None
                    else ""
                )
                note = f"  [dim]{seg['note']}[/dim]" if seg.get("note") else ""
                display.console.print(
                    f"       {label:<10} {goal_txt:<9} {reality:<9} {status}{note}"
                )
        if st.get("notes"):
            display.console.print(f"       [dim]{st['notes']}[/dim]")
    display.console.print("")


workout_app.command(name="exercises")(exercises)
workout_app.command(name="templates")(templates)
workout_app.command(name="show")(show)
workout_app.command(name="sessions")(sessions)
workout_app.command(name="review")(review)
workout_app.command(name="add-template")(add_template)
workout_app.command(name="log")(log)
