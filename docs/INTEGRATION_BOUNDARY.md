# Coordinator Integration Boundary

This repository owns the Epistemic Integrity Gate and the Coordinator's
research, evidence, candidate, package, gate, latency, conviction, audit, and
approval-handoff concerns.

Trade-TF and Algo-TF are external standalone systems. They are not implemented
or persisted here. The Coordinator may emit a candidate, sleeve, mandate
request, or approved handoff contract for those systems, and may ingest their
typed results as agent packets or evidence. It must not duplicate their state
machines, strategy floats, execution adaptation, or broker behavior.

The Root Execution Engine remains the only boundary in this repository that
can accept a broker adapter. An external Trade-TF or Algo-TF integration must
still submit through that boundary and provide the exact proposal identity and
payload hash required by the approval contract.