"""Tests for drafting api.manifest.yaml from a live OpenAPI/Swagger spec."""
from __future__ import annotations

from nina.openapi_probe import build_manifest_from_openapi

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
