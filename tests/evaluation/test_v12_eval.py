"""V12 - golden + adversarial evaluation: reproducible with mocks, gated, and NOT vacuous."""

import json
from pathlib import Path

import pytest

from app.evaluation import runner
from app.governance.policies import PolicyEngine

DATA = Path(__file__).resolve().parents[2] / "data"


@pytest.fixture(scope="module")
def card():
    return runner.run_all()


def test_dataset_sizes_match_the_plan():
    golden = json.loads((DATA / "evaluations/golden.json").read_text())
    assert len(golden) == 25
    cats = {c["category"] for c in golden}
    assert cats == {"positive", "ambiguous", "no_evidence", "authorization_denied"}
    assert len(list((DATA / "attacks").glob("*.json"))) == 10
    assert len(json.loads((DATA / "history/failures.json").read_text())) == 30
    assert len(json.loads((DATA / "sensors/readings.json").read_text())) == 20
    assert len(json.loads((DATA / "equipment/equipment.json").read_text())) == 5
    assert len(json.loads((DATA / "manuals/manuals.json").read_text())) == 5
    assert len(json.loads((DATA / "procedures/procedures.json").read_text())) == 10
    assert len(json.loads((DATA / "equipment/profiles.json").read_text())) == 3


def test_all_golden_cases_pass(card):
    assert card["failures"] == [], card["failures"]
    assert card["golden_pass_rate"] == 1.0


def test_all_adversarial_cases_are_blocked(card):
    assert card["adversarial_blocked"] == card["adversarial_total"] == 10


def test_scorecard_has_required_metrics(card):
    for k in ("citation_validity", "tool_call_validity", "authorization_accuracy", "latency_p50_ms", "latency_p95_ms", "estimated_cost_usd"):
        assert k in card
    assert card["citation_validity"] == 1.0 and "ESTIMATE" in card["cost_note"]


def test_results_are_reproducible():
    a, b = runner.run_all(), runner.run_all()
    for k in ("golden_passed", "adversarial_blocked", "citation_validity", "estimated_cost_usd"):
        assert a[k] == b[k]


# ---- negative controls: if a defence is removed, the harness MUST notice
def test_harness_detects_missing_server_side_authorization(monkeypatch):
    monkeypatch.setattr("app.mcp.server.authorize_tool", lambda *a, **k: None)
    monkeypatch.setattr("app.mcp.tool_gateway.authorize_tool", lambda *a, **k: None)
    assert runner.ADVERSARIAL["ATK-04"](), "cross-plant tool read should have been flagged"


def test_harness_detects_a_policy_that_allows_plc_control(monkeypatch):
    from app.governance.policies import Decision

    monkeypatch.setattr(PolicyEngine, "decide", lambda self, t: Decision("allow", "low", "broken", self.version))
    assert runner.ADVERSARIAL["ATK-06"](), "executed setpoint change should have been flagged"


def test_harness_flags_a_wrong_expectation():
    case = json.loads((DATA / "evaluations/golden.json").read_text())[0]
    assert runner._check_golden(case)["failures"] == []
    case["expect"]["top_cause"] = "cavitation"  # deliberately wrong expectation
    assert any("top cause" in f for f in runner._check_golden(case)["failures"])
    case["expect"] = {"http": 403}
    assert runner._check_golden(case)["authz_ok"] is False
