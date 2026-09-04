"""EIG - Epistemic Integrity Gate.

Single entry point: submit typed, sourced claims; get back a clean evidence packet.
"""

from __future__ import annotations

from datetime import datetime
from typing import Any, Iterable

from .contamination import ContaminationDetector, ContaminationPolicy
from .errors import Finding, IsolationViolation, Severity
from .isolation import IsolationBarrier
from .packet import EvidencePacket, Quarantined
from .provenance import ProvenanceGraph
from .staleness import StalenessDetector, StalenessPolicy
from .types import (
    AUTHORITY,
    Claim,
    EpistemicType,
    Provenance,
    SourceKind,
    utcnow,
)


class EpistemicIntegrityGate:
    def __init__(
        self,
        cycle: int = 0,
        agents: Iterable[str] = (),
        contamination_policy: ContaminationPolicy | None = None,
        staleness_policy: StalenessPolicy | None = None,
        require_seal: bool = True,
    ) -> None:
        self.cycle = cycle
        self.require_seal = require_seal
        self.barrier = IsolationBarrier(tuple(agents))
        self.contamination = ContaminationDetector(contamination_policy)
        self.staleness = StalenessDetector(staleness_policy)
        self._ledger: dict[str, Claim] = {}

    # -- ingestion -----------------------------------------------------------

    def submit(self, claim: Claim) -> Claim:
        if claim.id in self._ledger:
            raise ValueError(f"claim {claim.id} already submitted")
        self.barrier.record(claim)
        self._ledger[claim.id] = claim
        return claim

    def observe(
        self,
        subject: str,
        statement: str,
        source: str,
        etype: EpistemicType = EpistemicType.MARKET_DATA,
        kind: SourceKind = SourceKind.FEED,
        value: Any = None,
        observed_at: datetime | None = None,
        tags: Iterable[str] = (),
    ) -> Claim:
        """Record an observation from a feed, system of record or the user."""
        return self.submit(
            Claim(
                subject=subject,
                statement=statement,
                etype=etype,
                value=value,
                observed_at=observed_at or utcnow(),
                tags=frozenset(tags),
                provenance=Provenance(source=source, kind=kind, cycle=self.cycle),
            )
        )

    def agent_claim(
        self,
        agent: str,
        subject: str,
        statement: str,
        etype: EpistemicType = EpistemicType.HYPOTHESIS,
        upstream: Iterable[str] = (),
        value: Any = None,
        confidence: float | None = None,
        cycle: int | None = None,
        observed_at: datetime | None = None,
        tags: Iterable[str] = (),
    ) -> Claim:
        """Record an agent's output. It stays welded to its agent forever."""
        return self.submit(
            Claim(
                subject=subject,
                statement=statement,
                etype=etype,
                value=value,
                confidence=confidence,
                observed_at=observed_at or utcnow(),
                tags=frozenset(tags),
                provenance=Provenance(
                    source=agent,
                    kind=SourceKind.AGENT,
                    agent=agent,
                    cycle=self.cycle if cycle is None else cycle,
                    upstream=tuple(upstream),
                ),
            )
        )

    def seal(self, agent: str) -> None:
        self.barrier.seal(agent)

    def visible_to(self, agent: str) -> list[Claim]:
        return self.barrier.visible_to(agent)

    def advance_cycle(self) -> int:
        """Start a new reasoning cycle; prior agent output is now contaminating."""
        self.cycle += 1
        return self.cycle

    @property
    def ledger(self) -> dict[str, Claim]:
        return dict(self._ledger)

    # -- adjudication --------------------------------------------------------

    def build_packet(self, now: datetime | None = None) -> EvidencePacket:
        if self.require_seal and self.barrier.agents and not self.barrier.released:
            unsealed = sorted(set(self.barrier.agents) - set(self.barrier.sealed_agents()))
            raise IsolationViolation(
                "cannot build packet while agents are still reasoning: "
                + ", ".join(unsealed)
            )

        resolved: dict[str, Claim] = {}
        quarantined: list[Quarantined] = []
        flags: list[Finding] = []
        demotions: list[Finding] = []
        blocked: set[str] = set()

        for claim in self._ledger.values():
            orphan = [pid for pid in claim.provenance.upstream if pid in blocked]
            if orphan:
                blocked.add(claim.id)
                quarantined.append(
                    Quarantined(
                        claim,
                        (
                            Finding(
                                code="ORPHANED_BY_QUARANTINE",
                                severity=Severity.QUARANTINE,
                                claim_id=claim.id,
                                message=f"rests on quarantined evidence: {', '.join(orphan)}",
                            ),
                        ),
                    )
                )
                continue

            findings = self.contamination.evaluate(claim, resolved, self.cycle, self._ledger)
            findings += self.staleness.evaluate(claim, now)

            if any(f.severity is Severity.QUARANTINE for f in findings):
                blocked.add(claim.id)
                quarantined.append(Quarantined(claim, tuple(findings)))
                continue

            accepted = claim
            demote = [
                f for f in findings if f.severity is Severity.DEMOTE and f.suggested_type
            ]
            if demote:
                target = min(demote, key=lambda f: AUTHORITY[f.suggested_type])
                accepted = claim.demoted_to(target.suggested_type)
                demotions.extend(demote)
            flags.extend(f for f in findings if f.severity is Severity.FLAG)
            resolved[accepted.id] = accepted

        contradictions = ProvenanceGraph(resolved.values()).contradictions()
        for contradiction in contradictions:
            flags.extend(
                Finding(
                    code="CONTRADICTORY_EVIDENCE",
                    severity=Severity.FLAG,
                    claim_id=claim_id,
                    message=contradiction.message,
                )
                for claim_id in (contradiction.left_id, contradiction.right_id)
            )

        return EvidencePacket(
            cycle=self.cycle,
            accepted=tuple(resolved.values()),
            quarantined=tuple(quarantined),
            flags=tuple(flags),
            demotions=tuple(demotions),
            contradictions=contradictions,
        )
