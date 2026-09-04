"""FastAPI adapter for the Coordinator service."""

from dataclasses import asdict
from datetime import datetime
from decimal import Decimal
import os
from typing import Any
from pathlib import Path

from .coordinator import Candidate, CandidateState, CandidateType, Coordinator
from .coordination import AgentPacket, CoverageStatus, IndependenceRecord, Vote
from .evidence import EvidenceModality, EvidenceRecord
from .analytics import ShadowOutcome
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

    if service is None:
        configured_path = database_path or os.environ.get("EIG_DATABASE_PATH", ":memory:")
        configured_tenant = tenant_id or os.environ.get("EIG_TENANT_ID", "default")
        coordinator_service = CoordinatorService(Coordinator(registry=SQLiteRegistry(configured_path), tenant_id=configured_tenant))
    else:
        coordinator_service = service
    app = FastAPI(title="HedgeHog Trade Coordinator", version="0.1.0")

    def require_mutation_auth(api_key: str | None) -> None:
        expected = os.environ.get("EIG_API_KEY")
        if expected and api_key != expected:
            raise HTTPException(status_code=401, detail="authenticated mutation required")

    ui_path = Path(__file__).resolve().parents[2] / "ui" / "index.html"

    @app.get("/ui", include_in_schema=False)
    def ui():
        from fastapi.responses import HTMLResponse
        if not ui_path.exists():
            raise HTTPException(status_code=404, detail="UI asset not installed")
        return HTMLResponse(ui_path.read_text(encoding="utf-8"))

    @app.get("/health")
    def health() -> dict[str, str]:
        return {"status": "ok", "run_id": coordinator_service.start_coordination_run()}

    @app.get("/candidates")
    def candidates() -> list[dict[str, Any]]:
        return [_jsonable(candidate) for candidate in coordinator_service.list_candidates()]

    @app.get("/meeting-surface")
    def meeting_surface() -> list[dict[str, Any]]:
        return [_jsonable(candidate) for candidate in coordinator_service.get_meeting_surface()]

    @app.post("/evidence", status_code=201)
    def evidence(request: EvidenceRequest, x_api_key: str | None = Header(default=None), idempotency_key: str | None = Header(default=None)) -> dict[str, Any]:
        require_mutation_auth(x_api_key)
        try:
            record = coordinator_service.idempotent(idempotency_key, "evidence", lambda: coordinator_service.register_evidence(EvidenceRecord(**request.model_dump())))
        except ValueError as error:
            raise HTTPException(status_code=422, detail=str(error)) from error
        return _jsonable(record)

    @app.get("/evidence/{evidence_id}")
    def get_evidence(evidence_id: str) -> dict[str, Any]:
        try:
            return _jsonable(coordinator_service.get_evidence(evidence_id))
        except KeyError as error:
            raise HTTPException(status_code=404, detail=f"evidence {evidence_id} not found") from error

    @app.post("/candidates/{candidate_id}/outcome", status_code=201)
    def outcome(candidate_id: str, request: OutcomeRequest, x_api_key: str | None = Header(default=None), idempotency_key: str | None = Header(default=None)) -> dict[str, Any]:
        require_mutation_auth(x_api_key)
        try:
            result = coordinator_service.idempotent(idempotency_key, "outcome", lambda: coordinator_service.record_outcome(ShadowOutcome(candidate_id, **request.model_dump())))
        except KeyError as error:
            raise HTTPException(status_code=404, detail=f"candidate {candidate_id} not found") from error
        return _jsonable(result)

    @app.post("/packets", status_code=201)
    def packet(request: PacketRequest, x_api_key: str | None = Header(default=None), idempotency_key: str | None = Header(default=None)) -> dict[str, Any]:
        require_mutation_auth(x_api_key)
        try:
            result = coordinator_service.idempotent(idempotency_key, "packet", lambda: coordinator_service.submit_agent_packet(AgentPacket(**request.model_dump())))
        except ValueError as error:
            raise HTTPException(status_code=422, detail=str(error)) from error
        return _jsonable(result)

    @app.get("/coverage")
    def coverage() -> dict[str, Any]:
        return _jsonable(coordinator_service.get_coverage_matrix().cells)

    @app.post("/coverage/{factor}")
    def coverage_update(factor: str, request: CoverageRequest) -> dict[str, Any]:
        try:
            if request.packet_id is None:
                result = coordinator_service.get_coverage_matrix().assign(factor, request.owner)
            else:
                result = coordinator_service.get_coverage_matrix().answer(factor, request.owner, request.packet_id)
        except (KeyError, ValueError) as error:
            raise HTTPException(status_code=422, detail=str(error)) from error
        return _jsonable(result)

    @app.get("/independence")
    def independence() -> list[dict[str, Any]]:
        return [_jsonable(record) for record in coordinator_service.get_agent_independence()]

    @app.post("/independence", status_code=201)
    def independence_register(request: IndependenceRequest, x_api_key: str | None = Header(default=None), idempotency_key: str | None = Header(default=None)) -> dict[str, Any]:
        require_mutation_auth(x_api_key)
        return _jsonable(coordinator_service.idempotent(idempotency_key, "independence", lambda: coordinator_service.register_independence(IndependenceRecord(**request.model_dump()))))

    @app.post("/candidates", status_code=201)
    def register(request: CandidateRequest, x_api_key: str | None = Header(default=None), idempotency_key: str | None = Header(default=None)) -> dict[str, Any]:
        require_mutation_auth(x_api_key)
        try:
            candidate = coordinator_service.idempotent(idempotency_key, "candidate", lambda: coordinator_service.coordinator.register_candidate(Candidate(**request.model_dump())))
        except ValueError as error:
            raise HTTPException(status_code=409, detail=str(error)) from error
        return _jsonable(candidate)

    @app.get("/candidates/{candidate_id}/audit")
    def audit(candidate_id: str) -> dict[str, Any]:
        try:
            return _jsonable(coordinator_service.get_audit_view(candidate_id))
        except KeyError as error:
            raise HTTPException(status_code=404, detail=f"candidate {candidate_id} not found") from error

    @app.post("/candidates/{candidate_id}/disposition")
    def disposition(candidate_id: str, request: DispositionRequest, x_api_key: str | None = Header(default=None), idempotency_key: str | None = Header(default=None)) -> dict[str, Any]:
        require_mutation_auth(x_api_key)

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

    @app.post("/candidates/{candidate_id}/proposal", status_code=201)
    def proposal(candidate_id: str, request: ProposalRequest, x_api_key: str | None = Header(default=None), idempotency_key: str | None = Header(default=None)) -> dict[str, Any]:
        require_mutation_auth(x_api_key)
        try:
            result = coordinator_service.idempotent(idempotency_key, "proposal", lambda: coordinator_service.coordinator.generate_execution_proposal(candidate_id, **request.model_dump()))
        except KeyError as error:
            raise HTTPException(status_code=404, detail=f"candidate {candidate_id} not found") from error
        except ValueError as error:
            raise HTTPException(status_code=409, detail=str(error)) from error
        return _jsonable(result)

    @app.post("/proposals/{proposal_id}/approve")
    def approve(proposal_id: str, request: ApprovalRequest, x_api_key: str | None = Header(default=None), idempotency_key: str | None = Header(default=None)) -> dict[str, Any]:
        require_mutation_auth(x_api_key)
        try:
            result = coordinator_service.idempotent(idempotency_key, "approval", lambda: coordinator_service.coordinator.approve_exact(proposal_id, request.payload_hash))
        except KeyError as error:
            raise HTTPException(status_code=404, detail=f"proposal {proposal_id} not found") from error
        except ValueError as error:
            raise HTTPException(status_code=409, detail=str(error)) from error
        return _jsonable(result)

    return app