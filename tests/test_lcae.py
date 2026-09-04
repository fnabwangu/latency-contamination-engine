from datetime import timedelta

from eig import AgentPacket, Coordinator, CoordinatorService, Vote, detect_packet_errors
from eig.types import utcnow


def packet(run_id, agent, evidence, vote=Vote.SUPPORT, hard_veto=False):
    now = utcnow()
    return AgentPacket(run_id, agent, agent, ("c1",), now, now + timedelta(minutes=1), evidence_ids=(evidence,), vote=vote, hard_veto=hard_veto)


def test_detector_finds_shared_evidence_and_malformed_veto():
    values = (packet("r1", "A", "e1"), packet("r1", "B", "e1"), packet("r1", "C", "e2", Vote.HARD_VETO))
    errors = detect_packet_errors("r1", values)
    assert {error.category for error in errors} == {"correlation", "verification"}


def test_service_records_detected_lcaes():
    service = CoordinatorService(Coordinator("r1"))
    service.submit_agent_packet(packet("r1", "A", "e1"))
    service.submit_agent_packet(packet("r1", "B", "e1"))
    assert len(service.detect_lcaes()) == 1
    assert service.coordinator.lcaes[0].category == "correlation"