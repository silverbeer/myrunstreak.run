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


def _group_options(items: list[dict[str, Any]]) -> list[dict[str, Any]]:
    """Fold "pick one of N" alternatives into single rows (SB-448).

    Items sharing an ``option_group`` are alternatives — the aerobic day is run
    OR bike OR jump rope, and printed flat it read as all three. A group lands
    at the position of its first member, so alternatives listed non-contiguously
    still render as one block rather than repeating the heading.
    """
    rows: list[dict[str, Any]] = []
    index: dict[str, int] = {}
    for item in sorted(items, key=lambda i: i.get("position", 0)):
        key = item.get("option_group")
        if not key:
            rows.append({"kind": "item", "item": item})
            continue
        if key not in index:
            index[key] = len(rows)
            rows.append(
                {
                    "kind": "group",
                    "key": key,
                    # Read from whichever member carries it — a coach writes it once.
                    "label": item.get("option_group_label") or "Pick one",
                    "items": [item],
                }
            )
            continue
        row = rows[index[key]]
        row["items"].append(item)
        if row["label"] == "Pick one" and item.get("option_group_label"):
            row["label"] = item["option_group_label"]
    return rows


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


def _fmt_range(lo: float | None, hi: float | None, unit: str = "") -> str:
    """A target that may be a range: (8, 12) -> "8-12"; (8, None) -> "8" (SB-446)."""
    if lo is not None and hi is not None and hi != lo:
        return f"{lo:g}-{hi:g}{unit}"
    value = lo if lo is not None else hi
    return f"{value:g}{unit}" if value is not None else ""


def _fmt_rest(item: dict[str, Any]) -> str:
    """Rest as prescribed — which is not always a number (SB-446).

    "Full recovery" and "go off how you feel" are conditions the athlete
    resolves; rendering them as a made-up number would misreport the plan.
    """
    mode = item.get("rest_mode")
    if mode == "full":
        return "rest: full recovery"
    lo, hi = item.get("rest_seconds"), item.get("rest_seconds_max")
    if lo is None and hi is None:
        return "rest: by feel" if mode == "autoregulated" else ""
    text = f"rest {_fmt_range(lo, hi, 's')}"
    if mode == "autoregulated":
        text += " (by feel)"
    return text


def _fmt_target(item: dict[str, Any]) -> str:
    parts = []
    reps = _fmt_range(item.get("target_reps"), item.get("target_reps_max"))
    if reps:
        parts.append(f"{reps} reps")
    smin, smax = item.get("target_duration_seconds"), item.get("target_duration_max_seconds")
    if smin is not None or smax is not None:
        parts.append(_fmt_goal(smin, smax))
    lo_kg, hi_kg = item.get("target_load_kg"), item.get("target_load_max_kg")
    if lo_kg is not None or hi_kg is not None:
        lo_lb = lo_kg * 2.20462 if lo_kg is not None else None
        hi_lb = hi_kg * 2.20462 if hi_kg is not None else None
        # Loads are prescribed in lb; round each bound so "5-8lb" comes back as
        # "5-8lb" rather than "5-8.0000001lb" after the kg round-trip.
        lo_lb = round(lo_lb) if lo_lb is not None else None
        hi_lb = round(hi_lb) if hi_lb is not None else None
        parts.append(f"{_fmt_range(lo_lb, hi_lb)}lb")
    if item.get("target_distance_m") is not None:
        parts.append(_fmt_distance(item["target_distance_m"]))
    rest = _fmt_rest(item)
    if rest:
        parts.append(rest)
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

    def _segments(item: dict[str, Any], indent: str) -> None:
        # Broken rep (SB-264): one rep split into segments with per-segment goals.
        for seg in item.get("segments") or []:
            label = seg.get("label") or f"{seg['distance_m']:g}m"
            display.console.print(
                f"{indent}[dim]{label:<10}[/dim] "
                f"{_fmt_goal(seg.get('target_s_min'), seg.get('target_s_max'))}"
            )

    n = 0
    for row in _group_options(t.get("items", [])):
        if row["kind"] == "group":
            n += 1
            display.console.print(f"  {n}. [bold]{row['label']}[/bold] [dim]— do one[/dim]")
            for item in row["items"]:
                display.console.print(f"       ○ {item['exercise_key']:<14} {_fmt_target(item)}")
                _segments(item, "           ")
            continue
        item = row["item"]
        n += 1
        display.console.print(f"  {n}. {item['exercise_key']:<16} {_fmt_target(item)}")
        _segments(item, "       ")
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


def _range_status(actual: float, lo: float | None, hi: float | None) -> str:
    """Grade an actual against a prescribed range (SB-446).

    A range is a legitimate prescription, not a fuzzy point target: "8-12 reps"
    means anywhere in 8..12 is the plan followed, so anything inside reads as
    hit rather than "off by 2". With only a lower bound set, more is better —
    which is how Matthew writes rep targets.
    """
    if lo is None and hi is None:
        return ""
    if lo is not None and actual < lo:
        return "[yellow]under[/yellow]"
    if hi is not None and actual > hi:
        return "[green]over[/green]"
    return "[green]hit[/green]"


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

    # Goals come from the template the session was logged against — segment
    # goals (SB-264) and item-level targets, which may be ranges (SB-446).
    goals_by_key: dict[str, list[dict[str, Any]]] = {}
    items_by_key: dict[str, dict[str, Any]] = {}
    tpl_name = None
    if s.get("template_id"):
        tpl = api.request(f"workouts/templates/{s['template_id']}")
        tpl_name = tpl.get("name")
        for item in tpl.get("items", []):
            items_by_key.setdefault(item["exercise_key"], item)
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
            goal = items_by_key.get(st["exercise_key"], {})
            verdict = _range_status(
                st["reps"], goal.get("target_reps"), goal.get("target_reps_max")
            )
            if verdict:
                line += f"  {verdict}"
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
