"""FastAPI adapter for the Coordinator service."""

from dataclasses import asdict
from datetime import datetime
from decimal import Decimal
import os
from typing import Any
from pathlib import Path

from .coordinator import Candidate, CandidateState, CandidateType, Coordinator, GateDefinition, GateResult, Sleeve
from .coordination import AgentPacket, CoverageStatus, IndependenceRecord, Vote
from .evidence import EvidenceModality, EvidenceRecord
from .analytics import ShadowOutcome
from .gates import GateGraph
from .exposure import Exposure, summarize_exposure
from .packages import build_trade_set, promote_sleeve_to_algo
from .conviction import Analog, BaseRate, ConvictionFeatures, Uncertainty
from .registry import SQLiteRegistry
from .service import CoordinatorService


def _jsonable(value: Any) -> Any:
    if isinstance(value, Decimal):
        return str(value)
    if hasattr(value, "value"):
        return value.value
    if isinstance(value, tuple):
        return [_jsonable(item) for item in value]
    if isinstance(value, dict):
        return {key: _jsonable(item) for key, item in value.items()}
    if hasattr(value, "__dataclass_fields__"):
        return _jsonable(asdict(value))
    return value


def create_app(service: CoordinatorService | None = None, database_path: str | None = None, tenant_id: str | None = None):
    try:
        from fastapi import FastAPI, Header, HTTPException
        from pydantic import BaseModel, Field
    except ImportError as error:  # pragma: no cover
        raise RuntimeError("install eig[web] to use the HTTP application") from error

    class CandidateRequest(BaseModel):
        candidate_id: str = Field(min_length=1, max_length=128)
        candidate_type: CandidateType
        name: str = Field(min_length=1, max_length=200)
        thesis: str = Field(min_length=1)
        catalyst: str = Field(min_length=1)
        horizon: str = Field(min_length=1)

    class DispositionRequest(BaseModel):
        disposition: CandidateState
        reason: str = Field(min_length=1)
        expected_version: int | None = Field(default=None, ge=0)

    class TransitionRequest(BaseModel):
        state: CandidateState
        reason: str = Field(min_length=1)
        expected_version: int | None = Field(default=None, ge=0)

    class ProposalRequest(BaseModel):
        instrument: str = Field(min_length=1, max_length=32)
        side: str = Field(pattern="^(BUY|SELL)$")
        quantity: Decimal = Field(gt=0)
        intended_loss: Decimal = Field(ge=0)
        absolute_loss: Decimal = Field(ge=0)
        entry_trigger: str = Field(min_length=1)
        expiry: datetime

    class ApprovalRequest(BaseModel):
        payload_hash: str = Field(min_length=64, max_length=64)

    class EvidenceRequest(BaseModel):
        source: str = Field(min_length=1, max_length=300)
        captured_at: datetime
        effective_at: datetime
        modality: EvidenceModality
        content: str = Field(min_length=1)
        extractor_version: str = "native"
        confidence: float = Field(ge=0, le=1)
        claims: tuple[str, ...] = ()
        entities: tuple[str, ...] = ()
        candidate_ids: tuple[str, ...] = ()
        contradictions: tuple[str, ...] = ()
        expires_at: datetime | None = None

    class PacketRequest(BaseModel):
        run_id: str
        agent_id: str = Field(min_length=1, max_length=128)
        role: str = Field(min_length=1, max_length=128)
        candidate_ids: tuple[str, ...] = ()
        as_of: datetime
        valid_until: datetime
        claims: tuple[str, ...] = ()
        evidence_ids: tuple[str, ...] = ()
        unique_evidence: tuple[str, ...] = ()
        shared_evidence: tuple[str, ...] = ()
        known_unknowns: tuple[str, ...] = ()
        requests: tuple[str, ...] = ()
        dependencies: tuple[str, ...] = ()
        contradictions: tuple[str, ...] = ()
        directional_effect: str = "NEUTRAL"
        magnitude: str = "UNKNOWN"
        confidence: float = Field(ge=0, le=1)
        vote: Vote = Vote.INSUFFICIENT_DATA
        hard_veto: bool = False
        veto_invalidator: str | None = None
        next_action: str = ""
        model_lineage: str = ""
        prompt_version: str = "1"
        source_lineage: tuple[str, ...] = ()

    class CoverageRequest(BaseModel):
        owner: str = Field(min_length=1, max_length=128)
        packet_id: str | None = None

    class IndependenceRequest(BaseModel):
        agent_id: str = Field(min_length=1, max_length=128)
        provider: str = Field(min_length=1, max_length=128)
        model_version: str = Field(min_length=1, max_length=128)
        prompt_version: str = Field(min_length=1, max_length=128)
        tool_lineage: tuple[str, ...] = ()
        shared_upstream: tuple[str, ...] = ()
        feature_lineage: tuple[str, ...] = ()
        error_correlation: float = Field(ge=0, le=1)
        calibration: str = "UNKNOWN"
        config_version: str = "1"

    class OutcomeRequest(BaseModel):
        disposition: str = Field(min_length=1, max_length=64)
        realized_return: Decimal | None = None
        realized_loss: Decimal | None = None
        resolved_at: str | None = None

    class GateEvaluationRequest(BaseModel):
        definitions: tuple[dict[str, Any], ...]
        results: dict[str, str]
        stage: str = Field(min_length=1, max_length=64)

    class ExposureRequest(BaseModel):
        instrument: str = Field(min_length=1, max_length=32)
        dollar_delta: Decimal
        factor: str = Field(min_length=1, max_length=128)
        risk_name: str = Field(min_length=1, max_length=128)
        concentration_limit: Decimal = Field(gt=0, default=Decimal("25000"))

    class TradeSetRequest(BaseModel):
        candidate_id: str = Field(min_length=1, max_length=128)
        name: str = Field(min_length=1, max_length=200)
        thesis: str = Field(min_length=1)
        catalyst: str = Field(min_length=1)
        horizon: str = Field(min_length=1)
        sleeves: tuple[dict[str, Any], ...]

    class ExecutionHandoffRequest(BaseModel):
        proposal_id: str = Field(min_length=1, max_length=128)
        payload_hash: str = Field(min_length=64, max_length=64)

    class ConvictionRequest(BaseModel):
        strategy_family: str = Field(min_length=1, max_length=128)
        successes: int = Field(ge=0)
        failures: int = Field(ge=0)
        expected_gain: Decimal = Field(ge=0)
        expected_loss: Decimal = Field(ge=0)
        costs: Decimal = Field(ge=0, default=Decimal("0"))
        analogs: tuple[dict[str, Any], ...] = ()
        features: dict[str, Decimal] = Field(default_factory=dict)
        model_uncertainty: Decimal = Field(ge=0, le=1, default=Decimal("0.2"))
        path_uncertainty: Decimal = Field(ge=0, le=1, default=Decimal("0.2"))
        data_uncertainty: Decimal = Field(ge=0, le=1, default=Decimal("0.2"))


    if service is None:
        configured_path = database_path or os.environ.get("EIG_DATABASE_PATH", ":memory:")
        configured_tenant = tenant_id or os.environ.get("EIG_TENANT_ID", "default")
        coordinator_service = CoordinatorService(Coordinator(registry=SQLiteRegistry(configured_path), tenant_id=configured_tenant))
    else:
        coordinator_service = service
        configured_tenant = coordinator_service.coordinator.tenant_id
    app = FastAPI(title="HedgeHog Trade Coordinator", version="0.1.0")

    def require_mutation_auth(api_key: str | None) -> None:
        expected = os.environ.get("EIG_API_KEY")
        if expected and api_key != expected:
            raise HTTPException(status_code=401, detail="authenticated mutation required")

    def require_tenant(request_tenant: str | None) -> None:
        if request_tenant is not None and request_tenant != configured_tenant:
            raise HTTPException(status_code=403, detail="tenant scope mismatch")

    ui_path = Path(__file__).resolve().parents[2] / "ui" / "index.html"
    ui_components_path = ui_path.parent / "components.js"
    ui_styles_path = ui_path.parent / "components.css"

    @app.get("/ui", include_in_schema=False)
    def ui():
        from fastapi.responses import HTMLResponse
        if not ui_path.exists():
            raise HTTPException(status_code=404, detail="UI asset not installed")
        return HTMLResponse(ui_path.read_text(encoding="utf-8"))

    @app.get("/ui/components.js", include_in_schema=False)
    def ui_components():
        from fastapi.responses import Response
        if not ui_components_path.exists():
            raise HTTPException(status_code=404, detail="UI component asset not installed")
        return Response(ui_components_path.read_text(encoding="utf-8"), media_type="text/javascript")

    @app.get("/ui/components.css", include_in_schema=False)
    def ui_styles():
        from fastapi.responses import Response
        if not ui_styles_path.exists():
            raise HTTPException(status_code=404, detail="UI style asset not installed")
        return Response(ui_styles_path.read_text(encoding="utf-8"), media_type="text/css")

    @app.get("/health")
    def health(x_tenant_id: str | None = Header(default=None)) -> dict[str, str]:
        require_tenant(x_tenant_id)
        return {"status": "ok", "run_id": coordinator_service.start_coordination_run()}

    @app.get("/candidates")
    def candidates(x_tenant_id: str | None = Header(default=None)) -> list[dict[str, Any]]:
        require_tenant(x_tenant_id)
        return [_jsonable(candidate) for candidate in coordinator_service.list_candidates()]

    @app.get("/meeting-surface")
    def meeting_surface(x_tenant_id: str | None = Header(default=None)) -> list[dict[str, Any]]:
        require_tenant(x_tenant_id)
        return [_jsonable(candidate) for candidate in coordinator_service.get_meeting_surface()]

    @app.get("/queue")
    def queue(x_tenant_id: str | None = Header(default=None)) -> list[dict[str, Any]]:
        require_tenant(x_tenant_id)
        return [_jsonable(candidate) for candidate in coordinator_service.get_queue()]

    @app.get("/metrics")
    def metrics(x_tenant_id: str | None = Header(default=None)) -> dict[str, Any]:
        require_tenant(x_tenant_id)
        return coordinator_service.metrics().as_dict()

    @app.post("/lcaes/detect")
    def lcaes_detect(x_api_key: str | None = Header(default=None), x_tenant_id: str | None = Header(default=None)) -> list[dict[str, Any]]:
        require_mutation_auth(x_api_key)
        require_tenant(x_tenant_id)
        return [_jsonable(error) for error in coordinator_service.detect_lcaes()]

    @app.post("/gates/evaluate")
    def gates_evaluate(request: GateEvaluationRequest, x_api_key: str | None = Header(default=None), x_tenant_id: str | None = Header(default=None), idempotency_key: str | None = Header(default=None)) -> dict[str, Any]:
        require_mutation_auth(x_api_key)
        require_tenant(x_tenant_id)

        def evaluate():
            definitions = tuple(GateDefinition(**definition) for definition in request.definitions)
            results = {gate_id: GateResult(result) for gate_id, result in request.results.items()}
            decision = GateGraph(definitions).evaluate(results, request.stage)
            coordinator_service.coordinator.gate_evaluations.extend((decision.blockers + decision.warnings + tuple(decision.unknowns)))
            return decision

        return _jsonable(coordinator_service.idempotent(idempotency_key, "gate-evaluation", evaluate))

    @app.post("/exposure/evaluate")
    def exposure_evaluate(requests: tuple[ExposureRequest, ...], x_tenant_id: str | None = Header(default=None)) -> dict[str, Any]:
        require_tenant(x_tenant_id)
        if not requests:
            raise HTTPException(status_code=422, detail="at least one exposure is required")
        limit = requests[0].concentration_limit
        if any(request.concentration_limit != limit for request in requests):
            raise HTTPException(status_code=422, detail="concentration limit must be consistent")
        return _jsonable(summarize_exposure((Exposure(**request.model_dump(exclude={"concentration_limit"})) for request in requests), limit))

    @app.post("/conviction/assess")
    def conviction_assess(request: ConvictionRequest, x_tenant_id: str | None = Header(default=None)) -> dict[str, Any]:
        require_tenant(x_tenant_id)
        base_rate = BaseRate(request.strategy_family, request.successes, request.failures)
        analogs = tuple(Analog(bool(analog["outcome"]), Decimal(str(analog["similarity"])), Decimal(str(analog["time_to_event"]))) for analog in request.analogs)
        features = ConvictionFeatures(**{name: Decimal(str(value)) for name, value in request.features.items()})
        uncertainty = Uncertainty(request.model_uncertainty, request.path_uncertainty, request.data_uncertainty)
        return _jsonable(coordinator_service.assess_conviction(base_rate, analogs, features, request.expected_gain, request.expected_loss, request.costs, uncertainty))

    @app.post("/trade-sets", status_code=201)
    def trade_set(request: TradeSetRequest, x_api_key: str | None = Header(default=None), x_tenant_id: str | None = Header(default=None), idempotency_key: str | None = Header(default=None)) -> dict[str, Any]:
        require_mutation_auth(x_api_key)
        require_tenant(x_tenant_id)

        def create():
            sleeves = []
            for values in request.sleeves:
                normalized = dict(values)
                normalized["expected_gain"] = Decimal(str(normalized["expected_gain"]))
                normalized["expected_loss"] = Decimal(str(normalized["expected_loss"]))
                if normalized.get("probability") is not None:
                    normalized["probability"] = Decimal(str(normalized["probability"]))
                sleeves.append(Sleeve(**normalized))
            candidate = Candidate(request.candidate_id, CandidateType.BRANDED_TRADE_SET, request.name, request.thesis, request.catalyst, request.horizon, state=CandidateState.VIABLE, sleeves=tuple(sleeves), tenant_id=configured_tenant)
            package = build_trade_set(candidate)
            coordinator_service.coordinator.register_candidate(candidate)
            return package

        try:
            return _jsonable(coordinator_service.idempotent(idempotency_key, "trade-set", create))
        except ValueError as error:
            raise HTTPException(status_code=422, detail=str(error)) from error

    @app.post("/handoffs/trade-tf", status_code=201)
    def trade_tf_handoff(candidate_id: str, x_api_key: str | None = Header(default=None), x_tenant_id: str | None = Header(default=None), idempotency_key: str | None = Header(default=None)) -> dict[str, Any]:
        require_mutation_auth(x_api_key)
        require_tenant(x_tenant_id)
        try:
            return _jsonable(coordinator_service.idempotent(idempotency_key, "trade-tf-handoff", lambda: coordinator_service.create_trade_tf_handoff(candidate_id)))
        except KeyError as error:
            raise HTTPException(status_code=404, detail=f"candidate {candidate_id} not found") from error
        except ValueError as error:
            raise HTTPException(status_code=422, detail=str(error)) from error

    @app.post("/handoffs/algo-tf", status_code=201)
    def algo_tf_handoff(candidate_id: str, sleeve_id: str, x_api_key: str | None = Header(default=None), x_tenant_id: str | None = Header(default=None), idempotency_key: str | None = Header(default=None)) -> dict[str, Any]:
        require_mutation_auth(x_api_key)
        require_tenant(x_tenant_id)
        try:
            return _jsonable(coordinator_service.idempotent(idempotency_key, "algo-tf-handoff", lambda: coordinator_service.create_algo_tf_handoff(candidate_id, sleeve_id)))
        except KeyError as error:
            raise HTTPException(status_code=404, detail=f"candidate {candidate_id} not found") from error
        except ValueError as error:
            raise HTTPException(status_code=422, detail=str(error)) from error

    @app.post("/handoffs/execution", status_code=201)
    def execution_handoff(candidate_id: str, request: ExecutionHandoffRequest, x_api_key: str | None = Header(default=None), x_tenant_id: str | None = Header(default=None), idempotency_key: str | None = Header(default=None)) -> dict[str, Any]:
        require_mutation_auth(x_api_key)
        require_tenant(x_tenant_id)
        try:
            return _jsonable(coordinator_service.idempotent(idempotency_key, "execution-handoff", lambda: coordinator_service.create_execution_handoff(candidate_id, request.proposal_id, request.payload_hash)))
        except ValueError as error:
            raise HTTPException(status_code=422, detail=str(error)) from error

    @app.post("/candidates/{candidate_id}/sleeves/{sleeve_id}/algo", status_code=201)
    def promote_algo(candidate_id: str, sleeve_id: str, x_api_key: str | None = Header(default=None), x_tenant_id: str | None = Header(default=None), idempotency_key: str | None = Header(default=None)) -> dict[str, Any]:
        require_mutation_auth(x_api_key)
        require_tenant(x_tenant_id)
        try:
            result = coordinator_service.idempotent(idempotency_key, "algo-promotion", lambda: coordinator_service.promote_sleeve_to_algo(candidate_id, sleeve_id))
        except KeyError as error:
            raise HTTPException(status_code=404, detail=f"candidate {candidate_id} not found") from error
        except ValueError as error:
            raise HTTPException(status_code=422, detail=str(error)) from error
        return _jsonable(result)

    @app.post("/evidence", status_code=201)
    def evidence(request: EvidenceRequest, x_api_key: str | None = Header(default=None), idempotency_key: str | None = Header(default=None), x_tenant_id: str | None = Header(default=None)) -> dict[str, Any]:
        require_mutation_auth(x_api_key)
        require_tenant(x_tenant_id)
        try:
            record = coordinator_service.idempotent(idempotency_key, "evidence", lambda: coordinator_service.register_evidence(EvidenceRecord(**request.model_dump())))
        except ValueError as error:
            raise HTTPException(status_code=422, detail=str(error)) from error
        return _jsonable(record)

    @app.get("/evidence/{evidence_id}")
    def get_evidence(evidence_id: str, x_tenant_id: str | None = Header(default=None)) -> dict[str, Any]:
        require_tenant(x_tenant_id)
        try:
            return _jsonable(coordinator_service.get_evidence(evidence_id))
        except KeyError as error:
            raise HTTPException(status_code=404, detail=f"evidence {evidence_id} not found") from error

    @app.post("/candidates/{candidate_id}/outcome", status_code=201)
    def outcome(candidate_id: str, request: OutcomeRequest, x_api_key: str | None = Header(default=None), idempotency_key: str | None = Header(default=None), x_tenant_id: str | None = Header(default=None)) -> dict[str, Any]:
        require_mutation_auth(x_api_key)
        require_tenant(x_tenant_id)
        try:
            result = coordinator_service.idempotent(idempotency_key, "outcome", lambda: coordinator_service.record_outcome(ShadowOutcome(candidate_id, **request.model_dump())))
        except KeyError as error:
            raise HTTPException(status_code=404, detail=f"candidate {candidate_id} not found") from error
        return _jsonable(result)

    @app.post("/packets", status_code=201)
    def packet(request: PacketRequest, x_api_key: str | None = Header(default=None), idempotency_key: str | None = Header(default=None), x_tenant_id: str | None = Header(default=None)) -> dict[str, Any]:
        require_mutation_auth(x_api_key)
        require_tenant(x_tenant_id)
        try:
            result = coordinator_service.idempotent(idempotency_key, "packet", lambda: coordinator_service.submit_agent_packet(AgentPacket(**request.model_dump())))
        except ValueError as error:
            raise HTTPException(status_code=422, detail=str(error)) from error
        return _jsonable(result)

    @app.get("/coverage")
    def coverage(x_tenant_id: str | None = Header(default=None)) -> dict[str, Any]:
        require_tenant(x_tenant_id)
        return _jsonable(coordinator_service.get_coverage_matrix().cells)

    @app.post("/coverage/{factor}")
    def coverage_update(factor: str, request: CoverageRequest, x_api_key: str | None = Header(default=None), idempotency_key: str | None = Header(default=None), x_tenant_id: str | None = Header(default=None)) -> dict[str, Any]:
        require_mutation_auth(x_api_key)
        require_tenant(x_tenant_id)
        try:
            def update_coverage():
                if request.packet_id is None:
                    return coordinator_service.get_coverage_matrix().assign(factor, request.owner)
                return coordinator_service.get_coverage_matrix().answer(factor, request.owner, request.packet_id)

            result = coordinator_service.idempotent(idempotency_key, "coverage", update_coverage)
        except (KeyError, ValueError) as error:
            raise HTTPException(status_code=422, detail=str(error)) from error
        return _jsonable(result)

    @app.get("/independence")
    def independence(x_tenant_id: str | None = Header(default=None)) -> list[dict[str, Any]]:
        require_tenant(x_tenant_id)
        return [_jsonable(record) for record in coordinator_service.get_agent_independence()]

    @app.post("/independence", status_code=201)
    def independence_register(request: IndependenceRequest, x_api_key: str | None = Header(default=None), idempotency_key: str | None = Header(default=None), x_tenant_id: str | None = Header(default=None)) -> dict[str, Any]:
        require_mutation_auth(x_api_key)
        require_tenant(x_tenant_id)
        return _jsonable(coordinator_service.idempotent(idempotency_key, "independence", lambda: coordinator_service.register_independence(IndependenceRecord(**request.model_dump()))))

    @app.post("/candidates", status_code=201)
    def register(request: CandidateRequest, x_api_key: str | None = Header(default=None), idempotency_key: str | None = Header(default=None), x_tenant_id: str | None = Header(default=None)) -> dict[str, Any]:
        require_mutation_auth(x_api_key)
        require_tenant(x_tenant_id)
        try:
            values = {**request.model_dump(), "tenant_id": configured_tenant}
            candidate = coordinator_service.idempotent(idempotency_key, "candidate", lambda: coordinator_service.coordinator.register_candidate(Candidate(**values)))
        except ValueError as error:
            raise HTTPException(status_code=409, detail=str(error)) from error
        return _jsonable(candidate)

    @app.get("/candidates/{candidate_id}/audit")
    def audit(candidate_id: str, x_tenant_id: str | None = Header(default=None)) -> dict[str, Any]:
        require_tenant(x_tenant_id)
        try:
            return _jsonable(coordinator_service.get_audit_view(candidate_id))
        except KeyError as error:
            raise HTTPException(status_code=404, detail=f"candidate {candidate_id} not found") from error

    @app.post("/candidates/{candidate_id}/disposition")
    def disposition(candidate_id: str, request: DispositionRequest, x_api_key: str | None = Header(default=None), idempotency_key: str | None = Header(default=None), x_tenant_id: str | None = Header(default=None)) -> dict[str, Any]:
        require_mutation_auth(x_api_key)
        require_tenant(x_tenant_id)

        def apply_disposition():
            if request.disposition not in {CandidateState.BACK_BURNER, CandidateState.DISCARDED, CandidateState.ARCHIVED}:
                raise ValueError("disposition must be BACK_BURNER, DISCARDED, or ARCHIVED")
            return coordinator_service.coordinator.transition(candidate_id, request.disposition, request.reason, request.expected_version)

        try:
            candidate = coordinator_service.idempotent(idempotency_key, "disposition", apply_disposition)
        except KeyError as error:
            raise HTTPException(status_code=404, detail=f"candidate {candidate_id} not found") from error
        except ValueError as error:
            raise HTTPException(status_code=409, detail=str(error)) from error
        return _jsonable(candidate)

    @app.post("/candidates/{candidate_id}/transition")
    def transition(candidate_id: str, request: TransitionRequest, x_api_key: str | None = Header(default=None), idempotency_key: str | None = Header(default=None), x_tenant_id: str | None = Header(default=None)) -> dict[str, Any]:
        require_mutation_auth(x_api_key)
        require_tenant(x_tenant_id)
        try:
            result = coordinator_service.idempotent(idempotency_key, "transition", lambda: coordinator_service.coordinator.transition(candidate_id, request.state, request.reason, request.expected_version))
        except KeyError as error:
            raise HTTPException(status_code=404, detail=f"candidate {candidate_id} not found") from error
        except ValueError as error:
            raise HTTPException(status_code=409, detail=str(error)) from error
        return _jsonable(result)


    @app.post("/candidates/{candidate_id}/proposal", status_code=201)
    def proposal(candidate_id: str, request: ProposalRequest, x_api_key: str | None = Header(default=None), idempotency_key: str | None = Header(default=None), x_tenant_id: str | None = Header(default=None)) -> dict[str, Any]:
        require_mutation_auth(x_api_key)
        require_tenant(x_tenant_id)
        try:
            result = coordinator_service.idempotent(idempotency_key, "proposal", lambda: coordinator_service.coordinator.generate_execution_proposal(candidate_id, **request.model_dump()))
        except KeyError as error:
            raise HTTPException(status_code=404, detail=f"candidate {candidate_id} not found") from error
        except ValueError as error:
            raise HTTPException(status_code=409, detail=str(error)) from error
        return _jsonable(result)

    @app.post("/proposals/{proposal_id}/approve")
    def approve(proposal_id: str, request: ApprovalRequest, x_api_key: str | None = Header(default=None), idempotency_key: str | None = Header(default=None), x_tenant_id: str | None = Header(default=None)) -> dict[str, Any]:
        require_mutation_auth(x_api_key)
        require_tenant(x_tenant_id)
        try:
            result = coordinator_service.idempotent(idempotency_key, "approval", lambda: coordinator_service.coordinator.approve_exact(proposal_id, request.payload_hash))
        except KeyError as error:
            raise HTTPException(status_code=404, detail=f"proposal {proposal_id} not found") from error
        except ValueError as error:
            raise HTTPException(status_code=409, detail=str(error)) from error
        return _jsonable(result)

    return app