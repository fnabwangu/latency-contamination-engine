"""Typed coordination inputs and coverage bookkeeping."""

from __future__ import annotations

import uuid
from dataclasses import dataclass, field
from datetime import datetime
from enum import Enum
from typing import Mapping

from .types import utcnow


class Vote(str, Enum):
    SUPPORT = "SUPPORT"
    CONDITIONAL_SUPPORT = "CONDITIONAL_SUPPORT"
    NEUTRAL = "NEUTRAL"
    OPPOSE = "OPPOSE"
    HARD_VETO = "HARD_VETO"
    INSUFFICIENT_DATA = "INSUFFICIENT_DATA"


class CoverageStatus(str, Enum):
    ANSWERED = "ANSWERED"
    ASSIGNED = "ASSIGNED"
    NOT_APPLICABLE = "NOT_APPLICABLE"
    EXPLICITLY_DEFERRED = "EXPLICITLY_DEFERRED"


@dataclass(frozen=True)
class AgentPacket:
    run_id: str
    agent_id: str
    role: str
    candidate_ids: tuple[str, ...]
    as_of: datetime
    valid_until: datetime
    claims: tuple[str, ...] = ()
    evidence_ids: tuple[str, ...] = ()
    unique_evidence: tuple[str, ...] = ()
    shared_evidence: tuple[str, ...] = ()
    known_unknowns: tuple[str, ...] = ()
    requests: tuple[str, ...] = ()
    dependencies: tuple[str, ...] = ()
    contradictions: tuple[str, ...] = ()
    directional_effect: str = "NEUTRAL"
    magnitude: str = "UNKNOWN"
    confidence: float = 0.0
    vote: Vote = Vote.INSUFFICIENT_DATA
    hard_veto: bool = False
    veto_invalidator: str | None = None
    next_action: str = ""
    model_lineage: str = ""
    prompt_version: str = "1"
    source_lineage: tuple[str, ...] = ()
    packet_id: str = field(default_factory=lambda: uuid.uuid4().hex[:12])

    def validate(self) -> None:
        if not 0 <= self.confidence <= 1:
            raise ValueError("packet confidence must be between 0 and 1")
        if self.valid_until <= self.as_of:
            raise ValueError("packet validity must end after as_of")
        if self.hard_veto and (self.vote is not Vote.HARD_VETO or not self.veto_invalidator):
            raise ValueError("hard veto requires HARD_VETO and a named invalidator")


@dataclass(frozen=True)
class CoverageCell:
    factor: str
    status: CoverageStatus
    owner: str | None = None
    packet_ids: tuple[str, ...] = ()


class DecisionCoverageMatrix:
    FACTORS = ("thesis", "catalyst", "regime", "fundamentals", "analogs", "participation", "gex", "flow", "propagation", "dissent", "portfolio_fit", "execution", "account", "authorization")

    def __init__(self) -> None:
        self.cells: dict[str, CoverageCell] = {factor: CoverageCell(factor, CoverageStatus.EXPLICITLY_DEFERRED) for factor in self.FACTORS}

    def assign(self, factor: str, owner: str) -> CoverageCell:
        self._check_factor(factor)
        cell = CoverageCell(factor, CoverageStatus.ASSIGNED, owner)
        self.cells[factor] = cell
        return cell

    def answer(self, factor: str, owner: str, packet_id: str) -> CoverageCell:
        self._check_factor(factor)
        cell = CoverageCell(factor, CoverageStatus.ANSWERED, owner, (packet_id,))
        self.cells[factor] = cell
        return cell

    def unanswered(self, required: tuple[str, ...] | None = None) -> tuple[str, ...]:
        factors = required or self.FACTORS
        return tuple(factor for factor in factors if self.cells[factor].status not in {CoverageStatus.ANSWERED, CoverageStatus.NOT_APPLICABLE})

    def _check_factor(self, factor: str) -> None:
        if factor not in self.cells:
            raise KeyError(factor)


@dataclass(frozen=True)
class IndependenceRecord:
    agent_id: str
    provider: str
    model_version: str
    prompt_version: str
    tool_lineage: tuple[str, ...] = ()
    shared_upstream: tuple[str, ...] = ()
    feature_lineage: tuple[str, ...] = ()
    error_correlation: float = 0.0
    calibration: str = "UNKNOWN"
    config_version: str = "1"
