"""Infer candidate actions per page type from DOM signals."""

from __future__ import annotations

from typing import Any
from urllib.parse import urlparse


_PAGE_ACTIONS: dict[str, list[str]] = {
    "home": ["navigate", "search"],
    "product_list": ["search", "filter", "open_product"],
    "product_detail": ["add_to_cart", "navigate"],
    "cart": ["view_cart", "remove_from_cart", "checkout", "navigate"],
    "checkout": ["checkout", "navigate"],
    "login": ["navigate"],
    "account": ["navigate"],
    "search": ["search"],
    "contact": ["navigate", "show_message"],
    "generic": ["navigate", "search"],
}


def infer_actions(
    page_types: set[str],
    dom_by_type: dict[str, dict[str, Any]],
    heal_hints: list[dict[str, Any]] | None = None,
) -> tuple[list[dict[str, Any]], dict[str, str]]:
    """
    Build action definitions from page types and extracted DOM.
    heal_hints: optional broken-selector reports to prioritize re-extraction.
    """
    heal_hints = heal_hints or []
    broken_selectors = {
        (h.get("actionId"), h.get("selectorId"))
        for report in heal_hints
        for h in report.get("failures", [])
    }

    actions: dict[str, dict[str, Any]] = {}
    selectors: dict[str, str] = {}

    def avail(*candidates: str) -> list[str]:
        """Keep only page types that exist in this crawl."""
        return [p for p in candidates if p in page_types]

    def add_action(action_id: str, spec: dict[str, Any]) -> None:
        if action_id not in actions:
            on = spec.get("availableOn")
            if isinstance(on, list):
                spec = {**spec, "availableOn": [p for p in on if p in page_types]}
            actions[action_id] = spec

    search_sel = None
    for ptype in page_types:
        signals = dom_by_type.get(ptype, {})
        inputs = signals.get("searchInputs") or []
        if inputs and not search_sel:
            search_sel = inputs[0]["selector"]
            selectors["search_input"] = search_sel

    if search_sel:
        submit_sel = 'button[type="submit"]'
        selectors.setdefault("search_submit", submit_sel)
        add_action("search", {
            "id": "search",
            "description": "Search the site by keyword or product name",
            "parameters": {
                "query": {"type": "string", "required": True, "description": "Search terms"},
            },
            "risk": "low",
            "requiresAuth": False,
            "availableOn": avail("home", "product_list", "search", "generic"),
            "execute": {
                "type": "dom",
                "steps": [
                    {"op": "fill", "selectorId": "search_input", "param": "query"},
                    {"op": "click", "selectorId": "search_submit"},
                ],
            },
        })

    add_action("navigate", {
        "id": "navigate",
        "description": "Go to a page on this site by path or section name",
        "parameters": {
            "url": {"type": "string", "required": True, "description": "Target path e.g. /shop"},
        },
        "risk": "low",
        "requiresAuth": False,
        "availableOn": avail(*page_types) or ["generic"],
        "execute": {
            "type": "dom",
            "steps": [{"op": "navigate", "url": "{url}"}],
        },
    })

    product_pages = avail("product_list", "home", "product_detail")
    if product_pages:
        add_action("open_product", {
            "id": "open_product",
            "description": "Open a product detail page",
            "parameters": {
                "productUrl": {
                    "type": "string",
                    "required": True,
                    "description": "Product page path or URL e.g. /product/creator-pro",
                },
            },
            "risk": "low",
            "requiresAuth": False,
            "availableOn": product_pages,
            "execute": {
                "type": "dom",
                "steps": [{"op": "navigate", "url": "{productUrl}"}],
            },
        })

    add_cart_on = avail("product_detail", "product_list")
    if add_cart_on and ("cart" in page_types or "product_detail" in page_types):
        add_action("add_to_cart", {
            "id": "add_to_cart",
            "description": "Add the current product to the shopping cart",
            "parameters": {},
            "risk": "medium",
            "requiresAuth": False,
            "availableOn": avail("product_detail", "product_list"),
            "execute": {
                "type": "dom",
                "steps": [
                    {"op": "click", "selector": '[data-testid="add-to-cart"], button[name="add-to-cart"]'},
                    {"op": "toast", "message": "Added to cart", "level": "success"},
                ],
            },
        })

    if "cart" in page_types:
        add_action("checkout", {
            "id": "checkout",
            "description": "Proceed to checkout and place order",
            "parameters": {},
            "risk": "high",
            "requiresAuth": True,
            "availableOn": avail("cart", "checkout"),
            "execute": {
                "type": "dom",
                "steps": [
                    {"op": "click", "selector": '[data-testid="checkout"], a[href*="checkout"]'},
                ],
            },
        })

    add_action("show_message", {
        "id": "show_message",
        "description": "Answer an informational question without changing the page",
        "parameters": {
            "message": {
                "type": "string",
                "required": True,
                "description": "Informational reply to show the user",
            },
        },
        "risk": "low",
        "requiresAuth": False,
        "availableOn": avail(*page_types) or ["generic"],
        "execute": {
            "type": "message",
            "steps": [{"op": "show_message", "message": "{message}"}],
        },
    })

    for action_id, sid in broken_selectors:
        if action_id and action_id in actions and sid:
            actions[action_id].setdefault("_heal", []).append(sid)

    return list(actions.values()), selectors


def url_pattern_for_type(page_type: str, sample_urls: list[str]) -> str:
    """Derive urlPattern from sample crawled URLs."""
    paths = [urlparse(u).path for u in sample_urls]
    if page_type == "home":
        return "/"
    if page_type == "product_list":
        return "/shop/*"
    if page_type == "cart":
        return "/cart*"
    if page_type == "checkout":
        return "/checkout*"
    if page_type == "login":
        return "/login*"
    if page_type == "product_detail":
        return "/product/*"
    if paths:
        common = paths[0].rstrip("/") or "/"
        return common + "*"
    return "/*"
