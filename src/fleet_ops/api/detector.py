"""Deterministic rules for robot telemetry."""

from fleet_ops.api.schemas import TelemetryIn


LOW_BATTERY_THRESHOLD = 20.0
SENSOR_RANGE_MIN_M = 0.1
SENSOR_RANGE_MAX_M = 10.0


def detect_incidents(payload: TelemetryIn) -> list[dict]:
    """Return active incident conditions supported by one telemetry record."""
    faults = set(payload.fault_codes)
    common = {
        "run_id": payload.run_id,
        "robot_id": payload.robot_id,
        "scenario": payload.scenario,
        "telemetry_sequence": payload.sequence,
        "simulation_time_ns": payload.simulation_time_ns,
    }
    detected = []

    if payload.battery_percentage <= LOW_BATTERY_THRESHOLD or "LOW_BATTERY" in faults:
        detected.append(
            {
                "incident_type": "LOW_BATTERY",
                "severity": "WARNING",
                "summary": "Robot battery is at or below the 20% warning threshold.",
                "evidence": {
                    **common,
                    "battery_percentage": payload.battery_percentage,
                    "threshold_percentage": LOW_BATTERY_THRESHOLD,
                    "fault_codes": payload.fault_codes,
                },
            }
        )

    if not payload.connected or "ROBOT_DISCONNECTED" in faults:
        detected.append(
            {
                "incident_type": "ROBOT_DISCONNECTED",
                "severity": "HIGH",
                "summary": "Telemetry reports that the robot is disconnected.",
                "evidence": {
                    **common,
                    "connected": payload.connected,
                    "fault_codes": payload.fault_codes,
                },
            }
        )

    if payload.mission_state == "BLOCKED" or "ROUTE_BLOCKED" in faults:
        detected.append(
            {
                "incident_type": "ROUTE_BLOCKED",
                "severity": "HIGH",
                "summary": "Robot mission is blocked by a route condition.",
                "evidence": {
                    **common,
                    "mission_state": payload.mission_state,
                    "fault_codes": payload.fault_codes,
                },
            }
        )

    if payload.mission_state == "STALLED" or "MISSION_STALLED" in faults:
        detected.append(
            {
                "incident_type": "MISSION_STALLED",
                "severity": "HIGH",
                "summary": "Robot mission has stalled.",
                "evidence": {
                    **common,
                    "mission_state": payload.mission_state,
                    "fault_codes": payload.fault_codes,
                },
            }
        )

    if (
        payload.sensor_range_m < SENSOR_RANGE_MIN_M
        or payload.sensor_range_m > SENSOR_RANGE_MAX_M
        or "SENSOR_RANGE_ABNORMAL" in faults
    ):
        detected.append(
            {
                "incident_type": "SENSOR_RANGE_ABNORMAL",
                "severity": "MEDIUM",
                "summary": "Sensor range is outside the expected 0.1–10 m interval.",
                "evidence": {
                    **common,
                    "sensor_range_m": payload.sensor_range_m,
                    "expected_min_m": SENSOR_RANGE_MIN_M,
                    "expected_max_m": SENSOR_RANGE_MAX_M,
                    "fault_codes": payload.fault_codes,
                },
            }
        )

    return detected
