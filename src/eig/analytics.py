"""Deterministic gate and candidate outcome analytics."""

from __future__ import annotations

from dataclasses import dataclass
from decimal import Decimal
from typing import Iterable

from .coordinator import GateEvaluation


@dataclass(frozen=True)
class GateAnalytics:
    entered: int
    passed: int
    failed: int
    warned: int
    unknown: int
    stale: int
    attrition_rate: Decimal


@dataclass(frozen=True)
class ShadowOutcome:
    candidate_id: str
    disposition: str
    realized_return: Decimal | None = None
    realized_loss: Decimal | None = None
    resolved_at: str | None = None


def summarize_gates(evaluations: Iterable[GateEvaluation]) -> GateAnalytics:
    values = tuple(evaluations)
    entered = len(values)
    passed = sum(e.result.value == "PASS" or e.result.value == "NOT_APPLICABLE" for e in values)
    failed = sum(e.result.value == "FAIL" for e in values)
    warned = sum(e.result.value == "WARN" for e in values)
    unknown = sum(e.result.value == "UNKNOWN" for e in values)
    stale = sum(e.result.value == "STALE" for e in values)
    return GateAnalytics(entered, passed, failed, warned, unknown, stale, Decimal(failed) / entered if entered else Decimal("0"))