"""Merchant-visible conversation turn logs (7-day retention).

Redacted summaries of widget turns for dashboard debugging — not full session state.
"""

from __future__ import annotations

import re
from typing import Any

from .store_util import now_ts as _now_ts

RETENTION_DAYS = 7
RETENTION_SECONDS = RETENTION_DAYS * 86400
MAX_TEXT_LEN = 500
MAX_LOGS_PER_SITE = 2000

_PII_PATTERNS = (
    re.compile(r"(?i)\b[A-Z0-9._%+-]+@[A-Z0-9.-]+\.[A-Z]{2,}\b"),
    re.compile(r"(?i)\b(?:sk|pk|api)[-_][a-z0-9]{8,}\b"),
    re.compile(r"\b\d{12,19}\b"),
)


def _clip(text: str, limit: int = MAX_TEXT_LEN) -> str:
    raw = (text or "").strip()
    for pat in _PII_PATTERNS:
        raw = pat.sub("[redacted]", raw)
    if len(raw) <= limit:
        return raw
    return raw[: limit - 1] + "…"


def entry_from_turn(
    site_id: str,
    session_id: str | None,
    user_message: str,
    turn: dict[str, Any],
) -> dict[str, Any]:
    """Build a storable log row from a completed query turn."""
    result = turn.get("actionResult") if isinstance(turn.get("actionResult"), dict) else {}
    products = turn.get("products") or []
    product_count = len(products) if products else int(result.get("count") or 0)
    grounded = bool(result.get("grounded")) if result else bool(products)
    return {
        "id": str(turn.get("turnId") or ""),
        "siteId": site_id,
        "sessionId": session_id or "",
        "turnId": turn.get("turnId"),
        "userMessage": _clip(user_message),
        "reply": _clip(str(turn.get("naturalLanguageResponse") or "")),
        "actionCalled": turn.get("actionCalled") or turn.get("intent"),
        "productCount": product_count,
        "grounded": grounded,
        "createdAt": _now_ts(),
    }


def prune_entries(entries: list[dict[str, Any]], *, now: int | None = None) -> list[dict[str, Any]]:
    """Drop rows older than retention window and cap list size."""
    ts = now if now is not None else _now_ts()
    cutoff = ts - RETENTION_SECONDS
    kept = [e for e in entries if int(e.get("createdAt") or 0) >= cutoff]
    if len(kept) > MAX_LOGS_PER_SITE:
        kept = kept[-MAX_LOGS_PER_SITE:]
    return kept
