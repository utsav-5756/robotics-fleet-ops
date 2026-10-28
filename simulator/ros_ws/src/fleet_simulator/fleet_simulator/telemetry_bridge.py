"""Forward ROS fleet telemetry to the FastAPI ingestion endpoint."""

import json
import os
import queue
import threading
import urllib.error
import urllib.request

import rclpy
from fleet_interfaces.msg import RobotTelemetry
from rclpy.node import Node


class TelemetryHttpBridge(Node):
    """Queue telemetry outside the ROS callback and retry transient failures."""

    def __init__(self) -> None:
        super().__init__("telemetry_http_bridge")
        self.endpoint = os.environ.get(
            "FLEET_BACKEND_URL", "http://backend:8000/api/v1/telemetry"
        )
        self.pending: queue.Queue[dict] = queue.Queue(maxsize=1000)
        self.stopping = threading.Event()
        self.subscription = self.create_subscription(
            RobotTelemetry, "/fleet/telemetry", self.on_telemetry, 100
        )
        self.worker = threading.Thread(
            target=self.send_pending, name="telemetry-http-worker", daemon=True
        )
        self.worker.start()
        self.get_logger().info(
            f"Forwarding /fleet/telemetry to {self.endpoint}"
        )

    def on_telemetry(self, message: RobotTelemetry) -> None:
        """Normalize the ROS message and enqueue without blocking the executor."""
        payload = {
            "run_id": message.run_id,
            "robot_id": message.robot_id,
            "sequence": message.sequence,
            "scenario": message.scenario,
            "seed": message.seed,
            "simulation_time_ns": (
                message.header.stamp.sec * 1_000_000_000
                + message.header.stamp.nanosec
            ),
            "frame_id": message.header.frame_id,
            "x_m": message.pose.x,
            "y_m": message.pose.y,
            "heading_rad": message.pose.theta,
            "battery_percentage": message.battery_percentage,
            "mission_state": message.mission_state,
            "connected": message.connected,
            "fault_codes": list(message.fault_codes),
            "sensor_range_m": message.sensor_range_m,
        }
        try:
            self.pending.put_nowait(payload)
        except queue.Full:
            self.get_logger().error(
                "Telemetry HTTP queue is full; newest sample was dropped."
            )

    def send_pending(self) -> None:
        """Send queued payloads and retry transient backend failures."""
        while not self.stopping.is_set():
            try:
                payload = self.pending.get(timeout=0.25)
            except queue.Empty:
                continue

            backoff_seconds = 0.5
            while not self.stopping.is_set():
                request = urllib.request.Request(
                    self.endpoint,
                    data=json.dumps(payload, separators=(",", ":")).encode("utf-8"),
                    headers={"Content-Type": "application/json"},
                    method="POST",
                )
                try:
                    with urllib.request.urlopen(request, timeout=3.0) as result:
                        if result.status >= 400:
                            raise urllib.error.HTTPError(
                                self.endpoint,
                                result.status,
                                "Backend rejected telemetry.",
                                result.headers,
                                None,
                            )
                    break
                except urllib.error.HTTPError as error:
                    if 400 <= error.code < 500:
                        self.get_logger().error(
                            f"Backend rejected telemetry with HTTP {error.code}; "
                            "dropping this message."
                        )
                        break
                    self.get_logger().warning(
                        f"Telemetry backend returned HTTP {error.code}; "
                        f"retrying in {backoff_seconds:.1f}s."
                    )
                except (urllib.error.URLError, TimeoutError, OSError) as error:
                    self.get_logger().warning(
                        f"Telemetry backend unavailable ({error}); "
                        f"retrying in {backoff_seconds:.1f}s."
                    )
                self.stopping.wait(backoff_seconds)
                backoff_seconds = min(backoff_seconds * 2.0, 5.0)
            self.pending.task_done()

    def destroy_node(self) -> None:
        """Stop the HTTP worker before releasing ROS resources."""
        self.stopping.set()
        self.worker.join(timeout=4.0)
        super().destroy_node()


def main(args=None) -> None:
    rclpy.init(args=args)
    node = TelemetryHttpBridge()
    try:
        rclpy.spin(node)
    except KeyboardInterrupt:
        pass
    finally:
        node.destroy_node()
        rclpy.shutdown()


if __name__ == "__main__":
    main()
