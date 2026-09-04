from decimal import Decimal

import pytest

from eig import Candidate, CandidateState, CandidateType, Coordinator, CoordinatorRouter, HandoffStatus, HandoffTarget, Sleeve


class Connector:
    def receive(self, handoff):
        assert len(handoff.payload_hash) == 64
        return HandoffStatus.ACKNOWLEDGED


def candidate():
    sleeve = Sleeve("s1", "NBIS", "BUY", "equity", "thesis", "catalyst", "breakout", "45", "36", Decimal("100"), Decimal("50"))
    return Candidate("c1", CandidateType.BRANDED_TRADE_SET, "Set", "thesis", "catalyst", "week", sleeves=(sleeve,))


def test_router_targets_external_systems_without_owning_their_state():
    router = CoordinatorRouter(Connector(), Connector(), Connector())
    trade = router.to_trade_tf(candidate())
    algo = router.to_algo_tf(candidate(), candidate().sleeves[0])
    execution = router.to_execution_engine("c1", "p1", "a" * 64)
    assert trade.target is HandoffTarget.TRADE_TF
    assert algo.target is HandoffTarget.ALGO_TF
    assert router.send(trade.handoff_id) is HandoffStatus.ACKNOWLEDGED
    assert execution.target is HandoffTarget.EXECUTION_ENGINE


def test_queue_preserves_nonterminal_coordinator_ideas():
    coordinator = Coordinator()
    coordinator.register_candidate(candidate())
    coordinator.register_candidate(Candidate("c2", CandidateType.ALGO_SINGLE, "Done", "thesis", "catalyst", "day", state=CandidateState.DISCARDED))
    assert [item.candidate_id for item in coordinator.queue()] == ["c1"]
    with pytest.raises(ValueError):
        router = CoordinatorRouter()
        router.to_algo_tf(candidate(), Sleeve("wrong", "NBIS", "BUY", "equity", "thesis", "catalyst", "entry", "target", "stop", Decimal("1"), Decimal("1")))