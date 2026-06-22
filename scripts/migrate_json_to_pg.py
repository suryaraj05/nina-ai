#!/usr/bin/env python3
"""One-time migration: copy nina_console_store.json → PostgreSQL.

Usage:
    DATABASE_URL=postgresql://... python scripts/migrate_json_to_pg.py
    DATABASE_URL=postgresql://... python scripts/migrate_json_to_pg.py --store path/to/nina_console_store.json

The script is idempotent: rows already in PostgreSQL (same primary key) are
skipped with ON CONFLICT DO NOTHING, so it's safe to re-run.

After successful migration, verify counts match then set DATABASE_URL in
your deployment environment. The JSON file is left untouched as a backup.
"""
import json
import os
import sys
from pathlib import Path

try:
    import psycopg2
    import psycopg2.extras
except ImportError:
    print("ERROR: psycopg2 not installed. Run: pip install psycopg2-binary", file=sys.stderr)
    sys.exit(1)

# ── config ────────────────────────────────────────────────────────────────────

DSN = os.environ.get("DATABASE_URL", "")
if not DSN:
    print("ERROR: DATABASE_URL environment variable is not set.", file=sys.stderr)
    sys.exit(1)

DEFAULT_STORE = Path("nina_console_store.json")


def _jd(v) -> str:
    return json.dumps(v, ensure_ascii=False)


def _migrate(store_path: Path) -> None:
    if not store_path.exists():
        print(f"ERROR: {store_path} not found.", file=sys.stderr)
        sys.exit(1)

    print(f"Loading {store_path} ...")
    data = json.loads(store_path.read_text(encoding="utf-8"))
    orgs   = data.get("orgs", {})
    sites  = data.get("sites", {})
    keys   = data.get("api_keys", {})
    tokens = data.get("cli_tokens", {})
    events = data.get("webhook_events", [])
    usage  = data.get("usage", {})

    print(f"  {len(orgs)} orgs, {len(sites)} sites, {len(keys)} keys, "
          f"{len(tokens)} CLI tokens, {len(events)} webhook events, {len(usage)} usage records")

    conn = psycopg2.connect(DSN)
    conn.autocommit = False
    cur = conn.cursor()

    # ── schema ────────────────────────────────────────────────────────────────
    sql_file = Path(__file__).parent / "db_init.sql"
    if sql_file.exists():
        print("Ensuring schema ...")
        cur.execute(sql_file.read_text(encoding="utf-8"))
        conn.commit()

    # ── orgs ──────────────────────────────────────────────────────────────────
    print("Migrating orgs ...")
    inserted_orgs = 0
    for org in orgs.values():
        cur.execute(
            """
            INSERT INTO nina_orgs
                (id, name, owner_email, dashboard_token_digest,
                 dashboard_token_prefix, token_rotated_at, created_at)
            VALUES (%s,%s,%s,%s,%s,%s,%s)
            ON CONFLICT (id) DO NOTHING
            """,
            (
                org["id"],
                org.get("name", ""),
                org.get("ownerEmail"),
                org.get("dashboardTokenDigest"),
                org.get("dashboardTokenPrefix"),
                org.get("tokenRotatedAt"),
                str(org.get("createdAt", 0)),
            ),
        )
        if cur.rowcount:
            inserted_orgs += 1
    conn.commit()
    print(f"  {inserted_orgs}/{len(orgs)} orgs inserted (rest already present)")

    # ── sites ─────────────────────────────────────────────────────────────────
    print("Migrating sites ...")
    inserted_sites = 0
    skipped_sites = 0
    for site in sites.values():
        org_id = site.get("orgId", "")
        # Verify parent org exists in DB
        cur.execute("SELECT 1 FROM nina_orgs WHERE id = %s", (org_id,))
        if not cur.fetchone():
            print(f"  WARNING: site {site['id']} references unknown org {org_id} — skipping")
            skipped_sites += 1
            continue

        contract = site.get("agentContract")
        llm_cfg  = site.get("llmConfig")

        cur.execute(
            """
            INSERT INTO nina_sites
                (id, org_id, name, base_url, plan, currency, locales, markets,
                 allowed_origins, verification, agent_contract, llm_config,
                 wa_number_id, created_at)
            VALUES (%s,%s,%s,%s,%s,%s,%s,%s,%s,%s,%s,%s,%s,%s)
            ON CONFLICT (id) DO NOTHING
            """,
            (
                site["id"],
                org_id,
                site.get("name", ""),
                site.get("baseUrl", ""),
                site.get("plan", "free"),
                site.get("currency", "INR"),
                _jd(site.get("locales", ["en"])),
                _jd(site.get("markets", [])),
                _jd(site.get("allowedOrigins", [])),
                _jd(site.get("verification", {"sandbox": "verified", "production": "pending"})),
                _jd(contract) if contract else None,
                _jd(llm_cfg)  if llm_cfg  else None,
                site.get("waNumberId"),
                str(site.get("createdAt", 0)),
            ),
        )
        if cur.rowcount:
            inserted_sites += 1
    conn.commit()
    print(f"  {inserted_sites}/{len(sites)} sites inserted ({skipped_sites} skipped)")

    # ── api keys ──────────────────────────────────────────────────────────────
    print("Migrating API keys ...")
    inserted_keys = 0
    skipped_keys = 0
    for key in keys.values():
        site_id = key.get("siteId", "")
        cur.execute("SELECT 1 FROM nina_sites WHERE id = %s", (site_id,))
        if not cur.fetchone():
            print(f"  WARNING: key {key['id']} references unknown site {site_id} — skipping")
            skipped_keys += 1
            continue
        cur.execute(
            """
            INSERT INTO nina_api_keys
                (id, site_id, environment, kind, prefix, digest, revoked, created_at)
            VALUES (%s,%s,%s,%s,%s,%s,%s,%s)
            ON CONFLICT (id) DO NOTHING
            """,
            (
                key["id"],
                site_id,
                key.get("environment", "test"),
                key.get("kind", "pk"),
                key.get("prefix", ""),
                key.get("digest", ""),
                bool(key.get("revoked", False)),
                str(key.get("createdAt", 0)),
            ),
        )
        if cur.rowcount:
            inserted_keys += 1
    conn.commit()
    print(f"  {inserted_keys}/{len(keys)} keys inserted ({skipped_keys} skipped)")

    # ── CLI tokens ────────────────────────────────────────────────────────────
    print("Migrating CLI tokens ...")
    inserted_tokens = 0
    for tok in tokens.values():
        org_id = tok.get("orgId", "")
        cur.execute("SELECT 1 FROM nina_orgs WHERE id = %s", (org_id,))
        if not cur.fetchone():
            print(f"  WARNING: token {tok['id']} references unknown org {org_id} — skipping")
            continue
        cur.execute(
            """
            INSERT INTO nina_cli_tokens
                (id, org_id, label, digest, prefix, revoked, created_at)
            VALUES (%s,%s,%s,%s,%s,%s,%s)
            ON CONFLICT (id) DO NOTHING
            """,
            (
                tok["id"],
                org_id,
                tok.get("label", "default"),
                tok.get("digest", ""),
                tok.get("prefix", ""),
                bool(tok.get("revoked", False)),
                str(tok.get("createdAt", 0)),
            ),
        )
        if cur.rowcount:
            inserted_tokens += 1
    conn.commit()
    print(f"  {inserted_tokens}/{len(tokens)} CLI tokens inserted")

    # ── webhook events ────────────────────────────────────────────────────────
    if events:
        print(f"Migrating {len(events)} webhook events ...")
        for ev in events[-500:]:  # keep only the newest 500
            cur.execute(
                "INSERT INTO nina_webhook_events (event_type, payload, received_at) VALUES (%s,%s,%s)",
                (ev.get("type", "unknown"), _jd(ev.get("payload", {})), str(ev.get("receivedAt", 0))),
            )
        conn.commit()
        print(f"  {min(len(events), 500)} webhook events inserted")

    # ── usage ─────────────────────────────────────────────────────────────────
    if usage:
        print("Migrating usage records ...")
        inserted_usage = 0
        for site_id, rec in usage.items():
            cur.execute("SELECT 1 FROM nina_sites WHERE id = %s", (site_id,))
            if not cur.fetchone():
                continue
            cur.execute(
                """
                INSERT INTO nina_usage (site_id, calls, last_call_at, period)
                VALUES (%s, %s, %s, %s)
                ON CONFLICT (site_id) DO UPDATE
                    SET calls        = GREATEST(nina_usage.calls, EXCLUDED.calls),
                        last_call_at = EXCLUDED.last_call_at,
                        period       = EXCLUDED.period
                """,
                (
                    site_id,
                    rec.get("calls", 0),
                    str(rec.get("lastCallAt") or 0),
                    rec.get("period"),  # may be None for pre-migration data; treated as 0 by enforce_quota
                ),
            )
            if cur.rowcount:
                inserted_usage += 1
        conn.commit()
        print(f"  {inserted_usage} usage records upserted")

    cur.close()
    conn.close()

    # ── final verification ────────────────────────────────────────────────────
    conn2 = psycopg2.connect(DSN)
    cur2 = conn2.cursor()
    for table in ("nina_orgs", "nina_sites", "nina_api_keys", "nina_cli_tokens", "nina_usage"):
        cur2.execute(f"SELECT COUNT(*) FROM {table}")
        print(f"  {table}: {cur2.fetchone()[0]} rows")
    cur2.close()
    conn2.close()

    print()
    print("Migration complete.")
    print(f"The original JSON file ({store_path}) has NOT been deleted.")
    print("Set DATABASE_URL in your deployment environment to activate PostgreSQL mode.")


if __name__ == "__main__":
    import argparse
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--store", type=Path, default=DEFAULT_STORE,
                        help=f"Path to JSON store file (default: {DEFAULT_STORE})")
    args = parser.parse_args()
    _migrate(args.store)
