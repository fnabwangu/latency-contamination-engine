"""Inspectable conviction models and sensitivity analysis.

These deterministic estimators are model-provider-neutral baselines. They keep
probability, confidence, uncertainty, expected value, and sizing inputs
separate so an external Coordinator can replace a model without changing its
contract.
"""

from __future__ import annotations

import math
from dataclasses import dataclass
from decimal import Decimal
from enum import Enum
from typing import Iterable, Mapping


class ConvictionStatus(str, Enum):
    CALIBRATED = "CALIBRATED"
    PROVISIONAL = "PROVISIONAL"
    UNSCORABLE = "UNSCORABLE"


class Fragility(str, Enum):
    ROBUST = "ROBUST"
    FRAGILE = "FRAGILE"
    UNSCORABLE = "UNSCORABLE"


@dataclass(frozen=True)
class BaseRate:
    strategy_family: str
    successes: int
    failures: int
    prior_successes: Decimal = Decimal("1")
    prior_failures: Decimal = Decimal("1")

    def __post_init__(self) -> None:
        if min(self.successes, self.failures) < 0 or self.prior_successes <= 0 or self.prior_failures <= 0:
            raise ValueError("base-rate counts and priors must be non-negative and priors positive")

    @property
    def probability(self) -> Decimal:
        return (self.prior_successes + self.successes) / (self.prior_successes + self.prior_failures + self.successes + self.failures)

    @property
    def sample_size(self) -> int:
        return self.successes + self.failures


@dataclass(frozen=True)
class Analog:
    outcome: bool
    similarity: Decimal
    time_to_event: Decimal

    def __post_init__(self) -> None:
        if not 0 <= self.similarity <= 1 or self.time_to_event < 0:
            raise ValueError("analog similarity and time-to-event are out of range")


@dataclass(frozen=True)
class ConvictionFeatures:
    trend: Decimal = Decimal("0")
    volume: Decimal = Decimal("0")
    causal_strength: Decimal = Decimal("0")
    counter_thesis: Decimal = Decimal("0")
    mfe: Decimal = Decimal("0")
    mae: Decimal = Decimal("0")
    time_to_event: Decimal = Decimal("0")
    liquidity: Decimal = Decimal("1")

    def __post_init__(self) -> None:
        if not 0 <= self.liquidity <= 1 or self.mfe < 0 or self.mae < 0 or self.time_to_event < 0:
            raise ValueError("conviction feature values are out of range")


@dataclass(frozen=True)
class Uncertainty:
    model: Decimal
    path: Decimal
    data: Decimal

    def __post_init__(self) -> None:
        if any(value < 0 or value > 1 for value in (self.model, self.path, self.data)):
            raise ValueError("uncertainty values must be between 0 and 1")


@dataclass(frozen=True)
class ConvictionAssessment:
    probability: Decimal | None
    probability_range: tuple[Decimal, Decimal] | None
    confidence: Decimal
    expected_value: Decimal | None
    fragility: Fragility
    status: ConvictionStatus
    model_name: str
    uncertainty: Uncertainty
    sensitivity: Mapping[str, Decimal]


def bayesian_probability(base_rate: BaseRate, analogs: Iterable[Analog] = ()) -> Decimal:
    analog_values = tuple(analogs)
    weighted_success = sum((analog.similarity for analog in analog_values if analog.outcome), Decimal("0"))
    weighted_failure = sum((analog.similarity for analog in analog_values if not analog.outcome), Decimal("0"))
    numerator = base_rate.prior_successes + base_rate.successes + weighted_success
    denominator = base_rate.prior_successes + base_rate.prior_failures + base_rate.successes + base_rate.failures + weighted_success + weighted_failure
    return numerator / denominator


def regularized_logistic(features: ConvictionFeatures, weights: Mapping[str, Decimal] | None = None, intercept: Decimal = Decimal("0"), regularization: Decimal = Decimal("0.1")) -> Decimal:
    if regularization < 0:
        raise ValueError("regularization cannot be negative")
    coefficients = weights or {"trend": Decimal("0.8"), "volume": Decimal("0.3"), "causal_strength": Decimal("1.0"), "counter_thesis": Decimal("-0.9"), "mfe": Decimal("0.2"), "mae": Decimal("-0.2"), "time_to_event": Decimal("-0.1"), "liquidity": Decimal("0.3")}
    values = {name: getattr(features, name) for name in coefficients}
    linear = intercept + sum((coefficient * values[name] / (Decimal("1") + regularization) for name, coefficient in coefficients.items()), Decimal("0"))
    return Decimal(str(1 / (1 + math.exp(-float(linear)))))


def survival_probability(time_to_event: Decimal, hazard: Decimal, competing_hazard: Decimal = Decimal("0")) -> Decimal:
    if time_to_event < 0 or hazard < 0 or competing_hazard < 0:
        raise ValueError("survival inputs cannot be negative")
    return Decimal(str(math.exp(-float((hazard + competing_hazard) * time_to_event))))


def assess_conviction(base_rate: BaseRate | None, analogs: Iterable[Analog], features: ConvictionFeatures, expected_gain: Decimal, expected_loss: Decimal, costs: Decimal = Decimal("0"), uncertainty: Uncertainty = Uncertainty(Decimal("0.2"), Decimal("0.2"), Decimal("0.2")), sample_threshold: int = 30) -> ConvictionAssessment:
    if expected_gain < 0 or expected_loss < 0 or costs < 0:
        raise ValueError("payoff and costs cannot be negative")
    if base_rate is None and expected_gain + expected_loss == 0:
        return ConvictionAssessment(None, None, Decimal("0"), None, Fragility.UNSCORABLE, ConvictionStatus.UNSCORABLE, "none", uncertainty, {})
    prior = base_rate or BaseRate("unknown", 0, 0)
    bayesian = bayesian_probability(prior, analogs)
    logistic = regularized_logistic(features)
    survival = survival_probability(features.time_to_event, Decimal("0.05"), features.counter_thesis * Decimal("0.05"))
    probability = (bayesian + logistic + survival) / Decimal("3")
    confidence = max(Decimal("0"), min(Decimal("1"), (Decimal(str(min(prior.sample_size, sample_threshold))) / sample_threshold) * (Decimal("1") - uncertainty.data)))
    low = max(Decimal("0"), probability - uncertainty.model - uncertainty.path)
    high = min(Decimal("1"), probability + uncertainty.model + uncertainty.path)
    sensitivity = {"low": low * expected_gain - (1 - low) * expected_loss - costs, "base": probability * expected_gain - (1 - probability) * expected_loss - costs, "high": high * expected_gain - (1 - high) * expected_loss - costs}
    signs = {value >= 0 for value in sensitivity.values()}
    fragility = Fragility.FRAGILE if len(signs) > 1 else Fragility.ROBUST
    status = ConvictionStatus.CALIBRATED if prior.sample_size >= sample_threshold else ConvictionStatus.PROVISIONAL
    return ConvictionAssessment(probability, (low, high), confidence, sensitivity["base"], fragility, status, "bayesian-logistic-survival", uncertainty, sensitivity)