"""FastAPI adapter for the Coordinator service."""

from dataclasses import asdict
from datetime import datetime
from decimal import Decimal
import os
from typing import Any
from pathlib import Path

from .coordinator import Candidate, CandidateState, CandidateType, Coordinator
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


def create_app(service: CoordinatorService | None = None, database_path: str | None = None):
    try:
        from fastapi import FastAPI, HTTPException
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

    if service is None:
        configured_path = database_path or os.environ.get("EIG_DATABASE_PATH", ":memory:")
        coordinator_service = CoordinatorService(Coordinator(registry=SQLiteRegistry(configured_path)))
    else:
        coordinator_service = service
    app = FastAPI(title="HedgeHog Trade Coordinator", version="0.1.0")

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

    @app.post("/candidates", status_code=201)
    def register(request: CandidateRequest) -> dict[str, Any]:
        try:
            candidate = coordinator_service.coordinator.register_candidate(Candidate(**request.model_dump()))
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
    def disposition(candidate_id: str, request: DispositionRequest) -> dict[str, Any]:
        try:
            candidate = coordinator_service.coordinator.set_disposition(candidate_id, request.disposition, request.reason)
        except KeyError as error:
            raise HTTPException(status_code=404, detail=f"candidate {candidate_id} not found") from error
        except ValueError as error:
            raise HTTPException(status_code=409, detail=str(error)) from error
        return _jsonable(candidate)

    @app.post("/candidates/{candidate_id}/proposal", status_code=201)
    def proposal(candidate_id: str, request: ProposalRequest) -> dict[str, Any]:
        try:
            result = coordinator_service.coordinator.generate_execution_proposal(candidate_id, **request.model_dump())
        except KeyError as error:
            raise HTTPException(status_code=404, detail=f"candidate {candidate_id} not found") from error
        except ValueError as error:
            raise HTTPException(status_code=409, detail=str(error)) from error
        return _jsonable(result)

    @app.post("/proposals/{proposal_id}/approve")
    def approve(proposal_id: str, request: ApprovalRequest) -> dict[str, Any]:
        try:
            result = coordinator_service.coordinator.approve_exact(proposal_id, request.payload_hash)
        except KeyError as error:
            raise HTTPException(status_code=404, detail=f"proposal {proposal_id} not found") from error
        except ValueError as error:
            raise HTTPException(status_code=409, detail=str(error)) from error
        return _jsonable(result)

    return app