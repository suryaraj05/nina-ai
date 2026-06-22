# NINA blank-site example

API-first integration: actions run via declared REST endpoints (`/api/search`, `/api/sections/{id}`). DOM steps are optional UI sync only.

## Run

```powershell
cd nina/examples/blank-site
pip install -e "../../.[dev]"
uvicorn main:app --host 127.0.0.1 --port 8001
```

Open http://127.0.0.1:8001 and try: “search for contact” or “go to about section”.

## Files

- `public/agent.json` — API-first contract (`execute.type: api`, `runtime: server`)
- `public/index.html` — minimal page (no search input required)
- `main.py` — stub APIs + `register_from_contract()` + `turn_to_instructions`
