"""Latency contamination and provenance enforcement.

Core invariant: an output of reasoning can never re-enter the pipeline as an
observation. Yesterday's recommendation is not today's market data.
"""

from __future__ import annotations

from dataclasses import dataclass
from typing import Iterable, Mapping

from .errors import Finding, Severity
from .types import (
    AUTHORITY,
    OBSERVED_TYPES,
    Claim,
    EpistemicType,
    SourceKind,
)


@dataclass(frozen=True)
class ContaminationPolicy:
    #: Type an agent-origin claim is forced down to when it poses as observation.
    agent_floor: EpistemicType = EpistemicType.HYPOTHESIS
    #: Quarantine (rather than demote) claims that laundered a previous cycle's
    #: reasoning output into the current cycle's evidence tier.
    quarantine_cross_cycle: bool = True
    #: Reject claims with no upstream and a non-observational source kind.
    require_provenance: bool = True


class ContaminationDetector:
    def __init__(self, policy: ContaminationPolicy | None = None) -> None:
        self.policy = policy or ContaminationPolicy()

    def evaluate(
        self, claim: Claim, ledger: Mapping[str, Claim], cycle: int,
        graph_ledger: Mapping[str, Claim] | None = None,
    ) -> list[Finding]:
        findings: list[Finding] = []
        findings += self._check_source_authority(claim)
        findings += self._check_upstream_authority(claim, ledger)
        findings += self._check_cross_cycle(claim, ledger, cycle)
        findings += self._check_provenance(claim, ledger)
        findings += self._check_provenance_cycle(claim, graph_ledger or ledger)
        return findings

    # -- rules ---------------------------------------------------------------

    def _check_source_authority(self, claim: Claim) -> Iterable[Finding]:
        """An agent/model cannot mint FACT, MARKET_DATA or USER_STATE.

        Purely DERIVED claims are governed by upstream authority instead.
        """
        if claim.etype in OBSERVED_TYPES and claim.is_agent_origin:
            yield Finding(
                code="OPINION_LAUNDERING",
                severity=Severity.DEMOTE,
                claim_id=claim.id,
                message=(
                    f"{claim.provenance.kind.value} source "
                    f"'{claim.provenance.agent or claim.provenance.source}' cannot "
                    f"originate {claim.etype.value}"
                ),
                suggested_type=self.policy.agent_floor,
            )

    def _check_upstream_authority(
        self, claim: Claim, ledger: Mapping[str, Claim]
    ) -> Iterable[Finding]:
        """A derived claim may not outrank the weakest link it was built from."""
        parents = [ledger[pid] for pid in claim.provenance.upstream if pid in ledger]
        if not parents:
            return
        weakest = min(parents, key=lambda c: AUTHORITY[c.etype])
        if AUTHORITY[claim.etype] > AUTHORITY[weakest.etype]:
            yield Finding(
                code="AUTHORITY_INFLATION",
                severity=Severity.DEMOTE,
                claim_id=claim.id,
                message=(
                    f"typed {claim.etype.value} but derives from "
                    f"{weakest.label} ({weakest.id})"
                ),
                suggested_type=weakest.etype,
            )

    def _check_cross_cycle(
        self, claim: Claim, ledger: Mapping[str, Claim], cycle: int
    ) -> Iterable[Finding]:
        """Reasoning output from an earlier cycle cannot be recycled as evidence."""
        stale_origin = (
            claim.etype in OBSERVED_TYPES
            and claim.provenance.cycle < cycle
            and claim.is_agent_origin
        )
        laundered_parent = any(
            ledger[pid].is_agent_origin and ledger[pid].provenance.cycle < cycle
            for pid in claim.provenance.upstream
            if pid in ledger
        )
        if not (stale_origin or laundered_parent):
            return
        severity = (
            Severity.QUARANTINE
            if self.policy.quarantine_cross_cycle
            else Severity.DEMOTE
        )
        yield Finding(
            code="LATENCY_CONTAMINATION",
            severity=severity,
            claim_id=claim.id,
            message=(
                f"cycle {claim.provenance.cycle} reasoning output presented as "
                f"{claim.etype.value} in cycle {cycle}"
            ),
            suggested_type=self.policy.agent_floor,
        )

    def _check_provenance(
        self, claim: Claim, ledger: Mapping[str, Claim]
    ) -> Iterable[Finding]:
        if not self.policy.require_provenance:
            return
        if claim.provenance.kind is SourceKind.DERIVED and not claim.provenance.upstream:
            yield Finding(
                code="UNSOURCED_DERIVATION",
                severity=Severity.QUARANTINE,
                claim_id=claim.id,
                message="derived claim declares no upstream evidence",
            )
        missing = [
            pid for pid in claim.provenance.upstream if pid not in ledger
        ]
        if missing:
            yield Finding(
                code="DANGLING_PROVENANCE",
                severity=Severity.QUARANTINE,
                claim_id=claim.id,
                message=f"upstream claims not in ledger: {', '.join(sorted(missing))}",
            )

    def _check_provenance_cycle(
        self, claim: Claim, ledger: Mapping[str, Claim]
    ) -> Iterable[Finding]:
        def visits(current: str, path: frozenset[str]) -> bool:
            if current in path:
                return True
            parent = ledger.get(current)
            if parent is None:
                return False
            return any(visits(upstream, path | {current}) for upstream in parent.provenance.upstream)

        if any(visits(upstream, frozenset({claim.id})) for upstream in claim.provenance.upstream):
            yield Finding(
                code="PROVENANCE_CYCLE",
                severity=Severity.QUARANTINE,
                claim_id=claim.id,
                message="claim provenance contains a cycle",
            )
