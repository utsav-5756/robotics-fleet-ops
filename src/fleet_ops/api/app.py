"""FastAPI endpoints for telemetry, incident, and investigation APIs."""

from contextlib import asynccontextmanager
from typing import Annotated, Literal

from fastapi import FastAPI, HTTPException, Query, Response, status

from fleet_ops.agent.investigation import (
    create_investigation,
    get_incident_investigations,
    get_investigation_report,
)
from fleet_ops.api.database import (
    database_is_ready,
    initialize_database,
    insert_telemetry,
    list_incidents,
    list_telemetry,
)
from fleet_ops.api.recovery import (
    RecoveryConflict,
    RecoveryNotFound,
    create_recovery_request,
    decide_recovery_request,
    list_recovery_requests,
)
from fleet_ops.api.schemas import (
    RecoveryDecisionIn,
    RecoveryRequestRecord,
    IncidentPage,
    IncidentRecord,
    InvestigationPage,
    InvestigationReport,
    TelemetryAccepted,
    TelemetryIn,
    TelemetryPage,
    TelemetryRecord,
)


@asynccontextmanager
async def lifespan(_: FastAPI):
    initialize_database()
    yield


app = FastAPI(
    title="Fleet Operations API",
    version="0.1.0",
    description="Telemetry, deterministic incidents, and evidence-based investigations.",
    lifespan=lifespan,
)


@app.get("/healthz", tags=["health"])
def healthz(response: Response) -> dict[str, str]:
    """Report API and SQLite availability."""
    if not database_is_ready():
        response.status_code = status.HTTP_503_SERVICE_UNAVAILABLE
        return {"status": "unavailable", "database": "unavailable"}
    return {"status": "ok", "database": "ok"}


@app.post(
    "/api/v1/telemetry",
    response_model=TelemetryAccepted,
    status_code=status.HTTP_202_ACCEPTED,
    tags=["telemetry"],
)
def accept_telemetry(payload: TelemetryIn) -> TelemetryAccepted:
    """Validate, persist, and evaluate one telemetry record atomically."""
    record_id, duplicate = insert_telemetry(payload)
    return TelemetryAccepted(duplicate=duplicate, record_id=record_id)


@app.get(
    "/api/v1/telemetry",
    response_model=TelemetryPage,
    tags=["telemetry"],
)
def get_telemetry(
    robot_id: Annotated[str | None, Query(max_length=32)] = None,
    run_id: Annotated[str | None, Query(max_length=128)] = None,
    limit: Annotated[int, Query(ge=1, le=500)] = 100,
) -> TelemetryPage:
    """Return recent telemetry, optionally filtered by robot or run."""
    records = list_telemetry(robot_id=robot_id, run_id=run_id, limit=limit)
    return TelemetryPage(
        items=[TelemetryRecord.model_validate(record) for record in records],
        limit=limit,
        count=len(records),
    )


@app.get(
    "/api/v1/incidents",
    response_model=IncidentPage,
    tags=["incidents"],
)
def get_incidents(
    incident_status: Annotated[
        Literal["ACTIVE", "RESOLVED"] | None,
        Query(alias="status"),
    ] = None,
    robot_id: Annotated[str | None, Query(max_length=32)] = None,
    run_id: Annotated[str | None, Query(max_length=128)] = None,
    limit: Annotated[int, Query(ge=1, le=500)] = 100,
) -> IncidentPage:
    """Return recent incidents, optionally filtered by status, robot, or run."""
    incidents = list_incidents(
        status=incident_status,
        robot_id=robot_id,
        run_id=run_id,
        limit=limit,
    )
    return IncidentPage(
        items=[IncidentRecord.model_validate(incident) for incident in incidents],
        limit=limit,
        count=len(incidents),
    )


@app.post(
    "/api/v1/incidents/{incident_id}/investigations",
    response_model=InvestigationReport,
    status_code=status.HTTP_201_CREATED,
    tags=["investigations"],
)
def investigate(incident_id: int) -> InvestigationReport:
    """Create a report from bounded read-only telemetry evidence."""
    report = create_investigation(incident_id)
    if report is None:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="Incident not found.",
        )
    return report


@app.get(
    "/api/v1/incidents/{incident_id}/investigations",
    response_model=InvestigationPage,
    tags=["investigations"],
)
def get_incident_reports(
    incident_id: int,
    limit: Annotated[int, Query(ge=1, le=100)] = 20,
) -> InvestigationPage:
    """Return recent saved investigations for an incident."""
    reports = get_incident_investigations(incident_id, limit=limit)
    if reports is None:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="Incident not found.",
        )
    return InvestigationPage(items=reports, limit=limit, count=len(reports))


@app.get(
    "/api/v1/investigations/{investigation_id}",
    response_model=InvestigationReport,
    tags=["investigations"],
)
def get_investigation(investigation_id: int) -> InvestigationReport:
    """Return one immutable saved investigation report."""
    report = get_investigation_report(investigation_id)
    if report is None:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="Investigation not found.",
        )
    return report


@app.post(
    "/api/v1/incidents/{incident_id}/recovery-requests",
    response_model=RecoveryRequestRecord,
    status_code=status.HTTP_201_CREATED,
    tags=["recovery"],
)
def request_recovery(incident_id: int) -> RecoveryRequestRecord:
    """Create a pending allowlisted request without executing it."""
    try:
        return create_recovery_request(incident_id)
    except RecoveryNotFound as error:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND, detail=str(error)
        ) from error
    except RecoveryConflict as error:
        raise HTTPException(
            status_code=status.HTTP_409_CONFLICT, detail=str(error)
        ) from error


@app.get(
    "/api/v1/incidents/{incident_id}/recovery-requests",
    response_model=list[RecoveryRequestRecord],
    tags=["recovery"],
)
def get_recovery_requests(incident_id: int) -> list[RecoveryRequestRecord]:
    """List simulated recovery requests and audit events for one incident."""
    requests = list_recovery_requests(incident_id)
    if requests is None:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="Incident not found.",
        )
    return requests


@app.post(
    "/api/v1/recovery-requests/{request_id}/decision",
    response_model=RecoveryRequestRecord,
    tags=["recovery"],
)
def decide_recovery(
    request_id: int,
    payload: RecoveryDecisionIn,
) -> RecoveryRequestRecord:
    """Record explicit approval or rejection; approval dispatches the fixed action."""
    try:
        return decide_recovery_request(
            request_id,
            payload.decision,
            payload.operator_label.strip(),
        )
    except RecoveryNotFound as error:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND, detail=str(error)
        ) from error
    except RecoveryConflict as error:
        raise HTTPException(
            status_code=status.HTTP_409_CONFLICT, detail=str(error)
        ) from error