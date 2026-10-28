"""Pure deterministic fleet state and fault-scenario generation."""

import math
import random


ROBOT_IDS = ("robot_01", "robot_02", "robot_03")
SCENARIOS = {
    "normal",
    "low_battery",
    "blocked_route",
    "disconnected",
    "stalled_mission",
    "abnormal_sensor",
}


def initial_battery_levels(seed: int) -> dict[str, float]:
    """Return repeatable starting battery levels for the configured fleet."""
    battery_rng = random.Random(seed)
    return {
        robot_id: float(battery_rng.randint(82, 97))
        for robot_id in ROBOT_IDS
    }


def route_position(index: int, tick: int) -> tuple[float, float, float, bool]:
    """Return a repeatable kinematic position on one warehouse aisle."""
    lane_y = (-2.0, 0.0, 2.0)[index]
    distance = (0.25 * tick + 3.0 * index) % 10.0
    if distance <= 5.0:
        x = -5.0 + distance
        yaw = 0.0
        outbound = True
    else:
        x = 5.0 - (distance - 5.0)
        yaw = math.pi
        outbound = False
    return x, lane_y, yaw, outbound


def build_robot_state(
    *,
    scenario: str,
    fault_robot_id: str,
    robot_id: str,
    index: int,
    tick: int,
    initial_battery: float,
    initial_position: tuple[float, float, float, bool],
    reconnected: bool = False,
) -> dict:
    """Create one robot's state, applying only the selected target fault."""
    x, y, yaw, outbound = route_position(index, tick)
    is_fault_target = robot_id == fault_robot_id
    fault_codes = []
    mission_state = "EN_ROUTE" if outbound else "RETURNING"
    connected = True
    sensor_range_m = 5.0 + 0.2 * math.sin(0.15 * tick + index)
    battery = max(0.0, initial_battery - 0.01 * tick)

    if is_fault_target:
        if scenario in {"blocked_route", "disconnected", "stalled_mission"}:
            x, y, yaw, _ = initial_position

        if scenario == "low_battery":
            battery = max(5.0, 12.0 - 0.02 * tick)
            mission_state = "RETURNING"
            fault_codes.append("LOW_BATTERY")
        elif scenario == "blocked_route":
            mission_state = "BLOCKED"
            fault_codes.append("ROUTE_BLOCKED")
        elif scenario == "disconnected" and not reconnected:
            connected = False
            fault_codes.append("ROBOT_DISCONNECTED")
        elif scenario == "stalled_mission":
            mission_state = "STALLED"
            fault_codes.append("MISSION_STALLED")
        elif scenario == "abnormal_sensor":
            sensor_range_m = 999.0
            fault_codes.append("SENSOR_RANGE_ABNORMAL")

    return {
        "x": x,
        "y": y,
        "yaw": yaw,
        "battery_percentage": battery,
        "mission_state": mission_state,
        "connected": connected,
        "fault_codes": fault_codes,
        "sensor_range_m": sensor_range_m,
    }