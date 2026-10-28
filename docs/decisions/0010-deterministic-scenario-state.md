# ADR 0010: Pure deterministic simulator scenario state

- **Status:** Accepted and implemented
- **Decision date:** 2026-10-28

## Context

Fault scenarios are central to the portfolio acceptance criteria. Testing the ROS node directly would require ROS 2 and Gazebo in the unit-test environment, making quick feedback and CI needlessly expensive.

## Decision

Keep seeded fleet and fault-state generation in a dependency-free Python module. The ROS node delegates to this module to create each robot's state. Unit tests exercise all supported normal and fault scenarios, verify deterministic output for a fixed seed and tick, and verify that a fault affects only the selected robot.

## Consequences

- Core scenario tests run without ROS 2, Gazebo, or a language model.
- ROS message publishing and Gazebo pose updates remain in the simulator runtime.
- A new simulator run ID and wall-clock timestamps can differ even when scenario state is reproducible.
- These unit tests validate state generation; they do not replace a live runtime demonstration of every scenario.