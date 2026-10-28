"""Evidence assembly, safe report generation, and persistence."""

import os
from datetime import datetime, timezone
from typing import Any

from fleet_ops.agent.local_provider import (
    LocalProviderUnavailable,
    request_local_hypotheses,
)
from fleet_ops.api.database import (
    list_investigations,
    read_incident_context,
    save_investigation,
    utc_now,
)
from fleet_ops.api.schemas import (
    EvidenceFact,
    InvestigationHypothesis,
    InvestigationRecommendation,
    InvestigationReport,
    ModelHypothesis,
)


CANDIDATE_HYPOTHESES = {
    "LOW_BATTERY": {
        "NORMAL_ENERGY_DEPLETION": "Battery level may reflect normal energy use during the mission.",
        "BATTERY_HEALTH_CONCERN": "Battery capacity or charging health may need operator review.",
        "INSUFFICIENT_EVIDENCE": "Available telemetry does not establish the cause of the low battery.",
    },
    "ROBOT_DISCONNECTED": {
        "TEMPORARY_COMMUNICATION_INTERRUPTION": "A temporary communications interruption may explain the disconnected state.",
        "POWER_OR_NETWORK_LOSS": "A robot power or network issue may explain the disconnected state.",
        "INSUFFICIENT_EVIDENCE": "Available telemetry does not establish why the robot disconnected.",
    },
    "ROUTE_BLOCKED": {
        "ROUTE_OBSTRUCTION": "An obstruction may be preventing progress along the assigned route.",
        "ROUTE_UNAVAILABLE": "The route may be unavailable or inconsistent with the mission plan.",
        "INSUFFICIENT_EVIDENCE": "Available telemetry does not identify why the route is blocked.",
    },
    "MISSION_STALLED": {
        "MISSION_PROGRESS_INTERRUPTED": "An interruption in mission progress may explain the stalled state.",
        "DEPENDENCY_BLOCKED": "A blocked prerequisite or dependency may be preventing mission progress.",
        "INSUFFICIENT_EVIDENCE": "Available telemetry does not establish why mission progress stopped.",
    },
    "SENSOR_RANGE_ABNORMAL": {
        "SENSOR_READING_ANOMALY": "The sensor reading may be anomalous or the sensor may need inspection.",
        "INJECTED_SIMULATOR_FAULT": "The reading may be explained by the selected simulator fault scenario.",
        "INSUFFICIENT_EVIDENCE": "Available telemetry does not establish the cause of the abnormal sensor reading.",
    },
}

RECOMMENDATIONS = {
    "LOW_BATTERY": "Operator should review the battery trend and charging policy before deciding whether a simulated response is warranted.",
    "ROBOT_DISCONNECTED": "Operator should inspect connectivity history and confirm recent telemetry before selecting a response.",
    "ROUTE_BLOCKED": "Operator should inspect route and obstacle evidence before considering a recovery action.",
    "MISSION_STALLED": "Operator should review mission progress and recent telemetry before choosing a recovery step.",
    "SENSOR_RANGE_ABNORMAL": "Operator should compare the reading with recent range history and confirm the selected simulator scenario.",
}

EVIDENCE_LIMITATIONS = [
    "This report summarizes simulated telemetry and cannot establish a physical robot condition.",
    "Hypotheses are possible explanations, not measured facts.",
    "Recommendations are for operator review; no action was approved or executed.",
]


def _build_facts(context: dict[str, Any]) -> list[EvidenceFact]:
    facts = []
    allowed_values = (
        "scenario",
        "sequence",
        "simulation_time_ns",
        "battery_percentage",
        "mission_state",
        "connected",
        "fault_codes",
        "sensor_range_m",
    )
    for record in context["telemetry"]:
        observed_values = {
            key: record[key]
            for key in allowed_values
            if key in record
        }
        facts.append(
            EvidenceFact(
                evidence_id=f"telemetry:{record['id']}",
                telemetry_id=int(record["id"]),
                received_at_utc=record["received_at_utc"],
                observed_values=observed_values,
            )
        )
    return facts


def _fallback_hypothesis(
    incident_type: str,
    evidence_ids: list[str],
) -> InvestigationHypothesis:
    statement = CANDIDATE_HYPOTHESES[incident_type]["INSUFFICIENT_EVIDENCE"]
    return InvestigationHypothesis(
        hypothesis=statement,
        confidence=0.95,
        rationale=(
            "The stored observations support the incident condition but do not "
            "isolate its underlying cause."
        ),
        evidence_ids=evidence_ids[:3],
    )


def _render_model_hypotheses(
    selected: list[ModelHypothesis],
    incident_type: str,
    valid_evidence_ids: set[str],
) -> list[InvestigationHypothesis]:
    candidates = CANDIDATE_HYPOTHESES[incident_type]
    rendered = []
    for item in selected:
        if item.hypothesis_id not in candidates:
            raise LocalProviderUnavailable(
                "The local model selected a hypothesis outside this incident type."
            )
        if not set(item.evidence_ids).issubset(valid_evidence_ids):
            raise LocalProviderUnavailable(
                "The local model cited evidence outside the supplied packet."
            )
        rendered.append(
            InvestigationHypothesis(
                hypothesis=candidates[item.hypothesis_id],
                confidence=item.confidence,
                rationale=(
                    "This is a candidate interpretation of the referenced "
                    "telemetry, not a measured fact."
                ),
                evidence_ids=item.evidence_ids,
            )
        )
    return rendered


def create_investigation(incident_id: int) -> InvestigationReport | None:
    """Create and persist a report using deterministic or optional local inference."""
    context = read_incident_context(incident_id)
    if context is None:
        return None

    incident = context["incident"]
    facts = _build_facts(context)
    evidence_ids = [fact.evidence_id for fact in facts]
    incident_evidence_ids = []
    for evidence_snapshot in (incident['first_evidence'], incident['latest_evidence']):
        telemetry_id = evidence_snapshot.get('telemetry_id')
        if telemetry_id is not None:
            evidence_id = f"telemetry:{telemetry_id}"
            if evidence_id not in incident_evidence_ids:
                incident_evidence_ids.append(evidence_id)
    if not incident_evidence_ids:
        incident_evidence_ids = [f"telemetry:{incident.get('last_telemetry_id')}"]
    if not evidence_ids:
        evidence_ids = [
            f"telemetry:{incident['last_telemetry_id']}"
        ]
        facts = [
            EvidenceFact(
                evidence_id=evidence_ids[0],
                telemetry_id=int(incident["last_telemetry_id"]),
                received_at_utc=incident["last_seen_utc"],
                observed_values=incident["latest_evidence"],
            )
        ]

    configured_provider = os.environ.get(
        "FLEET_AGENT_PROVIDER", "deterministic"
    ).strip().lower()
    provider = "deterministic"
    provider_status = "DETERMINISTIC"
    model_name = None
    hypotheses: list[InvestigationHypothesis]

    if configured_provider == "ollama":
        try:
            model_name, selected = request_local_hypotheses(
                incident_type=incident["incident_type"],
                summary=incident["summary"],
                evidence=[
                    fact.model_dump(mode="json")
                    for fact in facts
                ],
            )
            hypotheses = _render_model_hypotheses(
                selected.hypotheses,
                incident["incident_type"],
                set(evidence_ids),
            )
            provider = "ollama"
            provider_status = "LOCAL_MODEL"
        except LocalProviderUnavailable:
            hypotheses = [
                _fallback_hypothesis(incident["incident_type"], incident_evidence_ids)
            ]
            provider_status = "FALLBACK"
            model_name = None
    else:
        hypotheses = [
            _fallback_hypothesis(incident["incident_type"], incident_evidence_ids)
        ]
        if configured_provider != "deterministic":
            provider_status = "FALLBACK"

    recommendation_ids = incident_evidence_ids[-1:]
    report_body = {
        "incident_id": incident_id,
        "created_at_utc": utc_now(),
        "provider": provider,
        "provider_status": provider_status,
        "model": model_name,
        "observed_facts": [fact.model_dump(mode="json") for fact in facts],
        "hypotheses": [item.model_dump(mode="json") for item in hypotheses],
        "recommended_next_steps": [
            InvestigationRecommendation(
                recommendation=RECOMMENDATIONS[incident["incident_type"]],
                evidence_ids=recommendation_ids,
            ).model_dump(mode="json")
        ],
        "limitations": EVIDENCE_LIMITATIONS,
    }
    report_id = save_investigation(incident_id, report_body)
    return InvestigationReport.model_validate({"id": report_id, **report_body})


def get_investigation_report(investigation_id: int) -> InvestigationReport | None:
    """Retrieve one immutable persisted report."""
    from fleet_ops.api.database import get_investigation

    record = get_investigation(investigation_id)
    if record is None:
        return None
    return InvestigationReport.model_validate(record)


def get_incident_investigations(
    incident_id: int,
    limit: int = 20,
) -> list[InvestigationReport] | None:
    """Read report history, returning None when the incident does not exist."""
    if read_incident_context(incident_id) is None:
        return None
    records = list_investigations(incident_id, limit=limit)
    return [InvestigationReport.model_validate(record) for record in records]
