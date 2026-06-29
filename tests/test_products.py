"""products_from_result — map action results into widget product cards."""
from __future__ import annotations

import pytest

from nina import Nina
from nina.session import products_from_result


def test_shopify_style_list_maps_handle_price_image():
    result = {
        "products": [
            {
                "id": 101, "title": "Oversized Calm Blue Tee", "handle": "calm-blue-tee",
                "images": [{"src": "https://cdn.shop/calm.jpg"}],
                "variants": [{"price": "899"}],
            }
        ]
    }
    cards = products_from_result(result, "search_products", base_url="https://shop.test")
    assert len(cards) == 1
    c = cards[0]
    assert c["title"] == "Oversized Calm Blue Tee"
    assert c["id"] == 101
    assert c["price"] == "899"
    assert c["image"] == "https://cdn.shop/calm.jpg"
    assert c["url"] == "https://shop.test/products/calm-blue-tee"


def test_generic_search_results_maps_name_price_image():
    result = {"results": [
        {"sku": "h1", "name": "Navy Hoodie", "price": 1999, "image_url": "https://i/h.png", "currency": "INR"},
        {"sku": "h2", "name": "Grey Hoodie", "price": 1799, "image_url": "https://i/g.png"},
    ]}
    cards = products_from_result(result, "search")
    assert [c["title"] for c in cards] == ["Navy Hoodie", "Grey Hoodie"]
    assert cards[0]["price"] == 1999
    assert cards[0]["currency"] == "INR"
    assert cards[0]["image"] == "https://i/h.png"
    assert cards[0]["id"] == "h1"


def test_bare_list_of_items():
    cards = products_from_result([{"title": "A", "price": 10}, {"title": "B"}], "list_products")
    assert [c["title"] for c in cards] == ["A", "B"]
    assert cards[0]["price"] == 10
    assert "price" not in cards[1]


def test_single_item_dict_becomes_one_card():
    cards = products_from_result({"id": "p1", "title": "Solo Tee", "price": "499"}, "get_product_detail")
    assert len(cards) == 1 and cards[0]["title"] == "Solo Tee"


def test_cart_and_auth_actions_yield_no_cards():
    cart = {"items": [{"id": 1, "title": "In Cart", "price": 100}]}
    assert products_from_result(cart, "add_to_cart") == []
    assert products_from_result(cart, "view_cart") == []
    assert products_from_result({"name": "x"}, "login") == []


def test_non_listing_result_yields_no_cards():
    assert products_from_result({"ok": True, "status": "done"}, "do_thing") == []
    assert products_from_result("plain string", "search") == []


def test_limit_caps_cards():
    result = {"items": [{"title": f"P{i}"} for i in range(20)]}
    assert len(products_from_result(result, "search", limit=8)) == 8


def test_items_without_title_are_skipped():
    result = {"results": [{"id": 1}, {"id": 2, "title": "Has Title"}]}
    cards = products_from_result(result, "search")
    assert [c["title"] for c in cards] == ["Has Title"]


def _stub_adapter(_prompt):
    return {
        "resolution": "action", "action": "search_products",
        "input": {"query": "blue"}, "confidence": 0.95,
        "user_reply": "Here are some blue tees:",
    }


@pytest.mark.asyncio
async def test_search_turn_surfaces_products_end_to_end():
    """A real engine turn whose action returns a listing attaches turn.products
    (what the widget renders as cards)."""
    nina = Nina()
    assert (await nina.init({"llm": {"provider": "custom", "adapter": _stub_adapter}}))["ok"]

    def handler(_inp, _ctx):
        return {"results": [
            {"id": "t1", "title": "Calm Blue Tee", "price": "899", "image": "https://i/1.jpg"},
            {"id": "t2", "title": "Washed Blue Tee", "price": "799", "image": "https://i/2.jpg"},
        ]}

    assert (await nina.register({
        "name": "search_products",
        "description": "Search the catalog for products by keyword or colour",
        "inputSchema": {"type": "object", "properties": {"query": {"type": "string", "description": "Search keyword"}}, "required": []},
        "handler": handler,
    }))["ok"]

    out = await nina.chat("show me blue tees", "ses-prod-1")
    assert out["ok"], out
    products = out["data"].get("products")
    assert products, "turn should carry products"
    assert [p["title"] for p in products] == ["Calm Blue Tee", "Washed Blue Tee"]
    assert products[0]["image"] == "https://i/1.jpg"
    await nina.aclose()
