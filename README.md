# latency-contamination-engine

Shared multi-agent coordination primitives for running agent reasoning through a single latency contamination gate.

- Pre-agent gate sanitizes decision context, quarantines stale/inherited recommendations, and locks a shared strategy universe.
- Agent-level `validate_agent_input` assertions enforce that no agent runs on unsanitized context.
- Post-agent classification relabels agent outputs as `AGENT_HYPOTHESIS` with provenance and `NON_FACTUAL` authority.
