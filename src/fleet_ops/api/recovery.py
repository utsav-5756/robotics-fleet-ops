"""Explicitly approved, allowlisted simulation-only recovery workflow."""

import json
import os
import sqlite3
import urllib.error
import urllib.request
from typing import Any

from fleet_ops.api.database import connect, utc_now


ACTION_TYPE = "SIMULATED_RECONNECT"
SIMULATOR_ACTION_URL = os.environ.get(
    "FLEET_SIMULATOR_ACTION_URL",
    "http://simulator:8765/v1/actions/reconnect",
)


class RecoveryNotFound(Exception):
    """Raised when an incident or recovery request does not exist."""


class RecoveryConflict(Exception):
    """Raised when the requested recovery state transition is not allowed."""


def _append_event(
    connection: sqlite3.Connection,
    request_id: int,
    event_type: str,
    operator_label: str | None,
    details: dict[str, Any],
) -> None:
    connection.execute(
        """
        INSERT INTO recovery_audit_events (
            request_id, event_type, occurred_at_utc, operator_label, details_json
        ) VALUES (?, ?, ?, ?, ?)
        """,
        (
            request_id,
            event_type,
            utc_now(),
            operator_label,
            json.dumps(details, separators=(",", ":"), sort_keys=True),
        ),
    )


def _request_detail(
    connection: sqlite3.Connection,
    request_id: int,
) -> dict[str, Any] | None:
    row = connection.execute(
        """
        SELECT id, incident_id, run_id, robot_id, action_type, status,
               requested_at_utc, decided_at_utc, operator_label, outcome_json
        FROM recovery_requests WHERE id = ?
        """,
        (request_id,),
    ).fetchone()
    if row is None:
        return None
    request = dict(row)
    request["outcome"] = (
        json.loads(request.pop("outcome_json"))
        if request["outcome_json"] is not None
        else None
    )
    event_rows = connection.execute(
        """
        SELECT id, request_id, event_type, occurred_at_utc,
               operator_label, details_json
        FROM recovery_audit_events
        WHERE request_id = ?
        ORDER BY id
        """,
        (request_id,),
    ).fetchall()
    request["events"] = []
    for event_row in event_rows:
        event = dict(event_row)
        event["details"] = json.loads(event.pop("details_json"))
        request["events"].append(event)
    return request


def get_recovery_request(request_id: int) -> dict[str, Any] | None:
    with connect() as connection:
        return _request_detail(connection, request_id)


def list_recovery_requests(
    incident_id: int,
    limit: int = 20,
) -> list[dict[str, Any]] | None:
    with connect() as connection:
        exists = connection.execute(
            "SELECT 1 FROM incidents WHERE id = ?", (incident_id,)
        ).fetchone()
        if exists is None:
            return None
        rows = connection.execute(
            """
            SELECT id FROM recovery_requests
            WHERE incident_id = ?
            ORDER BY id DESC LIMIT ?
            """,
            (incident_id, limit),
        ).fetchall()
        return [
            detail
            for row in rows
            if (detail := _request_detail(connection, int(row["id"]))) is not None
        ]


def create_recovery_request(incident_id: int) -> dict[str, Any]:
    """Create a pending request without contacting or changing the simulator."""
    with connect() as connection:
        incident = connection.execute(
            """
            SELECT id, run_id, robot_id, incident_type, status, last_telemetry_id
            FROM incidents WHERE id = ?
            """,
            (incident_id,),
        ).fetchone()
        if incident is None:
            raise RecoveryNotFound("Incident not found.")
        if incident["status"] != "ACTIVE":
            raise RecoveryConflict("Recovery is available only for active incidents.")
        if incident["incident_type"] != "ROBOT_DISCONNECTED":
            raise RecoveryConflict(
                "The only available action is for a disconnected-robot incident."
            )

        investigation_row = connection.execute(
            """
            SELECT id, report_json
            FROM investigations
            WHERE incident_id = ?
            ORDER BY id DESC
            LIMIT 1
            """,
            (incident_id,),
        ).fetchone()
        if investigation_row is None:
            raise RecoveryConflict(
                "Generate and review an investigation report before requesting recovery."
            )
        investigation = json.loads(investigation_row["report_json"])
        recommendations = investigation.get("recommended_next_steps", [])
        if not recommendations or not recommendations[0].get("recommendation"):
            raise RecoveryConflict(
                "The latest investigation report has no review recommendation."
            )
        recommendation = recommendations[0]
        latest_evidence_id = f"telemetry:{incident['last_telemetry_id']}"
        if latest_evidence_id not in recommendation.get("evidence_ids", []):
            raise RecoveryConflict(
                "Generate and review an investigation report using the latest incident telemetry before requesting recovery."
            )

        prior = connection.execute(
            """
            SELECT id, status FROM recovery_requests
            WHERE incident_id = ? ORDER BY id DESC LIMIT 1
            """,
            (incident_id,),
        ).fetchone()
        if prior is not None and prior["status"] in {
            "PENDING", "APPROVED", "EXECUTED", "FAILED"
        }:
            detail = _request_detail(connection, int(prior["id"]))
            if detail is not None:
                return detail

        created_at = utc_now()
        cursor = connection.execute(
            """
            INSERT INTO recovery_requests (
                incident_id, run_id, robot_id, action_type, status,
                requested_at_utc
            ) VALUES (?, ?, ?, ?, 'PENDING', ?)
            """,
            (
                incident_id,
                incident["run_id"],
                incident["robot_id"],
                ACTION_TYPE,
                created_at,
            ),
        )
        request_id = int(cursor.lastrowid)
        _append_event(
            connection,
            request_id,
            "REQUESTED",
            None,
            {
                "incident_id": incident_id,
                "run_id": incident["run_id"],
                "robot_id": incident["robot_id"],
                "action_type": ACTION_TYPE,
                "investigation_id": int(investigation_row["id"]),
                "recommendation": recommendation["recommendation"],
                "recommendation_evidence_ids": recommendation.get(
                    "evidence_ids", []
                ),
                "message": "A request was created; no simulator action was sent.",
            },
        )
        detail = _request_detail(connection, request_id)
        if detail is None:
            raise RuntimeError("New recovery request could not be read.")
        return detail


def _send_simulator_action(request: dict[str, Any]) -> dict[str, Any]:
    payload = {
        "action_id": str(request["id"]),
        "run_id": request["run_id"],
        "robot_id": request["robot_id"],
        "action_type": request["action_type"],
    }
    encoded = json.dumps(payload, separators=(",", ":")).encode("utf-8")
    outbound = urllib.request.Request(
        SIMULATOR_ACTION_URL,
        data=encoded,
        headers={"Content-Type": "application/json"},
        method="POST",
    )
    try:
        with urllib.request.urlopen(outbound, timeout=5) as response:
            result = json.loads(response.read().decode("utf-8"))
    except (
        urllib.error.URLError,
        TimeoutError,
        OSError,
        json.JSONDecodeError,
    ) as error:
        return {
            "confirmed": False,
            "message": (
                "The simulator did not confirm the action. Check simulator state "
                "before requesting any further action."
            ),
            "error_type": type(error).__name__,
        }

    expected = {
        "action_id": payload["action_id"],
        "run_id": payload["run_id"],
        "robot_id": payload["robot_id"],
    }
    if (
        not isinstance(result, dict)
        or result.get("accepted") is not True
        or result.get("status") not in {"APPLIED", "ALREADY_APPLIED"}
        or any(result.get(key) != value for key, value in expected.items())
    ):
        return {
            "confirmed": False,
            "message": "The simulator returned an unconfirmed action result.",
        }
    return {
        "confirmed": True,
        "message": "The simulator accepted the simulated reconnect.",
        "simulator_status": result["status"],
    }


def decide_recovery_request(
    request_id: int,
    decision: str,
    operator_label: str,
) -> dict[str, Any]:
    """Record one explicit decision; only approval dispatches the fixed action."""
    expired = False
    with connect() as connection:
        row = connection.execute(
            """
            SELECT r.id, r.incident_id, r.run_id, r.robot_id, r.action_type,
                   r.status, i.status AS incident_status
            FROM recovery_requests AS r
            JOIN incidents AS i ON i.id = r.incident_id
            WHERE r.id = ?
            """,
            (request_id,),
        ).fetchone()
        if row is None:
            raise RecoveryNotFound("Recovery request not found.")
        if row["status"] != "PENDING":
            raise RecoveryConflict(
                f"This request is already {row['status'].lower()} and cannot be decided again."
            )

        if decision == "approve" and row["incident_status"] != "ACTIVE":
            connection.execute(
                """
                UPDATE recovery_requests
                SET status = 'EXPIRED', decided_at_utc = ?, operator_label = ?
                WHERE id = ? AND status = 'PENDING'
                """,
                (utc_now(), operator_label, request_id),
            )
            _append_event(
                connection,
                request_id,
                "EXPIRED",
                operator_label,
                {"message": "The incident was no longer active at approval time."},
            )
            expired = True
        else:
            next_status = "APPROVED" if decision == "approve" else "REJECTED"
            cursor = connection.execute(
                """
                UPDATE recovery_requests
                SET status = ?, decided_at_utc = ?, operator_label = ?
                WHERE id = ? AND status = 'PENDING'
                """,
                (next_status, utc_now(), operator_label, request_id),
            )
            if cursor.rowcount != 1:
                raise RecoveryConflict("This request has already been decided.")
            _append_event(
                connection,
                request_id,
                "APPROVED" if decision == "approve" else "REJECTED",
                operator_label,
                {
                    "action_type": row["action_type"],
                    "run_id": row["run_id"],
                    "robot_id": row["robot_id"],
                },
            )
            request = _request_detail(connection, request_id)

    if expired:
        raise RecoveryConflict("The incident was no longer active; the request expired.")
    if decision == "reject":
        if request is None:
            raise RuntimeError("Recovery request could not be read after rejection.")
        return request

    outcome = _send_simulator_action(request)
    final_status = "EXECUTED" if outcome["confirmed"] else "FAILED"
    event_type = "EXECUTION_CONFIRMED" if outcome["confirmed"] else "EXECUTION_UNCONFIRMED"
    with connect() as connection:
        connection.execute(
            """
            UPDATE recovery_requests
            SET status = ?, outcome_json = ?
            WHERE id = ? AND status = 'APPROVED'
            """,
            (
                final_status,
                json.dumps(outcome, separators=(",", ":"), sort_keys=True),
                request_id,
            ),
        )
        _append_event(
            connection,
            request_id,
            event_type,
            operator_label,
            outcome,
        )
        result = _request_detail(connection, request_id)
    if result is None:
        raise RuntimeError("Recovery request disappeared after execution.")
    return result