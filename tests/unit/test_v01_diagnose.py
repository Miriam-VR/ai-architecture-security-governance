"""V01 - FastAPI + LLM provider. Runs offline with the mock provider."""

import httpx
import pytest

from app.api.main import create_app
from app.container import build_container
from app.llm.base import LLMError
from app.llm.openai_provider import OpenAIProvider
from app.models import ReasoningRequest
from tests.conftest import auth


def test_health_is_public(client):
    r = client.get("/health")
    assert r.status_code == 200 and r.json()["status"] == "ok"


def test_diagnose_returns_structured_response(client, p204):
    r = client.post("/diagnose", json=p204, headers=auth())
    assert r.status_code == 200, r.text
    body = r.json()
    for key in ("incident_id", "run_id", "status", "observations", "hypotheses", "recommended_checks", "citations", "proposed_actions", "trace_id"):
        assert key in body
    assert body["incident_id"] == "INC-204" and body["hypotheses"]


def test_invalid_input_is_rejected(client, p204):
    bad = {**p204, "incident_id": "no-valid-id"}
    assert client.post("/diagnose", json=bad, headers=auth()).status_code == 422
    assert client.post("/diagnose", json={**p204, "symptoms": "not-a-list"}, headers=auth()).status_code == 422


def test_llm_failure_becomes_503_without_leaking_details(settings, store, p204):
    class Broken:
        name = "broken"

        def reason(self, req):
            raise LLMError("boom sk-SECRETSECRETSECRET1234")

    from fastapi.testclient import TestClient

    c = TestClient(create_app(build_container(settings, store=store, llm=Broken())))
    r = c.post("/diagnose", json=p204, headers=auth())
    assert r.status_code == 503
    assert "sk-" not in r.text and "boom" not in r.text


def _req():
    return ReasoningRequest(equipment_id="P-204", plant_id="PLANT-A", symptoms=["high_vibration"], user_message="hola", evidence=[], observations=[])


def _provider(handler):
    return OpenAIProvider("sk-test-not-real-0000000000", "gpt-test", transport=httpx.MockTransport(handler))


def test_openai_provider_parses_json_without_network():
    content = '{"hypotheses":[],"recommended_checks":["medir"],"needs_more_data":true}'
    p = _provider(lambda r: httpx.Response(200, json={"choices": [{"message": {"content": content}}], "usage": {"prompt_tokens": 10, "completion_tokens": 5}}))
    out = p.reason(_req())
    assert out.needs_more_data and out.tokens_in == 10


@pytest.mark.parametrize("handler", [
    lambda r: httpx.Response(500, text="upstream sk-LEAKLEAKLEAKLEAK1234"),
    lambda r: httpx.Response(200, json={"choices": [{"message": {"content": "not json"}}]}),
    lambda r: (_ for _ in ()).throw(httpx.ReadTimeout("slow")),
])
def test_openai_provider_maps_errors_to_llmerror(handler):
    with pytest.raises(LLMError) as e:
        _provider(handler).reason(_req())
    assert "sk-" not in str(e.value)


def test_missing_api_key_fails_fast():
    with pytest.raises(LLMError):
        OpenAIProvider("", "gpt-test")
