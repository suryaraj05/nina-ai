"""Tests for per-site usage metering on the multi-tenant /v1/query endpoint."""
from fastapi.testclient import TestClient

from nina.console_app import POOL, STORE, create_app


def _reset():
    STORE.orgs.clear()
    STORE.sites.clear()
    STORE.api_keys.clear()
    STORE.usage.clear()
    POOL._instances.clear()
    POOL._locks.clear()


def _stub(prompt):
    return {"resolution": "chitchat", "user_reply": "Hi!", "confidence": 0.9}


_MINIMAL_CONTRACT = {
    "site": {"id": "acme", "name": "Acme"},
    "actions": [],
    "risk": {},
}


def _setup():
    _reset()
    app = create_app()
    client = TestClient(app)
    org = client.post("/v1/orgs", json={"name": "Acme"}).json()["data"]
    site = client.post(
        "/v1/sites",
        json={
            "orgId": org["id"],
            "name": "Acme Store",
            "baseUrl": "https://shop.acme.test",
            "allowedOrigins": ["https://shop.acme.test"],
        },
    ).json()["data"]
    key = client.post("/v1/keys/issue", json={"siteId": site["id"], "environment": "test", "kind": "pk"}).json()["data"]["token"]
    STORE.attach_contract(site["id"], _MINIMAL_CONTRACT)
    STORE.sites[site["id"]]["llmConfig"] = {"provider": "custom", "adapter": _stub}
    return client, site["id"], key


def test_usage_starts_at_zero():
    client, site_id, _ = _setup()
    res = client.get(f"/v1/sites/{site_id}/usage")
    assert res.status_code == 200
    data = res.json()["data"]
    assert data["calls"] == 0
    assert data["lastCallAt"] is None


def test_usage_increments_on_query():
    client, site_id, key = _setup()
    headers = {"X-NINA-API-Key": key, "Origin": "https://shop.acme.test"}

    client.post("/v1/query", json={"message": "hi", "sessionId": "s1"}, headers=headers)
    res = client.get(f"/v1/sites/{site_id}/usage")
    assert res.json()["data"]["calls"] == 1

    client.post("/v1/query", json={"message": "again", "sessionId": "s2"}, headers=headers)
    res = client.get(f"/v1/sites/{site_id}/usage")
    assert res.json()["data"]["calls"] == 2


def test_usage_records_last_call_timestamp():
    client, site_id, key = _setup()
    headers = {"X-NINA-API-Key": key, "Origin": "https://shop.acme.test"}
    client.post("/v1/query", json={"message": "hi", "sessionId": "s1"}, headers=headers)

    data = client.get(f"/v1/sites/{site_id}/usage").json()["data"]
    assert data["lastCallAt"] is not None
    assert isinstance(data["lastCallAt"], int)


def test_usage_not_incremented_on_auth_failure():
    client, site_id, _ = _setup()
    client.post(
        "/v1/query",
        json={"message": "hi", "sessionId": "s1"},
        headers={"X-NINA-API-Key": "pk_test_bad", "Origin": "https://shop.acme.test"},
    )
    assert STORE.get_usage(site_id)["calls"] == 0


def test_usage_endpoint_unknown_site():
    client, _, _ = _setup()
    res = client.get("/v1/sites/nonexistent/usage")
    assert res.status_code == 404


def test_direct_record_and_get_usage():
    _reset()
    STORE.create_org("Acme", None)
    STORE.sites["s"] = {"id": "s", "orgId": "org_1"}
    STORE.record_usage("s")
    STORE.record_usage("s")
    data = STORE.get_usage("s")
    assert data["calls"] == 2
    assert data["lastCallAt"] is not None
