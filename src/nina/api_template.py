"""Template substitution for API paths and bodies in contracts."""

from __future__ import annotations

import re
from typing import Any
from urllib.parse import urljoin

_PLACEHOLDER = re.compile(r"\{([a-zA-Z_][a-zA-Z0-9_]*)\}")


def apply_params_to_string(template: str, params: dict[str, Any]) -> str:
    def repl(match: re.Match[str]) -> str:
        key = match.group(1)
        return str(params.get(key, match.group(0)))

    return _PLACEHOLDER.sub(repl, template)


def apply_params_to_object(obj: Any, params: dict[str, Any]) -> Any:
    if isinstance(obj, str):
        return apply_params_to_string(obj, params)
    if isinstance(obj, dict):
        return {k: apply_params_to_object(v, params) for k, v in obj.items()}
    if isinstance(obj, list):
        return [apply_params_to_object(v, params) for v in obj]
    return obj


def resolve_api_url(
    contract: dict[str, Any],
    api_ref: dict[str, Any],
    params: dict[str, Any] | None = None,
) -> str:
    """Build full URL from contract apis map, site baseUrl, and apiRef path."""
    params = params or {}
    path = apply_params_to_string(api_ref.get("path", ""), params)
    api_id = api_ref.get("apiId") or "default"
    apis = contract.get("apis") or {}
    group = apis.get(api_id) or apis.get("default") or {}
    base = group.get("baseUrl") or (contract.get("site") or {}).get("baseUrl") or ""
    if path.startswith("http://") or path.startswith("https://"):
        return path
    return urljoin(base.rstrip("/") + "/", path.lstrip("/"))


def build_request_body(
    api_ref: dict[str, Any],
    params: dict[str, Any],
    step_body: dict[str, Any] | None = None,
) -> dict[str, Any] | None:
    """Merge bodyTemplate / step body with paramMap and param placeholders."""
    body = api_ref.get("bodyTemplate") or step_body
    if body is None:
        param_map = api_ref.get("paramMap") or {}
        if param_map:
            return {k: params.get(v, params.get(k)) for k, v in param_map.items()}
        return None
    mapped = apply_params_to_object(body, params)
    param_map = api_ref.get("paramMap") or {}
    for key, src in param_map.items():
        if src in params:
            if isinstance(mapped, dict):
                mapped[key] = params[src]
    return mapped if isinstance(mapped, dict) else None
