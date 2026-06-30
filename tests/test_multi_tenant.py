"""Multi-tenant /v1/query and site contract/llm-config endpoints."""
import pytest
from fastapi.testclient import TestClient

from nina.console_app import POOL, STORE, create_app


def _reset():
    STORE.orgs.clear()
    STORE.sites.clear()
    STORE.api_keys.clear()
    STORE.cli_tokens.clear()
    STORE.conversation_logs.clear()
    POOL._instances.clear()
    POOL._locks.clear()


def _stub_adapter(prompt):
    return {"resolution": "chitchat", "user_reply": "Hello!", "confidence": 0.9}


# Callable adapters can't go over HTTP (not JSON-serializable) and can't be
# persisted to the JSON store.  Tests that need them inject directly into the
# site dict, bypassing save().
_STUB_LLM = {"provider": "custom", "adapter": _stub_adapter}

# A serializable llmConfig for testing the HTTP PUT endpoint itself.
_SERIALIZABLE_LLM = {"provider": "openai", "model": "gpt-4o-mini", "apiKey": "sk-test-placeholder"}


def _inject_llm(site_id: str) -> None:
    """Inject callable adapter directly into site record without triggering save()."""
    STORE.sites[site_id]["llmConfig"] = _STUB_LLM

_MINIMAL_CONTRACT = {
    "site": {"id": "acme", "name": "Acme", "baseUrl": "https://shop.acme.test"},
    "actions": [],
    "risk": {},
}


@pytest.fixture()
def client_and_site():
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
    key_rec = client.post(
        "/v1/keys/issue", json={"siteId": site["id"], "environment": "test", "kind": "pk"}
    ).json()["data"]
    return client, site["id"], key_rec["token"]


# ---------------------------------------------------------------------------
# HTTP endpoint tests (serializable payloads only)
# ---------------------------------------------------------------------------

def test_attach_contract_via_http(client_and_site):
    client, site_id, _ = client_and_site

    res = client.put(f"/v1/sites/{site_id}/contract", json={"contract": _MINIMAL_CONTRACT})
    assert res.status_code == 200
    assert res.json()["data"]["contractAttached"] is True
    assert STORE.sites[site_id]["agentContract"] == _MINIMAL_CONTRACT


def test_attach_llm_config_via_http(client_and_site):
    client, site_id, _ = client_and_site

    res = client.put(f"/v1/sites/{site_id}/llm-config", json={"llmConfig": _SERIALIZABLE_LLM})
    assert res.status_code == 200
    assert res.json()["data"]["llmConfigAttached"] is True
    assert STORE.sites[site_id]["llmConfig"] == _SERIALIZABLE_LLM


def test_attach_contract_unknown_site(client_and_site):
    client, _, _ = client_and_site
    res = client.put("/v1/sites/nonexistent/contract", json={"contract": {}})
    assert res.status_code == 404


def test_query_missing_contract_returns_400(client_and_site):
    client, site_id, raw_key = client_and_site
    # llmConfig attached (directly into store — callable adapter) but no contract
    _inject_llm(site_id)

    res = client.post(
        "/v1/query",
        json={"message": "hello", "sessionId": "s1"},
        headers={"X-NINA-API-Key": raw_key, "Origin": "https://shop.acme.test"},
    )
    assert res.status_code == 400
    assert res.json()["error"]["code"] == "NO_CONTRACT"


def test_query_missing_llm_config_returns_400(client_and_site):
    client, site_id, raw_key = client_and_site
    STORE.attach_contract(site_id, _MINIMAL_CONTRACT)
    # no llmConfig

    res = client.post(
        "/v1/query",
        json={"message": "hello", "sessionId": "s1"},
        headers={"X-NINA-API-Key": raw_key, "Origin": "https://shop.acme.test"},
    )
    assert res.status_code == 400
    assert res.json()["error"]["code"] == "NO_LLM_CONFIG"


def test_query_bad_api_key_returns_401(client_and_site):
    client, site_id, _ = client_and_site
    STORE.attach_contract(site_id, _MINIMAL_CONTRACT)
    _inject_llm(site_id)

    res = client.post(
        "/v1/query",
        json={"message": "hello", "sessionId": "s1"},
        headers={"X-NINA-API-Key": "pk_test_bad", "Origin": "https://shop.acme.test"},
    )
    assert res.status_code == 401


# ---------------------------------------------------------------------------
# Pool + full-flow tests (callable adapter injected directly into store)
# ---------------------------------------------------------------------------

def test_multi_tenant_query_full_flow(client_and_site):
    """Key → site → pool init → chat turn — end-to-end happy path."""
    client, site_id, raw_key = client_and_site
    STORE.attach_contract(site_id, _MINIMAL_CONTRACT)
    _inject_llm(site_id)

    res = client.post(
        "/v1/query",
        json={"message": "hi there", "sessionId": "ses-001"},
        headers={"X-NINA-API-Key": raw_key, "Origin": "https://shop.acme.test"},
    )
    assert res.status_code == 200
    body = res.json()
    assert body["ok"] is True
    assert body["data"]["naturalLanguageResponse"]
    assert site_id in POOL._instances


def test_pool_evicted_on_llm_config_change(client_and_site):
    """Updating llmConfig via HTTP should evict the cached pool entry."""
    client, site_id, raw_key = client_and_site
    STORE.attach_contract(site_id, _MINIMAL_CONTRACT)
    _inject_llm(site_id)

    # Warm the pool
    client.post(
        "/v1/query",
        json={"message": "hi", "sessionId": "ses-warm"},
        headers={"X-NINA-API-Key": raw_key, "Origin": "https://shop.acme.test"},
    )
    assert site_id in POOL._instances

    # Update llmConfig via HTTP → pool evicted
    client.put(f"/v1/sites/{site_id}/llm-config", json={"llmConfig": _SERIALIZABLE_LLM})
    assert site_id not in POOL._instances


_API_CONTRACT = {
    "site": {"id": "acme", "name": "Acme", "baseUrl": "https://shop.acme.test"},
    "apis": {"default": {"baseUrl": "https://shop.acme.test"}},
    "actions": [
        {
            "id": "search_products",
            "description": "Search the product catalog by keyword",
            "parameters": {"query": {"type": "string", "required": True}},
            "risk": "low",
            "requiresAuth": False,
            "execute": {
                "type": "api",
                "runtime": "server",
                "apiRef": {"method": "GET", "path": "/search", "bodyTemplate": {"query": "{query}"}},
            },
        }
    ],
    "risk": {},
}


def test_pool_registers_contract_actions(client_and_site):
    """A query against a site with an API contract must make the contract's
    actions visible to the engine — the pool builds a bare Nina(), so without
    explicit registration the engine would see zero actions (chitchat only)."""
    client, site_id, raw_key = client_and_site
    STORE.attach_contract(site_id, _API_CONTRACT)
    _inject_llm(site_id)

    res = client.post(
        "/v1/query",
        json={"message": "hi", "sessionId": "ses-reg"},
        headers={"X-NINA-API-Key": raw_key, "Origin": "https://shop.acme.test"},
    )
    assert res.json()["ok"] is True
    nina = POOL._instances[site_id]
    registered = {a["name"] for a in nina._core.registry.all()}
    assert "search_products" in registered


def test_generate_from_url_builds_browser_contract(client_and_site):
    """The dashboard 'paste your API URL' flow: fetch a live OpenAPI doc and
    attach a generated, browser-runtime contract the engine can execute."""
    import json
    import threading
    from http.server import BaseHTTPRequestHandler, HTTPServer

    client, site_id, _ = client_and_site

    spec = {
        "openapi": "3.0.0",
        "info": {"title": "Demo Shop"},
        "paths": {
            "/search": {
                "get": {
                    "operationId": "search_products",
                    "summary": "Search the product catalog by keyword",
                    "parameters": [
                        {"name": "q", "in": "query", "required": True, "schema": {"type": "string"}}
                    ],
                }
            }
        },
    }

    class Handler(BaseHTTPRequestHandler):
        def log_message(self, *a):
            pass

        def do_GET(self):
            self.send_response(200)
            self.send_header("Content-Type", "application/json")
            self.end_headers()
            self.wfile.write(json.dumps(spec).encode())

    srv = HTTPServer(("127.0.0.1", 0), Handler)
    port = srv.server_address[1]
    threading.Thread(target=srv.serve_forever, daemon=True).start()
    try:
        # Need a dashboard token for the /v1/auth/* route — make a fresh org/site.
        org = client.post("/v1/orgs", json={"name": "Gen"}).json()["data"]
        site = client.post("/v1/sites", json={
            "orgId": org["id"], "name": "Gen Store",
            "baseUrl": "https://gen.test", "allowedOrigins": ["https://gen.test"],
        }).json()["data"]
        headers = {"Authorization": "Bearer " + org["dashboardToken"]}

        res = client.post(
            f"/v1/auth/sites/{site['id']}/generate-from-url",
            json={"apiBaseUrl": f"http://127.0.0.1:{port}/openapi.json", "runtime": "browser"},
            headers=headers,
        )
    finally:
        srv.shutdown()

    body = res.json()
    assert body["ok"] is True, body
    assert body["data"]["actionsFound"] == 1
    assert body["data"]["runtime"] == "browser"

    contract = STORE.sites[site["id"]]["agentContract"]
    action = contract["actions"][0]
    assert action["id"] == "search_products"
    assert action["execute"]["runtime"] == "browser"
    assert action["execute"]["apiRef"]["path"] == "/search"


def test_generate_from_url_rejects_bad_runtime(client_and_site):
    client, _, _ = client_and_site
    org = client.post("/v1/orgs", json={"name": "Gen2"}).json()["data"]
    site = client.post("/v1/sites", json={
        "orgId": org["id"], "name": "Gen2 Store",
        "baseUrl": "https://gen2.test", "allowedOrigins": ["https://gen2.test"],
    }).json()["data"]
    res = client.post(
        f"/v1/auth/sites/{site['id']}/generate-from-url",
        json={"apiBaseUrl": "http://x.test/openapi.json", "runtime": "cloud"},
        headers={"Authorization": "Bearer " + org["dashboardToken"]},
    )
    assert res.status_code == 400


def test_same_site_multiple_sessions_isolated(client_and_site):
    """Two sessionIds on the same site should produce independent turn responses."""
    client, site_id, raw_key = client_and_site
    STORE.attach_contract(site_id, _MINIMAL_CONTRACT)
    _inject_llm(site_id)

    headers = {"X-NINA-API-Key": raw_key, "Origin": "https://shop.acme.test"}
    r1 = client.post("/v1/query", json={"message": "hello", "sessionId": "sess-A"}, headers=headers)
    r2 = client.post("/v1/query", json={"message": "hello", "sessionId": "sess-B"}, headers=headers)

    assert r1.json()["ok"]
    assert r2.json()["ok"]
    nina = POOL._instances[site_id]
    assert nina._core.sessions is not None
