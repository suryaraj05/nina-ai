"""Tests for drafting api.manifest.yaml from a live OpenAPI/Swagger spec."""
from __future__ import annotations

from nina.openapi_probe import (
    build_contract_from_openapi,
    build_manifest_from_openapi,
    resolve_base_url,
    spec_to_actions,
    spec_url_for,
)

# Trimmed shape of a typical NestJS Swagger document (the kind served at
# /api/docs-json), covering a query-param GET, a path-param GET, and a
# $ref-bodied POST — the three shapes that caused manual-guess bugs.
NESTJS_STYLE_SPEC = {
    "info": {"title": "Shop API"},
    "servers": [{"url": "http://localhost:3011"}],
    "paths": {
        "/api/v1/search": {
            "get": {
                "operationId": "SearchController_search",
                "summary": "Search the product catalog",
                "parameters": [
                    {"name": "q", "in": "query", "required": True, "schema": {"type": "string"}},
                    {"name": "limit", "in": "query", "required": False, "schema": {"type": "integer"}},
                ],
            }
        },
        "/api/v1/categories/{id}": {
            "get": {
                "operationId": "CategoriesController_findOne",
                "summary": "Get a category by id",
                "parameters": [
                    {"name": "id", "in": "path", "required": True, "schema": {"type": "string"}},
                ],
            }
        },
        "/api/v1/cart/items": {
            "post": {
                "operationId": "CartController_addItem",
                "summary": "Add an item to the cart",
                "security": [{"bearer": []}],
                "requestBody": {
                    "content": {
                        "application/json": {
                            "schema": {"$ref": "#/components/schemas/AddCartItemDto"}
                        }
                    }
                },
            }
        },
    },
    "components": {
        "schemas": {
            "AddCartItemDto": {
                "type": "object",
                "required": ["variantId"],
                "properties": {
                    "variantId": {"type": "string", "description": "Product variant ID"},
                    "quantity": {"type": "integer", "description": "Quantity to add"},
                },
            }
        }
    },
}


def test_get_with_query_params_drafts_body_template():
    manifest = build_manifest_from_openapi(NESTJS_STYLE_SPEC)
    action = manifest["actions"]["search_controller_search"]
    assert action["method"] == "GET"
    assert action["path"] == "/api/v1/search"
    assert action["parameters"]["q"]["required"] is True
    assert action["parameters"]["limit"]["required"] is False
    assert action["bodyTemplate"] == {"q": "{q}", "limit": "{limit}"}
    assert action["risk"] == "low"


def test_get_with_path_param_keeps_placeholder_in_path():
    manifest = build_manifest_from_openapi(NESTJS_STYLE_SPEC)
    action = manifest["actions"]["categories_controller_find_one"]
    assert action["path"] == "/api/v1/categories/{id}"
    assert action["parameters"]["id"]["required"] is True
    assert "bodyTemplate" not in action


def test_post_with_ref_body_resolves_schema_and_marks_high_risk():
    manifest = build_manifest_from_openapi(NESTJS_STYLE_SPEC)
    action = manifest["actions"]["cart_controller_add_item"]
    assert action["method"] == "POST"
    assert action["risk"] == "high"
    assert action["requiresAuth"] is True
    assert action["parameters"]["variantId"]["required"] is True
    assert action["parameters"]["quantity"]["required"] is False
    assert action["bodyTemplate"] == {"variantId": "{variantId}", "quantity": "{quantity}"}


def test_base_url_defaults_to_spec_servers():
    manifest = build_manifest_from_openapi(NESTJS_STYLE_SPEC)
    assert manifest["apis"]["default"]["baseUrl"] == "http://localhost:3011"


def test_base_url_override_takes_precedence():
    manifest = build_manifest_from_openapi(NESTJS_STYLE_SPEC, base_url="https://override.example")
    assert manifest["apis"]["default"]["baseUrl"] == "https://override.example"


def test_action_names_are_unique_and_contract_compatible():
    spec = {
        "paths": {
            "/x": {"get": {"operationId": "dup"}},
            "/y": {"get": {"operationId": "dup"}},
        }
    }
    manifest = build_manifest_from_openapi(spec)
    names = list(manifest["actions"].keys())
    assert len(names) == len(set(names)) == 2
    for name in names:
        assert name[0].isalpha() and name.islower()


# ---------------------------------------------------------------------------
# spec_to_actions / build_contract_from_openapi — the runtime contract shape
# (a list of actions with execute.apiRef, not the api.manifest.yaml dict).
# ---------------------------------------------------------------------------


def _actions_by_id(actions):
    return {a["id"]: a for a in actions}


def test_spec_to_actions_get_query_builds_server_api_with_body_template():
    actions = _actions_by_id(spec_to_actions(NESTJS_STYLE_SPEC))
    search = actions["search_controller_search"]
    assert search["risk"] == "low"
    assert search["requiresAuth"] is False
    execute = search["execute"]
    assert execute == {
        "type": "api",
        "runtime": "server",
        "apiRef": {
            "method": "GET",
            "path": "/api/v1/search",
            "bodyTemplate": {"q": "{q}", "limit": "{limit}"},
        },
    }
    assert search["parameters"]["q"]["required"] is True


def test_spec_to_actions_path_param_stays_in_path_without_body_template():
    actions = _actions_by_id(spec_to_actions(NESTJS_STYLE_SPEC))
    cat = actions["categories_controller_find_one"]
    assert cat["execute"]["apiRef"]["path"] == "/api/v1/categories/{id}"
    assert "bodyTemplate" not in cat["execute"]["apiRef"]
    assert cat["parameters"]["id"]["required"] is True


def test_spec_to_actions_post_ref_body_is_high_risk_and_resolves_schema():
    actions = _actions_by_id(spec_to_actions(NESTJS_STYLE_SPEC))
    add = actions["cart_controller_add_item"]
    assert add["risk"] == "high"
    assert add["requiresAuth"] is True
    assert add["execute"]["runtime"] == "server"
    assert add["execute"]["apiRef"]["bodyTemplate"] == {
        "variantId": "{variantId}",
        "quantity": "{quantity}",
    }
    assert add["parameters"]["variantId"]["required"] is True


def test_spec_to_actions_coerces_non_scalar_param_types_to_string():
    spec = {
        "paths": {
            "/bulk": {
                "post": {
                    "operationId": "bulk",
                    "requestBody": {
                        "content": {
                            "application/json": {
                                "schema": {
                                    "type": "object",
                                    "properties": {
                                        "ids": {"type": "array"},
                                        "meta": {"type": "object"},
                                        "count": {"type": "integer"},
                                    },
                                }
                            }
                        }
                    },
                }
            }
        }
    }
    params = _actions_by_id(spec_to_actions(spec))["bulk"]["parameters"]
    # Contract params only allow scalar JSON types; array/object widen to string.
    assert params["ids"]["type"] == "string"
    assert params["meta"]["type"] == "string"
    assert params["count"]["type"] == "integer"


def test_build_contract_sets_base_url_and_confirm_actions():
    contract = build_contract_from_openapi(NESTJS_STYLE_SPEC)
    assert contract["apis"]["default"]["baseUrl"] == "http://localhost:3011"
    # Every write action is gated by default.
    assert "cart_controller_add_item" in contract["risk"]["confirmActions"]
    assert "search_controller_search" not in contract["risk"]["confirmActions"]
    assert {a["id"] for a in contract["actions"]} >= {
        "search_controller_search",
        "cart_controller_add_item",
    }


def test_spec_to_actions_runtime_defaults_to_server():
    actions = _actions_by_id(spec_to_actions(NESTJS_STYLE_SPEC))
    assert all(a["execute"]["runtime"] == "server" for a in actions.values())


def test_spec_to_actions_browser_runtime_for_localhost_demos():
    actions = _actions_by_id(spec_to_actions(NESTJS_STYLE_SPEC, runtime="browser"))
    assert all(a["execute"]["runtime"] == "browser" for a in actions.values())


def test_build_contract_propagates_runtime():
    contract = build_contract_from_openapi(NESTJS_STYLE_SPEC, runtime="browser")
    assert all(a["execute"]["runtime"] == "browser" for a in contract["actions"])


def test_spec_to_actions_rejects_bad_runtime():
    import pytest

    with pytest.raises(ValueError):
        spec_to_actions(NESTJS_STYLE_SPEC, runtime="cloud")


def test_build_contract_base_url_override():
    contract = build_contract_from_openapi(NESTJS_STYLE_SPEC, base_url="https://api.example.com/")
    assert contract["apis"]["default"]["baseUrl"] == "https://api.example.com"


def test_resolve_base_url_falls_back_to_empty_when_no_server():
    assert resolve_base_url({}) == ""
    assert resolve_base_url({}, base_url="http://x.test/") == "http://x.test"


def test_spec_url_for_recognizes_spec_documents_and_appends_default():
    assert spec_url_for("http://host:3011/api/docs-json") == "http://host:3011/api/docs-json"
    assert spec_url_for("http://host/openapi.json") == "http://host/openapi.json"
    assert spec_url_for("http://host:8000") == "http://host:8000/openapi.json"
    assert spec_url_for("http://host:8000/") == "http://host:8000/openapi.json"
