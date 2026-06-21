"""Athlete commands for stk CLI — coach platform foundation (SB-195)."""

from __future__ import annotations

import typer

from cli import api, config, display

athlete_app = typer.Typer(help="Manage athletes you coach + set the active athlete.")


def add(
    name: str = typer.Option(..., "--name", "-n", help="Athlete display name"),
    birth_year: int = typer.Option(None, "--birth-year", "-y", help="Birth year"),
) -> None:
    """Create a managed athlete (you become their coach)."""
    body: dict[str, object] = {"display_name": name}
    if birth_year is not None:
        body["birth_year"] = birth_year
    result = api.post_request("athletes", body)
    display.console.print(
        f"[green]Athlete added[/green] {result['display_name']}  id={result['id']}"
    )


def list_athletes() -> None:
    """List athletes you actively coach."""
    rows = api.request("athletes")
    if not rows:
        display.console.print("No athletes yet. Add one with 'stk athlete add --name <name>'.")
        return
    active = config.get_active_athlete()
    active_id = active["id"] if active else None
    for r in rows:
        mark = "→ " if r["id"] == active_id else "  "
        yr = f" (b. {r['birth_year']})" if r.get("birth_year") else ""
        display.console.print(f"{mark}{r['display_name']}{yr}  id={r['id'][:8]}")


def _resolve(who: str) -> dict[str, str]:
    """Resolve a name/id-prefix to one athlete you coach, or exit."""
    rows = api.request("athletes")
    matches = [
        r for r in rows if r["id"].startswith(who) or who.lower() in r["display_name"].lower()
    ]
    if not matches:
        display.console.print(f"[red]No athlete matching '{who}'[/red]")
        raise typer.Exit(1)
    if len(matches) > 1:
        display.console.print(f"[red]'{who}' is ambiguous — use the id prefix[/red]")
        raise typer.Exit(1)
    return matches[0]


def use(
    who: str = typer.Argument(..., help="Athlete name or 8-char id prefix"),
) -> None:
    """Set the active athlete (subsequent workout commands target them)."""
    a = _resolve(who)
    config.set_active_athlete(a["id"], a["display_name"])
    display.console.print(f"[green]Active athlete:[/green] {a['display_name']}")


def add_coach(
    who: str = typer.Argument(..., help="Athlete name or 8-char id prefix"),
    email: str = typer.Option(..., "--email", "-e", help="Coach's account email"),
) -> None:
    """Add a coach (by email) to an athlete. They must have an account already."""
    a = _resolve(who)
    api.post_request(f"athletes/{a['id']}/coaches", {"coach_email": email})
    display.console.print(f"[green]Coach added[/green] {email} → {a['display_name']}")


def coaches(
    who: str = typer.Argument(..., help="Athlete name or 8-char id prefix"),
) -> None:
    """List an athlete's active coaches."""
    a = _resolve(who)
    rows = api.request(f"athletes/{a['id']}/coaches")
    if not rows:
        display.console.print(f"{a['display_name']} has no coaches.")
        return
    for r in rows:
        display.console.print(f"  coach_id={r['coach_id'][:8]}  since {r['started_at'][:10]}")


def whoami() -> None:
    """Show your roles and the active athlete."""
    roles = api.request("me/roles")
    display.console.print(f"  roles: {', '.join(roles.get('roles', [])) or '(none)'}")
    active = config.get_active_athlete()
    if active:
        display.console.print(f"  active athlete: {active['name']}  id={active['id'][:8]}")
    else:
        display.console.print("  active athlete: (none) — set with 'stk athlete use <name>'")


athlete_app.command(name="add")(add)
athlete_app.command(name="list")(list_athletes)
athlete_app.command(name="use")(use)
athlete_app.command(name="add-coach")(add_coach)
athlete_app.command(name="coaches")(coaches)
athlete_app.command(name="whoami")(whoami)
