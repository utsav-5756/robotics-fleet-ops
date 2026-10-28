# Development conventions

These conventions guide implementation while keeping the first version small and reviewable.

## Code organization

- Place shared Python application code under `src/fleet_ops/`.
- Keep domain rules and data validation independent of FastAPI, ROS 2, and any model provider where practical.
- Keep ROS 2 message handling at the simulator adapter boundary.
- Keep model access behind a replaceable interface; do not let provider-specific code define incident facts or safety rules.
- Add service-specific directories when their first implementation is ready rather than committing empty placeholders.

## Reliability and safety

- Make seeded scenarios reproducible.
- Validate telemetry before storing or using it.
- Keep incident detection deterministic and usable without a model.
- Give the investigation agent read-only tools only.
- Require explicit operator approval before any allowlisted simulated action.
- Keep physical robot control out of scope.
- Distinguish measured facts from hypotheses and preserve evidence references.

## Data and configuration

- Do not commit credentials, tokens, local environment files, or generated databases.
- Keep SQLite runtime data and generated build output in Docker-managed volumes.
- Document units and timestamp semantics when telemetry schemas are introduced.
- Avoid adding external services or paid APIs as requirements.

## Changes and verification

- Keep changes focused and explain design decisions in `docs/decisions/` when they affect the architecture or safety boundaries.
- Add automated checks with the relevant component; core checks must not require a language model or network access. Pure simulator scenario generation is tested independently of ROS and Gazebo.
- Record commands and observed results accurately. Do not describe an unrun check as passing.
- Run the unit and API integration suite with docker compose -f simulator/compose.yaml run --build --rm tests. GitHub Actions runs the pytest suite on pushes and pull requests.
