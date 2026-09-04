"""The clean evidence packet emitted by the gate."""

from __future__ import annotations

import hashlib
import uuid
from dataclasses import dataclass, field
from datetime import datetime

from .errors import ContaminatedPacket, Finding
from .provenance import Contradiction
from .types import Claim, EpistemicType, utcnow


@dataclass(frozen=True)
class Quarantined:
    claim: Claim
    findings: tuple[Finding, ...]


@dataclass(frozen=True)
class EvidencePacket:
    cycle: int
    accepted: tuple[Claim, ...]
    quarantined: tuple[Quarantined, ...] = ()
    flags: tuple[Finding, ...] = ()
    demotions: tuple[Finding, ...] = ()
    contradictions: tuple[Contradiction, ...] = ()
    created_at: datetime = field(default_factory=utcnow)
    id: str = field(default_factory=lambda: uuid.uuid4().hex[:12])

    @property
    def digest(self) -> str:
        parts = [f"cycle={self.cycle}"]
        parts.extend(f"accepted:{claim.canonical()}" for claim in self.accepted)
        parts.extend(
            f"quarantined:{item.claim.canonical()}:{','.join(sorted(f.code for f in item.findings))}"
            for item in self.quarantined
        )
        parts.extend(f"flag:{finding.code}:{finding.claim_id}" for finding in self.flags)
        parts.extend(f"demotion:{finding.code}:{finding.claim_id}" for finding in self.demotions)
        parts.extend(f"contradiction:{item.left_id}:{item.right_id}" for item in self.contradictions)
        payload = "\n".join(sorted(parts))
        return hashlib.sha256(payload.encode()).hexdigest()

    def by_type(self, etype: EpistemicType) -> tuple[Claim, ...]:
        return tuple(c for c in self.accepted if c.etype is etype)

    def facts(self) -> tuple[Claim, ...]:
        return self.by_type(EpistemicType.FACT) + self.by_type(EpistemicType.MARKET_DATA)

    def assert_clean(self, allow_flags: bool = True) -> "EvidencePacket":
        if self.quarantined:
            raise ContaminatedPacket(
                f"{len(self.quarantined)} claim(s) quarantined: "
                + ", ".join(q.claim.id for q in self.quarantined)
            )
        if not allow_flags and self.flags:
            raise ContaminatedPacket(f"{len(self.flags)} flagged claim(s)")
        return self

    def summary(self) -> str:
        lines = [
            f"EvidencePacket {self.id} cycle={self.cycle} digest={self.digest[:12]}",
            f"  accepted={len(self.accepted)} quarantined={len(self.quarantined)} "
            f"demoted={len(self.demotions)} flagged={len(self.flags)} contradictions={len(self.contradictions)}",
        ]
        for claim in self.accepted:
            lines.append(f"  + {claim}")
        for q in self.quarantined:
            codes = ", ".join(f.code for f in q.findings)
            lines.append(f"  - {q.claim} [{codes}]")
        return "\n".join(lines)
