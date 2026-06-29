"""Hosted NINA Console (hybrid model) for onboarding and key management.

This module intentionally ships as a lightweight in-memory control plane so
teams can run and extend it without external dependencies.
"""

from __future__ import annotations

import argparse
import hmac
import json
import os
import secrets
import time
import uuid
from pathlib import Path
from typing import Any
from urllib.parse import urlparse

import yaml
from fastapi import FastAPI, Header, HTTPException, Request
from fastapi.middleware.cors import CORSMiddleware
from fastapi.responses import FileResponse, JSONResponse, Response
from fastapi.staticfiles import StaticFiles
from pydantic import BaseModel

from .console_deps import (
    POOL,
    STORE,
    _db_url,
    _require_dashboard_token,
    _require_site_ownership,
)
from .console_schemas import (
    CliTokenIn,
    KeyIssueIn,
    KeyVerifyIn,
    MultiTenantQueryIn,
    OnboardingPackIn,
    OrgCreate,
    RegistrarExportIn,
    SeoEmbedHealthIn,
    SeoSitemapIn,
    SiteContractIn,
    SiteCreate,
    SiteLlmConfigIn,
    WizardApiConnectIn,
    WizardGenerateIn,
    WizardInitIn,
    WizardValidateIn,
)
from .crypto import is_production
from .store_util import issue_key, parse_origin
from .console_pack import (
    build_onboarding_pack_files,
    resolve_site_fields,
    zip_onboarding_pack,
)
from .contract_validate import validate_executable
from .generator.pipeline import run_pipeline
from .console_infra import (
    METRICS,
    logger,
    _IP_LIMITER,
    _KEY_LIMITER,
    _request_id_var,
    _validate_external_url,
    _validate_local_path,
)
from .console_routes_auth import router as _auth_router
from .console_routes_wizard import router as _wizard_router
from .console_routes_tools import router as _tools_router
from .console_routes_query import router as _query_router
from .console_routes_channels import router as _channels_router


# Store helpers shared with PgStore (see store_util).
_parse_origin = parse_origin
_issue_key = issue_key


from .plans import PLAN_LIMITS as _PLAN_LIMITS, current_period as _current_period, VALID_PLANS as _VALID_PLANS


def create_app() -> FastAPI:
    # Fail closed: in production the admin secret is mandatory. Without it the
    # /v1/* control plane (create org, issue keys, run scans) would be open to
    # anonymous callers. Refuse to start rather than boot insecurely.
    if is_production() and not os.environ.get("NINA_CONSOLE_ADMIN_SECRET"):
        raise RuntimeError(
            "NINA_CONSOLE_ADMIN_SECRET is required when NINA_ENV=production "
            "(refusing to start with an unauthenticated admin API)."
        )

    app = FastAPI(title="NINA Console", version="0.1.0")

    # ── Request logging middleware (outermost — captures all requests) ─────────
    @app.middleware("http")
    async def _request_logger(request: Request, call_next):
        # Honor an inbound request id (e.g. from a gateway), else mint one, so
        # every log line for this request shares a correlation id.
        req_id = request.headers.get("X-NINA-Request-Id") or uuid.uuid4().hex
        token = _request_id_var.set(req_id)
        start = time.time()
        try:
            response = await call_next(request)
        finally:
            _request_id_var.reset(token)
        response.headers["X-NINA-Request-Id"] = req_id
        duration_ms = int((time.time() - start) * 1000)
        logger.info(
            "%s %s %d",
            request.method,
            request.url.path,
            response.status_code,
            extra={
                "method": request.method,
                "path": request.url.path,
                "status": response.status_code,
                "duration_ms": duration_ms,
                "ip": (request.headers.get("x-forwarded-for", "").split(",")[0].strip()
                       or (request.client.host if request.client else "unknown")),
            },
        )
        return response

    # ── Admin auth: protect all /v1/* except the widget query endpoint ────────
    # Set NINA_CONSOLE_ADMIN_SECRET in production. When unset (local dev) the
    # middleware is a no-op so everything works without configuration.
    @app.middleware("http")
    async def _admin_auth(request: Request, call_next):
        path = request.url.path
        # Public: health check, widget query, merchant auth, static assets
        if path in ("/health",) or path == "/v1/query" or path.startswith("/v1/auth/") or not path.startswith("/v1/"):
            return await call_next(request)
        secret = os.environ.get("NINA_CONSOLE_ADMIN_SECRET")
        if not secret:
            # No secret configured. In production this is a hard deny (the boot
            # check should already have prevented startup); in dev it's a no-op.
            if is_production():
                return JSONResponse(
                    status_code=401,
                    content={"ok": False, "error": {"code": "UNAUTHORIZED", "message": "Admin API is not configured."}},
                )
            return await call_next(request)
        auth = request.headers.get("authorization", "")
        expected = f"Bearer {secret}"
        if not hmac.compare_digest(
            auth.encode() if auth else b"",
            expected.encode(),
        ):
            return JSONResponse(
                status_code=401,
                content={"ok": False, "error": {"code": "UNAUTHORIZED", "message": "Console admin secret required. Set Authorization: Bearer <NINA_CONSOLE_ADMIN_SECRET>."}},
            )
        return await call_next(request)

    # ── CORS: widget must be callable from any merchant domain ────────────────
    app.add_middleware(
        CORSMiddleware,
        allow_origins=["*"],
        allow_methods=["GET", "POST", "PUT", "OPTIONS"],
        allow_headers=["*", "Authorization"],
        expose_headers=["X-NINA-Request-Id"],
    )

    @app.on_event("shutdown")
    async def _shutdown() -> None:
        # Release pooled LLM HTTP clients so connections aren't leaked on reload.
        await POOL.aclose_all()

    @app.get("/health")
    def health() -> dict[str, Any]:
        return {
            "ok": True,
            "service": "nina-console",
            "store": {
                "orgs":  STORE.count_orgs(),
                "sites": STORE.count_sites(),
                "keys":  STORE.count_keys(),
                "backend": "postgresql" if _db_url else "json-file",
            },
            "pool": {
                "cached":  len(POOL._instances),
                "max":     int(os.environ.get("NINA_POOL_MAX_SITES", "100")),
                "circuits_open": len(POOL._circuit_until),
            },
        }

    @app.get("/v1/metrics")
    def get_metrics() -> dict[str, Any]:
        return {"ok": True, "data": METRICS.snapshot()}

    @app.post("/v1/orgs")
    def create_org(body: OrgCreate) -> dict[str, Any]:
        return {"ok": True, "data": STORE.create_org(body.name, body.ownerEmail)}

    @app.get("/v1/orgs")
    def list_orgs() -> dict[str, Any]:
        return {"ok": True, "data": STORE.list_orgs()}

    @app.post("/v1/sites")
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

    @app.get("/v1/sites")
    def list_sites(org_id: str | None = None) -> dict[str, Any]:
        return {"ok": True, "data": STORE.list_sites(org_id)}

    @app.put("/v1/sites/{site_id}/contract")
    def put_site_contract(site_id: str, body: SiteContractIn) -> dict[str, Any]:
        try:
            STORE.attach_contract(site_id, body.contract)
        except ValueError as exc:
            raise HTTPException(status_code=404, detail=str(exc)) from exc
        POOL.evict(site_id)
        return {"ok": True, "data": {"siteId": site_id, "contractAttached": True}}

    @app.put("/v1/sites/{site_id}/llm-config")
    def put_site_llm_config(site_id: str, body: SiteLlmConfigIn) -> dict[str, Any]:
        try:
            STORE.attach_llm_config(site_id, body.llmConfig)
        except ValueError as exc:
            raise HTTPException(status_code=404, detail=str(exc)) from exc
        POOL.evict(site_id)
        return {"ok": True, "data": {"siteId": site_id, "llmConfigAttached": True}}

    @app.get("/v1/sites/{site_id}/usage")
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

    @app.put("/v1/sites/{site_id}/plan")
    def set_site_plan(site_id: str, body: dict[str, Any]) -> dict[str, Any]:
        plan = body.get("plan", "")
        try:
            STORE.set_plan(site_id, plan)
        except ValueError as exc:
            raise HTTPException(status_code=400, detail=str(exc)) from exc
        return {"ok": True, "data": {"siteId": site_id, "plan": plan, "limit": _PLAN_LIMITS[plan]}}

    # Merchant dashboard routes (/v1/auth/*) live in console_routes_auth.
    app.include_router(_auth_router)
    # Onboarding wizard routes (/v1/wizard/*) live in console_routes_wizard.
    app.include_router(_wizard_router)
    # Developer/registrar/seo tooling routes live in console_routes_tools.
    app.include_router(_tools_router)
    # Widget hot path (POST /v1/query) lives in console_routes_query.
    app.include_router(_query_router)
    # WhatsApp channel + Razorpay billing webhooks live in console_routes_channels.
    app.include_router(_channels_router)

    @app.post("/v1/rotate-token")
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

    @app.post("/v1/keys/issue")
    def issue_key(body: KeyIssueIn) -> dict[str, Any]:
        try:
            rec = STORE.issue_api_key(body.siteId, body.environment, body.kind)
        except ValueError as exc:
            raise HTTPException(status_code=400, detail=str(exc)) from exc
        return {"ok": True, "data": rec}

    @app.post("/v1/keys/verify")
    def verify_key(body: KeyVerifyIn, authorization: str | None = Header(default=None)) -> dict[str, Any]:
        expected_secret = os.environ.get("NINA_CONSOLE_VERIFY_SECRET")
        if expected_secret:
            if authorization != f"Bearer {expected_secret}":
                return {"ok": False, "error": {"code": "UNAUTHORIZED", "message": "Invalid verifier secret."}}
        origin = body.origin or _parse_origin(body.pageUrl)
        ok, err = STORE.verify_publishable_key(body.apiKey, body.siteId, origin)
        return {"ok": ok, "error": err}

    @app.post("/v1/keys/{key_id}/revoke")
    def revoke_key(key_id: str) -> dict[str, Any]:
        try:
            STORE.revoke_api_key(key_id)
        except ValueError as exc:
            raise HTTPException(status_code=404, detail=str(exc)) from exc
        return {"ok": True, "data": {"keyId": key_id, "revoked": True}}

    @app.get("/v1/sites/{site_id}/keys")
    def list_site_keys(site_id: str) -> dict[str, Any]:
        if not STORE.get_site(site_id):
            raise HTTPException(status_code=404, detail="Unknown site_id")
        return {"ok": True, "data": STORE.list_api_keys_for_site(site_id)}

    @app.get("/v1/orgs/{org_id}")
    def get_org(org_id: str) -> dict[str, Any]:
        org = STORE.get_org(org_id)
        if not org:
            raise HTTPException(status_code=404, detail="Unknown org_id")
        return {"ok": True, "data": {k: v for k, v in org.items() if k != "dashboardTokenDigest"}}

    @app.get("/v1/sites/{site_id}")
    def get_site(site_id: str) -> dict[str, Any]:
        site = STORE.get_site(site_id)
        if not site:
            raise HTTPException(status_code=404, detail="Unknown site_id")
        return {"ok": True, "data": site}

    @app.post("/v1/tokens/cli")
    def issue_cli_token(body: CliTokenIn) -> dict[str, Any]:
        try:
            rec = STORE.issue_cli_token(body.orgId, body.label)
        except ValueError as exc:
            raise HTTPException(status_code=400, detail=str(exc)) from exc
        return {"ok": True, "data": rec}

    @app.get("/v1/embed/snippet")
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

    @app.post("/v1/sites/{site_id}/generate-from-url")
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

    # ── Named HTML pages (must be before the catch-all static mount) ─────────
    console_static = Path(__file__).resolve().parent / "console_static"

    @app.get("/dashboard", include_in_schema=False)
    def serve_dashboard() -> FileResponse:
        return FileResponse(console_static / "dashboard.html")

    # ── Static assets — SDK first, then console UI (catch-all must be last) ──
    sdk_dir = Path(__file__).resolve().parent / "sdk"
    if sdk_dir.exists():
        app.mount("/sdk", StaticFiles(directory=sdk_dir), name="nina-sdk")

    if console_static.exists():
        app.mount("/", StaticFiles(directory=console_static, html=True), name="console-ui")

    return app


app = create_app()


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(prog="nina-console", description="Run NINA Console API")
    parser.add_argument("--host", default="127.0.0.1")
    parser.add_argument("--port", type=int, default=8787)
    args = parser.parse_args(argv)
    import uvicorn

    uvicorn.run("nina.console_app:app", host=args.host, port=args.port, reload=False)
    return 0

