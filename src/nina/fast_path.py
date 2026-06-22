"""Dual-path inference — a deterministic fast path for literal commands.

Most action-resolution calls go through a full LLM round trip (hundreds of
ms to seconds) even for unambiguous, literal commands like "search for
laptops" or "checkout". This module matches those literal patterns with
compiled regex in microseconds and skips the LLM call entirely; anything
that doesn't match falls through unchanged to the existing LLM resolution
path, which still does the real semantic reasoning for ambiguous or
multi-step requests.

Patterns come from two zero-extra-config sources plus one opt-in source:
1. A skill's `fastPath` frontmatter list (regex compiled from `{param}`
   placeholders), e.g. "search for {query}".
2. Exact (normalized) match against an action's own `examples`.
3. Exact (normalized) match against the action's own name/id with
   underscores treated as spaces, e.g. "list categories" -> list_categories.

Safety: actions under the contract's risk.confirmActions / risk.blockActions
are never fast-pathed — those must keep going through the full resolution
flow (and, separately, the contract-level confirm/block check), so a literal
phrase can never bypass a confirmation or block gate.
"""

from __future__ import annotations

import re
from typing import Any

_PLACEHOLDER_RE = re.compile(r"\{(\w+)\}")
_WHITESPACE_RE = re.compile(r"\s+")


def _normalize(text: str) -> str:
    return _WHITESPACE_RE.sub(" ", text.strip().lower()).rstrip(".!?")


def _compile_pattern(pattern: str) -> re.Pattern:
    parts: list[str] = []
    last = 0
    for m in _PLACEHOLDER_RE.finditer(pattern):
        parts.append(re.escape(pattern[last:m.start()]))
        parts.append(rf"(?P<{m.group(1)}>.+?)")
        last = m.end()
    parts.append(re.escape(pattern[last:]))
    body = "".join(parts).strip()
    return re.compile(rf"^\s*{body}\s*$", re.IGNORECASE)


def compile_fast_path_patterns(skills: list[dict[str, Any]]) -> list[dict[str, Any]]:
    """Returns [{action, pattern, regex}, ...] across all skills' fastPath entries."""
    compiled: list[dict[str, Any]] = []
    for skill in skills:
        for pattern in skill.get("fastPath") or []:
            for action_id in skill.get("appliesTo") or []:
                compiled.append({
                    "action": action_id,
                    "pattern": pattern,
                    "regex": _compile_pattern(pattern),
                })
    return compiled


def try_fast_path(
    message: str,
    actions: list[dict[str, Any]],
    fast_path_patterns: list[dict[str, Any]],
    *,
    excluded_actions: frozenset[str] = frozenset(),
) -> dict[str, Any] | None:
    """Returns {"action": id, "input": {...}} on a deterministic match, else None."""
    registered = {a["name"]: a for a in actions if a["name"] not in excluded_actions}
    if not registered:
        return None

    for entry in fast_path_patterns:
        if entry["action"] not in registered:
            continue
        match = entry["regex"].match(message)
        if match:
            params = {k: v.strip() for k, v in match.groupdict().items() if v is not None}
            return {"action": entry["action"], "input": params}

    normalized = _normalize(message)
    for action in registered.values():
        for example in action.get("examples") or []:
            if _normalize(example) == normalized:
                return {"action": action["name"], "input": {}}

    for action in registered.values():
        as_phrase = action["name"].replace("_", " ")
        if normalized in (action["name"], as_phrase):
            return {"action": action["name"], "input": {}}

    return None
