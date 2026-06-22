# NINA SDK configuration and mapping model

NINA is an embeddable accessibility layer on sites you control. The host website runs unchanged; NINA adds a panel that can execute contract-bound actions on the live DOM.

## File layers

| Layer | Files | Role |
|-------|-------|------|
| Generator inputs | `nina.site.yaml`, `sitemap.xml`, `auth.policy.yaml`, `risk.policy.yaml`, optional `docs/` | Offline discovery and policy |
| Published contract | `agent.json` | Runtime: pages, actions, selectors, execute steps |
| Secrets | API keys in env only | Authenticate SDK → API and LLM |

Schemas live in [`schemas/`](../schemas/).

## Mapping: when to execute what

1. **Browser SDK** sends `transcript`, `page_context` (URL → `pageId`), and lightweight `snapshot`.
2. **LLM** parses intent into `{ intent, params, confidence }` using action descriptions from `agent.json`.
3. **Contract resolver** (`nina.contract`) checks action exists, page availability, auth, risk, and parameters.
4. **Output** is typed `instructions[]` or `run_action` with `execute.steps` expanded to DOM ops.
5. **NinaExecutor** runs steps deterministically; failures POST to `report-broken-selector`.

## Minimum v1 file set

Developer repo:

- `nina.site.yaml`
- `sitemap.xml`
- `auth.policy.yaml` (if account/checkout)
- `risk.policy.yaml`

Generator output:

- `agent.json`

## Embed snippet

```html
<script src="/sdk/nina-bootstrap.js"
        data-site-id="dhaaga-thread"
        data-api="/v1/query"
        data-manifest="/agent.json"
        defer></script>
```

See [`sdk/README.md`](../sdk/README.md) for browser SDK details.
