from eig import Candidate, CandidateType, Coordinator, CoordinatorMetrics, CoordinatorService, snapshot


def test_metrics_snapshot_counts_state_without_sensitive_fields():
    service = CoordinatorService(Coordinator("run-1"))
    service.coordinator.register_candidate(Candidate("c1", CandidateType.ALGO_SINGLE, "single", "thesis", "catalyst", "day"))
    metrics = service.metrics()
    assert isinstance(metrics, CoordinatorMetrics)
    assert metrics.candidates == 1
    assert metrics.candidates_by_state == {"DISCOVERED": 1}
    assert "account" not in metrics.as_dict()