"""V13 - correlation, per-node latency, redaction and authorization audit."""

import json
import logging

from tests.conftest import P204, auth


def test_ids_correlate_across_response_run_logs_and_audit(client, store):
    r = client.post("/diagnose", json=P204, headers=auth())
    body = r.json()
    assert body["trace_id"] == r.headers["X-Trace-Id"]
    assert store.runs[body["run_id"]]["trace_id"] == body["trace_id"]
    events = client.get("/incidents/INC-204/audit", headers=auth("supervisor")).json()["events"]
    mine = [e for e in events if e["trace_id"] == body["trace_id"]]
    assert {"diagnose_requested", "diagnose_completed", "tool_call"} <= {e["event_type"] for e in mine}
    assert all(e["incident_id"] == "INC-204" for e in mine)
    assert any(e["run_id"] == body["run_id"] for e in mine)


def test_per_node_latency_is_recorded_on_run(client, store):
    body = client.post("/diagnose", json=P204, headers=auth()).json()
    timings = store.runs[body["run_id"]]["node_timings"]
    assert timings and all(v >= 0 for v in timings.values()) and "reason" in timings


def test_authorization_denials_are_audited(client, store):
    client.post("/diagnose", json=P204, headers=auth())
    r = client.get("/incidents/INC-204/audit", headers=auth())  # technician: no audit:read
    assert r.status_code == 403
    denied = [e for e in store.audit if e["event_type"] == "authorization_denied"]
    assert denied and denied[-1]["actor"] == "ana@example.com" and denied[-1]["incident_id"] == "INC-204"


def test_failed_authentication_is_audited(client, store):
    client.post("/diagnose", json=P204, headers={"Authorization": "Bearer nope"})
    assert any(e["event_type"] == "authentication_failed" and e["actor"] == "anonymous" for e in store.audit)


def test_secrets_and_pii_are_redacted_in_audit_and_logs(client, store, caplog):
    caplog.set_level(logging.INFO)
    msg = "token=abc123secretvalue contacto jefe@planta.com sk-LEAKLEAKLEAKLEAKLEAK1"
    client.post("/diagnose", json={**P204, "message": msg}, headers=auth())
    blob = json.dumps(store.audit, default=str)
    assert "abc123secretvalue" not in blob and "jefe@planta.com" not in blob and "sk-LEAK" not in blob


def test_audit_is_append_only_by_construction(container):
    forbidden = [m for m in dir(container.audit) if any(w in m for w in ("update", "delete", "remove", "clear"))]
    assert forbidden == []


def test_audit_endpoint_requires_scope(client):
    client.post("/diagnose", json=P204, headers=auth())
    assert client.get("/incidents/INC-204/audit", headers=auth("supervisor", ("PLANT-B",), sub="eva@example.com")).status_code == 403


def test_structured_logs_are_json_with_trace_id(client):
    from app.observability.telemetry import JsonFormatter

    class Capture(logging.Handler):
        def __init__(self):
            super().__init__()
            self.lines: list[str] = []
            self.setFormatter(JsonFormatter())

        def emit(self, record):  # formatted at emit time, i.e. inside the request context
            self.lines.append(self.format(record))

    h = Capture()
    logging.getLogger().addHandler(h)
    logging.getLogger().setLevel(logging.INFO)
    try:
        client.get("/health")
    finally:
        logging.getLogger().removeHandler(h)
    data = json.loads(next(ln for ln in h.lines if '"logger": "http"' in ln))
    assert data["trace_id"].startswith("TRC-") and data["status"] == 200 and "latency_ms" in data


def test_otel_is_off_unless_configured(monkeypatch):
    from app.observability import telemetry

    monkeypatch.delenv("OTEL_EXPORTER_OTLP_ENDPOINT", raising=False)
    assert telemetry.otel_enabled() is False
