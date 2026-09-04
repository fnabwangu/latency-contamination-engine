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
    AlgoRiskPolicy,
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
from .gates import GateGraph, StageDecision
from .exposure import Exposure, ExposureReport, hedge_reduces_named_risk, summarize_exposure
from .provenance import Contradiction, ProvenanceGraph
from .lineage import LineageCluster, cluster_claims, effective_independent_evidence, weighted_independent_evidence
from .reliability import SourceReliability
from .reconcile import Reconciliation, ReconciliationStatus, reconcile
from .conviction import Analog, BaseRate, ConvictionAssessment, ConvictionFeatures, ConvictionStatus, Fragility, Uncertainty, assess_conviction, bayesian_probability, regularized_logistic, survival_probability
from .integration import CoordinatorHandoff, CoordinatorRouter, ExternalCoordinator, HandoffStatus, HandoffTarget
from .run import CoordinationFrame, CoordinationRun, RunError, RunPhase, TaskAssignment

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
    "Analog",
    "AlgoRiskPolicy",
    "BrokerAdapter",
    "BaseRate",
    "BrandedTradeSet",
    "Candidate",
    "CandidateState",
    "CandidateType",
    "CalibrationMetrics",
    "Claim",
    "ContaminatedPacket",
    "ContaminationDetector",
    "ContaminationPolicy",
    "Contradiction",
    "ConvictionResult",
    "ConvictionAssessment",
    "ConvictionFeatures",
    "ConvictionStatus",
    "Coordinator",
    "CoordinatorHandoff",
    "CoordinatorRouter",
    "CoordinationFrame",
    "CoordinationRun",
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
    "Exposure",
    "ExposureReport",
    "Forecast",
    "ForecastStatus",
    "Fragility",
    "Finding",
    "ExternalCoordinator",
    "GateClass",
    "GateAnalytics",
    "GateDefinition",
    "GateGraph",
    "GateEvaluation",
    "GateResult",
    "Freshness",
    "IsolationBarrier",
    "IsolationViolation",
    "IndependenceRecord",
    "InformationValue",
    "LCAE",
    "HandoffStatus",
    "HandoffTarget",
    "RunError",
    "RunPhase",
    "detect_packet_errors",
    "LifecycleEvent",
    "LineageCluster",
    "OrderReceipt",
    "OrderStatus",
    "PackageError",
    "OpportunityClock",
    "OrchestrationResult",
    "OBSERVED_TYPES",
    "Provenance",
    "ProvenanceGraph",
    "Quarantined",
    "Severity",
    "Sleeve",
    "StageDecision",
    "ShadowOutcome",
    "SQLiteRegistry",
    "SourceKind",
    "StalenessDetector",
    "StalenessPolicy",
    "TaskAssignment",
    "RootExecutionEngine",
    "ResearchDecision",
    "Reconciliation",
    "ReconciliationStatus",
    "ResearchTask",
    "SourceReliability",
    "Vote",
    "Uncertainty",
    "assess_conviction",
    "bayesian_probability",
    "regularized_logistic",
    "survival_probability",
    "build_trade_set",
    "choose_research_action",
    "calibration_metrics",
    "summarize_gates",
    "summarize_exposure",
    "cluster_claims",
    "effective_independent_evidence",
    "weighted_independent_evidence",
    "hedge_reduces_named_risk",
    "run_research",
    "reconcile",
    "snapshot",
    "promote_sleeve_to_algo",
]
