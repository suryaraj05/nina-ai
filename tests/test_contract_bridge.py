"""Tests for demo contract bridge."""

from pathlib import Path

from nina.contract import load_agent

from contract_bridge import set_agent, turn_to_contract_instructions

DEMO_DIR = Path(__file__).resolve().parents[1] / "examples" / "ecommerce-fastapi"
AGENT = DEMO_DIR / "public" / "agent.json"


def test_hybrid_turn_includes_demo_and_dom():
    set_agent(load_agent(AGENT))
    turn = {
        "actionCalled": "search_products",
        "actionResult": {"results": [{"id": "1", "name": "Tee", "price": 100}], "count": 1},
        "confidence": 0.9,
    }
    instructions = turn_to_contract_instructions(
        turn, page_context={"pageId": "catalog"}
    )
    types = {i["type"] for i in instructions}
    assert "render_products" in types
