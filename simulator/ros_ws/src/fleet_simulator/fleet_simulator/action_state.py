"""ROS-independent policy and state for the simulated reconnect action."""

import threading
from typing import Any


class SimulatedReconnectState:
    """Apply an allowlisted reconnect once for the matching simulator run."""

    def __init__(
        self,
        run_id: str,
        scenario: str,
        fault_robot_id: str,
        robot_ids: tuple[str, ...],
    ) -> None:
        self.run_id = run_id
        self.scenario = scenario
        self.fault_robot_id = fault_robot_id
        self.robot_ids = robot_ids
        self.reconnected_robots: set[str] = set()
        self.applied_actions: dict[str, tuple[str, str, str]] = {}
        self._lock = threading.Lock()

    def is_reconnected(self, robot_id: str) -> bool:
        with self._lock:
            return robot_id in self.reconnected_robots

    def apply(self, payload: dict[str, Any]) -> tuple[int, dict[str, Any]]:
        """Validate a request and apply only SIMULATED_RECONNECT."""
        required = {"action_id", "run_id", "robot_id", "action_type"}
        if set(payload) != required:
            return 400, {"accepted": False, "message": "Invalid action fields."}

        action_id = payload.get("action_id")
        run_id = payload.get("run_id")
        robot_id = payload.get("robot_id")
        action_type = payload.get("action_type")
        if (
            not isinstance(action_id, str)
            or not action_id.isdigit()
            or len(action_id) > 20
            or action_type != "SIMULATED_RECONNECT"
            or robot_id not in self.robot_ids
        ):
            return 400, {"accepted": False, "message": "Action is not allowlisted."}
        if run_id != self.run_id:
            return 409, {"accepted": False, "message": "Action run does not match."}
        if self.scenario != "disconnected" or robot_id != self.fault_robot_id:
            return 409, {
                "accepted": False,
                "message": "Reconnect is unavailable for this robot and scenario.",
            }

        with self._lock:
            previous = self.applied_actions.get(action_id)
            if previous is not None:
                if previous != (run_id, robot_id, action_type):
                    return 409, {
                        "accepted": False,
                        "message": "Action ID was already used for another request.",
                    }
                status_text = "ALREADY_APPLIED"
            else:
                self.reconnected_robots.add(robot_id)
                self.applied_actions[action_id] = (run_id, robot_id, action_type)
                status_text = "APPLIED"
        return 200, {
            "accepted": True,
            "action_id": action_id,
            "run_id": run_id,
            "robot_id": robot_id,
            "status": status_text,
        }