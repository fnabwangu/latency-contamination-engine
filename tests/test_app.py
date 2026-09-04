import pytest
from fastapi.testclient import TestClient

from eig import CoordinatorService, create_app


def test_http_adapter_exposes_safe_surface():
    try:
        app = create_app(CoordinatorService())
    except RuntimeError:
        pytest.skip("fastapi is not installed")
    routes = {route.path for route in app.routes}
    assert {"/health", "/candidates", "/meeting-surface", "/evidence", "/evidence/{evidence_id}", "/ui", "/candidates/{candidate_id}/proposal", "/proposals/{proposal_id}/approve"} <= routes
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