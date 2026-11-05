"""Create the 3 demo users in Supabase Auth with role/plant claims in app_metadata (admin API).

  SUPABASE_URL=https://<ref>.supabase.co SUPABASE_SERVICE_ROLE_KEY=... DEMO_PASSWORD='...' python scripts/create_demo_users.py
The SERVICE ROLE key is a root credential: run this from your machine only, never from CI or the app.
app_metadata can only be written with this key, so end users cannot grant themselves a role or plant.
"""

from __future__ import annotations

import json
import os
import sys
import urllib.error
import urllib.request
from pathlib import Path

PROFILES = json.loads((Path(__file__).resolve().parent.parent / "data/equipment/profiles.json").read_text())


def main() -> int:
    url, key, pw = os.environ.get("SUPABASE_URL"), os.environ.get("SUPABASE_SERVICE_ROLE_KEY"), os.environ.get("DEMO_PASSWORD")
    if not (url and key and pw):
        print("set SUPABASE_URL, SUPABASE_SERVICE_ROLE_KEY and DEMO_PASSWORD", file=sys.stderr)
        return 2
    for p in PROFILES:
        body = {"email": p["user"], "password": pw, "email_confirm": True, "app_metadata": {"app_role": p["role"], "plants": p["plants"]}}
        req = urllib.request.Request(url.rstrip("/") + "/auth/v1/admin/users", method="POST", data=json.dumps(body).encode(),  # noqa: S310
                                     headers={"apikey": key, "Authorization": f"Bearer {key}", "Content-Type": "application/json"})
        try:
            with urllib.request.urlopen(req, timeout=20) as r:  # noqa: S310
                print(f"created {p['user']} ({p['role']}) -> {r.status}")
        except urllib.error.HTTPError as e:
            print(f"{p['user']}: HTTP {e.code} {e.read().decode()[:120]}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
