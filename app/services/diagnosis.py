"""Diagnosis service: builds a per-request graph, runs it, maps state -> contract."""

from __future__ import annotations

from app.agents.graph import build_graph
from app.agents.state import RunDeps
from app.container import Container
from app.llm.base import LLMError
from app.models import (
    Chunk,
    Citation,
    DiagnoseRequest,
    DiagnosisResponse,
    Hypothesis,
    Observation,
    Principal,
    ProposedAction,
)
from app.observability import telemetry


class ServiceUnavailable(Exception):
    """Upstream (LLM) failure -> 502/503 without leaking provider details."""


class DiagnosisService:
    def __init__(self, c: Container) -> None:
        self._c = c

    def diagnose(self, principal: Principal, req: DiagnoseRequest, *, max_steps: int | None = None) -> DiagnosisResponse:
        c = self._c
        trace_id = telemetry.current().get("trace_id") or telemetry.new_id("TRC")
        telemetry.bind(trace_id=trace_id, incident_id=req.incident_id, user=principal.user_id)
        deps = RunDeps(principal=principal, request=req, trace_id=trace_id, max_steps=max_steps or c.settings.quick_max_steps, llm=c.llm,
                       retriever=c.retriever, tools=c.tools, memory=c.memory, actions=c.actions)
        c.audit.record("diagnose_requested", actor=principal.user_id, incident_id=req.incident_id, decision="allowed",
                       details={"equipment_id": req.equipment_id, "plant_id": req.plant_id, "symptoms": req.symptoms})
        try:
            state = build_graph(deps).invoke({})
        except LLMError as e:
            c.audit.record("llm_error", actor=principal.user_id, incident_id=req.incident_id, decision="error", details={"error": str(e)})
            raise ServiceUnavailable("language model unavailable") from e
        chunks = {ch["source_id"]: Chunk(**ch) for ch in state["evidence"]}
        cited = [sid for h in state["hypotheses"] for sid in h["evidence_ids"]]
        citations = [Citation(source_id=sid, source_type=chunks[sid].source_type, snippet=chunks[sid].text[:240]) for sid in dict.fromkeys(cited)]
        checks = state["recommended_checks"] or (["Medir de nuevo vibracion y temperatura y aportar mas sintomas"] if state["status"] == "needs_more_data" else [])
        c.audit.record("diagnose_completed", actor=principal.user_id, incident_id=req.incident_id, decision=state["status"],
                       details={"steps": state["step"], "tokens_in": deps.tokens_in, "tokens_out": deps.tokens_out, "node_timings_ms": deps.timings.ms})
        resp = DiagnosisResponse(
            incident_id=req.incident_id, run_id=state["run_id"], status=state["status"], trace_id=trace_id,
            observations=[Observation(**o) for o in state["observations"]], hypotheses=[Hypothesis(**h) for h in state["hypotheses"]],
            recommended_checks=checks, citations=citations, proposed_actions=[ProposedAction(**a) for a in state["proposed_actions"]],
            resumed=state["resumed"], prior_run_count=state["prior_run_count"], steps=state["step"], node_timings_ms=deps.timings.ms)
        self.last_usage = {"tokens_in": deps.tokens_in, "tokens_out": deps.tokens_out}
        return resp

    last_usage: dict[str, int] = {}
