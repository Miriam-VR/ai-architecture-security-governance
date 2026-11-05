"""Human-in-the-loop approvals (V09/V11): separation of duties, expiry, single use, bound to the exact action."""

from __future__ import annotations

import hashlib
import json
from datetime import UTC, datetime, timedelta
from typing import Any

from app.governance.audit import AuditLog
from app.models import Principal
from app.observability.telemetry import new_id
from app.security.authorization import authorize
from app.security.errors import AccessDenied, Conflict, NotFound
from app.store.base import Row, Store


def action_hash(action: Row) -> str:
    body = {"action_id": action["action_id"], "incident": action["incident_id"], "type": action["action_type"], "params": action["params"]}
    return hashlib.sha256(json.dumps(body, sort_keys=True, default=str).encode()).hexdigest()


def idempotency_key(incident_id: str, action_type: str, params: dict[str, Any]) -> str:
    return hashlib.sha256(json.dumps({"i": incident_id, "t": action_type, "p": params}, sort_keys=True).encode()).hexdigest()


def _parse(ts: Any) -> datetime:
    return ts if isinstance(ts, datetime) else datetime.fromisoformat(str(ts))


class ApprovalService:
    def __init__(self, store: Store, audit: AuditLog, queue: Any, ttl_minutes: int = 60) -> None:
        self._store, self._audit, self._queue, self._ttl = store, audit, queue, ttl_minutes

    def request(self, action: Row, requester: str) -> str:
        approval_id = new_id("APR")
        self._store.insert_approval({"approval_id": approval_id, "action_id": action["action_id"], "status": "pending", "created_by": requester,
                                     "action_hash": action_hash(action), "expires_at": (datetime.now(UTC) + timedelta(minutes=self._ttl)).isoformat()})
        self._audit.record("approval_requested", actor=requester, incident_id=action["incident_id"], decision="pending",
                           details={"action_id": action["action_id"], "approval_id": approval_id})
        return approval_id

    def decide(self, principal: Principal, approval_id: str, approve: bool) -> Row:
        ap = self._store.get_approval(approval_id)
        if ap is None:
            raise NotFound("approval not found")
        action = self._store.get_action(ap["action_id"])
        if action is None:
            raise NotFound("action not found")
        try:
            authorize(principal, "approval:decide", plant_id=action["plant_id"])
        except AccessDenied as e:
            raise AccessDenied(str(e), incident_id=action["incident_id"]) from e
        if principal.user_id == action["created_by"]:
            raise AccessDenied("requester cannot approve their own action (separation of duties)", incident_id=action["incident_id"])
        if ap["status"] != "pending":
            raise Conflict(f"approval already {ap['status']}")
        if _parse(ap["expires_at"]) < datetime.now(UTC):
            self._store.decide_approval(approval_id, "pending", "expired", None)
            raise Conflict("approval expired")
        new_status = "approved" if approve else "rejected"
        if not self._store.decide_approval(approval_id, "pending", new_status, principal.user_id):  # atomic: loses races -> 409
            raise Conflict("approval already decided")
        self._audit.record(f"approval_{new_status}", actor=principal.user_id, incident_id=action["incident_id"], decision=new_status,
                           details={"action_id": action["action_id"], "approval_id": approval_id})
        if approve:
            self._store.transition_action(action["action_id"], "pending_approval", "queued")
            self._queue.send({"action_id": action["action_id"], "approval_id": approval_id})
        else:
            self._store.transition_action(action["action_id"], "pending_approval", "rejected")
        return self._store.get_action(action["action_id"])  # type: ignore[return-value]
