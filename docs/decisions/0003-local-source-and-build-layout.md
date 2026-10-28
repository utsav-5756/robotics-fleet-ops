# ADR 0003: Local source and build layout

- **Status:** Accepted
- **Date:** 2026-10-28

## Context

The project is developed from Windows while ROS 2, Gazebo, and Linux builds run in Docker. Linux containers can access Windows-hosted source through bind mounts, but file I/O may be slower than when source is stored in the WSL Linux filesystem.

## Decision

Keep the repository in the agreed Windows project directory for the current Codex workflow. Run ROS 2, Gazebo, and build processes inside Docker. Store generated build output and SQLite runtime data in Docker-managed volumes. Do not install a separate WSL development distribution for the initial workflow.

## Consequences

- The agreed workspace layout and Windows editing flow remain intact.
- Build outputs and databases stay out of Git and avoid unnecessary Windows-host filesystem traffic.
- Measure actual build performance; revisit source location only if results justify a change.
