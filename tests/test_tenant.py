from eig import Candidate, CandidateState, CandidateType, Coordinator, SQLiteRegistry


def test_coordinator_filters_persisted_candidates_by_tenant(tmp_path):
    store = SQLiteRegistry(tmp_path / "coordinator.sqlite")
    Coordinator("run-a", registry=store, tenant_id="alpha").register_candidate(Candidate("shared", CandidateType.ALGO_SINGLE, "Alpha", "thesis", "catalyst", "day", tenant_id="alpha"))
    Coordinator("run-b", registry=store, tenant_id="beta").register_candidate(Candidate("shared-beta", CandidateType.ALGO_SINGLE, "Beta", "thesis", "catalyst", "day", tenant_id="beta"))
    alpha = Coordinator("run-a", registry=store, tenant_id="alpha")
    assert tuple(alpha.candidates) == ("shared",)
    try:
        alpha.register_candidate(Candidate("wrong", CandidateType.ALGO_SINGLE, "Wrong", "thesis", "catalyst", "day", tenant_id="beta"))
    except ValueError as error:
        assert "different tenant" in str(error)
    else:
        raise AssertionError("cross-tenant candidate was accepted")
    store.close()