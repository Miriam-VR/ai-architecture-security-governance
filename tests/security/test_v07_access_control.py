"""V07 - JWT + RBAC/ABAC. A PLANT-A user can never read PLANT-B through ANY of the four routes."""

import time

import jwt
import pytest

from app.models import Principal
from app.security.errors import AccessDenied
from tests.conftest import JWT_SECRET, P204, auth, make_token

ANA = Principal(user_id="ana", role="technician", plants=("PLANT-A",))
P305 = {"incident_id": "INC-305", "equipment_id": "P-305", "plant_id": "PLANT-B", "symptoms": ["high_vibration"], "message": ""}


def bearer(tok):
    return {"Authorization": f"Bearer {tok}"}


# ---- JWT
@pytest.mark.parametrize("tok", [
    make_token(exp_in=-10),
    make_token(secret="x" * 40),
    make_token(aud="other"),
    jwt.encode({"sub": "a", "aud": "authenticated", "exp": int(time.time()) + 60, "app_metadata": {"app_role": "technician", "plants": ["PLANT-A"]}}, None, algorithm="none"),
    jwt.encode({"sub": "a", "aud": "authenticated", "exp": int(time.time()) + 60}, JWT_SECRET, algorithm="HS256"),  # no role/plants
    "garbage",
])
def test_bad_tokens_are_401(client, tok):
    assert client.post("/diagnose", json=P204, headers=bearer(tok)).status_code == 401


def test_missing_token_is_401(client):
    assert client.post("/diagnose", json=P204).status_code == 401


def test_issuer_is_enforced_when_configured(store):
    from fastapi.testclient import TestClient

    from app.api.main import create_app
    from app.container import build_container
    from tests.conftest import make_settings

    c = TestClient(create_app(build_container(make_settings(jwt_issuer="https://good/auth/v1"), store=store)))
    assert c.post("/diagnose", json=P204, headers=bearer(make_token(iss="https://evil"))).status_code == 401
    assert c.post("/diagnose", json=P204, headers=bearer(make_token(iss="https://good/auth/v1"))).status_code == 200


# ---- four leak routes
def test_route1_endpoint_plant_from_body_is_checked_against_token(client):
    assert client.post("/diagnose", json=P305, headers=auth()).status_code == 403


def test_route1b_reading_other_plant_incident_is_403(client):
    root = auth("administrator", ("*",))
    assert client.post("/diagnose", json=P305, headers=root).status_code == 200
    assert client.get("/incidents/INC-305", headers=auth()).status_code == 403
    assert client.get("/runs/" + client.get("/incidents/INC-305", headers=root).json()["runs"][0]["run_id"], headers=auth()).status_code == 403


def test_route2_rag_other_plant(container):
    with pytest.raises(AccessDenied):
        container.retriever.retrieve(ANA, plant_id="PLANT-B", equipment_id="P-305", symptoms=["high_vibration"])
    with pytest.raises(AccessDenied):  # right plant claimed, but equipment is PLANT-B's
        container.retriever.retrieve(ANA, plant_id="PLANT-A", equipment_id="P-305", symptoms=["high_vibration"])


def test_route3_memory_other_plant(client, container):
    client.post("/diagnose", json=P305, headers=auth("administrator", ("*",)))
    with pytest.raises(AccessDenied):
        container.memory.read_incident(ANA, "INC-305")
    with pytest.raises(AccessDenied):
        container.memory.snapshot(ANA, "INC-305")


def test_route4_mcp_other_plant_gateway_and_server(container):
    from app.mcp.client import MCPClient, MCPError
    from app.mcp.tool_gateway import ToolRejected

    with pytest.raises(ToolRejected) as e:
        container.tools.call(ANA, "get_sensor_readings", {"equipment_id": "P-305"})
    assert e.value.code == "forbidden"
    # bypass the gateway: call the MCP client directly -> the SERVER still refuses
    client = container.tools._client
    assert isinstance(client, MCPClient)
    with pytest.raises(MCPError) as me:
        client.call_tool(ANA, "get_sensor_readings", {"equipment_id": "P-305"})
    assert me.value.code == -32001


def test_admin_wildcard_can_see_all_plants(client):
    assert client.post("/diagnose", json=P305, headers=auth("administrator", ("*",))).status_code == 200


# ---- RBAC
def test_technician_cannot_read_audit_or_approve(client):
    client.post("/diagnose", json=P204, headers=auth())
    assert client.get("/incidents/INC-204/audit", headers=auth()).status_code == 403


def test_supervisor_can_read_audit_of_own_plant_only(client):
    client.post("/diagnose", json=P204, headers=auth())
    client.post("/diagnose", json=P305, headers=auth("administrator", ("*",)))
    sup = auth("supervisor")
    assert client.get("/incidents/INC-204/audit", headers=sup).status_code == 200
    assert client.get("/incidents/INC-305/audit", headers=sup).status_code == 403


def test_unknown_role_gets_nothing(client):
    assert client.post("/diagnose", json=P204, headers=auth("viewer")).status_code == 403


# ---- algorithm confusion
def test_rs256_token_is_rejected_when_only_a_shared_secret_is_configured(client):
    from cryptography.hazmat.primitives.asymmetric import rsa

    key = rsa.generate_private_key(public_exponent=65537, key_size=2048)
    tok = jwt.encode({"sub": "a", "aud": "authenticated", "exp": int(time.time()) + 60, "app_metadata": {"app_role": "technician", "plants": ["PLANT-A"]}}, key, algorithm="RS256")
    assert client.post("/diagnose", json=P204, headers=bearer(tok)).status_code == 401


def test_hs256_token_is_rejected_when_only_jwks_is_configured(store):
    """Classic key-confusion attack: attacker signs HS256 using a public key as the HMAC secret."""
    from fastapi.testclient import TestClient

    from app.api.main import create_app
    from app.container import build_container
    from tests.conftest import make_settings

    c = TestClient(create_app(build_container(make_settings(jwt_secret="", jwt_jwks_url="https://example.invalid/jwks.json"), store=store)))
    forged = make_token(secret="-----BEGIN PUBLIC KEY----- pretend-this-is-the-public-key-material")
    assert c.post("/diagnose", json=P204, headers=bearer(forged)).status_code == 401
