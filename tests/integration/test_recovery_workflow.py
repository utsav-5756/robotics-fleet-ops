from fleet_ops.api import recovery as recovery_service
from fleet_simulator.action_state import SimulatedReconnectState


def create_request(client, incident_id):
    reports = client.get(
        f"/api/v1/incidents/{incident_id}/investigations"
    ).json()["items"]
    if not reports:
        investigation = client.post(
            f"/api/v1/incidents/{incident_id}/investigations"
        )
        assert investigation.status_code == 201
    response = client.post(
        f"/api/v1/incidents/{incident_id}/recovery-requests"
    )
    assert response.status_code == 201
    return response.json()


def get_request_history(client, incident_id):
    response = client.get(
        f"/api/v1/incidents/{incident_id}/recovery-requests"
    )
    assert response.status_code == 200
    return response.json()


def test_request_is_pending_and_does_not_contact_simulator(
    client, create_incident, monkeypatch
):
    incident = create_incident()
    calls = []

    def unexpected_dispatch(_request):
        calls.append(True)
        raise AssertionError("Creating a request must not contact the simulator.")

    monkeypatch.setattr(recovery_service, "_send_simulator_action", unexpected_dispatch)
    first = create_request(client, incident["id"])
    second = create_request(client, incident["id"])

    assert first["status"] == "PENDING"
    assert second["id"] == first["id"]
    assert calls == []
    telemetry = client.get(
        "/api/v1/telemetry",
        params={"run_id": incident["run_id"], "robot_id": incident["robot_id"]},
    ).json()["items"]
    assert telemetry[0]["connected"] is False
    history = get_request_history(client, incident["id"])
    assert [event["event_type"] for event in history[0]["events"]] == ["REQUESTED"]
    request_details = history[0]["events"][0]["details"]
    saved_report = client.get(
        f"/api/v1/investigations/{request_details['investigation_id']}"
    ).json()
    recommendation = saved_report["recommended_next_steps"][0]
    assert request_details["recommendation"] == recommendation["recommendation"]
    assert request_details["recommendation_evidence_ids"] == recommendation["evidence_ids"]


def test_recovery_request_requires_a_saved_investigation(
    client, create_incident
):
    incident = create_incident()

    response = client.post(
        f"/api/v1/incidents/{incident['id']}/recovery-requests"
    )

    assert response.status_code == 409
    assert "investigation report" in response.json()["detail"].lower()


def test_recovery_request_requires_a_report_for_latest_incident_telemetry(
    client, create_incident, telemetry_payload
):
    incident = create_incident()
    first_report = client.post(
        f"/api/v1/incidents/{incident['id']}/investigations"
    )
    assert first_report.status_code == 201
    later_sample = telemetry_payload(
        sequence=1,
        simulation_time_ns=1_000_000_000,
    )
    assert client.post("/api/v1/telemetry", json=later_sample).status_code == 202

    stale_request = client.post(
        f"/api/v1/incidents/{incident['id']}/recovery-requests"
    )
    assert stale_request.status_code == 409
    assert "latest incident telemetry" in stale_request.json()["detail"].lower()

    fresh_report = client.post(
        f"/api/v1/incidents/{incident['id']}/investigations"
    )
    assert fresh_report.status_code == 201
    fresh_request = client.post(
        f"/api/v1/incidents/{incident['id']}/recovery-requests"
    )

    assert fresh_request.status_code == 201
    request_event = fresh_request.json()["events"][0]
    assert request_event["details"]["investigation_id"] == fresh_report.json()["id"]
    telemetry_items = client.get(
        "/api/v1/telemetry",
        params={
            "run_id": incident["run_id"],
            "robot_id": incident["robot_id"],
        },
    ).json()["items"]
    latest_telemetry_id = telemetry_items[0]["id"]
    assert request_event["details"]["recommendation_evidence_ids"] == [
        f"telemetry:{latest_telemetry_id}"
    ]


def test_rejection_is_audited_and_never_dispatches_action(
    client, create_incident, monkeypatch
):
    incident = create_incident()
    calls = []
    monkeypatch.setattr(
        recovery_service,
        "_send_simulator_action",
        lambda request: calls.append(request),
    )
    request = create_request(client, incident["id"])

    rejected = client.post(
        f"/api/v1/recovery-requests/{request['id']}/decision",
        json={"decision": "reject", "operator_label": "test operator"},
    )

    assert rejected.status_code == 200
    assert rejected.json()["status"] == "REJECTED"
    assert calls == []
    events = rejected.json()["events"]
    assert [event["event_type"] for event in events] == ["REQUESTED", "REJECTED"]

    replay = client.post(
        f"/api/v1/recovery-requests/{request['id']}/decision",
        json={"decision": "approve", "operator_label": "test operator"},
    )
    assert replay.status_code == 409
    assert calls == []


def test_explicit_approval_reconnects_robot_and_resolves_incident(
    client, create_incident, telemetry_payload, monkeypatch
):
    incident = create_incident()
    simulator = SimulatedReconnectState(
        incident["run_id"],
        "disconnected",
        incident["robot_id"],
        ("robot_01", "robot_02", "robot_03"),
    )
    dispatches = []

    def dispatch_to_simulator(request):
        dispatches.append(request["id"])
        status_code, result = simulator.apply(
            {
                "action_id": str(request["id"]),
                "run_id": request["run_id"],
                "robot_id": request["robot_id"],
                "action_type": request["action_type"],
            }
        )
        return {
            "confirmed": status_code == 200 and result.get("accepted") is True,
            "message": "simulator response",
            "simulator_status": result.get("status"),
        }

    monkeypatch.setattr(
        recovery_service, "_send_simulator_action", dispatch_to_simulator
    )
    request = create_request(client, incident["id"])
    assert request["status"] == "PENDING"
    assert not simulator.is_reconnected(incident["robot_id"])

    approved = client.post(
        f"/api/v1/recovery-requests/{request['id']}/decision",
        json={"decision": "approve", "operator_label": "portfolio reviewer"},
    )

    assert approved.status_code == 200
    result = approved.json()
    assert result["status"] == "EXECUTED"
    assert result["operator_label"] == "portfolio reviewer"
    assert simulator.is_reconnected(incident["robot_id"])
    assert dispatches == [request["id"]]
    assert [event["event_type"] for event in result["events"]] == [
        "REQUESTED",
        "APPROVED",
        "EXECUTION_CONFIRMED",
    ]

    healthy = telemetry_payload(
        run_id=incident["run_id"],
        robot_id=incident["robot_id"],
        sequence=1,
        connected=True,
        fault_codes=[],
    )
    telemetry_response = client.post("/api/v1/telemetry", json=healthy)
    assert telemetry_response.status_code == 202
    active = client.get(
        "/api/v1/incidents",
        params={"run_id": incident["run_id"], "status": "ACTIVE"},
    ).json()["items"]
    resolved = client.get(
        "/api/v1/incidents",
        params={"run_id": incident["run_id"], "status": "RESOLVED"},
    ).json()["items"]
    assert not any(item["id"] == incident["id"] for item in active)
    assert any(item["id"] == incident["id"] for item in resolved)

    replay = client.post(
        f"/api/v1/recovery-requests/{request['id']}/decision",
        json={"decision": "approve", "operator_label": "portfolio reviewer"},
    )
    assert replay.status_code == 409
    assert dispatches == [request["id"]]


def test_only_active_disconnection_incidents_can_request_recovery(
    client, create_incident
):
    battery_incident = create_incident(
        scenario="low_battery",
        battery_percentage=15.0,
        connected=True,
        fault_codes=["LOW_BATTERY"],
    )

    response = client.post(
        f"/api/v1/incidents/{battery_incident['id']}/recovery-requests"
    )

    assert response.status_code == 409


def test_resolved_incident_request_expires_without_dispatch(
    client, create_incident, telemetry_payload, monkeypatch
):
    incident = create_incident()
    calls = []
    monkeypatch.setattr(
        recovery_service,
        "_send_simulator_action",
        lambda request: calls.append(request),
    )
    request = create_request(client, incident["id"])
    healthy = telemetry_payload(
        run_id=incident["run_id"],
        robot_id=incident["robot_id"],
        sequence=1,
        connected=True,
        fault_codes=[],
    )
    assert client.post("/api/v1/telemetry", json=healthy).status_code == 202

    decision = client.post(
        f"/api/v1/recovery-requests/{request['id']}/decision",
        json={"decision": "approve", "operator_label": "test operator"},
    )

    assert decision.status_code == 409
    history = get_request_history(client, incident["id"])[0]
    assert history["status"] == "EXPIRED"
    assert [event["event_type"] for event in history["events"]] == [
        "REQUESTED",
        "EXPIRED",
    ]
    assert calls == []


def test_unconfirmed_execution_is_recorded_and_cannot_be_replayed(
    client, create_incident, monkeypatch
):
    incident = create_incident()
    calls = []

    def unconfirmed(_request):
        calls.append(True)
        return {"confirmed": False, "message": "Simulator did not confirm."}

    monkeypatch.setattr(recovery_service, "_send_simulator_action", unconfirmed)
    request = create_request(client, incident["id"])
    decision = client.post(
        f"/api/v1/recovery-requests/{request['id']}/decision",
        json={"decision": "approve", "operator_label": "test operator"},
    )

    assert decision.status_code == 200
    assert decision.json()["status"] == "FAILED"
    assert [event["event_type"] for event in decision.json()["events"]] == [
        "REQUESTED",
        "APPROVED",
        "EXECUTION_UNCONFIRMED",
    ]
    replay = client.post(
        f"/api/v1/recovery-requests/{request['id']}/decision",
        json={"decision": "approve", "operator_label": "test operator"},
    )
    assert replay.status_code == 409
    assert len(calls) == 1


def test_invalid_operator_label_does_not_decide_pending_request(
    client, create_incident
):
    incident = create_incident()
    request = create_request(client, incident["id"])

    response = client.post(
        f"/api/v1/recovery-requests/{request['id']}/decision",
        json={"decision": "approve", "operator_label": "   "},
    )

    assert response.status_code == 422
    history = get_request_history(client, incident["id"])[0]
    assert history["status"] == "PENDING"

def test_duplicate_active_fault_updates_one_incident(client, telemetry_payload):
    first_sample = telemetry_payload()
    first = client.post("/api/v1/telemetry", json=first_sample)
    second_sample = telemetry_payload(sequence=1, simulation_time_ns=1000000000)
    second = client.post("/api/v1/telemetry", json=second_sample)

    assert first.status_code == 202
    assert second.status_code == 202
    assert first.json()["duplicate"] is False
    assert second.json()["duplicate"] is False
    incidents = client.get(
        "/api/v1/incidents",
        params={
            "run_id": first_sample["run_id"],
            "robot_id": first_sample["robot_id"],
            "status": "ACTIVE",
        },
    ).json()["items"]
    assert len(incidents) == 1
    assert incidents[0]["observation_count"] == 2


def test_invalid_telemetry_is_rejected_without_persistence(
    client, telemetry_payload
):
    invalid = telemetry_payload(battery_percentage=101.0)

    response = client.post("/api/v1/telemetry", json=invalid)

    assert response.status_code == 422
    records = client.get(
        "/api/v1/telemetry",
        params={"run_id": invalid["run_id"], "robot_id": invalid["robot_id"]},
    ).json()["items"]
    assert records == []