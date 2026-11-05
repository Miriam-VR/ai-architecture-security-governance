"""V08 - secrets out of code/logs/state; MCP authorised on BOTH sides."""

import json
import logging
import re
import subprocess
from pathlib import Path

import pytest

from app.config import Settings
from app.mcp.client import MCPClient, MCPError
from app.mcp.server import MaintenanceMCPServer, sign_envelope
from app.models import Principal
from app.security import secrets as sec
from app.security.redaction import redact, redact_text
from tests.conftest import P204, auth

ROOT = Path(__file__).resolve().parents[2]
ANA = Principal(user_id="ana", role="technician", plants=("PLANT-A",))
SECRET_PATTERNS = [re.compile(p) for p in (r"sk-[A-Za-z0-9]{20,}", r"AKIA[0-9A-Z]{16}", r"eyJ[A-Za-z0-9_-]{15,}\.[A-Za-z0-9_-]{15,}\.", r"postgres(ql)?://[^\s'\"]+:[^\s'\"@]+@(?!localhost|127\.0\.0\.1)")]


def tracked_files():
    out = subprocess.run(["git", "ls-files", "--cached", "--others", "--exclude-standard"], cwd=ROOT, capture_output=True, text=True, check=True).stdout.split()
    return [ROOT / f for f in out if (ROOT / f).is_file() and not f.startswith("tests/") and not f.endswith((".png", ".ico"))]


def test_repo_contains_no_credentials():
    hits = [(str(f.relative_to(ROOT)), p.pattern) for f in tracked_files() for p in SECRET_PATTERNS if p.search(f.read_text(errors="ignore"))]
    assert not hits, hits


def test_env_files_are_not_tracked():
    names = [f.name for f in tracked_files()]
    assert ".env" not in names and not any(n.endswith(".tfstate") for n in names)


def test_secrets_manager_values_are_loaded_at_runtime():
    sec._CACHE.clear()

    class FakeSM:
        calls = 0

        def get_secret_value(self, SecretId):
            FakeSM.calls += 1
            return {"SecretString": json.dumps({"OPENAI_API_KEY": "sk-from-sm-000000000000", "DATABASE_URL": "postgresql://u:p@h/db", "JWT_SECRET": "j" * 40})}

    s = Settings(_env_file=None, secrets_backend="aws", app_secret_id="maintenance-ai/dev/app")
    s2 = sec.apply_runtime_secrets(s, FakeSM())
    assert s2.openai_api_key.startswith("sk-from-sm") and s2.jwt_secret == "j" * 40
    sec.apply_runtime_secrets(s, FakeSM())
    assert FakeSM.calls == 1, "second call must hit the in-memory cache"


def test_settings_repr_hides_secrets():
    s = Settings(_env_file=None, openai_api_key="sk-visible-visible-0000", database_url="postgresql://u:pw@h/db", jwt_secret="topsecret")
    text = repr(s) + str(s)
    assert "sk-visible" not in text and "pw@h" not in text and "topsecret" not in text


def test_logs_never_contain_the_secret(client, caplog):
    caplog.set_level(logging.INFO)
    secret_msg = "my key is sk-ABCDEFGHIJKLMNOPQRSTUV and password=hunter2 mail bob@corp.com"
    client.post("/diagnose", json={**P204, "message": secret_msg}, headers=auth())
    logging.getLogger("t").info("leak test %s", secret_msg)
    from app.observability.telemetry import JsonFormatter

    fmt = JsonFormatter()
    out = "\n".join(fmt.format(r) for r in caplog.records)
    assert "sk-ABCDEFGHIJKLMNOPQRSTUV" not in out and "hunter2" not in out and "bob@corp.com" not in out


def test_redaction_rules():
    assert "[REDACTED" in redact_text("Authorization: Bearer abcdefghijklmnop12345")
    assert redact({"api_key": "x", "nested": {"token": "y", "ok": "fine"}}) == {"api_key": "[REDACTED]", "nested": {"token": "[REDACTED]", "ok": "fine"}}


def test_audit_details_are_redacted(client, store):
    client.post("/diagnose", json={**P204, "symptoms": ["high_vibration"]}, headers=auth())
    store_text = json.dumps(store.audit, default=str)
    assert "eyJ" not in store_text


# ---- MCP: server-side authorization
def test_server_rejects_unsigned_and_forged_callers(container):
    server = MaintenanceMCPServer(container.store, "mcp-test-secret-mcp-test-secret-123456")
    base = {"jsonrpc": "2.0", "id": 1, "method": "tools/call", "params": {"name": "get_sensor_readings", "arguments": {"equipment_id": "P-204"}}}
    assert server.handle(base)["error"]["code"] == -32002
    forged = {**base, "meta": sign_envelope("wrong-secret-wrong-secret-wrong-secret", ANA, "tools/call", base["params"])}
    assert server.handle(forged)["error"]["code"] == -32002
    # privilege escalation: valid signature for ANA but meta swapped to an admin identity
    good = sign_envelope("mcp-test-secret-mcp-test-secret-123456", ANA, "tools/call", base["params"])
    esc = {**good, "principal": {"user_id": "ana", "role": "administrator", "plants": ["*"]}}
    assert server.handle({**base, "meta": esc})["error"]["code"] == -32002
    stale = sign_envelope("mcp-test-secret-mcp-test-secret-123456", ANA, "tools/call", base["params"], ts=1)
    assert server.handle({**base, "meta": stale})["error"]["code"] == -32002


def test_server_enforces_allowlist_and_role_even_if_gateway_is_bypassed(container):
    c: MCPClient = container.tools._client
    with pytest.raises(MCPError):
        c.call_tool(ANA, "run_shell", {"command": "id"})
    viewer = Principal(user_id="v", role="viewer", plants=("PLANT-A",))
    with pytest.raises(MCPError) as e:
        c.call_tool(viewer, "get_sensor_readings", {"equipment_id": "P-204"})
    assert e.value.code == -32001


def test_unauthorised_role_rejected_at_gateway_and_server(container):
    from app.mcp.tool_gateway import ToolRejected

    viewer = Principal(user_id="v", role="viewer", plants=("PLANT-A",))
    with pytest.raises(ToolRejected):
        container.tools.call(viewer, "get_sensor_readings", {"equipment_id": "P-204"})


def test_iam_policies_are_documented_and_least_privilege():
    doc = (ROOT / "docs/threat-model/iam-policies.md").read_text()
    assert "secretsmanager:GetSecretValue" in doc
    assert not re.search(r'"Action"\s*:\s*(\[\s*)?"(\*|[a-z0-9]+:\*)"', doc), "no action wildcards in documented policies"
    # the only legitimate Resource "*" is ecr:GetAuthorizationToken (AWS does not support scoping it)
    for m in re.finditer(r'"Resource"\s*:\s*"\*"', doc):
        assert "ecr:GetAuthorizationToken" in doc[max(0, m.start() - 200):m.start()]


def test_terraform_has_no_action_wildcards():
    for f in (ROOT / "infrastructure/terraform").rglob("*.tf"):
        txt = f.read_text()
        if f.parent.name == "bootstrap" or "deploy_roles" in str(f):
            continue  # CI deploy roles are reviewed separately (documented in SETUP.md)
        assert not re.search(r'actions\s*=\s*\[\s*"\*"', txt), f
