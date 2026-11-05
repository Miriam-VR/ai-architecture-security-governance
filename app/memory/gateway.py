"""Secure Memory Gateway (V04 + V07 + V09): every read/write is scoped, typed and provenance-checked.

* Reads/writes are authorised against the INCIDENT's plant (taken from storage, never from the body).
* Facts (observations) are accepted ONLY from trusted sources ('tool:*'); LLM output goes to hypotheses.
* Observations must refer to the incident's own equipment (no cross-equipment contamination).
"""

from __future__ import annotations

from typing import Any

from app.governance.audit import AuditLog
from app.models import DiagnoseRequest, Hypothesis, Observation, Principal
from app.observability.telemetry import new_id
from app.security.authorization import authorize
from app.security.errors import AccessDenied, NotFound
from app.store.base import Row, Store


class MemoryGateway:
    def __init__(self, store: Store, audit: AuditLog) -> None:
        self._store, self._audit = store, audit

    def _scoped_incident(self, principal: Principal, incident_id: str, permission: str) -> Row:
        inc = self._store.get_incident(incident_id)
        if inc is None:
            raise NotFound("incident not found")
        authorize(principal, permission, plant_id=inc["plant_id"])
        return inc

    def open_incident(self, principal: Principal, req: DiagnoseRequest) -> tuple[Row, bool]:
        """Create or resume. Returns (incident, resumed)."""
        existing = self._store.get_incident(req.incident_id)
        if existing:
            authorize(principal, "diagnose", plant_id=existing["plant_id"])
            if existing["plant_id"] != req.plant_id or existing["equipment_id"] != req.equipment_id:
                raise AccessDenied("incident belongs to a different plant/equipment")
            return existing, True
        authorize(principal, "incident:create", plant_id=req.plant_id)
        inc = self._store.create_incident({"incident_id": req.incident_id, "plant_id": req.plant_id, "equipment_id": req.equipment_id,
                                           "symptoms": req.symptoms, "created_by": principal.user_id})
        self._audit.record("incident_created", actor=principal.user_id, incident_id=req.incident_id, decision="allowed")
        return inc, False

    def read_incident(self, principal: Principal, incident_id: str) -> dict[str, Any]:
        inc = self._scoped_incident(principal, incident_id, "incident:read")
        return {**inc, "observations": self._store.list_observations(incident_id), "hypotheses": self._store.list_hypotheses(incident_id),
                "runs": self._store.list_runs(incident_id), "actions": self._store.list_actions(incident_id)}

    def snapshot(self, principal: Principal, incident_id: str) -> dict[str, Any]:
        self._scoped_incident(principal, incident_id, "incident:read")
        return {"hypotheses": [Hypothesis(**{k: h[k] for k in Hypothesis.model_fields}) for h in self._store.list_hypotheses(incident_id)],
                "prior_runs": len(self._store.list_runs(incident_id))}

    def start_run(self, principal: Principal, incident_id: str, trace_id: str) -> str:
        self._scoped_incident(principal, incident_id, "diagnose")
        run_id = new_id("RUN")
        self._store.add_run({"run_id": run_id, "incident_id": incident_id, "trace_id": trace_id, "status": "running", "created_by": principal.user_id})
        return run_id

    def finish_run(self, principal: Principal, incident_id: str, run_id: str, status: str, steps: int, timings: dict[str, float]) -> None:
        self._scoped_incident(principal, incident_id, "diagnose")
        self._store.finish_run(run_id, status, steps, timings)
        self._store.touch_incident(incident_id, status)

    def save_observations(self, principal: Principal, incident_id: str, run_id: str, obs: list[Observation]) -> int:
        inc = self._scoped_incident(principal, incident_id, "diagnose")
        for o in obs:
            if not o.source.startswith("tool:"):
                raise AccessDenied(f"observation from untrusted source '{o.source}' rejected (facts must come from tools)")
            if o.equipment_id != inc["equipment_id"]:
                raise AccessDenied("observation refers to a different equipment than the incident")
        self._store.add_observations(incident_id, run_id, principal.user_id, [o.model_dump() for o in obs])
        return len(obs)

    def save_hypotheses(self, principal: Principal, incident_id: str, run_id: str, hyps: list[Hypothesis]) -> int:
        self._scoped_incident(principal, incident_id, "diagnose")
        self._store.add_hypotheses(incident_id, run_id, principal.user_id, [h.model_dump() for h in hyps])
        return len(hyps)

    def read_run(self, principal: Principal, run_id: str) -> Row:
        run = self._store.get_run(run_id)
        if run is None:
            raise NotFound("run not found")
        self._scoped_incident(principal, run["incident_id"], "incident:read")
        return run
