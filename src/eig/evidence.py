"""Immutable multimodal evidence records and provenance-aware storage."""

from __future__ import annotations

import hashlib
import json
import uuid
from dataclasses import dataclass, field
from datetime import datetime, timedelta
from enum import Enum
from typing import Any, Mapping

from .types import utcnow


class EvidenceModality(str, Enum):
    TEXT = "TEXT"
    STRUCTURED = "STRUCTURED"
    PDF = "PDF"
    FILING = "FILING"
    CHART = "CHART"
    SCREENSHOT = "SCREENSHOT"
    AUDIO_TRANSCRIPT = "AUDIO_TRANSCRIPT"
    GENERATED_VISUAL = "GENERATED_VISUAL"


@dataclass(frozen=True)
class EvidenceRecord:
    source: str
    captured_at: datetime
    effective_at: datetime
    modality: EvidenceModality
    content: str
    extractor_version: str = "native"
    confidence: float = 1.0
    claims: tuple[str, ...] = ()
    entities: tuple[str, ...] = ()
    candidate_ids: tuple[str, ...] = ()
    contradictions: tuple[str, ...] = ()
    expires_at: datetime | None = None
    evidence_id: str = field(default_factory=lambda: uuid.uuid4().hex[:12])

    def __post_init__(self) -> None:
        if not 0 <= self.confidence <= 1:
            raise ValueError("evidence confidence must be between 0 and 1")
        if self.expires_at is not None and self.expires_at <= self.effective_at:
            raise ValueError("evidence expiry must follow effective time")

    @property
    def content_hash(self) -> str:
        payload = {"source": self.source, "effective_at": self.effective_at.isoformat(), "content": self.content, "extractor_version": self.extractor_version}
        return hashlib.sha256(json.dumps(payload, sort_keys=True).encode()).hexdigest()

    def is_expired(self, now: datetime | None = None) -> bool:
        return self.expires_at is not None and (now or utcnow()) >= self.expires_at

    def with_ttl(self, ttl: timedelta) -> "EvidenceRecord":
        if ttl <= timedelta(0):
            raise ValueError("evidence TTL must be positive")
        return EvidenceRecord(**{**self.__dict__, "expires_at": self.effective_at + ttl})


class EvidenceStore:
    """Content-addressed in-memory evidence store for one coordination run."""

    def __init__(self) -> None:
        self.records: dict[str, EvidenceRecord] = {}
        self.by_hash: dict[str, str] = {}

    def register(self, record: EvidenceRecord) -> EvidenceRecord:
        existing = self.by_hash.get(record.content_hash)
        if existing is not None:
            return self.records[existing]
        self.records[record.evidence_id] = record
        self.by_hash[record.content_hash] = record.evidence_id
        return record

    def get(self, evidence_id: str) -> EvidenceRecord:
        return self.records[evidence_id]

    def for_candidate(self, candidate_id: str) -> tuple[EvidenceRecord, ...]:
        return tuple(record for record in self.records.values() if candidate_id in record.candidate_ids)

    def fresh(self, candidate_id: str, now: datetime | None = None) -> tuple[EvidenceRecord, ...]:
        return tuple(record for record in self.for_candidate(candidate_id) if not record.is_expired(now))