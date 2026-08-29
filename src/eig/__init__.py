"""EIG - Epistemic Integrity Gate.

What do we actually know, and where did it come from?
"""

from .contamination import ContaminationDetector, ContaminationPolicy
from .errors import (
    ContaminatedPacket,
    EIGError,
    Finding,
    IsolationViolation,
    Severity,
)
from .gate import EpistemicIntegrityGate
from .isolation import IsolationBarrier
from .packet import EvidencePacket, Quarantined
from .staleness import Freshness, StalenessDetector, StalenessPolicy
from .types import (
    AUTHORITY,
    DERIVED_TYPES,
    OBSERVED_TYPES,
    Claim,
    EpistemicType,
    Provenance,
    SourceKind,
)

__all__ = [
    "AUTHORITY",
    "Claim",
    "ContaminatedPacket",
    "ContaminationDetector",
    "ContaminationPolicy",
    "DERIVED_TYPES",
    "EIGError",
    "EpistemicIntegrityGate",
    "EpistemicType",
    "EvidencePacket",
    "Finding",
    "Freshness",
    "IsolationBarrier",
    "IsolationViolation",
    "OBSERVED_TYPES",
    "Provenance",
    "Quarantined",
    "Severity",
    "SourceKind",
    "StalenessDetector",
    "StalenessPolicy",
]
