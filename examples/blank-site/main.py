"""Minimal NINA host — API-first contract (server runtime + optional DOM UI sync)."""
import os
import sys
from contextlib import asynccontextmanager
from pathlib import Path
from typing import Any

ROOT = Path(__file__).resolve().parents[2]
sys.path.insert(0, str(ROOT / "src"))

from fastapi import FastAPI, Header, Request
from fastapi.middleware.cors import CORSMiddleware
from fastapi.responses import JSONResponse
from fastapi.staticfiles import StaticFiles
from pydantic import BaseModel

from nina import Nina
from nina.api_security import RateLimiter, verify_api_key
from nina.contract import load_agent
from nina.contract_registry import register_from_contract
from nina.instructions import turn_to_instructions

PUBLIC = Path(__file__).resolve().parent / "public"
SDK = ROOT / "sdk"
AGENT_PATH = PUBLIC / "agent.json"

nina = Nina()
_contract = load_agent(AGENT_PATH)
_limiter = RateLimiter()

_DOCS = [
    {"id": "about", "title": "About", "snippet": "Contract-only NINA integration example."},
    {"id": "contact", "title": "Contact", "snippet": "support@example.com"},
    {"id": "api", "title": "API-first", "snippet": "Actions run via declared REST endpoints."},
]


class QueryIn(BaseModel):
    message: str = ""
    transcript: str = ""
    sessionId: str
    page_context: dict[str, Any] | None = None
    session_hints: dict[str, Any] | None = None
    confirmed: bool = False
    replayQueued: bool = False


class SearchIn(BaseModel):
    query: str = ""


async def _api_guard(
    request: Request,
    x_nina_api_key: str | None = Header(default=None, alias="X-NINA-API-Key"),
) -> JSONResponse | None:
    ok_key, key_err = verify_api_key(x_nina_api_key)
    if not ok_key:
        return JSONResponse(status_code=401, content={"ok": False, "data": None, "error": key_err})
    client = request.client.host if request.client else "unknown"
    ok_rate, rate_err = _limiter.allow(client)
    if not ok_rate:
        return JSONResponse(status_code=429, content={"ok": False, "data": None, "error": rate_err})
    return None


def _llm():
    return {
        "provider": "ollama",
        "model": os.environ.get("NINA_MODEL", "qwen2.5:7b"),
        "endpoint": os.environ.get("OLLAMA_HOST", "http://localhost:11434"),
        "temperature": 0.2,
    }


def _identity_from_contract(contract: dict[str, Any]) -> dict[str, Any]:
    site = contract.get("site") or {}
    name = site.get("name") or "this store"
    action_ids = [a.get("id") for a in (contract.get("actions") or []) if a.get("id")]
    return {
        "agentName": "NINA",
        "persona": f"A concise shopping assistant for {name}. Act, don't chat.",
        "systemContext": (
            f"Store: {name} ({site.get('baseUrl', '')}). "
            "Always call a contract action for catalog questions — never invent products or categories. "
            "Use list_categories for category lists, search_products for product search. "
            f"Actions: {', '.join(action_ids)}."
        ),
    }


@asynccontextmanager
async def lifespan(app: FastAPI):
    res = await nina.init({
        "llm": _llm(),
        "identity": _identity_from_contract(_contract),
        "behavior": {"confidenceThreshold": 0.65},
    })
    if not res["ok"]:
        raise RuntimeError(res["error"]["message"])
    reg = await register_from_contract(nina, _contract)
    if reg.get("failed"):
        raise RuntimeError(f"Contract registration failed: {reg['failed']}")
    yield


app = FastAPI(lifespan=lifespan)

app.add_middleware(
    CORSMiddleware,
    allow_origins=[
        "http://localhost:3010",
        "http://127.0.0.1:3010",
        "http://localhost:3012",
        "http://127.0.0.1:3012",
    ],
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)


@app.post("/api/search")
async def api_search(body: SearchIn):
    q = (body.query or "").strip().lower()
    results = [
        doc for doc in _DOCS
        if not q or q in doc["title"].lower() or q in doc["snippet"].lower()
    ]
    return {"ok": True, "query": body.query, "results": results, "count": len(results)}


@app.get("/api/sections/{section_id}")
async def api_section(section_id: str):
    for doc in _DOCS:
        if doc["id"] == section_id:
            return {"ok": True, "section": doc}
    return JSONResponse(status_code=404, content={"ok": False, "error": "section_not_found"})


@app.post("/v1/query")
async def query(
    body: QueryIn,
    request: Request,
    x_nina_api_key: str | None = Header(default=None, alias="X-NINA-API-Key"),
):
    blocked = await _api_guard(request, x_nina_api_key)
    if blocked:
        return blocked
    nina._core.config = {
        **(nina._core.config or {}),
        "_agentContract": _contract,
        "_sessionHints": body.session_hints or {},
        "_pageId": (body.page_context or {}).get("pageId"),
        "_sessionAuthenticated": True,
    }
    envelope = await nina.chat(
        body.transcript or body.message,
        body.sessionId,
        replay_queued=body.replayQueued,
    )
    if envelope.get("ok") and envelope.get("data"):
        turn = dict(envelope["data"])
        if turn.get("intent") != "blocked":
            turn["instructions"] = turn_to_instructions(
                _contract,
                turn,
                page_context=body.page_context,
                session_hints=body.session_hints,
                confirmed=body.confirmed,
            )
        envelope = {**envelope, "data": turn}
    return envelope


app.mount("/sdk", StaticFiles(directory=SDK), name="sdk")
app.mount("/", StaticFiles(directory=PUBLIC, html=True), name="static")
