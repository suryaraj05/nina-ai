"""Draft api.manifest.yaml from a live OpenAPI/Swagger spec.

Onboarding currently asks a developer to hand-write api.manifest.yaml from
memory, which is how guessed routes (e.g. POST /api/v1/products/search vs the
real GET /api/v1/search) end up shipped and 404 at demo time. This probes the
merchant's actual OpenAPI document and drafts entries from the real paths,
methods, and parameter schemas — still meant for a human to review and prune,
but starting from truth instead of a guess.
"""

from __future__ import annotations

import argparse
import re
import sys
from pathlib import Path
from typing import Any

import httpx
import yaml

_NAME_SANITIZE = re.compile(r"[^a-z0-9_]+")
_CAMEL_BOUNDARY = re.compile(r"(?<!^)(?=[A-Z])")
RESERVED_ACTION_NAMES = {"chat", "session", "init", "register", "help"}


def fetch_openapi_spec(url: str, *, timeout: float = 10.0) -> dict[str, Any]:
    with httpx.Client(timeout=timeout, follow_redirects=True) as client:
        resp = client.get(url)
        resp.raise_for_status()
        return resp.json()


def _resolve_ref(spec: dict[str, Any], ref: str) -> dict[str, Any]:
    """Resolve a local '#/components/...' JSON pointer. Returns {} if unresolved."""
    if not ref.startswith("#/"):
        return {}
    node: Any = spec
    for part in ref[2:].split("/"):
        if not isinstance(node, dict) or part not in node:
            return {}
        node = node[part]
    return node if isinstance(node, dict) else {}


def _to_snake(text: str) -> str:
    text = _CAMEL_BOUNDARY.sub("_", text)
    text = text.replace("-", "_").replace(" ", "_").replace("/", "_")
    return text.lower()


def _action_id_for(method: str, path: str, operation_id: str | None, used: set[str]) -> str:
    base = _to_snake(operation_id) if operation_id else f"{method.lower()}_{_to_snake(path)}"
    base = _NAME_SANITIZE.sub("_", base).strip("_") or "action"
    while "__" in base:
        base = base.replace("__", "_")
    if not base[0].isalpha():
        base = f"a_{base}"
    base = base[:60]
    if base in RESERVED_ACTION_NAMES:
        base = f"{base}_action"
    name = base
    i = 2
    while name in used:
        name = f"{base}_{i}"
        i += 1
    used.add(name)
    return name


def _schema_type(schema: dict[str, Any]) -> str:
    t = schema.get("type")
    if t in ("string", "integer", "number", "boolean", "array", "object"):
        return t
    return "string"


def _param_spec(name: str, schema: dict[str, Any], description: str, required: bool) -> dict[str, Any]:
    out: dict[str, Any] = {
        "type": _schema_type(schema),
        "required": required,
        "description": description or f"{name} parameter",
    }
    if schema.get("enum"):
        out["enum"] = schema["enum"]
    return out


def _request_body_params(spec: dict[str, Any], operation: dict[str, Any]) -> dict[str, Any]:
    body = operation.get("requestBody") or {}
    content = (body.get("content") or {}).get("application/json") or {}
    schema = content.get("schema") or {}
    if "$ref" in schema:
        schema = _resolve_ref(spec, schema["$ref"])
    props = schema.get("properties") or {}
    required_names = set(schema.get("required") or [])
    out: dict[str, Any] = {}
    for prop_name, prop_schema in props.items():
        if "$ref" in prop_schema:
            prop_schema = _resolve_ref(spec, prop_schema["$ref"])
        out[prop_name] = _param_spec(
            prop_name,
            prop_schema,
            prop_schema.get("description", ""),
            prop_name in required_names,
        )
    return out


def build_manifest_from_openapi(
    spec: dict[str, Any],
    *,
    base_url: str | None = None,
    methods: set[str] | None = None,
) -> dict[str, Any]:
    """Returns an api.manifest.yaml-shaped dict drafted from an OpenAPI document."""
    methods = methods or {"get", "post", "put", "patch", "delete"}
    servers = spec.get("servers") or []
    resolved_base = base_url or (servers[0].get("url") if servers else None) or ""

    actions: dict[str, Any] = {}
    used_names: set[str] = set()

    for path, path_item in (spec.get("paths") or {}).items():
        if not isinstance(path_item, dict):
            continue
        path_level_params = path_item.get("parameters") or []
        for method, operation in path_item.items():
            if method.lower() not in methods or not isinstance(operation, dict):
                continue
            action_id = _action_id_for(
                method, path, operation.get("operationId"), used_names
            )

            parameters: dict[str, Any] = {}
            for raw_param in [*path_level_params, *(operation.get("parameters") or [])]:
                if "$ref" in raw_param:
                    raw_param = _resolve_ref(spec, raw_param["$ref"])
                if raw_param.get("in") not in ("path", "query"):
                    continue
                p_name = raw_param.get("name")
                if not p_name:
                    continue
                parameters[p_name] = _param_spec(
                    p_name,
                    raw_param.get("schema") or {},
                    raw_param.get("description", ""),
                    bool(raw_param.get("required")),
                )

            body_params = _request_body_params(spec, operation)
            parameters.update(body_params)

            body_template: dict[str, Any] | None = None
            if method.lower() == "get":
                query_names = [
                    raw["name"]
                    for raw in [*path_level_params, *(operation.get("parameters") or [])]
                    if (raw.get("$ref") and _resolve_ref(spec, raw["$ref"]).get("in") == "query")
                    or raw.get("in") == "query"
                ]
                if query_names:
                    body_template = {name: f"{{{name}}}" for name in query_names}
            elif body_params:
                body_template = {name: f"{{{name}}}" for name in body_params}

            description = (
                operation.get("summary")
                or operation.get("description")
                or f"{method.upper()} {path}"
            )
            spec_entry: dict[str, Any] = {
                "method": method.upper(),
                "path": path,
                "description": description.strip()[:200],
                "parameters": parameters,
                "runtime": "server",
                "risk": "high" if method.lower() in ("post", "put", "patch", "delete") else "low",
                "requiresAuth": bool(operation.get("security")),
            }
            if body_template:
                spec_entry["bodyTemplate"] = body_template
            actions[action_id] = spec_entry

    return {
        "apis": {"default": {"baseUrl": resolved_base, "description": spec.get("info", {}).get("title", "API")}},
        "actions": actions,
    }


def probe_to_yaml(spec_url: str, output_path: Path, *, base_url: str | None = None) -> dict[str, Any]:
    spec = fetch_openapi_spec(spec_url)
    manifest = build_manifest_from_openapi(spec, base_url=base_url)
    output_path.parent.mkdir(parents=True, exist_ok=True)
    header = (
        "# DRAFT generated by `nina probe-openapi` from a live OpenAPI spec.\n"
        "# Review action ids, descriptions, risk, and requiresAuth before relying on this —\n"
        "# this captures the real paths/params but not your intent for each one.\n"
    )
    output_path.write_text(header + yaml.safe_dump(manifest, sort_keys=False), encoding="utf-8")
    return {"endpointCount": len(manifest["actions"]), "outputPath": str(output_path)}


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(
        prog="nina-probe-openapi",
        description="Draft api.manifest.yaml from a live OpenAPI/Swagger JSON spec.",
    )
    parser.add_argument("spec_url", help="URL to the OpenAPI JSON document, e.g. http://localhost:3011/api/docs-json")
    parser.add_argument("-o", "--output", type=Path, default=Path("api.manifest.yaml"))
    parser.add_argument("--base-url", help="Override the API base URL (defaults to the spec's servers[0].url)")
    args = parser.parse_args(argv)

    try:
        stats = probe_to_yaml(args.spec_url, args.output, base_url=args.base_url)
    except httpx.HTTPError as exc:
        print(f"error: could not fetch OpenAPI spec from {args.spec_url}: {exc}", file=sys.stderr)
        return 1

    print(f"Drafted {stats['endpointCount']} action(s) -> {stats['outputPath']}", file=sys.stderr)
    print("Review each entry's id, description, risk, and requiresAuth before use.", file=sys.stderr)
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
