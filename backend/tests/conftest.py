"""Shared test fixtures.

Sets the env vars Settings() requires before any backend module is imported.
"""

import os

os.environ.setdefault("SUPABASE_URL", "https://test.supabase.co")
os.environ.setdefault("SUPABASE_SERVICE_ROLE_KEY", "test-service-key")
os.environ.setdefault(
    "SUPABASE_JWT_SECRET", "test-jwt-secret-needs-to-be-long-enough-for-hs256"
)
os.environ.setdefault("CACHE_ENABLED", "false")
