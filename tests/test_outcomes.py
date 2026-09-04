from decimal import Decimal

from eig import Candidate, CandidateType, Coordinator, ShadowOutcome, SQLiteRegistry


def test_shadow_outcome_survives_restart(tmp_path):
    store = SQLiteRegistry(tmp_path / "coordinator.sqlite")
    first = Coordinator("run-1", registry=store)
    first.register_candidate(Candidate("c1", CandidateType.ALGO_SINGLE, "single", "thesis", "catalyst", "day"))
    outcome = first.record_outcome(ShadowOutcome("c1", "DISCARDED", realized_return=Decimal("12")))
    store.close()
    recovered_store = SQLiteRegistry(tmp_path / "coordinator.sqlite")
    recovered = Coordinator("run-1", registry=recovered_store)
    assert recovered.outcomes["c1"] == outcome
    recovered_store.close()