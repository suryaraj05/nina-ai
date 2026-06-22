"""CLI: nina generate <config-dir>"""

from __future__ import annotations

import argparse
import json
import sys
from pathlib import Path

from nina.generator.pipeline import run_pipeline


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(prog="nina-generate", description="Generate agent.json from site config")
    parser.add_argument("config_dir", type=Path, help="Directory with nina.site.yaml and sitemap.xml")
    parser.add_argument("--dry-run", action="store_true", help="Validate without writing agent.json")
    parser.add_argument("--heal-from", type=Path, help="JSON file of broken-selector reports")
    parser.add_argument(
        "--heal-only",
        action="store_true",
        help="Patch existing dist/agent.json from reports (no full regen)",
    )
    parser.add_argument(
        "--fetch-reports",
        type=str,
        help="Pull reports from a running API (GET /v1/reports) before healing",
    )
    parser.add_argument("--site-id", type=str, help="Filter fetched reports by siteId")
    parser.add_argument("--json", action="store_true", help="Print contract JSON to stdout")
    parser.add_argument(
        "--strict",
        action="store_true",
        default=True,
        help="Fail if generated contract is not executable (default: true)",
    )
    parser.add_argument(
        "--no-strict",
        action="store_false",
        dest="strict",
        help="Allow publish even when executable validation fails",
    )
    parser.add_argument(
        "--probe",
        action="store_true",
        help="Probe server API endpoints during strict validation",
    )
    args = parser.parse_args(argv)

    result = run_pipeline(
        args.config_dir,
        dry_run=args.dry_run,
        heal_from=args.heal_from,
        heal_only=args.heal_only,
        fetch_reports_url=args.fetch_reports,
        site_id=args.site_id,
        strict=args.strict,
        probe=args.probe,
    )

    if args.json and result.contract:
        print(json.dumps(result.contract, indent=2))

    if result.stats:
        print("Stats:", json.dumps(result.stats), file=sys.stderr)

    if result.errors:
        for err in result.errors:
            print(f"error: {err}", file=sys.stderr)

    if result.output_path:
        print(f"Wrote {result.output_path}", file=sys.stderr)
        diff_path = result.output_path.parent / "agent.review.diff"
        if diff_path.exists():
            print(f"Review diff: {diff_path}", file=sys.stderr)
        routes_path = result.output_path.parent / "routes.manifest.json"
        if routes_path.exists():
            print(f"Routes manifest: {routes_path}", file=sys.stderr)
        heal_path = result.output_path.parent / "agent.heal.json"
        if heal_path.exists():
            print(f"Heal log: {heal_path}", file=sys.stderr)

    if result.heal_log:
        patched = sum(1 for h in result.heal_log if h.get("status") == "patched")
        print(f"Heal: {patched} patched, {len(result.heal_log)} total", file=sys.stderr)

    return 0 if result.ok else 1


if __name__ == "__main__":
    raise SystemExit(main())
