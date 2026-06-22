"""Generator api.manifest.yaml integration tests."""

from pathlib import Path

from nina.generator.stages.api_manifest import load_api_manifest, merge_api_manifest_into_contract

MANIFEST = Path(__file__).resolve().parents[1] / "contracts" / "examples" / "api.manifest.yaml"


def test_load_api_manifest():
    data = load_api_manifest(MANIFEST)
    assert "search" in (data.get("actions") or {})


def test_merge_prefers_manifest_actions():
    contract = {
        "site": {"id": "ex", "name": "Ex", "baseUrl": "https://example.com"},
        "version": "1.0.0",
        "pages": [{"id": "home", "urlPattern": "/*"}],
        "embed": {"panel": "right"},
        "actions": [
            {
                "id": "search",
                "description": "Old DOM search",
                "parameters": {},
                "execute": {"type": "dom", "steps": [{"op": "click", "selector": "#x"}]},
            }
        ],
    }
    manifest = load_api_manifest(MANIFEST)
    merged = merge_api_manifest_into_contract(contract, manifest)
    search = next(a for a in merged["actions"] if a["id"] == "search")
    assert search["execute"]["type"] == "api"
    assert search["execute"]["runtime"] == "server"
    assert merged.get("apis")


def test_merge_enforces_high_risk_actions_from_manifest_without_separate_policy():
    """A risk:"high" action coming from api.manifest.yaml (e.g. drafted by
    nina-probe-openapi, which flags POST/PUT/PATCH/DELETE as high-risk) must
    end up enforced via contract.risk.confirmActions, the same as actions
    inferred from DOM crawling -- not just carry a descriptive label that
    nothing actually checks at runtime."""
    contract = {
        "site": {"id": "ex", "name": "Ex", "baseUrl": "https://example.com"},
        "version": "1.0.0",
        "pages": [{"id": "home", "urlPattern": "/*"}],
        "embed": {"panel": "right"},
        "actions": [],
    }
    manifest = {
        "apis": {"default": {"baseUrl": "https://example.com"}},
        "actions": {
            "place_order": {
                "method": "POST",
                "path": "/api/v1/orders",
                "risk": "high",
                "parameters": {},
            }
        },
    }
    merged = merge_api_manifest_into_contract(contract, manifest)
    assert "place_order" in merged["risk"]["confirmActions"]
