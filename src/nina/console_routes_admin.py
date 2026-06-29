"""Operator/admin control-plane routes (``/v1/*``, admin-secret protected).

Core CRUD the operator/CLI uses: orgs, sites, API keys, CLI tokens, plan/usage,
embed snippet, dashboard-token rotation, and self-serve contract generation from
a site URL. All sit behind the admin-secret middleware in ``console_app``.
Mounted via ``include_router`` in ``console_app.create_app``.
"""

from __future__ import annotations

import os
from pathlib import Path
from typing import Any

from fastapi import APIRouter, Header, HTTPException
from pydantic import BaseModel

from .console_deps import POOL, STORE
from .console_schemas import (
    CliTokenIn,
    KeyIssueIn,
    KeyVerifyIn,
    OrgCreate,
    SiteContractIn,
    SiteCreate,
    SiteLlmConfigIn,
)
from .plans import PLAN_LIMITS as _PLAN_LIMITS
from .store_util import parse_origin as _parse_origin

router = APIRouter()


@router.post("/v1/orgs")
def create_org(body: OrgCreate) -> dict[str, Any]:
    return {"ok": True, "data": STORE.create_org(body.name, body.ownerEmail)}

@router.get("/v1/orgs")
def list_orgs() -> dict[str, Any]:
    return {"ok": True, "data": STORE.list_orgs()}

@router.post("/v1/sites")
def create_site(body: SiteCreate) -> dict[str, Any]:
    site = STORE.create_site(
        body.orgId,
        body.name,
        body.baseUrl,
        locales=body.locales,
        markets=body.markets,
        allowed_origins=body.allowedOrigins,
        currency=body.currency,
    )
    return {"ok": True, "data": site}

@router.get("/v1/sites")
def list_sites(org_id: str | None = None) -> dict[str, Any]:
    return {"ok": True, "data": STORE.list_sites(org_id)}

@router.put("/v1/sites/{site_id}/contract")
def put_site_contract(site_id: str, body: SiteContractIn) -> dict[str, Any]:
    try:
        STORE.attach_contract(site_id, body.contract)
    except ValueError as exc:
        raise HTTPException(status_code=404, detail=str(exc)) from exc
    POOL.evict(site_id)
    return {"ok": True, "data": {"siteId": site_id, "contractAttached": True}}

@router.put("/v1/sites/{site_id}/llm-config")
def put_site_llm_config(site_id: str, body: SiteLlmConfigIn) -> dict[str, Any]:
    try:
        STORE.attach_llm_config(site_id, body.llmConfig)
    except ValueError as exc:
        raise HTTPException(status_code=404, detail=str(exc)) from exc
    POOL.evict(site_id)
    return {"ok": True, "data": {"siteId": site_id, "llmConfigAttached": True}}

@router.get("/v1/sites/{site_id}/usage")
def site_usage(site_id: str) -> dict[str, Any]:
    site = STORE.get_site(site_id)
    if not site:
        raise HTTPException(status_code=404, detail="Unknown site_id")
    plan = site.get("plan", "free")
    limit = _PLAN_LIMITS.get(plan)
    usage = STORE.get_usage(site_id)
    return {"ok": True, "data": {
        "siteId": site_id,
        "plan": plan,
        "limit": limit,
        "remaining": (limit - usage["calls"]) if limit is not None else None,
        **usage,
    }}

@router.put("/v1/sites/{site_id}/plan")
def set_site_plan(site_id: str, body: dict[str, Any]) -> dict[str, Any]:
    plan = body.get("plan", "")
    try:
        STORE.set_plan(site_id, plan)
    except ValueError as exc:
        raise HTTPException(status_code=400, detail=str(exc)) from exc
    return {"ok": True, "data": {"siteId": site_id, "plan": plan, "limit": _PLAN_LIMITS[plan]}}

@router.post("/v1/rotate-token")
def auth_rotate_token(body: dict[str, Any]) -> dict[str, Any]:
    """Rotate a merchant's dashboard token. Operator action — lives under
    /v1/ (NOT /v1/auth/) so the admin-secret middleware protects it. Issuing
    a new login token for an arbitrary org must never be unauthenticated."""
    org_id = body.get("orgId", "")
    try:
        rec = STORE.rotate_dashboard_token(org_id)
    except ValueError as exc:
        raise HTTPException(status_code=404, detail=str(exc)) from exc
    return {"ok": True, "data": rec}

@router.post("/v1/keys/issue")
def issue_key(body: KeyIssueIn) -> dict[str, Any]:
    try:
        rec = STORE.issue_api_key(body.siteId, body.environment, body.kind)
    except ValueError as exc:
        raise HTTPException(status_code=400, detail=str(exc)) from exc
    return {"ok": True, "data": rec}

@router.post("/v1/keys/verify")
def verify_key(body: KeyVerifyIn, authorization: str | None = Header(default=None)) -> dict[str, Any]:
    expected_secret = os.environ.get("NINA_CONSOLE_VERIFY_SECRET")
    if expected_secret:
        if authorization != f"Bearer {expected_secret}":
            return {"ok": False, "error": {"code": "UNAUTHORIZED", "message": "Invalid verifier secret."}}
    origin = body.origin or _parse_origin(body.pageUrl)
    ok, err = STORE.verify_publishable_key(body.apiKey, body.siteId, origin)
    return {"ok": ok, "error": err}

@router.post("/v1/keys/{key_id}/revoke")
def revoke_key(key_id: str) -> dict[str, Any]:
    try:
        STORE.revoke_api_key(key_id)
    except ValueError as exc:
        raise HTTPException(status_code=404, detail=str(exc)) from exc
    return {"ok": True, "data": {"keyId": key_id, "revoked": True}}

@router.get("/v1/sites/{site_id}/keys")
def list_site_keys(site_id: str) -> dict[str, Any]:
    if not STORE.get_site(site_id):
        raise HTTPException(status_code=404, detail="Unknown site_id")
    return {"ok": True, "data": STORE.list_api_keys_for_site(site_id)}

@router.get("/v1/orgs/{org_id}")
def get_org(org_id: str) -> dict[str, Any]:
    org = STORE.get_org(org_id)
    if not org:
        raise HTTPException(status_code=404, detail="Unknown org_id")
    return {"ok": True, "data": {k: v for k, v in org.items() if k != "dashboardTokenDigest"}}

@router.get("/v1/sites/{site_id}")
def get_site(site_id: str) -> dict[str, Any]:
    site = STORE.get_site(site_id)
    if not site:
        raise HTTPException(status_code=404, detail="Unknown site_id")
    return {"ok": True, "data": site}

@router.post("/v1/tokens/cli")
def issue_cli_token(body: CliTokenIn) -> dict[str, Any]:
    try:
        rec = STORE.issue_cli_token(body.orgId, body.label)
    except ValueError as exc:
        raise HTTPException(status_code=400, detail=str(exc)) from exc
    return {"ok": True, "data": rec}

@router.get("/v1/embed/snippet")
def embed_snippet(site_id: str, api_url: str, manifest_url: str, key_id: str) -> dict[str, Any]:
    rec = STORE.get_api_key(key_id)
    if not rec or rec["siteId"] != site_id:
        raise HTTPException(status_code=404, detail="Unknown key_id for site.")
    return {
        "ok": True,
        "data": {
            "snippet": STORE.embed_snippet(site_id, api_url, manifest_url, rec["prefix"] + "..."),
            "note": "Use the full token returned during issuance; prefix is shown for safety.",
        },
    }

# ── Self-serve contract generation from site URL ──────────────────────────
class GenerateFromUrlIn(BaseModel):
    apiBaseUrl: str | None = None
    openApiUrl: str | None = None

@router.post("/v1/sites/{site_id}/generate-from-url")
async def generate_from_url(site_id: str, body: GenerateFromUrlIn) -> dict[str, Any]:
    site = STORE.get_site(site_id)
    if not site:
        raise HTTPException(status_code=404, detail="Unknown site_id")

    import asyncio
    import tempfile
    from .console_pack import build_nina_site_yaml, build_api_manifest

    api_base = body.apiBaseUrl or site.get("baseUrl", "")
    locales = site.get("locales") or ["en"]
    allowed = site.get("allowedOrigins") or []

    site_yaml = build_nina_site_yaml(
        site_id=site["id"],
        name=site["name"],
        base_url=site["baseUrl"],
        locales=locales,
        allowed_origins=allowed,
    )

    def _run_pipeline(config_dir_str: str) -> "GenerationResult":
        from .generator.pipeline import run_pipeline as _rp
        cfg = Path(config_dir_str)
        (cfg / "nina.site.yaml").write_text(site_yaml, encoding="utf-8")
        manifest_yaml = build_api_manifest(api_base_url=api_base)
        (cfg / "api.manifest.yaml").write_text(manifest_yaml, encoding="utf-8")
        return _rp(cfg, dry_run=False, strict=False, probe=False)

    try:
        with tempfile.TemporaryDirectory() as tmp:
            loop = asyncio.get_event_loop()
            result = await loop.run_in_executor(None, _run_pipeline, tmp)
    except Exception as exc:
        return {"ok": False, "errors": [str(exc)], "data": None}

    if result.ok and result.contract:
        STORE.attach_contract(site_id, result.contract)
        POOL.evict(site_id)
        return {"ok": True, "data": {"siteId": site_id, "stats": result.stats}}

    return {"ok": False, "errors": result.errors, "data": {"stats": result.stats}}
