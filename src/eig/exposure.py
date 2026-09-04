"""Deterministic portfolio exposure and hedge checks."""

from __future__ import annotations

from dataclasses import dataclass
from decimal import Decimal
from typing import Iterable


@dataclass(frozen=True)
class Exposure:
    instrument: str
    dollar_delta: Decimal
    factor: str
    risk_name: str


@dataclass(frozen=True)
class ExposureReport:
    gross_delta: Decimal
    net_delta: Decimal
    concentration: dict[str, Decimal]
    hidden_concentration: tuple[str, ...]


def summarize_exposure(exposures: Iterable[Exposure], concentration_limit: Decimal = Decimal("25000")) -> ExposureReport:
    values = tuple(exposures)
    by_factor: dict[str, Decimal] = {}
    for exposure in values:
        by_factor[exposure.factor] = by_factor.get(exposure.factor, Decimal("0")) + exposure.dollar_delta
    hidden = tuple(sorted(factor for factor, delta in by_factor.items() if abs(delta) > concentration_limit))
    gross = sum((abs(exposure.dollar_delta) for exposure in values), Decimal("0"))
    net = sum((exposure.dollar_delta for exposure in values), Decimal("0"))
    return ExposureReport(gross, net, by_factor, hidden)


def hedge_reduces_named_risk(existing: Exposure, hedge: Exposure) -> bool:
    if hedge.risk_name != existing.risk_name or hedge.factor != existing.factor:
        return False
    return existing.dollar_delta * hedge.dollar_delta < 0