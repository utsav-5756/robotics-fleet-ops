# ADR 0001: Technology direction

- **Status:** Accepted
- **Date:** 2026-10-27

## Context

The project should be a reproducible, locally runnable robotics portfolio project on a Windows computer with modest CPU and integrated graphics. It should demonstrate fleet telemetry, deterministic fault handling, an evidence-based investigation agent, and operator-controlled recovery without paid services.

## Decision

Use Docker Desktop with its WSL 2 Linux engine, ROS 2 Jazzy, Gazebo Harmonic, Python and rclpy, FastAPI, SQLite, Streamlit, Docker Compose, pytest, and GitHub Actions. Keep the model interface replaceable; a small local model is optional and must not be required for core workflows.

## Consequences

- Start with headless simulation and a three-robot fleet; measure before increasing scale.
- Keep detection and core verification independent of a language model.
- Local setup and demonstration must not require paid APIs, cloud services, or subscriptions.
- The ROS/Gazebo workload and hardware performance still need to be validated in the implementation environment.
