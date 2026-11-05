"""Runtime secret loading (V08). Secret VALUES never live in code, git or Terraform state.

SECRETS_BACKEND=env -> values already in environment (local dev).
SECRETS_BACKEND=aws -> one JSON secret in AWS Secrets Manager (APP_SECRET_ID), cached per container.
"""

from __future__ import annotations

import json
import time
from typing import Any

_SECRET_FIELDS = {
    "OPENAI_API_KEY": "openai_api_key",
    "DATABASE_URL": "database_url",
    "JWT_SECRET": "jwt_secret",
    "MCP_SHARED_SECRET": "mcp_shared_secret",
}
_CACHE: dict[str, tuple[float, dict[str, Any]]] = {}
_TTL_S = 300


def fetch_secret_json(secret_id: str, region: str, client: Any = None) -> dict[str, Any]:
    now = time.time()
    hit = _CACHE.get(secret_id)
    if hit and now - hit[0] < _TTL_S:
        return hit[1]
    if client is None:
        import boto3

        client = boto3.client("secretsmanager", region_name=region)
    raw = client.get_secret_value(SecretId=secret_id)["SecretString"]
    data = json.loads(raw)
    _CACHE[secret_id] = (now, data)
    return data


def apply_runtime_secrets(settings: Any, client: Any = None) -> Any:
    """Return settings with secret fields filled from Secrets Manager when configured."""
    if settings.secrets_backend != "aws":
        return settings
    if not settings.app_secret_id:
        raise RuntimeError("SECRETS_BACKEND=aws requires APP_SECRET_ID")
    data = fetch_secret_json(settings.app_secret_id, settings.aws_region, client)
    updates = {attr: data[key] for key, attr in _SECRET_FIELDS.items() if data.get(key)}
    return settings.model_copy(update=updates)
