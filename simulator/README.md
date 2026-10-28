# Fleet simulator

This service launches a server-only Gazebo Harmonic warehouse world and a ROS 2 Jazzy fleet simulator. Three kinematic robot models follow deterministic aisle paths and publish typed telemetry.

The robot models are simple visual bodies moved along deterministic aisle paths. This version does not model wheel dynamics, navigation, or collision avoidance.

## Run the simulator and telemetry backend

From the repository root in PowerShell:

    docker compose -f simulator/compose.yaml up --build -d

The first build downloads the official ROS 2 Jazzy base image and installs the Gazebo ROS integration packages. Compose also starts the FastAPI telemetry backend. The simulator prints its scenario, seed, run ID, and periodic progress.

Check backend health and stored telemetry:

    Invoke-RestMethod http://localhost:8000/healthz
    Invoke-RestMethod 'http://localhost:8000/api/v1/telemetry?limit=10'

Open the API reference at `http://localhost:8000/docs`.

Stop both services with:

    docker compose -f simulator/compose.yaml down

The telemetry database is held in a Docker-managed volume and remains after this command.

## Inspect ROS telemetry directly

Open a second PowerShell window:

    docker compose -f simulator/compose.yaml exec simulator bash

Then, inside the container:

    source /opt/ros/jazzy/setup.bash
    source /workspace/ros_ws/install/setup.bash
    ros2 topic echo /fleet/telemetry

The topic uses the `fleet_interfaces/RobotTelemetry` ROS message. It includes the robot identifier, sequence, run ID, scenario, seed, simulation timestamp, position in meters, heading in radians, battery percentage from 0 to 100, mission state, supervisor-observed connectivity, fault codes, and a synthetic range reading in meters.

A telemetry bridge subscribes to the ROS topic and sends normalized samples to the backend over HTTP. ROS communication remains inside the simulator container.

## Select a reproducible fault scenario

Set the scenario in PowerShell and recreate the Compose services:

    $env:FLEET_SCENARIO = "low_battery"
    $env:FLEET_SEED = "7"
    $env:FAULT_ROBOT_ID = "robot_02"
    docker compose -f simulator/compose.yaml up --build -d --force-recreate

Available scenarios are normal, low_battery, blocked_route, disconnected, stalled_mission, and abnormal_sensor. For the same scenario and seed, telemetry values are repeatable; each simulator process gets a distinct run ID so historical data remains separate.

To return to the default run:

    $env:FLEET_SCENARIO = "normal"
    docker compose -f simulator/compose.yaml up -d --force-recreate

## Operator-approved simulated reconnect

For an active disconnected-robot incident, the backend can send one fixed SIMULATED_RECONNECT action to the simulator after an explicit operator approval. The simulator validates the current run and configured fault-target robot, changes only its in-memory connectivity state, and reports the result in later telemetry.

The simulator's action endpoint listens on port 8765 inside the Docker Compose network. Compose does not publish this port to Windows. Do not expose it as a host port. The endpoint is not connected to physical robot controls.
## Volumes and files

The simulator source is mounted read-only into the container. Colcon build, install, and log outputs use Docker-managed volumes and are excluded from the Git repository. The backend database uses its own named volume.

The ROS package manifest currently has placeholder maintainer and license metadata. Resolve both before publishing the repository.
