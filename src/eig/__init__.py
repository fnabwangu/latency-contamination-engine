"""EIG - Epistemic Integrity Gate.

What do we actually know, and where did it come from?
"""

from .contamination import ContaminationDetector, ContaminationPolicy
from .coordinator import (
    ApprovalError,
    Candidate,
    CandidateState,
    CandidateType,
    ConvictionResult,
    Coordinator,
    ExecutionProposal,
    GateClass,
    GateDefinition,
    GateEvaluation,
    GateResult,
    LCAE,
    LifecycleEvent,
    Sleeve,
)
from .coordination import AgentPacket, CoverageCell, CoverageStatus, DecisionCoverageMatrix, IndependenceRecord, Vote
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
from .registry import SQLiteRegistry
from .service import CoordinatorService
from .execution import (
    BrokerAdapter,
    ExecutionError,
    ExecutionMandate,
    OrderReceipt,
    OrderStatus,
    RootExecutionEngine,
)

try:
    from .app import create_app
except RuntimeError:
    create_app = None
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
    "ApprovalError",
    "AgentPacket",
    "BrokerAdapter",
    "Candidate",
    "CandidateState",
    "CandidateType",
    "Claim",
    "ContaminatedPacket",
    "ContaminationDetector",
    "ContaminationPolicy",
    "ConvictionResult",
    "Coordinator",
    "CoordinatorService",
    "create_app",
    "CoverageCell",
    "CoverageStatus",
    "DecisionCoverageMatrix",
    "DERIVED_TYPES",
    "EIGError",
    "EpistemicIntegrityGate",
    "EpistemicType",
    "EvidencePacket",
    "ExecutionProposal",
    "ExecutionError",
    "ExecutionMandate",
    "Finding",
    "GateClass",
    "GateDefinition",
    "GateEvaluation",
    "GateResult",
    "Freshness",
    "IsolationBarrier",
    "IsolationViolation",
    "IndependenceRecord",
    "LCAE",
    "LifecycleEvent",
    "OrderReceipt",
    "OrderStatus",
    "OBSERVED_TYPES",
    "Provenance",
    "Quarantined",
    "Severity",
    "Sleeve",
    "SQLiteRegistry",
    "SourceKind",
    "StalenessDetector",
    "StalenessPolicy",
    "RootExecutionEngine",
    "Vote",
]
