"""Isolated alignment critic for risk:"high" actions -- a second, narrow
check that only sees the user's literal message and the proposed action,
never conversation history or tool output, so it can't be poisoned by the
same manipulated data that might have misled the main resolution step."""
from __future__ import annotations

import asyncio

from nina import Nina
from nina.critic import check_action_alignment
from nina.init import build_llm_client

CONTRACT = {
    "site": {"id": "shop", "name": "Shop", "baseUrl": "http://x"},
    "apis": {"default": {"baseUrl": "http://x"}},
    "actions": [
        {"id": "checkout", "description": "Place an order and complete checkout.",
         "parameters": {}, "risk": "high",
         "execute": {"type": "message", "steps": []}},
    ],
    "risk": {"confirmActions": ["checkout"]},
}


def run(coro):
    return asyncio.run(coro)


def _llm_with_adapter(adapter):
    return build_llm_client({"provider": "custom", "adapter": adapter})


def test_flags_a_misaligned_action():
    def adapter(payload):
        return {"text": '{"aligned": false, "reason": "user asked about return policy, not checkout"}'}

    llm = _llm_with_adapter(adapter)
    result = run(check_action_alignment(llm, "what's your return policy", "checkout", "Place an order.", {}))
    assert result is not None
    assert "return policy" in result["reason"]


def test_passes_a_faithful_match():
    def adapter(payload):
        return {"text": '{"aligned": true, "reason": "matches the request"}'}

    llm = _llm_with_adapter(adapter)
    result = run(check_action_alignment(llm, "place my order now", "checkout", "Place an order.", {}))
    assert result is None


def test_fails_open_on_llm_error():
    def adapter(payload):
        raise RuntimeError("critic backend down")

    llm = _llm_with_adapter(adapter)
    result = run(check_action_alignment(llm, "place my order", "checkout", "Place an order.", {}))
    assert result is None


def test_end_to_end_misaligned_checkout_blocked_even_after_user_confirms():
    def adapter(payload):
        if payload.get("mode") == "compose":
            return {"text": '{"aligned": false, "reason": "quantity looks fabricated, not requested"}'}
        return {"resolution": "action", "action": "checkout",
                "input": {"quantity": 9999}, "confidence": 1.0}

    async def scenario():
        nina = Nina()
        await nina.init({"llm": {"provider": "custom", "adapter": adapter}})
        await nina.register({
            "name": "checkout",
            "description": "Place an order and complete checkout for the user.",
            "inputSchema": {"type": "object", "properties": {}, "required": []},
            "handler": lambda inp, ctx: {"orderId": "should-not-run"},
        })
        nina._core.config = {"_agentContract": CONTRACT}
        await nina.chat("checkout please", "s1")
        return await nina.chat("yes", "s1")

    envelope = run(scenario())
    data = envelope["data"]
    assert data["actionCalled"] is None
    assert data["actionResult"] is None
    assert data["intent"] == "blocked"
    assert data["guardrail"]["code"] == "ACTION_ALIGNMENT_FAILED"


def test_end_to_end_aligned_checkout_executes_normally_after_confirm():
    def adapter(payload):
        if payload.get("mode") == "compose":
            return {"text": '{"aligned": true, "reason": "matches request"}'}
        return {"resolution": "action", "action": "checkout", "input": {}, "confidence": 1.0}

    async def scenario():
        nina = Nina()
        await nina.init({"llm": {"provider": "custom", "adapter": adapter}})
        await nina.register({
            "name": "checkout",
            "description": "Place an order and complete checkout for the user.",
            "inputSchema": {"type": "object", "properties": {}, "required": []},
            "handler": lambda inp, ctx: {"orderId": "order-42"},
        })
        nina._core.config = {"_agentContract": CONTRACT}
        await nina.chat("checkout please", "s1")
        return await nina.chat("yes", "s1")

    envelope = run(scenario())
    data = envelope["data"]
    assert data["actionCalled"] == "checkout"
    assert data["actionResult"] == {"orderId": "order-42"}
