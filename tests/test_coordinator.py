from datetime import timedelta
from decimal import Decimal

import pytest

from eig import (
    ApprovalError,
    Candidate,
    CandidateState,
    CandidateType,
    Coordinator,
    GateClass,
    GateDefinition,
    GateResult,
    Sleeve,
)
from eig.types import utcnow


def candidate(state=CandidateState.DISCOVERED):
    return Candidate("trade-1", CandidateType.BRANDED_TRADE_SET, "Labor compression", "adoption expands margins", "earnings", "quarter", state=state)


def test_warning_does_not_block_stage_but_unknown_required_does():
    coordinator = Coordinator()
    definitions = (
        GateDefinition("spread", GateClass.WARNING, "execution", "Root"),
        GateDefinition("quote", GateClass.EXECUTION_HARD, "execution", "Root"),
    )
    evaluations = coordinator.evaluate_gates("trade-1", definitions, {"spread": GateResult.WARN, "quote": GateResult.UNKNOWN}, "execution")
    assert coordinator.stage_blocked(evaluations)
    warning_only = [evaluations[0]]
    assert not coordinator.stage_blocked(warning_only)


def test_execution_blocker_preserves_candidate_and_requires_exact_hash():
    coordinator = Coordinator()
    coordinator.register_candidate(candidate(CandidateState.READY))
    coordinator.account_available = False
    proposal = coordinator.generate_execution_proposal("trade-1", "NBIS", "BUY", Decimal("10"), Decimal("100"), Decimal("120"), "above VWAP", utcnow() + timedelta(hours=1))
    assert coordinator.candidates["trade-1"].state is CandidateState.BLOCKED
    with pytest.raises(ApprovalError):
        coordinator.approve_exact(proposal.proposal_id, "wrong")
    with pytest.raises(ApprovalError):
        coordinator.approve_exact(proposal.proposal_id, proposal.payload_hash)
    assert coordinator.candidates["trade-1"].state is CandidateState.BLOCKED


def test_failed_package_can_rescue_independent_algo_child():
    coordinator = Coordinator()
    coordinator.register_candidate(candidate(CandidateState.VIABLE))
    sleeve = Sleeve("s-1", "NBIS", "BUY", "equity", "bottleneck demand", "earnings", "breakout", "45", "below 36", Decimal("500"), Decimal("200"))
    child = coordinator.rescue_sleeve("trade-1", sleeve)
    assert child.candidate_type is CandidateType.ALGO_SINGLE
    assert child.sleeves[0].source_candidate_id == "trade-1"
    assert child.probability is None


def test_lifecycle_is_legal_and_audit_is_append_only():
    coordinator = Coordinator()
    coordinator.register_candidate(candidate())
    coordinator.transition("trade-1", CandidateState.RESEARCHING, "coverage assigned")
    coordinator.transition("trade-1", CandidateState.VIABLE, "package fields complete")
    assert [event.to_state for event in coordinator.events] == [CandidateState.DISCOVERED, CandidateState.RESEARCHING, CandidateState.VIABLE]
    with pytest.raises(ValueError):
        coordinator.transition("trade-1", CandidateState.ACTIVE, "skip authorization")


def test_score_and_decimal_size_are_explicit():
    result = Coordinator.score(Decimal("0.6"), Decimal("300"), Decimal("100"), Decimal("10"))
    assert result.expected_value == Decimal("130")
    assert result.break_even_probability == Decimal("0.25")
    assert Coordinator.size(Decimal("250"), Decimal("80")) == Decimal("3")


def test_registry_operations_expose_disposition_and_audit():
    coordinator = Coordinator()
    coordinator.register_candidate(candidate())
    coordinator.detect_lcae("trade-1", "coverage", "discovery", ("MACRO",), (), "MEDIUM", "assign missing factor")
    coordinator.set_disposition("trade-1", CandidateState.BACK_BURNER, "awaiting catalyst")
    audit = coordinator.audit_view("trade-1")
    assert coordinator.list_candidates()[0].state is CandidateState.BACK_BURNER
    assert audit["lcaes"][0].category == "coverage"