# ADR 0008: Local read-only operator dashboard

- **Status:** Accepted
- **Decision date:** 2026-10-28

## Context

Operators need one local view of fleet health, telemetry trends, incidents, and investigation reports. The dashboard must not bypass backend validation or the project's recovery approval boundary.

## Decision

Use a Streamlit service in Docker Compose. It calls the FastAPI backend over the Compose network and is published on the Windows host only through the loopback interface. It uses the existing health, telemetry, incident, and investigation endpoints.

The dashboard supports run and robot filters, fleet status, battery and sensor-range charts, incident evidence, saved reports, and an explicit request to create an investigation report. That request creates analysis only. The dashboard exposes no recovery approval or execution controls.

## Consequences

- The UI remains a thin API client and does not access ROS topics or SQLite directly.
- All services can be started with the existing Compose workflow.
- Dashboard access is local to the development machine.
- The screen reflects the newest bounded API sample window and requires a refresh to reload.
- Recovery approval and execution remain future work with separate safety controls.
