"""Tests for NINA site contract loading and resolution."""

from pathlib import Path

import pytest

from nina.contract import (
    action_available_on_page,
    expand_execute_steps,
    load_agent,
    match_page_id,
    recovery_for_report,
    resolve_intent,
    validate_agent,
    validate_report,
)

EXAMPLES = Path(__file__).resolve().parents[1] / "contracts" / "examples"
DEMO_AGENT = (
    Path(__file__).resolve().parents[1]
    / "examples"
    / "ecommerce-fastapi"
    / "public"
    / "agent.json"
)


def test_load_demo_agent():
    agent = load_agent(DEMO_AGENT)
    assert agent["site"]["id"] == "dhaaga-thread"
    assert len(agent["actions"]) >= 5


def test_match_page_id():
    agent = load_agent(DEMO_AGENT)
    assert match_page_id(agent, "http://127.0.0.1:8000/") == "home"
    pid = match_page_id(agent, "http://127.0.0.1:8000/anything")
    assert pid in ("catalog", "home")


def test_match_page_id_prefers_routes():
    contract = {
        "pages": [{"id": "home", "urlPattern": "/"}],
        "routes": [{"pattern": "/app/checkout", "pageId": "checkout"}],
    }
    assert match_page_id(contract, "https://shop.test/app/checkout") == "checkout"


def test_resolve_search_intent():
    agent = load_agent(DEMO_AGENT)
    result = resolve_intent(
        agent,
        intent="search_products",
        params={"query": "hoodie"},
        confidence=0.9,
        page_id="catalog",
    )
    assert result["ok"] is True


def test_action_available_on_page_allows_unknown_widget_page_id():
    contract = {
        "pages": [{"id": "home", "urlPattern": "/"}],
        "actions": [{
            "id": "search_products",
            "availableOn": ["home", "product_list"],
            "execute": {"type": "dom", "steps": [{"op": "navigate", "url": "/shop?search={query}"}]},
        }],
    }
    action = contract["actions"][0]
    assert action_available_on_page(contract, action, "TIGHTHUG — Shop All") is True
    assert action_available_on_page(contract, action, None) is True
    contract["pages"].append({"id": "product_detail", "urlPattern": "/product/"})
    assert action_available_on_page(contract, action, "product_detail") is False


def test_resolve_checkout_requires_confirm():
    agent = load_agent(DEMO_AGENT)
    result = resolve_intent(
        agent,
        intent="checkout",
        params={},
        confidence=0.95,
        page_id="catalog",
        session_hints={"cookies": {"nina_logged_in": "1"}},
        confirmed=False,
    )
    assert result["ok"] is True
    assert result["instructions"][0]["type"] == "confirm"


def test_expand_dom_steps():
    agent = load_agent(DEMO_AGENT)
    action = next(a for a in agent["actions"] if a["id"] == "navigate")
    steps = expand_execute_steps(agent, action, {})
    assert steps[0]["type"] == "scroll_to"
    assert steps[0]["selector"] == "#nina-catalog"


def test_validate_report_schema():
    report = {
        "siteId": "dhaaga-thread",
        "contractVersion": "1.0.0",
        "pageUrl": "http://127.0.0.1:8000/",
        "failures": [{
            "actionId": "search",
            "stepIndex": 0,
            "op": "fill",
            "selector": "#missing",
            "reason": "not_found",
        }],
    }
    assert validate_report(report) == []
    recovery = recovery_for_report(report)
    assert recovery[0]["type"] == "no_match"


def test_invalid_agent_rejected():
    errors = validate_agent({"site": {}, "version": "bad", "pages": [], "actions": [], "embed": {}})
    assert errors
