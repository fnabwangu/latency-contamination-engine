"""Opportunity-clock and information-value decisions."""

from __future__ import annotations

from dataclasses import dataclass
from datetime import datetime, timedelta
from decimal import Decimal
from enum import Enum


class ResearchDecision(str, Enum):
    CONTINUE = "CONTINUE"
    STOP = "STOP"
    ESCALATE = "ESCALATE"


@dataclass(frozen=True)
class OpportunityClock:
    discovery_deadline: datetime
    catalyst_time: datetime | None = None
    entry_window_end: datetime | None = None
    evidence_expiration: datetime | None = None
    mandate_expiration: datetime | None = None
    half_life: timedelta | None = None

    @property
    def effective_deadline(self) -> datetime:
        dates = [self.discovery_deadline]
        dates.extend(date for date in (self.catalyst_time, self.entry_window_end, self.evidence_expiration, self.mandate_expiration) if date is not None)
        return min(dates)

    def remaining(self, now: datetime) -> timedelta:
        return self.effective_deadline - now


@dataclass(frozen=True)
class InformationValue:
    probability_decision_changes: Decimal
    value_of_better_decision: Decimal
    retrieval_cost: Decimal
    opportunity_decay: Decimal

    @property
    def net_value(self) -> Decimal:
        return self.probability_decision_changes * self.value_of_better_decision - self.retrieval_cost - self.opportunity_decay


def choose_research_action(clock: OpportunityClock, value: InformationValue, now: datetime, required_unknowns: bool = False, fast_lane: bool = False) -> ResearchDecision:
    if fast_lane:
        return ResearchDecision.ESCALATE
    if now >= clock.effective_deadline or clock.remaining(now) <= timedelta(0):
        return ResearchDecision.STOP
    if required_unknowns or value.net_value > 0:
        return ResearchDecision.CONTINUE
    return ResearchDecision.STOP