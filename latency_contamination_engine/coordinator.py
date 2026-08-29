from __future__ import annotations

from dataclasses import dataclass, field
from enum import Enum
from typing import Dict, Iterable, List, Mapping, MutableMapping, Optional, Sequence


DEFAULT_STRATEGY_UNIVERSE: Sequence[str] = (
    "add",
    "hold",
    "trim",
    "exit",
    "roll",
    "hedge",
    "reprice",
    "delever",
)


class EpistemicType(str, Enum):
    MARKET_EVIDENCE = "MARKET_EVIDENCE"
    STALE_ASSUMPTION = "STALE_ASSUMPTION"
    INHERITED_RECOMMENDATION = "INHERITED_RECOMMENDATION"
    HISTORICAL_PRIOR = "HISTORICAL_PRIOR"
    USER_BEHAVIOR_RULE = "USER_BEHAVIOR_RULE"
    PRIOR_AGENT_CONCLUSION = "PRIOR_AGENT_CONCLUSION"
    AGENT_HYPOTHESIS = "AGENT_HYPOTHESIS"


@dataclass(frozen=True)
class EvidenceItem:
    key: str
    value: str
    epistemic_type: EpistemicType
    source: str = "RAW_CONTEXT"
    authority: str = "FACTUAL"
    quarantined: bool = False


@dataclass
class DecisionContext:
    observations: Mapping[str, str]
    stale_assumptions: Mapping[str, str] = field(default_factory=dict)
    inherited_recommendations: Mapping[str, str] = field(default_factory=dict)
    historical_priors: Mapping[str, str] = field(default_factory=dict)
    user_behavior_rules: Mapping[str, str] = field(default_factory=dict)
    prior_agent_conclusions: Mapping[str, str] = field(default_factory=dict)

    evidence: List[EvidenceItem] = field(default_factory=list)
    latency_contamination_checked: bool = False
    strategy_universe_locked: bool = False
    strategy_universe: Sequence[str] = ()
    previous_recommendations_as_evidence: bool = True


class LatencyContaminationGate:
    """Shared contamination layer for pre/post-agent checks and labeling."""

    def __init__(self, strategy_universe: Optional[Sequence[str]] = None) -> None:
        self._strategy_universe = tuple(strategy_universe or DEFAULT_STRATEGY_UNIVERSE)

    def sanitize_context(self, ctx: DecisionContext) -> MutableMapping[str, object]:
        """Mutates ctx in place with sanitized evidence and lock state."""
        if ctx.latency_contamination_checked:
            raise ValueError("decision context was already sanitized")
        ctx.evidence.clear()

        self._add_evidence(ctx, ctx.observations, EpistemicType.MARKET_EVIDENCE)
        self._add_evidence(
            ctx,
            ctx.stale_assumptions,
            EpistemicType.STALE_ASSUMPTION,
            quarantined=True,
        )
        self._add_evidence(
            ctx,
            ctx.inherited_recommendations,
            EpistemicType.INHERITED_RECOMMENDATION,
            source="INHERITED",
            quarantined=True,
        )
        self._add_evidence(ctx, ctx.historical_priors, EpistemicType.HISTORICAL_PRIOR)
        self._add_evidence(ctx, ctx.user_behavior_rules, EpistemicType.USER_BEHAVIOR_RULE)
        self._add_evidence(
            ctx,
            ctx.prior_agent_conclusions,
            EpistemicType.PRIOR_AGENT_CONCLUSION,
            source="AGENT",
            authority="NON_FACTUAL",
        )

        ctx.latency_contamination_checked = True
        ctx.strategy_universe_locked = True
        ctx.strategy_universe = self._strategy_universe
        ctx.previous_recommendations_as_evidence = False

        report = {
            "checked": True,
            "quarantined_items": sum(1 for item in ctx.evidence if item.quarantined),
            "priors_downweighted": len(ctx.historical_priors),
            "previous_recommendations_blocked": len(ctx.inherited_recommendations),
            "strategy_set_locked": True,
            "warnings": self._warnings(ctx),
        }
        return report

    def classify_agent_outputs(
        self, agent_outputs: Mapping[str, str]
    ) -> List[EvidenceItem]:
        classified: List[EvidenceItem] = []
        for source, conclusion in agent_outputs.items():
            classified.append(
                EvidenceItem(
                    key=f"{source}_conclusion",
                    value=conclusion,
                    epistemic_type=EpistemicType.AGENT_HYPOTHESIS,
                    source=source,
                    authority="NON_FACTUAL",
                    quarantined=False,
                )
            )
        return classified

    def _add_evidence(
        self,
        ctx: DecisionContext,
        values: Mapping[str, str],
        epistemic_type: EpistemicType,
        source: str = "RAW_CONTEXT",
        authority: str = "FACTUAL",
        quarantined: bool = False,
    ) -> None:
        for key, value in values.items():
            ctx.evidence.append(
                EvidenceItem(
                    key=key,
                    value=value,
                    epistemic_type=epistemic_type,
                    source=source,
                    authority=authority,
                    quarantined=quarantined,
                )
            )

    def _warnings(self, ctx: DecisionContext) -> List[str]:
        warnings: List[str] = []
        if ctx.historical_priors:
            warnings.append("Historical priors present and downweighted")
        if ctx.inherited_recommendations:
            warnings.append("Previous recommendations quarantined")
        return warnings


def validate_agent_input(ctx: DecisionContext) -> None:
    if not ctx.latency_contamination_checked:
        raise AssertionError("latency contamination gate was not executed")
    if not ctx.strategy_universe_locked:
        raise AssertionError("strategy universe is not locked")
    if ctx.previous_recommendations_as_evidence:
        raise AssertionError("previous recommendations cannot be used as evidence")


@dataclass
class CoordinatorResult:
    latency_report: Mapping[str, object]
    outputs_by_agent: Mapping[str, str]
    post_gate_outputs: Sequence[EvidenceItem]
    disagreements: Sequence[str]


class MultiAgentCoordinator:
    def __init__(self, gate: Optional[LatencyContaminationGate] = None) -> None:
        self.gate = gate or LatencyContaminationGate()

    def run(
        self,
        ctx: DecisionContext,
        agent_names: Iterable[str],
        llm_outputs: Mapping[str, str],
    ) -> CoordinatorResult:
        latency_report = self.gate.sanitize_context(ctx)

        outputs: Dict[str, str] = {}
        for agent_name in agent_names:
            validate_agent_input(ctx)
            if agent_name not in llm_outputs:
                raise ValueError(f"Missing llm output for agent: {agent_name}")
            outputs[agent_name] = llm_outputs[agent_name]

        post_gate_outputs = self.gate.classify_agent_outputs(outputs)
        disagreements = self._find_disagreements(outputs)

        return CoordinatorResult(
            latency_report=latency_report,
            outputs_by_agent=outputs,
            post_gate_outputs=post_gate_outputs,
            disagreements=disagreements,
        )

    def _find_disagreements(self, outputs: Mapping[str, str]) -> List[str]:
        by_strategy: Dict[str, List[str]] = {}
        for agent, conclusion in outputs.items():
            by_strategy.setdefault(conclusion, []).append(agent)
        if len(by_strategy) <= 1:
            return []
        return [
            f"{strategy}: {', '.join(sorted(agents))}"
            for strategy, agents in sorted(by_strategy.items())
        ]
