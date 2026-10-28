"""Validated telemetry and incident API models."""

from typing import Literal

from pydantic import BaseModel, ConfigDict, Field


Scenario = Literal[
    "normal",
    "low_battery",
    "blocked_route",
    "disconnected",
    "stalled_mission",
    "abnormal_sensor",
]
MissionState = Literal["EN_ROUTE", "RETURNING", "BLOCKED", "STALLED", "UNKNOWN"]
FaultCode = Literal["LOW_BATTERY", "ROUTE_BLOCKED", "ROBOT_DISCONNECTED", "MISSION_STALLED", "SENSOR_RANGE_ABNORMAL"]


class TelemetryIn(BaseModel):
    """Normalized representation of one fleet_interfaces telemetry message."""

    model_config = ConfigDict(extra="forbid")

    run_id: str = Field(min_length=1, max_length=128)
    robot_id: str = Field(pattern=r"^robot_[0-9]{2}$", max_length=32)
    sequence: int = Field(ge=0, le=9_223_372_036_854_775_807)
    scenario: Scenario
    seed: int = Field(ge=0, le=4_294_967_295)
    simulation_time_ns: int = Field(ge=0, le=9_223_372_036_854_775_807)
    frame_id: str = Field(min_length=1, max_length=128)
    x_m: float = Field(ge=-1000.0, le=1000.0, allow_inf_nan=False)
    y_m: float = Field(ge=-1000.0, le=1000.0, allow_inf_nan=False)
    heading_rad: float = Field(ge=-6.283185307179586, le=6.283185307179586, allow_inf_nan=False)
    battery_percentage: float = Field(ge=0.0, le=100.0, allow_inf_nan=False)
    mission_state: MissionState
    connected: bool
    fault_codes: list[FaultCode] = Field(max_length=16)
    sensor_range_m: float = Field(ge=0.0, le=1000.0, allow_inf_nan=False)


class TelemetryAccepted(BaseModel):
    """Acknowledgment returned after a telemetry record is accepted."""

    accepted: bool = True
    duplicate: bool
    record_id: int


class TelemetryRecord(TelemetryIn):
    """Persisted telemetry including server receipt time."""

    id: int
    received_at_utc: str


class TelemetryPage(BaseModel):
    """Bounded telemetry query response."""

    items: list[TelemetryRecord]
    limit: int
    count: int


class IncidentRecord(BaseModel):
    """A deterministic incident with its supporting telemetry evidence."""

    id: int
    run_id: str
    robot_id: str
    incident_type: str
    severity: Literal["WARNING", "MEDIUM", "HIGH"]
    status: Literal["ACTIVE", "RESOLVED"]
    summary: str
    first_seen_utc: str
    last_seen_utc: str
    resolved_at_utc: str | None
    observation_count: int
    first_telemetry_id: int
    last_telemetry_id: int
    resolved_by_telemetry_id: int | None
    first_evidence: dict
    latest_evidence: dict


class IncidentPage(BaseModel):
    """Bounded incident query response."""

    items: list[IncidentRecord]
    limit: int
    count: int


class EvidenceFact(BaseModel):
    """One measured, server-selected telemetry fact."""

    evidence_id: str
    telemetry_id: int
    received_at_utc: str
    observed_values: dict


class ModelHypothesis(BaseModel):
    """Constrained local-model hypothesis selection."""

    model_config = ConfigDict(extra="forbid")

    hypothesis_id: Literal[
        "NORMAL_ENERGY_DEPLETION",
        "BATTERY_HEALTH_CONCERN",
        "TEMPORARY_COMMUNICATION_INTERRUPTION",
        "POWER_OR_NETWORK_LOSS",
        "ROUTE_OBSTRUCTION",
        "ROUTE_UNAVAILABLE",
        "MISSION_PROGRESS_INTERRUPTED",
        "DEPENDENCY_BLOCKED",
        "SENSOR_READING_ANOMALY",
        "INJECTED_SIMULATOR_FAULT",
        "INSUFFICIENT_EVIDENCE",
    ]
    confidence: float = Field(ge=0.0, le=1.0, allow_inf_nan=False)
    evidence_ids: list[str] = Field(min_length=1, max_length=12)


class LocalModelOutput(BaseModel):
    """Only the constrained hypotheses are accepted from a local model."""

    model_config = ConfigDict(extra="forbid")

    hypotheses: list[ModelHypothesis] = Field(max_length=3)


class InvestigationHypothesis(BaseModel):
    """A hypothesis clearly separated from measured facts."""

    hypothesis: str
    confidence: float = Field(ge=0.0, le=1.0)
    rationale: str
    evidence_ids: list[str]


class InvestigationRecommendation(BaseModel):
    """A fixed operator review suggestion, never an executable action."""

    recommendation: str
    evidence_ids: list[str]


class InvestigationReport(BaseModel):
    """Persisted report with evidence, hypotheses, and safe next steps."""

    id: int
    incident_id: int
    created_at_utc: str
    provider: Literal["deterministic", "ollama"]
    provider_status: Literal["DETERMINISTIC", "LOCAL_MODEL", "FALLBACK"]
    model: str | None
    observed_facts: list[EvidenceFact]
    hypotheses: list[InvestigationHypothesis]
    recommended_next_steps: list[InvestigationRecommendation]
    limitations: list[str]


class InvestigationPage(BaseModel):
    """Bounded report history for one incident."""

    items: list[InvestigationReport]
    limit: int
    count: int

RecoveryActionType = Literal["SIMULATED_RECONNECT"]
RecoveryRequestStatus = Literal[
    "PENDING", "APPROVED", "REJECTED", "EXECUTED", "FAILED", "EXPIRED"
]


class RecoveryDecisionIn(BaseModel):
    """Explicit local operator decision for a pending simulated action."""

    model_config = ConfigDict(extra="forbid")

    decision: Literal["approve", "reject"]
    operator_label: str = Field(min_length=1, max_length=64, pattern=r"^.*\S.*$")


class RecoveryAuditEvent(BaseModel):
    """Append-only audit entry for one simulated recovery request."""

    id: int
    request_id: int
    event_type: str
    occurred_at_utc: str
    operator_label: str | None
    details: dict


class RecoveryRequestRecord(BaseModel):
    """Current state plus immutable event history for a simulated action."""

    id: int
    incident_id: int
    run_id: str
    robot_id: str
    action_type: RecoveryActionType
    status: RecoveryRequestStatus
    requested_at_utc: str
    decided_at_utc: str | None
    operator_label: str | None
    outcome: dict | None
    events: list[RecoveryAuditEvent]