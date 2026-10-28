"""Launch a server-only Gazebo world, ROS bridges, and fleet nodes."""

import os

from ament_index_python.packages import get_package_share_directory
from launch import LaunchDescription
from launch.actions import DeclareLaunchArgument, ExecuteProcess
from launch.substitutions import LaunchConfiguration, PathJoinSubstitution
from launch_ros.actions import Node
from launch_ros.parameter_descriptions import ParameterValue


def generate_launch_description():
    package_share = get_package_share_directory("fleet_simulator")
    world_file = PathJoinSubstitution(
        [package_share, "worlds", "warehouse.sdf"]
    )

    scenario_default = os.environ.get("FLEET_SCENARIO", "normal")
    seed_default = os.environ.get("FLEET_SEED", "7")
    robot_default = os.environ.get("FAULT_ROBOT_ID", "robot_02")
    run_id_default = os.environ.get("FLEET_RUN_ID", "")
    rate_default = os.environ.get("FLEET_PUBLISH_RATE_HZ", "1.0")

    return LaunchDescription(
        [
            DeclareLaunchArgument("scenario", default_value=scenario_default),
            DeclareLaunchArgument("seed", default_value=seed_default),
            DeclareLaunchArgument("run_id", default_value=run_id_default),
            DeclareLaunchArgument(
                "fault_robot_id", default_value=robot_default
            ),
            DeclareLaunchArgument(
                "publish_rate_hz", default_value=rate_default
            ),
            ExecuteProcess(
                cmd=["gz", "sim", "-s", "-r", world_file],
                output="screen",
            ),
            Node(
                package="ros_gz_bridge",
                executable="parameter_bridge",
                name="clock_bridge",
                arguments=["/clock@rosgraph_msgs/msg/Clock[gz.msgs.Clock"],
                output="screen",
            ),
            Node(
                package="ros_gz_bridge",
                executable="parameter_bridge",
                name="pose_bridge",
                arguments=[
                    "/world/warehouse/set_pose@ros_gz_interfaces/srv/SetEntityPose"
                ],
                output="screen",
            ),
            Node(
                package="fleet_simulator",
                executable="fleet_telemetry_bridge",
                name="telemetry_http_bridge",
                output="screen",
            ),
            Node(
                package="fleet_simulator",
                executable="fleet_simulator",
                name="fleet_simulator",
                parameters=[
                    {
                        "scenario": LaunchConfiguration("scenario"),
                        "seed": ParameterValue(
                            LaunchConfiguration("seed"), value_type=int
                        ),
                        "fault_robot_id": LaunchConfiguration("fault_robot_id"),
                        "run_id": LaunchConfiguration("run_id"),
                        "publish_rate_hz": ParameterValue(
                            LaunchConfiguration("publish_rate_hz"),
                            value_type=float,
                        ),
                        "use_sim_time": True,
                    }
                ],
                output="screen",
            ),
        ]
    )
