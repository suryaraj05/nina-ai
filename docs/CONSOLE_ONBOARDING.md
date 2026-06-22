# NINA Console onboarding

NINA Console is a hosted control plane for hybrid deployments:

- Console manages orgs, sites, API keys, onboarding, GEO/SEO tools
- Merchant infrastructure continues serving `/v1/query`
- Shopper traffic and business APIs stay on merchant systems

## Run Console locally

```powershell
nina-console --host 127.0.0.1 --port 8787
```

## Core APIs

- `POST /v1/orgs` — create organization
- `POST /v1/sites` — register merchant site
- `POST /v1/keys/issue` — issue `pk_*` or `sk_*` key
- `POST /v1/keys/verify` — verify publishable key (used by merchant backend)
- `POST /v1/tokens/cli` — issue `nk_*` CLI token

## Business wizard (10 steps)

`GET /v1/wizard/steps` returns the canonical onboarding steps:

1. Welcome
2. Your store
3. Capabilities
4. Connect APIs
5. Verify domain
6. Build contract
7. Review actions
8. Install NINA
9. Test sandbox
10. Go live

### Download onboarding pack (no manual YAML)

`POST /v1/wizard/onboarding-pack` returns a `.zip` containing:

- `nina.site.yaml`
- `api.manifest.yaml` (ecommerce template from selected capabilities)
- `sitemap.xml` (fetched from URL, or minimal generated fallback)
- `auth.policy.yaml` / `risk.policy.yaml` (optional)
- `README.txt` with next steps

Use the **Download onboarding pack** section in the Console UI at `http://127.0.0.1:8787/`.

Supporting endpoints:

- `POST /v1/wizard/init`
- `POST /v1/wizard/connect-apis`
- `POST /v1/wizard/generate-contract`
- `POST /v1/wizard/validate-contract`

## Developer workspace

- `GET /v1/developer/files` — load `nina.site.yaml`, `api.manifest.yaml`, policy files
- `POST /v1/developer/files` — save one config file
- `POST /v1/webhooks/broken-selector` — ingest selector failures

## Registrar + GEO

- `POST /v1/registrar/verify-domain` with method `dns_txt | html_meta | well_known`
- `POST /v1/registrar/export-nina-site` to write `nina.site.yaml`

Use site fields:

- `allowedOrigins`
- `locales`
- `markets`
- environment verification status

## SEO toolkit

- `POST /v1/seo/sitemap` — parse uploaded/fetched sitemap and URL coverage
- `POST /v1/seo/embed-health` — check bootstrap script and `agent.json` presence

## Merchant connector

Use `NinaConnector` to mount a drop-in hybrid router:

```python
from fastapi import FastAPI
from nina import Nina, NinaConnector

app = FastAPI()
nina = Nina()

connector = NinaConnector(
    nina=nina,
    contract_path="public/agent.json",
    sdk_dir="sdk",
    static_dir="public",
)
connector.mount(app)
```

Key validation options:

- local dev: `NINA_API_KEY`
- hosted console verify:
  - `NINA_CONSOLE_VERIFY_URL`
  - `NINA_CONSOLE_SECRET_KEY`

