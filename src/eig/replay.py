"""Deterministic safety replays for Coordinator invariants."""

from __future__ import annotations

from datetime import datetime, timezone
from decimal import Decimal

from .coordinator import Candidate, CandidateState, CandidateType, Coordinator, GateClass, GateDefinition, GateResult, Sleeve


def unavailable_account_replay() -> tuple[CandidateState, bool]:
    coordinator = Coordinator()
    coordinator.register_candidate(Candidate("replay-1", CandidateType.ALGO_SINGLE, "Replay single", "thesis", "catalyst", "day", state=CandidateState.READY))
    coordinator.account_available = False
    coordinator.generate_execution_proposal("replay-1", "NBIS", "BUY", Decimal("1"), Decimal("10"), Decimal("10"), "trigger", datetime.now(timezone.utc))
    return coordinator.get_candidate("replay-1").state, bool(coordinator.proposals)


def warning_veto_replay() -> bool:
    evaluations = Coordinator().evaluate_gates("replay-1", (GateDefinition("warning", GateClass.WARNING, "discovery", "agent"),), {"warning": GateResult.WARN}, "discovery")
    return not Coordinator.stage_blocked(evaluations)


def orphaned_sleeve_replay() -> bool:
    coordinator = Coordinator()
    coordinator.register_candidate(Candidate("package-1", CandidateType.BRANDED_TRADE_SET, "Package", "thesis", "catalyst", "week", state=CandidateState.VIABLE))
    child = coordinator.rescue_sleeve("package-1", Sleeve("sleeve-1", "NBIS", "BUY", "equity", "thesis", "catalyst", "breakout", "45", "36", Decimal("100"), Decimal("50")))
    return child.candidate_type is CandidateType.ALGO_SINGLE and child.probability is None