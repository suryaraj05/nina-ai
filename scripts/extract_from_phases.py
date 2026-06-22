"""Extract code blocks from nina-prod phase*.txt exports into the repo tree."""
from __future__ import annotations

import re
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
PHASE_DIR = ROOT.parent / "nina-prod"

# Map markdown headers to destination paths (relative to repo root).
HEADER_MAP = {
    "pyproject.toml": "pyproject.toml",
    "README.md": "README.md",
    "src/nina/errors.py": "src/nina/errors.py",
    "src/nina/prompt.py": "src/nina/prompt.py",
    "src/nina/init.py": "src/nina/init.py",
    "src/nina/registry.py": "src/nina/registry.py",
    "src/nina/session.py": "src/nina/session.py",
    "src/nina/intent.py": "src/nina/intent.py",
    "src/nina/reasoner.py": "src/nina/reasoner.py",
    "src/nina/executor.py": "src/nina/executor.py",
    "src/nina/responder.py": "src/nina/responder.py",
    "src/nina/chat.py": "src/nina/chat.py",
    "src/nina/__init__.py": "src/nina/__init__.py",
    "src/nina/cli.py": "src/nina/cli.py",
    "src/nina/__main__.py": "src/nina/__main__.py",
    "src/nina/types.py": "src/nina/types.py",
    "src/nina/voice/__init__.py": "src/nina/voice/__init__.py",
    "src/nina/voice/adapter.py": "src/nina/voice/adapter.py",
    "src/nina/voice/providers/__init__.py": "src/nina/voice/providers/__init__.py",
    "src/nina/voice/providers/deepgram.py": "src/nina/voice/providers/deepgram.py",
    "src/nina/voice/providers/elevenlabs.py": "src/nina/voice/providers/elevenlabs.py",
    "src/nina/voice/providers/whisper.py": "src/nina/voice/providers/whisper.py",
    "src/nina/voice/session.py": "src/nina/voice/session.py",
    "src/nina/voice/config.py": "src/nina/voice/config.py",
    "tests/test_voice.py": "tests/test_voice.py",
    "tests/test_developer_experience.py": "tests/test_developer_experience.py",
    "examples/ecommerce-fastapi/store.py": "examples/ecommerce-fastapi/store.py",
    "examples/ecommerce-fastapi/actions.py": "examples/ecommerce-fastapi/actions.py",
    "examples/ecommerce-fastapi/main.py": "examples/ecommerce-fastapi/main.py",
    "examples/ecommerce-fastapi/public/index.html": "examples/ecommerce-fastapi/public/index.html",
    "examples/ecommerce-fastapi/requirements.txt": "examples/ecommerce-fastapi/requirements.txt",
    "examples/ecommerce-fastapi/README.md": "examples/ecommerce-fastapi/README.md",
    "examples/ecommerce-fastapi/voice_endpoint.py": "examples/ecommerce-fastapi/voice_endpoint.py",
    "examples/legacy-flask/app.py": "examples/legacy-flask/app.py",
    "examples/legacy-flask/templates/index.html": "examples/legacy-flask/templates/index.html",
    "examples/legacy-flask/requirements.txt": "examples/legacy-flask/requirements.txt",
    "examples/legacy-flask/README.md": "examples/legacy-flask/README.md",
}

HEADER_RE = re.compile(r"^\*\*(.+?)\*\*\s*(?:\([^)]*\))?\s*$", re.MULTILINE)
FENCE_RE = re.compile(r"```(\w*)\n(.*?)```", re.DOTALL)
STOP_RE = re.compile(r"={3,}it has stopped here only={3,}", re.IGNORECASE)


def normalize_header(header: str) -> str | None:
    h = header.strip()
    if h in HEADER_MAP:
        return HEADER_MAP[h]
    for key, dest in HEADER_MAP.items():
        if key in h or h.endswith(key.split("/")[-1]):
            if "/" in key and key.split("/")[-1] in h:
                return dest
    # examples/... paths embedded in header
    for prefix in ("examples/", "tests/", "src/"):
        idx = h.find(prefix)
        if idx != -1:
            candidate = h[idx:].split()[0].rstrip(")")
            if candidate in HEADER_MAP.values() or candidate in HEADER_MAP:
                return HEADER_MAP.get(candidate, candidate)
    return None


def extract_file(path: Path) -> dict[str, str]:
    text = path.read_text(encoding="utf-8")
    text = STOP_RE.split(text)[0]
    found: dict[str, str] = {}
    headers = list(HEADER_RE.finditer(text))
    for i, match in enumerate(headers):
        dest = normalize_header(match.group(1))
        if not dest:
            continue
        start = match.end()
        end = headers[i + 1].start() if i + 1 < len(headers) else len(text)
        chunk = text[start:end]
        for fence in FENCE_RE.finditer(chunk):
            lang, body = fence.group(1), fence.group(2)
            if lang in ("python", "toml", "html", "markdown", "txt", ""):
                if body.strip():
                    found[dest] = body.rstrip() + "\n"
                    break
    return found


def main() -> None:
    merged: dict[str, str] = {}
    for phase in sorted(PHASE_DIR.glob("phase[0-9].txt")):
        for dest, content in extract_file(phase).items():
            merged[dest] = content  # later phases override
    for dest, content in merged.items():
        out = ROOT / dest
        out.parent.mkdir(parents=True, exist_ok=True)
        out.write_text(content, encoding="utf-8")
        print(f"wrote {dest} ({len(content)} bytes)")


if __name__ == "__main__":
    main()
