from datetime import timedelta

import pytest

from eig import AgentPacket, Coordinator, CoordinatorService, CoverageStatus, DecisionCoverageMatrix, EvidenceModality, EvidenceRecord, Vote
from eig.types import utcnow


def test_packet_validation_and_coverage_owner():
    service = CoordinatorService(Coordinator("run-1"))
    now = utcnow()
    packet = AgentPacket("run-1", "MACRO", "macro", (), now, now + timedelta(minutes=5), vote=Vote.SUPPORT, confidence=0.7)
    assert service.submit_agent_packet(packet).agent_id == "MACRO"
    cell = service.get_coverage_matrix().answer("regime", "MACRO", packet.packet_id)
    assert cell.status is CoverageStatus.ANSWERED
    assert cell.owner == "MACRO"


def test_packet_cannot_cross_runs_or_claim_invalid_hard_veto():
    now = utcnow()
    service = CoordinatorService(Coordinator("run-1"))
    with pytest.raises(ValueError):
        service.submit_agent_packet(AgentPacket("run-2", "EP", "earnings", (), now, now + timedelta(minutes=1)))
    with pytest.raises(ValueError):
        AgentPacket("run-1", "EP", "earnings", (), now, now + timedelta(minutes=1), hard_veto=True).validate()


def test_coverage_requires_owner_and_preserves_unanswered_factors():
    matrix = DecisionCoverageMatrix()
    matrix.assign("dissent", "BITO")
    assert matrix.cells["dissent"].owner == "BITO"
    assert "authorization" in matrix.unanswered()


def test_service_registers_immutable_evidence():
    service = CoordinatorService(Coordinator("run-1"))
    now = utcnow()
    record = EvidenceRecord("filing", now, now, EvidenceModality.FILING, "guidance", candidate_ids=("c1",))
    assert service.register_evidence(record) == service.get_evidence(record.evidence_id)