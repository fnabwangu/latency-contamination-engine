import pytest

from eig import CoordinatorService, create_app


def test_http_adapter_exposes_safe_surface():
    try:
        app = create_app(CoordinatorService())
    except RuntimeError:
        pytest.skip("fastapi is not installed")
    routes = {route.path for route in app.routes}
    assert {"/health", "/candidates", "/meeting-surface", "/ui", "/candidates/{candidate_id}/proposal", "/proposals/{proposal_id}/approve"} <= routes
    assert not any("broker" in path for path in routes)