"""Invite commands for stk CLI — invite-only onboarding (SB-188).

`create`/`list` are admin-only; `redeem` is how an invited user signs up.
"""

from __future__ import annotations

import typer

from cli import api, display, session as session_mod
from cli.api import post_unauth

invite_app = typer.Typer(help="Issue, list, and redeem onboarding invites.")


def create(
    email: str = typer.Option(..., "--email", "-e", help="Who the invite is for"),
    days: int = typer.Option(14, "--days", "-d", help="Days until the token expires"),
    role: str = typer.Option(None, "--role", "-r", help="Role to grant on redeem (e.g. coach)"),
) -> None:
    """Issue an invite. Prints a redeem link to text the invitee."""
    body: dict[str, object] = {"email": email, "expires_in_days": days}
    if role is not None:
        body["grant_role"] = role
    result = api.post_request("invites", body)
    link = f"https://myrunstreak.run/signup?invite={result['token']}"
    role_note = f" as [bold]{result['grant_role']}[/bold]" if result.get("grant_role") else ""
    display.console.print(
        f"[green]Invite issued[/green] for {result['email']}{role_note} "
        f"(expires {result['expires_at'][:10]})"
    )
    display.console.print(f"  link: [bold]{link}[/bold]")
    display.console.print("  [dim](text this to the invitee)[/dim]")


def list_invites() -> None:
    """List invites you've issued."""
    rows = api.request("invites")
    if not rows:
        display.console.print("No invites issued yet.")
        return
    for r in rows:
        state = "redeemed" if r.get("redeemed_at") else "open"
        display.console.print(f"  {r['email']:<30} {state:<9} expires {r['expires_at'][:10]}")


def redeem(
    token: str = typer.Option(None, "--token", "-t", help="Invite token (or paste when prompted)"),
) -> None:
    """Redeem an invite to create your account and log in."""
    if not token:
        token = typer.prompt("Invite token")
    password = typer.prompt("Choose a password", hide_input=True, confirmation_prompt=True)

    display.display_sync_progress("Redeeming invite...")
    data = post_unauth("invites/redeem", {"token": token, "password": password})

    email = (data.get("user") or {}).get("email") or ""
    session_mod.save(
        access_token=data["access_token"],
        refresh_token=data["refresh_token"],
        expires_in=data.get("expires_in"),
        email=email,
    )
    display.display_sync_progress(f"Welcome, {email}", done=True)
    display.console.print("\n[green]Account created + logged in. 'stk' commands now work.[/green]")


invite_app.command(name="create")(create)
invite_app.command(name="list")(list_invites)
invite_app.command(name="redeem")(redeem)
