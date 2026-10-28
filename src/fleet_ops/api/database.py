"""SQLite persistence for telemetry and deterministic incidents."""

import json
import os
import sqlite3
from datetime import datetime, timezone
from pathlib import Path
from typing import Any

from fleet_ops.api.detector import detect_incidents
from fleet_ops.api.schemas import TelemetryIn


DEFAULT_DATABASE_PATH = "/data/fleet.sqlite3"


def database_path() -> str:
    """Return the configured persistent SQLite file path."""
    return os.environ.get("FLEET_DATABASE_PATH", DEFAULT_DATABASE_PATH)


def connect(path: str | None = None) -> sqlite3.Connection:
    """Open a configured SQLite connection."""
    connection = sqlite3.connect(path or database_path(), timeout=5.0)
    connection.row_factory = sqlite3.Row
    connection.execute("PRAGMA foreign_keys = ON")
    return connection


def utc_now() -> str:
    """Return a timezone-aware UTC timestamp."""
    return datetime.now(timezone.utc).isoformat(timespec="milliseconds")


def initialize_database(path: str | None = None) -> None:
    """Create or extend the local schema without overwriting records."""
    target = path or database_path()
    Path(target).parent.mkdir(parents=True, exist_ok=True)
    with connect(target) as connection:
        connection.execute("PRAGMA journal_mode = WAL")
        connection.execute(
            """
            CREATE TABLE IF NOT EXISTS telemetry (
                id INTEGER PRIMARY KEY AUTOINCREMENT,
                run_id TEXT NOT NULL,
                robot_id TEXT NOT NULL,
                sequence INTEGER NOT NULL,
                scenario TEXT NOT NULL,
                seed INTEGER NOT NULL,
                simulation_time_ns INTEGER NOT NULL,
                frame_id TEXT NOT NULL,
                x_m REAL NOT NULL,
                y_m REAL NOT NULL,
                heading_rad REAL NOT NULL,
                battery_percentage REAL NOT NULL,
                mission_state TEXT NOT NULL,
                connected INTEGER NOT NULL CHECK (connected IN (0, 1)),
                fault_codes_json TEXT NOT NULL,
                sensor_range_m REAL NOT NULL,
                received_at_utc TEXT NOT NULL,
                UNIQUE (run_id, robot_id, sequence)
            )
            """
        )
        connection.execute(
            """
            CREATE TABLE IF NOT EXISTS incidents (
                id INTEGER PRIMARY KEY AUTOINCREMENT,
                run_id TEXT NOT NULL,
                robot_id TEXT NOT NULL,
                incident_type TEXT NOT NULL,
                severity TEXT NOT NULL,
                status TEXT NOT NULL CHECK (status IN ('ACTIVE', 'RESOLVED')),
                summary TEXT NOT NULL,
                first_seen_utc TEXT NOT NULL,
                last_seen_utc TEXT NOT NULL,
                resolved_at_utc TEXT,
                observation_count INTEGER NOT NULL CHECK (observation_count > 0),
                first_telemetry_id INTEGER NOT NULL REFERENCES telemetry(id),
                last_telemetry_id INTEGER NOT NULL REFERENCES telemetry(id),
                resolved_by_telemetry_id INTEGER REFERENCES telemetry(id),
                first_evidence_json TEXT NOT NULL,
                latest_evidence_json TEXT NOT NULL
            )
            """
        )
        connection.execute(
            """
            CREATE UNIQUE INDEX IF NOT EXISTS uq_active_incident
            ON incidents (run_id, robot_id, incident_type)
            WHERE status = 'ACTIVE'
            """
        )
        connection.execute(
            """
            CREATE INDEX IF NOT EXISTS idx_incidents_run_status
            ON incidents (run_id, status, id DESC)
            """
        )
        connection.execute(
            """
            CREATE TABLE IF NOT EXISTS investigations (
                id INTEGER PRIMARY KEY AUTOINCREMENT,
                incident_id INTEGER NOT NULL REFERENCES incidents(id),
                created_at_utc TEXT NOT NULL,
                provider TEXT NOT NULL,
                provider_status TEXT NOT NULL,
                model TEXT,
                report_json TEXT NOT NULL
            )
            """
        )
        connection.execute(
            """
            CREATE INDEX IF NOT EXISTS idx_investigations_incident
            ON investigations (incident_id, id DESC)
            """
        )
        connection.execute(
            """
            CREATE TABLE IF NOT EXISTS recovery_requests (
                id INTEGER PRIMARY KEY AUTOINCREMENT,
                incident_id INTEGER NOT NULL REFERENCES incidents(id),
                run_id TEXT NOT NULL,
                robot_id TEXT NOT NULL,
                action_type TEXT NOT NULL CHECK (
                    action_type = 'SIMULATED_RECONNECT'
                ),
                status TEXT NOT NULL CHECK (
                    status IN (
                        'PENDING', 'APPROVED', 'REJECTED', 'EXECUTED',
                        'FAILED', 'EXPIRED'
                    )
                ),
                requested_at_utc TEXT NOT NULL,
                decided_at_utc TEXT,
                operator_label TEXT,
                outcome_json TEXT
            )
            """
        )
        connection.execute(
            """
            CREATE INDEX IF NOT EXISTS idx_recovery_incident
            ON recovery_requests (incident_id, id DESC)
            """
        )
        connection.execute(
            """
            CREATE UNIQUE INDEX IF NOT EXISTS uq_pending_recovery_incident
            ON recovery_requests (incident_id) WHERE status = 'PENDING'
            """
        )
        connection.execute(
            """
            CREATE TABLE IF NOT EXISTS recovery_audit_events (
                id INTEGER PRIMARY KEY AUTOINCREMENT,
                request_id INTEGER NOT NULL REFERENCES recovery_requests(id),
                event_type TEXT NOT NULL,
                occurred_at_utc TEXT NOT NULL,
                operator_label TEXT,
                details_json TEXT NOT NULL
            )
            """
        )
        connection.execute(
            """
            CREATE INDEX IF NOT EXISTS idx_recovery_audit_request
            ON recovery_audit_events (request_id, id)
            """
        )
        connection.execute("PRAGMA user_version = 4")


def update_incidents(
    connection: sqlite3.Connection,
    payload: TelemetryIn,
    telemetry_id: int,
) -> None:
    """Apply one telemetry snapshot to all active rules in the same transaction."""
    now = utc_now()
    detected = {
        incident["incident_type"]: incident for incident in detect_incidents(payload)
    }
    active_rows = connection.execute(
        """
        SELECT id, incident_type FROM incidents
        WHERE run_id = ? AND robot_id = ? AND status = 'ACTIVE'
        """,
        (payload.run_id, payload.robot_id),
    ).fetchall()

    for active in active_rows:
        if active["incident_type"] not in detected:
            connection.execute(
                """
                UPDATE incidents
                SET status = 'RESOLVED', resolved_at_utc = ?,
                    resolved_by_telemetry_id = ?
                WHERE id = ? AND status = 'ACTIVE'
                """,
                (now, telemetry_id, active["id"]),
            )

    for incident_type, incident in detected.items():
        evidence = {
            **incident["evidence"],
            "telemetry_id": telemetry_id,
        }
        encoded_evidence = json.dumps(evidence, separators=(",", ":"), sort_keys=True)
        active = connection.execute(
            """
            SELECT id FROM incidents
            WHERE run_id = ? AND robot_id = ? AND incident_type = ?
              AND status = 'ACTIVE'
            """,
            (payload.run_id, payload.robot_id, incident_type),
        ).fetchone()
        if active is None:
            connection.execute(
                """
                INSERT INTO incidents (
                    run_id, robot_id, incident_type, severity, status, summary,
                    first_seen_utc, last_seen_utc, observation_count,
                    first_telemetry_id, last_telemetry_id,
                    first_evidence_json, latest_evidence_json
                ) VALUES (?, ?, ?, ?, 'ACTIVE', ?, ?, ?, 1, ?, ?, ?, ?)
                """,
                (
                    payload.run_id,
                    payload.robot_id,
                    incident_type,
                    incident["severity"],
                    incident["summary"],
                    now,
                    now,
                    telemetry_id,
                    telemetry_id,
                    encoded_evidence,
                    encoded_evidence,
                ),
            )
        else:
            connection.execute(
                """
                UPDATE incidents
                SET last_seen_utc = ?, observation_count = observation_count + 1,
                    last_telemetry_id = ?, latest_evidence_json = ?
                WHERE id = ? AND status = 'ACTIVE'
                """,
                (now, telemetry_id, encoded_evidence, active["id"]),
            )


def insert_telemetry(payload: TelemetryIn, path: str | None = None) -> tuple[int, bool]:
    """Insert once and evaluate incidents atomically for a new telemetry record."""
    values = payload.model_dump()
    with connect(path) as connection:
        cursor = connection.execute(
            """
            INSERT INTO telemetry (
                run_id, robot_id, sequence, scenario, seed, simulation_time_ns,
                frame_id, x_m, y_m, heading_rad, battery_percentage,
                mission_state, connected, fault_codes_json, sensor_range_m,
                received_at_utc
            ) VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
            ON CONFLICT (run_id, robot_id, sequence) DO NOTHING
            """,
            (
                values["run_id"],
                values["robot_id"],
                values["sequence"],
                values["scenario"],
                values["seed"],
                values["simulation_time_ns"],
                values["frame_id"],
                values["x_m"],
                values["y_m"],
                values["heading_rad"],
                values["battery_percentage"],
                values["mission_state"],
                int(values["connected"]),
                json.dumps(values["fault_codes"], separators=(",", ":")),
                values["sensor_range_m"],
                utc_now(),
            ),
        )
        if cursor.rowcount == 0:
            row = connection.execute(
                """
                SELECT id FROM telemetry
                WHERE run_id = ? AND robot_id = ? AND sequence = ?
                """,
                (values["run_id"], values["robot_id"], values["sequence"]),
            ).fetchone()
            if row is None:
                raise sqlite3.IntegrityError("Duplicate telemetry row disappeared.")
            return int(row["id"]), True

        telemetry_id = int(cursor.lastrowid)
        update_incidents(connection, payload, telemetry_id)
        return telemetry_id, False


def list_telemetry(
    robot_id: str | None = None,
    run_id: str | None = None,
    limit: int = 100,
    path: str | None = None,
) -> list[dict[str, Any]]:
    """Read recent telemetry with optional robot and run filters."""
    clauses = []
    parameters: list[Any] = []
    if robot_id is not None:
        clauses.append("robot_id = ?")
        parameters.append(robot_id)
    if run_id is not None:
        clauses.append("run_id = ?")
        parameters.append(run_id)

    where_sql = f"WHERE {' AND '.join(clauses)}" if clauses else ""
    parameters.append(limit)
    with connect(path) as connection:
        rows = connection.execute(
            f"""
            SELECT id, run_id, robot_id, sequence, scenario, seed,
                   simulation_time_ns, frame_id, x_m, y_m, heading_rad,
                   battery_percentage, mission_state, connected,
                   fault_codes_json, sensor_range_m, received_at_utc
            FROM telemetry
            {where_sql}
            ORDER BY id DESC
            LIMIT ?
            """,
            parameters,
        ).fetchall()

    records = []
    for row in rows:
        record = dict(row)
        record["connected"] = bool(record["connected"])
        record["fault_codes"] = json.loads(record.pop("fault_codes_json"))
        records.append(record)
    return records


def list_incidents(
    status: str | None = None,
    robot_id: str | None = None,
    run_id: str | None = None,
    limit: int = 100,
    path: str | None = None,
) -> list[dict[str, Any]]:
    """Read recent incidents with optional lifecycle and identity filters."""
    clauses = []
    parameters: list[Any] = []
    if status is not None:
        clauses.append("status = ?")
        parameters.append(status)
    if robot_id is not None:
        clauses.append("robot_id = ?")
        parameters.append(robot_id)
    if run_id is not None:
        clauses.append("run_id = ?")
        parameters.append(run_id)

    where_sql = f"WHERE {' AND '.join(clauses)}" if clauses else ""
    parameters.append(limit)
    with connect(path) as connection:
        rows = connection.execute(
            f"""
            SELECT id, run_id, robot_id, incident_type, severity, status,
                   summary, first_seen_utc, last_seen_utc, resolved_at_utc,
                   observation_count, first_telemetry_id, last_telemetry_id,
                   resolved_by_telemetry_id, first_evidence_json,
                   latest_evidence_json
            FROM incidents
            {where_sql}
            ORDER BY id DESC
            LIMIT ?
            """,
            parameters,
        ).fetchall()

    incidents = []
    for row in rows:
        incident = dict(row)
        incident["first_evidence"] = json.loads(incident.pop("first_evidence_json"))
        incident["latest_evidence"] = json.loads(incident.pop("latest_evidence_json"))
        incidents.append(incident)
    return incidents


def database_is_ready(path: str | None = None) -> bool:
    """Return whether SQLite can answer a basic query."""
    try:
        with connect(path) as connection:
            connection.execute("SELECT 1").fetchone()
        return True
    except sqlite3.Error:
        return False


def read_incident_context(incident_id: int, path: str | None = None) -> dict[str, Any] | None:
    """Load an incident and bounded same-run telemetry for investigation."""
    with connect(path) as connection:
        row = connection.execute(
            """
            SELECT id, run_id, robot_id, incident_type, severity, status, summary,
                   first_seen_utc, last_seen_utc, resolved_at_utc,
                   observation_count, first_telemetry_id, last_telemetry_id,
                   resolved_by_telemetry_id, first_evidence_json,
                   latest_evidence_json
            FROM incidents WHERE id = ?
            """,
            (incident_id,),
        ).fetchone()
        if row is None:
            return None
        incident = dict(row)
        incident["first_evidence"] = json.loads(incident.pop("first_evidence_json"))
        incident["latest_evidence"] = json.loads(incident.pop("latest_evidence_json"))
        anchor_id = incident["resolved_by_telemetry_id"] or incident["last_telemetry_id"]
        recent_rows = connection.execute(
            """
            SELECT id, run_id, robot_id, sequence, scenario, seed,
                   simulation_time_ns, battery_percentage, mission_state,
                   connected, fault_codes_json, sensor_range_m, received_at_utc
            FROM telemetry
            WHERE run_id = ? AND robot_id = ? AND id <= ?
            ORDER BY id DESC LIMIT 20
            """,
            (incident["run_id"], incident["robot_id"], anchor_id),
        ).fetchall()
        evidence_ids = {
            incident["first_telemetry_id"],
            incident["last_telemetry_id"],
        }
        if incident["resolved_by_telemetry_id"] is not None:
            evidence_ids.add(incident["resolved_by_telemetry_id"])
        evidence_rows = connection.execute(
            """
            SELECT id, run_id, robot_id, sequence, scenario, seed,
                   simulation_time_ns, battery_percentage, mission_state,
                   connected, fault_codes_json, sensor_range_m, received_at_utc
            FROM telemetry WHERE id IN (?, ?, ?)
            """,
            tuple(
                [
                    incident["first_telemetry_id"],
                    incident["last_telemetry_id"],
                    incident["resolved_by_telemetry_id"] or -1,
                ]
            ),
        ).fetchall()

    by_id = {int(item["id"]): dict(item) for item in recent_rows}
    by_id.update({int(item["id"]): dict(item) for item in evidence_rows})
    telemetry = []
    for record_id in sorted(by_id):
        item = by_id[record_id]
        item["connected"] = bool(item["connected"])
        item["fault_codes"] = json.loads(item.pop("fault_codes_json"))
        telemetry.append(item)
    return {"incident": incident, "telemetry": telemetry}


def save_investigation(
    incident_id: int,
    report: dict[str, Any],
    path: str | None = None,
) -> int:
    """Persist a completed immutable investigation report."""
    with connect(path) as connection:
        cursor = connection.execute(
            """
            INSERT INTO investigations (
                incident_id, created_at_utc, provider, provider_status, model,
                report_json
            ) VALUES (?, ?, ?, ?, ?, ?)
            """,
            (
                incident_id,
                report["created_at_utc"],
                report["provider"],
                report["provider_status"],
                report.get("model"),
                json.dumps(report, separators=(",", ":"), sort_keys=True),
            ),
        )
        return int(cursor.lastrowid)


def get_investigation(
    investigation_id: int,
    path: str | None = None,
) -> dict[str, Any] | None:
    """Read one saved investigation report."""
    with connect(path) as connection:
        row = connection.execute(
            """
            SELECT id, incident_id, report_json
            FROM investigations WHERE id = ?
            """,
            (investigation_id,),
        ).fetchone()
    if row is None:
        return None
    report = json.loads(row["report_json"])
    report["id"] = int(row["id"])
    report["incident_id"] = int(row["incident_id"])
    return report


def list_investigations(
    incident_id: int,
    limit: int = 20,
    path: str | None = None,
) -> list[dict[str, Any]]:
    """Read a bounded report history for one incident."""
    with connect(path) as connection:
        rows = connection.execute(
            """
            SELECT id, incident_id, report_json
            FROM investigations
            WHERE incident_id = ?
            ORDER BY id DESC LIMIT ?
            """,
            (incident_id, limit),
        ).fetchall()
    reports = []
    for row in rows:
        report = json.loads(row["report_json"])
        report["id"] = int(row["id"])
        report["incident_id"] = int(row["incident_id"])
        reports.append(report)
    return reports
