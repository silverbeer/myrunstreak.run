#!/bin/bash
# Complete local test suite for MyRunStreak.com
#
# Runs all local tests in sequence:
# 1. Supabase infrastructure
# 2. Sync Lambda
# 3. Query Lambda
# 4. OAuth migration
#
# Usage:
#   ./scripts/test_all_local.sh

set -e  # Exit on first error

echo "======================================"
echo "🧪 MyRunStreak.com Local Test Suite"
echo "======================================"
echo ""

# Check prerequisites
echo "🔍 Checking prerequisites..."

# Check if Supabase is running
if ! supabase status > /dev/null 2>&1; then
    echo "❌ Supabase is not running"
    echo "   Start it with: supabase start"
    exit 1
fi
echo "✅ Supabase is running"

# Check if uv is available
if ! command -v uv &> /dev/null; then
    echo "❌ uv is not installed"
    echo "   Install it from: https://github.com/astral-sh/uv"
    exit 1
fi
echo "✅ uv is available"

echo ""

# Run tests
echo "======================================"
echo "Running Tests"
echo "======================================"

# 1. Database tests
echo ""
echo "📊 Test 1/4: Supabase Infrastructure"
echo "--------------------------------------"
uv run python scripts/test_supabase_local.py || {
    echo "❌ Supabase tests failed"
    exit 1
}

# 2. Sync Lambda tests
echo ""
echo "🔄 Test 2/4: Sync Lambda"
echo "--------------------------------------"
uv run python scripts/test_sync_lambda_local.py || {
    echo "❌ Sync Lambda tests failed"
    exit 1
}

# 3. Query Lambda tests
echo ""
echo "🔍 Test 3/4: Query Lambda"
echo "--------------------------------------"
uv run python scripts/test_query_lambda_local.py || {
    echo "❌ Query Lambda tests failed"
    exit 1
}

# 4. OAuth Migration tests
echo ""
echo "🔐 Test 4/4: OAuth Migration"
echo "--------------------------------------"
uv run python scripts/test_oauth_migration_local.py || {
    echo "❌ OAuth migration tests failed"
    exit 1
}

echo ""
echo "======================================"
echo "✅ All Local Tests Passed!"
echo "======================================"
echo ""
echo "📝 Test Summary:"
echo "   ✓ Supabase Infrastructure"
echo "   ✓ Sync Lambda (Multi-User)"
echo "   ✓ Query Lambda (Multi-User)"
echo "   ✓ OAuth Token Migration"
echo ""
echo "🚀 Ready for deployment!"
echo "======================================"
