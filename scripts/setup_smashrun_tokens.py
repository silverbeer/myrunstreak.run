#!/usr/bin/env python3
"""
Setup script for SmashRun OAuth tokens.

This script helps you complete the OAuth flow and store tokens in AWS Secrets Manager
for the Lambda function to use.

Usage:
    python scripts/setup_smashrun_tokens.py
"""

import logging

from src.shared.config import get_settings
from src.shared.smashrun import SmashRunOAuthClient, TokenManager

logging.basicConfig(level=logging.INFO)
logger = logging.getLogger(__name__)


def main() -> None:
    """Run OAuth flow and store tokens in Secrets Manager."""
    print("=" * 60)
    print("MyRunStreak.com - SmashRun OAuth Setup")
    print("=" * 60)
    print()

    # Load settings
    settings = get_settings()

    # Create OAuth client
    oauth_client = SmashRunOAuthClient(
        client_id=settings.smashrun_client_id,
        client_secret=settings.smashrun_client_secret,
        redirect_uri=settings.smashrun_redirect_uri,
    )

    # Step 1: Generate authorization URL
    print("Step 1: Authorize Application")
    print("-" * 60)
    auth_url = oauth_client.get_authorization_url(state="setup_script")
    print(f"\nVisit this URL to authorize:\n{auth_url}\n")
    print("After authorizing, you'll be redirected to:")
    print(f"{settings.smashrun_redirect_uri}?code=AUTH_CODE&state=setup_script")
    print()

    # Step 2: Get authorization code
    print("Step 2: Enter Authorization Code")
    print("-" * 60)
    auth_code = input("Paste the authorization code from the URL: ").strip()

    if not auth_code:
        print("Error: No authorization code provided")
        return

    # Step 3: Exchange code for tokens
    print("\nStep 3: Exchange Code for Tokens")
    print("-" * 60)
    try:
        token_data = oauth_client.exchange_code_for_token(auth_code)
        print("✓ Successfully obtained tokens")
        print(f"  Access Token: {token_data['access_token'][:20]}...")
        print(f"  Refresh Token: {token_data['refresh_token'][:20]}...")
        print(f"  Expires In: {token_data['expires_in']} seconds (~12 weeks)")
    except Exception as e:
        print(f"✗ Failed to exchange code: {e}")
        return

    # Step 4: Store in AWS Secrets Manager
    print("\nStep 4: Store Tokens in AWS Secrets Manager")
    print("-" * 60)

    confirm = input(
        "\nThis will store tokens in AWS Secrets Manager.\n"
        "Make sure you have AWS credentials configured.\n"
        "Continue? [y/N]: "
    ).strip().lower()

    if confirm != "y":
        print("Aborted.")
        print("\nTokens obtained but not stored:")
        print(f"Access Token: {token_data['access_token']}")
        print(f"Refresh Token: {token_data['refresh_token']}")
        return

    try:
        token_manager = TokenManager(
            secret_name="myrunstreak/smashrun/tokens",
            oauth_client=oauth_client,
            region_name=settings.aws_region,
        )

        token_manager.initialize_tokens(
            access_token=token_data["access_token"],
            refresh_token=token_data["refresh_token"],
            expires_in=token_data["expires_in"],
        )

        print("✓ Successfully stored tokens in AWS Secrets Manager")
        print(f"  Secret Name: myrunstreak/smashrun/tokens")
        print(f"  Region: {settings.aws_region}")

    except Exception as e:
        print(f"✗ Failed to store tokens: {e}")
        print("\nTokens obtained but not stored:")
        print(f"Access Token: {token_data['access_token']}")
        print(f"Refresh Token: {token_data['refresh_token']}")
        return

    # Success!
    print("\n" + "=" * 60)
    print("Setup Complete!")
    print("=" * 60)
    print("\nYour Lambda function can now:")
    print("  • Fetch runs from SmashRun")
    print("  • Automatically refresh tokens")
    print("  • Sync daily without intervention")
    print("\nNext steps:")
    print("  1. Deploy Lambda function with Terraform")
    print("  2. Set up EventBridge schedule (daily trigger)")
    print("  3. Watch your runs sync automatically!")
    print()


if __name__ == "__main__":
    try:
        main()
    except KeyboardInterrupt:
        print("\n\nAborted by user.")
    except Exception as e:
        logger.exception(f"Setup failed: {e}")
