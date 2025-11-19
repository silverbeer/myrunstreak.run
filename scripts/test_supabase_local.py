#!/usr/bin/env python3
"""
Test script for local Supabase infrastructure.

Verifies:
- Connection to local Supabase
- Database schema and tables
- Repository operations
- Data mappers

Run with: uv run python scripts/test_supabase_local.py
"""

import sys
from pathlib import Path
from uuid import UUID

# Add src to path
sys.path.insert(0, str(Path(__file__).parent.parent))

from datetime import datetime

from src.shared.models import Activity
from src.shared.supabase_client import get_supabase_client, test_connection
from src.shared.supabase_ops import (
    RunsRepository,
    UsersRepository,
    activity_to_run_dict,
)


def test_connection_status():
    """Test basic Supabase connection."""
    print("\n🔌 Testing Supabase Connection...")
    try:
        result = test_connection()
        print(f"✅ Connected to: {result['supabase_url']}")
        print(f"✅ User count: {result['user_count']}")
        return True
    except Exception as e:
        print(f"❌ Connection failed: {e}")
        return False


def test_users_repository():
    """Test UsersRepository operations."""
    print("\n👤 Testing UsersRepository...")
    supabase = get_supabase_client()
    users_repo = UsersRepository(supabase)

    try:
        # Check if test user exists (from seed data)
        test_user_id = UUID("00000000-0000-0000-0000-000000000001")
        user = users_repo.get_user_by_id(test_user_id)

        if user:
            print(f"✅ Found test user: {user['email']} ({user['display_name']})")
        else:
            print("❌ Test user not found in database")
            return False

        # Get user sources
        sources = users_repo.get_user_sources(test_user_id)
        print(f"✅ User has {len(sources)} data source(s)")

        for source in sources:
            print(
                f"   - {source['source_type']}: {source['source_user_id']} (active={source['is_active']})"
            )

        return True

    except Exception as e:
        print(f"❌ UsersRepository test failed: {e}")
        return False


def test_runs_repository():
    """Test RunsRepository operations."""
    print("\n🏃 Testing RunsRepository...")
    supabase = get_supabase_client()
    runs_repo = RunsRepository(supabase)

    try:
        # Get test user and source
        test_user_id = UUID("00000000-0000-0000-0000-000000000001")
        users_repo = UsersRepository(supabase)
        sources = users_repo.get_user_sources(test_user_id)

        if not sources:
            print("❌ No sources found for test user")
            return False

        source_id = UUID(sources[0]["id"])

        # Create a test activity
        print("📝 Creating test run...")
        test_activity = Activity(
            activity_id="test-12345",
            start_date_time_local=datetime.now(),
            distance=5.0,  # 5km
            duration=1800,  # 30 minutes
        )

        # Convert to run dict
        run_data = activity_to_run_dict(test_activity, test_user_id, source_id)

        # Upsert the run
        result = runs_repo.upsert_run(test_user_id, source_id, run_data)
        print(f"✅ Created run: {result['id']}")
        print(f"   Distance: {result['distance_km']} km")
        print(f"   Duration: {result['duration_seconds']} seconds")
        print(f"   Pace: {result['average_pace_min_per_km']:.2f} min/km")

        # Test queries
        print("\n📊 Testing query operations...")

        # Get runs by user
        runs = runs_repo.get_runs_by_user(test_user_id, limit=10)
        print(f"✅ Found {len(runs)} run(s) for user")

        # Get overall stats
        stats = runs_repo.get_user_overall_stats(test_user_id)
        print("✅ Overall stats:")
        print(f"   Total runs: {stats['total_runs']}")
        print(f"   Total km: {stats['total_km']}")
        print(f"   Avg km: {stats['avg_km']}")

        # Test duplicate insert (should update, not create new)
        print("\n🔄 Testing upsert (duplicate)...")
        result2 = runs_repo.upsert_run(test_user_id, source_id, run_data)
        print(f"✅ Upsert returned same ID: {result['id'] == result2['id']}")

        # Clean up test data
        print("\n🧹 Cleaning up test run...")
        runs_repo.delete_run(UUID(result["id"]))
        print("✅ Test run deleted")

        return True

    except Exception as e:
        print(f"❌ RunsRepository test failed: {e}")
        import traceback

        traceback.print_exc()
        return False


def test_data_mapper():
    """Test activity to run dict conversion."""
    print("\n🗺️  Testing Data Mapper...")

    try:
        # Create test activity with all fields
        activity = Activity(
            activity_id="mapper-test-123",
            start_date_time_local=datetime.now(),
            distance=10.5,
            duration=3600,
            cadence_average=180,
            heart_rate_average=150,
        )

        test_user_id = UUID("00000000-0000-0000-0000-000000000001")
        test_source_id = UUID("00000000-0000-0000-0000-000000000002")

        run_dict = activity_to_run_dict(activity, test_user_id, test_source_id)

        # Verify mappings
        assert run_dict["user_id"] == str(test_user_id)
        assert run_dict["source_id"] == str(test_source_id)
        assert run_dict["source_activity_id"] == "mapper-test-123"
        assert run_dict["distance_km"] == 10.5
        assert run_dict["duration_seconds"] == 3600
        assert run_dict["cadence_average"] == 180
        assert run_dict["heart_rate_average"] == 150

        print("✅ Activity → Run dict mapping correct")
        print(f"   Mapped {len(run_dict)} fields")

        return True

    except Exception as e:
        print(f"❌ Data mapper test failed: {e}")
        return False


def test_database_schema():
    """Test database schema and tables exist."""
    print("\n🗄️  Testing Database Schema...")
    supabase = get_supabase_client()

    try:
        # Test each table exists and is accessible
        tables = [
            "users",
            "user_sources",
            "runs",
            "splits",
            "recording_data",
            "laps",
            "sync_history",
        ]

        for table in tables:
            result = supabase.table(table).select("*", count="exact").limit(0).execute()
            print(f"✅ Table '{table}' exists (count: {result.count})")

        # Test views
        views = ["daily_summary", "monthly_summary"]
        for view in views:
            result = supabase.table(view).select("*", count="exact").limit(0).execute()
            print(f"✅ View '{view}' exists")

        return True

    except Exception as e:
        print(f"❌ Schema test failed: {e}")
        return False


def main():
    """Run all tests."""
    print("=" * 60)
    print("🧪 Testing Supabase Local Infrastructure")
    print("=" * 60)

    results = {
        "Connection": test_connection_status(),
        "Database Schema": test_database_schema(),
        "Users Repository": test_users_repository(),
        "Data Mapper": test_data_mapper(),
        "Runs Repository": test_runs_repository(),
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
        print("\n✅ Supabase infrastructure is working correctly")
        print("✅ Ready to proceed with Lambda updates")
        return 0
    else:
        print("⚠️  Some tests failed")
        print("\n❌ Please review errors above")
        return 1


if __name__ == "__main__":
    sys.exit(main())
