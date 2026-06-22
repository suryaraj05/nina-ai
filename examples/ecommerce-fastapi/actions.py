"""All NINA actions for the ecommerce demo.

Per-session demo state (last search, carts) lives here, keyed by the
sessionId NINA passes in the handler context — the SDK is not modified.
"""
import re
import uuid

from store import BY_ID, PRODUCTS

LAST_SEARCH: dict[str, list] = {}   # sessionId -> last result list
CARTS: dict[str, dict] = {}         # sessionId -> {productId: qty}


_SYNONYMS = {
    "hoodie": {"hoodie", "hoodies", "sweatshirt", "sweatshirts"},
    "kurta": {"kurta", "kurtas", "kurti", "kurtis"},
    "summer": {"summer", "hot", "breathable", "cotton", "linen"},
    "winter": {"winter", "warm", "wool", "puffer"},
}


def _tokens(text):
    raw = set(re.findall(r"[a-z0-9]+", str(text).lower()))
    expanded = set(raw)
    for terms in _SYNONYMS.values():
        if raw & terms:
            expanded |= terms
    return expanded


def _cart_view(session_id):
    items, total = [], 0
    for pid, qty in CARTS.get(session_id, {}).items():
        p = BY_ID[pid]
        items.append({"id": pid, "name": p["name"], "price": p["price"],
                      "qty": qty, "subtotal": p["price"] * qty})
        total += p["price"] * qty
    return {"cart": {"items": items, "total": total}}


def _err(code, message):
    return {"_error": {"code": code, "message": message}}


# --- handlers -----------------------------------------------------------------

def search_products(inp, ctx):
    terms = _tokens(inp.get("query", ""))
    for t in inp.get("tags") or []:
        terms |= _tokens(t)
    if inp.get("category"):
        terms |= _tokens(inp["category"])
    scored = []
    for p in PRODUCTS:
        hay = _tokens(p["name"]) | _tokens(p["category"])
        for tag in p["tags"]:
            hay |= _tokens(tag)
        score = len(terms & hay)
        if score:
            scored.append((score, p))
    scored.sort(key=lambda s: (-s[0], s[1]["price"]))
    results = [p for _, p in scored[:8]]
    LAST_SEARCH[ctx["sessionId"]] = results
    return {"results": results, "count": len(results)}


def filter_products(inp, ctx):
    base = LAST_SEARCH.get(ctx["sessionId"])
    if not base:
        return _err("NO_PRIOR_SEARCH",
                    "There are no search results to filter yet. Search first.")
    results = base
    if inp.get("min_price") is not None:
        results = [p for p in results if p["price"] >= inp["min_price"]]
    if inp.get("max_price") is not None:
        results = [p for p in results if p["price"] <= inp["max_price"]]
    if inp.get("size"):
        results = [p for p in results if inp["size"] in p["sizes"]]
    if inp.get("category"):
        results = [p for p in results if p["category"] == inp["category"]]
    if inp.get("in_stock") is not None:
        results = [p for p in results if p["in_stock"] == inp["in_stock"]]
    LAST_SEARCH[ctx["sessionId"]] = results
    return {"results": results, "count": len(results)}


def get_product_detail(inp, ctx):
    p = BY_ID.get(inp["productId"])
    if not p:
        return _err("PRODUCT_NOT_FOUND", f"No product with id {inp['productId']}.")
    return p


def add_to_cart(inp, ctx):
    p = BY_ID.get(inp["productId"])
    if not p:
        return _err("PRODUCT_NOT_FOUND", f"No product with id {inp['productId']}.")
    if not p["in_stock"]:
        return _err("OUT_OF_STOCK", f"{p['name']} is currently out of stock.")
    qty = inp.get("quantity") or 1
    cart = CARTS.setdefault(ctx["sessionId"], {})
    cart[p["id"]] = cart.get(p["id"], 0) + qty
    return {"added": {"id": p["id"], "name": p["name"], "qty": qty},
            **_cart_view(ctx["sessionId"])}


def remove_from_cart(inp, ctx):
    cart = CARTS.get(ctx["sessionId"], {})
    if inp["productId"] not in cart:
        return _err("NOT_IN_CART", "That product is not in the cart.")
    del cart[inp["productId"]]
    return {"removed": inp["productId"], **_cart_view(ctx["sessionId"])}


def view_cart(inp, ctx):
    return _cart_view(ctx["sessionId"])


def clear_cart(inp, ctx):
    CARTS.pop(ctx["sessionId"], None)
    return {"cleared": True, **_cart_view(ctx["sessionId"])}


def checkout(inp, ctx):
    view = _cart_view(ctx["sessionId"])
    if not view["cart"]["items"]:
        return _err("EMPTY_CART", "The cart is empty — nothing to check out.")
    order_id = f"ORD-{uuid.uuid4().hex[:8].upper()}"
    CARTS.pop(ctx["sessionId"], None)
    return {"id": order_id, "orderId": order_id, "status": "placed",
            "total": view["cart"]["total"], "items": view["cart"]["items"]}


# --- registration manifest ------------------------------------------------------

def _id_prop():
    return {"type": "string",
            "description": "The product id, e.g. 'p07'. Must come from a prior "
                           "search result, product detail, or the reference map "
                           "— never invented."}


def build_actions():
    return [
        {
            "name": "search_products",
            "description": (
                "Searches the store catalogue by free-text query, matching product "
                "names, categories, and tags such as season, occasion, or style. Use "
                "it for direct product requests like 'show me sweatshirts' and also "
                "for goal-based requests once pre-reasoning has produced inferred "
                "attributes or suggested terms, for example 'summer clothes' becoming "
                "breathable cotton short-sleeve items. Do not use it to narrow results "
                "already returned — use filter_products for that."),
            "inputSchema": {
                "type": "object",
                "properties": {
                    "query": {"type": "string",
                              "description": "Free-text search terms; include "
                                             "reasoner-suggested terms when present."},
                    "category": {"type": "string",
                                 "enum": ["tops", "bottoms", "outerwear",
                                          "footwear", "accessories"],
                                 "description": "Optional category restriction."},
                    "tags": {"type": "array", "items": {"type": "string"},
                             "description": "Optional tags such as 'summer', "
                                            "'festive', 'athletic'."},
                },
                "required": ["query"],
            },
            "handler": search_products,
            "examples": ["show me sweatshirts", "what should I wear for summer?",
                         "something festive for a wedding"],
        },
        {
            "name": "filter_products",
            "description": (
                "Narrows the results of the most recent product search in this "
                "session by price range, size, category, or stock availability. Use "
                "it only after a search has already returned results and the user "
                "wants to refine them, for example 'under 2000 rupees' or 'only size "
                "M' or 'just the ones in stock'. Do not use it for a brand-new search "
                "with different keywords — call search_products for that instead."),
            "inputSchema": {
                "type": "object",
                "properties": {
                    "min_price": {"type": "number",
                                  "description": "Minimum price in rupees."},
                    "max_price": {"type": "number",
                                  "description": "Maximum price in rupees."},
                    "size": {"type": "string",
                             "description": "Required size, e.g. 'M' or '32'."},
                    "category": {"type": "string",
                                 "enum": ["tops", "bottoms", "outerwear",
                                          "footwear", "accessories"],
                                 "description": "Keep only this category."},
                    "in_stock": {"type": "boolean",
                                 "description": "Keep only in-stock items when true."},
                },
                "required": [],
            },
            "handler": filter_products,
            "examples": ["only under 2000", "show me just the size M ones"],
        },
        {
            "name": "get_product_detail",
            "description": (
                "Returns the complete detail of one specific product identified by "
                "its product id, including price, available sizes, tags, and stock "
                "status. Use it when the user asks about a single specific item, for "
                "example 'tell me more about the second one' or 'is the kurta in "
                "stock', resolving references against the reference map. Do not use "
                "it for browsing many products or general discovery — that is what "
                "search_products is for."),
            "inputSchema": {"type": "object",
                            "properties": {"productId": _id_prop()},
                            "required": ["productId"]},
            "handler": get_product_detail,
            "examples": ["tell me more about the second one"],
        },
        {
            "name": "add_to_cart",
            "description": (
                "Adds one specific product to the user's shopping cart by product id "
                "with an optional quantity that defaults to one. Use it when the user "
                "clearly wants to buy or keep a specific identifiable item, including "
                "pronoun references resolved against the reference map such as 'add "
                "it' or 'add the second one to cart'. Do not use it when the intended "
                "product is ambiguous — ask for clarification instead of guessing an "
                "id."),
            "inputSchema": {
                "type": "object",
                "properties": {
                    "productId": _id_prop(),
                    "quantity": {"type": "integer", "minimum": 1,
                                 "description": "How many units; defaults to 1."},
                },
                "required": ["productId"],
            },
            "handler": add_to_cart,
            "confirmation": False,
            "examples": ["add it to cart", "add two of the grey sweatshirt"],
        },
        {
            "name": "remove_from_cart",
            "description": (
                "Removes a single product from the user's shopping cart by product "
                "id. Use it when the user asks to take one specific item out of the "
                "cart, for example 'remove that' right after adding something, or "
                "'take the hoodie out of my cart'. Do not use it to empty the whole "
                "cart at once — clear_cart exists for that — and do not call it for "
                "products that were never added to the cart."),
            "inputSchema": {"type": "object",
                            "properties": {"productId": _id_prop()},
                            "required": ["productId"]},
            "handler": remove_from_cart,
            "examples": ["remove that", "take the juttis out of my cart"],
        },
        {
            "name": "view_cart",
            "description": (
                "Returns the current contents of the user's shopping cart, including "
                "each item with its name, quantity, unit price, line subtotal, and "
                "the cart's grand total in rupees. Use it whenever the user asks what "
                "is in their cart, what the total comes to, or wants to review the "
                "cart before checking out. It changes nothing — it is a purely "
                "read-only operation and is always safe to call."),
            "inputSchema": {"type": "object", "properties": {}, "required": []},
            "handler": view_cart,
            "examples": ["what's in my cart?", "show my cart"],
        },
        {
            "name": "clear_cart",
            "description": (
                "Empties the user's entire shopping cart, removing every item in one "
                "destructive operation that cannot be undone. Use it only when the "
                "user explicitly asks to clear, empty, or start the cart over "
                "completely. Do not use it to remove one specific item — that is "
                "remove_from_cart. Because this is destructive, the user must confirm "
                "before the action actually runs."),
            "inputSchema": {"type": "object", "properties": {}, "required": []},
            "handler": clear_cart,
            "confirmation": True,
            "examples": ["empty my cart", "start over"],
        },
        {
            "name": "checkout",
            "description": (
                "Places an order for everything currently in the user's shopping "
                "cart, simulating payment and returning a generated order id together "
                "with the final total in rupees. Use it only when the user explicitly "
                "says they want to check out, buy now, or place the order. Do not use "
                "it just to review the cart — that is view_cart. It is a financial "
                "operation, so the user must confirm before it runs."),
            "inputSchema": {"type": "object", "properties": {}, "required": []},
            "handler": checkout,
            "confirmation": True,
            "examples": ["checkout", "place my order"],
        },
    ]
