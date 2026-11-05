"""V05 - the same core runs behind Lambda (Mangum, API Gateway REST event) and behind Uvicorn/EC2 (ASGI)."""

import json

import pytest
from fastapi.testclient import TestClient
from mangum import Mangum

from app.api.main import create_app
from app.container import build_container
from tests.conftest import P204 as PAYLOAD
from tests.conftest import auth, make_settings

VOLATILE = {"run_id", "trace_id", "node_timings_ms", "action_id", "approval_id"}


def _strip(o):
    if isinstance(o, dict):
        return {k: _strip(v) for k, v in o.items() if k not in VOLATILE}
    if isinstance(o, list):
        return [_strip(v) for v in o]
    return o


def apigw_event(path: str, body: dict, headers: dict, method: str = "POST") -> dict:
    return {"resource": "/{proxy+}", "path": path, "httpMethod": method, "headers": {"Content-Type": "application/json", **headers},
            "multiValueHeaders": {}, "queryStringParameters": None, "pathParameters": {"proxy": path.lstrip("/")}, "stageVariables": None,
            "requestContext": {"resourcePath": "/{proxy+}", "httpMethod": method, "path": f"/dev{path}", "stage": "dev", "identity": {"sourceIp": "1.2.3.4"}, "requestId": "r1"},
            "body": json.dumps(body), "isBase64Encoded": False}


@pytest.fixture
def two_runtimes(store):
    from app.llm.embeddings import HashEmbedder
    from app.retrieval.ingest import ingest
    from app.store.memory import MemoryStore

    stores = [MemoryStore(), MemoryStore()]
    for s in stores:
        ingest(s, HashEmbedder(1536))
    ec2 = TestClient(create_app(build_container(make_settings(), store=stores[0])))
    lam = Mangum(create_app(build_container(make_settings(), store=stores[1])), lifespan="off")
    return ec2, lam


@pytest.mark.parametrize("route", ["/diagnose/quick", "/diagnose/extended"])
def test_same_diagnosis_on_lambda_and_ec2(two_runtimes, route):
    ec2, lam = two_runtimes
    h = auth()
    r_ec2 = ec2.post(route, json=PAYLOAD, headers=h)
    r_lam = lam(apigw_event(route, PAYLOAD, h), None)
    assert r_ec2.status_code == r_lam["statusCode"] == 200
    assert _strip(r_ec2.json()) == _strip(json.loads(r_lam["body"]))


def test_unauthenticated_is_401_on_both(two_runtimes):
    ec2, lam = two_runtimes
    assert ec2.post("/diagnose/quick", json=PAYLOAD).status_code == 401
    assert lam(apigw_event("/diagnose/quick", PAYLOAD, {}), None)["statusCode"] == 401


def test_lambda_entrypoint_imports_and_exposes_handler():
    import handlers.lambda_api as h

    assert callable(h.handler)


def test_memory_mode_container_is_ready_to_diagnose_out_of_the_box():
    """Regression: `uvicorn app.api.main:app` in memory mode must index the corpus itself (no manual ingest)."""
    c = TestClient(create_app(build_container(make_settings())))
    r = c.post("/diagnose", json=PAYLOAD, headers=auth())
    assert r.status_code == 200 and r.json()["hypotheses"][0]["cause"] == "bearing_wear"
