"""Compose natural-language replies from action results (spec §3 step 9)."""
from __future__ import annotations

import json

from .errors import LLMError
from .prompt import COMPOSE_TEMPLATE, render


def _deterministic_reply(action_name, result, action_error=None) -> str:
    if action_error:
        return (
            f"I ran into a problem with {action_name.replace('_', ' ')}: "
            f"{action_error['message']}"
        )
    if result is None:
        return "Done."
    if isinstance(result, dict):
        if "count" in result and "results" in result:
            n = result.get("count", len(result.get("results") or []))
            return f"I found {n} result{'s' if n != 1 else ''}."
        if "cart" in result:
            total = (result.get("cart") or {}).get("total")
            if total is not None:
                return f"Your cart is updated. Total: {total}."
        if "orderId" in result or "id" in result:
            oid = result.get("orderId") or result.get("id")
            return f"Order placed successfully. Reference: {oid}."
        if result.get("reset"):
            return "Conversation reset. How can I help?"
    return "Done — let me know if you need anything else."


async def compose_response(
    llm,
    identity,
    behavior,
    user_message,
    action_name,
    result,
    action_error=None,
) -> tuple[str, dict]:
    """Returns (natural_language_response, usage_dict)."""
    status = "error" if action_error else "success"
    payload = {
        "agent_name": identity["agentName"],
        "action_name": action_name or "none",
        "user_message": user_message,
        "result_status": status,
        "action_result_json": json.dumps(
            result if not action_error else action_error,
            ensure_ascii=False,
            default=str,
        ),
        "language": behavior.get("language", "auto"),
    }
    prompt = render(COMPOSE_TEMPLATE, payload)
    try:
        text, usage = await llm.compose(prompt)
        return text.strip(), usage
    except LLMError:
        return _deterministic_reply(action_name, result, action_error), {}
