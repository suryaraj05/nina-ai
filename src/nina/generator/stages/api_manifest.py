"""Merge api.manifest.yaml into agent.json actions."""

from __future__ import annotations

from pathlib import Path
from typing import Any

import yaml


def load_api_manifest(path: Path) -> dict[str, Any]:
    if not path.exists():
        return {}
    with path.open(encoding="utf-8") as f:
        return yaml.safe_load(f) or {}


def manifest_to_actions(
    manifest: dict[str, Any],
    *,
    apis: dict[str, Any] | None = None,
) -> tuple[list[dict[str, Any]], dict[str, str]]:
    """
    Convert api.manifest actions map to agent.json action definitions.
    Returns (actions, selectors) — selectors empty for API-first.
    """
    actions_out: list[dict[str, Any]] = []
    apis_map = dict(manifest.get("apis") or {})
    if apis:
        apis_map.update(apis)

    for action_id, spec in (manifest.get("actions") or {}).items():
        if not isinstance(spec, dict):
            continue
        runtime = spec.get("runtime", "server")
        parameters = spec.get("parameters") or {}
        api_ref: dict[str, Any] = {
            "apiId": spec.get("apiId", "default"),
            "method": spec.get("method", "GET"),
            "path": spec.get("path", ""),
        }
        if spec.get("paramMap"):
            api_ref["paramMap"] = spec["paramMap"]
        if spec.get("bodyTemplate") is not None:
            api_ref["bodyTemplate"] = spec["bodyTemplate"]
        execute: dict[str, Any] = {
            "type": "api",
            "runtime": runtime,
            "apiRef": api_ref,
            "steps": spec.get("uiSteps") or [],
        }
        if spec.get("uiSteps"):
            execute["type"] = "hybrid"
        actions_out.append({
            "id": action_id,
            "description": spec.get("description", action_id),
            "parameters": parameters,
            "risk": spec.get("risk", "low"),
            "requiresAuth": bool(spec.get("requiresAuth", False)),
            "availableOn": spec.get("availableOn") or ["home"],
            "execute": execute,
        })
    return actions_out, {}


def merge_api_manifest_into_contract(
    contract: dict[str, Any],
    manifest: dict[str, Any],
) -> dict[str, Any]:
    """Overlay API-first actions from manifest; prefer manifest over inferred DOM."""
    if not manifest:
        return contract
    api_actions, _ = manifest_to_actions(manifest)
    if not api_actions:
        return contract

    apis_map = dict(manifest.get("apis") or {})
    if apis_map:
        contract["apis"] = {**(contract.get("apis") or {}), **apis_map}

    by_id = {a["id"]: a for a in contract.get("actions") or []}
    for action in api_actions:
        by_id[action["id"]] = action
    contract["actions"] = list(by_id.values())

    # Mirror assemble_contract's rule: any action marked risk:"high" (e.g.
    # by the OpenAPI probe, which flags POST/PUT/PATCH/DELETE as high-risk)
    # must be enforced via contract.risk.confirmActions, not just labeled.
    high_risk_ids = {a["id"] for a in by_id.values() if a.get("risk") == "high"}
    if high_risk_ids:
        risk = dict(contract.get("risk") or {})
        risk["confirmActions"] = sorted(set(risk.get("confirmActions") or []) | high_risk_ids)
        contract["risk"] = risk

    return contract
