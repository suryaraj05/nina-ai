"""Plan auto-continuation, auth-replay, and plan-resume all call
_execute_action_turn directly, bypassing the entire LLM resolution path --
before this fix, that meant they also bypassed the contract-level
needs_login/confirm/blocked/critic gate entirely. A host application
scheduling a multi-step plan (via nina.session.schedule_plan) that included
a risk.confirmActions-listed step like "checkout" would have it execute
with zero confirmation, on auto-continuation, the moment the prior step
completed. This is the same class of gap as the earlier
test_contract_risk_enforcement.py fix, just reached through the plan path
instead of the main resolution path.
"""
from __future__ import annotations

import asyncio

from nina import Nina

CONTRACT = {
    "site": {"id": "shop", "name": "Shop", "baseUrl": "http://x"},
    "apis": {"default": {"baseUrl": "http://x"}},
    "actions": [
        {"id": "list_categories", "description": "List categories.", "parameters": {},
         "execute": {"type": "message", "steps": []}},
        {"id": "checkout", "description": "Place an order.", "parameters": {},
         "execute": {"type": "message", "steps": []}},
    ],
    "risk": {"confirmActions": ["checkout"]},
}


def run(coro):
    return asyncio.run(coro)


async def _make_nina_with_plan():
    def adapter(payload):
        if payload.get("mode") == "compose":
            return "Done."
        return {"resolution": "chitchat", "user_reply": "ok", "confidence": 1.0}

    nina = Nina()
    await nina.init({"llm": {"provider": "custom", "adapter": adapter}})
    await nina.register({
        "name": "list_categories",
        "description": "List the available product categories for the user.",
        "inputSchema": {"type": "object", "properties": {}, "required": []},
        "handler": lambda inp, ctx: {"results": [{"id": "cats"}]},
    })
    await nina.register({
        "name": "checkout",
        "description": "Place an order and complete checkout for the user.",
        "inputSchema": {"type": "object", "properties": {}, "required": []},
        "handler": lambda inp, ctx: {"orderId": "should-not-run-without-confirm"},
    })
    nina._core.config = {"_agentContract": CONTRACT}

    state = await nina._core.sessions.load_or_create("plan-session")
    from nina.planner import schedule
    schedule(state, [
        {"action": "list_categories", "params": {}},
        {"action": "checkout", "params": {}},
    ])
    state["pendingPlan"]["autoContinue"] = True
    await nina._core.sessions.save(state)
    return nina


def test_plan_auto_continuation_still_requires_confirmation_for_confirm_actions():
    nina = run(_make_nina_with_plan())

    # First turn: auto-continuation runs step 0 (list_categories, no
    # confirmation needed) and advances the plan to step 1 (checkout),
    # arming autoContinue for it since checkout has no per-step
    # requiresConfirm flag of its own.
    first = run(nina.chat("continue", "plan-session"))
    assert first["data"]["actionCalled"] == "list_categories"

    # Second turn: pending_auto_action() now returns the "checkout" step --
    # reached entirely through the plan auto-continuation path, never
    # through the main LLM resolution path. Before this fix this executed
    # immediately with zero confirmation, because that path called
    # _execute_action_turn directly and skipped the contract gate.
    second = run(nina.chat("continue", "plan-session"))
    data = second["data"]
    assert data["actionCalled"] is None, (
        "checkout executed via plan auto-continuation without going through "
        "the contract-level confirm gate"
    )
    assert data["intent"] == "confirmation"
