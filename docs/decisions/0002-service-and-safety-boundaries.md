# ADR 0002: Service and safety boundaries

- **Status:** Accepted
- **Date:** 2026-10-28

## Context

The simulator, operator application, and optional language model need clear boundaries. The project must remain useful without a model and must prevent model-generated recommendations from becoming autonomous robot-control commands.

## Decision

Use three Docker Compose services: simulator, backend, and dashboard. Keep ROS 2 communication inside the simulator service. Send normalized telemetry to the FastAPI backend over HTTP; the Streamlit dashboard also uses the backend API. The backend owns validation, deterministic incident detection, SQLite persistence, read-only agent tools, operator approval checks, and audit records.

The agent receives read-only investigation tools. A separate operator flow may request only allowlisted simulated recovery actions after explicit approval. The MVP has no physical-robot connection and sends no motor commands.

## Consequences

- ROS 2 discovery does not need to cross container boundaries.
- Core detection remains testable with the model unavailable.
- The operator approval and action outcome can be audited.
- The approved action handler must remain limited to simulation state.
