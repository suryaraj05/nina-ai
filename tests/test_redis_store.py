"""Tests for RedisStore using an in-process async fake client."""
import asyncio
import json

import pytest

from nina.redis_store import RedisStore, _ttl_from_state


# ---------------------------------------------------------------------------
# Minimal async fake-redis client
# ---------------------------------------------------------------------------

class _FakeRedis:
    """Minimal async Redis stub: supports get, setex, delete."""

    def __init__(self):
        self._store: dict[str, tuple[str, int | None]] = {}  # key -> (value, ttl_s)

    async def get(self, key: str) -> str | None:
        entry = self._store.get(key)
        return entry[0] if entry else None

    async def setex(self, key: str, ttl: int, value: str) -> None:
        self._store[key] = (value, ttl)

    async def delete(self, key: str) -> None:
        self._store.pop(key, None)


def run(coro):
    return asyncio.run(coro)


@pytest.fixture()
def store():
    return RedisStore(client=_FakeRedis())


def test_get_missing_returns_none(store):
    assert run(store.get("sess-missing")) is None


def test_set_and_get_roundtrip(store):
    state = {"sessionId": "s1", "turnCount": 3, "expiresAt": None}
    run(store.set("s1", state))
    result = run(store.get("s1"))
    assert result["turnCount"] == 3
    assert result["sessionId"] == "s1"


def test_delete_removes_session(store):
    state = {"sessionId": "s2", "expiresAt": None}
    run(store.set("s2", state))
    run(store.delete("s2"))
    assert run(store.get("s2")) is None


def test_set_uses_ttl_from_state(store):
    from datetime import datetime, timedelta, timezone
    expires = (datetime.now(timezone.utc) + timedelta(seconds=300)).isoformat()
    state = {"sessionId": "s3", "expiresAt": expires}
    run(store.set("s3", state))
    raw = store._client._store.get(store._key("s3"))
    assert raw is not None
    _, ttl = raw
    assert 250 <= ttl <= 300


def test_set_defaults_ttl_when_no_expiry(store):
    state = {"sessionId": "s4", "expiresAt": None}
    run(store.set("s4", state))
    raw = store._client._store.get(store._key("s4"))
    _, ttl = raw
    assert ttl == 1800


def test_get_corrupted_value_returns_none(store):
    store._client._store[store._key("bad")] = ("not-json}", None)
    assert run(store.get("bad")) is None


def test_prefix_applied_to_keys(store):
    store._prefix = "test:"
    run(store.set("px", {"sessionId": "px", "expiresAt": None}))
    assert "test:px" in store._client._store


def test_ttl_from_state_fallback():
    assert _ttl_from_state({}) == 1800
    assert _ttl_from_state({"expiresAt": "bad-date"}) == 1800
