"""PgStore against a real Postgres + pgvector. Skipped unless TEST_DATABASE_URL is set.

  docker run -d --name pgv -e POSTGRES_PASSWORD=pw -p 54329:5432 pgvector/pgvector:pg16
  export TEST_DATABASE_URL=postgresql://postgres:pw@localhost:54329/postgres
  python scripts/apply_migrations.py --seed --stub-auth
"""

import os

import psycopg2
import pytest
from fastapi.testclient import TestClient

from app.api.main import create_app
from app.container import build_container
from app.llm.embeddings import HashEmbedder
from app.retrieval.ingest import ingest
from tests.conftest import P204, auth, make_settings

DSN = os.getenv("TEST_DATABASE_URL")
pytestmark = pytest.mark.skipif(not DSN, reason="TEST_DATABASE_URL not set")


@pytest.fixture
def pg():
    from app.store.postgres import PgStore

    conn = psycopg2.connect(DSN)
    conn.autocommit = True
    with conn.cursor() as cur:
        cur.execute("alter table audit_events disable trigger audit_events_no_update")
        cur.execute("truncate audit_events, approvals, action_requests, hypotheses, observations, agent_runs, incidents, policy_versions cascade")
        cur.execute("alter table audit_events enable trigger audit_events_no_update")
    store = PgStore(DSN, pool_max=3)
    ingest(store, HashEmbedder(1536))
    yield store
    store.close()
    conn.close()


@pytest.fixture
def pgclient(pg):
    return TestClient(create_app(build_container(make_settings(store_mode="memory"), store=pg)))


def test_vector_search_is_scoped_and_relevant(pg):
    emb = HashEmbedder(1536).embed("high_vibration high_bearing_temperature low_discharge_pressure pump")
    hits = pg.search_chunks(emb, "PLANT-A", "pump", 5, 0.12)
    assert hits and hits[0].source_id == "FH-012" and all(h.plant_id in (None, "PLANT-A") for h in hits)


def test_full_flow_on_postgres(pgclient, pg):
    r = pgclient.post("/diagnose", json=P204, headers=auth()).json()
    assert r["hypotheses"][0]["cause"] == "bearing_wear" and r["observations"]
    assert pgclient.post("/diagnose", json=P204, headers=auth()).json()["resumed"] is True
    apid = next(a for a in r["proposed_actions"] if a["action_type"] == "publish_work_order")["approval_id"]
    assert pgclient.post(f"/approvals/{apid}/approve", headers=auth("supervisor")).status_code == 200
    assert pgclient.post(f"/approvals/{apid}/approve", headers=auth("supervisor")).status_code == 409
    states = {a["action_type"]: a["status"] for a in pg.list_actions("INC-204")}
    assert states == {"draft_work_order": "executed", "publish_work_order": "executed"}
    assert pgclient.get("/incidents/INC-204/audit", headers=auth("supervisor")).json()["events"]


def test_cross_plant_blocked_on_postgres(pgclient):
    assert pgclient.post("/diagnose", json={**P204, "plant_id": "PLANT-B", "equipment_id": "P-305", "incident_id": "INC-305"}, headers=auth()).status_code == 403


def test_audit_table_is_append_only_in_the_database(pg):
    pg.append_audit({"event_id": "AUD-x", "event_type": "t", "actor": "a", "details": {}})
    with pytest.raises(psycopg2.Error):
        pg._exec("update audit_events set actor='evil' where event_id='AUD-x'")
    with pytest.raises(psycopg2.Error):
        pg._exec("delete from audit_events where event_id='AUD-x'")


def test_duplicate_idempotency_key_is_rejected_atomically(pg):
    pg.create_incident({"incident_id": "INC-D", "plant_id": "PLANT-A", "equipment_id": "P-204", "symptoms": [], "created_by": "ana"})
    base = {"incident_id": "INC-D", "plant_id": "PLANT-A", "run_id": None, "action_type": "draft_work_order", "params": {}, "risk": "low",
            "status": "queued", "idempotency_key": "k1", "policy_version": "v1", "created_by": "ana"}
    _, created1 = pg.insert_action({**base, "action_id": "ACT-1"})
    row2, created2 = pg.insert_action({**base, "action_id": "ACT-2"})
    assert created1 and not created2 and row2["action_id"] == "ACT-1"
    assert pg.transition_action("ACT-1", "queued", "executing") is True
    assert pg.transition_action("ACT-1", "queued", "executing") is False
