"""Deterministic latent collective-action error detection."""

from __future__ import annotations

from collections import defaultdict
from typing import Iterable

from .coordination import AgentPacket
from .coordinator import LCAE


def detect_packet_errors(run_id: str, packets: Iterable[AgentPacket]) -> tuple[LCAE, ...]:
    values = tuple(packets)
    errors: list[LCAE] = []
    evidence_agents: dict[str, list[str]] = defaultdict(list)
    for packet in values:
        for evidence_id in packet.evidence_ids:
            evidence_agents[evidence_id].append(packet.agent_id)
        if packet.vote.value == "HARD_VETO" and not packet.hard_veto:
            errors.append(LCAE(run_id, packet.candidate_ids[0] if packet.candidate_ids else "", "verification", "research", (packet.agent_id,), packet.evidence_ids, "HIGH", "reject malformed veto and request named invalidator"))
    for evidence_id, agents in evidence_agents.items():
        unique_agents = tuple(dict.fromkeys(agents))
        if len(unique_agents) > 1:
            errors.append(LCAE(run_id, "", "correlation", "pooling", unique_agents, (evidence_id,), "MEDIUM", "discount shared evidence and elicit unique evidence"))
    return tuple(errors)