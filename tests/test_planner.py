"""Tests for multi-action session planner."""

from nina.planner import (
    MAX_PLAN_STEPS,
    cancel,
    on_step_complete,
    pending_auto_action,
    schedule,
)


def _state():
    return {"sessionId": "s1", "history": [], "turnCount": 0}


def test_schedule_and_advance():
    state = _state()
    steps = [
        {"action": "search_products", "params": {"query": "hoodie"}},
        {"action": "add_to_cart", "params": {"position": 1}},
    ]
    assert schedule(state, steps)
    assert pending_auto_action(state) is None
    nxt = on_step_complete(state, "search_products")
    assert nxt is not None
    assert nxt.get("autoContinue") is True
    auto = pending_auto_action(state)
    assert auto is not None
    assert auto["action"] == "add_to_cart"


def test_plan_cap():
    state = _state()
    steps = [{"action": f"a{i}", "params": {}} for i in range(MAX_PLAN_STEPS + 2)]
    assert schedule(state, steps)
    assert len(state["pendingPlan"]["steps"]) == MAX_PLAN_STEPS


def test_stagnation_cancels():
    state = _state()
    schedule(state, [{"action": "search_products", "params": {}}] * 5)
    for _ in range(4):
        on_step_complete(state, "search_products")
    assert state["pendingPlan"]["status"] == "cancelled"


def test_auth_pause_sets_plan_resume_pending():
    state = _state()
    schedule(state, [
        {"action": "search_products", "params": {}},
        {"action": "checkout", "params": {}, "requiresAuth": True},
    ])
    on_step_complete(state, "search_products", authenticated=False)
    assert state["pendingPlan"]["awaitingAuth"] is True
    assert state["planResumePending"] is True


def test_cancel_plan():
    state = _state()
    schedule(state, [{"action": "a", "params": {}}])
    cancel(state, "user_cancel")
    assert state["pendingPlan"]["status"] == "cancelled"
