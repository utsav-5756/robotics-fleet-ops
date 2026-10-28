# Operator dashboard

The Streamlit dashboard provides a local operations view over the Fleet Operations API. It summarizes the selected simulator run, shows each robot's latest state, graphs battery or sensor-range history, and displays incidents with their evidence and investigation reports.

## Run

From the repository root in PowerShell:

    docker compose -f simulator/compose.yaml up --build -d

Open localhost port 8501 in a browser. The dashboard and backend are published only on the local machine.

Use the sidebar to select a simulator run, robot, and incident status. Use Refresh data to reload the view. The chart shows up to 500 recent telemetry records for the selected run.

## Simulated reconnect workflow

The first recovery demonstration is deliberately limited to an active ROBOT_DISCONNECTED incident. The dashboard offers the fixed SIMULATED_RECONNECT action for that case only.

1. Review the incident and its supporting telemetry evidence.
2. Generate and review an investigation report. It separates measured facts from hypotheses and includes a fixed operator review recommendation with evidence references.
3. Select Request simulated reconnect. This records a pending request and does not contact the simulator. The request audit stores the investigation report ID, recommendation, and evidence references.
4. Enter an operator label. It is self-reported because this local demo has no login or identity verification.
5. Check the approval statement, then select Approve simulated reconnect. Only this explicit decision causes the backend to send the fixed action to the simulator. Select Reject request to record rejection without changing simulated state.
6. Review the recovery request history. It shows the incident, report recommendation, decision, and simulator outcome. After a confirmed reconnect, refresh the dashboard to see the next telemetry sample and incident resolution.

The backend accepts a request only for an active disconnection incident and refuses decisions on requests that are no longer pending. The simulator validates the action type, current run, and fault-target robot, and recognizes repeated request IDs. If the simulator does not confirm the action, the dashboard reports the unconfirmed outcome; do not replay that request.

## Safety and limitations

The reconnect changes simulated connectivity only. The action API listens on the Docker Compose network and has no host-published port. This project has no physical-robot connection, motor command, operator authentication, or production authorization system. The action is selected by fixed backend logic; the investigation model cannot approve or choose executable actions.

Investigation reports remain advisory. Their creation is an analysis action and does not trigger recovery.

Stop the services with:

    docker compose -f simulator/compose.yaml down

The Docker-managed database volume, including telemetry and audit records, remains after this command.