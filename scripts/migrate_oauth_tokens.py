#!/usr/bin/env python3
"""
OAuth Token Migration Script for Supabase Multi-User Architecture.

Migrates OAuth tokens from single-user structure to per-user structure:
- Old: myrunstreak/dev/smashrun/oauth (single token)
- New: myrunstreak/users/{user_id}/sources/{source_type}/tokens (per-user)

This script:
1. Reads the old OAuth token from AWS Secrets Manager
2. For each active user source in Supabase:
   - Creates a new secret with per-user path structure
   - Copies the OAuth tokens to the new secret
   - Updates user_sources table with the new secret path
3. Validates the migration
4. Supports dry-run mode (default) for safety

Usage:
    # Dry run (default, safe)
    uv run python scripts/migrate_oauth_tokens.py

    # Dry run with explicit flag
    uv run python scripts/migrate_oauth_tokens.py --dry-run

    # Actually perform migration
    uv run python scripts/migrate_oauth_tokens.py --no-dry-run

    # Specify custom environment
    uv run python scripts/migrate_oauth_tokens.py --environment prod --no-dry-run
"""

import argparse
import json
import sys
from pathlib import Path
from typing import Any

import boto3
from botocore.exceptions import ClientError

# Add src to path
sys.path.insert(0, str(Path(__file__).parent.parent))

from src.shared.supabase_client import get_supabase_client
from src.shared.supabase_ops import UsersRepository


def get_old_oauth_token(secrets_client: Any, old_secret_name: str) -> dict[str, Any] | None:
    """
    Get OAuth token from old single-user secret.

    Args:
        secrets_client: Boto3 Secrets Manager client
        old_secret_name: Name of the old secret

    Returns:
        Token data or None if not found
    """
    print(f"\n📥 Reading old OAuth token from: {old_secret_name}")

    try:
        response = secrets_client.get_secret_value(SecretId=old_secret_name)
        token_data = json.loads(response["SecretString"])

        print("✅ Found old OAuth token")
        print(f"   Access token: {token_data.get('access_token', 'N/A')[:20]}...")
        print(f"   Refresh token: {token_data.get('refresh_token', 'N/A')[:20]}...")
        print(f"   Expires at: {token_data.get('expires_at', 'N/A')}")

        return token_data

    except secrets_client.exceptions.ResourceNotFoundException:
        print(f"⚠️  Old secret not found: {old_secret_name}")
        print("   This is expected if tokens haven't been initialized yet")
        return None

    except ClientError as e:
        print(f"❌ Failed to read old secret: {e}")
        return None


def create_per_user_secret(
    secrets_client: Any,
    user_id: str,
    source_type: str,
    token_data: dict[str, Any],
    environment: str,
    dry_run: bool,
) -> str:
    """
    Create per-user OAuth token secret.

    Args:
        secrets_client: Boto3 Secrets Manager client
        user_id: User UUID
        source_type: Source type (e.g., 'smashrun')
        token_data: OAuth token data
        environment: Environment (dev, prod)
        dry_run: If True, don't actually create secret

    Returns:
        New secret name/path
    """
    # Generate new secret name
    new_secret_name = f"myrunstreak/users/{user_id}/sources/{source_type}/tokens"

    print(f"\n📤 Creating per-user secret: {new_secret_name}")

    if dry_run:
        print("   [DRY RUN] Would create secret with:")
        print(f"      Access token: {token_data.get('access_token', 'N/A')[:20]}...")
        print(f"      Refresh token: {token_data.get('refresh_token', 'N/A')[:20]}...")
        return new_secret_name

    try:
        # Check if secret already exists
        try:
            secrets_client.get_secret_value(SecretId=new_secret_name)
            print(f"⚠️  Secret already exists: {new_secret_name}")
            print("   Updating existing secret...")

            # Update existing secret
            secrets_client.update_secret(
                SecretId=new_secret_name, SecretString=json.dumps(token_data)
            )
            print("✅ Updated existing secret")

        except secrets_client.exceptions.ResourceNotFoundException:
            # Create new secret
            secrets_client.create_secret(
                Name=new_secret_name,
                Description=f"OAuth tokens for user {user_id} - {source_type}",
                SecretString=json.dumps(token_data),
                Tags=[
                    {"Key": "Project", "Value": "MyRunStreak"},
                    {"Key": "Environment", "Value": environment},
                    {"Key": "UserId", "Value": user_id},
                    {"Key": "SourceType", "Value": source_type},
                ],
            )
            print("✅ Created new secret")

        return new_secret_name

    except ClientError as e:
        print(f"❌ Failed to create secret: {e}")
        raise


def update_user_source_secret_path(
    users_repo: UsersRepository, source_id: str, new_secret_path: str, dry_run: bool
) -> None:
    """
    Update user_sources table with new secret path.

    Args:
        users_repo: UsersRepository instance
        source_id: User source UUID
        new_secret_path: New secret path
        dry_run: If True, don't actually update
    """
    print(f"\n💾 Updating user_sources table for source {source_id}")
    print(f"   New secret path: {new_secret_path}")

    if dry_run:
        print("   [DRY RUN] Would update database")
        return

    try:
        users_repo.supabase.table("user_sources").update(
            {"access_token_secret": new_secret_path}
        ).eq("id", source_id).execute()

        print("✅ Updated database")

    except Exception as e:
        print(f"❌ Failed to update database: {e}")
        raise


def validate_migration(
    secrets_client: Any, users_repo: UsersRepository, source: dict[str, Any]
) -> bool:
    """
    Validate that migration was successful for a source.

    Args:
        secrets_client: Boto3 Secrets Manager client
        users_repo: UsersRepository instance
        source: User source record

    Returns:
        True if validation passes
    """
    print(f"\n✅ Validating migration for source {source['id']}")

    try:
        # Get updated source from database
        updated_source = users_repo.get_source_by_id(source["id"])

        if not updated_source:
            print("❌ Source not found in database")
            return False

        new_secret_path = updated_source["access_token_secret"]
        print(f"   Database secret path: {new_secret_path}")

        # Verify secret exists and has correct data
        try:
            response = secrets_client.get_secret_value(SecretId=new_secret_path)
            token_data = json.loads(response["SecretString"])

            required_fields = ["access_token", "refresh_token", "expires_at"]
            for field in required_fields:
                if field not in token_data:
                    print(f"❌ Missing field in secret: {field}")
                    return False

            print("✅ Secret exists and has correct structure")
            return True

        except secrets_client.exceptions.ResourceNotFoundException:
            print(f"❌ Secret not found: {new_secret_path}")
            return False

    except Exception as e:
        print(f"❌ Validation failed: {e}")
        return False


def main():
    """Run OAuth token migration."""
    parser = argparse.ArgumentParser(description="Migrate OAuth tokens to per-user structure")
    parser.add_argument(
        "--dry-run",
        action="store_true",
        default=True,
        help="Perform dry run without making changes (default)",
    )
    parser.add_argument(
        "--no-dry-run",
        dest="dry_run",
        action="store_false",
        help="Actually perform migration (USE WITH CAUTION)",
    )
    parser.add_argument(
        "--environment",
        choices=["dev", "prod"],
        default="dev",
        help="Environment to migrate (default: dev)",
    )
    parser.add_argument(
        "--old-secret",
        default="myrunstreak/dev/smashrun/oauth",
        help="Old secret name (default: myrunstreak/dev/smashrun/oauth)",
    )
    parser.add_argument("--region", default="us-east-2", help="AWS region (default: us-east-2)")

    args = parser.parse_args()

    print("=" * 60)
    print("🔐 OAuth Token Migration Script")
    print("=" * 60)
    print(f"\nMode: {'DRY RUN (safe)' if args.dry_run else 'LIVE MIGRATION'}")
    print(f"Environment: {args.environment}")
    print(f"AWS Region: {args.region}")
    print(f"Old Secret: {args.old_secret}")

    if not args.dry_run:
        print("\n⚠️  WARNING: This will modify AWS Secrets Manager and Supabase!")
        response = input("Are you sure you want to continue? (yes/no): ")
        if response.lower() != "yes":
            print("❌ Migration cancelled")
            return 1

    # Initialize clients
    print("\n🔧 Initializing clients...")
    secrets_client = boto3.client("secretsmanager", region_name=args.region)
    supabase = get_supabase_client()
    users_repo = UsersRepository(supabase)

    # Get old OAuth token
    old_token_data = get_old_oauth_token(secrets_client, args.old_secret)

    if not old_token_data:
        print("\n❌ No old token found - cannot proceed with migration")
        print("   Please ensure OAuth tokens are initialized first")
        return 1

    # Get all active user sources
    print("\n📋 Fetching active user sources from Supabase...")
    active_sources = users_repo.get_all_active_sources(source_type="smashrun")
    print(f"✅ Found {len(active_sources)} active SmashRun source(s)")

    if not active_sources:
        print("\n⚠️  No active sources to migrate")
        return 0

    # Migrate each source
    migration_results = []

    for idx, source in enumerate(active_sources, 1):
        print("\n" + "=" * 60)
        print(f"Migrating source {idx}/{len(active_sources)}")
        print("=" * 60)
        print(f"User ID: {source['user_id']}")
        print(f"Source ID: {source['id']}")
        print(f"Source Type: {source['source_type']}")

        try:
            # Create per-user secret
            new_secret_path = create_per_user_secret(
                secrets_client=secrets_client,
                user_id=source["user_id"],
                source_type=source["source_type"],
                token_data=old_token_data,
                environment=args.environment,
                dry_run=args.dry_run,
            )

            # Update database
            update_user_source_secret_path(
                users_repo=users_repo,
                source_id=source["id"],
                new_secret_path=new_secret_path,
                dry_run=args.dry_run,
            )

            # Validate (only if not dry run)
            if not args.dry_run:
                validation_passed = validate_migration(secrets_client, users_repo, source)
                migration_results.append({"source_id": source["id"], "success": validation_passed})
            else:
                migration_results.append({"source_id": source["id"], "success": True})

            print(f"\n✅ Migration complete for source {source['id']}")

        except Exception as e:
            print(f"\n❌ Migration failed for source {source['id']}: {e}")
            migration_results.append({"source_id": source["id"], "success": False})
            continue

    # Summary
    print("\n" + "=" * 60)
    print("📊 Migration Summary")
    print("=" * 60)

    successful = sum(1 for r in migration_results if r["success"])
    failed = len(migration_results) - successful

    print(f"\nTotal sources: {len(migration_results)}")
    print(f"✅ Successful: {successful}")
    print(f"❌ Failed: {failed}")

    if args.dry_run:
        print("\n🔍 DRY RUN COMPLETE - No changes were made")
        print("   Run with --no-dry-run to perform actual migration")

    print("\n" + "=" * 60)

    return 0 if failed == 0 else 1


if __name__ == "__main__":
    sys.exit(main())
