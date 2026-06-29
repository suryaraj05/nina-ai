"""Shared console dependencies: the live Store/Pool singletons and auth guards.

Importable by both ``console_app`` and the route modules without an import cycle
— this module imports the store/pool implementations, never ``console_app``.
"""

from __future__ import annotations

import os
from pathlib import Path
from typing import Any

from fastapi import HTTPException

from .console_store import ConsoleStore
from .pool import NinaPool
from .store import Store

# Backend selection: PostgreSQL when DATABASE_URL is set, else the JSON store.
_db_url = os.environ.get("DATABASE_URL", "")
if _db_url:
    from .pg_store import PgStore
    STORE: Store = PgStore()
    STORE.load()
else:
    STORE = ConsoleStore()
    STORE.load(Path(os.environ.get("NINA_CONSOLE_STORE_PATH", "nina_console_store.json")))

POOL = NinaPool()


def _require_dashboard_token(authorization: str | None) -> dict[str, Any]:
    """Validate a merchant dashboard token and return the org. Raises 401 on failure."""
    if not authorization or not authorization.startswith("Bearer "):
        raise HTTPException(status_code=401, detail="Dashboard token required.")
    raw = authorization.removeprefix("Bearer ").strip()
    org = STORE.verify_dashboard_token(raw)
    if not org:
        raise HTTPException(status_code=401, detail="Invalid or expired dashboard token.")
    return org


def _require_site_ownership(org: dict[str, Any], site_id: str) -> dict[str, Any]:
    """Confirm the org owns site_id; return the site. Raises 404/403 otherwise."""
    site = STORE.get_site(site_id)
    if not site:
        raise HTTPException(status_code=404, detail="Site not found.")
    if site.get("orgId") != org["id"]:
        raise HTTPException(status_code=403, detail="Access denied.")
    return site
