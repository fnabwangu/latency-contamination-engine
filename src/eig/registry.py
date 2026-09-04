"""Small SQLite persistence boundary for Coordinator state.

SQLite is used here as the library's deployable default. The schema is explicit
and replaceable by a server-side repository without changing domain objects.
"""

from __future__ import annotations

import json
import sqlite3
from dataclasses import asdict
from datetime import datetime
from decimal import Decimal
from enum import Enum
from pathlib import Path
from typing import Any

from .coordinator import Candidate, CandidateState, CandidateType, ExecutionProposal, LifecycleEvent, Sleeve


def _encode(value: Any) -> Any:
    if isinstance(value, Enum):
        return value.value
    if isinstance(value, Decimal):
        return {"__decimal__": str(value)}
    if isinstance(value, datetime):
        return {"__datetime__": value.isoformat()}
    if isinstance(value, tuple):
        return [_encode(item) for item in value]
    if isinstance(value, dict):
        return {key: _encode(item) for key, item in value.items()}
    return value


def _decode(value: Any) -> Any:
    if isinstance(value, list):
        return tuple(_decode(item) for item in value)
    if isinstance(value, dict):
        if "__decimal__" in value:
            return Decimal(value["__decimal__"])
        if "__datetime__" in value:
            return datetime.fromisoformat(value["__datetime__"])
        return {key: _decode(item) for key, item in value.items()}
    return value


class SQLiteRegistry:
    """Transactional candidate/event store with idempotent candidate writes."""

    def __init__(self, path: str | Path = ":memory:") -> None:
        self.connection = sqlite3.connect(str(path), check_same_thread=False)
        self.connection.execute("PRAGMA foreign_keys = ON")
        self.connection.executescript(
            """
            CREATE TABLE IF NOT EXISTS candidates (
                candidate_id TEXT PRIMARY KEY,
                candidate_type TEXT NOT NULL,
                payload TEXT NOT NULL,
                updated_at TEXT NOT NULL
            );
            CREATE TABLE IF NOT EXISTS lifecycle_events (
                event_id TEXT PRIMARY KEY,
                candidate_id TEXT NOT NULL,
                payload TEXT NOT NULL,
                FOREIGN KEY(candidate_id) REFERENCES candidates(candidate_id)
            );
            CREATE TABLE IF NOT EXISTS proposals (
                proposal_id TEXT PRIMARY KEY,
                candidate_id TEXT NOT NULL,
                payload TEXT NOT NULL,
                FOREIGN KEY(candidate_id) REFERENCES candidates(candidate_id)
            );
            """
        )
        self.connection.commit()

    def save_candidate(self, candidate: Candidate) -> None:
        payload = json.dumps(_encode(asdict(candidate)), sort_keys=True)
        self.connection.execute(
            "INSERT INTO candidates(candidate_id, candidate_type, payload, updated_at) VALUES (?, ?, ?, datetime('now')) "
            "ON CONFLICT(candidate_id) DO UPDATE SET payload=excluded.payload, updated_at=excluded.updated_at",
            (candidate.candidate_id, candidate.candidate_type.value, payload),
        )
        self.connection.commit()

    def load_candidate(self, candidate_id: str) -> Candidate:
        row = self.connection.execute("SELECT payload FROM candidates WHERE candidate_id = ?", (candidate_id,)).fetchone()
        if row is None:
            raise KeyError(candidate_id)
        values = _decode(json.loads(row[0]))
        values["candidate_type"] = CandidateType(values["candidate_type"])
        values["state"] = CandidateState(values["state"])
        values["sleeves"] = tuple(Sleeve(**sleeve) for sleeve in values["sleeves"])
        if values["probability_range"] is not None:
            values["probability_range"] = tuple(values["probability_range"])
        return Candidate(**values)

    def load_candidates(self) -> tuple[Candidate, ...]:
        rows = self.connection.execute("SELECT candidate_id FROM candidates ORDER BY updated_at, candidate_id").fetchall()
        return tuple(self.load_candidate(row[0]) for row in rows)

    def append_event(self, event: LifecycleEvent) -> None:
        payload = json.dumps(_encode(asdict(event)), sort_keys=True)
        self.connection.execute(
            "INSERT OR IGNORE INTO lifecycle_events(event_id, candidate_id, payload) VALUES (?, ?, ?)",
            (event.event_id, event.candidate_id, payload),
        )
        self.connection.commit()

    def load_events(self, candidate_id: str) -> tuple[LifecycleEvent, ...]:
        rows = self.connection.execute("SELECT payload FROM lifecycle_events WHERE candidate_id = ? ORDER BY rowid", (candidate_id,)).fetchall()
        events = []
        for row in rows:
            values = _decode(json.loads(row[0]))
            if values["from_state"] is not None:
                values["from_state"] = CandidateState(values["from_state"])
            values["to_state"] = CandidateState(values["to_state"])
            events.append(LifecycleEvent(**values))
        return tuple(events)

    def save_proposal(self, proposal: ExecutionProposal) -> None:
        payload = json.dumps(_encode(asdict(proposal)), sort_keys=True)
        self.connection.execute(
            "INSERT INTO proposals(proposal_id, candidate_id, payload) VALUES (?, ?, ?) "
            "ON CONFLICT(proposal_id) DO UPDATE SET payload=excluded.payload",
            (proposal.proposal_id, proposal.candidate_id, payload),
        )
        self.connection.commit()

    def load_proposals(self) -> tuple[ExecutionProposal, ...]:
        rows = self.connection.execute("SELECT payload FROM proposals ORDER BY rowid").fetchall()
        return tuple(ExecutionProposal(**_decode(json.loads(row[0]))) for row in rows)

    def close(self) -> None:
        self.connection.close()