import pytest

from fleet_ops.api.detector import detect_incidents
from fleet_ops.api.schemas import TelemetryIn


def make_telemetry(**overrides):
    values = {
        "run_id": "detector-test",
        "robot_id": "robot_01",
        "sequence": 1,
        "scenario": "normal",
        "seed": 7,
        "simulation_time_ns": 1_000_000_000,
        "frame_id": "warehouse",
        "x_m": 0.0,
        "y_m": 0.0,
        "heading_rad": 0.0,
        "battery_percentage": 75.0,
        "mission_state": "EN_ROUTE",
        "connected": True,
        "fault_codes": [],
        "sensor_range_m": 5.0,
    }
    values.update(overrides)
    return TelemetryIn(**values)


@pytest.mark.parametrize(
    ("overrides", "expected_type"),
    [
        ({"battery_percentage": 20.0}, "LOW_BATTERY"),
        ({"connected": False}, "ROBOT_DISCONNECTED"),
        ({"mission_state": "BLOCKED"}, "ROUTE_BLOCKED"),
        ({"mission_state": "STALLED"}, "MISSION_STALLED"),
        ({"sensor_range_m": 10.01}, "SENSOR_RANGE_ABNORMAL"),
    ],
)
def test_detects_each_supported_incident_rule(overrides, expected_type):
    incidents = detect_incidents(make_telemetry(**overrides))

    assert [incident["incident_type"] for incident in incidents] == [expected_type]


def test_normal_telemetry_does_not_create_an_incident():
    assert detect_incidents(make_telemetry()) == []


@pytest.mark.parametrize("sensor_range", [0.1, 10.0])
def test_sensor_range_boundary_values_are_accepted(sensor_range):
    incidents = detect_incidents(make_telemetry(sensor_range_m=sensor_range))

    assert all(item["incident_type"] != "SENSOR_RANGE_ABNORMAL" for item in incidents)


def test_fault_codes_trigger_the_matching_deterministic_rule():
    telemetry = make_telemetry(
        scenario="abnormal_sensor",
        fault_codes=["SENSOR_RANGE_ABNORMAL"],
    )

    incidents = detect_incidents(telemetry)

    assert [incident["incident_type"] for incident in incidents] == [
        "SENSOR_RANGE_ABNORMAL"
    ]
    assert incidents[0]["evidence"]["telemetry_sequence"] == 1