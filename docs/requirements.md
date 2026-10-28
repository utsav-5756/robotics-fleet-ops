# MVP Requirements and Acceptance Criteria

**Status:** Scope agreed. The operator-approved simulated reconnect workflow and automated test suite are implemented; test scope and latest local results are recorded in docs/testing.md.

## Purpose

Build a reproducible, locally runnable portfolio project that monitors a small warehouse robot fleet, detects operational faults, investigates incidents, and keeps recovery decisions under operator control.

## Required capabilities

1. Simulate a small fleet and publish robot position, battery, mission state, connectivity, and fault codes.
2. Reproduce low-battery, blocked-route, lost-connection, stalled-mission, and abnormal-sensor scenarios.
3. Validate, persist, and expose telemetry for inspection.
4. Detect incidents deterministically and prevent duplicate active alerts for the same ongoing fault.
5. Let an investigation agent use read-only tools for robot status, telemetry, fault history, and mission history.
6. Return findings, likely causes, confidence, and recommended next steps with supporting evidence; distinguish measured facts from hypotheses.
7. Present fleet health, incidents, historical telemetry, and recommendations in a dashboard.
8. Require explicit operator approval for allowlisted simulated recovery actions and retain an audit trail.
9. Keep simulation, detection, and tests useful when a language model is unavailable.

## Acceptance criteria

The MVP is ready to demonstrate when:

1. Documented instructions start it locally without paid APIs, paid cloud services, or required subscriptions.
2. A reproducible run simulates at least three robots and produces valid telemetry for each.
3. All five fault types can be triggered reproducibly and appear in telemetry.
4. Deterministic detection identifies each injected fault and avoids repeated active alerts for the same ongoing incident.
5. An investigation retrieves relevant evidence and produces a recommendation that refers to that evidence.
6. A recovery action cannot be recorded as approved without an explicit operator approval step.
7. The audit trail records the incident, recommendation, approval decision, and action outcome.
8. The dashboard shows current fleet status and incident history.
9. Automated checks cover telemetry validation, fault detection, duplicate-alert prevention, and approval enforcement.
10. Documentation explains architecture, setup, safety boundaries, and known limitations.

Performance and runtime thresholds will be set after measuring the implementation on the development computer.

## Safety requirements

- The language model cannot issue direct motor commands or unrestricted robot-control instructions.
- Recommendations and execution remain separate.
- An operator explicitly approves a recovery action before the backend requests its allowlisted simulated outcome.
- Deterministic detection and core tests do not depend on model availability.
- Findings distinguish measured facts from hypotheses and cite evidence.

## Out of scope

- Connecting to or controlling physical robots.
- Autonomous execution of AI-generated recovery actions.
- Paid APIs, paid cloud services, or required subscriptions.
- Large-fleet or performance claims that have not been measured.
- Requiring a local language model; it may be evaluated as an optional enhancement.

## Progress reporting

These criteria describe the agreed target. They are not claims that the capabilities have been implemented or verified. Record completion only alongside the corresponding implementation and observed verification results.
