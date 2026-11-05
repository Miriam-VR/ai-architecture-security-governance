"""LangGraph nodes. Each node is thin: it delegates to a gateway that enforces the rules."""

from __future__ import annotations

from typing import Any

from app.agents.state import AgentState, RunDeps
from app.governance.audit import AuditLog  # noqa: F401  (re-export for type hints in tests)
from app.mcp.schemas import SensorReadings
from app.mcp.tool_gateway import ToolRejected
from app.models import Chunk, Hypothesis, Observation, ProposedAction, ReasoningRequest
from app.observability import telemetry

MAX_TOOL_CALLS_PER_STEP = 5
MAX_ACTIONS_PER_RUN = 5


def make_nodes(d: RunDeps):  # noqa: C901
    def load_incident(state: AgentState) -> AgentState:
        with d.timings.span("load_incident"):
            inc, resumed = d.memory.open_incident(d.principal, d.request)
            snap = d.memory.snapshot(d.principal, inc["incident_id"]) if resumed else {"hypotheses": [], "prior_runs": 0}
            run_id = d.memory.start_run(d.principal, inc["incident_id"], d.trace_id)
            telemetry.bind(run_id=run_id, incident_id=inc["incident_id"])
            return {"incident": inc, "resumed": resumed, "prior_run_count": snap["prior_runs"], "run_id": run_id, "step": 0,
                    "prior_hypotheses": [h.model_dump() for h in snap["hypotheses"]], "observations": [], "tool_errors": [], "evidence": []}

    def retrieve(state: AgentState) -> AgentState:
        with d.timings.span("retrieve"):
            chunks = d.retriever.retrieve(d.principal, plant_id=d.request.plant_id, equipment_id=d.request.equipment_id, symptoms=d.request.symptoms)
            return {"evidence": [c.model_dump() for c in chunks]}

    def reason(state: AgentState) -> AgentState:
        with d.timings.span("reason"):
            req = ReasoningRequest(
                equipment_id=d.request.equipment_id, plant_id=d.request.plant_id, symptoms=d.request.symptoms, user_message=d.request.message,
                evidence=[Chunk(**c) for c in state["evidence"]], observations=[Observation(**o) for o in state["observations"]],
                tool_errors=state["tool_errors"], prior_hypotheses=[Hypothesis(**h) for h in state["prior_hypotheses"]], step=state["step"])
            out = d.llm.reason(req)
            d.tokens_in += out.tokens_in
            d.tokens_out += out.tokens_out
            return {"step": state["step"] + 1, "pending_tool_calls": [t.model_dump() for t in out.tool_calls],
                    "hypotheses": [h.model_dump() for h in out.hypotheses], "recommended_checks": out.recommended_checks,
                    "proposed_actions": [a.model_dump() for a in out.proposed_actions], "needs_more_data": out.needs_more_data}

    def route_after_reason(state: AgentState) -> str:
        if state["pending_tool_calls"]:
            return "tools" if state["step"] < d.max_steps else "diagnose"
        return "diagnose"

    def tools(state: AgentState) -> AgentState:
        with d.timings.span("tools"):
            obs, errors = list(state["observations"]), list(state["tool_errors"])
            seen = {(o["name"], o["source"]) for o in obs}
            for call in state["pending_tool_calls"][:MAX_TOOL_CALLS_PER_STEP]:
                try:
                    res = d.tools.call(d.principal, call["name"], call["arguments"], incident_id=state["incident"]["incident_id"])
                except ToolRejected as e:  # blocked by the gateway: recorded, never executed
                    errors.append(f"{call['name']}: {e.code}")
                    continue
                if isinstance(res, SensorReadings):
                    for r in res.readings:
                        key = (r.sensor, "tool:get_sensor_readings")
                        if key not in seen:
                            seen.add(key)
                            obs.append(Observation(name=r.sensor, value=r.value, unit=r.unit, source="tool:get_sensor_readings", equipment_id=res.equipment_id).model_dump())
            return {"observations": obs, "tool_errors": errors, "pending_tool_calls": []}

    def diagnose(state: AgentState) -> AgentState:
        with d.timings.span("diagnose"):
            allowed = {c["source_id"] for c in state["evidence"]}
            hyps: list[dict[str, Any]] = []
            for h in state["hypotheses"]:  # no invented sources: keep only evidence that was really retrieved
                valid = [e for e in h["evidence_ids"] if e in allowed]
                if valid:
                    hyps.append({**h, "evidence_ids": valid})
            hyps.sort(key=lambda h: -h["confidence"])
            actions: list[dict[str, Any]] = []
            for raw in state["proposed_actions"][:MAX_ACTIONS_PER_RUN]:
                if not hyps and raw["action_type"] not in {"change_setpoint", "plc_write", "stop_equipment"}:
                    continue  # never propose work without a supported hypothesis
                actions.append(d.actions.submit(d.principal, state["incident"], state["run_id"], ProposedAction(**raw)).model_dump())
            if state["pending_tool_calls"]:
                status = "max_steps_reached"
            elif not hyps:
                status = "needs_more_data"
            elif any(a["decision"] == "pending_approval" for a in actions):
                status = "pending_approval"
            else:
                status = "completed"
            return {"hypotheses": hyps, "proposed_actions": actions, "status": status}

    def persist(state: AgentState) -> AgentState:
        with d.timings.span("persist"):
            iid, rid = state["incident"]["incident_id"], state["run_id"]
            d.memory.save_observations(d.principal, iid, rid, [Observation(**o) for o in state["observations"]])
            d.memory.save_hypotheses(d.principal, iid, rid, [Hypothesis(**h) for h in state["hypotheses"]])
            d.memory.finish_run(d.principal, iid, rid, state["status"], state["step"], d.timings.ms)
            return {}

    return {"load_incident": load_incident, "retrieve": retrieve, "reason": reason, "tools": tools, "diagnose": diagnose,
            "persist": persist, "route_after_reason": route_after_reason}
