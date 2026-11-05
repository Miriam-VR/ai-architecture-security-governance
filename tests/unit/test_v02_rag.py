"""V02 - RAG: relevant, scoped, citable, no invented sources."""

from app.models import Principal
from app.retrieval.ingest import build_chunks
from tests.conftest import auth

ANA = Principal(user_id="ana", role="technician", plants=("PLANT-A",))
SYM = ["high_vibration", "high_bearing_temperature", "low_discharge_pressure"]


def test_retrieves_relevant_pump_failures_with_source_ids(container):
    chunks = container.retriever.retrieve(ANA, plant_id="PLANT-A", equipment_id="P-204", symptoms=SYM)
    assert chunks and all(c.source_id for c in chunks)
    assert "FH-012" in {c.source_id for c in chunks}
    assert all(c.equipment_type in ("pump", "all") for c in chunks)


def test_never_returns_other_plants(container):
    chunks = container.retriever.retrieve(ANA, plant_id="PLANT-A", equipment_id="P-204", symptoms=SYM)
    assert all(c.plant_id in (None, "PLANT-A") for c in chunks)


def test_chunking_preserves_source_id_for_every_chunk():
    chunks = [c for c, _ in build_chunks()]
    assert len(chunks) >= 50 and all(c.source_id and c.chunk_id for c in chunks)


def test_every_citation_comes_from_retrieval(client, container, p204):
    body = client.post("/diagnose", json=p204, headers=auth()).json()
    retrieved = {c.source_id for c in container.retriever.retrieve(ANA, plant_id="PLANT-A", equipment_id="P-204", symptoms=p204["symptoms"])}
    assert body["citations"] and {c["source_id"] for c in body["citations"]} <= retrieved


def test_invented_citation_from_llm_is_dropped(settings, store, p204):
    from fastapi.testclient import TestClient

    from app.api.main import create_app
    from app.container import build_container
    from app.models import Hypothesis, ReasoningOutput

    class Liar:
        name = "liar"

        def reason(self, req):
            return ReasoningOutput(hypotheses=[Hypothesis(cause="magic", confidence=0.9, evidence_ids=["FH-999"])])

    c = TestClient(create_app(build_container(settings, store=store, llm=Liar())))
    body = c.post("/diagnose", json=p204, headers=auth()).json()
    assert body["hypotheses"] == [] and body["citations"] == [] and body["status"] == "needs_more_data"


def test_no_evidence_means_ask_for_more_data(client, p204):
    r = client.post("/diagnose", json={**p204, "incident_id": "INC-NE", "symptoms": ["unknown_weird_symptom"]}, headers=auth()).json()
    assert r["status"] == "needs_more_data" and r["hypotheses"] == [] and r["recommended_checks"]
