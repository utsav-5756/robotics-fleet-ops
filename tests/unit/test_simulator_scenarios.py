import pytest

from fleet_simulator.scenario_state import (
    ROBOT_IDS,
    SCENARIOS,
    build_robot_state,
    initial_battery_levels,
    route_position,
)


EXPECTED_FAULTS = {
    "low_battery": ("LOW_BATTERY", "mission_state", "RETURNING"),
    "blocked_route": ("ROUTE_BLOCKED", "mission_state", "BLOCKED"),
    "disconnected": ("ROBOT_DISCONNECTED", "connected", False),
    "stalled_mission": ("MISSION_STALLED", "mission_state", "STALLED"),
    "abnormal_sensor": (
        "SENSOR_RANGE_ABNORMAL",
        "sensor_range_m",
        999.0,
    ),
}


def state_for(scenario, robot_id, index, tick=12):
    battery = initial_battery_levels(7)
    return build_robot_state(
        scenario=scenario,
        fault_robot_id="robot_02",
        robot_id=robot_id,
        index=index,
        tick=tick,
        initial_battery=battery[robot_id],
        initial_position=route_position(index, 0),
    )


@pytest.mark.parametrize("scenario", sorted(SCENARIOS))
def test_scenario_state_is_reproducible_and_affects_only_its_target(scenario):
    first = {
        robot_id: state_for(scenario, robot_id, index)
        for index, robot_id in enumerate(ROBOT_IDS)
    }
    second = {
        robot_id: state_for(scenario, robot_id, index)
        for index, robot_id in enumerate(ROBOT_IDS)
    }

    assert first == second
    for robot_id in ("robot_01", "robot_03"):
        assert first[robot_id]["connected"] is True
        assert first[robot_id]["fault_codes"] == []
        assert first[robot_id]["mission_state"] not in {"BLOCKED", "STALLED"}
        assert 4.8 <= first[robot_id]["sensor_range_m"] <= 5.2

    target = first["robot_02"]
    if scenario == "normal":
        assert target["fault_codes"] == []
        assert target["connected"] is True
    elif scenario == "low_battery":
        assert target["fault_codes"] == ["LOW_BATTERY"]
        assert target["battery_percentage"] <= 20.0
    else:
        fault_code, field, expected = EXPECTED_FAULTS[scenario]
        assert target["fault_codes"] == [fault_code]
        assert target[field] == expected


def test_disconnected_scenario_reports_healthy_state_after_simulated_reconnect():
    battery = initial_battery_levels(7)
    reconnected = build_robot_state(
        scenario="disconnected",
        fault_robot_id="robot_02",
        robot_id="robot_02",
        index=1,
        tick=12,
        initial_battery=battery["robot_02"],
        initial_position=route_position(1, 0),
        reconnected=True,
    )

    assert reconnected["connected"] is True
    assert reconnected["fault_codes"] == []