# Agentic Robotics Fleet Operations Center

A local, reproducible portfolio project for monitoring a simulated warehouse robot fleet, detecting incidents, and helping an operator investigate them safely.

> **Project status:** The simulator, telemetry pipeline, deterministic incident detection, investigation service, local dashboard, and one operator-approved simulation-only recovery action are implemented. Thirty-nine unit and API integration tests cover seeded fault scenarios, investigation evidence, telemetry validation, duplicate-alert prevention, and the recovery approval flow. A GitHub Actions workflow is configured to run the suite on pushes and pull requests.

## Project goals

The MVP is intended to:

- Simulate a small fleet and reproducible operational faults.
- Validate and persist telemetry, then detect incidents with deterministic rules.
- Let an AI agent investigate incidents through read-only tools and return evidence-backed recommendations.
- Present fleet status and incident history in an operator dashboard.
- Require explicit operator approval for allowlisted, simulation-only recovery demonstrations and record an audit trail.
- Keep the core workflow useful when no language model is available.

The project will not connect to or control physical robots. It will not require paid APIs, paid cloud services, or subscriptions.

## Quick start

Requirements: Docker Desktop running with the WSL 2 Linux engine. From the repository root in PowerShell:

    docker compose -f simulator/compose.yaml up --build -d
    Invoke-RestMethod http://localhost:8000/healthz

Open the dashboard at http://localhost:8501 and the API reference at http://localhost:8000/docs. The default simulator scenario is normal. Run the automated checks with:

    docker compose -f simulator/compose.yaml run --build --rm tests

To start a reproducible fault scenario, select one of low_battery, blocked_route, disconnected, stalled_mission, or abnormal_sensor:

    $env:FLEET_SCENARIO = "blocked_route"
    $env:FLEET_SEED = "7"
    docker compose -f simulator/compose.yaml up -d --force-recreate simulator
    Remove-Item Env:FLEET_SCENARIO
    Remove-Item Env:FLEET_SEED

The simulator uses three robots and a new run ID at each start. The selected fault and seeded initial state are repeatable; run IDs and wall-clock timestamps are expected to differ. Stop the services with docker compose -f simulator/compose.yaml down. This preserves the Docker-managed database volume.
## Agreed technology direction

Docker Compose, ROS 2 Jazzy, Gazebo Harmonic, Python with rclpy, FastAPI, SQLite, Streamlit, pytest, and GitHub Actions. A local language model may be evaluated as an optional, replaceable provider.

## Safety boundaries

- The agent's investigation tools are read-only.
- Recommendations are separate from execution.
- An operator must explicitly approve any allowlisted simulated recovery action.
- Deterministic detection and tests must not depend on a language model.
- Reports must distinguish measured facts from hypotheses and cite supporting evidence.

## Repository structure

- src/fleet_ops/ — Python application package as implementation begins.
- docs/requirements.md — agreed MVP scope and acceptance criteria.
- docs/architecture.md — agreed component design and safety boundaries.
- docs/development.md — repository and development conventions.
- docs/testing.md — automated test scope and run instructions.
- docs/release-readiness.md — acceptance status, observed verification, and remaining publication work.
- docs/decisions/ — accepted architecture decisions.

## Current status

The simulator and backend run through Docker Compose. The backend exposes health, telemetry, incident, investigation, and recovery-request APIs; storage uses a Docker-managed SQLite volume. Incident detection uses five deterministic rules. The investigation service stores fact-separated reports and cannot approve or execute actions. For an active disconnected-robot incident, the dashboard can request a simulated reconnect, record an explicit operator decision, and display the audit history. The simulator action endpoint is internal to the Compose network and is not exposed on the host. The pytest suite covers incident detection, telemetry validation, duplicate active incident prevention, and the recovery workflow; run it using the Docker test command or the configured GitHub Actions workflow.

## License

This project is released under the MIT License. See LICENSE for the full terms.
