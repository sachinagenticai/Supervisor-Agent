# Enterprise AI Supervisor

A configuration-driven Streamlit application for evaluating, governing and auditing outputs produced by enterprise AI agents.

This version is intentionally **Streamlit-only**. It does not include FastAPI, Uvicorn, REST endpoints, API keys or CORS configuration. The application is designed to be deployed directly from GitHub to Streamlit Community Cloud or run locally with `streamlit run app.py`.

## What is included

- Generic Agent Library loaded from `config/agents.json`
- Configuration-only agent onboarding for generic agents
- Capability-, source-, record-type- and payload-key-based routing
- Restricted LLM routing fallback for ambiguous records
- Built-in Python rule packs for complex domains
- JSON-configured rule packs for generic agents
- Generic tool framework and optional custom plugins
- Generalized LLM-as-a-Judge with common and agent-specific rubrics
- Explainable AI Assurance Score with safety caps and disagreement penalties
- Business decisions: `READY`, `NEEDS_REVIEW`, `BLOCKED`
- Business context and safe structured historical memory
- Cross-agent dependency and approval governance
- Approval-only remediation planning; no external write-back
- Custom Google OAuth authentication using `GOOGLE_CLIENT_ID`, `GOOGLE_CLIENT_SECRET` and `GOOGLE_REDIRECT_URI`
- Equal application access for all authenticated users
- Professional Streamlit UI: Dashboard, Evaluate, History and a detailed Agent Glossary
- Complete audit history and JSON exports inside the Streamlit application
- Excel connector with atomic writes and file locking
- Production-like dataset with 32 records across five agent types
- 64 seeded historical evaluations for trends, memory and dashboards
- Automated tests and deployment validation scripts

## Included agents

1. Pipeline Troubleshooting
2. Infrastructure Provisioning
3. FinOps Optimization
4. AI-Driven Project Management
5. Enterprise Document Review

The fifth agent is configuration-only and demonstrates that a generic agent can be added without changing the Supervisor orchestrator.

## Agent Glossary page

The Agent Glossary is generated from the same configuration used by routing and validation. It includes:

- A searchable overview of every registered agent
- Business purpose, outcomes and common use cases
- Typical inputs, outputs and required evidence
- Supported source systems, task types and routing signals
- The complete deterministic control catalogue for each agent
- Agent-specific LLM-as-a-Judge rubric and decision thresholds
- Human-review triggers, escalation paths and operating boundaries
- End-to-end supervision flow and Assurance Score explanation
- Business decision definitions and core AI-governance terminology

New agents automatically appear when their definition and glossary metadata are added to `config/agents.json`.

## Architecture

```text
Excel Record Connector
        |
        v
Input normalization and payload limits
        |
        v
Generic Agent Registry and capability routing
        |
        +--> deterministic profile match
        +--> restricted LLM routing fallback
        |
        v
Configured tool and rule pack
        |
        v
Business context + structured prior-run memory
        |
        v
Generalized LLM-as-a-Judge
        |
        v
Governance and deterministic final synthesis
        |
        v
Business decision + AI Assurance Score + remediation plan
        |
        v
Excel audit store + Streamlit Dashboard, Evaluate, History and Agent Glossary
```

## LLM backend

The application uses the **standard OpenAI API only** through `OPENAI_API_KEY` and `LLM_MODEL`. There is no Azure OpenAI path. Set `MOCK_LLM=true` for repeatable local testing without an external API call.

## AI Assurance Score

The score is an explainable governance indicator, not a calibrated probability.

```text
30% severity-weighted deterministic rules
25% LLM Judge confidence
20% quality-dimension average
15% data completeness
10% routing confidence
- disagreement penalty
- critical-failure, degraded-mode and missing-evidence caps
```

A critical control failure caps the assurance score at 40% by default. LLM degraded mode caps it at 70%. Missing mandatory evidence applies the configured agent cap.

## Local setup

Use Python 3.11 or 3.12.

### Windows PowerShell

```powershell
py -3.11 -m venv .venv
.\.venv\Scripts\Activate.ps1
python -m pip install --upgrade pip
python -m pip install -r requirements-dev.txt
Copy-Item .env.example .env
New-Item -ItemType Directory -Force .streamlit | Out-Null
notepad .env
streamlit run app.py
```

Before starting the app, set `GOOGLE_REDIRECT_URI=http://localhost:8501` in `.env` and add the same root URL to the Google OAuth client's Authorized redirect URIs. Authentication is mandatory; there is no demo or local-user bypass.

Use `python -m pip`, not `pip -m`.

### Linux/macOS

```bash
python3.11 -m venv .venv
source .venv/bin/activate
python -m pip install --upgrade pip
python -m pip install -r requirements-dev.txt
cp .env.example .env
streamlit run app.py
```

Before starting the app, set `GOOGLE_REDIRECT_URI=http://localhost:8501` in `.env` and add the same root URL to the Google OAuth client's Authorized redirect URIs. Authentication is mandatory; there is no demo or local-user bypass.

To recreate the realistic local workbook and run all checks:

```bash
python run_all.py
```

`run_all.py` resets seed data and is blocked when `APP_ENV=PRODUCTION`.

## Streamlit Community Cloud deployment

1. Push the project contents to a GitHub repository.
2. Ensure `app.py`, `requirements.txt`, `src/`, `config/` and `data/supervisor_control_tower.xlsx` are committed.
3. Do not commit `.env`.
4. Create the app in Streamlit Community Cloud and select `app.py` as the entrypoint.
5. Add the same top-level variable names from `.env.example` in the app's Secrets settings.
6. Set `GOOGLE_REDIRECT_URI=https://<app-name>.streamlit.app` in Streamlit Secrets.
7. Add the same root URL to the Google OAuth client's Authorized redirect URIs.

The application preserves the original custom Google OAuth flow. It receives the Google `code` and `state` callback on the Streamlit root URL, verifies the ID token, and gives all authenticated users the same application access. Google handles the user's email and password on Google's hosted sign-in page.

Example Streamlit Cloud secrets:

```toml
STORAGE_BACKEND = "excel"
EXCEL_STORE_PATH = "data/supervisor_control_tower.xlsx"
MOCK_LLM = false
OPENAI_API_KEY = "replace-with-secret"
LLM_MODEL = "gpt-5-mini"
APP_ENV = "POC"
EXTERNAL_WRITEBACK_ENABLED = false
GOOGLE_CLIENT_ID = "replace-with-google-client-id"
GOOGLE_CLIENT_SECRET = "replace-with-google-client-secret"
GOOGLE_REDIRECT_URI = "https://<app-name>.streamlit.app"
```

### Important Excel limitation on Community Cloud

The committed Excel workbook provides realistic input data and lets the application run. Evaluations, history and audit writes made to the local workbook are not guaranteed to survive a Community Cloud reboot, redeployment or platform file cleanup. Therefore:

- Community Cloud + Excel is appropriate for a POC or stakeholder demonstration.
- Download/export important results before a reboot.
- Do not describe this deployment as durable production persistence.
- Move persistence to PostgreSQL or managed object storage before a true production rollout.

## Access model

There are no Admin, Reviewer or Viewer restrictions in this release. Every authenticated user can open Dashboard, run evaluations, review history, inspect the Agent Glossary and export results. Enterprise authorization can be added later without changing Google authentication.

## Add a configuration-only agent

1. Add an agent definition to `config/agents.json`.
2. Give it a unique `code` and `tool_code`.
3. Set `plugin` to `null` for a generic configured agent.
4. Define routing source systems, record types and payload-key hints.
5. Add its rule pack to `config/rule_packs.json`.
6. Add business context to `config/business_context.json`.
7. Add representative records to the Excel input dataset.
8. Run `python run_all.py` locally.

No orchestrator change is required. Complex domain logic can still be implemented as a custom tool plugin registered in `src/supervisor_control_tower/tools/__init__.py`.

## Excel data model

The workbook contains:

- `_meta`
- `application_user`
- `agent_registry`
- `validation_record`
- `validation_run`
- `rule_result`
- `llm_judgement`
- `audit_event`
- `connector_sync`

Writes are guarded by an inter-process file lock and saved atomically. Network-bound LLM calls occur outside the Excel lock.

Create a local locked backup with:

```bash
python scripts/backup_excel.py --destination data/backups --retention 20
```

Run the non-destructive deployment check with:

```bash
python scripts/validate_deployment.py
```

## Remediation safety

The application creates a remediation plan from failed deterministic controls and LLM recommendations. Every action is approval-required. It does not invoke GitHub, Jira, Azure, ServiceNow, cloud-resource or shell write operations. `EXTERNAL_WRITEBACK_ENABLED=true` is rejected at startup.

## Testing

```bash
python -m pytest
```

Coverage includes routing, rule packs, configuration-only onboarding, Google OIDC claim mapping, assurance caps, realistic seed quality, OpenAI configuration, mock judge validation and end-to-end Excel persistence.

## Project structure

```text
app.py                          Streamlit entrypoint
config/                         Agent, rule and business-context definitions
data/                           Excel input and local audit store
scripts/                        Initialization, seeding, backup and validation
src/supervisor_control_tower/
  agent_registry.py             Generic Agent Library
  agent_glossary.py             Searchable business glossary helpers
  orchestrator.py               Capability-based routing
  rules/                        Built-in and configured rules
  tools/                        Generic tool registry and domain plugins
  judge.py                      Generalized LLM-as-a-Judge
  data_science/scorecard.py     Explainable assurance score
  context.py                    Business context layer
  memory.py                     Structured history memory
  governance.py                 Dependencies and approvals
  remediation.py                Approval-only action planning
  repositories.py               Excel repository facade
  validation_service.py         End-to-end workflow
  ui/                           Dashboard, Evaluate, History and Agent Glossary
requirements.txt                Streamlit runtime dependencies
.streamlit/config.toml          Streamlit presentation/server configuration
.streamlit/secrets.toml.example Secret names for local/cloud configuration
```
