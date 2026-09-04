from datetime import datetime, timedelta, timezone
from decimal import Decimal

from eig import Candidate, CandidateState, CandidateType, Coordinator, CoordinatorService, GateClass, GateDefinition, GateResult, InformationValue, OpportunityClock, ResearchDecision, Sleeve


def test_service_exposes_full_coordinator_contract():
    service = CoordinatorService(Coordinator("run-1"))
    sleeve = Sleeve("s1", "NBIS", "BUY", "equity", "thesis", "catalyst", "breakout", "45", "36", Decimal("100"), Decimal("50"))
    service.coordinator.register_candidate(Candidate("c1", CandidateType.BRANDED_TRADE_SET, "Set", "thesis", "catalyst", "week", state=CandidateState.VIABLE, sleeves=(sleeve,)))
    assert service.build_trade_set("c1").aggregate_risk == Decimal("50")
    child = service.promote_sleeve_to_algo("c1", "s1")
    assert child.candidate_type is CandidateType.ALGO_SINGLE
    decision = service.evaluate_gate_graph((GateDefinition("warning", GateClass.WARNING, "execution", "Root"),), {"warning": GateResult.WARN}, "execution")
    assert not decision.blocked
    now = datetime.now(timezone.utc)
    assert service.stop_or_continue_research(OpportunityClock(now + timedelta(hours=1)), InformationValue(Decimal("1"), Decimal("10"), Decimal("1"), Decimal("0")), now) is ResearchDecision.CONTINUE