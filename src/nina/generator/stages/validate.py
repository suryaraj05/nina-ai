"""Validate assembled agent.json."""

from __future__ import annotations

from typing import Any

from nina.contract import validate_agent


def validate_contract(contract: dict[str, Any]) -> tuple[bool, list[str]]:
    """Return (ok, errors). Adds cross-field rules beyond JSON Schema."""
    errors = list(validate_agent(contract))
    page_ids = {p["id"] for p in contract.get("pages", [])}
    action_ids = {a["id"] for a in contract.get("actions", [])}

    for page in contract.get("pages", []):
        for aid in page.get("actions", []):
            if aid not in action_ids:
                errors.append(f"Page '{page['id']}' references unknown action '{aid}'")

    for action in contract.get("actions", []):
        for pid in action.get("availableOn", []):
            if pid not in page_ids:
                errors.append(f"Action '{action['id']}' availableOn unknown page '{pid}'")
        for step in action.get("execute", {}).get("steps", []):
            sid = step.get("selectorId")
            if sid and sid not in (contract.get("selectors") or {}):
                if not step.get("selector"):
                    errors.append(
                        f"Action '{action['id']}' step references unknown selectorId '{sid}'"
                    )

    return len(errors) == 0, errors
