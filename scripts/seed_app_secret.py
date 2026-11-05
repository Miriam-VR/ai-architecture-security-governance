"""Write the app secret VALUE into AWS Secrets Manager (Terraform only creates the empty container).

Reads values from environment variables so nothing is typed on the command line / shell history:
  OPENAI_API_KEY (optional), DATABASE_URL, JWT_SECRET, MCP_SHARED_SECRET (auto-generated if missing)
  python scripts/seed_app_secret.py --secret-id maintenance-ai/dev/app --region us-east-1
"""

from __future__ import annotations

import argparse
import json
import os
import secrets

import boto3


def main() -> int:
    ap = argparse.ArgumentParser()
    ap.add_argument("--secret-id", required=True)
    ap.add_argument("--region", default="us-east-1")
    a = ap.parse_args()
    values = {
        "OPENAI_API_KEY": os.environ.get("OPENAI_API_KEY", ""),
        "DATABASE_URL": os.environ["DATABASE_URL"],
        "JWT_SECRET": os.environ["JWT_SECRET"],
        "MCP_SHARED_SECRET": os.environ.get("MCP_SHARED_SECRET") or secrets.token_urlsafe(48),
    }
    boto3.client("secretsmanager", region_name=a.region).put_secret_value(SecretId=a.secret_id, SecretString=json.dumps(values))
    print(f"stored {sorted(k for k, v in values.items() if v)} in {a.secret_id} (values not printed)")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
