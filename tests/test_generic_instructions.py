"""Generic contract instruction builder tests."""

from pathlib import Path

from nina.contract import load_agent
from nina.instructions import turn_to_instructions

AGENT = Path(__file__).resolve().parents[1] / "examples" / "blank-site" / "public" / "agent.json"


def test_api_first_server_no_dom_required():
    contract = load_agent(AGENT)
    inst = turn_to_instructions(
        contract,
        {
            "actionCalled": "search_products",
            "actionInput": {"query": "hello"},
            "actionResult": {"results": [{"id": "about"}], "count": 1},
            "confidence": 0.9,
        },
        page_context={"pageId": "home"},
    )
    types = [i["type"] for i in inst]
    assert "fill" not in types
    assert "click" not in types
    assert "toast" in types


def test_api_first_server_ui_sync_steps():
    """An API-first server action can still declare optional UI-sync steps
    (e.g. scroll the results panel into view); when present, those take
    priority over the generic results toast. Uses a synthetic contract with
    a non-empty execute.steps, since the shipped demo contract's
    search_products has steps: [] and so never exercises this branch.

    Note: actionResult is always populated here because in production
    chat.py always sets it on the turn whenever actionCalled is set
    (see chat.py _build_turn) -- there's no reachable state where an action
    was called but its result is absent.
    """
    contract = load_agent(AGENT)
    action = next(a for a in contract["actions"] if a["id"] == "search_products")
    action["execute"]["steps"] = [{"op": "scroll", "selector": "#results"}]
    inst = turn_to_instructions(
        contract,
        {
            "actionCalled": "search_products",
            "actionInput": {"query": "hello"},
            "actionResult": {"results": [{"id": "about"}], "count": 1},
            "confidence": 0.9,
        },
        page_context={"pageId": "home"},
    )
    types = [i["type"] for i in inst]
    assert types == ["scroll_to"]
