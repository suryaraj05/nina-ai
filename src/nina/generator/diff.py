"""Human-review diff for generated agent.json."""

from __future__ import annotations

import difflib
import json
from pathlib import Path
from typing import Any


def contract_diff_text(
    previous: dict[str, Any],
    current: dict[str, Any],
    *,
    from_label: str = "agent.json (previous)",
    to_label: str = "agent.json (new)",
) -> str:
    """Unified diff between two contract dicts."""
    old_lines = json.dumps(previous, indent=2, ensure_ascii=False).splitlines(keepends=True)
    new_lines = json.dumps(current, indent=2, ensure_ascii=False).splitlines(keepends=True)
    return "".join(
        difflib.unified_diff(old_lines, new_lines, fromfile=from_label, tofile=to_label)
    )


def load_previous_contract(path: Path) -> dict[str, Any] | None:
    if not path.exists():
        return None
    with path.open(encoding="utf-8") as f:
        return json.load(f)


def write_review_diff(
    output_dir: Path,
    previous: dict[str, Any] | None,
    current: dict[str, Any],
) -> Path | None:
    """Write agent.review.diff when a previous contract exists."""
    if previous is None:
        return None
    diff_text = contract_diff_text(previous, current)
    if not diff_text.strip():
        return None
    out = output_dir / "agent.review.diff"
    with out.open("w", encoding="utf-8") as f:
        f.write(diff_text)
    return out
