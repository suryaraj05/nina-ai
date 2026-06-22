# NINA integration guide

## Quick paths

| Goal | Start here |
|------|------------|
| Full demo store | [examples/ecommerce-fastapi](../examples/ecommerce-fastapi/) |
| Contract-only minimal site | [examples/blank-site](../examples/blank-site/) |
| Hosted onboarding/control plane | [CONSOLE_ONBOARDING.md](./CONSOLE_ONBOARDING.md) |
| Python SDK only | [README](../README.md) quickstart |

## Embed snippet

```html
<script src="https://your-host/sdk/nina-bootstrap.js"
        data-site-id="your-site-id"
        data-api="/v1/query"
        data-manifest="/agent.json"
        data-api-key="optional-if-NINA_API_KEY-set"
        defer></script>
```

## API

- `POST /v1/query` — chat + instructions
- Optional header `X-NINA-API-Key` when env `NINA_API_KEY` is set
- Rate limit: `NINA_RATE_LIMIT` per IP per `NINA_RATE_WINDOW` seconds (default 60/min)

### Auth replay

When a gated action requires login, NINA returns `needs_login` with `queuedIntent`. After the user signs in on your site:

1. SDK stores `queuedIntent` in `sessionStorage`
2. On return (cookie present), SDK calls `/v1/query` with `replayQueued: true`
3. Server replays the queued action without asking again

Configure in `agent.json`:

```json
"auth": {
  "loginUrl": "/login.html",
  "sessionIndicator": { "type": "cookie", "name": "your_session_cookie" },
  "gatedActions": ["checkout"]
}
```

## API-first executable contract

Declare what must work in `api.manifest.yaml` (alongside `nina.site.yaml`):

```yaml
apis:
  default:
    baseUrl: https://staging.example.com
actions:
  search:
    method: POST
    path: /api/v1/products/search
    runtime: server
    bodyTemplate: { query: "{query}" }
    parameters:
      query: { type: string, required: true }
```

Onboarding flow:

1. `nina.site.yaml` + `api.manifest.yaml` + `sitemap.xml`
2. `nina-generate contracts/your-site` (merges manifest → api-first `agent.json`)
3. `nina-validate dist/agent.json --executable [--probe]`
4. Embed script + optional `NINA_API_KEY`

| `execute.runtime` | Runs where | Use for |
|-------------------|------------|---------|
| `server` | NINA backend (`httpx`) | Auth, writes, cart/checkout |
| `browser` | Embed `fetch` same-origin | Public search, read-only catalog |
| `dom_only` | Executor | UI feedback only |

Business outcomes must succeed via **server or browser API**; DOM steps are optional UI sync.

`register_from_contract()` in your FastAPI app auto-registers server-runtime actions from `agent.json` (see `blank-site`).

## Contract-only vs hybrid demo

- **API-first** (`blank-site`): `execute.type: api` + `runtime: server`; stub `/api/*` routes; no required DOM selectors
- **Hybrid demo** (`ecommerce-fastapi`): server handlers + optional `demo_instructions.py` for `render_products`, `update_cart`, etc.

Prefer API-first actions from `api.manifest.yaml`; use DOM steps only for cosmetic UI sync.

### Plan resume after login

Multi-step plans that pause for auth (`requiresAuth` on a plan step) set `planResumePending` on the session. After login:

1. SDK stores `planStatus.awaitingAuth` in `sessionStorage`
2. On return, SDK calls `/v1/query` with `replayPlan: true`
3. Server runs the next plan step via `resume_after_auth` + `pending_auto_action`

Schedule plans with `nina.session.schedule_plan(sessionId, steps)`.

## Skills (procedural guidance per action)

A skill is a markdown file with YAML frontmatter that gets injected straight
into the LLM's resolution prompt, next to the action(s) it applies to. Use
it when an action description alone isn't enough to get the LLM to behave
reliably — e.g. how to resolve "add it to cart" to a real product id
instead of guessing one, or when a custom `apply_loyalty_points` action
should fire versus not.

```markdown
---
name: cart-skill
appliesTo: [add_to_cart]
description: How to resolve which product the user means before adding to cart.
fastPath:
  - "add {query} to cart"
  - "add {query} to my cart"
---
- The ONLY valid source for `variantId` is the `id` field on an item from
  `last_search_results` in the reference map — never construct or guess one
  from a product title or slug.
- If the user's reference doesn't match anything in `last_search_results`,
  ask which item they mean instead of guessing.
```

Frontmatter fields:

| Field | Required | Purpose |
|---|---|---|
| `name` | yes | Unique id; a skill with the same `name` as a built-in one overrides it |
| `appliesTo` | yes | Action id(s) this skill's body gets attached to |
| `description` | no | One-line summary (not sent to the LLM; for humans browsing the file) |
| `fastPath` | no | `{param}`-style patterns that bypass the LLM entirely on an exact match — see Dual-path inference below |

Skills load **always-on** (no separate "load this skill" round trip, no
extra LLM call) — the body text is concatenated into the same single-call
resolution prompt the action's description already lives in, so a skill
can't introduce a new way for a turn to fail or stall mid-conversation.

Built-in skills ship in `src/nina/skills/` (`search.md`, `cart.md`,
`checkout.md`). Load your own alongside them:

```python
await nina.init({
    "llm": {...},
    "skillsDir": "contracts/your-site/skills",
})
```

The NINA onboarding pack (`/v1/wizard/onboarding-pack`, `includeSkills: true`
by default) ships a worked example at `skills/loyalty-points.md` you can
copy and rename for your own custom actions.

### Dual-path inference

Most queries don't need full LLM reasoning. NINA tries a fast deterministic
path first — regex-compiled from a skill's `fastPath` patterns plus each
action's own name/examples — and only falls through to the LLM resolution
call on a miss. This keeps ambiguous or multi-step phrasing (e.g. "show me
the dressing I can wear for summer") on the full reasoning path, since
those don't match a `fastPath` pattern exactly.

The fast path never applies to actions listed in `risk.confirmActions` or
`risk.blockActions` — those always go through full resolution (and the
contract safety gate) regardless of phrasing.

## Generator (offline onboarding)

```powershell
nina-generate contracts/examples
nina-validate contracts/examples/dist/agent.json --executable
```

`nina-generate --strict` (default) fails if any action cannot execute without guessed selectors. Use `--no-strict` to skip. Add `--probe` to HEAD-check server API base URLs.

Outputs:

- `dist/agent.json` — site contract (includes `routes` when generated)
- `dist/routes.manifest.json` — SPA route map (also merged at runtime if present)
- `dist/agent.review.diff` — unified diff vs previous `agent.json` for human review

### Heal loop (broken selectors)

```powershell
curl http://127.0.0.1:8000/v1/reports/export -o reports.json
nina-generate contracts/examples --heal-from reports.json
# or fast patch only:
nina-generate contracts/examples --heal-only --heal-from reports.json
```

See [RECOVERY_LOOP.md](RECOVERY_LOOP.md).

Optional Playwright DOM pass (install `pip install -e ".[generator]"` + `playwright install chromium`):

```yaml
# nina.site.yaml
generator:
  crawl:
    usePlaywright: true
    playwrightMaxPages: 10
```
