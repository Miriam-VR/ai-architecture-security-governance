"""Apply supabase/migrations/*.sql (+ optional seed.sql) to a Postgres database.

Usage:
  DATABASE_URL=postgresql://... python scripts/apply_migrations.py --seed
Use the DIRECT or SESSION-pooler connection (port 5432), not the transaction pooler (6543).
--stub-auth creates a fake `auth.jwt()` so RLS migrations also run on a plain pgvector container.
"""

from __future__ import annotations

import argparse
import os
import sys
from pathlib import Path

import psycopg2

ROOT = Path(__file__).resolve().parent.parent
STUB = """
create schema if not exists auth;
create or replace function auth.jwt() returns jsonb language sql stable as $$ select '{}'::jsonb $$;
do $$ begin if not exists (select 1 from pg_roles where rolname='authenticated') then create role authenticated nologin; end if; end $$;
"""


def main() -> int:
    ap = argparse.ArgumentParser()
    ap.add_argument("--seed", action="store_true")
    ap.add_argument("--stub-auth", action="store_true")
    a = ap.parse_args()
    dsn = os.environ.get("DATABASE_URL") or os.environ.get("TEST_DATABASE_URL")
    if not dsn:
        print("DATABASE_URL is not set", file=sys.stderr)
        return 2
    files = sorted((ROOT / "supabase/migrations").glob("*.sql")) + ([ROOT / "supabase/seed.sql"] if a.seed else [])
    conn = psycopg2.connect(dsn)
    conn.autocommit = True
    with conn.cursor() as cur:
        if a.stub_auth:
            cur.execute(STUB)
        for f in files:
            print(f"applying {f.relative_to(ROOT)}")
            cur.execute(f.read_text())
    conn.close()
    print("done")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
