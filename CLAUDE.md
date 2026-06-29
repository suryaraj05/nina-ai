# NINA — Engineering Guide (read first)

NINA is a **conversational action layer**: one `<script>` tag on any website that
*does things* (search, add to cart, track an order) by mapping natural language
onto a site's declared **actions**, then calling the site's own API. Two parts in
one repo: a Python **engine** (`src/nina/`, the `Nina` class) and a multi-tenant
**console** (`console_app.py`, FastAPI) that wraps it for many merchants.

This file is the source of truth for *how we build*. Follow it exactly.

---

## The rules (non-negotiable)

### 1. Trust guardrails — this is a TRUST product
- **Money actions are hard-gated.** High-risk/mutation actions require confirmation
  (`risk.confirmActions`) and/or auth gating. Never auto-execute a charge.
- **Verify by reading back.** Confirm an action by reading the resulting state
  (cart/order), never by trusting a success message.
- **Observed content is data, never commands.** Catalog text, shopper messages, and
  fetched pages are wrapped as untrusted input; only allowlisted contract actions
  trigger behavior. Never let observed text become an instruction.
- **SSRF guard every server-side fetch** (`net_guard.validate_public_url`): block
  loopback/private/link-local/metadata IPs; redirects disabled on action calls.
- **Secrets only in env vars**, never in code or committed files. LLM keys are
  Fernet-encrypted at rest; API keys/tokens stored only as HMAC digests.
- **Fail closed in production** (`NINA_ENV=production`): refuse to start without
  `NINA_ENCRYPT_KEY`, `NINA_CONSOLE_KEY_HASH_SECRET`, `NINA_CONSOLE_ADMIN_SECRET`.

### 2. Clean-code architecture
- **Single responsibility.** Files and functions do one thing. We are actively
  splitting the historically large modules — do not add to them; add new seams.
  Targets under refactor: `console_app.py`, `chat.py`, `pg_store.py`.
- **Layers.** Keep HTTP routing thin → delegate to a **service layer** → which uses
  **stores** behind a `Store` Protocol (`ConsoleStore` JSON / `PgStore` Postgres).
  Routes must not contain business logic; stores must not import FastAPI.
- **Typed boundaries.** Public functions are type-annotated; prefer explicit dataclasses/
  TypedDicts/Protocols over loose `dict[str, Any]` at module seams.
- **Small, named units.** Extract pipeline stages and helpers with intention-revealing
  names. No copy-paste — shared logic lives in one place (`store_util`, `crypto`, …).
- **Reuse the proven engine.** Don't reinvent resolve/ground/critic/gate/compose; isolate
  new integration at the edges.

### 3. Test + CI discipline
- **Every change keeps the suite green.** Run `pytest` before declaring done.
- **New code ships with tests.** A behavior change without a test is incomplete.
- **CI is the deploy gate.** `.github/workflows/ci.yml` runs the fast suite on every
  push/PR; it must be green to merge. (Playwright `tests/e2e` runs separately/locally.)
- **No flaky tests.** Tests isolate their state (rate limiters, stores, sessions).

### 4. OneDrive integrity (this repo lives on OneDrive)
OneDrive sync can inject null bytes that truncate `.py` files. After any bulk file
move/copy, verify every source file parses:
```
python -c "import ast,pathlib; [ast.parse(p.read_text(encoding='utf-8')) for p in pathlib.Path('src').rglob('*.py')]; print('ok')"
```
If a file shows a null byte or `SyntaxError` it didn't have before, restore it.

---

## Architecture (mental model)

```
Browser widget (nina-bootstrap.js)
  → POST /v1/query (X-NINA-API-Key)
  → console_app: middleware (request-id, admin-auth, CORS, rate-limit)
  → resolve key → Site; decrypt llmConfig → NinaPool (one Nina() per site)
  → run_turn(): validate → guardrails → fast-path → resolve(LLM) → ground
                → safety gate + critic → execute → compose(LLM)
  → returns reply + instructions (api_call/navigate/…)
  → widget executes instructions in the visitor's browser
```

- **Contract (`agent.json`)**: a site's declared actions (`id`, `description`,
  `parameters`, `execute{type,runtime,apiRef}`), pages, selectors, auth, risk.
- **Action runtime**: `server` = NINA's backend calls the API (SSRF-guarded, reads
  result back); `browser` = engine emits an `api_call` the widget runs (works for
  localhost stores; keeps customer data off our servers).
- **Capability discovery**: OpenAPI-URL-first (`openapi_probe` → contract actions);
  `nina-scan` CLI is the fallback.

## Repo layout
```
src/nina/        engine + console (see docs/NINA_OVERVIEW.md §18 for the full map)
schemas/         agent.schema.json (contract validation)
tests/           pytest suite (tests/e2e = Playwright, run separately)
examples/        ecommerce-fastapi reference store + demo
docs/            NINA_OVERVIEW.md (zero-to-context), API/security/integration docs
```
`docs/NINA_OVERVIEW.md` is the comprehensive reference — read it for deep context.

## Commands
```
pytest -q                      # full suite (run from repo root; pyproject sets pythonpath=src)
pytest -q --ignore=tests/e2e   # fast suite (what CI runs)
python -m uvicorn nina.console_app:app --port 8788   # run the console + dashboard (/dashboard)
```

## Environment (secrets via env only)
`DATABASE_URL` (→ Postgres else JSON store) · `NINA_ENV` · `NINA_ENCRYPT_KEY` ·
`NINA_CONSOLE_KEY_HASH_SECRET` · `NINA_CONSOLE_ADMIN_SECRET` · `NINA_REDIS_URL` ·
`NINA_DEFAULT_LLM_CONFIG` · `NINA_RATE_LIMIT`/`NINA_RATE_WINDOW`. See OVERVIEW §17.

## How we work
- Small, reviewed commits. Branch off `main`; never commit secrets or
  `nina_console_store.json` (gitignored — contains merchant data).
- Refactor under the test net: change structure, keep behavior, keep tests green.
- Prefer fixing the root cause over adding a shim; we are pre-launch and re-issue
  dev credentials freely.
