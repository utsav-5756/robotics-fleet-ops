# Automated tests

The project uses pytest for unit and API integration tests. The suite is designed to run without ROS, Gazebo, Ollama, cloud services, or access to the persistent simulator database.

## Run locally with Docker

From the repository root in PowerShell:

    docker compose -f simulator/compose.yaml run --build --rm tests

The test image uses a pinned Python base image and installs the pinned API and test dependency groups. Each API test gets a fresh SQLite database in a temporary directory.

## Continuous integration

The GitHub Actions workflow is configured to run pytest on pushes, pull requests, and manual workflow runs. It installs Python 3.12 and the project API/test extras.

## Latest local result

The Docker test command completed with 39 passing tests and one Starlette/AnyIO deprecation warning. The warning comes from the test client dependency; it did not cause a test failure.

## Coverage

Unit tests cover all five deterministic incident rules, normal telemetry, sensor boundaries, seeded simulator scenarios, and the simulator reconnect policy. Scenario tests verify repeatable state, target-only fault injection, and disconnected-state recovery. API integration tests cover evidence-backed investigation reports, persisted retrieval, local-model fallback, and rejection of citations outside the supplied evidence. They check that reconnects are limited to the selected robot and run, and that invalid, duplicate, or out-of-scope action requests are handled safely.

API integration tests cover telemetry validation and persistence, duplicate active incident prevention, and:

- Creating a pending recovery request without contacting or changing the simulator.
- Explicit rejection and its audit record.
- Explicit approval dispatching the allowlisted simulated action.
- A following connected telemetry sample resolving the incident.
- Expiring a pending request when its incident resolves before approval.
- Recording an unconfirmed simulator outcome and refusing to replay it.
- Rejecting unsupported incidents and invalid operator labels.

The API tests dispatch to the pure Python simulator policy in-process. They do not invoke the running Docker simulator or approve actions against its persistent database.