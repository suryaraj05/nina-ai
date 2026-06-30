import asyncio

from nina import Nina

CATALOG = [
    {
        "sku": "h1",
        "name": "Black Fleece Hoodie",
        "price": 1299,
        "currency": "INR",
        "category": "Hoodies",
        "in_stock": True,
    },
    {
        "sku": "h2",
        "name": "Grey Zip Hoodie",
        "price": 3499,
        "currency": "INR",
        "category": "Hoodies",
        "in_stock": True,
    },
]


def test_search_never_hallucinates_products():
    llm_calls: list[dict] = []

    def adapter(payload):
        llm_calls.append(payload)
        if payload.get("mode") == "compose":
            raise AssertionError("compose must not run for grounded catalog search")
        return {
            "resolution": "action",
            "action": "search_products",
            "input": {"query": "hoodies under 3000"},
            "confidence": 0.9,
        }

    async def scenario():
        nina = Nina()
        await nina.init({"llm": {"provider": "custom", "adapter": adapter}})
        await nina.register({
            "name": "search_products",
            "description": "Search the product catalog by keyword.",
            "inputSchema": {
                "type": "object",
                "properties": {
                    "query": {"type": "string", "description": "Search terms"},
                },
                "required": ["query"],
            },
            "handler": lambda inp, ctx: __import__(
                "nina.catalog_rail", fromlist=["execute_catalog_search"]
            ).execute_catalog_search(inp, ctx.get("productCatalog") or []),
        })
        nina._core.config = {
            "_productCatalog": CATALOG,
            "_agentContract": {"site": {"baseUrl": "https://shop.test"}},
        }
        return await nina.chat("search for hoodies under 3000", "s1")

    envelope = asyncio.run(scenario())
    data = envelope["data"]
    assert data["actionCalled"] == "search_products"
    assert data["actionResult"]["count"] == 1
    assert data["actionResult"]["grounded"] is True
    assert len(data.get("products") or []) == 1
    assert data["products"][0]["price"] == 1299
    assert "couldn't find" not in data["naturalLanguageResponse"].lower()
    assert "several" not in data["naturalLanguageResponse"].lower()
    reply_compose = [
        c for c in llm_calls
        if c.get("mode") == "compose" and "was executed for" in (c.get("prompt") or "")
    ]
    assert not reply_compose
