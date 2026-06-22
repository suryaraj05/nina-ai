"""Auto-register server-side API handlers from agent.json contract."""

from __future__ import annotations

from typing import Any

import httpx

from .api_template import build_request_body, resolve_api_url


def _parameters_to_input_schema(parameters: dict[str, Any]) -> dict[str, Any]:
    props: dict[str, Any] = {}
    required: list[str] = []
    for name, spec in (parameters or {}).items():
        if not isinstance(spec, dict):
            continue
        props[name] = {
            "type": spec.get("type", "string"),
            "description": (spec.get("description") or f"{name} parameter").strip(),
        }
        if spec.get("enum"):
            props[name]["enum"] = spec["enum"]
        if spec.get("required"):
            required.append(name)
    return {"type": "object", "properties": props, "required": required}


def _execute_runtime(execute: dict[str, Any]) -> str:
    if execute.get("runtime"):
        return execute["runtime"]
    etype = execute.get("type", "dom")
    if etype == "api":
        return "server"
    if etype == "message":
        return "dom_only"
    return "dom_only"


def _ensure_description(desc: str, action_id: str) -> str:
    text = (desc or action_id).strip()
    if len(text) < 20:
        text = f"{text}. Executed via the NINA site contract."
    return text[:500]


def _passthrough_handler(inp: dict[str, Any], _ctx: dict[str, Any]) -> dict[str, Any]:
    return {"ok": True, **(inp or {})}


def make_api_handler(contract: dict[str, Any], action: dict[str, Any]) -> Any:
    """Return handler that calls the declared API endpoint via httpx."""
    execute = action.get("execute") or {}
    api_ref = execute.get("apiRef") or {}
    method = (api_ref.get("method") or "GET").upper()

    def handler(inp: dict[str, Any], ctx: dict[str, Any]) -> dict[str, Any]:
        params = dict(inp or {})
        url = resolve_api_url(contract, api_ref, params)
        body = build_request_body(api_ref, params)
        headers = {"Content-Type": "application/json", "Accept": "application/json"}
        session_id = (ctx or {}).get("sessionId")
        if session_id:
            headers["X-NINA-Session-Id"] = session_id
        try:
            with httpx.Client(timeout=30.0, follow_redirects=True) as http:
                resp = http.request(
                    method,
                    url,
                    json=body if method not in ("GET", "DELETE") else None,
                    params=body if method in ("GET", "DELETE") and isinstance(body, dict) else None,
                    headers=headers,
                )
                resp.raise_for_status()
                try:
                    data = resp.json()
                except Exception:
                    data = {"text": resp.text, "status": resp.status_code}
                return data if isinstance(data, dict) else {"data": data}
        except httpx.HTTPStatusError as exc:
            return {
                "_error": {
                    "code": "API_HTTP_ERROR",
                    "message": f"API returned {exc.response.status_code}",
                    "details": {"url": url, "body": exc.response.text[:500]},
                }
            }
        except httpx.HTTPError as exc:
            return {
                "_error": {
                    "code": "API_UNREACHABLE",
                    "message": str(exc),
                    "details": {"url": url},
                }
            }

    return handler


def contract_actions_for_registry(contract: dict[str, Any]) -> list[dict[str, Any]]:
    """Build nina.register() payloads for all contract actions."""
    out: list[dict[str, Any]] = []
    for action in contract.get("actions") or []:
        execute = action.get("execute") or {}
        etype = execute.get("type", "dom")
        runtime = _execute_runtime(execute)
        api_ref = execute.get("apiRef")
        mode = "passthrough"
        if etype in ("api", "hybrid") and runtime == "server" and api_ref:
            mode = "server_api"
        out.append({
            "name": action["id"],
            "description": _ensure_description(action.get("description", ""), action["id"]),
            "inputSchema": _parameters_to_input_schema(action.get("parameters") or {}),
            "_contractAction": action,
            "_mode": mode,
        })
    return out


async def register_from_contract(
    nina,
    contract: dict[str, Any],
    *,
    extra_handlers: dict[str, Any] | None = None,
) -> dict[str, Any]:
    """
    Register contract actions with NINA.
    extra_handlers: action_id -> handler overrides (e.g. demo Python logic).
    """
    extra_handlers = extra_handlers or {}
    registered: list[str] = []
    failed: list[dict[str, Any]] = []

    for spec in contract_actions_for_registry(contract):
        action_id = spec["name"]
        action = spec.pop("_contractAction")
        mode = spec.pop("_mode", "passthrough")
        if action_id in extra_handlers:
            handler = extra_handlers[action_id]
        elif mode == "server_api":
            handler = make_api_handler(contract, action)
        else:
            handler = _passthrough_handler
        reg_spec = {
            "name": action_id,
            "description": spec["description"],
            "inputSchema": spec["inputSchema"],
            "handler": handler,
        }
        result = await nina.register(reg_spec)
        if result.get("ok"):
            registered.append(action_id)
        else:
            failed.append({"name": action_id, "error": result.get("error")})

    return {"registered": registered, "failed": failed}
