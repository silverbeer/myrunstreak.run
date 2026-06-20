"""Invite commands for stk CLI — admin-only invite-only onboarding (SB-188)."""

from __future__ import annotations

import typer

from cli import api, display

invite_app = typer.Typer(help="Issue + list onboarding invites (admin only).")


def create(
    email: str = typer.Option(..., "--email", "-e", help="Who the invite is for"),
    days: int = typer.Option(14, "--days", "-d", help="Days until the token expires"),
) -> None:
    """Issue an invite. Prints the token to share with the invitee."""
    result = api.post_request("invites", {"email": email, "expires_in_days": days})
    display.console.print(
        f"[green]Invite issued[/green] for {result['email']} (expires {result['expires_at'][:10]})"
    )
    display.console.print(f"  token: [bold]{result['token']}[/bold]")


def list_invites() -> None:
    """List invites you've issued."""
    rows = api.request("invites")
    if not rows:
        display.console.print("No invites issued yet.")
        return
    for r in rows:
        state = "redeemed" if r.get("redeemed_at") else "open"
        display.console.print(f"  {r['email']:<30} {state:<9} expires {r['expires_at'][:10]}")


invite_app.command(name="create")(create)
invite_app.command(name="list")(list_invites)
