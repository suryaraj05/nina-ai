"""Handler invocation with timeout (spec §3 step 8). Returns (result, error|None)."""
from __future__ import annotations

import asyncio
import inspect

from .errors import error_object


async def _invoke(handler, input_, context):
    if inspect.iscoroutinefunction(handler):
        return await handler(input_, context)
    result = await asyncio.to_thread(handler, input_, context)
    if inspect.isawaitable(result):
        result = await result
    return result


async def execute_action(action, input_, context):
    name = action["name"]
    timeout_ms = action.get("timeoutMs") or 10000
    try:
        result = await asyncio.wait_for(
            _invoke(action["handler"], input_, context),
            timeout_ms / 1000,
        )
    except asyncio.TimeoutError:
        return None, error_object(
            "ACTION_TIMEOUT",
            f"Action '{name}' exceeded {timeout_ms} ms.",
            {"timeoutMs": timeout_ms},
        )
    except Exception as exc:
        return None, error_object(
            "ACTION_RUNTIME_ERROR",
            f"Action '{name}' raised an unexpected error.",
            {"reason": str(exc)},
        )

    if isinstance(result, dict) and isinstance(result.get("_error"), dict):
        err = result["_error"]
        return None, error_object(
            "ACTION_DOMAIN_ERROR",
            str(err.get("message") or "Action reported a domain failure."),
            {"code": err.get("code"), "action": name},
        )
    return result, None
