"""End-to-end registration guard.

Exercises the REAL Nina core (registry.validate_and_add) against every
real agent.json shipped in examples/, through the same register_from_contract
path the demo sidecar uses. This is the regression test for the "action
silently failed to register but register() still said ok" class of bug:
a unit test mocking nina.register() can't catch that, because it never
reaches the real validation rules in registry.py (name pattern, description
length, schema keyword subset, handler arity, etc).
"""
from __future__ import annotations

import json
from pathlib import Path

import pytest

from nina import Nina
from nina.contract_registry import register_from_contract

REPO_ROOT = Path(__file__).resolve().parent.parent
AGENT_JSON_FIXTURES = sorted(REPO_ROOT.glob("examples/*/public/agent.json"))


async def _init_nina() -> Nina:
    nina = Nina()
    res = await nina.init(
        {"llm": {"provider": "custom", "adapter": lambda p: {"resolution": "chitchat"}}}
    )
    assert res["ok"], res
    return nina


@pytest.mark.asyncio
@pytest.mark.parametrize(
    "agent_json_path", AGENT_JSON_FIXTURES, ids=lambda p: str(p.relative_to(REPO_ROOT))
)
async def test_every_contract_action_registers_with_no_silent_failures(agent_json_path):
    contract = json.loads(agent_json_path.read_text(encoding="utf-8"))
    expected_action_ids = {a["id"] for a in contract.get("actions") or []}
    assert expected_action_ids, f"{agent_json_path} declares no actions — fixture is empty"

    nina = await _init_nina()
    result = await register_from_contract(nina, contract)

    assert result["failed"] == [], (
        f"{agent_json_path}: actions failed to register: {result['failed']}"
    )
    assert set(result["registered"]) == expected_action_ids, (
        f"{agent_json_path}: registered {sorted(result['registered'])} but "
        f"contract declares {sorted(expected_action_ids)}"
    )
