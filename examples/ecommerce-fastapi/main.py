"""FastAPI ecommerce demo — split-panel embed + server-side action layer."""

import os

from contextlib import asynccontextmanager

from datetime import datetime, timezone

from pathlib import Path

from typing import Any



from fastapi import FastAPI, Header, Request

from fastapi.responses import JSONResponse

from fastapi.staticfiles import StaticFiles

from pydantic import BaseModel



from nina import Nina

from nina.api_security import RateLimiter, verify_api_key

from nina.contract import is_authenticated, load_agent, recovery_for_report, validate_report

from actions import build_actions

from contract_bridge import set_agent, turn_to_contract_instructions

from store import PRODUCTS



REPO_ROOT = Path(__file__).resolve().parents[2]

PUBLIC_DIR = Path(__file__).resolve().parent / "public"

SDK_DIR = REPO_ROOT / "sdk"

BLANK_DIR = REPO_ROOT / "examples" / "blank-site" / "public"



nina = Nina()

AGENT_PATH = PUBLIC_DIR / "agent.json"

_agent_contract: dict[str, Any] | None = None

_selector_reports: list[dict[str, Any]] = []

_rate_limiter = RateLimiter(

    max_requests=int(os.environ.get("NINA_RATE_LIMIT", "60")),

    window_seconds=int(os.environ.get("NINA_RATE_WINDOW", "60")),

)





def _security_config() -> dict[str, Any]:

    if not _agent_contract:

        return {}

    risk = _agent_contract.get("risk") or {}

    auth = _agent_contract.get("auth") or {}

    return {

        "blockPatterns": risk.get("blockPatterns"),

        "blockActions": risk.get("blockActions") or [],

        "loginUrl": auth.get("loginUrl", "/login"),

        "enableCredentialBlock": True,

        "enableInjectionGuard": True,

    }





def _llm_config() -> dict:

    provider = os.environ.get("NINA_LLM_PROVIDER", "ollama").lower()

    if provider == "ollama":

        return {

            "provider": "ollama",

            "model": os.environ.get("NINA_MODEL", "qwen2.5:7b"),

            "endpoint": os.environ.get("OLLAMA_HOST", "http://localhost:11434"),

            "temperature": float(os.environ.get("NINA_TEMPERATURE", "0.2")),

            "maxTokens": int(os.environ.get("NINA_MAX_TOKENS", "1024")),

        }

    if provider == "openai":

        return {

            "provider": "openai",

            "model": os.environ.get("NINA_MODEL", "gpt-4o-mini"),

            "apiKey": os.environ["OPENAI_API_KEY"],

        }

    if provider == "gemini":

        # Gemini exposes an OpenAI-compatible /chat/completions endpoint, so

        # NINA's existing "openai" provider works against it unchanged --

        # just point it at Google's base URL with a Gemini key.

        return {

            "provider": "openai",

            "model": os.environ.get("NINA_MODEL", "gemini-2.5-flash"),

            "apiKey": os.environ["GEMINI_API_KEY"],

            "endpoint": "https://generativelanguage.googleapis.com/v1beta/openai",

        }

    return {

        "provider": "anthropic",

        "model": os.environ.get("NINA_MODEL", "claude-sonnet-4-20250514"),

        "apiKey": os.environ["ANTHROPIC_API_KEY"],

    }





def _apply_request_context(body: "QueryIn") -> None:

    authenticated = False

    if _agent_contract and body.session_hints is not None:

        authenticated = is_authenticated(_agent_contract, body.session_hints)

    nina._core.config = {

        **(nina._core.config or {}),

        "_agentContract": _agent_contract,

        "_sessionHints": body.session_hints or {},

        "_sessionAuthenticated": authenticated,

        "_pageId": (body.page_context or {}).get("pageId"),

        "_replayQueued": body.replayQueued,

        "_resumePlan": body.replayPlan,

    }





async def _api_guard(

    request: Request,

    x_nina_api_key: str | None = Header(default=None, alias="X-NINA-API-Key"),

) -> JSONResponse | None:

    ok_key, key_err = verify_api_key(x_nina_api_key)

    if not ok_key:

        return JSONResponse(

            status_code=401,

            content={"ok": False, "data": None, "error": key_err},

        )

    client = request.client.host if request.client else "unknown"

    ok_rate, rate_err = _rate_limiter.allow(client)

    if not ok_rate:

        return JSONResponse(

            status_code=429,

            content={"ok": False, "data": None, "error": rate_err},

        )

    return None





@asynccontextmanager

async def lifespan(app: FastAPI):

    global _agent_contract

    if AGENT_PATH.exists():

        _agent_contract = load_agent(AGENT_PATH)

        set_agent(_agent_contract)

    res = await nina.init({

        "llm": _llm_config(),

        "security": _security_config(),

        "identity": {

            "agentName": "NINA",

            "persona": "A helpful, concise shopping assistant for an Indian "

                       "clothing store. Friendly but never chatty.",

            "systemContext": "Store: Dhaaga & Thread. All prices are in Indian "

                             "Rupees (INR). Catalogue mixes western and Indian "

                             "ethnic wear. Sizes are per-product.",

        },

        "behavior": {"confidenceThreshold": 0.7},

        "debug": os.environ.get("NINA_DEBUG", "").lower() in ("1", "true", "yes"),

    })

    if not res["ok"]:

        raise RuntimeError(f"NINA init failed: {res['error']['message']}")

    reg = await nina.register(build_actions())

    if reg["data"]["failed"]:

        raise RuntimeError(f"Action registration failed: {reg['data']['failed']}")

    yield





app = FastAPI(title="NINA ecommerce demo", lifespan=lifespan)





class QueryIn(BaseModel):

    message: str = ""

    transcript: str = ""

    sessionId: str

    siteId: str | None = None

    page_context: dict[str, Any] | None = None

    snapshot: dict[str, Any] | None = None

    session_hints: dict[str, Any] | None = None

    contractVersion: str | None = None

    confirmed: bool = False

    priorIntent: str | None = None

    replayQueued: bool = False

    replayPlan: bool = False





class SelectorReportIn(BaseModel):

    siteId: str

    contractVersion: str

    sessionId: str | None = None

    pageUrl: str

    pageId: str | None = None

    userAgent: str | None = None

    failures: list[dict[str, Any]]

    snapshot: dict[str, Any] | None = None

    reportedAt: str | None = None





async def _handle_query(body: QueryIn) -> dict[str, Any]:

    text = body.transcript or body.message

    _apply_request_context(body)



    replay = body.replayQueued

    if not replay and _agent_contract and body.session_hints:

        if is_authenticated(_agent_contract, body.session_hints):

            sess = await nina._core.sessions.get(body.sessionId)

            if sess and sess.get("authReplayPending") and sess.get("queuedIntent"):

                replay = True



    resume_plan = body.replayPlan

    if not resume_plan and _agent_contract and body.session_hints:

        if is_authenticated(_agent_contract, body.session_hints):

            sess = await nina._core.sessions.get(body.sessionId)

            if sess and sess.get("planResumePending"):

                resume_plan = True



    envelope = await nina.chat(

        text if not (replay or resume_plan) else "",

        body.sessionId,

        replay_queued=replay,

        resume_plan=resume_plan,

    )

    if envelope.get("ok") and envelope.get("data"):

        turn = dict(envelope["data"])

        if turn.get("intent") == "blocked" and turn.get("instructions"):

            pass

        else:

            contract_instructions = turn_to_contract_instructions(

                turn,

                page_context=body.page_context,

                session_hints=body.session_hints,

                confirmed=body.confirmed,

            )

            guard_instructions = turn.get("instructions") or []

            turn["instructions"] = guard_instructions + contract_instructions

            for inst in turn["instructions"]:

                if inst.get("type") == "needs_login":

                    qi = inst.get("queuedIntent") or {}

                    if qi.get("intent"):

                        await nina.session.set_queued_intent(

                            body.sessionId,

                            qi["intent"],

                            qi.get("params"),

                        )

        envelope = {**envelope, "data": turn}

    return envelope





@app.post("/v1/query")

async def query_v1(

    body: QueryIn,

    request: Request,

    x_nina_api_key: str | None = Header(default=None, alias="X-NINA-API-Key"),

):

    blocked = await _api_guard(request, x_nina_api_key)

    if blocked:

        return blocked

    return await _handle_query(body)





@app.post("/chat")

async def chat(

    body: QueryIn,

    request: Request,

    x_nina_api_key: str | None = Header(default=None, alias="X-NINA-API-Key"),

):

    blocked = await _api_guard(request, x_nina_api_key)

    if blocked:

        return blocked

    return await _handle_query(body)





@app.post("/v1/report-broken-selector")

async def report_broken_selector(

    body: SelectorReportIn,

    request: Request,

    x_nina_api_key: str | None = Header(default=None, alias="X-NINA-API-Key"),

):

    blocked = await _api_guard(request, x_nina_api_key)

    if blocked:

        return blocked

    report = body.model_dump()

    if not report.get("reportedAt"):

        report["reportedAt"] = datetime.now(timezone.utc).isoformat()

    errors = validate_report(report)

    if errors:

        return {

            "ok": False,

            "data": None,

            "error": {"code": "INVALID_REPORT", "message": "; ".join(errors)},

        }

    _selector_reports.append(report)

    recovery = recovery_for_report(report)

    return {

        "ok": True,

        "data": {

            "received": len(report.get("failures", [])),

            "instructions": recovery,

            "message": recovery[0].get("suggestion") if recovery else "Report recorded.",

        },

        "error": None,

    }





@app.get("/v1/reports")

async def list_reports(siteId: str | None = None):

    data = _selector_reports

    if siteId:

        data = [r for r in data if r.get("siteId") == siteId]

    return {"ok": True, "data": data, "error": None, "count": len(data)}




@app.get("/v1/reports/export")

async def export_reports(siteId: str | None = None):

    """Export accumulated broken-selector reports for nina-generate --heal-from."""

    data = _selector_reports

    if siteId:

        data = [r for r in data if r.get("siteId") == siteId]

    return {

        "ok": True,

        "data": data,

        "error": None,

        "hint": (

            "Save this JSON and run: "

            "nina-generate <config-dir> --heal-from reports.json"

        ),

    }





@app.get("/products")

async def products():

    return PRODUCTS





app.mount("/sdk", StaticFiles(directory=SDK_DIR), name="nina-sdk")

if BLANK_DIR.exists():

    app.mount("/blank", StaticFiles(directory=BLANK_DIR, html=True), name="blank-site")

app.mount("/", StaticFiles(directory=PUBLIC_DIR, html=True), name="static")


