"""Write agent.json and review artifacts to output directory."""

from __future__ import annotations

import json
from pathlib import Path
from typing import Any

from nina.generator.diff import load_previous_contract, write_review_diff


def publish_contract(
    contract: dict[str, Any],
    output_dir: Path,
    *,
    routes_manifest: dict[str, Any] | None = None,
) -> Path:
    """Write agent.json (and optional routes.manifest.json); return agent path."""
    output_dir.mkdir(parents=True, exist_ok=True)
    out = output_dir / "agent.json"
    previous = load_previous_contract(out)
    with out.open("w", encoding="utf-8") as f:
        json.dump(contract, f, indent=2, ensure_ascii=False)
        f.write("\n")
    write_review_diff(output_dir, previous, contract)
    if routes_manifest:
        routes_path = output_dir / "routes.manifest.json"
        with routes_path.open("w", encoding="utf-8") as f:
            json.dump(routes_manifest, f, indent=2, ensure_ascii=False)
            f.write("\n")
    return out
