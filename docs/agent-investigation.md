# Incident investigation

The investigation service produces an immutable report for a stored incident. It gathers a bounded set of telemetry records from the same robot and simulator run. The model receives only this selected evidence and cannot query SQLite, invoke arbitrary tools, approve actions, or control robots.

## Report contents

Each report contains:

- Measured telemetry facts with evidence IDs such as `telemetry:123`.
- Hypotheses with confidence and rationale, clearly separated from the facts.
- Fixed operator review suggestions linked to evidence.
- Provider/model status and limitations.

Local-model output is restricted to selecting from predefined hypothesis labels and citing evidence IDs in the supplied packet. Backend code supplies all report text and recommendations. Invalid or unavailable local output falls back to the deterministic report. No motor commands or executable recovery actions are exposed.

## Generate and retrieve a report

Use the interactive API at `http://localhost:8000/docs`, or call:

    Invoke-RestMethod -Method Post -Uri 'http://localhost:8000/api/v1/incidents/6/investigations'
    Invoke-RestMethod 'http://localhost:8000/api/v1/incidents/6/investigations?limit=10'
    Invoke-RestMethod 'http://localhost:8000/api/v1/investigations/1'

Replace the example IDs with an incident and investigation ID from your database. Reports are persisted in the SQLite volume and remain available after container restarts.

## Provider behavior

Deterministic investigation is the default and requires no model. It reports observed facts, an explicit insufficient-evidence hypothesis, and a fixed operator review suggestion.

An optional Ollama instance running locally on the Windows host can be selected with PowerShell environment variables before recreating the backend:

    $env:FLEET_AGENT_PROVIDER = "ollama"
    $env:FLEET_OLLAMA_MODEL = "your-local-model-tag"
    docker compose -f simulator/compose.yaml up -d --force-recreate backend

The default endpoint is `http://host.docker.internal:11434/api/chat`. Only localhost, loopback, and Docker Desktop's host alias are accepted. The model is not downloaded or started by this project. If Ollama is unreachable, misconfigured, or returns invalid evidence references, the request saves a deterministic fallback report. No paid or remote model service is supported.
