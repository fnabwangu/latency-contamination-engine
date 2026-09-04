"""Provenance graph validation and conservative contradiction detection."""

from __future__ import annotations

from dataclasses import dataclass
from typing import Iterable, Mapping

from .errors import Finding, Severity
from .types import Claim


@dataclass(frozen=True)
class Contradiction:
    left_id: str
    right_id: str
    subject: str
    message: str


class ProvenanceGraph:
    def __init__(self, claims: Iterable[Claim] = ()) -> None:
        self.claims: dict[str, Claim] = {claim.id: claim for claim in claims}

    def add(self, claim: Claim) -> None:
        if claim.id in self.claims:
            raise ValueError(f"claim {claim.id} already exists")
        self.claims[claim.id] = claim

    def validate(self, max_depth: int = 64) -> tuple[Finding, ...]:
        findings: list[Finding] = []
        for claim in self.claims.values():
            missing = [parent for parent in claim.provenance.upstream if parent not in self.claims]
            if missing:
                findings.append(Finding("DANGLING_PROVENANCE", Severity.QUARANTINE, claim.id, f"upstream claims not in graph: {', '.join(sorted(missing))}"))
            if self._has_cycle(claim.id, max_depth):
                findings.append(Finding("PROVENANCE_CYCLE", Severity.QUARANTINE, claim.id, "provenance graph contains a cycle"))
        return tuple(findings)

    def contradictions(self) -> tuple[Contradiction, ...]:
        groups: dict[tuple[str, str], dict[str, list[Claim]]] = {}
        for claim in self.claims.values():
            group = next((tag.split(":", 1)[1] for tag in claim.tags if tag.startswith("contradiction_group:")), None)
            polarity = next((tag.split(":", 1)[1] for tag in claim.tags if tag.startswith("polarity:")), None)
            if group and polarity:
                groups.setdefault((claim.subject, group), {}).setdefault(polarity, []).append(claim)
        found: list[Contradiction] = []
        for (subject, _), polarities in groups.items():
            for left in polarities.get("positive", ()):
                for right in polarities.get("negative", ()):
                    found.append(Contradiction(left.id, right.id, subject, "claims with the same contradiction group have opposite polarity"))
        return tuple(found)

    def _has_cycle(self, claim_id: str, max_depth: int) -> bool:
        def visit(current: str, path: set[str], depth: int) -> bool:
            if depth > max_depth:
                return True
            if current in path:
                return True
            claim = self.claims.get(current)
            if claim is None:
                return False
            return any(visit(parent, path | {current}, depth + 1) for parent in claim.provenance.upstream)

        return visit(claim_id, set(), 0)