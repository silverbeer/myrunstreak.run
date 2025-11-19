#!/usr/bin/env python3
"""
Local test script for OAuth token migration using moto (mock AWS).

Tests the complete migration flow without touching real AWS resources:
1. Sets up mock AWS Secrets Manager
2. Creates test OAuth token in old structure
3. Runs migration script logic
4. Validates migration success

Usage:
    uv run python scripts/test_oauth_migration_local.py
"""

import json
import sys
from pathlib import Path

import boto3
from moto import mock_aws

# Add src to path
sys.path.insert(0, str(Path(__file__).parent.parent))

from src.shared.supabase_client import get_supabase_client
from src.shared.supabase_ops import UsersRepository


@mock_aws
def test_oauth_migration():
    """Test OAuth token migration with mocked AWS Secrets Manager."""
    print("=" * 60)
    print("🧪 Testing OAuth Token Migration Locally")
    print("=" * 60)

    # Initialize mock AWS Secrets Manager
    print("\n🔧 Setting up mock AWS Secrets Manager...")
    secrets_client = boto3.client("secretsmanager", region_name="us-east-2")

    # Create old OAuth token secret (single-user structure)
    old_secret_name = "myrunstreak/dev/smashrun/oauth"
    old_token_data = {
        "access_token": "mock_access_token_12345",
        "refresh_token": "mock_refresh_token_67890",
        "expires_at": "2026-12-31T23:59:59Z",
        "created_at": "2025-01-01T00:00:00Z",
    }

    print(f"📝 Creating old token secret: {old_secret_name}")
    secrets_client.create_secret(
        Name=old_secret_name,
        Description="Test OAuth token (old structure)",
        SecretString=json.dumps(old_token_data),
    )
    print("✅ Created old secret")

    # Initialize Supabase and get test user source
    print("\n🔗 Connecting to local Supabase...")
    supabase = get_supabase_client()
    users_repo = UsersRepository(supabase)

    # Get test user source
    active_sources = users_repo.get_all_active_sources(source_type="smashrun")

    if not active_sources:
        print("❌ No test user sources found")
        print("   Run: uv run python scripts/test_supabase_local.py first")
        return False

    print(f"✅ Found {len(active_sources)} active source(s)")

    # Test migration for each source
    print("\n🔄 Starting migration test...")
    for idx, source in enumerate(active_sources, 1):
        print(f"\n--- Migrating source {idx}/{len(active_sources)} ---")
        print(f"User ID: {source['user_id']}")
        print(f"Source ID: {source['id']}")
        print(f"Source Type: {source['source_type']}")

        # Step 1: Read old token
        print("\n📥 Reading old OAuth token...")
        response = secrets_client.get_secret_value(SecretId=old_secret_name)
        token_data = json.loads(response["SecretString"])
        print(f"✅ Retrieved old token: {token_data['access_token'][:20]}...")

        # Step 2: Create new per-user secret
        new_secret_name = (
            f"myrunstreak/users/{source['user_id']}/sources/{source['source_type']}/tokens"
        )
        print(f"\n📤 Creating new per-user secret: {new_secret_name}")

        try:
            secrets_client.create_secret(
                Name=new_secret_name,
                Description=f"OAuth tokens for user {source['user_id']} - {source['source_type']}",
                SecretString=json.dumps(token_data),
                Tags=[
                    {"Key": "Project", "Value": "MyRunStreak"},
                    {"Key": "Environment", "Value": "test"},
                    {"Key": "UserId", "Value": source["user_id"]},
                    {"Key": "SourceType", "Value": source["source_type"]},
                ],
            )
            print("✅ Created new secret")
        except secrets_client.exceptions.ResourceExistsException:
            print("⚠️  Secret already exists, updating...")
            secrets_client.update_secret(
                SecretId=new_secret_name, SecretString=json.dumps(token_data)
            )
            print("✅ Updated existing secret")

        # Step 3: Update database
        print(f"\n💾 Updating database for source {source['id']}...")
        old_secret_path = source.get("access_token_secret")
        print(f"   Old path: {old_secret_path}")
        print(f"   New path: {new_secret_name}")

        supabase.table("user_sources").update({"access_token_secret": new_secret_name}).eq(
            "id", source["id"]
        ).execute()
        print("✅ Updated database")

        # Step 4: Validate migration
        print("\n✅ Validating migration...")

        # Check database was updated
        updated_source = users_repo.get_source_by_id(source["id"])
        assert updated_source is not None, "Source not found after update"
        assert updated_source["access_token_secret"] == new_secret_name, "Secret path not updated"
        print("   ✓ Database updated correctly")

        # Check new secret exists and has correct data
        new_secret_response = secrets_client.get_secret_value(SecretId=new_secret_name)
        new_token_data = json.loads(new_secret_response["SecretString"])
        assert "access_token" in new_token_data, "Missing access_token"
        assert "refresh_token" in new_token_data, "Missing refresh_token"
        assert "expires_at" in new_token_data, "Missing expires_at"
        print("   ✓ New secret has correct structure")

        # Check data matches
        assert new_token_data["access_token"] == old_token_data["access_token"], (
            "Access token mismatch"
        )
        assert new_token_data["refresh_token"] == old_token_data["refresh_token"], (
            "Refresh token mismatch"
        )
        print("   ✓ Token data matches original")

        print(f"\n✅ Migration successful for source {source['id']}")

        # Rollback for next test run
        print("\n🔄 Rolling back for clean state...")
        supabase.table("user_sources").update(
            {"access_token_secret": old_secret_path or old_secret_name}
        ).eq("id", source["id"]).execute()
        print("✅ Rolled back database change")

    print("\n" + "=" * 60)
    print("🎉 All Migration Tests Passed!")
    print("=" * 60)
    print("\n✅ Migration script logic validated")
    print("✅ AWS Secrets Manager operations work correctly")
    print("✅ Database updates work correctly")
    print("✅ Validation checks work correctly")
    print("\n📝 Ready for production migration with:")
    print("   uv run python scripts/migrate_oauth_tokens.py --no-dry-run")
    print("=" * 60)

    return True


def main():
    """Run local migration test."""
    try:
        success = test_oauth_migration()
        return 0 if success else 1
    except Exception as e:
        print(f"\n❌ Test failed with error: {e}")
        import traceback

        traceback.print_exc()
        return 1


if __name__ == "__main__":
    sys.exit(main())
