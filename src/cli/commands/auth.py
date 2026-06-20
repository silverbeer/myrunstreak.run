"""Auth commands for stk CLI."""

import json
import socket
import webbrowser
from http.server import BaseHTTPRequestHandler, HTTPServer
from pathlib import Path
from typing import Any
from urllib.parse import parse_qs, urlparse

import httpx
import typer
from rich.console import Console
from rich.panel import Panel

from cli import display
from cli import session as session_mod
from cli.api import get_api_url, post_unauth

app = typer.Typer(help="Authentication commands")
console = Console()

# Config directory
CONFIG_DIR = Path.home() / ".config" / "stk"
CONFIG_FILE = CONFIG_DIR / "config.json"

TIMEOUT = 30.0


def ensure_config_dir() -> None:
    """Create config directory if it doesn't exist."""
    CONFIG_DIR.mkdir(parents=True, exist_ok=True)


def save_config(config: dict[str, str]) -> None:
    """Save config to file."""
    ensure_config_dir()
    with open(CONFIG_FILE, "w") as f:
        json.dump(config, f, indent=2)


def get_config() -> dict[str, str]:
    """Load config from file."""
    if not CONFIG_FILE.exists():
        return {}
    with open(CONFIG_FILE) as f:
        data: dict[str, str] = json.load(f)
        return data


class OAuthCallbackHandler(BaseHTTPRequestHandler):
    """HTTP handler for OAuth callback."""

    auth_code: str | None = None
    error: str | None = None

    def do_GET(self) -> None:
        """Handle GET request from OAuth callback."""
        parsed = urlparse(self.path)
        params = parse_qs(parsed.query)

        if "code" in params:
            OAuthCallbackHandler.auth_code = params["code"][0]
            self.send_response(200)
            self.send_header("Content-type", "text/html")
            self.end_headers()
            self.wfile.write(b"""
            <!DOCTYPE html>
            <html>
            <head>
                <title>stk - Login Successful</title>
                <style>
                    body {
                        font-family: -apple-system, BlinkMacSystemFont, 'Segoe UI', Roboto, sans-serif;
                        display: flex;
                        justify-content: center;
                        align-items: center;
                        height: 100vh;
                        margin: 0;
                        background: linear-gradient(135deg, #667eea 0%, #764ba2 100%);
                        color: white;
                    }
                    .container {
                        text-align: center;
                        padding: 40px;
                        background: rgba(0,0,0,0.3);
                        border-radius: 16px;
                    }
                    h1 { font-size: 3em; margin: 0; }
                    p { font-size: 1.2em; opacity: 0.9; }
                    .emoji { font-size: 4em; }
                </style>
            </head>
            <body>
                <div class="container">
                    <div class="emoji">&#x1F525;</div>
                    <h1>Success!</h1>
                    <p>You can close this window and return to your terminal.</p>
                </div>
            </body>
            </html>
            """)
        elif "error" in params:
            OAuthCallbackHandler.error = params["error"][0]
            self.send_response(400)
            self.send_header("Content-type", "text/html")
            self.end_headers()
            self.wfile.write(b"<h1>Login Failed</h1>")
        else:
            self.send_response(400)
            self.send_header("Content-type", "text/html")
            self.end_headers()
            self.wfile.write(b"<h1>Invalid Callback</h1>")

    def log_message(self, format: str, *args: object) -> None:
        """Suppress default logging."""
        pass


def is_port_available(port: int) -> bool:
    """Check if a port is available."""
    with socket.socket(socket.AF_INET, socket.SOCK_STREAM) as s:
        try:
            s.bind(("localhost", port))
            return True
        except OSError:
            return False


@app.command()
def login(
    email: str = typer.Option(None, "--email", "-e", help="Account email"),
) -> None:
    """Log in to MyRunStreak (email + password).

    Creates the app session the CLI needs for plan, metrics, stats, and sync.
    To connect your SmashRun source for run-sync, use 'stk auth connect'.
    """
    if not email:
        email = typer.prompt("Email")
    password = typer.prompt("Password", hide_input=True)

    display.display_sync_progress("Logging in...")
    # post_unauth prints a useful error and exits on failure (e.g. bad password).
    data = post_unauth("auth/login", {"email": email, "password": password})

    resolved_email = (data.get("user") or {}).get("email") or email
    session_mod.save(
        access_token=data["access_token"],
        refresh_token=data["refresh_token"],
        expires_in=data.get("expires_in"),
        email=resolved_email,
    )
    display.display_sync_progress(f"Logged in as {resolved_email}", done=True)
    console.print("\n[green]Session saved — 'stk plan', 'stk splits', 'stk sync' now work.[/green]")


@app.command(name="connect")
def connect_smashrun(
    no_browser: bool = typer.Option(False, "--no-browser", help="Don't open browser automatically"),
) -> None:
    """Connect your SmashRun account (OAuth) so the backend can sync your runs."""
    port = 9876
    redirect_uri = f"http://localhost:{port}/callback"

    # Check if we can use automatic callback
    if not is_port_available(port):
        display.display_error(f"Port {port} is in use")
        display.display_info(f"Check what's using it: lsof -i :{port}")
        raise typer.Exit(1)

    # Get login URL from API
    display.display_sync_progress("Getting login URL...")

    try:
        url = f"{get_api_url()}/auth/login-url"
        response = httpx.get(url, params={"redirect_uri": redirect_uri}, timeout=TIMEOUT)
        response.raise_for_status()
        data: dict[str, Any] = response.json()
        auth_url = data["auth_url"]
    except Exception as e:
        display.display_error(f"Failed to get login URL: {e}")
        raise typer.Exit(1) from None

    # Show panel and open browser
    if no_browser:
        console.print(
            Panel(
                "[bold]Authorize with SmashRun[/bold]\n\n"
                f"[cyan]{auth_url}[/cyan]\n\n"
                "After authorizing, copy the [bold]code[/bold] from the URL.",
                title="Login",
                border_style="cyan",
            )
        )
        auth_code = typer.prompt("Paste authorization code")
    else:
        console.print(
            Panel(
                "[bold]Authorize with SmashRun[/bold]\n\n"
                "Opening browser for authorization...\n"
                "Waiting for callback...",
                title="Login",
                border_style="cyan",
            )
        )

        # Reset state and start server
        OAuthCallbackHandler.auth_code = None
        OAuthCallbackHandler.error = None

        server = HTTPServer(("localhost", port), OAuthCallbackHandler)
        server.timeout = 120

        # Open browser
        webbrowser.open(auth_url)

        # Wait for callback
        try:
            server.handle_request()
            server.server_close()

            if OAuthCallbackHandler.error:
                display.display_error(f"Authorization failed: {OAuthCallbackHandler.error}")
                raise typer.Exit(1)
            if not OAuthCallbackHandler.auth_code:
                display.display_error("Timed out waiting for authorization")
                raise typer.Exit(1)

            auth_code = OAuthCallbackHandler.auth_code
            display.display_sync_progress("Authorization received!", done=True)
        except Exception as e:
            server.server_close()
            display.display_error(f"Callback failed: {e}")
            raise typer.Exit(1) from None

    # Exchange code via API
    display.display_sync_progress("Completing login...")

    try:
        url = f"{get_api_url()}/auth/callback"
        response = httpx.post(
            url,
            json={"code": auth_code, "redirect_uri": redirect_uri},
            timeout=TIMEOUT,
        )
        response.raise_for_status()
        result: dict[str, Any] = response.json()

        user_id = result["user_id"]
        username = result["username"]
        created = result.get("created", False)

        # Save to config
        config = get_config()
        config["user_id"] = user_id
        config["username"] = username
        save_config(config)

        if created:
            display.display_sync_progress(f"Account created for {username}!", done=True)
        else:
            display.display_sync_progress(f"Welcome back, {username}!", done=True)

        console.print(
            "\n[green]SmashRun connected.[/green] "
            "Make sure you've run [bold]stk auth login[/bold], then [bold]stk sync[/bold]."
        )

    except httpx.HTTPStatusError as e:
        try:
            error_data = e.response.json()
            error_msg = error_data.get("message", e.response.text)
        except Exception:
            error_msg = e.response.text
        display.display_error(f"Login failed: {error_msg}")
        raise typer.Exit(1) from None
    except Exception as e:
        display.display_error(f"Login failed: {e}")
        raise typer.Exit(1) from None


@app.command()
def logout() -> None:
    """Log out — remove the app session and the SmashRun config."""
    had_session = session_mod.clear()
    had_config = CONFIG_FILE.exists()
    if had_config:
        CONFIG_FILE.unlink()
    if had_session or had_config:
        display.display_sync_progress("Logged out", done=True)
        display.display_info(f"Cleared credentials from {CONFIG_DIR}")
    else:
        display.display_info("Not logged in")


@app.command()
def status() -> None:
    """Show authentication status (app session + SmashRun connection)."""
    s = session_mod.load()
    config = get_config()

    if s is None:
        display.display_warning("Not logged in (no app session)")
        display.display_info("Run 'stk auth login' to authenticate")
    else:
        state = "expired — auto-refreshes" if s.is_expired() else "active"
        console.print(f"[bold]Logged in:[/bold] {s.email}  [dim]({state})[/dim]")

    if config.get("username"):
        display.display_info(f"SmashRun connected: {config.get('username')}")
    elif s is not None:
        display.display_info("SmashRun not connected — run 'stk auth connect'")
