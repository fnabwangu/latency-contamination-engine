from datetime import timedelta

import pytest

from eig import AgentPacket, CoordinationFrame, CoordinationRun, RunError, RunPhase, TaskAssignment, Vote
from eig.types import utcnow


def packet(run_id, agent):
    now = utcnow()
    return AgentPacket(run_id, agent, agent, ("c1",), now, now + timedelta(minutes=5), vote=Vote.SUPPORT, confidence=0.6)


def test_run_hides_aggregate_until_required_packets_are_pooled():
    frame = CoordinationFrame(("c1",), "target before stop", "one week", "earnings", ("MACRO", "BITO"))
    run = CoordinationRun(frame)
    run.begin_elicitation()
    run.assign(TaskAssignment("macro-task", "macro", "MACRO"))
    run.assign(TaskAssignment("dissent-task", "BITO", "BITO", ("macro-task",)))
    run.commit_packet(packet(run.run_id, "MACRO"))
    assert not run.aggregate_visible
    with pytest.raises(RunError):
        run.pool()
    run.commit_packet(packet(run.run_id, "BITO"))
    run.pool()
    assert run.phase is RunPhase.POOL
    assert not run.visible_packets
    run.challenge()
    run.decide()
    assert run.visible_packets


def test_run_requires_dispositions_before_completion():
    frame = CoordinationFrame(("c1", "c2"), "forecast", "day", "event", ("MACRO", "BITO"))
    run = CoordinationRun(frame)
    run.begin_elicitation()
    run.assign(TaskAssignment("macro", "macro", "MACRO"))
    run.assign(TaskAssignment("dissent", "BITO", "BITO"))
    run.commit_packet(packet(run.run_id, "MACRO"))
    run.commit_packet(packet(run.run_id, "BITO"))
    run.pool()
    run.challenge()
    run.decide()
    run.set_disposition("c1", "BACK_BURNER")
    with pytest.raises(RunError):
        run.complete()
    run.set_disposition("c2", "DISCARD")
    run.complete()
    assert run.phase is RunPhase.COMPLETE