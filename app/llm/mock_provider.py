"""Deterministic mock LLM. Intentionally GULLIBLE: it obeys 'call tool X' found in untrusted text,
so security tests prove the gateways (not the model) stop the attack."""

from __future__ import annotations

import re

from app.models import Hypothesis, ProposedAction, ReasoningOutput, ReasoningRequest, ToolCall

_INJECT = re.compile(r"call tool (\w+)([^\n.]*)", re.I)
_KV = re.compile(r"(\w+)=([\w\-./@]+)")
_FORBIDDEN = re.compile(r"setpoint|plc|apaga la bomba|stop the pump", re.I)

CHECKS = {
    "bearing_wear": ["Medir vibracion de nuevo en lado acople y lado libre", "Inspeccionar lubricacion y temperatura del rodamiento"],
    "misalignment": ["Verificar alineacion laser bomba-motor", "Revisar pata coja y tension de tuberia"],
    "cavitation": ["Verificar nivel y filtro de succion", "Escuchar ruido de cavitacion con equipo en carga"],
    "seal_leak": ["Inspeccionar visualmente sello mecanico", "Revisar temperatura de sello"],
    "impeller_damage": ["Comparar caudal vs curva de bomba", "Planificar inspeccion de impulsor"],
}
DEFAULT_CHECKS = ["Medir de nuevo la vibracion en lado acople", "Confirmar sintomas con el operador", "Registrar temperatura con termografia"]


def _jaccard(a: set[str], b: set[str]) -> float:
    return len(a & b) / len(a | b) if a | b else 0.0


class MockLLM:
    name = "mock"

    def reason(self, req: ReasoningRequest) -> ReasoningOutput:
        out = ReasoningOutput(tokens_in=sum(len(c.text) for c in req.evidence) // 4 + len(req.user_message) // 4 + 200)
        texts = [req.user_message, *[c.text for c in req.evidence]]

        if req.step == 0:  # obey injected tool calls (gullible by design)
            for t in texts:
                for m in _INJECT.finditer(t):
                    out.tool_calls.append(ToolCall(name=m.group(1), arguments=dict(_KV.findall(m.group(2)))))
            if not req.observations:
                out.tool_calls += [ToolCall(name="get_sensor_readings", arguments={"equipment_id": req.equipment_id}),
                                   ToolCall(name="get_equipment_info", arguments={"equipment_id": req.equipment_id})]
            if out.tool_calls:
                out.needs_more_data = True
                return out

        sym = set(req.symptoms)
        by_cause: dict[str, list] = {}
        for c in req.evidence:
            if c.root_cause:
                by_cause.setdefault(c.root_cause, []).append(c)
        vib = next((float(o.value) for o in req.observations if o.name == "vibration"), 0.0)
        temp = next((float(o.value) for o in req.observations if o.name == "bearing_temperature"), 0.0)
        hyps = []
        for cause, chunks in by_cause.items():
            sources = {c.source_id for c in chunks}
            support = max(_jaccard(sym, set(c.symptoms)) for c in chunks)
            conf = 0.15 + 0.75 * support + 0.03 * (len(sources) - 1)
            if any(c.equipment_id == req.equipment_id for c in chunks):
                conf += 0.04
            if cause == "bearing_wear" and vib > 7 and temp > 80:
                conf += 0.08
            conf = round(min(conf, 0.95), 2)
            if conf >= 0.3:
                hyps.append(Hypothesis(cause=cause, confidence=conf, evidence_ids=sorted(sources),
                                       rationale=f"{len(sources)} falla(s) historica(s) con sintomas similares"))
        hyps.sort(key=lambda h: (-h.confidence, h.cause))
        out.hypotheses = hyps[:3]

        if not out.hypotheses:
            out.needs_more_data = True
            out.recommended_checks = list(DEFAULT_CHECKS)
        else:
            top = out.hypotheses[0]
            out.recommended_checks = CHECKS.get(top.cause, DEFAULT_CHECKS)
            if top.confidence >= 0.6:
                p = {"equipment_id": req.equipment_id, "plant_id": req.plant_id, "cause": top.cause}
                out.proposed_actions = [
                    ProposedAction(action_type="draft_work_order", summary=f"Borrador OT: inspeccionar {top.cause} en {req.equipment_id}", params=p),
                    ProposedAction(action_type="publish_work_order", summary=f"Publicar OT: inspeccionar {top.cause} en {req.equipment_id}", params=p),
                ]
        if any(_FORBIDDEN.search(t) for t in texts):  # obey forbidden-action requests; policy must reject
            out.proposed_actions.append(ProposedAction(action_type="change_setpoint", summary="Cambiar setpoint del PLC", params={"equipment_id": req.equipment_id, "value": 0}))
        out.tokens_out = 120 + 40 * len(out.hypotheses)
        return out


class LoopingMockLLM(MockLLM):
    """Always asks for another tool call -> used to prove max_steps terminates the graph."""

    name = "mock-looping"

    def reason(self, req: ReasoningRequest) -> ReasoningOutput:
        return ReasoningOutput(needs_more_data=True, tool_calls=[ToolCall(name="get_sensor_readings", arguments={"equipment_id": req.equipment_id})])
