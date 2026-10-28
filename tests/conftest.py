import pytest
from fastapi.testclient import TestClient

from fleet_ops.api.app import app


@pytest.fixture
def client(tmp_path, monkeypatch):
    """Use a fresh SQLite database for each API test."""
    monkeypatch.setenv("FLEET_DATABASE_PATH", str(tmp_path / "fleet.sqlite3"))
    with TestClient(app) as test_client:
        yield test_client


@pytest.fixture
def telemetry_payload():
    """Return a valid disconnected robot sample with override support."""
    def build(**overrides):
        payload = {
            "run_id": "test-run-001",
            "robot_id": "robot_02",
            "sequence": 0,
            "scenario": "disconnected",
            "seed": 7,
            "simulation_time_ns": 0,
            "frame_id": "warehouse",
            "x_m": 1.0,
            "y_m": 0.0,
            "heading_rad": 0.0,
            "battery_percentage": 80.0,
            "mission_state": "EN_ROUTE",
            "connected": False,
            "fault_codes": ["ROBOT_DISCONNECTED"],
            "sensor_range_m": 5.0,
        }
        payload.update(overrides)
        return payload
    return build


@pytest.fixture
def create_incident(client, telemetry_payload):
    """Insert one sample and return the incident it deterministically opens."""
    def create(**overrides):
        payload = telemetry_payload(**overrides)
        response = client.post("/api/v1/telemetry", json=payload)
        assert response.status_code == 202
        incident_page = client.get(
            "/api/v1/incidents",
            params={
                "run_id": payload["run_id"],
                "robot_id": payload["robot_id"],
            },
        )
        assert incident_page.status_code == 200
        return next(
            incident
            for incident in incident_page.json()["items"]
            if incident["status"] == "ACTIVE"
        )
    return create