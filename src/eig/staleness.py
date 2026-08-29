"""Staleness detection: age-out yields, options chains and thesis assumptions."""

from __future__ import annotations

from dataclasses import dataclass, field
from datetime import datetime, timedelta
from enum import Enum

from .errors import Finding, Severity
from .types import Claim, EpistemicType, utcnow


class Freshness(str, Enum):
    FRESH = "FRESH"
    AGING = "AGING"
    STALE = "STALE"
    EXPIRED = "EXPIRED"


DEFAULT_TYPE_TTL: dict[EpistemicType, timedelta] = {
    EpistemicType.MARKET_DATA: timedelta(minutes=15),
    EpistemicType.USER_STATE: timedelta(hours=12),
    EpistemicType.FACT: timedelta(days=30),
    EpistemicType.PRIOR: timedelta(days=7),
    EpistemicType.ASSUMPTION: timedelta(days=3),
    EpistemicType.HYPOTHESIS: timedelta(days=1),
    EpistemicType.AGENT_OPINION: timedelta(hours=6),
}

#: Tag overrides win over type defaults; the tightest matching TTL applies.
DEFAULT_TAG_TTL: dict[str, timedelta] = {
    "options_chain": timedelta(minutes=5),
    "quote": timedelta(minutes=1),
    "yield_curve": timedelta(hours=6),
    "earnings": timedelta(days=90),
    "thesis_assumption": timedelta(days=2),
}


@dataclass(frozen=True)
class StalenessPolicy:
    type_ttl: dict[EpistemicType, timedelta] = field(
        default_factory=lambda: dict(DEFAULT_TYPE_TTL)
    )
    tag_ttl: dict[str, timedelta] = field(default_factory=lambda: dict(DEFAULT_TAG_TTL))
    #: Fraction of the TTL after which a claim is reported as AGING.
    aging_ratio: float = 0.5
    #: Multiple of the TTL beyond which a claim is quarantined outright.
    expiry_multiple: float = 2.0

    def ttl_for(self, claim: Claim) -> timedelta:
        candidates = [self.type_ttl[claim.etype]]
        candidates += [self.tag_ttl[t] for t in claim.tags if t in self.tag_ttl]
        return min(candidates)


class StalenessDetector:
    def __init__(self, policy: StalenessPolicy | None = None) -> None:
        self.policy = policy or StalenessPolicy()

    def age(self, claim: Claim, now: datetime | None = None) -> timedelta:
        return (now or utcnow()) - claim.observed_at

    def assess(self, claim: Claim, now: datetime | None = None) -> Freshness:
        ttl = self.policy.ttl_for(claim)
        age = self.age(claim, now)
        if age > ttl * self.policy.expiry_multiple:
            return Freshness.EXPIRED
        if age > ttl:
            return Freshness.STALE
        if age > ttl * self.policy.aging_ratio:
            return Freshness.AGING
        return Freshness.FRESH

    def evaluate(self, claim: Claim, now: datetime | None = None) -> list[Finding]:
        state = self.assess(claim, now)
        if state in (Freshness.FRESH, Freshness.AGING):
            return []
        severity = (
            Severity.QUARANTINE if state is Freshness.EXPIRED else Severity.FLAG
        )
        return [
            Finding(
                code=f"STALE_{state.value}",
                severity=severity,
                claim_id=claim.id,
                message=(
                    f"observed {self.age(claim, now)} ago, ttl "
                    f"{self.policy.ttl_for(claim)}"
                ),
            )
        ]
