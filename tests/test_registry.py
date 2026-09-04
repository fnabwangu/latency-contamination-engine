from decimal import Decimal

from datetime import timedelta

from eig import Candidate, CandidateState, CandidateType, Coordinator, LifecycleEvent, SQLiteRegistry, Sleeve
from eig.types import utcnow


def test_sqlite_registry_recovers_candidate_and_event(tmp_path):
    path = tmp_path / "coordinator.sqlite"
    candidate = Candidate(
        "persisted-1",
        CandidateType.ALGO_SINGLE,
        "NBIS single",
        "bottleneck demand",
        "earnings",
        "one week",
        state=CandidateState.WATCHING,
        probability=Decimal("0.58"),
        probability_range=(Decimal("0.48"), Decimal("0.68")),
        sleeves=(Sleeve("s1", "NBIS", "BUY", "equity", "bottleneck demand", "earnings", "breakout", "45", "below 36", Decimal("500"), Decimal("200")),),
    )
    store = SQLiteRegistry(path)
    store.save_candidate(candidate)
    store.append_event(LifecycleEvent("persisted-1", CandidateState.VIABLE, CandidateState.WATCHING, "trigger pending"))
    store.close()

    recovered = SQLiteRegistry(path)
    assert recovered.load_candidate("persisted-1") == candidate
    assert recovered.load_events("persisted-1")[0].to_state is CandidateState.WATCHING
    recovered.close()


def test_coordinator_writes_and_recovers_its_lifecycle(tmp_path):
    store = SQLiteRegistry(tmp_path / "coordinator.sqlite")
    first = Coordinator("run-1", registry=store)
    first.register_candidate(Candidate("c1", CandidateType.ALGO_SINGLE, "single", "thesis", "catalyst", "day"))
    first.transition("c1", CandidateState.RESEARCHING, "coverage")
    store.close()

    recovered_store = SQLiteRegistry(tmp_path / "coordinator.sqlite")
    recovered = Coordinator("run-1", registry=recovered_store)
    assert recovered.get_candidate("c1").state is CandidateState.RESEARCHING
    assert len(recovered.events) == 2
    recovered_store.close()


def test_proposal_hash_survives_restart(tmp_path):
    store = SQLiteRegistry(tmp_path / "coordinator.sqlite")
    first = Coordinator("run-1", registry=store)
    first.register_candidate(Candidate("c1", CandidateType.ALGO_SINGLE, "single", "thesis", "catalyst", "day", state=CandidateState.READY))
    proposal = first.generate_execution_proposal("c1", "NBIS", "BUY", Decimal("2"), Decimal("20"), Decimal("25"), "breakout", utcnow() + timedelta(hours=1))
    store.close()
    recovered_store = SQLiteRegistry(tmp_path / "coordinator.sqlite")
    recovered = Coordinator("run-1", registry=recovered_store)
    assert recovered.proposals[proposal.proposal_id].payload_hash == proposal.payload_hash
    recovered_store.close()