"""Merchant dashboard routes (``/v1/auth/*``).

Dashboard-token-scoped endpoints a merchant uses to self-serve: usage, keys,
LLM config, contract upload, generate-from-URL, and site settings. Mounted on
the app via ``include_router`` in ``console_app.create_app``. Auth is enforced
per-route through the dashboard-token guard, not the admin middleware.
"""

from __future__ import annotations

from typing import Any

from fastapi import APIRouter, Header, HTTPException

from .console_deps import POOL, STORE, _require_dashboard_token, _require_site_ownership
from .console_schemas import KeyIssueIn, SiteLlmConfigIn

router = APIRouter()


@router.get("/v1/auth/whoami")
def auth_whoami(authorization: str | None = Header(default=None)) -> dict[str, Any]:
    """Validate a merchant dashboard token and return org info."""
    if not authorization or not authorization.startswith("Bearer "):
        raise HTTPException(status_code=401, detail="Dashboard token required.")
    raw = authorization.removeprefix("Bearer ").strip()
    org = STORE.verify_dashboard_token(raw)
    if not org:
        raise HTTPException(status_code=401, detail="Invalid or expired dashboard token.")
    sites = STORE.list_sites(org_id=org["id"])
    return {"ok": True, "data": {"org": {k: v for k, v in org.items() if k != "dashboardTokenDigest"}, "sites": sites}}

@router.get("/v1/auth/sites/{site_id}/usage")
def merchant_get_usage(site_id: str, authorization: str | None = Header(default=None)) -> dict[str, Any]:
    org = _require_dashboard_token(authorization)
    _require_site_ownership(org, site_id)
    usage = STORE.get_usage(site_id)
    plan = STORE.get_site(site_id).get("plan", "free")
    return {"ok": True, "data": {**(usage or {}), "plan": plan}}

@router.get("/v1/auth/sites/{site_id}/keys")
def merchant_list_keys(site_id: str, authorization: str | None = Header(default=None)) -> dict[str, Any]:
    org = _require_dashboard_token(authorization)
    _require_site_ownership(org, site_id)
    return {"ok": True, "data": STORE.list_api_keys_for_site(site_id)}

@router.put("/v1/auth/sites/{site_id}/llm-config")
def merchant_set_llm_config(site_id: str, body: SiteLlmConfigIn, authorization: str | None = Header(default=None)) -> dict[str, Any]:
    org = _require_dashboard_token(authorization)
    _require_site_ownership(org, site_id)
    try:
        STORE.attach_llm_config(site_id, body.llmConfig)
    except ValueError as exc:
        raise HTTPException(status_code=400, detail=str(exc)) from exc
    POOL.evict(site_id)
    return {"ok": True, "data": {"siteId": site_id, "llmConfigAttached": True}}

@router.put("/v1/auth/sites/{site_id}/contract")
def merchant_set_contract(site_id: str, body: dict[str, Any], authorization: str | None = Header(default=None)) -> dict[str, Any]:
    org = _require_dashboard_token(authorization)
    _require_site_ownership(org, site_id)
    contract = body.get("contract")
    if not contract:
        raise HTTPException(status_code=400, detail="contract field required.")
    try:
        STORE.attach_contract(site_id, contract)
    except ValueError as exc:
        raise HTTPException(status_code=400, detail=str(exc)) from exc
    POOL.evict(site_id)
    return {"ok": True, "data": {"siteId": site_id, "contractAttached": True}}

@router.post("/v1/auth/keys/issue")
def merchant_issue_key(body: KeyIssueIn, authorization: str | None = Header(default=None)) -> dict[str, Any]:
    org = _require_dashboard_token(authorization)
    _require_site_ownership(org, body.siteId)
    try:
        rec = STORE.issue_api_key(body.siteId, body.environment, body.kind)
    except ValueError as exc:
        raise HTTPException(status_code=400, detail=str(exc)) from exc
    return {"ok": True, "data": rec}

@router.post("/v1/auth/keys/{key_id}/revoke")
def merchant_revoke_key(key_id: str, authorization: str | None = Header(default=None)) -> dict[str, Any]:
    org = _require_dashboard_token(authorization)
    key = STORE.get_api_key(key_id)
    if not key:
        raise HTTPException(status_code=404, detail="Key not found.")
    _require_site_ownership(org, key["siteId"])
    try:
        STORE.revoke_api_key(key_id)
    except ValueError as exc:
        raise HTTPException(status_code=404, detail=str(exc)) from exc
    return {"ok": True, "data": {"keyId": key_id, "revoked": True}}

@router.post("/v1/auth/sites/{site_id}/generate-from-url")
async def merchant_generate_from_url(site_id: str, body: dict[str, Any], authorization: str | None = Header(default=None)) -> dict[str, Any]:
    org = _require_dashboard_token(authorization)
    _require_site_ownership(org, site_id)
    api_base_url = body.get("apiBaseUrl", "")
    if not api_base_url:
        raise HTTPException(status_code=400, detail="apiBaseUrl required.")
    runtime = body.get("runtime", "server")
    if runtime not in ("server", "browser"):
        raise HTTPException(status_code=400, detail="runtime must be 'server' or 'browser'.")
    from urllib.parse import urlparse

    from .openapi_probe import build_contract_from_openapi, fetch_openapi_spec, resolve_base_url, spec_url_for
    try:
        spec = fetch_openapi_spec(spec_url_for(api_base_url))
        # Prefer the spec's declared server; fall back to the origin of the
        # pasted URL when the spec gives only a relative/empty server (so
        # the server-side handler has a real host to call).
        base = resolve_base_url(spec)
        if not base.startswith(("http://", "https://")):
            parsed = urlparse(api_base_url)
            base = f"{parsed.scheme}://{parsed.netloc}" if parsed.netloc else base
        contract = build_contract_from_openapi(spec, base_url=base or None, runtime=runtime)
        if not contract["actions"]:
            return {"ok": False, "errors": ["No operations found in the OpenAPI document."]}
        STORE.attach_contract(site_id, contract)
        POOL.evict(site_id)
        return {
            "ok": True,
            "data": {
                "siteId": site_id,
                "actionsFound": len(contract["actions"]),
                "baseUrl": contract["apis"]["default"]["baseUrl"],
                "runtime": runtime,
            },
        }
    except Exception as exc:
        return {"ok": False, "errors": [str(exc)]}

@router.put("/v1/auth/sites/{site_id}/settings")
def merchant_update_settings(site_id: str, body: dict[str, Any], authorization: str | None = Header(default=None)) -> dict[str, Any]:
    org = _require_dashboard_token(authorization)
    _require_site_ownership(org, site_id)
    allowed = body.get("allowedOrigins")
    if allowed is not None:
        if not isinstance(allowed, list):
            raise HTTPException(status_code=400, detail="allowedOrigins must be a list of URL strings.")
        STORE.update_site_fields(site_id, allowedOrigins=allowed)
    return {"ok": True, "data": {"siteId": site_id, "updated": True}}
