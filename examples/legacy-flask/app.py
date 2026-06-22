"""Flask legacy demo — NINA on a synchronous, pre-async Python stack.

Note on async bridging: NINA's Anthropic provider holds an httpx.AsyncClient
bound to the event loop it was created on, so calling asyncio.run() per
request (fresh loop each time) would break it. Instead we run one persistent
event loop in a background thread and submit coroutines to it — Flask itself
stays 100% synchronous, which is the point of this demo.
"""
import asyncio
import os
import sys
import threading

from flask import Flask, jsonify, render_template, request

# Reuse the catalogue and actions from the FastAPI example (DRY).
sys.path.insert(0, os.path.join(os.path.dirname(__file__), "..",
                                "ecommerce-fastapi"))
from store import PRODUCTS          # noqa: E402
from actions import build_actions   # noqa: E402
from main import _llm_config        # noqa: E402
from nina import Nina               # noqa: E402

_loop = asyncio.new_event_loop()
threading.Thread(target=_loop.run_forever, daemon=True).start()


def run_async(coro):
    """Synchronous bridge into NINA's async API."""
    return asyncio.run_coroutine_threadsafe(coro, _loop).result(timeout=120)


nina = Nina()
_init = run_async(nina.init({
    "llm": _llm_config(),
    "identity": {
        "agentName": "NINA",
        "persona": "A helpful, concise shopping assistant for an Indian "
                   "clothing store.",
        "systemContext": "Store: Dhaaga & Thread (legacy storefront). All "
                         "prices are in Indian Rupees (INR).",
    },
    "behavior": {"confidenceThreshold": 0.7},
}))
if not _init["ok"]:
    raise RuntimeError(f"NINA init failed: {_init['error']['message']}")
_reg = run_async(nina.register(build_actions()))
if _reg["data"]["failed"]:
    raise RuntimeError(f"Action registration failed: {_reg['data']['failed']}")

app = Flask(__name__)


@app.get("/")
def index():
    return render_template("index.html")


@app.post("/chat")
def chat():
    body = request.get_json(force=True) or {}
    envelope = run_async(nina.chat(body.get("message", ""),
                                   body.get("sessionId", "")))
    return jsonify(envelope)


@app.get("/products")
def products():
    return jsonify(PRODUCTS)


if __name__ == "__main__":
    app.run(port=5000, debug=False)
