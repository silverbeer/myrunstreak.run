"""Redis cache wrapper with a small ``@cached`` decorator.

Designed for read endpoints that aggregate large query results. Keys are
namespaced by user_id so a sync invalidation can clear one user without
nuking the whole cache.

When ``CACHE_ENABLED=false`` or Redis is unreachable, decorated functions
fall through to the wrapped function — no behavior change.
"""

from __future__ import annotations

import functools
import json
import logging
from collections.abc import Awaitable, Callable
from typing import Any, TypeVar
from uuid import UUID

import redis.asyncio as redis_asyncio

from backend.config import get_settings

logger = logging.getLogger(__name__)

T = TypeVar("T")

_redis_client: redis_asyncio.Redis | None = None


async def get_redis() -> redis_asyncio.Redis | None:
    """Lazy-initialise a single async Redis client."""
    global _redis_client
    settings = get_settings()
    if not settings.cache_enabled:
        return None
    if _redis_client is None:
        try:
            _redis_client = redis_asyncio.from_url(
                settings.redis_url,
                decode_responses=True,
                socket_connect_timeout=2,
                socket_timeout=2,
            )
            await _redis_client.ping()
        except Exception as exc:
            logger.warning(f"Redis unavailable, caching disabled: {exc}")
            _redis_client = None
    return _redis_client


def user_key(user_id: UUID, prefix: str, *parts: str) -> str:
    """Build a namespaced cache key — `mrs:<prefix>:<user_id>:<parts>`."""
    suffix = ":".join(parts)
    base = f"mrs:{prefix}:{user_id}"
    return f"{base}:{suffix}" if suffix else base


def cached(ttl: int | None = None, key_prefix: str = ""):
    """Decorator: cache the result of an async function in Redis.

    The wrapped function MUST take ``user_id: UUID`` as its first positional
    argument so the key is correctly user-scoped.
    """

    def decorator(
        fn: Callable[..., Awaitable[T]],
    ) -> Callable[..., Awaitable[T]]:
        @functools.wraps(fn)
        async def wrapper(user_id: UUID, *args: Any, **kwargs: Any) -> T:
            settings = get_settings()
            client = await get_redis()
            if client is None:
                return await fn(user_id, *args, **kwargs)

            extra_parts = [str(a) for a in args] + [
                f"{k}={v}" for k, v in sorted(kwargs.items())
            ]
            key = user_key(user_id, key_prefix or fn.__name__, *extra_parts)

            try:
                cached_value = await client.get(key)
                if cached_value is not None:
                    return json.loads(cached_value)  # type: ignore[no-any-return]
            except Exception as exc:
                logger.warning(f"cache get failed for {key}: {exc}")

            value = await fn(user_id, *args, **kwargs)
            try:
                await client.set(
                    key,
                    json.dumps(value, default=str),
                    ex=ttl or settings.cache_default_ttl_seconds,
                )
            except Exception as exc:
                logger.warning(f"cache set failed for {key}: {exc}")
            return value

        return wrapper

    return decorator


async def invalidate_user(user_id: UUID) -> int:
    """Delete every cached entry under ``mrs:*:<user_id>*``. Returns count."""
    client = await get_redis()
    if client is None:
        return 0
    pattern = f"mrs:*:{user_id}*"
    deleted = 0
    try:
        async for key in client.scan_iter(match=pattern):
            await client.delete(key)
            deleted += 1
    except Exception as exc:
        logger.warning(f"cache invalidation failed for {user_id}: {exc}")
    return deleted
