# NINA — Technical Overview

**Version:** 1.0 | **Audience:** Engineering team | **Last updated:** June 2026

---

## 1. What is NINA?

NINA (Natural Intelligence for Native Actions) is a **multi-tenant AI commerce assistant SaaS**. It embeds into any e-commerce website as a floating chat widget and lets shoppers do things — search products, track orders, apply coupons, check stock — using natural language, without leaving the page.

NINA is not a chatbot that answers FAQs. It is an **action-execution engine**: it reads a merchant's API contract (a structured description of their endpoints), understands what the user wants, calls the right API, and replies in natural language.

**From the shopper's perspective:** type "where is my order #1234?" → NINA calls the merchant's order API → replies "Your order ships tomorrow, tracking: DHL 9876."

**From the merchant's perspective:** paste one `<script>` tag, upload an API manifest → done. No backend changes needed.

---

## 2. Architecture at a glance

```
Browser (shopper)
      │  POST /v1/query   (publishable API key)
      ▼
┌─────────────────────────────────────────────────────┐
│                  NINA Console Server                 │
│                  FastAPI + uvicorn                   │
│                  Port 8787                           │
│                                                      │
│   ┌──────────────┐    ┌────────────────────────┐    │
│   │  ConsoleStore│    │      NinaPool           │    │
│   │  (PostgreSQL)│    │  per-site Nina() cache  │    │
│   └──────────────┘    └────────────────────────┘    │
│          │                      │                    │
│   stores: orgs, sites,          │ each site gets     │
│   api_keys, usage, tokens       │ one Nina() instance│
└─────────────────────────────────────────────────────┘
               │
               ▼
    LLM Provider API
    (Anthropic / OpenAI / Ollama)
               │
               ▼
    Merchant's own API
    (product search, orders, cart, etc.)
```

**Key design principle:** NINA never touches shopper data directly. It orchestrates calls between the LLM and the merchant's existing APIs. The merchant's API is the source of truth for everything.

---

## 3. Core components

### 3.1 Console Server (`src/nina/console_app.py`)

The main FastAPI application. It does two jobs:

**Job 1 — Control plane (admin routes `/v1/*`):** Merchant onboarding, API key management, site configuration, billing. Protected by `NINA_CONSOLE_ADMIN_SECRET`.

**Job 2 — Query plane (`POST /v1/query`):** Handles every shopper message in real time. This is the hot path — must be fast.

### 3.2 ConsoleStore / PgStore

The persistent data layer. Two implementations with identical interfaces:

| Store | When used | Persistence |
|---|---|---|
| `ConsoleStore` | `DATABASE_URL` not set (local dev) | JSON file on disk |
| `PgStore` | `DATABASE_URL` set (production) | PostgreSQL via psycopg2 |

The six data entities stored:

| Entity | Description |
|---|---|
| `orgs` | Merchant organization (company) |
| `sites` | One website per merchant. Holds contract, LLM config, plan. |
| `api_keys` | Publishable (`pk_`) and secret (`sk_`) keys per site |
| `cli_tokens` | Long-lived tokens for the `nina-scan` CLI tool |
| `usage` | Monthly query count per site, resets each billing period |
| `webhook_events` | Inbound events (e.g. broken DOM selectors), capped at 500 |

### 3.3 NinaPool (`src/nina/pool.py`)

A per-site cache of initialized `Nina()` instances. Creating a `Nina()` is expensive (connects to LLM provider, loads config). The pool keeps one instance per site, initialized once, reused for every query.

**LRU eviction:** When the pool exceeds 100 sites (configurable via `NINA_POOL_MAX_SITES`), the least recently queried site is evicted. It will be re-initialized on its next request.

**Circuit breaker:** After 3 consecutive LLM infrastructure failures for a site (bad API key, provider unreachable), the circuit opens. For the next 30 seconds, all queries to that site immediately return a `SERVICE_UNAVAILABLE` error without hitting the LLM. This prevents a broken site from consuming rate limits. Only infrastructure failures trip the breaker — user-level errors (blocked intent, quota exceeded) do not.

**Per-site lock:** Each site has its own `asyncio.Lock`. Concurrent requests to the same site are serialized. This prevents race conditions when injecting per-request context (contract, session hints) into the shared `Nina()` instance.

### 3.4 Nina() instance (`src/nina/__init__.py`, `src/nina/chat.py`)

The core AI engine. Each instance is tied to one merchant site. It holds:
- LLM client connection (Anthropic / OpenAI / Ollama)
- Session store (in-memory dict by default, or Redis)
- Conversation history per session ID
- The agent contract (loaded fresh per request from the site record)

When `nina.chat(message, session_id)` is called:
1. Load session history for `session_id`
2. Send message + history + agent contract to the LLM
3. LLM responds with a resolution: `action`, `clarify`, `confirm`, `chitchat`, or `unsupported`
4. If `action`: execute the corresponding API call from the contract
5. Format the API response into natural language
6. Append to session history
7. Return the response envelope

### 3.5 Agent Contract

The contract is the most important concept in NINA. It is a structured JSON document that describes what actions NINA can take on a merchant's site.

```json
{
  "actions": [
    {
      "id": "search_products",
      "description": "Search for products by name, category, or price",
      "endpoint": {
        "method": "GET",
        "url": "https://acme.com/api/products/search",
        "params": { "q": "{query}", "limit": 10 }
      },
      "schema": {
        "query": { "type": "string", "required": true }
      }
    }
  ]
}
```

NINA never makes API calls outside the contract. The contract is the security boundary between NINA and the merchant's backend.

### 3.6 LLM Providers (`src/nina/init.py`)

NINA supports three LLM providers:

| Provider | How it works |
|---|---|
| `anthropic` | Claude API with tool_use for structured JSON resolution |
| `openai` | OpenAI API with function calling |
| `ollama` | Local/remote Ollama with JSON-mode structured output |

The provider is configured per site via `llmConfig`. NINA extracts the intent, action, and parameters from the LLM response using a strict JSON schema (`RESOLUTION_SCHEMA`). If the LLM returns invalid JSON or an unknown resolution type, it is treated as an error.

### 3.7 nina-scan CLI (`src/nina/scanner/`)

A developer tool that merchants run locally on their own API source code. It:
1. Detects the framework (FastAPI, Django, Flask, Express, Laravel, Rails)
2. Scans source files for route definitions using regex
3. Tags each route with a role (`customer`, `admin`, `superadmin`)
4. Generates a `nina-manifest.json` with a SHA-256 checksum
5. Optionally probes each endpoint live (`--verify`)

The manifest is the starting point for building the agent contract. No source code is uploaded — only the route structure.

---

## 4. Query lifecycle (the hot path)

This is what happens every time a shopper sends a message:

```
1. Browser POSTs to /v1/query
   { "message": "track my order", "sessionId": "sid_abc123", "apiKey": "pk_live_..." }

2. Rate limiting check
   → 60 req/min per IP, 200 req/min per API key
   → 429 Too Many Requests if exceeded

3. API key resolution
   → STORE.resolve_key_to_site(apiKey, origin)
   → HMAC-SHA256 digest compared with hmac.compare_digest()
   → Validates origin against site's allowedOrigins list
   → Returns: site record (with contract + sealed LLM config)

4. Quota enforcement
   → STORE.enforce_quota(site_id)
   → Checks usage.calls against plan limit for current billing period
   → 402 Payment Required if over limit

5. LLM config decryption
   → unseal_llm_config(site["llmConfig"])
   → Fernet AES-128 decryption using NINA_ENCRYPT_KEY
   → Plaintext config exists only in memory, never logged

6. NinaPool.run(site_id, llm_config, contract, message, session_id)
   → Circuit breaker check (returns error immediately if open)
   → Get-or-create Nina() instance for site_id
   → Inject contract into Nina._core.config under per-site lock
   → nina.chat(message, session_id) → LLM call → action execution
   → Returns response envelope

7. Usage recording
   → STORE.record_usage(site_id)
   → Increments usage.calls for current billing period (YYYYMM)

8. Metrics + logging
   → METRICS.record(ok=..., latency_ms=...)
   → logger.info(JSON log line with method, path, status, duration_ms, site_id)

9. Response returned to browser
   { "ok": true, "data": { "naturalLanguageResponse": "Your order ships tomorrow..." } }
```

**Typical latency:** 800ms–3s (dominated by LLM call). Steps 1–5 and 7–9 add under 5ms.

---

## 5. Multi-tenancy

Every merchant is completely isolated at every layer:

| Layer | Isolation mechanism |
|---|---|
| Database | Each site has its own row; `org_id` foreign key enforces ownership |
| API keys | Keys are HMAC-SHA256 hashed; raw key never stored |
| LLM config | Encrypted with Fernet; decrypted only at query time |
| Nina() instance | Separate object per site in NinaPool |
| Session history | Keyed by `session_id`; no cross-site session access possible |
| Contract | Injected per-request from the site's own DB record |
| Origin validation | Each site has an `allowedOrigins` allowlist; requests from other origins are rejected |

A compromise of one merchant's API key cannot access another merchant's data.

---

## 6. Security model

### API keys
- Generated with `secrets.token_urlsafe(32)` (256-bit entropy)
- Stored only as `HMAC-SHA256(secret + raw_key)` — the raw key is returned once at issuance and never stored
- All comparisons use `hmac.compare_digest()` to prevent timing attacks
- Two types: `pk_` (publishable, browser-safe) and `sk_` (secret, server-only)
- Can be revoked via `POST /v1/keys/{key_id}/revoke`

### LLM API keys (merchant's keys)
- Encrypted at rest with Fernet symmetric encryption (AES-128-CBC + HMAC-SHA256)
- Encryption key: `NINA_ENCRYPT_KEY` env var (never committed to code)
- Decrypted only in memory at query time; plaintext never logged or persisted

### Admin routes
- All `/v1/*` routes (except `/v1/query` and `/v1/auth/*`) require `Authorization: Bearer <NINA_CONSOLE_ADMIN_SECRET>`
- Compared with `hmac.compare_digest()` to prevent timing attacks
- When `NINA_CONSOLE_ADMIN_SECRET` is not set: dev mode (no auth required, warns loudly)

### Rate limiting
- In-process sliding window counter
- 60 requests/min per IP (reads `X-Forwarded-For`)
- 200 requests/min per API key

### Input validation
- **SSRF guard:** Any user-supplied URL validated against a blocklist of private IP ranges (10.x, 172.16-31.x, 192.168.x, 169.254.x, loopback). Non-HTTP/S schemes rejected.
- **Path traversal guard:** Local file paths blocked from reading `/etc/`, `/proc/`, `/sys/`, `/root/`, `/boot/`, `/dev/`
- **Widget XSS:** LLM output never goes to `innerHTML`. Only `textContent` is used.
- **Widget fetch:** Cross-origin fetch instructions from the LLM are silently dropped. Only same-origin requests allowed.
- **Session IDs:** Generated with `crypto.getRandomValues()` (128-bit). `Math.random()` is banned.

### CORS
- `allow_origins=["*"]` (required for the widget to load from any merchant domain)
- Methods restricted to GET, POST, PUT, PATCH
- `Authorization` header allowed (for the admin console)

---

## 7. Data model

### PostgreSQL tables

```
nina_orgs
  id TEXT PK
  name TEXT
  owner_email TEXT
  dashboard_token_digest TEXT   ← HMAC of merchant's dashboard token
  dashboard_token_prefix TEXT   ← first 16 chars for recognition
  created_at TEXT

nina_sites
  id TEXT PK
  org_id TEXT FK → nina_orgs
  name TEXT
  base_url TEXT
  plan TEXT                     ← free|starter|growth|scale|enterprise
  currency TEXT
  locales TEXT (JSON array)
  markets TEXT (JSON array)
  allowed_origins TEXT (JSON array)
  verification TEXT (JSON object)
  agent_contract TEXT (JSON)    ← the full action contract
  llm_config TEXT (JSON)        ← sealed (encrypted) LLM config
  wa_number_id TEXT             ← WhatsApp business number ID (optional)
  created_at TEXT

nina_api_keys
  id TEXT PK
  site_id TEXT FK → nina_sites
  environment TEXT              ← test|live
  kind TEXT                     ← pk|sk
  prefix TEXT                   ← first 14 chars (for display)
  digest TEXT                   ← HMAC-SHA256 of full key
  revoked BOOLEAN
  created_at TEXT

nina_cli_tokens
  id TEXT PK
  org_id TEXT FK → nina_orgs
  label TEXT
  digest TEXT
  prefix TEXT
  revoked BOOLEAN
  created_at TEXT

nina_usage
  site_id TEXT PK FK → nina_sites
  calls INTEGER
  last_call_at TEXT
  period TEXT                   ← YYYYMM, e.g. "202601" — resets monthly

nina_webhook_events
  id SERIAL PK
  event_type TEXT
  payload TEXT (JSON)
  received_at TEXT
```

### Plan limits

| Plan | Monthly queries | Price |
|---|---|---|
| free | 5,000 | ₹0 |
| starter | 30,000 | ₹799/month |
| growth | 75,000 | ₹1,999/month |
| scale | 200,000 | ₹5,999/month |
| enterprise | unlimited | custom |

Quota resets on the 1st of each UTC month. `usage.period` stores `YYYYMM`; if the current month differs, calls reset to 0 before counting.

---

## 8. Key management flows

### Merchant onboarding (wizard flow)

```
POST /v1/wizard/init
  → create_org() → returns dashboardToken (ONCE, never stored in plaintext)
  → create_site() → returns site_id
  → issue_api_key(kind="pk", env="live") → returns pk_live_...
  → issue_api_key(kind="sk", env="live") → returns sk_live_...
```

The dashboard token is the merchant's credential to access their own dashboard. It is returned once and must be saved by the merchant. If lost, an operator can rotate it via `POST /v1/auth/rotate-token` (requires admin secret).

### Key resolution (query flow)

```
raw_key → HMAC-SHA256(NINA_CONSOLE_KEY_HASH_SECRET + raw_key)
        → compare_digest() against every pk_ digest in DB
        → if match: return site record
        → if no match: 401 Unauthorized
```

The key hash secret (`NINA_CONSOLE_KEY_HASH_SECRET`) must never change after keys are issued. Changing it invalidates all existing keys.

---

## 9. Channels

### Web widget (`src/nina/sdk/nina-bootstrap.js`)

Vanilla JS, zero dependencies, ~3KB. Loaded via a `<script>` tag on the merchant's site. Creates a floating chat panel. Communicates with `/v1/query` using the publishable key.

Session IDs are generated with `crypto.getRandomValues()` (128-bit) and stored in `sessionStorage` (cleared when tab closes).

### WhatsApp (`POST /v1/channels/whatsapp/webhook`)

Receives messages from the WhatsApp Cloud API via a Meta webhook. Looks up the site by `waNumberId`, routes through `NinaPool.run()`, sends the reply via the WhatsApp API. The merchant configures their WhatsApp number via `PUT /v1/sites/{id}/whatsapp`.

### Razorpay billing (`POST /v1/billing/razorpay/webhook`)

Receives subscription events (`subscription.activated`, `subscription.charged`, `subscription.cancelled`). Validates the HMAC-SHA256 signature using `NINA_RAZORPAY_WEBHOOK_SECRET`. Automatically upgrades or downgrades the site's plan.

---

## 10. Monitoring and reliability

### Structured logging

Every HTTP request logs a JSON line:
```json
{
  "time": 1750000000,
  "level": "INFO",
  "method": "POST",
  "path": "/v1/query",
  "status": 200,
  "duration_ms": 1240,
  "ip": "103.x.x.x"
}
```

### In-process metrics (`GET /v1/metrics`)

Tracks P50/P95 latency, total queries, quota exceeded count, rate limited count. Reset on server restart. For production dashboards, forward logs to Datadog/Grafana.

### Sentry

Set `SENTRY_DSN` env var to enable automatic error capture. Unhandled exceptions, 5xx responses, and LLM timeouts are captured with full stack traces.

### Health endpoint (`GET /health`)

```json
{
  "ok": true,
  "service": "nina-console",
  "store": { "orgs": 12, "sites": 34, "keys": 67, "backend": "postgresql" },
  "pool": { "cached": 12, "max": 100, "circuits_open": 0 }
}
```

Use this for Render health checks and uptime monitoring.

---

## 11. Environment variables reference

| Variable | Required | Description |
|---|---|---|
| `DATABASE_URL` | Production | PostgreSQL connection string. If unset, uses JSON file store. |
| `NINA_CONSOLE_KEY_HASH_SECRET` | Yes | HMAC secret for hashing API keys. Never change after first use. |
| `NINA_CONSOLE_ADMIN_SECRET` | Yes | Bearer token for all admin `/v1/*` routes. |
| `NINA_ENCRYPT_KEY` | Yes | Fernet key for encrypting merchant LLM API keys at rest. |
| `NINA_DEFAULT_LLM_CONFIG` | Optional | Sealed JSON config for free-tier merchants with no own LLM key. |
| `NINA_LLM_TIMEOUT_SECONDS` | Optional | LLM request timeout (default: 20s). |
| `NINA_POOL_MAX_SITES` | Optional | Max cached Nina() instances (default: 100). |
| `NINA_CIRCUIT_TRIP_AFTER` | Optional | Failures before circuit opens (default: 3). |
| `NINA_CIRCUIT_OPEN_SECONDS` | Optional | Seconds circuit stays open (default: 30). |
| `NINA_REDIS_URL` | Optional | Redis URL for persistent session store across workers. |
| `NINA_WHATSAPP_VERIFY_TOKEN` | Optional | Meta webhook verification token. |
| `NINA_WHATSAPP_API_KEY` | Optional | WhatsApp Cloud API Bearer token for sending replies. |
| `NINA_RAZORPAY_WEBHOOK_SECRET` | Optional | Razorpay webhook HMAC secret. |
| `SENTRY_DSN` | Optional | Sentry DSN for error tracking. |
| `UVICORN_WORKERS` | Optional | Number of uvicorn workers (default: 1; safe to increase with DATABASE_URL set). |

---

## 12. Repository structure

```
nina/
├── src/nina/
│   ├── console_app.py        ← Main FastAPI app (1400+ lines)
│   ├── pool.py               ← NinaPool: LRU cache + circuit breaker
│   ├── pg_store.py           ← PostgreSQL-backed store
│   ├── plans.py              ← Plan limits + billing period helper
│   ├── crypto.py             ← Fernet encrypt/decrypt for LLM keys
│   ├── init.py               ← Nina() initialization, LLM provider setup
│   ├── chat.py               ← Conversation handling
│   ├── contract.py           ← Agent contract parsing
│   ├── intent.py             ← Intent classification
│   ├── executor.py           ← API call execution
│   ├── session.py            ← Session history management
│   ├── redis_store.py        ← Optional Redis session backend
│   ├── scanner/              ← nina-scan CLI
│   │   ├── cli.py            ← Entry point (nina-scan command)
│   │   ├── detector.py       ← Framework auto-detection
│   │   ├── manifest.py       ← Manifest builder + SHA-256 signer
│   │   ├── verifier.py       ← Live endpoint prober
│   │   └── scanners/         ← Per-framework route scanners
│   │       ├── fastapi_scanner.py
│   │       ├── express_scanner.py
│   │       ├── django_scanner.py
│   │       ├── flask_scanner.py
│   │       ├── laravel_scanner.py
│   │       └── rails_scanner.py
│   ├── generator/            ← Contract generator pipeline
│   └── sdk/
│       └── nina-bootstrap.js ← Browser widget (vanilla JS)
├── scripts/
│   ├── db_init.sql           ← PostgreSQL schema
│   └── migrate_json_to_pg.py ← One-time migration script
├── legal/
│   ├── PRIVACY_POLICY.md
│   ├── TERMS_OF_SERVICE.md
│   ├── DATA_PROCESSING_AGREEMENT.md
│   ├── DATA_RETENTION_POLICY.md
│   └── SOC2_ROADMAP.md
├── Dockerfile
└── pyproject.toml
```

---

## 13. How to run locally

```bash
# 1. Install dependencies
pip install -e ".[dev]" && pip install uvicorn[standard] cryptography redis psycopg2-binary

# 2. Generate secrets (one time)
python -c "import secrets; print(secrets.token_hex(32))"  # KEY_HASH_SECRET
python -c "from cryptography.fernet import Fernet; print(Fernet.generate_key().decode())"  # FERNET_KEY

# 3. Set env vars
export NINA_CONSOLE_KEY_HASH_SECRET=<from above>
export NINA_ENCRYPT_KEY=<from above>
export NINA_CONSOLE_ADMIN_SECRET=localdev

# 4. Start the server (JSON file store, no DB needed for local)
python -m uvicorn nina.console_app:app --host 0.0.0.0 --port 8787 --reload

# 5. Open the console UI
# http://localhost:8787/
```

---

## 14. Key design decisions and why

| Decision | Why |
|---|---|
| Single server process in dev | ConsoleStore is in-memory; multiple workers each have divergent state. PostgreSQL mode enables multiple workers. |
| Per-site asyncio.Lock in NinaPool | Concurrent requests to the same site would race on `nina._core.config`. The lock serializes them. |
| HMAC for key storage (not bcrypt) | Keys are looked up on every query (hot path). HMAC is O(1) with a fixed secret; bcrypt is deliberately slow (designed for passwords, not API keys). |
| Fernet for LLM key encryption | Symmetric encryption is sufficient here — the server both encrypts and decrypts. AES-128-CBC + HMAC-SHA256 is the Fernet standard. |
| `hmac.compare_digest()` everywhere | Prevents timing attacks where an attacker can infer partial key matches from response latency differences. |
| `allow_origins=["*"]` in CORS | The widget loads on any merchant domain. We can't enumerate all merchant domains in advance. The publishable key + origin validation per site enforces real access control. |
| Quota period stored as `YYYYMM` | Simpler than computing elapsed seconds. Natural month boundaries. PostgreSQL `CASE WHEN period = current_period THEN calls+1 ELSE 1 END` is atomic. |
