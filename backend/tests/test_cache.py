"""Tests for the Redis cache wrapper."""

from __future__ import annotations

import importlib
from uuid import UUID

import fakeredis.aioredis
import pytest

USER_A = UUID("11111111-1111-1111-1111-111111111111")
USER_B = UUID("22222222-2222-2222-2222-222222222222")


@pytest.fixture
def cache_module(monkeypatch):
    """Reload cache module with CACHE_ENABLED=true and a fakeredis client."""
    monkeypatch.setenv("CACHE_ENABLED", "true")

    # Clear cached settings + redis client
    import backend.config

    importlib.reload(backend.config)
    import backend.cache

    importlib.reload(backend.cache)

    fake = fakeredis.aioredis.FakeRedis(decode_responses=True)

    async def _get() -> fakeredis.aioredis.FakeRedis:
        return fake

    monkeypatch.setattr(backend.cache, "get_redis", _get)
    return backend.cache


class TestUserKey:
    def test_basic(self) -> None:
        from backend.cache import user_key

        assert user_key(USER_A, "stats") == f"mrs:stats:{USER_A}"

    def test_with_parts(self) -> None:
        from backend.cache import user_key

        assert (
            user_key(USER_A, "runs", "limit=10", "offset=0")
            == f"mrs:runs:{USER_A}:limit=10:offset=0"
        )


@pytest.mark.asyncio
class TestCachedDecorator:
    async def test_returns_value_when_disabled(self, monkeypatch) -> None:
        monkeypatch.setenv("CACHE_ENABLED", "false")
        import backend.config

        importlib.reload(backend.config)
        import backend.cache

        importlib.reload(backend.cache)

        calls = 0

        @backend.cache.cached(key_prefix="t")
        async def fn(user_id: UUID) -> dict[str, int]:
            nonlocal calls
            calls += 1
            return {"hits": calls}

        assert (await fn(USER_A)) == {"hits": 1}
        assert (await fn(USER_A)) == {"hits": 2}  # not cached

    async def test_caches_repeated_calls(self, cache_module) -> None:
        calls = 0

        @cache_module.cached(ttl=60, key_prefix="overall")
        async def fn(user_id: UUID) -> dict[str, int]:
            nonlocal calls
            calls += 1
            return {"hits": calls}

        first = await fn(USER_A)
        second = await fn(USER_A)
        assert first == second
        assert calls == 1

    async def test_separate_keys_per_user(self, cache_module) -> None:
        calls = 0

        @cache_module.cached(key_prefix="overall")
        async def fn(user_id: UUID) -> dict[str, str]:
            nonlocal calls
            calls += 1
            return {"who": str(user_id)}

        await fn(USER_A)
        await fn(USER_B)
        assert calls == 2  # one call per distinct user
        await fn(USER_A)
        assert calls == 2  # still 2 — A served from cache

    async def test_separate_keys_per_args(self, cache_module) -> None:
        calls = 0

        @cache_module.cached(key_prefix="recent")
        async def fn(user_id: UUID, limit: int) -> dict[str, int]:
            nonlocal calls
            calls += 1
            return {"limit": limit}

        await fn(USER_A, 7)
        await fn(USER_A, 10)
        assert calls == 2

    async def test_invalidate_user_clears_keys(self, cache_module) -> None:
        @cache_module.cached(key_prefix="stats:overall")
        async def fn(user_id: UUID) -> dict[str, int]:
            return {"x": 1}

        await fn(USER_A)
        await fn(USER_B)

        cleared = await cache_module.invalidate_user(USER_A)
        assert cleared >= 1

        # A re-cached, B untouched
        client = await cache_module.get_redis()
        a_keys = [k async for k in client.scan_iter(match=f"mrs:*:{USER_A}*")]
        b_keys = [k async for k in client.scan_iter(match=f"mrs:*:{USER_B}*")]
        assert len(a_keys) == 0
        assert len(b_keys) >= 1
