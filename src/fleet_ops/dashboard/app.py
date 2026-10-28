"""Local read-only Streamlit console backed by the Fleet Operations API."""

import json
import os
import urllib.error
import urllib.parse
import urllib.request
from collections import defaultdict
from datetime import datetime, timezone
from typing import Any

import streamlit as st


API_BASE_URL = os.environ.get("FLEET_API_URL", "http://backend:8000").rstrip("/")
REQUEST_TIMEOUT_SECONDS = 8


class ApiUnavailable(RuntimeError):
    """Raised when the backend cannot serve a dashboard request."""


def api_request(
    path: str,
    params: dict[str, str | int] | None = None,
    method: str = "GET",
    json_body: dict[str, Any] | None = None,
) -> dict[str, Any]:
    """Call only the configured local Fleet Operations API."""
    query = f"?{urllib.parse.urlencode(params)}" if params else ""
    url = f"{API_BASE_URL}{path}{query}"
    if json_body is not None:
        data = json.dumps(json_body).encode("utf-8")
        headers = {"Content-Type": "application/json"}
    else:
        data = b"" if method == "POST" else None
        headers = {}
    request = urllib.request.Request(
        url, data=data, headers=headers, method=method
    )
    try:
        with urllib.request.urlopen(request, timeout=REQUEST_TIMEOUT_SECONDS) as response:
            return json.loads(response.read().decode("utf-8"))
    except urllib.error.HTTPError as error:
        try:
            detail = json.loads(error.read().decode("utf-8")).get("detail")
        except (OSError, json.JSONDecodeError):
            detail = None
        message = str(detail or "The backend rejected the request.")
        raise ApiUnavailable(message) from error
    except (urllib.error.URLError, TimeoutError, OSError, json.JSONDecodeError) as error:
        raise ApiUnavailable("The backend could not complete the request.") from error


def latest_robot_samples(records: list[dict[str, Any]]) -> list[dict[str, Any]]:
    """Select the newest record for each robot from descending API results."""
    latest = {}
    for record in records:
        latest.setdefault(record["robot_id"], record)
    return list(latest.values())


def build_chart_rows(
    records: list[dict[str, Any]],
    metric: str,
    robot_ids: list[str],
) -> list[dict[str, float]]:
    """Combine robot samples at matching simulation times for a line chart."""
    values_by_time: dict[float, dict[str, float]] = defaultdict(dict)
    for record in records:
        timestamp = record["simulation_time_ns"] / 1_000_000_000
        value = (
            record["battery_percentage"]
            if metric == "Battery (%)"
            else record["sensor_range_m"]
        )
        values_by_time[timestamp][record["robot_id"]] = float(value)

    rows = []
    for timestamp in sorted(values_by_time):
        row: dict[str, float] = {"Simulation time (s)": timestamp}
        for robot_id in robot_ids:
            value = values_by_time[timestamp].get(robot_id)
            if value is not None:
                row[robot_id] = value
        rows.append(row)
    return rows


def render_report(report: dict[str, Any]) -> None:
    """Show measured facts separately from hypotheses and operator suggestions."""
    st.subheader(f"Investigation report #{report['id']}")
    st.caption(
        f"Provider: {report['provider']} · {report['provider_status']} · "
        f"{report.get('model') or 'no model'} · {report['created_at_utc']}"
    )

    st.markdown("#### Measured facts")
    st.dataframe(report["observed_facts"], hide_index=True, width="stretch")

    st.markdown("#### Hypotheses")
    for item in report["hypotheses"]:
        st.write(f"**{item['hypothesis']}** — confidence {item['confidence']:.0%}")
        st.caption(item["rationale"])
        st.caption("Evidence: " + ", ".join(item["evidence_ids"]))

    st.markdown("#### Operator review suggestions")
    for item in report["recommended_next_steps"]:
        st.write(item["recommendation"])
        st.caption("Evidence: " + ", ".join(item["evidence_ids"]))

    with st.expander("Report limitations"):
        for limitation in report["limitations"]:
            st.write(f"- {limitation}")


def render_recovery_controls(
    incident: dict[str, Any],
    investigation_reports: list[dict[str, Any]],
) -> None:
    """Show the allowlisted action and preserve its audit history."""
    st.markdown("### Simulated recovery")
    st.caption(
        "This action changes simulated connectivity only. It cannot control a "
        "physical robot. The operator label is self-reported; this demo has no login."
    )
    if incident["incident_type"] != "ROBOT_DISCONNECTED":
        st.info(
            "Simulated reconnect is available only for disconnected-robot incidents."
        )
        return

    try:
        requests = api_request(
            f"/api/v1/incidents/{incident['id']}/recovery-requests"
        )
    except ApiUnavailable as error:
        st.error(f"Could not load recovery history: {error}")
        return

    latest = requests[0] if requests else None
    if incident["status"] != "ACTIVE":
        st.info("This incident is resolved; no new recovery request can be made.")
    elif not investigation_reports or (
        f"telemetry:{incident['last_telemetry_id']}"
        not in investigation_reports[0]["recommended_next_steps"][0]["evidence_ids"]
    ):
        st.info(
            "Generate and review an investigation report for the latest incident "
            "telemetry before requesting a simulated reconnect. Its recommendation "
            "and evidence will be included in the recovery audit."
        )
    elif latest is None or latest["status"] in {"REJECTED", "EXPIRED"}:
        if st.button(
            "Request simulated reconnect",
            help="Creates a pending request only; it does not change the simulator.",
            key=f"request_recovery_{incident['id']}",
        ):
            try:
                api_request(
                    f"/api/v1/incidents/{incident['id']}/recovery-requests",
                    method="POST",
                )
                st.rerun()
            except ApiUnavailable as error:
                st.error(f"Could not create the request: {error}")
    elif latest["status"] == "PENDING":
        st.warning(
            f"Request #{latest['id']} is pending. No simulated action has been sent."
        )
        operator_label = st.text_input(
            "Operator label (self-reported)",
            value="local operator",
            max_chars=64,
            key=f"operator_label_{latest['id']}",
        )
        confirmed = st.checkbox(
            "I reviewed the incident evidence and approve this simulated reconnect.",
            key=f"approve_confirm_{latest['id']}",
        )
        approve_col, reject_col = st.columns(2)
        with approve_col:
            if st.button(
                "Approve simulated reconnect",
                type="primary",
                disabled=not confirmed or not operator_label.strip(),
                key=f"approve_recovery_{latest['id']}",
            ):
                try:
                    api_request(
                        f"/api/v1/recovery-requests/{latest['id']}/decision",
                        method="POST",
                        json_body={
                            "decision": "approve",
                            "operator_label": operator_label.strip(),
                        },
                    )
                    st.rerun()
                except ApiUnavailable as error:
                    st.error(f"Could not approve the request: {error}")
        with reject_col:
            if st.button(
                "Reject request",
                key=f"reject_recovery_{latest['id']}",
            ):
                try:
                    api_request(
                        f"/api/v1/recovery-requests/{latest['id']}/decision",
                        method="POST",
                        json_body={
                            "decision": "reject",
                            "operator_label": operator_label.strip() or "local operator",
                        },
                    )
                    st.rerun()
                except ApiUnavailable as error:
                    st.error(f"Could not reject the request: {error}")
    elif latest["status"] == "EXECUTED":
        st.success(
            "The simulator confirmed the reconnect. Refresh data to see the next "
            "telemetry sample and incident status."
        )
    elif latest["status"] == "FAILED":
        st.error(
            "The simulator did not confirm the action. Inspect the latest fleet "
            "state; this request cannot be replayed."
        )
    elif latest["status"] == "APPROVED":
        st.info("Approval was recorded; the simulator outcome is being recorded.")
    else:
        st.info(f"Recovery request status: {latest['status']}.")

    if requests:
        st.markdown("#### Recovery request history")
        for recovery in requests:
            st.caption(
                f"Request #{recovery['id']} | {recovery['action_type']} | "
                f"{recovery['status']} | run {recovery['run_id']} | "
                f"{recovery['robot_id']}"
            )
            st.dataframe(
                [
                    {
                        "Event": event["event_type"],
                        "Time (UTC)": event["occurred_at_utc"],
                        "Operator label": event["operator_label"] or "System",
                        "Details": json.dumps(event["details"], sort_keys=True),
                    }
                    for event in recovery["events"]
                ],
                hide_index=True,
                width="stretch",
            )


def main() -> None:
    """Render fleet, telemetry, incident, and investigation views."""
    st.set_page_config(
        page_title="Fleet Operations Center",
        page_icon="🤖",
        layout="wide",
    )
    st.title("Agentic Robotics Fleet Operations Center")
    st.caption(
        "Local simulator operations view. Investigation suggestions are advisory. Recovery actions are simulated and require explicit operator approval."
    )

    with st.sidebar:
        st.header("View filters")
        st.caption(f"Backend: {API_BASE_URL}")
        if st.button("Refresh data", width="stretch"):
            st.rerun()

    try:
        health = api_request("/healthz")
        if health.get("status") != "ok":
            st.error("The backend or telemetry database is unavailable.")
            st.stop()
        recent = api_request("/api/v1/telemetry", {"limit": 500})["items"]
    except (ApiUnavailable, KeyError) as error:
        st.error(f"Dashboard data is unavailable: {error}")
        st.stop()

    if not recent:
        st.info("No telemetry is available yet. Start the simulator to populate this view.")
        return

    run_ids = list(dict.fromkeys(record["run_id"] for record in recent))
    with st.sidebar:
        selected_run = st.selectbox("Simulator run", run_ids)
        robot_options = ["All robots"] + sorted(
            {record["robot_id"] for record in recent if record["run_id"] == selected_run}
        )
        selected_robot = st.selectbox("Robot", robot_options)
        selected_status = st.selectbox(
            "Incident status",
            ["All", "ACTIVE", "RESOLVED"],
        )

    try:
        query = {"run_id": selected_run, "limit": 500}
        run_records = api_request("/api/v1/telemetry", query)["items"]
        incidents = api_request("/api/v1/incidents", query)["items"]
    except (ApiUnavailable, KeyError) as error:
        st.error(f"Could not load the selected run: {error}")
        st.stop()

    if selected_robot != "All robots":
        run_records = [
            record for record in run_records
            if record["robot_id"] == selected_robot
        ]
        incidents = [
            incident for incident in incidents
            if incident["robot_id"] == selected_robot
        ]
    if selected_status != "All":
        incidents = [
            incident for incident in incidents
            if incident["status"] == selected_status
        ]

    latest = latest_robot_samples(run_records)
    active_count = sum(incident["status"] == "ACTIVE" for incident in incidents)
    connected_count = sum(record["connected"] for record in latest)
    metric_columns = st.columns(4)
    metric_columns[0].metric("Robots in view", len(latest))
    metric_columns[1].metric("Connected", connected_count)
    metric_columns[2].metric("Active incidents", active_count)
    metric_columns[3].metric("Telemetry samples", len(run_records))

    st.markdown("### Fleet status")
    status_rows = [
        {
            "Robot": record["robot_id"],
            "Connected": "Yes" if record["connected"] else "No",
            "Battery (%)": round(record["battery_percentage"], 1),
            "Mission": record["mission_state"],
            "Fault codes": ", ".join(record["fault_codes"]) or "None",
            "Scenario": record["scenario"],
            "Sequence": record["sequence"],
        }
        for record in latest
    ]
    st.dataframe(status_rows, hide_index=True, width="stretch")

    chart_left, chart_right = st.columns([2, 1])
    with chart_left:
        st.markdown("### Telemetry history")
        metric = st.selectbox(
            "Measure",
            ["Battery (%)", "Sensor range (m)"],
        )
        selected_robot_ids = sorted(
            {record["robot_id"] for record in run_records}
        )
        chart_rows = build_chart_rows(run_records, metric, selected_robot_ids)
        if chart_rows:
            st.line_chart(
                chart_rows,
                x="Simulation time (s)",
                y=selected_robot_ids,
                alt=f"{metric} over simulation time for each robot",
            )
        else:
            st.info("No samples are available for this chart.")

    with chart_right:
        st.markdown("### Incidents")
        if not incidents:
            st.info("No incidents match these filters.")
            selected_incident = None
        else:
            incident_labels = {
                incident["id"]: (
                    f"#{incident['id']} · {incident['robot_id']} · "
                    f"{incident['incident_type']} · {incident['status']}"
                )
                for incident in incidents
            }
            selected_incident_id = st.selectbox(
                "Select incident",
                list(incident_labels),
                format_func=lambda incident_id: incident_labels[incident_id],
            )
            selected_incident = next(
                incident
                for incident in incidents
                if incident["id"] == selected_incident_id
            )
            st.write(selected_incident["summary"])
            st.caption(
                f"Run {selected_incident['run_id']} · "
                f"Severity {selected_incident['severity']} · "
                f"{selected_incident['observation_count']} observations"
            )
            with st.expander("Incident evidence"):
                st.json(selected_incident["latest_evidence"])

    if selected_incident is None:
        return



    st.markdown("### Investigation reports")
    try:
        report_history = api_request(
            f"/api/v1/incidents/{selected_incident['id']}/investigations",
            {"limit": 20},
        )["items"]
    except (ApiUnavailable, KeyError) as error:
        st.error(f"Could not load saved reports: {error}")
        return

    button_col, provider_col = st.columns([1, 3])
    with button_col:
        if st.button(
            "Generate investigation report",
            type="primary",
            help="Creates a persisted evidence-backed report; it does not execute actions.",
        ):
            try:
                with st.spinner("Preparing the evidence-backed report..."):
                    api_request(
                        f"/api/v1/incidents/{selected_incident['id']}/investigations",
                        method="POST",
                    )
                st.rerun()
            except ApiUnavailable as error:
                st.error(f"Could not create the report: {error}")
    with provider_col:
        st.caption(
            "The backend uses its deterministic provider by default. "
            "An optional configured local model may be used."
        )

    if not report_history:
        st.info("No investigation reports have been saved for this incident yet.")
    else:
        selected_report = st.selectbox(
            "Saved report",
            report_history,
            format_func=lambda report: (
                f"Report #{report['id']} · {report['provider_status']} · "
                f"{report['created_at_utc']}"
            ),
        )
        render_report(selected_report)
        st.caption(
            "Measured telemetry is shown separately from hypotheses. "
            "Recommendations are for operator review only."
        )

    render_recovery_controls(selected_incident, report_history)


if __name__ == "__main__":
    main()
