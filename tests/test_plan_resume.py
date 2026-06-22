"""Plan resume after authentication."""

import pytest

from nina.planner import (
    on_step_complete,
    pop_plan_resume_if_ready,
    schedule,
)


def _state():
    return {
        "sessionId": "plan-resume-1",
        "history": [],
        "turnCount": 0,
        "planResumePending": False,
    }


def test_pop_plan_resume_after_auth_pause():
    state = _state()
    schedule(state, [
        {"action": "search_products", "params": {}},
        {"action": "checkout", "params": {}, "requiresAuth": True},
    ])
    on_step_complete(state, "search_products", authenticated=False)
    assert state["planResumePending"] is True

    step = pop_plan_resume_if_ready(state, authenticated=False, resume_requested=True)
    assert step is None

    step = pop_plan_resume_if_ready(state, authenticated=True, resume_requested=True)
    assert step is not None
    assert step["action"] == "checkout"
    assert step.get("resumedPlan") is True
    assert state["planResumePending"] is False


@pytest.mark.asyncio
async def test_chat_resume_plan_step():
    from nina import Nina
    from nina.chat import run_turn
    from nina.planner import schedule

    nina = Nina()

    def _adapter(payload):
        if payload.get("mode") == "compose":
            return {"text": "Done."}
        raise AssertionError("LLM should not run during plan resume")

    await nina.init({
        "llm": {"provider": "custom", "model": "t", "adapter": _adapter},
    })
    await nina.register({
        "name": "checkout",
        "description": "Complete checkout for the current cart.",
        "inputSchema": {"type": "object", "properties": {}},
        "handler": lambda _i, _c: {"orderId": "ORD-1"},
    })
    sid = "plan-resume-chat"
    state = await nina._core.sessions.load_or_create(sid)
    schedule(state, [{"action": "checkout", "params": {}, "requiresAuth": True}])
    state["planResumePending"] = True
    state["pendingPlan"]["awaitingAuth"] = True
    state["pendingPlan"]["autoContinue"] = False
    await nina._core.sessions.save(state)
    nina._core.config = {**(nina._core.config or {}), "_sessionAuthenticated": True}

    envelope = await run_turn(nina._core, "", sid, resume_plan=True)
    assert envelope["ok"]
    assert envelope["data"]["actionCalled"] == "checkout"
    assert envelope["data"].get("resumedPlan")
