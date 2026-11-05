from __future__ import annotations

import time

import jwt
import pytest
from fastapi.testclient import TestClient

from app.api.main import create_app
from app.config import Settings
from app.container import Container, build_container
from app.llm.embeddings import HashEmbedder
from app.retrieval.ingest import ingest
from app.store.memory import MemoryStore

JWT_SECRET = "test-secret-test-secret-test-secret-123456"
MCP_SECRET = "mcp-test-secret-mcp-test-secret-123456"


def make_token(sub="ana@example.com", role="technician", plants=("PLANT-A",), *, secret=JWT_SECRET, aud="authenticated", iss=None, exp_in=3600, alg="HS256"):
    claims = {"sub": sub, "aud": aud, "exp": int(time.time()) + exp_in, "app_metadata": {"app_role": role, "plants": list(plants)}}
    if iss:
        claims["iss"] = iss
    return jwt.encode(claims, secret, algorithm=alg)


def auth(role="technician", plants=("PLANT-A",), sub=None):
    sub = sub or {"technician": "ana@example.com", "supervisor": "luis@example.com", "administrator": "root@example.com"}.get(role, f"{role}@example.com")
    return {"Authorization": f"Bearer {make_token(sub, role, plants)}"}


def make_settings(**over) -> Settings:
    base = dict(_env_file=None, jwt_secret=JWT_SECRET, mcp_shared_secret=MCP_SECRET, llm_mode="mock", store_mode="memory")
    return Settings(**{**base, **over})


@pytest.fixture
def settings() -> Settings:
    return make_settings()


@pytest.fixture
def store() -> MemoryStore:
    s = MemoryStore()
    ingest(s, HashEmbedder(1536))
    return s


@pytest.fixture
def container(settings, store) -> Container:
    return build_container(settings, store=store)


@pytest.fixture
def client(container) -> TestClient:
    return TestClient(create_app(container))


P204 = {"incident_id": "INC-204", "equipment_id": "P-204", "plant_id": "PLANT-A",
        "symptoms": ["high_vibration", "high_bearing_temperature", "low_discharge_pressure"],
        "message": "Diagnostica la falla y recomienda verificaciones"}


@pytest.fixture
def p204() -> dict:
    return dict(P204)
