# Supervisor Agent Control Tower - Excel-first Streamlit POC

This is a Docker-free, Excel-first Proof of Concept for supervising four existing AI agents:

1. Pipeline Troubleshooting Agent
2. Infrastructure Provisioning Agent
3. InfraScaling & Cost Optimization Agent
4. AI-Driven Project Management Agent

The app uses Excel as the current persistence layer and keeps the repository boundary ready for PostgreSQL migration later. The UI, orchestrator, tools, rules, LLM Judge, and final synthesizer do not need to change when storage moves from Excel to PostgreSQL.

## Only Two Commands

From the project folder, use only these two commands.

### 1. Setup, seed data, compile check, and tests

```bash
python run_all.py
```

This command does the full terminal check:

- creates or refreshes the Excel data store
- loads production-like seed records
- runs Python compile checks
- runs automated tests
- confirms the app is ready

### 2. Start the Streamlit app

```bash
streamlit run app.py
```

No Docker. No `PYTHONPATH`. No separate init, seed, or test command.

## What the POC Does

The Supervisor Agent Control Tower validates stored agent execution records. The user selects a data row only. The app never asks the user to manually select the agent, tool, validation mode, or review type.

Validation flow:

```text
Selected Record
  -> Supervisor Orchestrator
  -> Auto-selected Tool Node
  -> Deterministic Rule Checks
  -> gpt-5-mini LLM Judge or MOCK_LLM
  -> Deterministic Final Synthesizer
  -> Excel Storage now / PostgreSQL later
```

Final verdicts are always one of:

- PASS
- WARNING
- FAIL

Each validation stores:

- selected record
- detected agent
- selected tool
- routing reason and confidence
- rule results
- LLM judgement
- final verdict, reason, tag, and confidence
- timestamps
- initiating user
- audit events

## Storage Mode

Current default:

```env
STORAGE_BACKEND=excel
EXCEL_STORE_PATH=data/supervisor_control_tower.xlsx
```

The Excel workbook mirrors the future PostgreSQL tables using sheets such as:

- `_meta`
- `application_user`
- `agent_registry`
- `validation_record`
- `validation_run`
- `rule_result`
- `llm_judgement`
- `audit_event`

## Production-like Seed Data

The seed data includes 12 complex records:

- 3 Pipeline Troubleshooting records
- 3 Infrastructure Provisioning records
- 3 FinOps Optimization records
- 3 Project Management records

Each agent has PASS, WARNING, and FAIL style scenarios. Records include nested real-world fields such as CI/CD logs, stack traces, PR metadata, Terraform/Bicep output, compliance policy results, Azure telemetry, cost data, Jira sprint metrics, repository activity, blockers, risks, capacity, and ownership metadata.

## LLM Mode

Default local/demo mode:

```env
MOCK_LLM=true
LLM_MODEL=gpt-5-mini
```

For a real LLM call later, set:

```env
MOCK_LLM=false
OPENAI_API_KEY=your_key_here
LLM_MODEL=gpt-5-mini
```

The LLM Judge is used only for quality evaluation. It does not select tools, mutate systems, or write directly to storage.

## PostgreSQL Migration Later

When you are ready to move from Excel to PostgreSQL, change configuration only:

```env
STORAGE_BACKEND=postgres
DATABASE_URL=postgresql+psycopg2://user:password@host:5432/supervisor_control_tower
```

The existing UI and validation logic remain the same because storage is isolated behind the repository layer.

## Project Structure

```text
supervisor_agent_control_tower_streamlit/
  app.py                     # Streamlit launcher
  run_all.py                 # one-command setup, seed, compile, and test check
  requirements.txt
  .env.example
  .streamlit/
    config.toml
    secrets.toml.example
  data/
    supervisor_control_tower.xlsx
  scripts/
    init_db.py               # internal helper used by run_all.py
    seed_data.py             # internal helper used by run_all.py
  sql/
    schema.sql               # PostgreSQL schema for later migration
  src/supervisor_control_tower/
    auth.py
    config.py
    db.py
    excel_store.py
    repositories.py
    models.py
    orchestrator.py
    judge.py
    llm_client.py
    synthesizer.py
    validation_service.py
    seed_records.py
    data_science/
      scorecard.py
      record_profile.py
    rules/
      engine.py
    tools/
      pipeline.py
      infrastructure.py
      finops.py
      project_management.py
    ui/
      app.py
      components.py
      pages/
        overview.py
        run_validation.py
        review_history.py
        glossary.py
  tests/
```

## Demo Flow

1. Run `python run_all.py`.
2. Run `streamlit run app.py`.
3. Open the Streamlit URL.
4. Use demo login.
5. Open **Overview** to see validation KPIs.
6. Open **Run Validation**.
7. Select one stored record.
8. Optionally add comments or a focus area.
9. Click **Run Validation**.
10. Review detected agent, selected tool, rule results, LLM judgement, confidence, and final verdict.
11. Open **Review History** to see persisted runs.
12. Open **Glossary** to explain POC scope and capabilities.

## Notes

- Agent/tool selection is automatic.
- The user selects only a stored data row.
- Every validation uses deterministic rules plus LLM Judge plus deterministic final synthesis.
- No live GitHub, Azure, Jira, Teams, or cloud action is performed.
- No generated code is executed.
- Excel is used now only for fast POC execution.
- PostgreSQL can be enabled later through configuration.
