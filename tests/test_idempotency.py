import pytest

from eig import Candidate, CandidateType, Coordinator, CoordinatorService, SQLiteRegistry


def test_service_rejects_replayed_persistent_mutation(tmp_path):
    store = SQLiteRegistry(tmp_path / "coordinator.sqlite")
    first = CoordinatorService(Coordinator("run-1", registry=store))
    candidate = Candidate("c1", CandidateType.ALGO_SINGLE, "single", "thesis", "catalyst", "day")
    first.idempotent("request-1", "candidate", lambda: first.coordinator.register_candidate(candidate))
    second = CoordinatorService(Coordinator("run-1", registry=store))
    with pytest.raises(ValueError, match="already processed"):
        second.idempotent("request-1", "candidate", lambda: (_ for _ in ()).throw(AssertionError("mutation replayed")))
    store.close()


def test_failed_mutation_releases_persistent_key(tmp_path):
    store = SQLiteRegistry(tmp_path / "coordinator.sqlite")
    service = CoordinatorService(Coordinator("run-1", registry=store))
    with pytest.raises(RuntimeError):
        service.idempotent("request-2", "candidate", lambda: (_ for _ in ()).throw(RuntimeError("temporary")))
    assert service.idempotent("request-2", "candidate", lambda: "retried") == "retried"
    store.close()