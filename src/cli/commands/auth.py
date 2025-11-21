"""Auth commands for stk CLI."""

import json
import socket
from http.server import BaseHTTPRequestHandler, HTTPServer
from pathlib import Path
from typing import Any
from urllib.parse import parse_qs, urlparse
import webbrowser

import httpx
import typer
from rich.console import Console
from rich.panel import Panel

from cli import display
from cli.api import get_api_url

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
    no_browser: bool = typer.Option(False, "--no-browser", help="Don't open browser automatically"),
) -> None:
    """Login to SmashRun via OAuth."""
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

        console.print("\n[green]You can now run 'stk sync' to fetch your runs![/green]")

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
    """Remove saved credentials."""
    if CONFIG_FILE.exists():
        CONFIG_FILE.unlink()
        display.display_sync_progress("Logged out", done=True)
        display.display_info(f"Removed config from {CONFIG_DIR}")
    else:
        display.display_info("Not logged in")


@app.command()
def status() -> None:
    """Show authentication status."""
    config = get_config()

    if not config.get("user_id"):
        display.display_warning("Not logged in")
        display.display_info("Run 'stk auth login' to authenticate")
        return

    username = config.get("username", "Unknown")
    user_id = config.get("user_id", "")

    console.print(f"[bold]User:[/bold] {username}")
    display.display_sync_progress("Logged in", done=True)
    display.display_info(f"User ID: {user_id[:8]}...")
    display.display_info(f"Config: {CONFIG_DIR}")
