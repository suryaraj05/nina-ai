"""Conversation log retention and merchant API."""

from __future__ import annotations

from nina.console_store import ConsoleStore
from nina.conversation_log import RETENTION_SECONDS, entry_from_turn, prune_entries
from nina.store_util import now_ts as _now_ts


def test_entry_from_turn_grounded_search():
    turn = {
        "turnId": "turn_1",
        "intent": "search_products",
        "actionCalled": "search_products",
        "naturalLanguageResponse": "I found 1 item in the catalog.",
        "actionResult": {"grounded": True, "count": 1, "query": "hoodies"},
        "products": [{"title": "Hoodie", "price": 1299}],
    }
    row = entry_from_turn("site_1", "sid_abc", "show me hoodies", turn)
    assert row["siteId"] == "site_1"
    assert row["sessionId"] == "sid_abc"
    assert row["grounded"] is True
    assert row["productCount"] == 1
    assert "hoodies" in row["userMessage"]


def test_entry_redacts_email():
    turn = {
        "turnId": "t2",
        "naturalLanguageResponse": "ok",
        "actionResult": {},
    }
    row = entry_from_turn("s", "sid", "reach me at shopper@example.com", turn)
    assert "[redacted]" in row["userMessage"]
    assert "shopper@example.com" not in row["userMessage"]


def test_console_store_append_and_list():
    store = ConsoleStore()
    site_id = "site_log"
    store.sites[site_id] = {"id": site_id, "orgId": "org_1", "name": "T", "baseUrl": "https://x.com"}

    turn = {
        "turnId": "turn_x",
        "actionCalled": "search_products",
        "naturalLanguageResponse": "No matches.",
        "actionResult": {"grounded": True, "count": 0},
    }
    store.append_conversation_log(site_id, entry_from_turn(site_id, "sid_1", "pink elephant", turn))
    logs = store.list_conversation_logs(site_id)
    assert len(logs) == 1
    assert logs[0]["userMessage"] == "pink elephant"
    assert logs[0]["productCount"] == 0


def test_prune_drops_old_entries():
    store = ConsoleStore()
    site_id = "site_old"
    now = _now_ts()
    old = now - RETENTION_SECONDS - 3600
    store.conversation_logs[site_id] = [
        {"createdAt": old, "userMessage": "old"},
        {"createdAt": now, "userMessage": "fresh"},
    ]
    store.conversation_logs[site_id] = prune_entries(store.conversation_logs[site_id], now=now)
    assert len(store.conversation_logs[site_id]) == 1
    assert store.conversation_logs[site_id][0]["userMessage"] == "fresh"


def test_list_filters_by_session():
    store = ConsoleStore()
    site_id = "site_sess"
    ts = _now_ts()
    store.conversation_logs[site_id] = [
        {"sessionId": "a", "createdAt": ts, "userMessage": "one"},
        {"sessionId": "b", "createdAt": ts, "userMessage": "two"},
    ]
    logs = store.list_conversation_logs(site_id, session_id="b")
    assert len(logs) == 1
    assert logs[0]["userMessage"] == "two"
