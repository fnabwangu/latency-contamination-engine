"""Findings and errors raised by the gate."""

from __future__ import annotations

from dataclasses import dataclass
from enum import Enum

from .types import EpistemicType


class Severity(str, Enum):
    FLAG = "FLAG"
    DEMOTE = "DEMOTE"
    QUARANTINE = "QUARANTINE"


@dataclass(frozen=True)
class Finding:
    code: str
    severity: Severity
    claim_id: str
    message: str
    suggested_type: EpistemicType | None = None


class EIGError(Exception):
    """Base error for the Epistemic Integrity Gate."""


class IsolationViolation(EIGError):
    """An agent tried to read another agent's conclusions before sealing."""


class ContaminatedPacket(EIGError):
    """A packet was asserted clean but carries quarantined or flagged material."""
