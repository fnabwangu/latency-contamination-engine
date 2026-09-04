"""Small-sample source reliability calibration for evidence weighting."""

from __future__ import annotations

from dataclasses import dataclass
from decimal import Decimal


@dataclass(frozen=True)
class SourceReliability:
    source: str
    successes: int = 0
    failures: int = 0
    prior_successes: Decimal = Decimal("1")
    prior_failures: Decimal = Decimal("1")

    def __post_init__(self) -> None:
        if min(self.successes, self.failures) < 0:
            raise ValueError("source outcomes cannot be negative")
        if self.prior_successes <= 0 or self.prior_failures <= 0:
            raise ValueError("reliability priors must be positive")

    @property
    def posterior_mean(self) -> Decimal:
        return (self.prior_successes + self.successes) / (self.prior_successes + self.prior_failures + self.successes + self.failures)

    @property
    def effective_sample_size(self) -> Decimal:
        return self.prior_successes + self.prior_failures + self.successes + self.failures

    def record(self, success: bool) -> "SourceReliability":
        return SourceReliability(self.source, self.successes + int(success), self.failures + int(not success), self.prior_successes, self.prior_failures)

    def weight(self, minimum: Decimal = Decimal("0.25"), maximum: Decimal = Decimal("1")) -> Decimal:
        if not 0 < minimum <= maximum:
            raise ValueError("reliability weight bounds are invalid")
        return max(minimum, min(maximum, self.posterior_mean))