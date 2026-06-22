"""Redis-backed session store for multi-instance NINA deployments.

Drop-in replacement for MemoryStore: implements the same get/set/delete
interface the SessionManager expects.  Connect by passing a redis.asyncio
client or a URL string; if a URL is given, the client is created lazily on
first use.

Usage:
    from nina.redis_store import RedisStore
    store = RedisStore(url=os.environ["NINA_REDIS_URL"])
    await nina.init({"llm": ..., "session": {"store": store}})
"""
from __future__ import annotations

import json
import os
from datetime import datetime, timezone
from typing import Any


def _ttl_from_state(state: dict) -> int:
    """Compute remaining TTL in seconds from state['expiresAt'] (ISO string)."""
    expires = state.get("expiresAt")
    if not expires:
        return 1800
    try:
        exp_dt = datetime.fromisoformat(expires)
        remaining = int((exp_dt - datetime.now(timezone.utc)).total_seconds())
        return max(remaining, 1)
    except (ValueError, TypeError):
        return 1800


class RedisStore:
    """Async Redis session store.

    Parameters
    ----------
    url:
        redis:// or rediss:// URL.  Ignored when *client* is provided.
    prefix:
        Key prefix for all session keys (default ``nina:sess:``).
    client:
        Pre-built redis.asyncio client.  Pass in tests to avoid a real server.
    """

    def __init__(
        self,
        url: str | None = None,
        *,
        prefix: str = "nina:sess:",
        client: Any = None,
    ) -> None:
        self._url = url or os.environ.get("NINA_REDIS_URL", "redis://localhost:6379")
        self._prefix = prefix
        self._client = client

    def _redis(self):
        if self._client is None:
            import redis.asyncio as aioredis
            self._client = aioredis.from_url(self._url, decode_responses=True)
        return self._client

    def _key(self, session_id: str) -> str:
        return f"{self._prefix}{session_id}"

    async def get(self, session_id: str) -> dict | None:
        data = await self._redis().get(self._key(session_id))
        if not data:
            return None
        try:
            return json.loads(data)
        except json.JSONDecodeError:
            return None

    async def set(self, session_id: str, state: dict) -> None:
        ttl = _ttl_from_state(state)
        await self._redis().setex(
            self._key(session_id),
            ttl,
            json.dumps(state, default=str),
        )

    async def delete(self, session_id: str) -> None:
        await self._redis().delete(self._key(session_id))
