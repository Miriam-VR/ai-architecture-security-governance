"""Action Executor (V09). Never trusts the queue: re-checks policy, approval, expiry, hash and idempotency."""

from __future__ import annotations

from datetime import UTC, datetime
from typing import Any

from app.actions.cmms import MockCMMS
from app.governance.approvals import _parse, action_hash
from app.governance.audit import AuditLog
from app.governance.policies import PolicyEngine
from app.store.base import Store


class ActionExecutor:
    def __init__(self, store: Store, policy: PolicyEngine, audit: AuditLog, cmms: MockCMMS) -> None:
        self._store, self._policy, self._audit, self._cmms = store, policy, audit, cmms

    def handle_message(self, message: dict[str, Any]) -> str:
        return self.execute(message["action_id"], message.get("approval_id"))

    def _fail(self, action: dict[str, Any], reason: str) -> str:
        self._audit.record("action_blocked", actor="executor", incident_id=action["incident_id"], decision="denied",
                           details={"action_id": action["action_id"], "reason": reason})
        return f"blocked:{reason}"

    def execute(self, action_id: str, approval_id: str | None = None) -> str:
        a = self._store.get_action(action_id)
        if a is None:
            return "blocked:unknown_action"
        if a["status"] in ("executed", "executing"):
            self._audit.record("action_duplicate_ignored", actor="executor", incident_id=a["incident_id"], decision="ignored", details={"action_id": action_id})
            return "duplicate_ignored"
        d = self._policy.decide(a["action_type"])  # re-check: policy may have changed since queued
        if d.decision == "deny":
            self._store.transition_action(action_id, a["status"], "denied")
            return self._fail(a, "policy_denied")
        if a["status"] != "queued":
            return self._fail(a, f"bad_status_{a['status']}")
        if d.decision == "require_approval":
            ap = self._store.get_approval(approval_id) if approval_id else None
            if not ap or ap["action_id"] != action_id:
                return self._fail(a, "missing_approval")
            if ap["status"] != "approved":  # consumed (replay), rejected, expired, pending
                return self._fail(a, f"approval_{ap['status']}")
            if _parse(ap["expires_at"]) < datetime.now(UTC):
                return self._fail(a, "approval_expired")
            if ap["action_hash"] != action_hash(a):
                return self._fail(a, "approval_hash_mismatch")
        if not self._store.transition_action(action_id, "queued", "executing"):  # atomic claim: exactly one executor wins
            return "duplicate_ignored"
        if d.decision == "require_approval" and not self._store.decide_approval(approval_id, "approved", "consumed", None):  # type: ignore[arg-type]
            self._store.transition_action(action_id, "executing", "denied")
            return self._fail(a, "approval_replayed")
        mode = "draft" if a["action_type"] == "draft_work_order" else "published"
        wo = self._cmms.create_work_order(a["idempotency_key"], mode, a["params"])
        self._store.transition_action(action_id, "executing", "executed", result=wo)
        self._audit.record("action_executed", actor="executor", incident_id=a["incident_id"], decision="executed",
                           details={"action_id": action_id, "work_order_id": wo["work_order_id"], "mode": mode, "policy_version": d.policy_version})
        return "executed"
