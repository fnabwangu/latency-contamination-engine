"""Stage-aware gate graph composition."""

from __future__ import annotations

from dataclasses import dataclass
from typing import Iterable, Mapping

from .coordinator import GateClass, GateDefinition, GateEvaluation, GateResult


@dataclass(frozen=True)
class StageDecision:
    stage: str
    blocked: bool
    warnings: tuple[GateEvaluation, ...]
    blockers: tuple[GateEvaluation, ...]
    unknowns: tuple[GateEvaluation, ...]


class GateGraph:
    """Compose typed evaluations without collapsing all stages into one Boolean."""

    def __init__(self, definitions: Iterable[GateDefinition]) -> None:
        self.definitions = tuple(definitions)
        if any(not definition.owner for definition in self.definitions):
            raise ValueError("every gate must have an owner")

    def evaluate(self, results: Mapping[str, GateResult], stage: str) -> StageDecision:
        evaluations = tuple(
            GateEvaluation(definition.gate_id, stage, definition.gate_class, definition.required, results.get(definition.gate_id, GateResult.UNKNOWN), "graph evaluation", policy_version=definition.policy_version)
            for definition in self.definitions if definition.stage == stage
        )
        blockers = tuple(evaluation for evaluation in evaluations if evaluation.required and evaluation.gate_class is not GateClass.WARNING and evaluation.result in {GateResult.FAIL, GateResult.UNKNOWN, GateResult.STALE})
        return StageDecision(stage, bool(blockers), tuple(e for e in evaluations if e.result is GateResult.WARN), blockers, tuple(e for e in evaluations if e.result is GateResult.UNKNOWN))

    def discovery_preserved(self, results: Mapping[str, GateResult]) -> bool:
        decision = self.evaluate(results, "discovery")
        return not any(e.gate_class is GateClass.RESEARCH_INVALIDATOR and e.result is GateResult.FAIL for e in decision.blockers)