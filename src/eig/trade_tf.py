"""Trade-TF strategy mandate and float lifecycle.

Trade-TF can manage an approved strategy float, but it cannot submit broker
orders. Broker authority remains exclusively with RootExecutionEngine.
"""

from __future__ import annotations

import hashlib
import json
import uuid
from dataclasses import dataclass, replace
from decimal import Decimal
from enum import Enum
from typing import Mapping


class StrategyState(str, Enum):
    DRAFT = "DRAFT"
    PROPOSED = "PROPOSED"
    APPROVED = "APPROVED"
    ENTERING = "ENTERING"
    MONITORING = "MONITORING"
    REDUCING = "REDUCING"
    EXITING = "EXITING"
    COMPLETED = "COMPLETED"
    HALTED = "HALTED"
    REVOKED = "REVOKED"


class StrategyError(ValueError):
    """A strategy mandate or float operation violates its authority bounds."""


@dataclass(frozen=True)
class StrategyRiskBounds:
    max_loss: Decimal
    max_gross_exposure: Decimal
    max_position_count: int

    def __post_init__(self) -> None:
        if self.max_loss <= 0 or self.max_gross_exposure <= 0 or self.max_position_count <= 0:
            raise StrategyError("strategy risk bounds must be positive")


@dataclass(frozen=True)
class StrategyMandate:
    mandate_id: str
    candidate_id: str
    thesis: str
    allowed_instruments: tuple[str, ...]
    allowed_sides: tuple[str, ...]
    horizon: str
    bounds: StrategyRiskBounds
    state: StrategyState = StrategyState.DRAFT
    payload_hash: str = ""
    approval_hash: str | None = None
    version: int = 0

    def payload(self) -> Mapping[str, object]:
        return {"mandate_id": self.mandate_id, "candidate_id": self.candidate_id, "thesis": self.thesis, "allowed_instruments": self.allowed_instruments, "allowed_sides": self.allowed_sides, "horizon": self.horizon, "max_loss": str(self.bounds.max_loss), "max_gross_exposure": str(self.bounds.max_gross_exposure), "max_position_count": self.bounds.max_position_count}

    def with_hash(self) -> "StrategyMandate":
        digest = hashlib.sha256(json.dumps(self.payload(), sort_keys=True, separators=(",", ":")).encode()).hexdigest()
        return replace(self, payload_hash=digest)


@dataclass(frozen=True)
class FloatPosition:
    instrument: str
    side: str
    exposure: Decimal
    worst_case_loss: Decimal


@dataclass(frozen=True)
class StrategyFloat:
    mandate_id: str
    positions: tuple[FloatPosition, ...] = ()

    @property
    def gross_exposure(self) -> Decimal:
        return sum((abs(position.exposure) for position in self.positions), Decimal("0"))

    @property
    def worst_case_loss(self) -> Decimal:
        return sum((position.worst_case_loss for position in self.positions), Decimal("0"))


_TRANSITIONS = {
    StrategyState.DRAFT: {StrategyState.PROPOSED, StrategyState.REVOKED},
    StrategyState.PROPOSED: {StrategyState.APPROVED, StrategyState.REVOKED},
    StrategyState.APPROVED: {StrategyState.ENTERING, StrategyState.HALTED, StrategyState.REVOKED},
    StrategyState.ENTERING: {StrategyState.MONITORING, StrategyState.HALTED, StrategyState.EXITING},
    StrategyState.MONITORING: {StrategyState.REDUCING, StrategyState.EXITING, StrategyState.HALTED, StrategyState.COMPLETED},
    StrategyState.REDUCING: {StrategyState.MONITORING, StrategyState.EXITING, StrategyState.HALTED},
    StrategyState.EXITING: {StrategyState.COMPLETED, StrategyState.HALTED},
    StrategyState.HALTED: {StrategyState.EXITING, StrategyState.REVOKED},
}


class TradeTF:
    """Manage approved strategy state and float risk without broker authority."""

    def __init__(self) -> None:
        self.mandates: dict[str, StrategyMandate] = {}
        self.floats: dict[str, StrategyFloat] = {}

    def create_mandate(self, candidate_id: str, thesis: str, instruments: tuple[str, ...], sides: tuple[str, ...], horizon: str, bounds: StrategyRiskBounds) -> StrategyMandate:
        if not candidate_id or not thesis or not instruments or not sides or any(side not in {"BUY", "SELL"} for side in sides):
            raise StrategyError("mandate requires thesis, instruments, and BUY/SELL sides")
        mandate = StrategyMandate(uuid.uuid4().hex[:12], candidate_id, thesis, instruments, sides, horizon, bounds).with_hash()
        self.mandates[mandate.mandate_id] = mandate
        self.floats[mandate.mandate_id] = StrategyFloat(mandate.mandate_id)
        return mandate

    def transition(self, mandate_id: str, state: StrategyState, expected_version: int | None = None) -> StrategyMandate:
        mandate = self.mandates[mandate_id]
        if expected_version is not None and mandate.version != expected_version:
            raise StrategyError("strategy mandate version conflict")
        if state is not mandate.state and state not in _TRANSITIONS.get(mandate.state, set()):
            raise StrategyError(f"illegal strategy transition {mandate.state} -> {state}")
        updated = replace(mandate, state=state, version=mandate.version + 1)
        self.mandates[mandate_id] = updated
        return updated

    def approve(self, mandate_id: str, payload_hash: str) -> StrategyMandate:
        mandate = self.mandates[mandate_id]
        if mandate.payload_hash != payload_hash:
            raise StrategyError("approval hash does not match strategy mandate")
        if mandate.state is not StrategyState.PROPOSED:
            raise StrategyError("only proposed strategy mandates can be approved")
        updated = replace(mandate, state=StrategyState.APPROVED, approval_hash=payload_hash, version=mandate.version + 1)
        self.mandates[mandate_id] = updated
        return updated

    def add_position(self, mandate_id: str, position: FloatPosition) -> StrategyFloat:
        mandate = self.mandates[mandate_id]
        if mandate.state not in {StrategyState.APPROVED, StrategyState.ENTERING, StrategyState.MONITORING, StrategyState.REDUCING}:
            raise StrategyError("strategy float is not active for position changes")
        if position.instrument not in mandate.allowed_instruments or position.side not in mandate.allowed_sides:
            raise StrategyError("position is outside strategy mandate")
        strategy_float = replace(self.floats[mandate_id], positions=self.floats[mandate_id].positions + (position,))
        if len(strategy_float.positions) > mandate.bounds.max_position_count or strategy_float.gross_exposure > mandate.bounds.max_gross_exposure or strategy_float.worst_case_loss > mandate.bounds.max_loss:
            raise StrategyError("strategy float exceeds risk bounds")
        self.floats[mandate_id] = strategy_float
        return strategy_float

    def revoke(self, mandate_id: str) -> StrategyMandate:
        mandate = self.mandates[mandate_id]
        if mandate.state in {StrategyState.COMPLETED, StrategyState.REVOKED}:
            raise StrategyError("terminal strategy mandate cannot be revoked")
        return self.transition(mandate_id, StrategyState.REVOKED)