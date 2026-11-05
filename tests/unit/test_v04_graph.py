"""V04 - LangGraph + memory."""

from app.models import Principal, ReasoningOutput, ToolCall
from tests.conftest import auth

ANA = Principal(user_id="ana", role="technician", plants=("PLANT-A",))


def test_second_request_resumes_incident_state(client, container, p204):
    first = client.post("/diagnose", json=p204, headers=auth()).json()
    assert first["resumed"] is False and first["prior_run_count"] == 0
    second = client.post("/diagnose", json=p204, headers=auth()).json()
    assert second["resumed"] is True and second["prior_run_count"] == 1
    inc = client.get("/incidents/INC-204", headers=auth()).json()
    assert len(inc["runs"]) == 2 and inc["observations"] and inc["hypotheses"]


def test_resumed_run_gives_the_llm_prior_hypotheses(settings, store, p204):
    from fastapi.testclient import TestClient

    from app.api.main import create_app
    from app.container import build_container
    from app.llm.mock_provider import MockLLM

    seen = []

    class Spy(MockLLM):
        def reason(self, req):
            seen.append(req)
            return super().reason(req)

    c = TestClient(create_app(build_container(settings, store=store, llm=Spy())))
    c.post("/diagnose", json=p204, headers=auth())
    c.post("/diagnose", json=p204, headers=auth())
    assert not seen[0].prior_hypotheses and any(r.prior_hypotheses for r in seen[1:])


def test_max_steps_terminates_a_looping_agent(settings, store, p204):
    from fastapi.testclient import TestClient

    from app.api.main import create_app
    from app.container import build_container
    from app.llm.mock_provider import LoopingMockLLM

    c = TestClient(create_app(build_container(settings, store=store, llm=LoopingMockLLM())))
    r = c.post("/diagnose/quick", json=p204, headers=auth()).json()
    assert r["status"] == "max_steps_reached" and r["steps"] == settings.quick_max_steps
    r2 = c.post("/diagnose/extended", json={**p204, "incident_id": "INC-LOOP"}, headers=auth()).json()
    assert r2["steps"] == settings.extended_max_steps


def test_hypotheses_never_become_observations(client, container, p204):
    client.post("/diagnose", json=p204, headers=auth())
    inc = container.memory.read_incident(ANA, "INC-204")
    causes = {h["cause"] for h in inc["hypotheses"]}
    assert causes and all(o["name"] not in causes and o["source"].startswith("tool:") for o in inc["observations"])


def test_p204_observations_are_the_scenario_values(client, p204):
    body = client.post("/diagnose", json=p204, headers=auth()).json()
    obs = {o["name"]: o["value"] for o in body["observations"]}
    assert obs["bearing_temperature"] == 86.0 and obs["vibration"] == 8.4 and obs["discharge_pressure"] == 2.8
    assert body["hypotheses"][0]["cause"] == "bearing_wear"
    assert "FH-012" in body["hypotheses"][0]["evidence_ids"]


def test_node_timings_are_reported(client, p204):
    t = client.post("/diagnose", json=p204, headers=auth()).json()["node_timings_ms"]
    assert {"load_incident", "retrieve", "reason", "tools", "diagnose", "persist"} <= set(t)


def test_toolcall_model_roundtrip():
    assert ReasoningOutput(tool_calls=[ToolCall(name="x")]).tool_calls[0].arguments == {}
