"""Framework-neutral service facade for embedding the Coordinator."""

from __future__ import annotations

from datetime import datetime
from typing import Mapping

from .coordination import AgentPacket, DecisionCoverageMatrix, IndependenceRecord
from .coordinator import Candidate, Coordinator
from .evidence import EvidenceRecord, EvidenceStore
from .analytics import ShadowOutcome
from .metrics import CoordinatorMetrics, snapshot
from .lcae import detect_packet_errors
from .latency import InformationValue, OpportunityClock, ResearchDecision, choose_research_action
from .gates import GateGraph, StageDecision
from .coordinator import GateDefinition, GateResult, LCAE
from .packages import BrandedTradeSet, build_trade_set, promote_sleeve_to_algo, PackageError
from .integration import CoordinatorHandoff, CoordinatorRouter


class CoordinatorService:
    def __init__(self, coordinator: Coordinator | None = None) -> None:
        self.coordinator = coordinator or Coordinator()
        self.packets: dict[str, AgentPacket] = {}
        self.coverage = DecisionCoverageMatrix()
        self.independence: dict[str, IndependenceRecord] = {}
        self.evidence = EvidenceStore()
        self.router = CoordinatorRouter()
        self._idempotency: dict[str, object] = {}
        if self.coordinator.registry is not None:
            for record in self.coordinator.registry.load_evidence():
                self.evidence.register(record)
            self.packets = {packet.packet_id: packet for packet in self.coordinator.registry.load_packets(self.coordinator.run_id)}
            self.independence = {record.agent_id: record for record in self.coordinator.registry.load_independence()}

    def idempotent(self, key: str | None, operation: str, action):
        """Run a mutation once for a caller-provided idempotency key."""
        if not key:
            return action()
        identity = f"{operation}:{key}"
        if identity in self._idempotency:
            return self._idempotency[identity]
        if self.coordinator.registry is not None and not self.coordinator.registry.claim_idempotency(operation, key):
            raise ValueError(f"idempotency key already processed: {operation}:{key}")
        try:
            result = action()
        except Exception:
            if self.coordinator.registry is not None:
                self.coordinator.registry.release_idempotency(operation, key)
            raise
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
        if self.coordinator.registry is not None:
            self.coordinator.registry.save_packet(packet)
        return packet

    def get_coverage_matrix(self) -> DecisionCoverageMatrix:
        return self.coverage

    def get_agent_independence(self) -> tuple[IndependenceRecord, ...]:
        return tuple(self.independence.values())

    def register_evidence(self, record: EvidenceRecord) -> EvidenceRecord:
        stored = self.evidence.register(record)
        if self.coordinator.registry is not None:
            self.coordinator.registry.save_evidence(stored)
        return stored

    def get_evidence(self, evidence_id: str) -> EvidenceRecord:
        return self.evidence.get(evidence_id)

    def record_outcome(self, outcome: ShadowOutcome) -> ShadowOutcome:
        return self.coordinator.record_outcome(outcome)

    def metrics(self) -> CoordinatorMetrics:
        return snapshot(self.coordinator, packets=len(self.packets), evidence=len(self.evidence.records))

    def detect_lcaes(self):
        detected = detect_packet_errors(self.coordinator.run_id, self.packets.values())
        self.coordinator.lcaes.extend(detected)
        if self.coordinator.registry is not None:
            for lcae in detected:
                self.coordinator.registry.save_lcae(lcae)
        return detected

    def register_independence(self, record: IndependenceRecord) -> IndependenceRecord:
        self.independence[record.agent_id] = record
        if self.coordinator.registry is not None:
            self.coordinator.registry.save_independence(record)
        return record

    def list_candidates(self) -> tuple[Candidate, ...]:
        return self.coordinator.list_candidates()

    def get_meeting_surface(self) -> tuple[Candidate, ...]:
        return self.coordinator.meeting_surface()

    def get_queue(self) -> tuple[Candidate, ...]:
        return self.coordinator.queue()

    def create_trade_tf_handoff(self, candidate_id: str) -> CoordinatorHandoff:
        return self.router.to_trade_tf(self.coordinator.get_candidate(candidate_id))

    def create_algo_tf_handoff(self, candidate_id: str, sleeve_id: str) -> CoordinatorHandoff:
        candidate = self.coordinator.get_candidate(candidate_id)
        sleeve = next((sleeve for sleeve in candidate.sleeves if sleeve.sleeve_id == sleeve_id), None)
        if sleeve is None:
            raise PackageError(f"sleeve {sleeve_id} not found")
        return self.router.to_algo_tf(candidate, sleeve)

    def create_execution_handoff(self, candidate_id: str, proposal_id: str, payload_hash: str) -> CoordinatorHandoff:
        return self.router.to_execution_engine(candidate_id, proposal_id, payload_hash)

    def get_audit_view(self, candidate_id: str):
        return self.coordinator.audit_view(candidate_id)

    def estimate_information_value(self, value: InformationValue):
        return value.net_value

    def stop_or_continue_research(self, clock: OpportunityClock, value: InformationValue, now: datetime, required_unknowns: bool = False, fast_lane: bool = False) -> ResearchDecision:
        return choose_research_action(clock, value, now, required_unknowns, fast_lane)

    def detect_lcae(self, candidate_id: str, category: str, stage: str, agents=(), evidence_ids=(), severity="MEDIUM", correction="") -> LCAE:
        return self.coordinator.detect_lcae(candidate_id, category, stage, agents, evidence_ids, severity, correction)

    def evaluate_gate_graph(self, definitions: tuple[GateDefinition, ...], results: Mapping[str, GateResult], stage: str) -> StageDecision:
        decision = GateGraph(definitions).evaluate(results, stage)
        self.coordinator.gate_evaluations.extend(decision.blockers + decision.warnings + decision.unknowns)
        if self.coordinator.registry is not None:
            for evaluation in decision.blockers + decision.warnings + decision.unknowns:
                self.coordinator.registry.save_gate_evaluation(evaluation)
        return decision

    def score_candidate(self, probability, expected_gain, expected_loss, costs=0):
        return self.coordinator.score(probability, expected_gain, expected_loss, costs)

    def build_trade_set(self, candidate_id: str) -> BrandedTradeSet:
        return build_trade_set(self.coordinator.get_candidate(candidate_id))

    def promote_sleeve_to_algo(self, candidate_id: str, sleeve_id: str):
        candidate = self.coordinator.get_candidate(candidate_id)
        sleeve = next((sleeve for sleeve in candidate.sleeves if sleeve.sleeve_id == sleeve_id), None)
        if sleeve is None:
            raise PackageError(f"sleeve {sleeve_id} not found")
        child = promote_sleeve_to_algo(candidate, sleeve)
        return self.coordinator.register_candidate(child)

    def refresh_candidate(self, candidate_id: str) -> Candidate:
        return self.coordinator.get_candidate(candidate_id)

    def coordinator_name(self) -> str:
        return "Coordinator"

