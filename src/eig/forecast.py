"""Forecast contracts, resolution rules, and calibration metrics."""

from __future__ import annotations

from dataclasses import dataclass
from datetime import datetime
from decimal import Decimal
from enum import Enum
from typing import Iterable


class ForecastStatus(str, Enum):
    OPEN = "OPEN"
    SUCCESS = "SUCCESS"
    FAILURE = "FAILURE"
    CENSORED = "CENSORED"


@dataclass(frozen=True)
class Forecast:
    forecast_id: str
    instrument: str
    direction: str
    entry: Decimal
    target: Decimal
    stop: Decimal
    horizon: str
    forecasted_at: datetime
    probability: Decimal
    regime: str = "UNKNOWN"
    strategy_family: str = "UNKNOWN"
    asset_class: str = "UNKNOWN"
    transaction_costs: Decimal = Decimal("0")
    status: ForecastStatus = ForecastStatus.OPEN

    def __post_init__(self) -> None:
        if not 0 <= self.probability <= 1:
            raise ValueError("forecast probability must be between 0 and 1")
        if self.direction not in {"BUY", "SELL"}:
            raise ValueError("forecast direction must be BUY or SELL")
        if self.target == self.entry or self.stop == self.entry:
            raise ValueError("target and stop must differ from entry")

    def resolve(self, target_reached: bool, stop_reached: bool, censored: bool = False) -> "Forecast":
        if sum((target_reached, stop_reached, censored)) > 1:
            raise ValueError("forecast resolution outcomes are mutually exclusive")
        status = ForecastStatus.CENSORED if censored else ForecastStatus.SUCCESS if target_reached else ForecastStatus.FAILURE if stop_reached else ForecastStatus.OPEN
        return Forecast(**{**self.__dict__, "status": status})


@dataclass(frozen=True)
class CalibrationMetrics:
    count: int
    brier_score: Decimal
    log_loss: Decimal
    reliability: Decimal


def calibration_metrics(forecasts: Iterable[Forecast]) -> CalibrationMetrics:
    resolved = tuple(forecast for forecast in forecasts if forecast.status in {ForecastStatus.SUCCESS, ForecastStatus.FAILURE})
    if not resolved:
        return CalibrationMetrics(0, Decimal("0"), Decimal("0"), Decimal("0"))
    brier = sum(((forecast.probability - (1 if forecast.status is ForecastStatus.SUCCESS else 0)) ** 2 for forecast in resolved), Decimal("0")) / len(resolved)
    log_loss = sum((-(Decimal("1") if forecast.status is ForecastStatus.SUCCESS else Decimal("0")) * _log(forecast.probability) - (Decimal("0") if forecast.status is ForecastStatus.SUCCESS else Decimal("1")) * _log(Decimal("1") - forecast.probability) for forecast in resolved), Decimal("0")) / len(resolved)
    errors = []
    for forecast in resolved:
        outcome = Decimal("1") if forecast.status is ForecastStatus.SUCCESS else Decimal("0")
        errors.append(abs(forecast.probability - outcome))
    reliability = sum(errors, Decimal("0")) / len(resolved)
    return CalibrationMetrics(len(resolved), brier, log_loss, reliability)


def _log(value: Decimal) -> Decimal:
    # Decimal has no logarithm on the minimum supported Python version; this
    # bounded approximation keeps the metric deterministic and dependency-free.
    value = max(Decimal("0.000001"), min(Decimal("0.999999"), value))
    term = (value - 1) / (value + 1)
    result = Decimal("0")
    for index in range(1, 12, 2):
        result += term ** index / index
    return 2 * result