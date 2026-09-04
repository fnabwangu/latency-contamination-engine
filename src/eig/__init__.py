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
from .evidence import EvidenceModality, EvidenceRecord, EvidenceStore
from .analytics import GateAnalytics, ShadowOutcome, summarize_gates
from .latency import InformationValue, OpportunityClock, ResearchDecision, choose_research_action
from .packages import BrandedTradeSet, PackageError, build_trade_set, promote_sleeve_to_algo
from .forecast import CalibrationMetrics, Forecast, ForecastStatus, calibration_metrics
from .metrics import CoordinatorMetrics, snapshot
from .orchestrator import OrchestrationResult, ResearchTask, run_research
from .lcae import detect_packet_errors

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
    "BrandedTradeSet",
    "Candidate",
    "CandidateState",
    "CandidateType",
    "CalibrationMetrics",
    "Claim",
    "ContaminatedPacket",
    "ContaminationDetector",
    "ContaminationPolicy",
    "ConvictionResult",
    "Coordinator",
    "CoordinatorService",
    "CoordinatorMetrics",
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
    "EvidenceModality",
    "EvidenceRecord",
    "EvidenceStore",
    "Forecast",
    "ForecastStatus",
    "Finding",
    "GateClass",
    "GateAnalytics",
    "GateDefinition",
    "GateEvaluation",
    "GateResult",
    "Freshness",
    "IsolationBarrier",
    "IsolationViolation",
    "IndependenceRecord",
    "InformationValue",
    "LCAE",
    "detect_packet_errors",
    "LifecycleEvent",
    "OrderReceipt",
    "OrderStatus",
    "PackageError",
    "OpportunityClock",
    "OrchestrationResult",
    "OBSERVED_TYPES",
    "Provenance",
    "Quarantined",
    "Severity",
    "Sleeve",
    "ShadowOutcome",
    "SQLiteRegistry",
    "SourceKind",
    "StalenessDetector",
    "StalenessPolicy",
    "RootExecutionEngine",
    "ResearchDecision",
    "ResearchTask",
    "Vote",
    "build_trade_set",
    "choose_research_action",
    "calibration_metrics",
    "summarize_gates",
    "run_research",
    "snapshot",
    "promote_sleeve_to_algo",
]
