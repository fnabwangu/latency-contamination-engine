"""Framework-neutral service facade for embedding the Coordinator."""

from __future__ import annotations

from datetime import datetime

from .coordination import AgentPacket, DecisionCoverageMatrix, IndependenceRecord
from .coordinator import Candidate, Coordinator
from .evidence import EvidenceRecord, EvidenceStore
from .analytics import ShadowOutcome


class CoordinatorService:
    def __init__(self, coordinator: Coordinator | None = None) -> None:
        self.coordinator = coordinator or Coordinator()
        self.packets: dict[str, AgentPacket] = {}
        self.coverage = DecisionCoverageMatrix()
        self.independence: dict[str, IndependenceRecord] = {}
        self.evidence = EvidenceStore()
        self._idempotency: dict[str, object] = {}

    def idempotent(self, key: str | None, operation: str, action):
        """Run a mutation once for a caller-provided idempotency key."""
        if not key:
            return action()
        identity = f"{operation}:{key}"
        if identity in self._idempotency:
            return self._idempotency[identity]
        result = action()
        self._idempotency[identity] = result
        return result

    def start_coordination_run(self) -> str:
        return self.coordinator.run_id

    def submit_agent_packet(self, packet: AgentPacket) -> AgentPacket:
        packet.validate()
        if packet.run_id != self.coordinator.run_id:
            raise ValueError("packet belongs to a different coordination run")
        if packet.packet_id in self.packets:
            raise ValueError(f"duplicate packet {packet.packet_id}")
        self.packets[packet.packet_id] = packet
        return packet

    def get_coverage_matrix(self) -> DecisionCoverageMatrix:
        return self.coverage

    def get_agent_independence(self) -> tuple[IndependenceRecord, ...]:
        return tuple(self.independence.values())

    def register_evidence(self, record: EvidenceRecord) -> EvidenceRecord:
        return self.evidence.register(record)

    def get_evidence(self, evidence_id: str) -> EvidenceRecord:
        return self.evidence.get(evidence_id)

    def record_outcome(self, outcome: ShadowOutcome) -> ShadowOutcome:
        return self.coordinator.record_outcome(outcome)

    def register_independence(self, record: IndependenceRecord) -> IndependenceRecord:
        self.independence[record.agent_id] = record
        return record

    def list_candidates(self) -> tuple[Candidate, ...]:
        return self.coordinator.list_candidates()

    def get_meeting_surface(self) -> tuple[Candidate, ...]:
        return self.coordinator.meeting_surface()

    def get_audit_view(self, candidate_id: str):
        return self.coordinator.audit_view(candidate_id)
