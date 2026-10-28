# Deterministic incident rules

The backend evaluates each newly accepted telemetry record in the same SQLite transaction that stores it. Rules are deterministic and do not call a language model.

| Incident | Condition | Severity |
|---|---|---|
| `LOW_BATTERY` | Battery is at or below 20%, or the telemetry includes `LOW_BATTERY`. | Warning |
| `ROBOT_DISCONNECTED` | `connected` is false, or the telemetry includes `ROBOT_DISCONNECTED`. | High |
| `ROUTE_BLOCKED` | Mission state is `BLOCKED`, or the telemetry includes `ROUTE_BLOCKED`. | High |
| `MISSION_STALLED` | Mission state is `STALLED`, or the telemetry includes `MISSION_STALLED`. | High |
| `SENSOR_RANGE_ABNORMAL` | Sensor range is below 0.1 m or above 10 m, or the telemetry includes `SENSOR_RANGE_ABNORMAL`. | Medium |

## Lifecycle and duplicate suppression

Incidents are scoped to a simulator run, robot, and rule. The database allows only one active incident for that key. Repeated matching samples update the incident's last-seen time, latest evidence, and observation count instead of creating repeated incident rows. When a later sample for the same robot and run no longer matches a rule, that incident is marked resolved. If the condition returns, a new incident row is opened.

The evidence records the telemetry ID, run, robot, scenario, sequence, simulation timestamp, threshold where relevant, and the observed field values or fault codes. Both the first and latest evidence snapshots are retained. Since incidents belong to a run, use the `run_id` query parameter when reviewing one simulation execution.

## Inspect incidents

The read-only endpoint is `GET /api/v1/incidents`. Optional filters are `status=ACTIVE`, `robot_id=robot_02`, and `run_id=<run id>`. Results are capped at 500. The API's `/docs` page describes the response schema.
