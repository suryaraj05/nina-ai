"""Action registration and validation (spec §2, rules V1–V8)."""
from __future__ import annotations

import inspect
import re

from jsonschema import Draft202012Validator
from jsonschema.exceptions import SchemaError

from .errors import error_object

NAME_RE = re.compile(r"^[a-z][a-z0-9_]{2,63}$")
RESERVED = {"chat", "session", "init", "register", "help"}
ALLOWED_KEYWORDS = {
    "type",
    "properties",
    "required",
    "enum",
    "items",
    "description",
    "default",
    "minimum",
    "maximum",
    "minLength",
    "maxLength",
    "format",
}

COMMON_VERBS = (
    "search",
    "get",
    "fetch",
    "find",
    "list",
    "create",
    "add",
    "update",
    "set",
    "delete",
    "remove",
    "send",
    "return",
    "show",
    "check",
    "track",
    "cancel",
    "place",
    "clear",
    "filter",
)


def _check_schema_subset(schema, path="inputSchema"):
    if not isinstance(schema, dict):
        return path, "schema must be an object"
    for key in schema:
        if key not in ALLOWED_KEYWORDS:
            return f"{path}.{key}", f"keyword '{key}' is outside the supported subset"
    for prop, sub in (schema.get("properties") or {}).items():
        if not isinstance(sub, dict):
            return f"{path}.properties.{prop}", "property schema must be an object"
        if not sub.get("description"):
            return (
                f"{path}.properties.{prop}",
                "every property MUST have a description",
            )
        err = _check_schema_subset(sub, f"{path}.properties.{prop}")
        if err:
            return err
    if "items" in schema:
        err = _check_schema_subset(schema["items"], f"{path}.items")
        if err:
            return err
    return None


def _verb_warning(description: str) -> str | None:
    low = description.lower()
    if not any(re.search(rf"\b{verb}", low) for verb in COMMON_VERBS):
        return (
            "description contains no recognizable action verb; the LLM "
            "routes on this text, so state plainly what the action does."
        )
    return None


def _arity_error(handler) -> str | None:
    try:
        sig = inspect.signature(handler)
    except (TypeError, ValueError):
        return None
    params = list(sig.parameters.values())
    if any(p.kind is inspect.Parameter.VAR_POSITIONAL for p in params):
        return None
    positional = [
        p
        for p in params
        if p.kind
        in (
            inspect.Parameter.POSITIONAL_ONLY,
            inspect.Parameter.POSITIONAL_OR_KEYWORD,
        )
    ]
    if len(positional) < 2:
        return (
            "Handler must be callable with signature (input, context) — "
            "it must accept at least two positional parameters."
        )
    return None


class Registry:
    def __init__(self):
        self._actions: dict[str, dict] = {}

    def all(self) -> list[dict]:
        return list(self._actions.values())

    def get(self, name: str) -> dict | None:
        return self._actions.get(name)

    def validate(self, action, initialized: bool):
        """Runs V1–V8. Returns (error_object | None, warnings list)."""
        warnings: list[str] = []
        if not isinstance(action, dict):
            return (
                error_object(
                    "NINA_ACTION_NAME_INVALID",
                    "Action definition must be an object.",
                ),
                warnings,
            )
        name = action.get("name")

        if not isinstance(name, str) or not NAME_RE.match(name) or name in RESERVED:
            return (
                error_object(
                    "NINA_ACTION_NAME_INVALID",
                    f"Action name '{name}' must match ^[a-z][a-z0-9_]{{2,63}}$ "
                    "and not be reserved.",
                ),
                warnings,
            )
        if name in self._actions:
            return (
                error_object(
                    "NINA_ACTION_DUPLICATE",
                    f"Action '{name}' is already registered.",
                ),
                warnings,
            )

        desc = action.get("description")
        if not isinstance(desc, str) or not (20 <= len(desc) <= 500):
            return (
                error_object(
                    "NINA_ACTION_DESCRIPTION_INVALID",
                    "Description must be 20-500 characters.",
                ),
                warnings,
            )

        schema = action.get("inputSchema")
        if not isinstance(schema, dict) or schema.get("type") != "object":
            return (
                error_object(
                    "NINA_ACTION_SCHEMA_INVALID",
                    'inputSchema invalid at inputSchema: root type MUST be "object".',
                ),
                warnings,
            )
        subset_err = _check_schema_subset(schema)
        if subset_err:
            return (
                error_object(
                    "NINA_ACTION_SCHEMA_INVALID",
                    f"inputSchema invalid at {subset_err[0]}: {subset_err[1]}.",
                ),
                warnings,
            )
        try:
            Draft202012Validator.check_schema(schema)
        except SchemaError as exc:
            return (
                error_object(
                    "NINA_ACTION_SCHEMA_INVALID",
                    f"inputSchema invalid at inputSchema: {exc.message}.",
                ),
                warnings,
            )

        if not callable(action.get("handler")):
            return (
                error_object(
                    "NINA_ACTION_HANDLER_INVALID",
                    "Handler must be callable.",
                ),
                warnings,
            )

        arity = _arity_error(action["handler"])
        if arity:
            return (
                error_object("NINA_ACTION_HANDLER_INVALID", arity),
                warnings,
            )

        if not initialized:
            return (
                error_object(
                    "NINA_NOT_INITIALIZED", "Call nina.init() first."
                ),
                warnings,
            )

        verb = _verb_warning(desc)
        if verb:
            warnings.append(verb)
        return None, warnings

    def validate_and_add(self, action, initialized: bool):
        error, warnings = self.validate(action, initialized)
        if error:
            return error, warnings

        name = action["name"]
        examples = action.get("examples") or []
        self._actions[name] = {
            "name": name,
            "description": action["description"],
            "inputSchema": action["inputSchema"],
            "handler": action["handler"],
            "confirmation": bool(action.get("confirmation", False)),
            "timeoutMs": action.get("timeoutMs", 10000),
            "examples": list(examples)[:5],
        }
        return None, warnings


def validate_action(action):
    """Pre-flight validation — same checks as register without mutating registry."""
    error, warnings = Registry().validate(action, initialized=True)
    if error:
        result = {"ok": False, "data": None, "error": error}
    else:
        result = {
            "ok": True,
            "error": None,
            "data": {"name": action.get("name"), "valid": True},
        }
    if warnings:
        result["warnings"] = warnings
    return result
