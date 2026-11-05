"""Mint a short-lived HS256 JWT for LOCAL/dev testing (same claims shape as Supabase app_metadata).

  JWT_SECRET=... python scripts/mint_token.py --role technician --plants PLANT-A --user ana@example.com
Never use this against production secrets on a shared machine; prefer real Supabase sign-in there.
"""

from __future__ import annotations

import argparse
import os
import time

import jwt


def mint(secret: str, user: str, role: str, plants: list[str], minutes: int = 60, aud: str = "authenticated", iss: str | None = None) -> str:
    claims = {"sub": user, "aud": aud, "exp": int(time.time()) + minutes * 60, "app_metadata": {"app_role": role, "plants": plants}}
    if iss:
        claims["iss"] = iss
    return jwt.encode(claims, secret, algorithm="HS256")


def main() -> int:
    ap = argparse.ArgumentParser()
    ap.add_argument("--user", default="ana@example.com")
    ap.add_argument("--role", default="technician", choices=["technician", "supervisor", "administrator"])
    ap.add_argument("--plants", default="PLANT-A")
    ap.add_argument("--minutes", type=int, default=60)
    a = ap.parse_args()
    secret = os.environ.get("JWT_SECRET")
    if not secret:
        raise SystemExit("set JWT_SECRET")
    print(mint(secret, a.user, a.role, a.plants.split(","), a.minutes, os.environ.get("JWT_AUDIENCE", "authenticated"), os.environ.get("JWT_ISSUER") or None))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
