"""Coordinator run lifecycle and packet visibility rules."""

from __future__ import annotations

import uuid
from dataclasses import dataclass, field
from enum import Enum
from typing import Iterable

from .coordination import AgentPacket


class RunPhase(str, Enum):
    FRAME = "FRAME"
    ELICIT = "ELICIT"
    POOL = "POOL"
    CHALLENGE = "CHALLENGE"
    DECIDE = "DECIDE"
    COMPLETE = "COMPLETE"


class RunError(ValueError):
    """A coordination run attempted an incomplete or invalid operation."""


@dataclass(frozen=True)
class CoordinationFrame:
    candidate_ids: tuple[str, ...]
    forecast: str
    horizon: str
    catalyst_clock: str
    required_roles: tuple[str, ...] = ()
    required_dissent_role: str = "BITO"

    def __post_init__(self) -> None:
        if not self.candidate_ids or not self.forecast or not self.horizon or not self.catalyst_clock:
            raise RunError("frame requires candidates, forecast, horizon, and catalyst clock")
        if self.required_dissent_role not in self.required_roles:
            raise RunError("required dissent role must be assigned in the frame")


@dataclass(frozen=True)
class TaskAssignment:
    task_id: str
    role: str
    owner: str
    depends_on: tuple[str, ...] = ()
    required: bool = True


@dataclass
class CoordinationRun:
    frame: CoordinationFrame
    run_id: str = field(default_factory=lambda: uuid.uuid4().hex)
    phase: RunPhase = RunPhase.FRAME
    assignments: dict[str, TaskAssignment] = field(default_factory=dict)
    packets: dict[str, AgentPacket] = field(default_factory=dict)
    committed_packets: set[str] = field(default_factory=set)
    dispositions: dict[str, str] = field(default_factory=dict)

    def begin_elicitation(self) -> None:
        self._advance(RunPhase.FRAME, RunPhase.ELICIT)

    def assign(self, assignment: TaskAssignment) -> TaskAssignment:
        if self.phase is not RunPhase.ELICIT:
            raise RunError("tasks can only be assigned during elicitation")
        if assignment.task_id in self.assignments:
            raise RunError(f"duplicate task assignment {assignment.task_id}")
        missing = set(assignment.depends_on) - self.assignments.keys()
        if missing:
            raise RunError(f"task dependencies are not assigned: {', '.join(sorted(missing))}")
        self.assignments[assignment.task_id] = assignment
        return assignment

    def commit_packet(self, packet: AgentPacket) -> AgentPacket:
        if self.phase is not RunPhase.ELICIT:
            raise RunError("packets can only be committed during elicitation")
        packet.validate()
        if packet.run_id != self.run_id:
            raise RunError("packet belongs to another run")
        if packet.packet_id in self.packets:
            raise RunError(f"duplicate packet {packet.packet_id}")
        if not any(assignment.owner == packet.agent_id for assignment in self.assignments.values()):
            raise RunError(f"agent {packet.agent_id} has no task assignment")
        self.packets[packet.packet_id] = packet
        self.committed_packets.add(packet.packet_id)
        return packet

    def pool(self) -> None:
        self._require_required_packets()
        self._advance(RunPhase.ELICIT, RunPhase.POOL)

    def challenge(self) -> None:
        self._advance(RunPhase.POOL, RunPhase.CHALLENGE)

    def decide(self) -> None:
        self._advance(RunPhase.CHALLENGE, RunPhase.DECIDE)

    def set_disposition(self, candidate_id: str, disposition: str) -> None:
        if self.phase is not RunPhase.DECIDE:
            raise RunError("dispositions can only be recorded during decision")
        if candidate_id not in self.frame.candidate_ids:
            raise RunError(f"candidate {candidate_id} is not in this run")
        if disposition not in {"USE", "BACK_BURNER", "DISCARD", "BLOCKED", "EXPIRED"}:
            raise RunError("invalid candidate disposition")
        self.dispositions[candidate_id] = disposition

    def complete(self) -> None:
        missing = set(self.frame.candidate_ids) - self.dispositions.keys()
        if missing:
            raise RunError(f"run cannot complete without dispositions: {', '.join(sorted(missing))}")
        self._advance(RunPhase.DECIDE, RunPhase.COMPLETE)

    @property
    def aggregate_visible(self) -> bool:
        return self.phase in {RunPhase.DECIDE, RunPhase.COMPLETE}

    @property
    def visible_packets(self) -> tuple[AgentPacket, ...]:
        return tuple(self.packets.values()) if self.aggregate_visible else ()

    def _require_required_packets(self) -> None:
        owners = {packet.agent_id for packet in self.packets.values()}
        required = {assignment.owner for assignment in self.assignments.values() if assignment.required}
        missing = required - owners
        if missing:
            raise RunError(f"required packets are missing: {', '.join(sorted(missing))}")
        if self.frame.required_dissent_role not in {assignment.role for assignment in self.assignments.values() if assignment.required}:
            raise RunError("required dissent task is not assigned")

    def _advance(self, current: RunPhase, next_phase: RunPhase) -> None:
        if self.phase is not current:
            raise RunError(f"run is {self.phase}, expected {current}")
        self.phase = next_phase