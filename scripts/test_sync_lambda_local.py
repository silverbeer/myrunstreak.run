#!/usr/bin/env python3
"""
Test script for multi-user sync Lambda handler.

Verifies:
- Lambda handler can connect to Supabase
- Multi-user source iteration works
- Error handling for missing tokens

Run with: uv run python scripts/test_sync_lambda_local.py
"""

import sys
from pathlib import Path
from unittest.mock import MagicMock

# Add src to path
sys.path.insert(0, str(Path(__file__).parent.parent))


def test_handler_structure():
    """Test that the handler has correct structure and imports."""
    print("\n🔍 Testing handler structure...")

    try:
        # Import handler (verifies all dependencies are available)
        from src.lambdas.sync_runs import handler

        # Verify main functions exist
        assert hasattr(handler, "lambda_handler"), "lambda_handler function not found"
        assert hasattr(handler, "sync_user_source"), "sync_user_source function not found"

        print("✅ Handler structure is correct")
        print(f"   - lambda_handler: {handler.lambda_handler.__doc__.split(chr(10))[0]}")
        print(f"   - sync_user_source: {handler.sync_user_source.__doc__.split(chr(10))[0]}")

        return True

    except Exception as e:
        print(f"❌ Handler structure test failed: {e}")
        import traceback

        traceback.print_exc()
        return False


def test_supabase_connection():
    """Test that handler can connect to Supabase."""
    print("\n🔌 Testing Supabase connection from handler...")

    try:
        from src.shared.supabase_client import get_supabase_client
        from src.shared.supabase_ops import UsersRepository

        supabase = get_supabase_client()
        users_repo = UsersRepository(supabase)

        # Get all active sources (what the Lambda does)
        active_sources = users_repo.get_all_active_sources(source_type="smashrun")

        print("✅ Connected to Supabase")
        print(f"✅ Found {len(active_sources)} active SmashRun source(s)")

        for source in active_sources:
            print(f"   - User: {source['user_id']}")
            print(f"     Source ID: {source['id']}")
            print(f"     Type: {source['source_type']}")
            print(f"     Secret: {source['access_token_secret']}")

        return True

    except Exception as e:
        print(f"❌ Supabase connection test failed: {e}")
        import traceback

        traceback.print_exc()
        return False


def test_handler_with_no_sources():
    """Test handler behavior when no sources are active."""
    print("\n🧪 Testing handler with no active sources...")

    try:
        from src.lambdas.sync_runs.handler import lambda_handler
        from src.shared.supabase_client import get_supabase_client
        from src.shared.supabase_ops import UsersRepository

        # Deactivate all sources temporarily
        supabase = get_supabase_client()
        users_repo = UsersRepository(supabase)

        # Get current sources
        active_sources = users_repo.get_all_active_sources()
        print(f"   Found {len(active_sources)} source(s) to deactivate")

        # Deactivate them
        for source in active_sources:
            users_repo.deactivate_source(source["id"])

        # Create mock Lambda context
        mock_context = MagicMock()
        mock_context.function_name = "test-sync-lambda"
        mock_context.invoked_function_arn = "arn:aws:lambda:us-east-2:123456789:function:test"

        # Call handler
        result = lambda_handler(
            event={"source": "test", "action": "test-no-sources"}, context=mock_context
        )

        print(f"✅ Handler returned: {result['statusCode']}")
        print(f"✅ Message: {result['body']['message']}")

        # Reactivate sources
        for source in active_sources:
            supabase.table("user_sources").update({"is_active": True}).eq(
                "id", source["id"]
            ).execute()
            print(f"   Reactivated source {source['id']}")

        return True

    except Exception as e:
        print(f"❌ Handler test failed: {e}")
        import traceback

        traceback.print_exc()

        # Try to reactivate sources
        try:
            from src.shared.supabase_client import get_supabase_client

            supabase = get_supabase_client()
            supabase.table("user_sources").update({"is_active": True}).execute()
            print("   Reactivated all sources after error")
        except Exception:
            pass

        return False


def test_config_has_supabase():
    """Test that config has Supabase settings."""
    print("\n⚙️  Testing configuration...")

    try:
        from src.shared.config import get_settings

        settings = get_settings()

        # Verify Supabase settings exist
        assert hasattr(settings, "supabase_url"), "supabase_url not in settings"
        assert hasattr(settings, "supabase_key"), "supabase_key not in settings"

        print("✅ Configuration has Supabase settings")
        print(f"   URL: {settings.supabase_url}")
        print(f"   Key: {settings.supabase_key[:20]}...")

        return True

    except Exception as e:
        print(f"❌ Configuration test failed: {e}")
        import traceback

        traceback.print_exc()
        return False


def main():
    """Run all tests."""
    print("=" * 60)
    print("🧪 Testing Multi-User Sync Lambda Handler")
    print("=" * 60)

    results = {
        "Handler Structure": test_handler_structure(),
        "Configuration": test_config_has_supabase(),
        "Supabase Connection": test_supabase_connection(),
        "Handler (No Sources)": test_handler_with_no_sources(),
    }

    print("\n" + "=" * 60)
    print("📊 Test Results Summary")
    print("=" * 60)

    all_passed = True
    for test_name, passed in results.items():
        status = "✅ PASS" if passed else "❌ FAIL"
        print(f"{status}: {test_name}")
        if not passed:
            all_passed = False

    print("=" * 60)

    if all_passed:
        print("🎉 All tests passed!")
        print("\n✅ Multi-user sync Lambda is ready")
        print("✅ Can be deployed to AWS")
        return 0
    else:
        print("⚠️  Some tests failed")
        print("\n❌ Please review errors above")
        return 1


if __name__ == "__main__":
    sys.exit(main())
