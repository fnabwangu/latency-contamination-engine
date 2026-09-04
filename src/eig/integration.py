"""Coordinator contracts for external Trade-TF, Algo-TF, and execution systems."""

from __future__ import annotations

import hashlib
import json
import uuid
from dataclasses import dataclass
from enum import Enum
from typing import Protocol

from .coordinator import Candidate, CandidateType, Sleeve


class HandoffTarget(str, Enum):
    TRADE_TF = "TRADE_TF"
    ALGO_TF = "ALGO_TF"
    EXECUTION_ENGINE = "EXECUTION_ENGINE"


class HandoffStatus(str, Enum):
    READY = "READY"
    SENT = "SENT"
    ACKNOWLEDGED = "ACKNOWLEDGED"
    REJECTED = "REJECTED"


@dataclass(frozen=True)
class CoordinatorHandoff:
    handoff_id: str
    candidate_id: str
    target: HandoffTarget
    payload: dict[str, object]
    payload_hash: str
    status: HandoffStatus = HandoffStatus.READY
    source_handoff_id: str | None = None


class ExternalCoordinator(Protocol):
    def receive(self, handoff: CoordinatorHandoff) -> HandoffStatus:
        """Receive a handoff; the external system owns its own lifecycle."""


class CoordinatorRouter:
    """Build handoffs without importing or implementing external agent state."""

    def __init__(self, trade_tf: ExternalCoordinator | None = None, algo_tf: ExternalCoordinator | None = None, execution_engine: ExternalCoordinator | None = None) -> None:
        self.connectors = {HandoffTarget.TRADE_TF: trade_tf, HandoffTarget.ALGO_TF: algo_tf, HandoffTarget.EXECUTION_ENGINE: execution_engine}
        self.handoffs: dict[str, CoordinatorHandoff] = {}

    def to_trade_tf(self, candidate: Candidate) -> CoordinatorHandoff:
        if candidate.candidate_type is not CandidateType.BRANDED_TRADE_SET:
            raise ValueError("Trade-TF handoff requires a Branded Trade Set")
        return self._create(candidate.candidate_id, HandoffTarget.TRADE_TF, {"thesis": candidate.thesis, "catalyst": candidate.catalyst, "horizon": candidate.horizon, "sleeve_ids": [sleeve.sleeve_id for sleeve in candidate.sleeves]})

    def to_algo_tf(self, candidate: Candidate, sleeve: Sleeve) -> CoordinatorHandoff:
        if sleeve not in candidate.sleeves:
            raise ValueError("Algo-TF handoff sleeve is not part of the candidate")
        return self._create(candidate.candidate_id, HandoffTarget.ALGO_TF, {"sleeve_id": sleeve.sleeve_id, "instrument": sleeve.instrument, "side": sleeve.side, "thesis": sleeve.thesis, "catalyst": sleeve.catalyst, "entry": sleeve.entry, "target": sleeve.target, "invalidation": sleeve.invalidation})

    def to_execution_engine(self, candidate_id: str, proposal_id: str, payload_hash: str) -> CoordinatorHandoff:
        if not proposal_id or len(payload_hash) != 64:
            raise ValueError("execution handoff requires proposal ID and payload hash")
        return self._create(candidate_id, HandoffTarget.EXECUTION_ENGINE, {"proposal_id": proposal_id, "payload_hash": payload_hash})

    def send(self, handoff_id: str) -> HandoffStatus:
        handoff = self.handoffs[handoff_id]
        connector = self.connectors[handoff.target]
        if connector is None:
            raise ValueError(f"no connector configured for {handoff.target.value}")
        status = connector.receive(handoff)
        self.handoffs[handoff_id] = CoordinatorHandoff(handoff.handoff_id, handoff.candidate_id, handoff.target, handoff.payload, handoff.payload_hash, status, handoff.source_handoff_id)
        return status

    def _create(self, candidate_id: str, target: HandoffTarget, payload: dict[str, object], source_handoff_id: str | None = None) -> CoordinatorHandoff:
        handoff_id = uuid.uuid4().hex[:12]
        encoded = json.dumps(payload, sort_keys=True, separators=(",", ":"))
        handoff = CoordinatorHandoff(handoff_id, candidate_id, target, payload, hashlib.sha256(encoded.encode()).hexdigest(), source_handoff_id=source_handoff_id)
        self.handoffs[handoff_id] = handoff
        return handoff