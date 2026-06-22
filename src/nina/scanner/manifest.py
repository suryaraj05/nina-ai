"""Build and sign the NINA manifest from scanned routes."""
from __future__ import annotations

import hashlib
import json
from datetime import datetime, timezone
from pathlib import Path
from typing import Any

from .scanners import Route


def build_manifest(
    project: Path,
    framework: str,
    routes: list[Route],
) -> dict[str, Any]:
    """Assemble the manifest dict from scanned routes."""
    customer_routes = [r for r in routes if r.role == "customer"]
    admin_routes    = [r for r in routes if r.role == "admin"]
    superadmin_routes = [r for r in routes if r.role == "superadmin"]

    return {
        "version": "1.0",
        "generatedAt": datetime.now(timezone.utc).isoformat(),
        "projectDir": str(project),
        "framework": framework,
        "checksum": "",  # filled by sign_manifest()
        "summary": {
            "totalRoutes": len(routes),
            "customerRoutes": len(customer_routes),
            "adminRoutes": len(admin_routes),
            "superadminRoutes": len(superadmin_routes),
            "authRequired": sum(1 for r in routes if r.auth_required),
            "publicRoutes": sum(1 for r in routes if not r.auth_required),
        },
        "routes": [r.to_dict() for r in customer_routes],
        "adminRoutes": [r.to_dict() for r in admin_routes],
        "superadminRoutes": [r.to_dict() for r in superadmin_routes],
        "verification": None,  # filled by verifier if --verify flag used
    }


def sign_manifest(manifest: dict[str, Any]) -> dict[str, Any]:
    """Compute SHA-256 checksum of the routes payload and embed it.

    The checksum covers routes + adminRoutes + superadminRoutes only —
    not metadata like generatedAt or checksum itself. This lets us add
    verification results later without invalidating the route checksum.
    """
    payload = {
        "routes": manifest["routes"],
        "adminRoutes": manifest["adminRoutes"],
        "superadminRoutes": manifest["superadminRoutes"],
    }
    digest = hashlib.sha256(
        json.dumps(payload, sort_keys=True, ensure_ascii=False).encode()
    ).hexdigest()
    return {**manifest, "checksum": f"sha256:{digest}"}


def verify_checksum(manifest: dict[str, Any]) -> bool:
    """Return True if the manifest's checksum matches its routes content."""
    payload = {
        "routes": manifest.get("routes", []),
        "adminRoutes": manifest.get("adminRoutes", []),
        "superadminRoutes": manifest.get("superadminRoutes", []),
    }
    digest = hashlib.sha256(
        json.dumps(payload, sort_keys=True, ensure_ascii=False).encode()
    ).hexdigest()
    return manifest.get("checksum") == f"sha256:{digest}"
