"""NINA CLI — `nina init` scaffolds a runnable project in the current directory.

Pure sys.argv parsing, no CLI framework. Never overwrites existing files.
"""
import sys
from pathlib import Path

_NINA_CONFIG = '''"""NINA configuration. Fill in the placeholders, then run:
    uvicorn server:app --reload
"""
import os

CONFIG = {
    "llm": {                                      # REQUIRED
        "provider": "ollama",                     # "ollama" | "anthropic" | "openai" | "custom"
        "model": os.environ.get("NINA_MODEL", "llama3.2"),
        "endpoint": os.environ.get("OLLAMA_HOST", "http://localhost:11434"),
        # Cloud providers (uncomment and switch provider):
        # "provider": "anthropic",
        # "model": "claude-sonnet-4-20250514",
        # "apiKey": os.environ.get("ANTHROPIC_API_KEY", ""),
        # "temperature": 0.2,                   # default 0.2 — action precision
        # "maxTokens": 1024,                      # default 1024
    },
    # "session": {                                # OPTIONAL
    #     "store": "memory",                      # or your {get,set,delete} adapter
    #     "ttlSeconds": 1800,                     # 0 = sessions never expire
    #     "maxTurns": 20,                         # history window per session
    # },
    # "behavior": {                               # OPTIONAL
    #     "confidenceThreshold": 0.75,            # below this NINA asks, not acts
    #     "maxClarifications": 2,                 # per intent
    #     "allowChitchat": True,                  # False -> off-task = "unsupported"
    #     "language": "auto",                     # BCP-47 hint
    # },
    # "identity": {                               # OPTIONAL
    #     "agentName": "NINA",
    #     "persona": "A concise, helpful assistant.",
    #     "systemContext": "Domain facts the LLM treats as ground truth.",
    # },
    # "hooks": {                                  # OPTIONAL — fire-and-observe
    #     "onActionCall": lambda name, inp, sid: None,
    #     "onActionResult": lambda name, result, sid: None,
    #     "onError": lambda err, sid: None,
    # },
    # "debug": True,                              # print a debug block per turn
}
'''

_ACTIONS = '''"""Example NINA actions. Replace the handler bodies with calls into
your own system — the descriptions and schemas are what the LLM routes on.
"""


def search_items(inp, ctx):
    # TODO: replace with a real query against your database or API.
    return {"results": [
        {"id": "item-1", "name": "Example item one", "price": 100},
        {"id": "item-2", "name": "Example item two", "price": 200},
    ], "count": 2}


def get_item_detail(inp, ctx):
    # TODO: replace with a real lookup by id in your system.
    return {"id": inp["itemId"], "name": "Example item",
            "price": 100, "in_stock": True}


def reset_conversation(inp, ctx):
    # TODO: clear any per-session state your handlers keep (carts, drafts...).
    return {"reset": True}


ACTIONS = [
    {
        "name": "search_items",
        "description": (
            "Searches the catalogue by free-text query, matching item names and "
            "attributes, and returns a list of matching items. Use it whenever "
            "the user wants to browse, discover, or look for items. Do not use "
            "it to fetch full details of one already-identified item — that is "
            "what get_item_detail is for."),
        "inputSchema": {
            "type": "object",
            "properties": {
                "query": {"type": "string",
                          "description": "Free-text search terms."},
            },
            "required": ["query"],
        },
        "handler": search_items,
        "examples": ["show me items", "do you have anything for summer?"],
    },
    {
        "name": "get_item_detail",
        "description": (
            "Returns the complete detail of one specific item identified by its "
            "item id, including price and availability. Use it when the user "
            "asks about a single known item, including pronoun references like "
            "'tell me more about the second one'. Do not use it for browsing "
            "multiple items — use search_items for discovery."),
        "inputSchema": {
            "type": "object",
            "properties": {
                "itemId": {"type": "string",
                           "description": "The item id from a prior search "
                                          "result — never invented."},
            },
            "required": ["itemId"],
        },
        "handler": get_item_detail,
        "examples": ["tell me more about the first one"],
    },
    {
        "name": "reset_conversation",
        "description": (
            "Clears the working state of the current conversation so the user "
            "can start over from a clean slate. Use it only when the user "
            "explicitly asks to start over, reset, or begin again. Do not use "
            "it for removing a single thing — it discards everything in "
            "progress for this session."),
        "inputSchema": {"type": "object", "properties": {}, "required": []},
        "handler": reset_conversation,
        "confirmation": True,
        "examples": ["start over", "reset everything"],
    },
]
'''

_SERVER = '''"""Minimal NINA server. Run:  uvicorn server:app --reload"""
from contextlib import asynccontextmanager

from fastapi import FastAPI
from pydantic import BaseModel

from nina import Nina
from nina_config import CONFIG
from actions import ACTIONS

nina = Nina()


@asynccontextmanager
async def lifespan(app: FastAPI):
    res = await nina.init(CONFIG)
    if not res["ok"]:
        raise RuntimeError(f"NINA init failed: {res['error']['message']}")
    reg = await nina.register(ACTIONS)
    if reg["data"]["failed"]:
        raise RuntimeError(f"Registration failed: {reg['data']['failed']}")
    yield


app = FastAPI(lifespan=lifespan)


class ChatIn(BaseModel):
    message: str
    sessionId: str


@app.post("/chat")
async def chat(body: ChatIn):
    # NINA never raises — the envelope is returned as-is.
    return await nina.chat(body.message, body.sessionId)
'''

_ENV = '''# --- Local Ollama (default in nina_config.py) --------------------
OLLAMA_HOST=http://localhost:11434
NINA_MODEL=llama3.2

# --- Cloud LLM (set NINA_LLM_PROVIDER and matching keys) ------------
# NINA_LLM_PROVIDER=anthropic
# ANTHROPIC_API_KEY=sk-ant-...
# OPENAI_API_KEY=sk-...          # if llm.provider is "openai"

# --- Voice layer (optional: pip install "nina-sdk[voice]") ---------
# DEEPGRAM_API_KEY=
# ELEVENLABS_API_KEY=
# ELEVENLABS_VOICE_ID=
'''

SCAFFOLD = {
    "nina_config.py": _NINA_CONFIG,
    "actions.py": _ACTIONS,
    "server.py": _SERVER,
    ".env.example": _ENV,
}


def main(argv=None) -> int:
    args = sys.argv[1:] if argv is None else argv
    if not args or args[0] != "init":
        print("usage: nina init    scaffold a new NINA project here")
        return 1
    created, skipped = [], []
    for filename, content in SCAFFOLD.items():
        path = Path.cwd() / filename
        if path.exists():
            print(f"warning: {filename} already exists - skipped "
                  "(nina init never overwrites)")
            skipped.append(filename)
            continue
        path.write_text(content, encoding="utf-8")
        created.append(filename)
    if created:
        print("\nCreated:")
        for name in created:
            print(f"  {name}")
        print("\nNext:")
        print("  1. cp .env.example .env   # then add your ANTHROPIC_API_KEY")
        print("  2. pip install fastapi uvicorn")
        print("  3. uvicorn server:app --reload")
    elif skipped:
        print("Nothing to do - all scaffold files already exist.")
    return 0


if __name__ == "__main__":
    sys.exit(main())
