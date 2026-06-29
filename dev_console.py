"""Dev launcher for the console — guarantees this repo's src/ is imported.

The package may be pip-installed editable from another checkout; inserting our
own src/ at the front of sys.path makes `nina` resolve to THIS repo regardless
of cwd or any editable install. Used by .claude/launch.json (preview).
"""
import pathlib
import sys

sys.path.insert(0, str(pathlib.Path(__file__).resolve().parent / "src"))

import uvicorn  # noqa: E402

if __name__ == "__main__":
    port = int(sys.argv[1]) if len(sys.argv) > 1 else 8788
    uvicorn.run("nina.console_app:app", host="127.0.0.1", port=port)
