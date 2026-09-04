-- Coordinator persistence baseline. Apply once per database.
CREATE TABLE IF NOT EXISTS candidates (
    candidate_id TEXT PRIMARY KEY,
    candidate_type TEXT NOT NULL CHECK (candidate_type IN ('BRANDED_TRADE_SET', 'ALGO_SINGLE')),
    tenant_id TEXT NOT NULL DEFAULT 'default',
    version INTEGER NOT NULL DEFAULT 0,
    payload TEXT NOT NULL,
    updated_at TEXT NOT NULL
);

CREATE TABLE IF NOT EXISTS lifecycle_events (
    event_id TEXT PRIMARY KEY,
    candidate_id TEXT NOT NULL REFERENCES candidates(candidate_id),
    payload TEXT NOT NULL
);

CREATE TABLE IF NOT EXISTS proposals (
    proposal_id TEXT PRIMARY KEY,
    candidate_id TEXT NOT NULL REFERENCES candidates(candidate_id),
    payload TEXT NOT NULL,
    UNIQUE (proposal_id, candidate_id)
);

CREATE TABLE IF NOT EXISTS shadow_outcomes (
    candidate_id TEXT PRIMARY KEY REFERENCES candidates(candidate_id),
    payload TEXT NOT NULL
);

CREATE TABLE IF NOT EXISTS evidence (
    evidence_id TEXT PRIMARY KEY,
    payload TEXT NOT NULL
);

CREATE TABLE IF NOT EXISTS agent_packets (
    packet_id TEXT PRIMARY KEY,
    run_id TEXT NOT NULL,
    payload TEXT NOT NULL
);

CREATE TABLE IF NOT EXISTS independence (
    agent_id TEXT PRIMARY KEY,
    payload TEXT NOT NULL
);

CREATE TABLE IF NOT EXISTS idempotency_keys (
    operation TEXT NOT NULL,
    key TEXT NOT NULL,
    created_at TEXT NOT NULL DEFAULT CURRENT_TIMESTAMP,
    PRIMARY KEY (operation, key)
);

CREATE INDEX IF NOT EXISTS lifecycle_events_candidate_idx
    ON lifecycle_events(candidate_id);
CREATE INDEX IF NOT EXISTS candidates_tenant_idx ON candidates(tenant_id);
CREATE INDEX IF NOT EXISTS proposals_candidate_idx
    ON proposals(candidate_id);
CREATE INDEX IF NOT EXISTS agent_packets_run_idx ON agent_packets(run_id);
