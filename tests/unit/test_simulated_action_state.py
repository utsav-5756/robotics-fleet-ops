import pytest

from fleet_simulator.action_state import SimulatedReconnectState


def make_state(scenario="disconnected"):
    return SimulatedReconnectState(
        run_id="run-123",
        scenario=scenario,
        fault_robot_id="robot_02",
        robot_ids=("robot_01", "robot_02", "robot_03"),
    )


def action_payload(**overrides):
    payload = {
        "action_id": "17",
        "run_id": "run-123",
        "robot_id": "robot_02",
        "action_type": "SIMULATED_RECONNECT",
    }
    payload.update(overrides)
    return payload


def test_allowed_reconnect_changes_only_the_target_simulated_state():
    state = make_state()

    status_code, result = state.apply(action_payload())

    assert status_code == 200
    assert result["accepted"] is True
    assert result["status"] == "APPLIED"
    assert state.is_reconnected("robot_02")
    assert not state.is_reconnected("robot_01")
    assert not state.is_reconnected("robot_03")


def test_repeating_the_same_request_id_is_idempotent():
    state = make_state()

    first = state.apply(action_payload())
    second = state.apply(action_payload())

    assert first[1]["status"] == "APPLIED"
    assert second[0] == 200
    assert second[1]["status"] == "ALREADY_APPLIED"
    assert len(state.applied_actions) == 1


@pytest.mark.parametrize(
    ("scenario", "overrides", "expected_status"),
    [
        ("disconnected", {"action_type": "MOVE_ROBOT"}, 400),
        ("disconnected", {"action_id": "not-numeric"}, 400),
        ("disconnected", {"run_id": "another-run"}, 409),
        ("disconnected", {"robot_id": "robot_01"}, 409),
        ("normal", {}, 409),
        ("disconnected", {"unexpected": "field"}, 400),
    ],
)
def test_invalid_or_out_of_scope_action_is_rejected_without_state_change(
    scenario,
    overrides,
    expected_status,
):
    state = make_state(scenario=scenario)

    status_code, result = state.apply(action_payload(**overrides))

    assert status_code == expected_status
    assert result["accepted"] is False
    assert not state.is_reconnected("robot_02")
    assert state.applied_actions == {}