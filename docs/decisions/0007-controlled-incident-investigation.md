# ADR 0007: Controlled incident investigation

- **Status:** Accepted
- **Decision date:** 2026-10-28

## Context

Operators need a concise, evidence-backed analysis of stored incidents. The model must remain optional, use local inference only, and have no path to robot-control functions or unrestricted data access.

## Decision

An investigation endpoint loads the incident and a bounded same-run telemetry window through fixed read-only database queries. It assembles measured facts with telemetry IDs, then produces a persisted report containing hypotheses, confidence, evidence references, fixed operator review suggestions, provider status, and limitations.

The deterministic provider is the default. An optional Ollama adapter may select only predefined hypothesis labels and evidence IDs from the supplied packet using a JSON-schema-constrained response. The adapter accepts only local endpoint hostnames. The backend supplies all report text and recommendations; invalid or unavailable local output falls back to deterministic findings. The model has no tools, SQL access, action endpoints, or ability to approve actions.

## Consequences

- Reports remain available when no model is installed or configured.
- Model-generated hypotheses cannot invent arbitrary report text or recommendations.
- Each hypothesis references server-selected evidence; measured facts are rendered by the backend.
- Reports are immutable records linked to the incident and SQLite telemetry history.
- Local inference may be slow on CPU hardware, and no model is installed or started by default.
- Investigation does not approve or execute recovery actions.
