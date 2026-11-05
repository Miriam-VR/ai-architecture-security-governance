"""SQS worker Lambda: executes approved actions. Idempotent; reports partial batch failures."""

from __future__ import annotations

import json
from typing import Any

from app.config import get_settings
from app.container import Container, build_container

_container: Container | None = None


def _c() -> Container:
    global _container  # noqa: PLW0603
    if _container is None:
        _container = build_container(get_settings())
    return _container


def handler(event: dict[str, Any], context: Any = None) -> dict[str, Any]:
    failures = []
    for rec in event.get("Records", []):
        try:
            _c().executor.handle_message(json.loads(rec["body"]))
        except Exception:  # noqa: BLE001  -> message returns to the queue, then DLQ after maxReceiveCount
            failures.append({"itemIdentifier": rec["messageId"]})
    return {"batchItemFailures": failures}
