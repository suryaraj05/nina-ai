# NINA — Flask legacy demo

This demo exists to prove **legacy system compatibility**: NINA embedded in a
plain synchronous Flask app, no async framework anywhere in the host code.
The catalogue and all 8 actions are imported from the FastAPI example (DRY) —
the only new code is the synchronous bridge.

> Why not `asyncio.run()` per request? NINA's LLM client is bound to the
> event loop it was initialized on. `app.py` therefore runs one persistent
> loop in a background daemon thread and submits NINA coroutines to it via
> `run_coroutine_threadsafe`. Flask handlers remain fully synchronous.

## Setup (5 steps)

1. `cd examples/legacy-flask`
2. `python -m venv .venv && source .venv/bin/activate`
3. `pip install -r requirements.txt`   *(installs `nina-sdk` via `-e ../../`)*
4. `export ANTHROPIC_API_KEY=sk-ant-...`
5. `python app.py` → open <http://localhost:5000>

## Example conversation flows

1. **Direct search** — "show me sweatshirts"
2. **Season reasoning** — "what should I wear for summer?"
3. **Add to cart** — "add the linen shirt to my cart"
4. **Confirmation** — "empty my cart" → Yes/No buttons → "yes"
5. **Pronoun reference** — "show me hoodies" then "add the second one to cart"
