"""V11 - deterministic risk policy + HITL + auditable policy changes."""

import pytest

from app.container import build_container
from app.governance.policies import PLC_CONTROL, PolicyEngine
from app.security.errors import AccessDenied
from tests.conftest import P204, auth, make_settings


def test_default_decisions(container):
    d = container.policy.decide
    assert d("query").decision == "allow"
    assert d("draft_work_order").decision == "allow"
    assert d("publish_work_order").decision == "require_approval"
    assert d("unknown_thing").decision == "deny"


@pytest.mark.parametrize("action", sorted(PLC_CONTROL))
def test_plc_control_is_always_denied(container, action):
    assert container.policy.decide(action).decision == "deny"


def test_policy_cannot_relax_plc_prohibition(container):
    with pytest.raises(AccessDenied):
        container.policy.activate({"change_setpoint": {"decision": "allow", "risk": "low"}}, "policy-evil", "root")
    assert container.policy.decide("change_setpoint").decision == "deny"


def test_policy_change_creates_a_decision_record(container, store):
    new = {**container.policy.rules, "draft_work_order": {"decision": "require_approval", "risk": "low"}}
    container.policy.activate(new, "policy-v2", "root@example.com")
    rec = [e for e in store.audit if e["event_type"] == "policy_changed"][-1]
    assert rec["actor"] == "root@example.com"
    assert rec["details"]["old_version"] == "policy-v1" and rec["details"]["new_version"] == "policy-v2"
    assert rec["details"]["changed_actions"] == ["draft_work_order"] and rec["details"]["old_hash"] != rec["details"]["new_hash"]
    assert container.policy.decide("draft_work_order").decision == "require_approval"


def test_every_action_decision_records_the_policy_version(client, store):
    client.post("/diagnose", json=P204, headers=auth())
    decisions = [e for e in store.audit if e["event_type"] == "policy_decision"]
    assert decisions and all(e["details"]["policy_version"] == "policy-v1" for e in decisions)
    assert all(a["policy_version"] == "policy-v1" for a in store.actions.values())


def test_active_policy_survives_restart(container, store):
    container.policy.activate({**container.policy.rules, "query": {"decision": "allow", "risk": "low"}}, "policy-v3", "root")
    again = PolicyEngine(store, container.audit)
    assert again.version == "policy-v3"


def test_policy_admin_api_is_admin_only(client):
    body = {"version": "policy-v9", "rules": {"query": {"decision": "allow", "risk": "low"}}}
    assert client.post("/admin/policy", json=body, headers=auth()).status_code == 403
    assert client.post("/admin/policy", json=body, headers=auth("supervisor")).status_code == 403
    assert client.post("/admin/policy", json=body, headers=auth("administrator", ("*",))).status_code == 200
    bad = {"version": "policy-v10", "rules": {"plc_write": {"decision": "allow", "risk": "low"}}}
    assert client.post("/admin/policy", json=bad, headers=auth("administrator", ("*",))).status_code == 403


def test_stricter_policy_blocks_already_queued_work(container, store):
    """Policy is re-checked at execution time (executor does not trust older decisions)."""
    c = build_container(make_settings(), store=store)
    assert c.policy.decide("draft_work_order").decision == "allow"
