# Telemetry ingestion

The backend accepts normalized telemetry from the simulator over HTTP, validates it, and stores it in SQLite. ROS messages and ROS discovery stay inside the simulator service. A small ROS node forwards each message to the backend on a worker thread so HTTP waits do not block ROS callbacks.

## API

The backend is available locally at `http://localhost:8000`.

- `GET /healthz` reports API and SQLite availability.
- `POST /api/v1/telemetry` validates and persists one telemetry sample.
- `GET /api/v1/telemetry?robot_id=robot_02&limit=100` returns recent records. `run_id` can also be supplied as a filter. The maximum result count is 500.
- `GET /docs` provides the generated OpenAPI interface.

The ingestion payload maps the ROS header timestamp to `simulation_time_ns`, retains `frame_id`, and uses metric units in field names. The server adds `received_at_utc`, so simulation time and ingestion time remain distinguishable.

Validation rejects unknown fields, unsupported scenario or mission states, invalid identifiers, negative sequence/time values, non-finite measurements, and values outside documented bounds. Sensor range accepts up to 1000 meters to retain the simulator's deliberate abnormal-sensor scenario.

## Persistence and retries

SQLite is stored in the Docker-managed `fleet_data` volume at `/data/fleet.sqlite3`. Each record is unique by `(run_id, robot_id, sequence)`. The simulator creates a UUID run ID at process startup by default; its telemetry values remain reproducible for the same scenario and seed. Set `FLEET_RUN_ID` only when intentionally assigning a unique known ID to a run.

The simulator adapter uses a bounded in-memory queue and retries transient connection and server errors with exponential backoff. Client-side validation errors are logged and dropped. If the queue fills while the backend is unavailable, the adapter logs a dropped sample; this first implementation does not persist an offline spool.

## Run and inspect

From the repository root in PowerShell:

    docker compose -f simulator/compose.yaml up --build -d
    Invoke-RestMethod http://localhost:8000/healthz
    Invoke-RestMethod 'http://localhost:8000/api/v1/telemetry?limit=10'

Stop the services with:

    docker compose -f simulator/compose.yaml down

The SQLite volume is preserved by `down`; removing named volumes is a separate operation and is not part of the normal stop command.

## Incident detection

Accepted new telemetry is evaluated by the deterministic rules in [incident-rules.md](incident-rules.md). Active incidents and their evidence can be queried at `GET /api/v1/incidents`. Duplicate telemetry retries do not create a second incident evaluation because the telemetry insert is idempotent.