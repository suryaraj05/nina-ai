"""Multi-action plan queue with caps, auth pause, and stagnation detection."""

from __future__ import annotations

from typing import Any

MAX_PLAN_STEPS = 5
MAX_REPEAT_SAME_ACTION = 3


def _empty_plan() -> dict[str, Any]:
    return {
        "steps": [],
        "index": 0,
        "status": "idle",
        "lastAction": None,
        "repeatCount": 0,
        "awaitingAuth": False,
        "queuedAfterAuth": None,
    }


def get_plan(state: dict[str, Any]) -> dict[str, Any]:
    plan = state.get("pendingPlan")
    if not plan:
        plan = _empty_plan()
        state["pendingPlan"] = plan
    return plan


def schedule(state: dict[str, Any], steps: list[dict[str, Any]]) -> bool:
    """
    Schedule a multi-action plan. Each step: { action, params?, requiresConfirm? }.
    Returns False if over cap or empty.
    """
    if not steps:
        return False
    if len(steps) > MAX_PLAN_STEPS:
        steps = steps[:MAX_PLAN_STEPS]
    state["pendingPlan"] = {
        "steps": steps,
        "index": 0,
        "status": "active",
        "lastAction": None,
        "repeatCount": 0,
        "awaitingAuth": False,
        "queuedAfterAuth": None,
    }
    return True


def cancel(state: dict[str, Any], reason: str = "cancelled") -> None:
    plan = get_plan(state)
    plan["status"] = "cancelled"
    plan["cancelReason"] = reason
    plan["steps"] = []
    plan["index"] = 0


def current_step(state: dict[str, Any]) -> dict[str, Any] | None:
    plan = get_plan(state)
    if plan.get("status") != "active":
        return None
    steps = plan.get("steps") or []
    idx = plan.get("index", 0)
    if idx >= len(steps):
        return None
    return steps[idx]


def pending_auto_action(state: dict[str, Any]) -> dict[str, Any] | None:
    """Next plan step to run automatically before LLM (after prior step completed)."""
    plan = get_plan(state)
    if plan.get("status") != "active":
        return None
    if plan.get("awaitingAuth"):
        return None
    if not plan.get("autoContinue"):
        return None
    step = current_step(state)
    if not step:
        return None
    plan["autoContinue"] = False
    return {
        "action": step.get("action") or step.get("actionId"),
        "params": step.get("params") or {},
        "requiresConfirm": bool(step.get("requiresConfirm")),
        "planIndex": plan.get("index", 0),
    }


def on_step_complete(
    state: dict[str, Any],
    action_name: str,
    *,
    authenticated: bool = True,
) -> dict[str, Any] | None:
    """
    Advance plan after a successful action. Returns next step summary or None.
    Sets autoContinue when the next step should run on the following turn.
    """
    plan = get_plan(state)
    if plan.get("status") != "active":
        return None

    if plan.get("lastAction") == action_name:
        plan["repeatCount"] = plan.get("repeatCount", 0) + 1
    else:
        plan["repeatCount"] = 0
        plan["lastAction"] = action_name

    if plan.get("repeatCount", 0) >= MAX_REPEAT_SAME_ACTION:
        cancel(state, "stagnation")
        return None

    plan["index"] = plan.get("index", 0) + 1
    next_step = current_step(state)
    if not next_step:
        plan["status"] = "completed"
        return None

    if next_step.get("requiresAuth") and not authenticated:
        plan["awaitingAuth"] = True
        plan["queuedAfterAuth"] = next_step
        plan["autoContinue"] = False
        state["planResumePending"] = True
        return {
            "paused": True,
            "reason": "auth_required",
            "queued": next_step,
        }

    if next_step.get("requiresConfirm"):
        plan["autoContinue"] = False
        return {
            "paused": True,
            "reason": "confirm_required",
            "next": next_step,
        }

    plan["autoContinue"] = True
    return {"next": next_step, "autoContinue": True}


def resume_after_auth(state: dict[str, Any]) -> bool:
    """Resume plan after user logs in manually."""
    plan = get_plan(state)
    if not plan.get("awaitingAuth"):
        return False
    plan["awaitingAuth"] = False
    plan["autoContinue"] = True
    plan["queuedAfterAuth"] = None
    state["planResumePending"] = False
    return True


def pop_plan_resume_if_ready(
    state: dict[str, Any],
    *,
    authenticated: bool,
    resume_requested: bool = False,
) -> dict[str, Any] | None:
    """
    Return the next plan step to run after login when a plan was paused for auth.
    Clears planResumePending on success.
    """
    plan = get_plan(state)
    if plan.get("status") != "active" or not authenticated:
        return None
    if not plan.get("awaitingAuth") and not state.get("planResumePending"):
        return None
    if not resume_requested and not state.get("planResumePending"):
        return None

    if plan.get("awaitingAuth"):
        resume_after_auth(state)
    else:
        state["planResumePending"] = False

    step = pending_auto_action(state)
    if not step or not step.get("action"):
        return None
    state["planResumePending"] = False
    return {
        "action": step["action"],
        "params": step.get("params") or {},
        "resumedPlan": True,
    }


def plan_status(state: dict[str, Any]) -> dict[str, Any]:
    plan = get_plan(state)
    steps = plan.get("steps") or []
    return {
        "status": plan.get("status", "idle"),
        "index": plan.get("index", 0),
        "total": len(steps),
        "awaitingAuth": plan.get("awaitingAuth", False),
        "autoContinue": plan.get("autoContinue", False),
    }
