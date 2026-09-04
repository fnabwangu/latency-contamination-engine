import pytest
from fastapi.testclient import TestClient

from eig import CoordinatorService, create_app


def test_http_adapter_exposes_safe_surface():
    try:
        app = create_app(CoordinatorService())
    except RuntimeError:
        pytest.skip("fastapi is not installed")
    routes = {route.path for route in app.routes}
    assert {"/health", "/candidates", "/meeting-surface", "/evidence", "/evidence/{evidence_id}", "/packets", "/coverage", "/coverage/{factor}", "/independence", "/ui", "/candidates/{candidate_id}/proposal", "/proposals/{proposal_id}/approve"} <= routes
    assert not any("broker" in path for path in routes)


def test_http_candidates_recover_from_configured_sqlite(tmp_path):
    try:
        first = TestClient(create_app(database_path=str(tmp_path / "coordinator.sqlite")))
    except RuntimeError:
        pytest.skip("fastapi is not installed")
    payload = {
        "candidate_id": "http-1",
        "candidate_type": "ALGO_SINGLE",
        "name": "HTTP candidate",
        "thesis": "test thesis",
        "catalyst": "test catalyst",
        "horizon": "one day",
    }
    assert first.post("/candidates", json=payload).status_code == 201
    second = TestClient(create_app(database_path=str(tmp_path / "coordinator.sqlite")))
    assert second.get("/candidates").json()[0]["candidate_id"] == "http-1"


def test_http_packet_coverage_and_independence_flow():
    try:
        client = TestClient(create_app())
    except RuntimeError:
        pytest.skip("fastapi is not installed")
    now = "2026-09-04T00:00:00+00:00"
    packet = {"run_id": client.get("/health").json()["run_id"], "agent_id": "MACRO", "role": "macro", "as_of": now, "valid_until": "2026-09-04T00:05:00+00:00", "confidence": 0.8, "vote": "SUPPORT"}
    response = client.post("/packets", json=packet)
    assert response.status_code == 201
    packet_id = response.json()["packet_id"]
    assert client.post("/coverage/regime", json={"owner": "MACRO", "packet_id": packet_id}).status_code == 200
    assert client.post("/independence", json={"agent_id": "MACRO", "provider": "local", "model_version": "1", "prompt_version": "1", "error_correlation": 0.1}).status_code == 201