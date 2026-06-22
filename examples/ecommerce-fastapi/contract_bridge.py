"""Bridge NINA turns to client instructions — generic contract + optional demo hybrid."""

from __future__ import annotations

from typing import Any, Callable

from nina.instructions import turn_to_instructions as generic_turn_to_instructions

from demo_instructions import demo_turn_to_instructions

_AGENT: dict[str, Any] | None = None
_DEMO_HANDLER: Callable[[dict], list[dict]] | None = demo_turn_to_instructions


def set_agent(contract: dict[str, Any]) -> None:
    global _AGENT
    _AGENT = contract


def set_demo_handler(handler: Callable[[dict], list[dict]] | None) -> None:
    global _DEMO_HANDLER
    _DEMO_HANDLER = handler


def turn_to_contract_instructions(
    turn: dict[str, Any],
    *,
    page_context: dict[str, Any] | None = None,
    session_hints: dict[str, Any] | None = None,
    confirmed: bool = False,
    hybrid_demo: bool = True,
) -> list[dict[str, Any]]:
    """Generic contract instructions, merged with demo handlers when hybrid_demo=True."""
    if not _AGENT:
        if hybrid_demo and _DEMO_HANDLER:
            return _DEMO_HANDLER(turn)
        return []

    generic = generic_turn_to_instructions(
        _AGENT,
        turn,
        page_context=page_context,
        session_hints=session_hints,
        confirmed=confirmed,
    )

    if not hybrid_demo or not _DEMO_HANDLER:
        return generic

    action_id = turn.get("actionCalled")
    if not action_id:
        return generic

    action = next((a for a in _AGENT.get("actions", []) if a.get("id") == action_id), None)
    if not action or action.get("execute", {}).get("type") != "hybrid":
        return generic

    demo = _DEMO_HANDLER(turn)
    if generic and generic[0].get("type") in ("needs_login", "confirm", "no_match"):
        return generic

    out = list(demo)
    for step in generic:
        if step.get("type") not in {i.get("type") for i in out}:
            out.append(step)
    return out
