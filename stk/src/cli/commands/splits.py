"""Splits commands for stk CLI — backfill + negative-split analysis."""

from __future__ import annotations

import json
from typing import Any

import typer

from cli import api, display
from cli.api import post_request

splits_app = typer.Typer(help="Per-mile splits — backfill + analysis.")


def _fmt_pace(p: float | None) -> str:
    if p is None:
        return "—"
    m = int(p)
    s = round((p - m) * 60)
    if s == 60:
        m, s = m + 1, 0
    return f"{m}:{s:02d}"


def show(
    since: str = typer.Option(None, "--since", "-s", help="Only runs on/after YYYY-MM-DD"),
    limit: int = typer.Option(30, "--limit", "-l", help="Most-recent N runs with splits"),
    json_output: bool = typer.Option(False, "--json", "-j", help="Output raw JSON"),
) -> None:
    """Negative-split analysis: per-mile pace, 1st-vs-last mile, fade.

    stk splits show --since 2026-06-01
    """
    params: dict[str, Any] = {"limit": limit}
    if since is not None:
        params["since"] = since
    data = api.request("stats/splits", params)

    if json_output:
        print(json.dumps(data, indent=2, default=str))
        return

    s = data.get("summary", {})
    if not s.get("runs_analyzed"):
        display.display_info("No runs with splits yet. Run 'stk splits backfill' first.")
        return
    display.console.print(
        f"[bold]Splits — {s['runs_analyzed']} runs[/bold]  "
        f"negative-split rate [cyan]{s['negative_split_rate_pct']}%[/cyan]"
    )
    display.console.print(
        f"  avg 1st mile {_fmt_pace(s['avg_first_mile_pace'])}  ·  "
        f"avg last mile {_fmt_pace(s['avg_last_mile_pace'])}  ·  "
        f"avg fade {s['avg_fade_pct']:+}%"
    )
    display.console.print()
    for r in data.get("runs", [])[:limit]:
        flag = "📉 neg" if r["negative_split"] else f"{r['fade_pct']:+}%"
        display.console.print(
            f"  {r['date']}  {_fmt_pace(r['first_mile_pace'])}→{_fmt_pace(r['last_mile_pace'])}"
            f"  fastest {_fmt_pace(r['fastest_mile_pace'])}  [{flag}]"
        )


def backfill(
    since: str = typer.Option(None, "--since", "-s", help="Only runs on/after YYYY-MM-DD"),
    limit: int = typer.Option(50, "--limit", "-l", help="Runs per batch"),
    max_batches: int = typer.Option(200, "--max-batches", help="Safety cap on batches"),
) -> None:
    """Fetch + store per-mile splits for runs that don't have them yet.

    Runs in batches (the server rate-limits each one) until none remain.

        stk splits backfill --since 2026-01-01
    """
    body: dict[str, Any] = {"limit": limit}
    if since is not None:
        body["since"] = since

    total_runs = 0
    total_splits = 0
    display.display_sync_progress("Backfilling splits...")
    for _ in range(max_batches):
        result = post_request("sync-splits", data=body, timeout=180.0)
        processed = result.get("runs_processed", 0)
        synced = result.get("splits_synced", 0)
        remaining = result.get("remaining", 0)
        total_runs += processed
        total_splits += synced
        display.display_info(f"  {processed} runs, {synced} splits — {remaining} remaining")
        if remaining == 0 or processed == 0:
            break

    display.display_sync_progress(
        f"Backfilled {total_runs} runs ({total_splits} splits)", done=True
    )


def status(
    json_output: bool = typer.Option(False, "--json", "-j", help="Output raw JSON"),
) -> None:
    """Show splits-backfill progress (how many runs still lack splits)."""
    data = api.request("sync-splits/status")
    if json_output:
        print(json.dumps(data, indent=2))
        return
    done = data.get("done")
    icon = "✓" if done else "…"
    display.console.print(
        f"  {icon} splits: {data['runs_with_splits']}/{data['runs_total']} runs "
        f"({data['pct_complete']}%) — {data['runs_missing_splits']} remaining"
    )


splits_app.command(name="backfill")(backfill)
splits_app.command(name="show")(show)
splits_app.command(name="status")(status)
