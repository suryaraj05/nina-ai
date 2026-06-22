"""Client instruction mapping for embed SDK."""
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parents[1] / "examples" / "ecommerce-fastapi"))

from demo_instructions import demo_turn_to_instructions as turn_to_instructions


def test_search_emits_render_and_scroll():
    inst = turn_to_instructions({
        "actionCalled": "search_products",
        "actionResult": {"results": [{"id": "p01", "name": "Hoodie"}], "count": 1},
    })
    types = [i["type"] for i in inst]
    assert "render_products" in types
    assert "scroll_to" in types


def test_no_action_no_instructions():
    assert turn_to_instructions({"intent": "chitchat"}) == []
