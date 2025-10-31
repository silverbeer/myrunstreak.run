"""SmashRun OAuth 2.0 client implementation."""

import logging
from typing import Any
from urllib.parse import urlencode

import httpx
from authlib.integrations.httpx_client import OAuth2Client

logger = logging.getLogger(__name__)


class SmashRunOAuthClient:
    """
    OAuth 2.0 client for SmashRun API.

    Implements the authorization code flow with refresh token support.
    """

    # SmashRun OAuth endpoints
    AUTHORIZATION_ENDPOINT = "https://secure.smashrun.com/oauth2/authenticate"
    TOKEN_ENDPOINT = "https://secure.smashrun.com/oauth2/token"

    # Available scopes
    SCOPE_READ_ACTIVITY = "read_activity"
    SCOPE_WRITE_ACTIVITY = "write_activity"

    def __init__(
        self,
        client_id: str,
        client_secret: str,
        redirect_uri: str,
        scope: str = SCOPE_READ_ACTIVITY,
    ) -> None:
        """
        Initialize OAuth client.

        Args:
            client_id: SmashRun OAuth client ID
            client_secret: SmashRun OAuth client secret
            redirect_uri: Redirect URI for OAuth callback
            scope: OAuth scope (default: read_activity)
        """
        self.client_id = client_id
        self.client_secret = client_secret
        self.redirect_uri = redirect_uri
        self.scope = scope

        self._oauth_client: OAuth2Client | None = None

    def get_authorization_url(self, state: str | None = None) -> str:
        """
        Generate authorization URL for user to authenticate.

        Args:
            state: Optional state parameter for CSRF protection

        Returns:
            Authorization URL to redirect user to
        """
        params = {
            "client_id": self.client_id,
            "redirect_uri": self.redirect_uri,
            "response_type": "code",
            "scope": self.scope,
        }

        if state:
            params["state"] = state

        url = f"{self.AUTHORIZATION_ENDPOINT}?{urlencode(params)}"
        logger.info(f"Generated authorization URL with scope: {self.scope}")
        return url

    def exchange_code_for_token(self, authorization_code: str) -> dict[str, Any]:
        """
        Exchange authorization code for access token.

        Args:
            authorization_code: Authorization code from OAuth callback

        Returns:
            Token response containing access_token, refresh_token, expires_in, etc.

        Raises:
            httpx.HTTPStatusError: If token exchange fails
        """
        logger.info("Exchanging authorization code for access token")

        data = {
            "grant_type": "authorization_code",
            "code": authorization_code,
            "client_id": self.client_id,
            "client_secret": self.client_secret,
            "redirect_uri": self.redirect_uri,
        }

        with httpx.Client() as client:
            response = client.post(
                self.TOKEN_ENDPOINT,
                data=data,
                headers={"Accept": "application/json"},
            )
            response.raise_for_status()
            token_data = response.json()

        logger.info("Successfully obtained access token")
        return token_data

    def refresh_access_token(self, refresh_token: str) -> dict[str, Any]:
        """
        Refresh an expired access token using a refresh token.

        Args:
            refresh_token: Refresh token from previous token exchange

        Returns:
            New token response with fresh access_token

        Raises:
            httpx.HTTPStatusError: If token refresh fails
        """
        logger.info("Refreshing access token")

        data = {
            "grant_type": "refresh_token",
            "refresh_token": refresh_token,
            "client_id": self.client_id,
            "client_secret": self.client_secret,
        }

        with httpx.Client() as client:
            response = client.post(
                self.TOKEN_ENDPOINT,
                data=data,
                headers={"Accept": "application/json"},
            )
            response.raise_for_status()
            token_data = response.json()

        logger.info("Successfully refreshed access token")
        return token_data

    def create_authorized_client(self, access_token: str) -> OAuth2Client:
        """
        Create an authorized HTTP client with access token.

        Args:
            access_token: Valid access token

        Returns:
            OAuth2Client configured with access token
        """
        token = {"access_token": access_token, "token_type": "Bearer"}

        client = OAuth2Client(
            client_id=self.client_id,
            client_secret=self.client_secret,
            token=token,
        )

        return client

    def revoke_token(self, token: str, token_type_hint: str = "access_token") -> None:
        """
        Revoke an access or refresh token.

        Note: SmashRun may not support token revocation. This is a best-effort attempt.

        Args:
            token: Token to revoke
            token_type_hint: Type of token ('access_token' or 'refresh_token')
        """
        logger.info(f"Attempting to revoke {token_type_hint}")

        # SmashRun doesn't explicitly document a revocation endpoint
        # Tokens are revoked by user action in their settings
        logger.warning(
            "SmashRun token revocation must be done through user account settings at "
            "https://smashrun.com/settings/api"
        )
