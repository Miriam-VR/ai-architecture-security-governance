"""Append-only audit trail (V09/V13). Details are redacted BEFORE persistence. No update/delete API exists."""

from __future__ import annotations

from typing import Any

from app.observability import telemetry
from app.security.redaction import redact
from app.store.base import Store


class AuditLog:
    def __init__(self, store: Store) -> None:
        self._store = store

    def record(self, event_type: str, *, actor: str, decision: str | None = None, incident_id: str | None = None,
               run_id: str | None = None, details: dict[str, Any] | None = None) -> str:
        ctx = telemetry.current()
        event_id = telemetry.new_id("AUD")
        self._store.append_audit({
            "event_id": event_id, "event_type": event_type, "incident_id": incident_id or ctx.get("incident_id"),
            "run_id": run_id or ctx.get("run_id"), "trace_id": ctx.get("trace_id"), "actor": actor,
            "decision": decision, "details": redact(details or {}),
        })
        return event_id

    def for_incident(self, incident_id: str) -> list[dict[str, Any]]:
        return self._store.list_audit(incident_id)
