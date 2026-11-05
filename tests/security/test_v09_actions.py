"""V09 - secure memory + approved, idempotent actions."""

from datetime import UTC, datetime, timedelta

import pytest
from fastapi.testclient import TestClient

from app.actions.queue import InlineQueue
from app.api.main import create_app
from app.container import build_container
from app.models import Observation, Principal
from app.security.errors import AccessDenied
from tests.conftest import P204, auth, make_settings

ANA = Principal(user_id="ana@example.com", role="technician", plants=("PLANT-A",))


def _publish(store):
    return next(a for a in store.actions.values() if a["action_type"] == "publish_work_order")


def _setup(client, store):
    r = client.post("/diagnose", json=P204, headers=auth()).json()
    act = _publish(store)
    ap = next(a for a in r["proposed_actions"] if a["action_type"] == "publish_work_order")
    return r, act, ap["approval_id"]


def test_publish_requires_approval_and_nothing_runs_before(client, container, store):
    r, act, apid = _setup(client, store)
    assert act["status"] == "pending_approval" and apid
    assert not [w for w in container.cmms.work_orders.values() if w["mode"] == "published"]
    assert r["status"] == "pending_approval"


def test_draft_is_allowed_without_approval(client, container, store):
    _setup(client, store)
    drafts = [w for w in container.cmms.work_orders.values() if w["mode"] == "draft"]
    assert len(drafts) == 1 and drafts[0]["simulated"] is True


def test_supervisor_approval_executes_exactly_once(client, container, store):
    _, act, apid = _setup(client, store)
    r = client.post(f"/approvals/{apid}/approve", headers=auth("supervisor"))
    assert r.status_code == 200
    assert store.actions[act["action_id"]]["status"] == "executed"
    assert len([w for w in container.cmms.work_orders.values() if w["mode"] == "published"]) == 1


def test_technician_cannot_approve_and_other_plant_supervisor_cannot(client, store):
    _, _, apid = _setup(client, store)
    assert client.post(f"/approvals/{apid}/approve", headers=auth()).status_code == 403
    assert client.post(f"/approvals/{apid}/approve", headers=auth("supervisor", ("PLANT-B",), sub="eva@example.com")).status_code == 403


def test_requester_cannot_approve_own_action(client, store):
    r = client.post("/diagnose", json=P204, headers=auth("supervisor", sub="luis@example.com")).json()
    apid = next(a for a in r["proposed_actions"] if a["action_type"] == "publish_work_order")["approval_id"]
    assert client.post(f"/approvals/{apid}/approve", headers=auth("supervisor", sub="luis@example.com")).status_code == 403


def test_approval_replay_is_rejected(client, container, store):
    _, act, apid = _setup(client, store)
    assert client.post(f"/approvals/{apid}/approve", headers=auth("supervisor")).status_code == 200
    assert client.post(f"/approvals/{apid}/approve", headers=auth("supervisor")).status_code == 409
    assert client.post(f"/approvals/{apid}/reject", headers=auth("supervisor")).status_code == 409
    # re-delivering the same queue message with the consumed approval does nothing
    assert container.executor.execute(act["action_id"], apid) == "duplicate_ignored"
    assert len(container.cmms.work_orders) == 2  # one draft + one published


def test_rejected_action_never_executes(client, container, store):
    _, act, apid = _setup(client, store)
    assert client.post(f"/approvals/{apid}/reject", headers=auth("supervisor")).status_code == 200
    assert store.actions[act["action_id"]]["status"] == "rejected"
    assert container.executor.execute(act["action_id"], apid).startswith(("blocked", "duplicate"))
    assert not [w for w in container.cmms.work_orders.values() if w["mode"] == "published"]


def test_expired_approval_is_refused(client, container, store):
    _, act, apid = _setup(client, store)
    store.approvals[apid]["expires_at"] = (datetime.now(UTC) - timedelta(minutes=1)).isoformat()
    assert client.post(f"/approvals/{apid}/approve", headers=auth("supervisor")).status_code == 409


def test_executor_does_not_trust_the_queue(client, container, store):
    """A forged queue message for a pending action (no approval) must be blocked by the executor re-check."""
    _, act, _ = _setup(client, store)
    store.actions[act["action_id"]]["status"] = "queued"  # attacker/bug forces the status
    assert container.executor.execute(act["action_id"], None) == "blocked:missing_approval"
    other = "APR-forged"
    store.approvals[other] = {"approval_id": other, "action_id": "ACT-other", "status": "approved", "action_hash": "x",
                              "expires_at": (datetime.now(UTC) + timedelta(hours=1)).isoformat()}
    assert container.executor.execute(act["action_id"], other) == "blocked:missing_approval"
    assert not [w for w in container.cmms.work_orders.values() if w["mode"] == "published"]


def test_tampered_params_break_the_approval_hash(client, container, store):
    _, act, apid = _setup(client, store)
    client.post(f"/approvals/{apid}/approve", headers=auth("supervisor"))
    # fresh pending action approved, then params altered in the DB before execution
    store2 = type(store)()
    c2 = build_container(make_settings(), store=store2, queue=InlineQueue())
    c2.queue.handler = None
    cl = TestClient(create_app(c2))
    from app.llm.embeddings import HashEmbedder
    from app.retrieval.ingest import ingest

    ingest(store2, HashEmbedder(1536))
    r = cl.post("/diagnose", json=P204, headers=auth()).json()
    apid2 = next(a for a in r["proposed_actions"] if a["action_type"] == "publish_work_order")["approval_id"]
    act2 = _publish(store2)
    cl.post(f"/approvals/{apid2}/approve", headers=auth("supervisor"))
    store2.actions[act2["action_id"]]["params"]["cause"] = "TAMPERED"
    assert c2.executor.execute(act2["action_id"], apid2) == "blocked:approval_hash_mismatch"


def test_retries_and_duplicate_queue_delivery_do_not_duplicate(store):
    c = build_container(make_settings(), store=store, queue=InlineQueue(deliver_twice=True))
    cl = TestClient(create_app(c))
    from app.llm.embeddings import HashEmbedder
    from app.retrieval.ingest import ingest

    ingest(store, HashEmbedder(1536))
    for _ in range(3):  # client retries the same diagnosis 3 times
        cl.post("/diagnose", json=P204, headers=auth())
    assert len([a for a in store.actions.values() if a["action_type"] == "draft_work_order"]) == 1
    assert len([w for w in c.cmms.work_orders.values() if w["mode"] == "draft"]) == 1
    assert len([a for a in store.actions.values() if a["action_type"] == "publish_work_order"]) == 1


def test_prohibited_actions_are_denied_for_every_role(container):
    for role in ("technician", "supervisor", "administrator"):
        for atype in ("change_setpoint", "plc_write", "stop_equipment"):
            assert container.policy.decide(atype).decision == "deny"
    assert container.policy.decide("something_new").decision == "deny"


# ---- secure memory
def test_cross_plant_memory_write_is_blocked(client, container):
    client.post("/diagnose", json={**P204, "incident_id": "INC-305", "equipment_id": "P-305", "plant_id": "PLANT-B"}, headers=auth("administrator", ("*",)))
    obs = [Observation(name="vibration", value=0.1, source="tool:get_sensor_readings", equipment_id="P-305")]
    with pytest.raises(AccessDenied):
        container.memory.save_observations(ANA, "INC-305", "RUN-x", obs)


def test_memory_rejects_facts_from_untrusted_sources(client, container):
    client.post("/diagnose", json=P204, headers=auth())
    fake = [Observation(name="health", value="perfect", source="llm:reasoning", equipment_id="P-204")]
    with pytest.raises(AccessDenied):
        container.memory.save_observations(ANA, "INC-204", "RUN-x", fake)
    wrong_eq = [Observation(name="vibration", value=1.0, source="tool:get_sensor_readings", equipment_id="P-101")]
    with pytest.raises(AccessDenied):
        container.memory.save_observations(ANA, "INC-204", "RUN-x", wrong_eq)


def test_incident_cannot_be_hijacked_by_reusing_its_id_with_another_plant(client):
    client.post("/diagnose", json=P204, headers=auth())
    r = client.post("/diagnose", json={**P204, "equipment_id": "P-101"}, headers=auth())
    assert r.status_code == 403


def test_every_decision_is_audited(client, store):
    _, act, apid = _setup(client, store)
    client.post(f"/approvals/{apid}/approve", headers=auth("supervisor"))
    kinds = {e["event_type"] for e in store.audit}
    assert {"policy_decision", "approval_requested", "approval_approved", "action_executed"} <= kinds
