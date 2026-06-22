# NINA — FastAPI ecommerce demo

A reference integration showing NINA as the action layer of an ecommerce
backend. The SDK is installed editable from the repo root — no PyPI needed.

## Setup (5 steps)

1. `cd examples/ecommerce-fastapi`
2. `python -m venv .venv && source .venv/bin/activate`
3. `pip install -r requirements.txt`   *(installs `nina-sdk` via `-e ../../`)*
4. `ollama pull llama3.2` and ensure `ollama serve` is running (default)
   - optional: `export NINA_MODEL=mistral` / `export OLLAMA_HOST=http://localhost:11434`
   - for cloud instead: `export NINA_LLM_PROVIDER=anthropic` and `export ANTHROPIC_API_KEY=...`
5. `uvicorn main:app --reload` → open <http://localhost:8000>

## Example conversation flows

1. **Direct search** — "show me sweatshirts" → `search_products` runs,
   products render as cards.
2. **Season reasoning** — "what should I wear for summer?" → the reasoner
   produces inferred attributes (breathable, cotton, short-sleeve), then
   `search_products` runs with enriched terms. `reasoningUsed` is true on
   the Turn.
3. **Add to cart** — "add the white kurta to my cart" → `add_to_cart` runs,
   the cart renders with the running total.
4. **Confirmation flow** — "checkout" → NINA asks for confirmation
   (Yes/No buttons appear); "yes" places the order and returns an order id.
5. **Pronoun reference** — "show me hoodies" then "add the second one to
   cart" → the reference map resolves "the second one" to a real product id.
