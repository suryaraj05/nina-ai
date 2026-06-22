"""NINA Console onboarding API tests."""

from pathlib import Path

from fastapi.testclient import TestClient

from nina.console_app import STORE, create_app


def _reset_store():
    STORE.orgs.clear()
    STORE.sites.clear()
    STORE.api_keys.clear()
    STORE.cli_tokens.clear()
    STORE.webhook_events.clear()


def test_console_org_site_key_flow(tmp_path):
    _reset_store()
    app = create_app()
    client = TestClient(app)

    org_res = client.post("/v1/orgs", json={"name": "Acme", "ownerEmail": "owner@acme.test"})
    assert org_res.status_code == 200
    org_id = org_res.json()["data"]["id"]

    site_res = client.post(
        "/v1/sites",
        json={
            "orgId": org_id,
            "name": "Acme Store",
            "baseUrl": "https://shop.acme.test",
            "locales": ["en-IN"],
            "markets": ["IN"],
            "allowedOrigins": ["https://shop.acme.test"],
        },
    )
    assert site_res.status_code == 200
    site_id = site_res.json()["data"]["id"]

    key_res = client.post("/v1/keys/issue", json={"siteId": site_id, "environment": "test", "kind": "pk"})
    assert key_res.status_code == 200
    raw_key = key_res.json()["data"]["token"]

    verify = client.post(
        "/v1/keys/verify",
        json={"apiKey": raw_key, "siteId": site_id, "origin": "https://shop.acme.test"},
    )
    assert verify.status_code == 200
    assert verify.json()["ok"] is True

    export_path = tmp_path / "nina.site.yaml"
    export = client.post(
        "/v1/registrar/export-nina-site",
        json={"siteId": site_id, "outputPath": str(export_path)},
    )
    assert export.status_code == 200
    assert export_path.exists()
    assert "allowedOrigins" in export_path.read_text(encoding="utf-8")


def test_console_wizard_and_seo_endpoints():
    _reset_store()
    app = create_app()
    client = TestClient(app)

    steps = client.get("/v1/wizard/steps")
    assert steps.status_code == 200
    assert len(steps.json()["data"]) == 10

    init = client.post(
        "/v1/wizard/init",
        json={
            "orgName": "Beta",
            "siteName": "Beta Shop",
            "baseUrl": "https://beta.shop.test",
            "country": "US",
            "languages": ["en"],
        },
    )
    assert init.status_code == 200
    site_id = init.json()["data"]["site"]["id"]

    seo = client.post(
        "/v1/seo/sitemap",
        json={
            "siteId": site_id,
            "rawSitemapXml": "<urlset><url><loc>https://beta.shop.test/</loc></url></urlset>",
        },
    )
    assert seo.status_code == 200
    assert seo.json()["data"]["urlCount"] == 1


def test_console_ui_homepage_served():
    _reset_store()
    app = create_app()
    client = TestClient(app)
    res = client.get("/")
    assert res.status_code == 200
    assert "NINA" in res.text

