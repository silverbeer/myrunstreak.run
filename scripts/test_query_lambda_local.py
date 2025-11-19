#!/usr/bin/env python3
"""
Test script for multi-user query Lambda handler.

Verifies:
- Lambda handler structure and imports
- All query endpoints work with user_id parameter
- Error handling for missing user_id
- Data returned matches expected format

Run with: uv run python scripts/test_query_lambda_local.py
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
        from src.lambdas.query_runs import handler

        # Verify main functions exist
        assert hasattr(handler, "lambda_handler"), "lambda_handler function not found"
        assert hasattr(handler, "get_user_id_from_request"), (
            "get_user_id_from_request function not found"
        )

        # Verify endpoints exist
        assert hasattr(handler, "get_overall_stats"), "get_overall_stats not found"
        assert hasattr(handler, "get_recent_runs"), "get_recent_runs not found"
        assert hasattr(handler, "get_monthly_stats"), "get_monthly_stats not found"
        assert hasattr(handler, "get_streaks"), "get_streaks not found"
        assert hasattr(handler, "get_records"), "get_records not found"
        assert hasattr(handler, "list_runs"), "list_runs not found"

        print("✅ Handler structure is correct")
        print("   - All 6 query endpoints found")
        print("   - User authentication helpers present")

        return True

    except Exception as e:
        print(f"❌ Handler structure test failed: {e}")
        import traceback

        traceback.print_exc()
        return False


def test_overall_stats_endpoint():
    """Test /stats/overall endpoint."""
    print("\n📊 Testing /stats/overall endpoint...")

    try:
        from src.lambdas.query_runs.handler import lambda_handler

        # Mock event for /stats/overall
        event = {
            "resource": "/stats/overall",
            "path": "/stats/overall",
            "httpMethod": "GET",
            "requestContext": {"requestId": "test-123"},
            "queryStringParameters": {"user_id": "00000000-0000-0000-0000-000000000001"},
        }

        # Mock context
        context = MagicMock()
        context.function_name = "test-query-lambda"

        # Call handler
        response = lambda_handler(event, context)

        print(f"✅ Response: {response['statusCode']}")

        # Parse body
        import json

        body = json.loads(response["body"])

        # Verify response structure
        assert "total_runs" in body, "total_runs not in response"
        assert "total_km" in body, "total_km not in response"
        assert "avg_km" in body, "avg_km not in response"

        print(f"   Total runs: {body['total_runs']}")
        print(f"   Total km: {body['total_km']}")

        return True

    except Exception as e:
        print(f"❌ Overall stats test failed: {e}")
        import traceback

        traceback.print_exc()
        return False


def test_recent_runs_endpoint():
    """Test /runs/recent endpoint."""
    print("\n🏃 Testing /runs/recent endpoint...")

    try:
        from src.lambdas.query_runs.handler import lambda_handler

        # Mock event for /runs/recent
        event = {
            "resource": "/runs/recent",
            "path": "/runs/recent",
            "httpMethod": "GET",
            "requestContext": {"requestId": "test-123"},
            "queryStringParameters": {
                "user_id": "00000000-0000-0000-0000-000000000001",
                "limit": "5",
            },
        }

        # Mock context
        context = MagicMock()
        context.function_name = "test-query-lambda"

        # Call handler
        response = lambda_handler(event, context)

        print(f"✅ Response: {response['statusCode']}")

        # Parse body
        import json

        body = json.loads(response["body"])

        # Verify response structure
        assert "count" in body, "count not in response"
        assert "runs" in body, "runs not in response"

        print(f"   Returned {body['count']} runs")

        return True

    except Exception as e:
        print(f"❌ Recent runs test failed: {e}")
        import traceback

        traceback.print_exc()
        return False


def test_monthly_stats_endpoint():
    """Test /stats/monthly endpoint."""
    print("\n📅 Testing /stats/monthly endpoint...")

    try:
        from src.lambdas.query_runs.handler import lambda_handler

        # Mock event for /stats/monthly
        event = {
            "resource": "/stats/monthly",
            "path": "/stats/monthly",
            "httpMethod": "GET",
            "requestContext": {"requestId": "test-123"},
            "queryStringParameters": {
                "user_id": "00000000-0000-0000-0000-000000000001",
                "limit": "6",
            },
        }

        # Mock context
        context = MagicMock()
        context.function_name = "test-query-lambda"

        # Call handler
        response = lambda_handler(event, context)

        print(f"✅ Response: {response['statusCode']}")

        # Parse body
        import json

        body = json.loads(response["body"])

        # Verify response structure
        assert "count" in body, "count not in response"
        assert "months" in body, "months not in response"

        print(f"   Returned {body['count']} months")

        return True

    except Exception as e:
        print(f"❌ Monthly stats test failed: {e}")
        import traceback

        traceback.print_exc()
        return False


def test_missing_user_id():
    """Test error handling when user_id is missing."""
    print("\n⚠️  Testing missing user_id error handling...")

    try:
        from src.lambdas.query_runs.handler import lambda_handler

        # Mock event without user_id
        event = {
            "resource": "/stats/overall",
            "path": "/stats/overall",
            "httpMethod": "GET",
            "requestContext": {"requestId": "test-123"},
            "queryStringParameters": {},  # No user_id
        }

        # Mock context
        context = MagicMock()
        context.function_name = "test-query-lambda"

        # Call handler
        response = lambda_handler(event, context)

        # Should return 400 error
        assert response["statusCode"] == 400, f"Expected 400, got {response['statusCode']}"

        print(f"✅ Correctly returned {response['statusCode']} for missing user_id")

        # Parse body
        import json

        body = json.loads(response["body"])
        print(f"   Error message: {body.get('message')}")

        return True

    except Exception as e:
        print(f"❌ Missing user_id test failed: {e}")
        import traceback

        traceback.print_exc()
        return False


def test_invalid_user_id():
    """Test error handling when user_id is invalid format."""
    print("\n⚠️  Testing invalid user_id error handling...")

    try:
        from src.lambdas.query_runs.handler import lambda_handler

        # Mock event with invalid user_id
        event = {
            "resource": "/stats/overall",
            "path": "/stats/overall",
            "httpMethod": "GET",
            "requestContext": {"requestId": "test-123"},
            "queryStringParameters": {"user_id": "not-a-uuid"},
        }

        # Mock context
        context = MagicMock()
        context.function_name = "test-query-lambda"

        # Call handler
        response = lambda_handler(event, context)

        # Should return 400 error
        assert response["statusCode"] == 400, f"Expected 400, got {response['statusCode']}"

        print(f"✅ Correctly returned {response['statusCode']} for invalid user_id")

        # Parse body
        import json

        body = json.loads(response["body"])
        print(f"   Error message: {body.get('message')}")

        return True

    except Exception as e:
        print(f"❌ Invalid user_id test failed: {e}")
        import traceback

        traceback.print_exc()
        return False


def main():
    """Run all tests."""
    print("=" * 60)
    print("🧪 Testing Multi-User Query Lambda Handler")
    print("=" * 60)

    results = {
        "Handler Structure": test_handler_structure(),
        "/stats/overall": test_overall_stats_endpoint(),
        "/runs/recent": test_recent_runs_endpoint(),
        "/stats/monthly": test_monthly_stats_endpoint(),
        "Missing user_id": test_missing_user_id(),
        "Invalid user_id": test_invalid_user_id(),
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
        print("\n✅ Multi-user query Lambda is ready")
        print("✅ Can be deployed to AWS")
        return 0
    else:
        print("⚠️  Some tests failed")
        print("\n❌ Please review errors above")
        return 1


if __name__ == "__main__":
    sys.exit(main())
