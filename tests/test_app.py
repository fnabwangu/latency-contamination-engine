import pytest
from fastapi.testclient import TestClient

from eig import CoordinatorService, create_app


def test_http_adapter_exposes_safe_surface():
    try:
        app = create_app(CoordinatorService())
    except RuntimeError:
        pytest.skip("fastapi is not installed")
    routes = {route.path for route in app.routes}
    assert {"/health", "/candidates", "/meeting-surface", "/metrics", "/lcaes/detect", "/gates/evaluate", "/exposure/evaluate", "/trade-sets", "/evidence", "/evidence/{evidence_id}", "/packets", "/coverage", "/coverage/{factor}", "/independence", "/candidates/{candidate_id}/outcome", "/ui", "/candidates/{candidate_id}/proposal", "/proposals/{proposal_id}/approve"} <= routes
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
    assert client.post("/coverage/regime", json={"owner": "MACRO", "packet_id": packet_id}, headers={"Idempotency-Key": "coverage-1"}).status_code == 200
    assert client.post("/independence", json={"agent_id": "MACRO", "provider": "local", "model_version": "1", "prompt_version": "1", "error_correlation": 0.1}).status_code == 201


def test_mutations_require_configured_key_and_idempotency(monkeypatch):
    try:
        monkeypatch.setenv("EIG_API_KEY", "test-key")
        client = TestClient(create_app())
    except RuntimeError:
        pytest.skip("fastapi is not installed")
    payload = {"candidate_id": "auth-1", "candidate_type": "ALGO_SINGLE", "name": "Auth candidate", "thesis": "thesis", "catalyst": "catalyst", "horizon": "day"}
    assert client.post("/candidates", json=payload).status_code == 401
    headers = {"X-API-Key": "test-key", "Idempotency-Key": "candidate-auth-1"}
    first = client.post("/candidates", json=payload, headers=headers)
    second = client.post("/candidates", json=payload, headers=headers)
    assert first.status_code == second.status_code == 201
    assert first.json()["candidate_id"] == second.json()["candidate_id"] == "auth-1"


def test_http_tenant_scope_is_enforced(monkeypatch):
    try:
        monkeypatch.setenv("EIG_TENANT_ID", "alpha")
        client = TestClient(create_app())
    except RuntimeError:
        pytest.skip("fastapi is not installed")
    assert client.get("/health", headers={"X-Tenant-ID": "beta"}).status_code == 403
    response = client.post("/candidates", headers={"X-Tenant-ID": "alpha"}, json={"candidate_id": "tenant-1", "candidate_type": "ALGO_SINGLE", "name": "Tenant candidate", "thesis": "thesis", "catalyst": "catalyst", "horizon": "day"})
    assert response.status_code == 201
    assert response.json()["tenant_id"] == "alpha"


def test_http_gate_evaluation_separates_warning_and_blocker():
    try:
        client = TestClient(create_app())
    except RuntimeError:
        pytest.skip("fastapi is not installed")
    request = {"definitions": [{"gate_id": "warning", "gate_class": "WARNING", "stage": "execution", "owner": "Root"}, {"gate_id": "quote", "gate_class": "EXECUTION_HARD", "stage": "execution", "owner": "Root"}], "results": {"warning": "WARN", "quote": "UNKNOWN"}, "stage": "execution"}
    response = client.post("/gates/evaluate", json=request, headers={"Idempotency-Key": "gates-1"})
    assert response.status_code == 200
    assert response.json()["blocked"] is True
    assert len(response.json()["warnings"]) == 1


def test_http_creates_validated_trade_set():
    try:
        client = TestClient(create_app())
    except RuntimeError:
        pytest.skip("fastapi is not installed")
    sleeve = {"sleeve_id": "s1", "instrument": "NBIS", "side": "BUY", "role": "equity", "thesis": "thesis", "catalyst": "catalyst", "entry": "breakout", "target": "45", "invalidation": "below 36", "expected_gain": "100", "expected_loss": "50"}
    response = client.post("/trade-sets", headers={"Idempotency-Key": "set-1"}, json={"candidate_id": "set-http", "name": "Set", "thesis": "thesis", "catalyst": "catalyst", "horizon": "week", "sleeves": [sleeve]})
    assert response.status_code == 201
    assert response.json()["aggregate_risk"] == "50"