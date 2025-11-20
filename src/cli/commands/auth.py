"""Auth commands for stk CLI."""

import json
import socket
import webbrowser
from datetime import UTC, datetime, timedelta
from http.server import BaseHTTPRequestHandler, HTTPServer
from pathlib import Path
from typing import Any
from urllib.parse import parse_qs, urlparse

import typer
from rich.console import Console
from rich.panel import Panel

app = typer.Typer(help="Authentication commands")
console = Console()

# Config directory
CONFIG_DIR = Path.home() / ".config" / "stk"
TOKENS_FILE = CONFIG_DIR / "tokens.json"
CONFIG_FILE = CONFIG_DIR / "config.json"


def ensure_config_dir() -> None:
    """Create config directory if it doesn't exist."""
    CONFIG_DIR.mkdir(parents=True, exist_ok=True)


def save_tokens(token_data: dict[str, Any]) -> None:
    """Save tokens to config file."""
    ensure_config_dir()
    with open(TOKENS_FILE, "w") as f:
        json.dump(token_data, f, indent=2)


def get_tokens() -> dict[str, Any] | None:
    """Load tokens from config file."""
    if not TOKENS_FILE.exists():
        return None
    with open(TOKENS_FILE) as f:
        data: dict[str, Any] = json.load(f)
        return data


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
            OAuthCallbackHandler.error = params.get("error_description", params["error"])[0]
            self.send_response(400)
            self.send_header("Content-type", "text/html")
            self.end_headers()
            self.wfile.write(f"<h1>Error</h1><p>{OAuthCallbackHandler.error}</p>".encode())
        else:
            self.send_response(404)
            self.end_headers()

    def log_message(self, format: str, *args: object) -> None:
        """Suppress default logging."""
        pass


def wait_for_oauth_callback(port: int = 8000, timeout: int = 120) -> str:
    """
    Start a temporary server to receive OAuth callback.

    Args:
        port: Port to listen on
        timeout: Timeout in seconds

    Returns:
        Authorization code

    Raises:
        TimeoutError: If no callback received
        ValueError: If callback contains error
    """
    # Reset state
    OAuthCallbackHandler.auth_code = None
    OAuthCallbackHandler.error = None

    server = HTTPServer(("localhost", port), OAuthCallbackHandler)
    server.timeout = timeout

    # Handle one request
    server.handle_request()
    server.server_close()

    if OAuthCallbackHandler.error:
        raise ValueError(OAuthCallbackHandler.error)
    if not OAuthCallbackHandler.auth_code:
        raise TimeoutError("No authorization code received")

    return OAuthCallbackHandler.auth_code


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
    from cli import display

    try:
        from shared.config import get_settings
        from shared.smashrun import SmashRunOAuthClient
    except ImportError as e:
        display.display_error(f"Missing dependencies: {e}")
        display.display_info("Run 'uv sync' to install dependencies")
        raise typer.Exit(1) from None

    # Get settings
    try:
        settings = get_settings()
    except Exception as e:
        display.display_error(f"Failed to load settings: {e}")
        display.display_info(
            "Check your .env file has SMASHRUN_CLIENT_ID and SMASHRUN_CLIENT_SECRET"
        )
        raise typer.Exit(1) from None

    # Create OAuth client
    oauth_client = SmashRunOAuthClient(
        client_id=settings.smashrun_client_id,
        client_secret=settings.smashrun_client_secret,
        redirect_uri=settings.smashrun_redirect_uri,
    )

    # Get authorization URL
    auth_url = oauth_client.get_authorization_url(state="stk_cli")

    # Check if we can use automatic callback
    port = 8000
    if not is_port_available(port):
        if not no_browser:
            display.display_warning(f"Port {port} is in use - cannot auto-capture callback")
            display.display_info("Stop the other service or use: stk auth login --no-browser")
            display.display_info(f"Check what's using port {port}: lsof -i :{port}")
        use_auto_callback = False
    else:
        use_auto_callback = not no_browser

    if use_auto_callback:
        console.print(
            Panel(
                "[bold]Authorize with SmashRun[/bold]\n\n"
                "Opening browser for authorization...\n"
                "Waiting for callback...",
                title="Login",
                border_style="cyan",
            )
        )

        # Start server FIRST, then open browser
        # Reset state
        OAuthCallbackHandler.auth_code = None
        OAuthCallbackHandler.error = None

        server = HTTPServer(("localhost", port), OAuthCallbackHandler)
        server.timeout = 120

        # Now open browser
        webbrowser.open(auth_url)

        # Wait for callback
        try:
            server.handle_request()
            server.server_close()

            if OAuthCallbackHandler.error:
                display.display_error(f"Authorization failed: {OAuthCallbackHandler.error}")
                raise typer.Exit(1) from None
            if not OAuthCallbackHandler.auth_code:
                display.display_error("Timed out waiting for authorization")
                display.display_info("Try again or use --no-browser for manual mode")
                raise typer.Exit(1) from None

            auth_code = OAuthCallbackHandler.auth_code
            display.display_sync_progress("Authorization received!", done=True)
        except Exception as e:
            server.server_close()
            display.display_error(f"Callback failed: {e}")
            raise typer.Exit(1) from None
    else:
        # Fallback to manual code entry
        console.print(
            Panel(
                "[bold]Authorize with SmashRun[/bold]\n\n"
                f"[cyan]{auth_url}[/cyan]\n\n"
                "After authorizing, copy the [bold]code[/bold] from the URL.\n"
                "(The part after 'code=' and before '&')",
                title="Login",
                border_style="cyan",
            )
        )

        if not no_browser:
            console.print("\n[dim]Opening browser...[/dim]")
            webbrowser.open(auth_url)

        console.print()
        auth_code = typer.prompt("Paste authorization code")

        if not auth_code:
            display.display_error("No code provided")
            raise typer.Exit(1) from None

    # Exchange code for tokens
    display.display_sync_progress("Exchanging code for tokens...")

    try:
        token_data = oauth_client.exchange_code_for_token(auth_code)

        # Add expiration timestamp
        token_data["expires_at"] = (
            datetime.now(UTC) + timedelta(seconds=token_data["expires_in"])
        ).isoformat()

        # Save tokens
        save_tokens(token_data)
        display.display_sync_progress("Tokens saved", done=True)

        # Get SmashRun user info
        display.display_sync_progress("Getting SmashRun profile...")
        from shared.smashrun import SmashRunAPIClient

        with SmashRunAPIClient(access_token=token_data["access_token"]) as api_client:
            user_info = api_client.get_user_info()
            username = user_info.get("userName", "unknown")
            user_id_smashrun = str(user_info.get("id", ""))

        display.display_sync_progress(f"Welcome, {username}!", done=True)

        # Register with Supabase
        display.display_sync_progress("Registering with MyRunStreak...")
        try:
            from shared.supabase_client import get_supabase_client
            from shared.supabase_ops import UsersRepository

            supabase = get_supabase_client()
            users_repo = UsersRepository(supabase)

            user, created = users_repo.get_or_create_user_with_source(
                source_type="smashrun",
                source_username=username,
                source_user_id=user_id_smashrun,
                display_name=username,
            )

            user_id = user["user_id"]

            # Save user_id to config
            config = get_config()
            config["user_id"] = user_id
            config["username"] = username
            save_config(config)

            if created:
                display.display_sync_progress("Account created!", done=True)
            else:
                display.display_sync_progress("Account linked!", done=True)

        except Exception as e:
            display.display_warning(f"Could not register with Supabase: {e}")
            display.display_info("You can still use stk, but cloud sync may not work")

        console.print("\n[green]You can now run 'stk sync' to fetch your runs![/green]")

    except Exception as e:
        display.display_error(f"Login failed: {e}")
        raise typer.Exit(1) from None


@app.command()
def logout() -> None:
    """Remove saved credentials."""
    from cli import display

    removed = False
    if TOKENS_FILE.exists():
        TOKENS_FILE.unlink()
        removed = True
    if CONFIG_FILE.exists():
        CONFIG_FILE.unlink()
        removed = True

    if removed:
        display.display_sync_progress("Logged out", done=True)
        display.display_info(f"Removed config from {CONFIG_DIR}")
    else:
        display.display_info("Not logged in")


@app.command()
def status() -> None:
    """Show authentication status."""
    from cli import display

    tokens = get_tokens()
    config = get_config()

    if not tokens:
        display.display_warning("Not logged in")
        display.display_info("Run 'stk auth login' to authenticate")
        return

    # Show username if available
    username = config.get("username")
    if username:
        console.print(f"[bold]User:[/bold] {username}")

    # Check expiration
    expires_at_str = tokens.get("expires_at")
    if expires_at_str:
        expires_at = datetime.fromisoformat(expires_at_str)
        if expires_at.tzinfo is None:
            expires_at = expires_at.replace(tzinfo=UTC)

        now = datetime.now(UTC)
        if now >= expires_at:
            display.display_warning("Token expired")
            display.display_info(
                "Run 'stk sync' to refresh, or 'stk auth login' to re-authenticate"
            )
        else:
            days_left = (expires_at - now).days
            if days_left > 1:
                display.display_sync_progress(f"Logged in (expires in {days_left} days)", done=True)
            else:
                hours_left = int((expires_at - now).total_seconds() / 3600)
                display.display_warning(f"Token expires in {hours_left} hours")
    else:
        display.display_sync_progress("Logged in", done=True)

    # Show user_id status
    user_id = config.get("user_id")
    if user_id:
        display.display_info(f"User ID: {user_id[:8]}...")
    else:
        display.display_warning("No user ID - run 'stk auth login' to register")

    display.display_info(f"Config: {CONFIG_DIR}")
