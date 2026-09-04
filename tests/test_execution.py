from datetime import timedelta
from decimal import Decimal

import pytest

from eig import (
    Candidate,
    CandidateState,
    CandidateType,
    Coordinator,
    ExecutionError,
    ExecutionMandate,
    OrderReceipt,
    OrderStatus,
    RootExecutionEngine,
)
from eig.types import utcnow


class FakeBroker:
    def __init__(self):
        self.submitted = []

    def submit(self, proposal):
        self.submitted.append(proposal)
        return OrderReceipt(proposal.proposal_id, OrderStatus.ACCEPTED, "broker-1")


def make_approved():
    coordinator = Coordinator()
    coordinator.register_candidate(Candidate("c1", CandidateType.ALGO_SINGLE, "single", "thesis", "catalyst", "day", state=CandidateState.READY))
    proposal = coordinator.generate_execution_proposal("c1", "NBIS", "BUY", Decimal("2"), Decimal("20"), Decimal("25"), "breakout", utcnow() + timedelta(hours=1))
    return coordinator.approve_exact(proposal.proposal_id, proposal.payload_hash)


def test_root_engine_requires_exact_approval_and_mandate():
    broker = FakeBroker()
    engine = RootExecutionEngine(broker)
    proposal = make_approved()
    mandate = ExecutionMandate("m1", "c1", "NBIS", "BUY", Decimal("2"), Decimal("25"))
    receipt = engine.submit(proposal, mandate)
    assert receipt.status is OrderStatus.ACCEPTED
    assert broker.submitted == [proposal]
    with pytest.raises(ExecutionError):
        engine.submit(proposal, ExecutionMandate("m2", "c1", "NBIS", "BUY", Decimal("1"), Decimal("25")))


def test_root_engine_rejects_unconfigured_broker():
    with pytest.raises(ExecutionError):
        RootExecutionEngine().submit(make_approved(), ExecutionMandate("m1", "c1", "NBIS", "BUY", Decimal("2"), Decimal("25")))