"""Lazy Redis client for direct Redis access.

Requires the ``redis`` extra: ``pip install kctl-api[redis]``
"""

from __future__ import annotations

from typing import Any

_redis_clients: dict[str, Any] = {}


def get_redis(redis_url: str) -> Any:
    """Get or create a Redis client keyed by URL.

    Raises ImportError if redis is not installed.
    """
    if redis_url in _redis_clients:
        return _redis_clients[redis_url]

    try:
        from redis.asyncio import Redis
    except ImportError as e:
        raise ImportError("Redis support requires the 'redis' extra. Install with: pip install kctl-api[redis]") from e

    client = Redis.from_url(redis_url, decode_responses=True)
    _redis_clients[redis_url] = client
    return client


async def close_redis() -> None:
    """Close all cached Redis clients."""
    for client in _redis_clients.values():
        await client.aclose()
    _redis_clients.clear()
