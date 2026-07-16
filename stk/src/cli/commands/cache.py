"""stk cache — inspect, relocate, and clear the local response cache."""

from __future__ import annotations

from pathlib import Path

import typer
from rich.console import Console
from rich.table import Table

from cli import cache
from cli import config as config_mod

cache_app = typer.Typer(help="Local response cache")
console = Console()

# Path fragments that mean "this lives on a file-sync service".
_SYNC_HINTS = ("Mobile Documents", "com~apple~CloudDocs", "CloudStorage", "Dropbox", "OneDrive")


def clear() -> None:
    """Delete every cached response."""
    n = cache.clear_all()
    console.print(f"[green]Cleared {n} cached entr{'y' if n == 1 else 'ies'}.[/green]")


def stats() -> None:
    """Show cache size and a per-endpoint breakdown."""
    data = cache.stats()
    kb = data["size_bytes"] / 1024
    console.print(f"[bold]Local response cache[/bold] — {data['rows']} rows, {kb:.1f} KB")
    console.print(f"[dim]{cache.db_path()}[/dim]")
    by_endpoint = data["by_endpoint"]
    if by_endpoint:
        table = Table(show_header=True, header_style="bold")
        table.add_column("Endpoint")
        table.add_column("Rows", justify="right")
        for endpoint, count in by_endpoint.items():
            table.add_row(endpoint, str(count))
        console.print(table)


def path(
    location: str = typer.Argument(
        None, help="Directory or .db file for the cache. Omit to show the current path."
    ),
    reset: bool = typer.Option(False, "--reset", help="Revert to the default location."),
) -> None:
    """Show or change where the cache DB is stored.

    Point it at a synced folder to share the cache across machines — but note
    SQLite on iCloud/Dropbox can corrupt if both machines write at once. It's a
    disposable cache (fails open and refetches), so corruption never breaks
    stk, but don't run stk on two synced machines at the same time.
    """
    if reset:
        config_mod.clear_cache_db()
        console.print(f"[green]Cache location reset to default:[/green] {cache.CACHE_DB}")
        return
    if location is None:
        console.print(f"[bold]Cache DB:[/bold] {cache.db_path()}")
        return

    p = Path(location).expanduser()
    target = p if p.suffix == ".db" else p / "cache.db"
    config_mod.set_cache_db(str(target))
    console.print(f"[green]Cache will be stored at:[/green] {target}")
    console.print(
        "[dim]Existing entries aren't migrated; the new location rebuilds on demand.[/dim]"
    )
    if any(hint in str(target) for hint in _SYNC_HINTS):
        console.print(
            "[yellow]Heads up:[/yellow] that's a file-sync location. SQLite can corrupt if two "
            "machines write at once — don't run stk on both simultaneously. (It fails open and "
            "refetches, so this never breaks commands.)"
        )


cache_app.command(name="clear")(clear)
cache_app.command(name="stats")(stats)
cache_app.command(name="path")(path)
