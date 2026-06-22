"""Core envelope and registration contract tests."""
import asyncio

from nina import Nina, validate_action


def run(coro):
    return asyncio.run(coro)


def test_init_returns_envelope_not_exception():
    nina = Nina()
    res = run(
        nina.init(
            {
                "llm": {
                    "provider": "custom",
                    "adapter": lambda p: {"resolution": "chitchat"},
                }
            }
        )
    )
    assert res["ok"]
    assert res["data"]["version"]


def test_register_batch_shape():
    nina = Nina()
    run(
        nina.init(
            {
                "llm": {
                    "provider": "custom",
                    "adapter": lambda p: {},
                }
            }
        )
    )
    actions = [
        {
            "name": "search_items",
            "description": (
                "Searches items in the catalogue for matching products and "
                "returns a list of hits for the user to browse."
            ),
            "inputSchema": {
                "type": "object",
                "properties": {
                    "query": {"type": "string", "description": "Terms."},
                },
                "required": ["query"],
            },
            "handler": lambda i, c: {"results": []},
        },
        {
            "name": "BAD",
            "description": "too short",
            "inputSchema": {"type": "object", "properties": {}},
            "handler": lambda i, c: None,
        },
    ]
    res = run(nina.register(actions))
    assert res["ok"]
    assert "search_items" in res["data"]["registered"]
    assert res["data"]["failed"]


def test_validate_action_preflight():
    action = {
        "name": "get_item",
        "description": (
            "Gets one item by id from the catalogue when the user asks about "
            "a specific product they already identified."
        ),
        "inputSchema": {
            "type": "object",
            "properties": {
                "itemId": {"type": "string", "description": "Item id."},
            },
            "required": ["itemId"],
        },
        "handler": lambda inp, ctx: {"id": inp["itemId"]},
    }
    assert validate_action(action)["ok"]
