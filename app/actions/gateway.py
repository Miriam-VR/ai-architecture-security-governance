"""Action Gateway (V09/V11): the agent PROPOSES; deterministic policy DECIDES; executor ACTS (once)."""

from __future__ import annotations

from app.actions.queue import ActionQueue
from app.governance.approvals import ApprovalService, idempotency_key
from app.governance.audit import AuditLog
from app.governance.policies import PolicyEngine
from app.models import Principal, ProposedAction
from app.observability.telemetry import new_id
from app.security.authorization import authorize
from app.store.base import Row, Store


class ActionGateway:
    def __init__(self, store: Store, policy: PolicyEngine, approvals: ApprovalService, queue: ActionQueue, audit: AuditLog) -> None:
        self._store, self._policy, self._approvals, self._queue, self._audit = store, policy, approvals, queue, audit

    def submit(self, principal: Principal, incident: Row, run_id: str, proposal: ProposedAction) -> ProposedAction:
        authorize(principal, "diagnose", plant_id=incident["plant_id"])
        d = self._policy.decide(proposal.action_type)
        status = {"allow": "queued", "require_approval": "pending_approval", "deny": "denied"}[d.decision]
        row, created = self._store.insert_action({
            "action_id": new_id("ACT"), "incident_id": incident["incident_id"], "plant_id": incident["plant_id"], "run_id": run_id,
            "action_type": proposal.action_type, "params": proposal.params, "risk": d.risk, "status": status,
            "idempotency_key": idempotency_key(incident["incident_id"], proposal.action_type, proposal.params),
            "policy_version": d.policy_version, "created_by": principal.user_id})
        self._audit.record("policy_decision" if created else "action_deduplicated", actor=principal.user_id, incident_id=incident["incident_id"],
                           run_id=run_id, decision=d.decision, details={"action_id": row["action_id"], "action_type": proposal.action_type,
                                                                        "risk": d.risk, "reason": d.reason, "policy_version": d.policy_version})
        approval_id = None
        if created and d.decision == "require_approval":
            approval_id = self._approvals.request(row, principal.user_id)
        elif created and d.decision == "allow":
            self._queue.send({"action_id": row["action_id"]})
            row = self._store.get_action(row["action_id"]) or row
        if approval_id is None and row["status"] == "pending_approval":  # dedup path: find the existing approval id
            ap = self._store.approval_for_action(row["action_id"])
            approval_id = ap["approval_id"] if ap else None
        shown = {"queued": "allowed", "executing": "allowed", "executed": "allowed", "pending_approval": "pending_approval",
                 "approved": "allowed", "denied": "denied", "rejected": "denied"}.get(row["status"], "proposed")
        return proposal.model_copy(update={"action_id": row["action_id"], "decision": shown, "reason": d.reason, "approval_id": approval_id})
