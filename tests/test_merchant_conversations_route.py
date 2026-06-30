"""GET /v1/auth/sites/{id}/conversations"""

from __future__ import annotations

import pytest
from fastapi.testclient import TestClient

from nina.console_app import POOL, STORE, create_app
from nina.conversation_log import entry_from_turn


def _reset():
    STORE.orgs.clear()
    STORE.sites.clear()
    STORE.api_keys.clear()
    STORE.cli_tokens.clear()
    STORE.conversation_logs.clear()
    POOL._instances.clear()
    POOL._locks.clear()


@pytest.fixture()
def merchant_client():
    _reset()
    client = TestClient(create_app())
    org = client.post("/v1/orgs", json={"name": "Log Org"}).json()["data"]
    site = client.post(
        "/v1/sites",
        json={"orgId": org["id"], "name": "Store", "baseUrl": "https://shop.test"},
    ).json()["data"]
    token = org["dashboardToken"]
    return client, site["id"], token


def test_merchant_conversations_route(merchant_client):
    client, site_id, token = merchant_client
    headers = {"Authorization": f"Bearer {token}"}

    turn = {
        "turnId": "turn_route_1",
        "actionCalled": "search_products",
        "naturalLanguageResponse": "I found 2 items.",
        "actionResult": {"grounded": True, "count": 2},
        "products": [{"title": "A"}, {"title": "B"}],
    }
    STORE.append_conversation_log(
        site_id,
        entry_from_turn(site_id, "sid_route", "hoodies under 2000", turn),
    )

    res = client.get(f"/v1/auth/sites/{site_id}/conversations", headers=headers)
    assert res.status_code == 200
    body = res.json()
    assert body["ok"] is True
    logs = body["data"]["logs"]
    assert body["data"]["retentionDays"] == 7
    assert len(logs) >= 1
    assert logs[0]["userMessage"] == "hoodies under 2000"
    assert logs[0]["productCount"] == 2
