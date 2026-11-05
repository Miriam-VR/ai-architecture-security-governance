"""Deterministic, versioned risk policy (V11). Pure code: the LLM can never change a decision."""

from __future__ import annotations

import hashlib
import json
from dataclasses import dataclass
from typing import Any

from app.governance.audit import AuditLog
from app.security.errors import AccessDenied
from app.store.base import Store

# Physical/industrial control is OUT OF SCOPE. These can never be allowed or approved, by any role or policy version.
PLC_CONTROL = frozenset({"change_setpoint", "plc_write", "stop_equipment", "start_equipment", "override_interlock"})

DEFAULT_RULES: dict[str, dict[str, Any]] = {
    "query": {"decision": "allow", "risk": "low"},
    "draft_work_order": {"decision": "allow", "risk": "low"},
    "publish_work_order": {"decision": "require_approval", "risk": "medium", "approver_role": "supervisor"},
}


@dataclass(frozen=True)
class Decision:
    decision: str  # allow | require_approval | deny
    risk: str
    reason: str
    policy_version: str


def rules_hash(rules: dict[str, Any]) -> str:
    return hashlib.sha256(json.dumps(rules, sort_keys=True).encode()).hexdigest()


class PolicyEngine:
    def __init__(self, store: Store, audit: AuditLog, rules: dict[str, Any] | None = None, version: str = "policy-v1") -> None:
        self._store, self._audit = store, audit
        active = store.active_policy_version()
        if active:  # persisted policy wins on restart
            self.rules, self.version = active["rules"], active["version"]
        else:
            self.rules, self.version = (rules or DEFAULT_RULES), version
            store.save_policy_version({"version": self.version, "rules": self.rules, "rules_hash": rules_hash(self.rules), "created_by": "system"})
            audit.record("policy_activated", actor="system", decision="allowed", details={"version": self.version, "rules_hash": rules_hash(self.rules)})

    def decide(self, action_type: str) -> Decision:
        if action_type in PLC_CONTROL:
            return Decision("deny", "critical", "physical/PLC control is permanently prohibited", self.version)
        rule = self.rules.get(action_type)
        if rule is None:
            return Decision("deny", "unknown", f"action '{action_type}' is not in the policy (default deny)", self.version)
        return Decision(rule["decision"], rule["risk"], f"policy rule for '{action_type}'", self.version)

    def activate(self, rules: dict[str, Any], version: str, actor: str) -> None:
        """New policy version + auditable decision record. Hard-denied actions can never be relaxed."""
        for a, r in rules.items():
            if a in PLC_CONTROL and r.get("decision") != "deny":
                raise AccessDenied(f"policy may not relax prohibited action '{a}'")
            if r.get("decision") not in {"allow", "require_approval", "deny"}:
                raise ValueError(f"invalid decision for '{a}'")
        old_hash, new_hash = rules_hash(self.rules), rules_hash(rules)
        changed = sorted(a for a in set(self.rules) | set(rules) if self.rules.get(a) != rules.get(a))
        self._store.save_policy_version({"version": version, "rules": rules, "rules_hash": new_hash, "created_by": actor})
        self._audit.record("policy_changed", actor=actor, decision="allowed",
                           details={"old_version": self.version, "new_version": version, "old_hash": old_hash, "new_hash": new_hash, "changed_actions": changed})
        self.rules, self.version = rules, version
