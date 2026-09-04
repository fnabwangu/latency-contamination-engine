from eig import Candidate, CandidateType, Coordinator, GateClass, GateDefinition, GateResult, SQLiteRegistry


def test_gate_and_lcae_audit_records_survive_restart(tmp_path):
    store = SQLiteRegistry(tmp_path / "coordinator.sqlite")
    first = Coordinator("run-1", registry=store)
    first.register_candidate(Candidate("c1", CandidateType.ALGO_SINGLE, "single", "thesis", "catalyst", "day"))
    first.evaluate_gates("c1", (GateDefinition("quote", GateClass.EXECUTION_HARD, "execution", "Root"),), {"quote": GateResult.UNKNOWN}, "execution")
    first.detect_lcae("c1", "coverage", "research", ("MACRO",), (), "MEDIUM", "assign owner")
    store.close()
    recovered_store = SQLiteRegistry(tmp_path / "coordinator.sqlite")
    recovered = Coordinator("run-1", registry=recovered_store)
    assert recovered.gate_evaluations[0].result is GateResult.UNKNOWN
    assert recovered.lcaes[0].category == "coverage"
    recovered_store.close()