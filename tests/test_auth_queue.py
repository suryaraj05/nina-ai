"""Auth queue and replay tests."""

import pytest

from nina.auth_queue import (
    clear_queued_intent,
    pop_replay_if_ready,
    save_queued_intent,
)


def test_save_and_pop_replay():
    state = {}
    save_queued_intent(state, "checkout", {"foo": 1})
    assert state["authReplayPending"] is True
    assert pop_replay_if_ready(state, authenticated=False) is None
    replay = pop_replay_if_ready(state, authenticated=True, replay_requested=True)
    assert replay["intent"] == "checkout"
    assert replay["params"]["foo"] == 1
    assert state["queuedIntent"] is None


@pytest.mark.asyncio
async def test_chat_replay_queued_action():
    from nina import Nina
    from nina.chat import run_turn

    nina = Nina()

    def _adapter(payload):
        if payload.get("mode") == "compose":
            return {"text": "Done."}
        if "PRE-REASONING" in payload.get("prompt", ""):
            return {"needs_reasoning": False}
        raise AssertionError("LLM should not run during replay")

    await nina.init({
        "llm": {"provider": "custom", "model": "t", "adapter": _adapter},
    })
    await nina.register({
        "name": "track",
        "description": "Track shipment status for the current order.",
        "inputSchema": {"type": "object", "properties": {}},
        "handler": lambda _i, _c: {"done": True},
    })
    sid = "replay-sess-isolated-99"
    state = await nina._core.sessions.load_or_create(sid)
    save_queued_intent(state, "track", {})
    await nina._core.sessions.save(state)
    nina._core.config = {**(nina._core.config or {}), "_sessionAuthenticated": True}
    envelope = await run_turn(nina._core, "continue", sid, replay_queued=True)
    assert envelope["ok"]
    assert envelope["data"]["actionCalled"] == "track"
    assert envelope["data"].get("replayedQueuedIntent")
