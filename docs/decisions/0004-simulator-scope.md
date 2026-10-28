# ADR 0004: First simulator implementation scope

- **Status:** Accepted for the first implementation slice
- **Date:** 2026-10-28

## Context

The project needs repeatable fleet state and fault scenarios while keeping the simulator light enough to start headless on the available computer. The ROS 2 Jazzy and Gazebo Harmonic pairing is supported by the official ros_gz integration.

## Decision

Run Gazebo Harmonic server-only in the simulator container. Use three simple warehouse robot models whose poses follow deterministic kinematic aisle loops. A ROS 2 Jazzy node publishes a typed RobotTelemetry message on /fleet/telemetry and updates the corresponding Gazebo model poses through the ros_gz SetEntityPose service bridge.

Select one scenario per run: normal, low battery, blocked route, disconnected, stalled mission, or abnormal sensor. A seed controls deterministic initial battery values. Do not add wheel dynamics, navigation, or collision avoidance in this first slice.

## Consequences

- The first run is lightweight and repeatable.
- ROS messages have explicit fields rather than unstructured JSON.
- The robot locations are kinematic state updates, not a physics-based drive model.
- Telemetry persistence and incident detection remain separate later steps.
