"""Post-deploy smoke test (used by GitHub Actions and by hand).

  python scripts/smoke_test.py --base-url https://xxxx.execute-api.us-east-1.amazonaws.com/dev --api-key KEY \
        [--secret-id maintenance-ai/dev/app]   # mints a technician JWT from the app secret (needs secretsmanager:GetSecretValue)
  or  --token <jwt>
Checks: /health, unauthenticated -> 401, authenticated P-204 diagnosis with citations, cross-plant -> 403.
Exit code 1 on the first failed check.
"""

from __future__ import annotations

import argparse
import json
import sys
import urllib.error
import urllib.request
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent))
from mint_token import mint  # noqa: E402

P204 = {"incident_id": "INC-SMOKE", "equipment_id": "P-204", "plant_id": "PLANT-A",
        "symptoms": ["high_vibration", "high_bearing_temperature", "low_discharge_pressure"], "message": "smoke test"}


def call(base: str, method: str, path: str, headers: dict, body: dict | None = None) -> tuple[int, dict]:
    req = urllib.request.Request(base.rstrip("/") + path, method=method, data=json.dumps(body).encode() if body is not None else None,  # noqa: S310
                                 headers={"Content-Type": "application/json", **headers})
    try:
        with urllib.request.urlopen(req, timeout=40) as r:  # noqa: S310
            return r.status, json.loads(r.read() or b"{}")
    except urllib.error.HTTPError as e:
        try:
            return e.code, json.loads(e.read() or b"{}")
        except ValueError:
            return e.code, {}


def main() -> int:
    ap = argparse.ArgumentParser()
    ap.add_argument("--base-url", required=True)
    ap.add_argument("--api-key", default="")
    ap.add_argument("--token", default="")
    ap.add_argument("--secret-id", default="")
    ap.add_argument("--region", default="us-east-1")
    ap.add_argument("--route", default="/diagnose/quick")
    a = ap.parse_args()
    key = {"x-api-key": a.api_key} if a.api_key else {}
    token = a.token
    if not token and a.secret_id:
        import boto3

        secret = json.loads(boto3.client("secretsmanager", region_name=a.region).get_secret_value(SecretId=a.secret_id)["SecretString"])["JWT_SECRET"]
        token = mint(secret, "smoke@example.com", "technician", ["PLANT-A"], minutes=5)
    failures: list[str] = []

    def check(name: str, ok: bool, detail: str = "") -> None:
        print(("PASS " if ok else "FAIL ") + name + (f" ({detail})" if detail and not ok else ""))
        if not ok:
            failures.append(name)

    s, _ = call(a.base_url, "GET", "/health", key)
    check("health 200", s == 200, str(s))
    s, _ = call(a.base_url, "POST", a.route, key, P204)
    check("unauthenticated -> 401", s == 401, str(s))
    if token:
        h = {**key, "Authorization": f"Bearer {token}"}
        s, b = call(a.base_url, "POST", a.route, h, P204)
        check("P-204 diagnosis 200", s == 200, str(s))
        check("has hypotheses + citations", bool(b.get("hypotheses")) and bool(b.get("citations")))
        check("observations are the scenario values", {o["name"]: o["value"] for o in b.get("observations", [])}.get("vibration") == 8.4)
        s, _ = call(a.base_url, "POST", a.route, h, {**P204, "incident_id": "INC-SMOKE-B", "plant_id": "PLANT-B", "equipment_id": "P-305"})
        check("cross-plant -> 403", s == 403, str(s))
    else:
        print("SKIP authenticated checks (no --token / --secret-id)")
    print("SMOKE", "FAILED" if failures else "OK")
    return 1 if failures else 0


if __name__ == "__main__":
    raise SystemExit(main())
