"""Publish deterministic robot state and mirror robot poses into Gazebo."""

import math
import os
import uuid

import rclpy
from fleet_interfaces.msg import RobotTelemetry
from rclpy.node import Node
from ros_gz_interfaces.msg import Entity
from ros_gz_interfaces.srv import SetEntityPose

from .action_api import SimulatorActionServer
from .action_state import SimulatedReconnectState
from .scenario_state import (
    ROBOT_IDS,
    SCENARIOS,
    build_robot_state as generate_robot_state,
    initial_battery_levels,
    route_position,
)

class FleetSimulator(Node):
    """Generate repeatable fleet telemetry and kinematic model positions."""

    def __init__(self) -> None:
        super().__init__("fleet_simulator")

        self.declare_parameter("scenario", "normal")
        self.declare_parameter("seed", 7)
        self.declare_parameter("fault_robot_id", "robot_02")
        self.declare_parameter("run_id", "")
        self.declare_parameter("publish_rate_hz", 1.0)

        self.scenario = str(self.get_parameter("scenario").value)
        self.seed = int(self.get_parameter("seed").value)
        self.fault_robot_id = str(self.get_parameter("fault_robot_id").value)
        configured_run_id = str(self.get_parameter("run_id").value)
        self.run_id = configured_run_id or uuid.uuid4().hex
        self.publish_rate_hz = float(self.get_parameter("publish_rate_hz").value)

        if self.scenario not in SCENARIOS:
            raise ValueError(
                f"Unknown scenario {self.scenario!r}; choose one of "
                f"{', '.join(sorted(SCENARIOS))}."
            )
        if self.fault_robot_id not in ROBOT_IDS:
            raise ValueError(
                f"Unknown fault robot {self.fault_robot_id!r}; "
                f"choose one of {', '.join(ROBOT_IDS)}."
            )
        if self.publish_rate_hz <= 0.0:
            raise ValueError("publish_rate_hz must be greater than zero.")

        self.publisher = self.create_publisher(
            RobotTelemetry, "/fleet/telemetry", 10
        )
        self.pose_client = self.create_client(
            SetEntityPose, "/world/warehouse/set_pose"
        )
        self.pending_pose_updates = {}
        self.action_state = SimulatedReconnectState(
            self.run_id, self.scenario, self.fault_robot_id, ROBOT_IDS
        )
        self.logged_service_wait = False
        self.sequence = 0
        self.tick = 0

        self.initial_battery = initial_battery_levels(self.seed)
        self.initial_positions = {
            robot_id: route_position(index, 0)
            for index, robot_id in enumerate(ROBOT_IDS)
        }

        self.timer = self.create_timer(
            1.0 / self.publish_rate_hz, self.publish_fleet_state
        )
        action_port = int(os.environ.get("FLEET_SIMULATOR_ACTION_PORT", "8765"))
        self.action_server = SimulatorActionServer(
            "0.0.0.0", action_port, self.handle_simulated_action
        )
        self.action_server.start()
        self.get_logger().info(
            "Fleet simulator ready: "
            f"scenario={self.scenario}, seed={self.seed}, run_id={self.run_id}, "
            f"fault_robot_id={self.fault_robot_id}, robots={len(ROBOT_IDS)}, "
            f"rate_hz={self.publish_rate_hz}"
        )

    def publish_fleet_state(self) -> None:
        """Publish one typed telemetry sample for each simulated robot."""
        stamp = self.get_clock().now().to_msg()

        for index, robot_id in enumerate(ROBOT_IDS):
            state = self.build_robot_state(index, robot_id)
            message = RobotTelemetry()
            message.header.stamp = stamp
            message.header.frame_id = "warehouse"
            message.robot_id = robot_id
            message.sequence = self.sequence
            message.run_id = self.run_id
            message.scenario = self.scenario
            message.seed = self.seed
            message.pose.x = state["x"]
            message.pose.y = state["y"]
            message.pose.theta = state["yaw"]
            message.battery_percentage = state["battery_percentage"]
            message.mission_state = state["mission_state"]
            message.connected = state["connected"]
            message.fault_codes = state["fault_codes"]
            message.sensor_range_m = state["sensor_range_m"]
            self.publisher.publish(message)
            self.update_gazebo_pose(robot_id, state)

            self.sequence += 1

        if self.tick % 10 == 0:
            self.get_logger().info(
                f"tick={self.tick}, scenario={self.scenario}, "
                f"telemetry_topic=/fleet/telemetry"
            )
        self.tick += 1

    def build_robot_state(self, index: int, robot_id: str) -> dict:
        """Return a deterministic state snapshot for one robot."""
        return generate_robot_state(
            scenario=self.scenario,
            fault_robot_id=self.fault_robot_id,
            robot_id=robot_id,
            index=index,
            tick=self.tick,
            initial_battery=self.initial_battery[robot_id],
            initial_position=self.initial_positions[robot_id],
            reconnected=self.action_state.is_reconnected(robot_id),
        )

    def handle_simulated_action(self, payload: dict) -> tuple[int, dict]:
        """Apply the validated simulated action policy."""
        return self.action_state.apply(payload)

    def stop_action_server(self) -> None:
        self.action_server.close()


    def update_gazebo_pose(self, robot_id: str, state: dict) -> None:
        """Set the simple Gazebo model pose through the ros_gz service bridge."""
        previous = self.pending_pose_updates.get(robot_id)
        if previous is not None:
            if not previous.done():
                return
            try:
                result = previous.result()
                if not result.success:
                    self.get_logger().warning(
                        f"Gazebo did not update model pose for {robot_id}."
                    )
            except Exception as error:  # noqa: BLE001
                self.get_logger().warning(
                    f"Pose update failed for {robot_id}: {error}"
                )
            self.pending_pose_updates.pop(robot_id, None)

        if not self.pose_client.service_is_ready():
            if not self.logged_service_wait:
                self.get_logger().info(
                    "Waiting for Gazebo pose service at "
                    "/world/warehouse/set_pose."
                )
                self.logged_service_wait = True
            return

        request = SetEntityPose.Request()
        request.entity.name = robot_id
        request.entity.type = Entity.MODEL
        request.pose.position.x = float(state["x"])
        request.pose.position.y = float(state["y"])
        request.pose.position.z = 0.12
        request.pose.orientation.z = math.sin(float(state["yaw"]) / 2.0)
        request.pose.orientation.w = math.cos(float(state["yaw"]) / 2.0)
        self.pending_pose_updates[robot_id] = self.pose_client.call_async(request)


def main(args=None) -> None:
    rclpy.init(args=args)
    node = FleetSimulator()
    try:
        rclpy.spin(node)
    except KeyboardInterrupt:
        pass
    finally:
        node.stop_action_server()
        node.destroy_node()
        rclpy.shutdown()


if __name__ == "__main__":
    main()
