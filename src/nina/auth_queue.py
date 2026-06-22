"""Auth queue — persist and replay intents after login."""

from __future__ import annotations

from typing import Any

from .planner import resume_after_auth


def save_queued_intent(
    state: dict[str, Any],
    intent: str,
    params: dict[str, Any] | None = None,
) -> None:
    state["queuedIntent"] = {
        "intent": intent,
        "params": params or {},
    }
    state["authReplayPending"] = True


def clear_queued_intent(state: dict[str, Any]) -> None:
    state["queuedIntent"] = None
    state["authReplayPending"] = False


def get_queued_intent(state: dict[str, Any]) -> dict[str, Any] | None:
    return state.get("queuedIntent")


def pop_replay_if_ready(
    state: dict[str, Any],
    *,
    authenticated: bool,
    replay_requested: bool = False,
) -> dict[str, Any] | None:
    """
    Return {intent, params} to replay when user is authenticated and a queue exists.
    Clears the queue on success.
    """
    queued = state.get("queuedIntent")
    if not queued or not authenticated:
        return None
    if not replay_requested and not state.get("authReplayPending"):
        return None

    intent = queued.get("intent") or queued.get("action")
    if not intent:
        clear_queued_intent(state)
        return None

    params = queued.get("params") or {}
    clear_queued_intent(state)
    resume_after_auth(state)
    return {"intent": intent, "params": params, "replayed": True}
