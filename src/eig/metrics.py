"""Privacy-preserving Coordinator metrics snapshots."""

from __future__ import annotations

from collections import Counter
from dataclasses import dataclass
from typing import Any, Mapping

from .coordinator import Coordinator


@dataclass(frozen=True)
class CoordinatorMetrics:
    candidates: int
    candidates_by_state: Mapping[str, int]
    packets: int
    evidence: int
    lcaes: int
    gate_evaluations: int
    proposals: int
    outcomes: int
    surfaced_cards: int

    def as_dict(self) -> dict[str, Any]:
        return {
            "candidates": self.candidates,
            "candidates_by_state": dict(self.candidates_by_state),
            "packets": self.packets,
            "evidence": self.evidence,
            "lcaes": self.lcaes,
            "gate_evaluations": self.gate_evaluations,
            "proposals": self.proposals,
            "outcomes": self.outcomes,
            "surfaced_cards": self.surfaced_cards,
        }


def snapshot(coordinator: Coordinator, packets: int = 0, evidence: int = 0) -> CoordinatorMetrics:
    states = Counter(candidate.state.value for candidate in coordinator.candidates.values())
    return CoordinatorMetrics(len(coordinator.candidates), states, packets, evidence, len(coordinator.lcaes), len(coordinator.gate_evaluations), len(coordinator.proposals), len(coordinator.outcomes), len(coordinator.meeting_surface()))