"""Build routes.manifest.json for SPA and client-side routing coverage."""

from __future__ import annotations

from typing import Any
from urllib.parse import urlparse


def build_routes_manifest(
    crawled: list[dict[str, Any]],
    *,
    version: str = "1.0.0",
) -> dict[str, Any]:
    """
    Produce routes manifest from crawled pages.
    Each route maps a URL path pattern to a pageId (pageType).
    """
    seen: set[tuple[str, str]] = set()
    routes: list[dict[str, str]] = []
    for page in crawled:
        url = page.get("url") or ""
        page_id = page.get("pageType") or "generic"
        path = urlparse(url).path or "/"
        pattern = path.rstrip("/") or "/"
        key = (pattern, page_id)
        if key in seen:
            continue
        seen.add(key)
        routes.append({"pattern": pattern, "pageId": page_id})
    return {"version": version, "routes": routes}


def merge_routes_into_contract(
    contract: dict[str, Any],
    manifest: dict[str, Any],
) -> dict[str, Any]:
    """Attach routes from manifest to contract for runtime loaders."""
    routes = manifest.get("routes") or []
    if routes:
        contract["routes"] = routes
    return contract
