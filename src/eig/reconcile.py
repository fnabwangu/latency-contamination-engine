"""Conservative reconciliation of contradictory claims."""

from __future__ import annotations

from dataclasses import dataclass
from enum import Enum
from typing import Mapping

from .provenance import Contradiction
from .types import AUTHORITY, Claim


class ReconciliationStatus(str, Enum):
    RESOLVED = "RESOLVED"
    UNRESOLVED = "UNRESOLVED"


@dataclass(frozen=True)
class Reconciliation:
    contradiction: Contradiction
    status: ReconciliationStatus
    winner_id: str | None
    reason: str


def reconcile(contradiction: Contradiction, claims: Mapping[str, Claim]) -> Reconciliation:
    left = claims[contradiction.left_id]
    right = claims[contradiction.right_id]
    left_authority = AUTHORITY[left.etype]
    right_authority = AUTHORITY[right.etype]
    if left_authority == right_authority:
        return Reconciliation(contradiction, ReconciliationStatus.UNRESOLVED, None, "equal-authority contradiction requires new evidence")
    winner = left if left_authority > right_authority else right
    return Reconciliation(contradiction, ReconciliationStatus.RESOLVED, winner.id, "higher-authority claim retained")