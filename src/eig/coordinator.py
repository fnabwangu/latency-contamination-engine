"""Deterministic temporal and collective-action core for the Trade Coordinator."""

from __future__ import annotations

import hashlib
import json
import uuid
from dataclasses import dataclass, field, replace
from datetime import datetime, timezone
from decimal import Decimal, ROUND_DOWN
from enum import Enum
from typing import Any, Iterable, Mapping

from .types import utcnow
from .analytics import ShadowOutcome


class CandidateType(str, Enum):
    BRANDED_TRADE_SET = "BRANDED_TRADE_SET"
    ALGO_SINGLE = "ALGO_SINGLE"


class CandidateState(str, Enum):
    DISCOVERED = "DISCOVERED"
    RESEARCHING = "RESEARCHING"
    VIABLE = "VIABLE"
    WATCHING = "WATCHING"
    READY = "READY"
    PROPOSED = "PROPOSED"
    BLOCKED = "BLOCKED"
    ARMED = "ARMED"
    ACTIVE = "ACTIVE"
    REDUCING = "REDUCING"
    EXITING = "EXITING"
    COMPLETED = "COMPLETED"
    BACK_BURNER = "BACK_BURNER"
    DISCARDED = "DISCARDED"
    INVALIDATED = "INVALIDATED"
    EXPIRED = "EXPIRED"
    HALTED = "HALTED"
    ARCHIVED = "ARCHIVED"


class GateClass(str, Enum):
    RESEARCH_INVALIDATOR = "RESEARCH_INVALIDATOR"
    PACKAGE_REQUIRED = "PACKAGE_REQUIRED"
    EXECUTION_HARD = "EXECUTION_HARD"
    AUTHORIZATION_HARD = "AUTHORIZATION_HARD"
    CONDITIONAL_TRIGGER = "CONDITIONAL_TRIGGER"
    SIZING_OVERLAY = "SIZING_OVERLAY"
    RANKING_OVERLAY = "RANKING_OVERLAY"
    INFORMATION_REQUIREMENT = "INFORMATION_REQUIREMENT"
    WARNING = "WARNING"


class GateResult(str, Enum):
    PASS = "PASS"
    FAIL = "FAIL"
    WARN = "WARN"
    UNKNOWN = "UNKNOWN"
    NOT_APPLICABLE = "NOT_APPLICABLE"
    STALE = "STALE"


class LCAEStatus(str, Enum):
    OPEN = "OPEN"
    CORRECTED = "CORRECTED"
    RESOLVED = "RESOLVED"


class ApprovalError(ValueError):
    """An execution proposal was not approved as the exact immutable payload."""


@dataclass(frozen=True)
class GateDefinition:
    gate_id: str
    gate_class: GateClass
    stage: str
    owner: str
    required: bool = True
    assets: tuple[str, ...] = ()
    policy_version: str = "1"


@dataclass(frozen=True)
class GateEvaluation:
    gate_id: str
    stage: str
    gate_class: GateClass
    required: bool
    result: GateResult
    reason: str
    inputs: Mapping[str, Any] = field(default_factory=dict)
    evaluated_at: datetime = field(default_factory=utcnow)
    policy_version: str = "1"


@dataclass(frozen=True)
class LifecycleEvent:
    candidate_id: str
    from_state: CandidateState | None
    to_state: CandidateState
    reason: str
    occurred_at: datetime = field(default_factory=utcnow)
    event_id: str = field(default_factory=lambda: uuid.uuid4().hex)


@dataclass(frozen=True)
class Sleeve:
    sleeve_id: str
    instrument: str
    side: str
    role: str
    thesis: str
    catalyst: str
    entry: str
    target: str
    invalidation: str
    expected_gain: Decimal
    expected_loss: Decimal
    liquidity_ok: bool = True
    probability: Decimal | None = None
    source_candidate_id: str | None = None


@dataclass(frozen=True)
class Candidate:
    candidate_id: str
    candidate_type: CandidateType
    name: str
    thesis: str
    catalyst: str
    horizon: str
    state: CandidateState = CandidateState.DISCOVERED
    sleeves: tuple[Sleeve, ...] = ()
    evidence_ids: tuple[str, ...] = ()
    dissent: str = ""
    probability: Decimal | None = None
    probability_range: tuple[Decimal, Decimal] | None = None
    confidence: Decimal | None = None
    expected_value: Decimal | None = None
    conviction: Decimal | None = None
    created_at: datetime = field(default_factory=utcnow)
    tenant_id: str = "default"
    version: int = 0


@dataclass(frozen=True)
class LCAE:
    run_id: str
    candidate_id: str
    category: str
    stage: str
    agents: tuple[str, ...]
    evidence_ids: tuple[str, ...]
    severity: str
    correction: str
    status: LCAEStatus = LCAEStatus.OPEN
    detected_at: datetime = field(default_factory=utcnow)
    counterfactual_outcome: str | None = None


@dataclass(frozen=True)
class ConvictionResult:
    probability_of_success: Decimal | None
    probability_range: tuple[Decimal, Decimal] | None
    confidence_in_estimate: Decimal
    expected_value: Decimal | None
    break_even_probability: Decimal | None
    sensitivity: Mapping[str, Decimal]
    status: str


@dataclass(frozen=True)
class ExecutionProposal:
    proposal_id: str
    proposal_version: int
    candidate_id: str
    instrument: str
    side: str
    quantity: Decimal
    intended_loss: Decimal
    absolute_loss: Decimal
    entry_trigger: str
    expiry: datetime
    payload_hash: str
    state: str = "PROPOSED"


_TRANSITIONS: Mapping[CandidateState, frozenset[CandidateState]] = {
    CandidateState.DISCOVERED: frozenset({CandidateState.RESEARCHING, CandidateState.VIABLE, CandidateState.BACK_BURNER, CandidateState.DISCARDED}),
    CandidateState.RESEARCHING: frozenset({CandidateState.VIABLE, CandidateState.WATCHING, CandidateState.BACK_BURNER, CandidateState.DISCARDED, CandidateState.EXPIRED}),
    CandidateState.VIABLE: frozenset({CandidateState.WATCHING, CandidateState.READY, CandidateState.BACK_BURNER, CandidateState.DISCARDED, CandidateState.INVALIDATED}),
    CandidateState.WATCHING: frozenset({CandidateState.READY, CandidateState.EXPIRED, CandidateState.INVALIDATED, CandidateState.BACK_BURNER}),
    CandidateState.READY: frozenset({CandidateState.PROPOSED, CandidateState.BLOCKED, CandidateState.WATCHING, CandidateState.INVALIDATED}),
    CandidateState.PROPOSED: frozenset({CandidateState.ARMED, CandidateState.BLOCKED, CandidateState.WATCHING}),
    CandidateState.BLOCKED: frozenset({CandidateState.READY, CandidateState.PROPOSED, CandidateState.WATCHING, CandidateState.INVALIDATED}),
    CandidateState.ARMED: frozenset({CandidateState.ACTIVE, CandidateState.BLOCKED, CandidateState.HALTED}),
    CandidateState.ACTIVE: frozenset({CandidateState.REDUCING, CandidateState.EXITING, CandidateState.HALTED, CandidateState.COMPLETED}),
    CandidateState.REDUCING: frozenset({CandidateState.ACTIVE, CandidateState.EXITING, CandidateState.COMPLETED}),
    CandidateState.EXITING: frozenset({CandidateState.COMPLETED}),
}


class Coordinator:
    """In-process registry with append-only events and no broker capability."""

    def __init__(self, run_id: str | None = None, registry: Any | None = None, tenant_id: str = "default") -> None:
        self.run_id = run_id or uuid.uuid4().hex
        self.registry = registry
        if not tenant_id or len(tenant_id) > 128:
            raise ValueError("tenant_id must be non-empty and at most 128 characters")
        self.tenant_id = tenant_id
        self.candidates: dict[str, Candidate] = {}
        self.events: list[LifecycleEvent] = []
        self.gate_evaluations: list[GateEvaluation] = []
        self.lcaes: list[LCAE] = []
        self.proposals: dict[str, ExecutionProposal] = {}
        self.outcomes: dict[str, ShadowOutcome] = {}
        self.kill_switch_locked = False
        self.account_available = True
        if registry is not None:
            self.candidates = {candidate.candidate_id: candidate for candidate in registry.load_candidates() if candidate.tenant_id == tenant_id}
            self.events = [event for candidate in self.candidates.values() for event in registry.load_events(candidate.candidate_id)]
            self.proposals = {proposal.proposal_id: proposal for proposal in registry.load_proposals()}
            self.outcomes = {outcome.candidate_id: outcome for outcome in registry.load_outcomes()}

    def _persist_candidate(self, candidate: Candidate) -> None:
        if self.registry is not None:
            self.registry.save_candidate(candidate)

    def _persist_event(self, event: LifecycleEvent) -> None:
        if self.registry is not None:
            self.registry.append_event(event)

    def register_candidate(self, candidate: Candidate) -> Candidate:
        if candidate.tenant_id != self.tenant_id:
            raise ValueError("candidate belongs to a different tenant")
        if candidate.candidate_id in self.candidates:
            raise ValueError(f"duplicate candidate {candidate.candidate_id}")
        self.candidates[candidate.candidate_id] = candidate
        self._persist_candidate(candidate)
        event = LifecycleEvent(candidate.candidate_id, None, candidate.state, "registered")
        self.events.append(event)
        self._persist_event(event)
        return candidate

    def get_candidate(self, candidate_id: str) -> Candidate:
        return self.candidates[candidate_id]

    def record_outcome(self, outcome: ShadowOutcome) -> ShadowOutcome:
        if outcome.candidate_id not in self.candidates:
            raise KeyError(outcome.candidate_id)
        self.outcomes[outcome.candidate_id] = outcome
        if self.registry is not None:
            self.registry.save_outcome(outcome)
        return outcome

    def list_candidates(self, candidate_type: CandidateType | None = None) -> tuple[Candidate, ...]:
        candidates = self.candidates.values()
        if candidate_type is not None:
            candidates = (candidate for candidate in candidates if candidate.candidate_type is candidate_type)
        return tuple(sorted(candidates, key=lambda candidate: candidate.created_at))

    def set_disposition(self, candidate_id: str, disposition: CandidateState, reason: str) -> Candidate:
        if disposition not in {CandidateState.BACK_BURNER, CandidateState.DISCARDED, CandidateState.ARCHIVED}:
            raise ValueError("disposition must be BACK_BURNER, DISCARDED, or ARCHIVED")
        return self.transition(candidate_id, disposition, reason)

    def audit_view(self, candidate_id: str) -> Mapping[str, Any]:
        if candidate_id not in self.candidates:
            raise KeyError(candidate_id)
        return {
            "candidate": self.candidates[candidate_id],
            "lifecycle": tuple(event for event in self.events if event.candidate_id == candidate_id),
            "gates": tuple(self.gate_evaluations),
            "lcaes": tuple(lcae for lcae in self.lcaes if lcae.candidate_id == candidate_id),
        }

    def transition(self, candidate_id: str, state: CandidateState, reason: str, expected_version: int | None = None) -> Candidate:
        current = self.candidates[candidate_id]
        if expected_version is not None and expected_version != current.version:
            raise ValueError(f"candidate version conflict: expected {expected_version}, current {current.version}")
        if state is not current.state and state not in _TRANSITIONS.get(current.state, frozenset()):
            raise ValueError(f"illegal candidate transition {current.state} -> {state}")
        updated = replace(current, state=state, version=current.version + 1)
        self.candidates[candidate_id] = updated
        self._persist_candidate(updated)
        event = LifecycleEvent(candidate_id, current.state, state, reason)
        self.events.append(event)
        self._persist_event(event)
        return updated

    def evaluate_gates(self, candidate_id: str, definitions: Iterable[GateDefinition], results: Mapping[str, GateResult], stage: str) -> tuple[GateEvaluation, ...]:
        evaluations = []
        for definition in definitions:
            if definition.stage != stage:
                continue
            result = results.get(definition.gate_id, GateResult.UNKNOWN)
            evaluation = GateEvaluation(definition.gate_id, stage, definition.gate_class, definition.required, result, "configured result", policy_version=definition.policy_version)
            evaluations.append(evaluation)
            self.gate_evaluations.append(evaluation)
        return tuple(evaluations)

    @staticmethod
    def stage_blocked(evaluations: Iterable[GateEvaluation]) -> bool:
        return any(e.required and e.gate_class is not GateClass.WARNING and e.result in (GateResult.FAIL, GateResult.UNKNOWN, GateResult.STALE) for e in evaluations)

    @staticmethod
    def discovery_preserved(evaluations: Iterable[GateEvaluation]) -> bool:
        return not any(e.result is GateResult.FAIL and e.stage == "discovery" for e in evaluations)

    def detect_lcae(self, candidate_id: str, category: str, stage: str, agents: Iterable[str], evidence_ids: Iterable[str], severity: str, correction: str) -> LCAE:
        lcae = LCAE(self.run_id, candidate_id, category, stage, tuple(agents), tuple(evidence_ids), severity, correction)
        self.lcaes.append(lcae)
        return lcae

    def rescue_sleeve(self, source_candidate_id: str, sleeve: Sleeve, name: str | None = None) -> Candidate:
        if sleeve.source_candidate_id not in (None, source_candidate_id):
            raise ValueError("sleeve lineage does not match source candidate")
        child_sleeve = replace(sleeve, source_candidate_id=source_candidate_id)
        child = Candidate(uuid.uuid4().hex[:12], CandidateType.ALGO_SINGLE, name or f"{sleeve.instrument} single", sleeve.thesis, sleeve.catalyst, "sleeve horizon", sleeves=(child_sleeve,))
        return self.register_candidate(child)

    @staticmethod
    def score(probability: Decimal, expected_gain: Decimal, expected_loss: Decimal, costs: Decimal = Decimal("0")) -> ConvictionResult:
        if not 0 <= probability <= 1 or expected_gain < 0 or expected_loss < 0:
            raise ValueError("probability and payoff inputs are out of range")
        ev = probability * expected_gain - (Decimal("1") - probability) * expected_loss - costs
        breakeven = expected_loss / (expected_gain + expected_loss) if expected_gain + expected_loss else None
        low = max(Decimal("0"), probability - Decimal("0.1"))
        high = min(Decimal("1"), probability + Decimal("0.1"))
        sensitivity = {"p_low": low * expected_gain - (1 - low) * expected_loss - costs, "p_high": high * expected_gain - (1 - high) * expected_loss - costs}
        return ConvictionResult(probability, (low, high), probability, ev, breakeven, sensitivity, "PROVISIONAL")

    @staticmethod
    def size(permitted_risk: Decimal, risk_per_unit: Decimal) -> Decimal:
        if permitted_risk < 0 or risk_per_unit <= 0:
            raise ValueError("risk values must be positive")
        return (permitted_risk / risk_per_unit).to_integral_value(rounding=ROUND_DOWN)

    def generate_execution_proposal(self, candidate_id: str, instrument: str, side: str, quantity: Decimal, intended_loss: Decimal, absolute_loss: Decimal, entry_trigger: str, expiry: datetime) -> ExecutionProposal:
        execution_blocked = self.kill_switch_locked or not self.account_available
        if execution_blocked and self.candidates[candidate_id].state is not CandidateState.BLOCKED:
            self.transition(candidate_id, CandidateState.BLOCKED, "execution authority unavailable")
        candidate = self.candidates[candidate_id]
        if candidate.state not in (CandidateState.READY, CandidateState.BLOCKED):
            raise ValueError("execution proposals require a READY candidate")
        payload = {"candidate_id": candidate_id, "instrument": instrument, "side": side, "quantity": str(quantity), "intended_loss": str(intended_loss), "absolute_loss": str(absolute_loss), "entry_trigger": entry_trigger, "expiry": expiry.astimezone(timezone.utc).isoformat()}
        digest = hashlib.sha256(json.dumps(payload, sort_keys=True, separators=(",", ":")).encode()).hexdigest()
        proposal = ExecutionProposal(uuid.uuid4().hex[:12], 1, candidate_id, instrument, side, quantity, intended_loss, absolute_loss, entry_trigger, expiry, digest)
        self.proposals[proposal.proposal_id] = proposal
        if self.registry is not None:
            self.registry.save_proposal(proposal)
        if not execution_blocked:
            self.transition(candidate_id, CandidateState.PROPOSED, "proposal generated")
        return proposal

    def approve_exact(self, proposal_id: str, payload_hash: str) -> ExecutionProposal:
        proposal = self.proposals[proposal_id]
        if proposal.payload_hash != payload_hash:
            raise ApprovalError("approval hash does not match the immutable proposal payload")
        if self.kill_switch_locked or not self.account_available:
            raise ApprovalError("execution hard control is unavailable")
        approved = replace(proposal, state="APPROVED")
        self.proposals[proposal_id] = approved
        if self.registry is not None:
            self.registry.save_proposal(approved)
        self.transition(proposal.candidate_id, CandidateState.ARMED, "exact proposal approved")
        return approved

    def meeting_surface(self) -> tuple[Candidate, ...]:
        active = [c for c in self.candidates.values() if c.state not in {CandidateState.ARCHIVED, CandidateState.DISCARDED, CandidateState.COMPLETED}]
        return tuple(sorted(active, key=lambda c: (c.state is CandidateState.BLOCKED, c.created_at))[:3])