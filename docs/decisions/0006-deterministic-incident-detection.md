# ADR 0006: Deterministic incident detection

- **Status:** Accepted
- **Decision date:** 2026-10-28

## Context

The project needs repeatable, explainable incident detection that remains available when no language model is configured. Each incident must point to the telemetry facts that caused it, and repeated samples must not generate duplicate active alerts.

## Decision

The backend evaluates five deterministic rules when it accepts a new telemetry record: low battery (at or below 20%), disconnected robot, blocked route, stalled mission, and sensor range outside 0.1–10 meters. Matching simulator fault codes also activate their corresponding rules.

Incidents are scoped by simulator run, robot, and rule. One partial unique index permits only one active incident for that key. Matching samples update its observation count and latest evidence. A later non-matching sample resolves it; a future recurrence opens a new incident. Telemetry insertion and incident lifecycle changes share a SQLite transaction. The read-only API supports filtering by status, robot, and run.

## Consequences

- Detection outcomes are repeatable and do not depend on an AI provider.
- Each incident stores first and latest evidence referencing telemetry records.
- A simulator restart creates a new run, preserving prior incidents as history.
- Threshold changes require an explicit code/documentation update and should receive a new rule version before long-lived production use.
- This step does not recommend or execute recovery actions.
