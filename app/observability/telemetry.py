"""Structured JSON logs (CloudWatch), correlation ids, per-node latency (V13).

OpenTelemetry is OPTIONAL: spans are exported only if OTEL_EXPORTER_OTLP_ENDPOINT is set AND the
opentelemetry SDK is installed. Otherwise only correlation ids + logs exist (we do not pretend otherwise).
"""

from __future__ import annotations

import contextvars
import json
import logging
import os
import time
import uuid
from collections.abc import Iterator
from contextlib import contextmanager
from typing import Any

from app.security.redaction import redact

_ctx: contextvars.ContextVar[dict[str, Any] | None] = contextvars.ContextVar("ctx", default=None)


def new_id(prefix: str) -> str:
    return f"{prefix}-{uuid.uuid4().hex[:12]}"


def bind(**kv: Any) -> None:
    _ctx.set({**(_ctx.get() or {}), **kv})


def current() -> dict[str, Any]:
    return dict(_ctx.get() or {})


def otel_enabled() -> bool:
    if not os.getenv("OTEL_EXPORTER_OTLP_ENDPOINT"):
        return False
    try:
        import opentelemetry  # noqa: F401
    except ImportError:
        return False
    return True


class JsonFormatter(logging.Formatter):
    def format(self, record: logging.LogRecord) -> str:
        payload = {"ts": self.formatTime(record), "level": record.levelname, "logger": record.name,
                   "msg": record.getMessage(), **current(), **getattr(record, "extra_fields", {})}
        return json.dumps(redact(payload), default=str)


def configure_logging(level: str = "INFO") -> None:
    root = logging.getLogger()
    if any(isinstance(h.formatter, JsonFormatter) for h in root.handlers):
        root.setLevel(level)
        return
    h = logging.StreamHandler()
    h.setFormatter(JsonFormatter())
    root.handlers = [h]
    root.setLevel(level)
    logging.getLogger("httpx").setLevel(logging.WARNING)
    logging.getLogger("httpx2").setLevel(logging.WARNING)


def log(logger: str, msg: str, **fields: Any) -> None:
    logging.getLogger(logger).info(msg, extra={"extra_fields": fields})


class Timings:
    """Collects per-node latency for one run."""

    def __init__(self) -> None:
        self.ms: dict[str, float] = {}

    @contextmanager
    def span(self, name: str) -> Iterator[None]:
        t0 = time.perf_counter()
        try:
            yield
        finally:
            self.ms[name] = round(self.ms.get(name, 0.0) + (time.perf_counter() - t0) * 1000, 3)
