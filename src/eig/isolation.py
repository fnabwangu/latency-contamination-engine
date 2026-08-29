"""Agent isolation: EDGE / HEDGE / EP reason independently before cross-reading."""

from __future__ import annotations

from dataclasses import dataclass, field

from .errors import IsolationViolation
from .types import Claim


@dataclass
class Lane:
    agent: str
    claims: list[Claim] = field(default_factory=list)
    sealed: bool = False


class IsolationBarrier:
    """Holds each agent's conclusions private until every lane is sealed."""

    def __init__(self, agents: list[str] | tuple[str, ...] = ()) -> None:
        self._lanes: dict[str, Lane] = {a: Lane(a) for a in agents}
        self._shared: list[Claim] = []

    # -- registration --------------------------------------------------------

    def register(self, agent: str) -> None:
        self._lanes.setdefault(agent, Lane(agent))

    @property
    def agents(self) -> tuple[str, ...]:
        return tuple(self._lanes)

    @property
    def released(self) -> bool:
        return bool(self._lanes) and all(l.sealed for l in self._lanes.values())

    def sealed_agents(self) -> tuple[str, ...]:
        return tuple(a for a, l in self._lanes.items() if l.sealed)

    # -- writing -------------------------------------------------------------

    def record(self, claim: Claim) -> None:
        agent = claim.provenance.agent if claim.is_agent_origin else None
        if agent is None:
            self._shared.append(claim)
            return
        self.register(agent)
        lane = self._lanes[agent]
        if lane.sealed and not self.released:
            raise IsolationViolation(
                f"{agent} sealed its independent analysis and cannot add claims "
                "while the barrier is still up"
            )
        self._check_cross_reads(agent, claim)
        lane.claims.append(claim)

    def seal(self, agent: str) -> None:
        self.register(agent)
        self._lanes[agent].sealed = True

    # -- reading -------------------------------------------------------------

    def visible_to(self, agent: str) -> list[Claim]:
        self.register(agent)
        visible = list(self._shared) + list(self._lanes[agent].claims)
        if self.released:
            for name, lane in self._lanes.items():
                if name != agent:
                    visible.extend(lane.claims)
        return visible

    def read(self, agent: str, claim_id: str) -> Claim:
        for claim in self.visible_to(agent):
            if claim.id == claim_id:
                return claim
        owner = self._owner_of(claim_id)
        if owner is not None:
            raise IsolationViolation(
                f"{agent} cannot read {owner}'s claim {claim_id}: barrier is up "
                f"(sealed: {', '.join(self.sealed_agents()) or 'none'})"
            )
        raise KeyError(claim_id)

    def all_claims(self) -> list[Claim]:
        claims = list(self._shared)
        for lane in self._lanes.values():
            claims.extend(lane.claims)
        return claims

    # -- internals -----------------------------------------------------------

    def _owner_of(self, claim_id: str) -> str | None:
        for name, lane in self._lanes.items():
            if any(c.id == claim_id for c in lane.claims):
                return name
        return None

    def _check_cross_reads(self, agent: str, claim: Claim) -> None:
        if self.released:
            return
        for pid in claim.provenance.upstream:
            owner = self._owner_of(pid)
            if owner is not None and owner != agent:
                raise IsolationViolation(
                    f"{agent} derived {claim.id} from {owner}'s claim {pid} "
                    "before the isolation barrier was released"
                )
