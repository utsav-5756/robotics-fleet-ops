# ADR 0005: Telemetry ingestion and persistence

- **Status:** Accepted
- **Decision date:** 2026-10-28

## Context

The simulator publishes typed ROS 2 telemetry. ROS discovery should remain inside the simulator container, while the backend needs a stable interface for validation, storage, and later consumers.

## Decision

A ROS adapter inside the simulator service forwards normalized JSON over HTTP to a FastAPI backend. The backend validates the payload and stores it in SQLite on a Docker-managed volume. A read-only bounded query and health endpoint support operator inspection and later dashboard integration.

Each simulator process uses a unique run ID by default. Telemetry writes are idempotent on `(run_id, robot_id, sequence)`, allowing the adapter to retry a request when the server response is lost. Simulation timestamps and server receipt timestamps are stored separately.

The adapter queues work outside its ROS callback and retries transient backend failures with bounded exponential delay. It uses a bounded in-memory queue; an offline disk spool is out of scope for this increment.

## Consequences

- ROS topics do not need to be exposed beyond the simulator container.
- SQLite data survives container recreation through a named volume.
- Same-seed scenario values remain reproducible while separate process runs do not collide in storage.
- A prolonged backend outage can fill the in-memory queue and lose later samples; the adapter logs this condition.
- The API provides a base for deterministic incident detection in a later step.
