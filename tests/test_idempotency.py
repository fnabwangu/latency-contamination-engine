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