# MVP release readiness

**Review date:** 2026-10-28
**Status:** MVP implementation is ready for local demonstration. Public GitHub release is pending repository creation, final file review, and explicit push approval.

## Acceptance review

| # | Acceptance criterion | Status and evidence |
|---|---|---|
| 1 | Documented local setup without paid services | Verified locally. README quick start and component guides use Docker Compose; no paid service is required. |
| 2 | Reproducible run with at least three robots | Verified locally. The latest run published telemetry for robot_01, robot_02, and robot_03. |
| 3 | Five reproducible fault scenarios | Automated state-generation tests cover all five faults and normal operation with seed 7. A live disconnected scenario was also verified. The other four fault scenarios have not each been demonstrated through the running ROS/Gazebo stack in this review. |
| 4 | Deterministic detection and duplicate suppression | Covered by unit and API integration tests for all rules, repeated samples, and incident lifecycle. |
| 5 | Evidence-backed investigation | Covered by API tests for deterministic reports, persisted retrieval, model fallback, fixed hypothesis selection, and rejection of evidence IDs outside the supplied packet. |
| 6 | Explicit approval before recovery | Covered by API tests. A request remains pending without dispatch; only explicit approval dispatches the allowlisted simulated reconnect. |
| 7 | Audit incident, recommendation, decision, and outcome | Covered by API tests. The request event links the report ID, recommendation, and evidence IDs; subsequent events record the decision and simulator outcome. |
| 8 | Dashboard fleet and incident view | Verified locally. Dashboard returned HTTP 200 and the user previously reviewed the interface. The recovery history remains visible for resolved incidents. |
| 9 | Automated checks | Verified locally: 39 tests passed. One Starlette/AnyIO deprecation warning was emitted by the test client dependency. |
| 10 | Architecture, setup, safety, and limitations documented | Documented in README and the architecture, testing, telemetry, investigation, dashboard, and decision records. |

## Latest runtime smoke check

- Compose configuration validated.
- ROS workspace build completed for both packages.
- Backend health and SQLite health returned ok.
- Dashboard returned HTTP 200.
- The simulator ran the disconnected scenario with seed 7 and published samples for all three robots.
- Run ID: c84839b0fe284796a003f08a148b72de.
- The target robot reported disconnected in the new run. No recovery request was created or approved during this smoke check.

## Remaining release work

- The repository has no commits and no configured Git remote. GitHub Actions is configured but has not run on GitHub.
- The project license is MIT. ROS package metadata uses the configured GitHub noreply identity.
- All five injected scenarios are unit-tested, but only the disconnected scenario has been verified in a live ROS/Gazebo run during this review.
- Performance has not been benchmarked; do not make fleet-size or performance claims.
- Python dependency pins cover direct project requirements; transitive dependencies are not frozen in a lock file.

A local credential-pattern scan found no common GitHub/cloud/API token or private-key patterns and no environment, database, or log files in the repository tree. This scan does not replace review of the exact files and history before public publication.
