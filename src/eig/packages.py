"""Trade Set and Algo Single package validation."""

from __future__ import annotations

from dataclasses import dataclass
from decimal import Decimal

from .coordinator import Candidate, CandidateType, Sleeve


class PackageError(ValueError):
    """A package does not satisfy its explicit economic contract."""


@dataclass(frozen=True)
class BrandedTradeSet:
    candidate_id: str
    thesis: str
    catalyst: str
    horizon: str
    sleeves: tuple[Sleeve, ...]
    aggregate_risk: Decimal
    invalidator: str

    def __post_init__(self) -> None:
        if not self.sleeves:
            raise PackageError("a Trade Set requires at least one sleeve")
        if not self.thesis or not self.catalyst or not self.invalidator:
            raise PackageError("Trade Set requires thesis, catalyst, and invalidator")


def build_trade_set(candidate: Candidate) -> BrandedTradeSet:
    if candidate.candidate_type is not CandidateType.BRANDED_TRADE_SET:
        raise PackageError("only branded candidates can become Trade Sets")
    if not candidate.sleeves:
        raise PackageError("Trade Set has no viable sleeves")
    if any(sleeve.thesis != candidate.thesis for sleeve in candidate.sleeves):
        raise PackageError("all Trade Set sleeves must share the package thesis")
    aggregate_risk = sum((sleeve.expected_loss for sleeve in candidate.sleeves), Decimal("0"))
    return BrandedTradeSet(candidate.candidate_id, candidate.thesis, candidate.catalyst, candidate.horizon, candidate.sleeves, aggregate_risk, candidate.sleeves[0].invalidation)


def promote_sleeve_to_algo(source: Candidate, sleeve: Sleeve) -> Candidate:
    if sleeve not in source.sleeves:
        raise PackageError("sleeve is not part of the source Trade Set")
    return Candidate(
        candidate_id=f"algo-{sleeve.sleeve_id}",
        candidate_type=CandidateType.ALGO_SINGLE,
        name=f"{sleeve.instrument} Algo Single",
        thesis=sleeve.thesis,
        catalyst=sleeve.catalyst,
        horizon="sleeve horizon",
        sleeves=(sleeve,),
    )