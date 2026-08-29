"""Epistemic types, sources and claim representation."""

from __future__ import annotations

import uuid
from dataclasses import dataclass, field, replace
from datetime import datetime, timezone
from enum import Enum
from typing import Any, Mapping


class EpistemicType(str, Enum):
    """What kind of thing an input actually is."""

    FACT = "FACT"
    MARKET_DATA = "MARKET_DATA"
    USER_STATE = "USER_STATE"
    PRIOR = "PRIOR"
    ASSUMPTION = "ASSUMPTION"
    HYPOTHESIS = "HYPOTHESIS"
    AGENT_OPINION = "AGENT_OPINION"


#: Higher authority means "closer to observed reality". A derived claim may never
#: be typed above the weakest link in its provenance chain.
AUTHORITY: Mapping[EpistemicType, int] = {
    EpistemicType.FACT: 100,
    EpistemicType.MARKET_DATA: 90,
    EpistemicType.USER_STATE: 80,
    EpistemicType.PRIOR: 50,
    EpistemicType.ASSUMPTION: 40,
    EpistemicType.HYPOTHESIS: 30,
    EpistemicType.AGENT_OPINION: 20,
}

OBSERVED_TYPES = frozenset(
    {EpistemicType.FACT, EpistemicType.MARKET_DATA, EpistemicType.USER_STATE}
)
DERIVED_TYPES = frozenset(set(EpistemicType) - OBSERVED_TYPES)


class SourceKind(str, Enum):
    """Where the bytes physically came from, independent of what they claim to be."""

    FEED = "FEED"
    SYSTEM_OF_RECORD = "SYSTEM_OF_RECORD"
    USER = "USER"
    AGENT = "AGENT"
    MODEL = "MODEL"
    DERIVED = "DERIVED"


#: Source kinds that are allowed to originate observed-tier claims.
OBSERVATIONAL_KINDS = frozenset(
    {SourceKind.FEED, SourceKind.SYSTEM_OF_RECORD, SourceKind.USER}
)


def utcnow() -> datetime:
    return datetime.now(timezone.utc)


@dataclass(frozen=True)
class Provenance:
    """Immutable record of origin. Cannot be rewritten downstream."""

    source: str
    kind: SourceKind
    cycle: int = 0
    agent: str | None = None
    upstream: tuple[str, ...] = ()

    def __post_init__(self) -> None:
        if self.kind is SourceKind.AGENT and not self.agent:
            object.__setattr__(self, "agent", self.source)


@dataclass(frozen=True)
class Claim:
    """A single typed, sourced input to the reasoning pipeline."""

    subject: str
    statement: str
    etype: EpistemicType
    provenance: Provenance
    value: Any = None
    observed_at: datetime = field(default_factory=utcnow)
    ingested_at: datetime = field(default_factory=utcnow)
    confidence: float | None = None
    tags: frozenset[str] = frozenset()
    id: str = field(default_factory=lambda: uuid.uuid4().hex[:12])

    @property
    def is_agent_origin(self) -> bool:
        return self.provenance.kind in (SourceKind.AGENT, SourceKind.MODEL)

    @property
    def label(self) -> str:
        """Human-readable type that keeps the source welded to the claim."""
        name = self.etype.value
        if self.is_agent_origin and not name.startswith("AGENT_"):
            name = f"AGENT_{name}"
        origin = self.provenance.agent or self.provenance.source
        return f"{name}(source={origin})"

    def demoted_to(self, etype: EpistemicType) -> "Claim":
        if AUTHORITY[etype] > AUTHORITY[self.etype]:
            raise ValueError("demotion cannot raise epistemic authority")
        return replace(self, etype=etype)

    def canonical(self) -> str:
        return "|".join(
            [
                self.id,
                self.subject,
                self.statement,
                self.etype.value,
                repr(self.value),
                self.provenance.source,
                self.provenance.kind.value,
                str(self.provenance.cycle),
                ",".join(sorted(self.provenance.upstream)),
                self.observed_at.astimezone(timezone.utc).isoformat(),
            ]
        )

    def __str__(self) -> str:  # pragma: no cover - convenience
        return f"{self.subject}: {self.statement} :: {self.label}"
