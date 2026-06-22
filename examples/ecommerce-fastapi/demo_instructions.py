"""Demo-only DOM instructions for the ecommerce store (hybrid mode)."""

from __future__ import annotations


def demo_turn_to_instructions(turn: dict) -> list[dict]:
    """Build demo-specific client instructions (render_products, update_cart, etc.)."""
    if not turn or not turn.get("actionCalled"):
        return []

    action = turn["actionCalled"]
    result = turn.get("actionResult") or {}
    instructions: list[dict] = []

    if action in ("search_products", "filter_products") and "results" in result:
        instructions.append({
            "type": "render_products",
            "target": "#nina-product-grid",
            "data": result.get("results") or [],
        })
        instructions.append({
            "type": "scroll_to",
            "selector": "#nina-catalog",
        })
        instructions.append({
            "type": "toast",
            "message": f"Showing {result.get('count', 0)} products on the page",
        })

    elif action == "get_product_detail" and result.get("id"):
        instructions.append({"type": "show_product_detail", "data": result})
        instructions.append({
            "type": "scroll_to",
            "selector": "#nina-product-detail",
        })

    elif action == "add_to_cart" and result.get("cart"):
        instructions.append({"type": "update_cart", "data": result})
        instructions.append({
            "type": "toast",
            "message": "Added to cart",
            "level": "success",
        })

    elif action == "remove_from_cart" and result.get("cart"):
        instructions.append({"type": "update_cart", "data": result})

    elif action == "view_cart" and result.get("cart"):
        instructions.append({"type": "update_cart", "data": result})
        instructions.append({"type": "open_cart"})

    elif action == "clear_cart":
        instructions.append({
            "type": "update_cart",
            "data": result.get("cart") or {"items": [], "total": 0},
        })

    elif action == "checkout" and (result.get("orderId") or result.get("id")):
        instructions.append({"type": "show_order", "data": result})
        instructions.append({
            "type": "update_cart",
            "data": {"cart": {"items": [], "total": 0}},
        })
        instructions.append({"type": "close_cart"})

    return instructions
