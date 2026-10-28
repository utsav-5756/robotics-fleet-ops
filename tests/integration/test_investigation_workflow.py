from fleet_ops.agent import investigation as investigation_service
from fleet_ops.agent.local_provider import LocalProviderUnavailable
from fleet_ops.api.schemas import LocalModelOutput, ModelHypothesis


def investigate(client, incident_id):
    response = client.post(
        f"/api/v1/incidents/{incident_id}/investigations"
    )
    assert response.status_code == 201
    return response.json()


def test_deterministic_report_separates_facts_from_evidence_linked_advice(
    client, create_incident
):
    incident = create_incident()

    report = investigate(client, incident["id"])

    fact_ids = {fact["evidence_id"] for fact in report["observed_facts"]}
    assert report["provider"] == "deterministic"
    assert report["provider_status"] == "DETERMINISTIC"
    assert fact_ids
    assert report["hypotheses"]
    assert report["hypotheses"][0]["evidence_ids"]
    assert set(report["hypotheses"][0]["evidence_ids"]) <= fact_ids
    recommendation = report["recommended_next_steps"][0]
    assert recommendation["recommendation"]
    assert set(recommendation["evidence_ids"]) <= fact_ids
    assert any("not measured facts" in item for item in report["limitations"])

    saved = client.get(f"/api/v1/investigations/{report['id']}")
    assert saved.status_code == 200
    assert saved.json() == report


def test_unavailable_local_model_falls_back_to_deterministic_report(
    client, create_incident, monkeypatch
):
    incident = create_incident()
    monkeypatch.setenv("FLEET_AGENT_PROVIDER", "ollama")

    def unavailable(**_kwargs):
        raise LocalProviderUnavailable("test-only unavailable provider")

    monkeypatch.setattr(
        investigation_service, "request_local_hypotheses", unavailable
    )
    report = investigate(client, incident["id"])

    assert report["provider"] == "deterministic"
    assert report["provider_status"] == "FALLBACK"
    assert report["model"] is None
    assert report["hypotheses"]


def test_local_model_can_select_only_fixed_hypotheses_and_supplied_evidence(
    client, create_incident, monkeypatch
):
    incident = create_incident()
    monkeypatch.setenv("FLEET_AGENT_PROVIDER", "ollama")

    def constrained_selection(**kwargs):
        evidence_id = f"telemetry:{kwargs['evidence'][0]['telemetry_id']}"
        return (
            "test-local-model",
            LocalModelOutput(
                hypotheses=[
                    ModelHypothesis(
                        hypothesis_id="POWER_OR_NETWORK_LOSS",
                        confidence=0.7,
                        evidence_ids=[evidence_id],
                    )
                ]
            ),
        )

    monkeypatch.setattr(
        investigation_service,
        "request_local_hypotheses",
        constrained_selection,
    )
    report = investigate(client, incident["id"])

    assert report["provider"] == "ollama"
    assert report["provider_status"] == "LOCAL_MODEL"
    assert report["model"] == "test-local-model"
    assert report["hypotheses"][0]["hypothesis"] == (
        investigation_service.CANDIDATE_HYPOTHESES["ROBOT_DISCONNECTED"][
            "POWER_OR_NETWORK_LOSS"
        ]
    )
    assert report["hypotheses"][0]["evidence_ids"][0].startswith("telemetry:")


def test_local_model_cannot_cite_unsupplied_evidence(
    client, create_incident, monkeypatch
):
    incident = create_incident()
    monkeypatch.setenv("FLEET_AGENT_PROVIDER", "ollama")
    monkeypatch.setattr(
        investigation_service,
        "request_local_hypotheses",
        lambda **_kwargs: (
            "test-local-model",
            LocalModelOutput(
                hypotheses=[
                    ModelHypothesis(
                        hypothesis_id="POWER_OR_NETWORK_LOSS",
                        confidence=0.7,
                        evidence_ids=["telemetry:999999"],
                    )
                ]
            ),
        ),
    )

    report = investigate(client, incident["id"])

    assert report["provider"] == "deterministic"
    assert report["provider_status"] == "FALLBACK"
    assert report["model"] is None