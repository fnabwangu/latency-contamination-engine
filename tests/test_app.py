import pytest
from fastapi.testclient import TestClient

from eig import CoordinatorService, create_app


def test_http_adapter_exposes_coordinator_surface():
    try:
        app = create_app(CoordinatorService())
    except RuntimeError:
        pytest.skip("fastapi is not installed")
    routes = {route.path for route in app.routes}
    expected = {
        "/health", "/candidates", "/meeting-surface", "/queue", "/metrics",
        "/lcaes/detect", "/gates/evaluate", "/exposure/evaluate",
        "/conviction/assess",
        "/trade-sets", "/handoffs/trade-tf", "/handoffs/algo-tf", "/handoffs/execution", "/candidates/{candidate_id}/sleeves/{sleeve_id}/algo",
        "/candidates/{candidate_id}/transition", "/evidence",
        "/runs", "/runs/{run_id}/tasks", "/runs/{run_id}/packets", "/runs/{run_id}/advance", "/runs/{run_id}/dispositions",
        "/evidence/{evidence_id}", "/packets", "/coverage",
        "/coverage/{factor}", "/independence",
        "/candidates/{candidate_id}/outcome", "/ui",
        "/candidates/{candidate_id}/proposal", "/proposals/{proposal_id}/approve",
    }
    assert expected <= routes
    assert not any("broker" in path for path in routes)
    client = TestClient(app)
    assert client.get("/ui/components.js").status_code == 200
    assert client.get("/ui/components.css").status_code == 200


def test_http_candidates_recover_from_configured_sqlite(tmp_path):
    try:
        first = TestClient(create_app(database_path=str(tmp_path / "coordinator.sqlite")))
    except RuntimeError:
        pytest.skip("fastapi is not installed")
    payload = {
        "candidate_id": "http-1", "candidate_type": "ALGO_SINGLE",
        "name": "HTTP candidate", "thesis": "test thesis",
        "catalyst": "test catalyst", "horizon": "one day",
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
    packet = {
        "run_id": client.get("/health").json()["run_id"], "agent_id": "MACRO",
        "role": "macro", "as_of": now,
        "valid_until": "2026-09-04T00:05:00+00:00", "confidence": 0.8,
        "vote": "SUPPORT",
    }
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


def test_http_conviction_assessment_returns_range_ev_and_fragility():
    try:
        client = TestClient(create_app())
    except RuntimeError:
        pytest.skip("fastapi is not installed")
    response = client.post("/conviction/assess", json={"strategy_family": "momentum", "successes": 10, "failures": 5, "expected_gain": "100", "expected_loss": "60", "costs": "5", "features": {"trend": "0.5", "mfe": "0.4", "mae": "0.2"}})
    assert response.status_code == 200
    assert response.json()["probability_range"]
    assert "expected_value" in response.json()
    assert response.json()["uncertainty"]["model"] == "0.2"


def test_http_creates_validated_trade_set():
    try:
        client = TestClient(create_app())
    except RuntimeError:
        pytest.skip("fastapi is not installed")
    sleeve = {"sleeve_id": "s1", "instrument": "NBIS", "side": "BUY", "role": "equity", "thesis": "thesis", "catalyst": "catalyst", "entry": "breakout", "target": "45", "invalidation": "below 36", "expected_gain": "100", "expected_loss": "50"}
    response = client.post("/trade-sets", headers={"Idempotency-Key": "set-1"}, json={"candidate_id": "set-http", "name": "Set", "thesis": "thesis", "catalyst": "catalyst", "horizon": "week", "sleeves": [sleeve]})
    assert response.status_code == 201
    assert response.json()["aggregate_risk"] == "50"


def test_http_promotes_sleeve_to_independent_algo():
    try:
        client = TestClient(create_app())
    except RuntimeError:
        pytest.skip("fastapi is not installed")
    sleeve = {"sleeve_id": "s2", "instrument": "NBIS", "side": "BUY", "role": "equity", "thesis": "thesis", "catalyst": "catalyst", "entry": "breakout", "target": "45", "invalidation": "below 36", "expected_gain": "100", "expected_loss": "50"}
    created = client.post("/trade-sets", headers={"Idempotency-Key": "set-2"}, json={"candidate_id": "set-promotion", "name": "Set", "thesis": "thesis", "catalyst": "catalyst", "horizon": "week", "sleeves": [sleeve]})
    assert created.status_code == 201
    promoted = client.post("/candidates/set-promotion/sleeves/s2/algo", headers={"Idempotency-Key": "algo-2"})
    assert promoted.status_code == 201
    assert promoted.json()["candidate_type"] == "ALGO_SINGLE"
    assert promoted.json()["probability"] is None


def test_http_transition_enforces_lifecycle_and_version():
    try:
        client = TestClient(create_app())
    except RuntimeError:
        pytest.skip("fastapi is not installed")
    payload = {"candidate_id": "transition-1", "candidate_type": "ALGO_SINGLE", "name": "Transition", "thesis": "thesis", "catalyst": "catalyst", "horizon": "day"}
    assert client.post("/candidates", json=payload).status_code == 201
    response = client.post("/candidates/transition-1/transition", json={"state": "RESEARCHING", "reason": "assign research", "expected_version": 0}, headers={"Idempotency-Key": "transition-1"})
    assert response.status_code == 200
    assert response.json()["version"] == 1
    stale = client.post("/candidates/transition-1/transition", json={"state": "VIABLE", "reason": "stale", "expected_version": 0}, headers={"Idempotency-Key": "transition-2"})
    assert stale.status_code == 409


def test_http_run_lifecycle_requires_owned_packets_and_dispositions():
    try:
        client = TestClient(create_app())
    except RuntimeError:
        pytest.skip("fastapi is not installed")
    frame = {"candidate_ids": ["c1"], "forecast": "target before stop", "horizon": "week", "catalyst_clock": "earnings", "required_roles": ["MACRO", "BITO"], "required_dissent_role": "BITO"}
    created = client.post("/runs", json=frame, headers={"Idempotency-Key": "run-1"})
    assert created.status_code == 201
    run_id = created.json()["run_id"]
    assert client.post(f"/runs/{run_id}/tasks", json={"task_id": "macro", "role": "macro", "owner": "MACRO"}, headers={"Idempotency-Key": "task-1"}).status_code == 201
    assert client.post(f"/runs/{run_id}/tasks", json={"task_id": "dissent", "role": "BITO", "owner": "BITO", "depends_on": ["macro"]}, headers={"Idempotency-Key": "task-2"}).status_code == 201
    now = "2026-09-04T00:00:00+00:00"
    for agent, key in (("MACRO", "packet-1"), ("BITO", "packet-2")):
        packet = {"run_id": run_id, "agent_id": agent, "role": agent, "candidate_ids": ["c1"], "as_of": now, "valid_until": "2026-09-04T00:05:00+00:00", "confidence": 0.6, "vote": "SUPPORT"}
        assert client.post(f"/runs/{run_id}/packets", json=packet, headers={"Idempotency-Key": key}).status_code == 201
    assert client.post(f"/runs/{run_id}/advance", json={"phase": "POOL"}, headers={"Idempotency-Key": "advance-1"}).status_code == 200
    assert client.post(f"/runs/{run_id}/advance", json={"phase": "CHALLENGE"}, headers={"Idempotency-Key": "advance-2"}).status_code == 200
    assert client.post(f"/runs/{run_id}/advance", json={"phase": "DECIDE"}, headers={"Idempotency-Key": "advance-3"}).status_code == 200
    assert client.post(f"/runs/{run_id}/dispositions", json={"candidate_id": "c1", "disposition": "USE"}, headers={"Idempotency-Key": "disposition-1"}).status_code == 200
    assert client.post(f"/runs/{run_id}/advance", json={"phase": "COMPLETE"}, headers={"Idempotency-Key": "advance-4"}).status_code == 200
