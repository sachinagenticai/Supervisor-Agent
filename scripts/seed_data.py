from __future__ import annotations

from pathlib import Path
import sys
from datetime import datetime, timezone, timedelta
from uuid import uuid4

ROOT_DIR = Path(__file__).resolve().parents[1]
SRC_DIR = ROOT_DIR / "src"
if str(SRC_DIR) not in sys.path:
    sys.path.insert(0, str(SRC_DIR))

from dotenv import load_dotenv
from sqlalchemy import create_engine, text

from supervisor_control_tower.config import get_settings
from supervisor_control_tower.excel_store import ExcelDataStore, initialize_excel_workbook, json_dumps, now_iso
from supervisor_control_tower.seed_records import AGENTS, RECORDS, SEED_VERSION, j


# ── Historical run scenarios ─────────────────────────────────────────────────
# Produces a rich pre-seeded history so the Insights and Overview dashboards
# look populated from day 1 — without needing the user to click Run Validation
# 20+ times first.

_DEMO_USER_ID = "seed-demo-user-001"
_DEMO_USER_EMAIL = "demo.user@example.com"

def _past(days_ago: int, hours_ago: int = 0) -> str:
    dt = datetime.now(timezone.utc) - timedelta(days=days_ago, hours=hours_ago)
    return dt.isoformat(timespec="seconds")


# Each tuple: (record_id, verdict, confidence, final_tag, routing_confidence, days_ago)
# ~56 runs spread across 30 days so the Overview, Insights, and Review History
# dashboards look production-grade from first launch. Storyline per agent:
#   Pipeline  (UAT Testing)  → strong & improving, high recent pass rate
#   Infra     (Dev / UAT)    → recovering after early security failures
#   FinOps    (UAT Active)   → healthy, with a recent fail cluster (drift signal)
#   PM        (POC)          → mixed, lower pass rate consistent with POC maturity
_HISTORY: list[tuple[str, str, float, str, float, int]] = [
    # ── Pipeline Troubleshooting ───────────────────────────────────────────
    ("rec-pipe-003", "FAIL",    0.29, "REMEDIATION_SAFETY",  0.96, 29),
    ("rec-pipe-002", "WARNING", 0.66, "LOG_EVIDENCE",        0.96, 27),
    ("rec-pipe-004", "PASS",    0.90, "PIPELINE_VALIDATED",  0.96, 24),
    ("rec-pipe-001", "PASS",    0.92, "PIPELINE_VALIDATED",  0.96, 23),
    ("rec-pipe-005", "WARNING", 0.69, "RCA_QUALITY",         0.96, 18),
    ("rec-pipe-001", "PASS",    0.93, "PIPELINE_VALIDATED",  0.96, 17),
    ("rec-pipe-006", "FAIL",    0.31, "REMEDIATION_SAFETY",  0.96, 12),
    ("rec-pipe-004", "PASS",    0.94, "PIPELINE_VALIDATED",  0.96, 10),
    ("rec-pipe-001", "PASS",    0.95, "PIPELINE_VALIDATED",  0.96, 8),
    ("rec-pipe-002", "WARNING", 0.71, "RCA_QUALITY",         0.96, 6),
    ("rec-pipe-004", "PASS",    0.95, "PIPELINE_VALIDATED",  0.96, 5),
    ("rec-pipe-001", "PASS",    0.96, "PIPELINE_VALIDATED",  0.96, 3),
    ("rec-pipe-004", "PASS",    0.94, "PIPELINE_VALIDATED",  0.96, 2),
    ("rec-pipe-001", "PASS",    0.95, "PIPELINE_VALIDATED",  0.96, 1),
    # ── Infrastructure Provisioning ────────────────────────────────────────
    ("rec-ipa-003",  "FAIL",    0.22, "SECURITY_BASELINE",   0.96, 28),
    ("rec-ipa-002",  "WARNING", 0.70, "NAMING_TAGGING",      0.96, 25),
    ("rec-ipa-006",  "FAIL",    0.24, "SECURITY_BASELINE",   0.96, 22),
    ("rec-ipa-004",  "PASS",    0.90, "INFRA_VALIDATED",     0.96, 20),
    ("rec-ipa-001",  "PASS",    0.91, "INFRA_VALIDATED",     0.96, 16),
    ("rec-ipa-005",  "WARNING", 0.72, "TAGGING",             0.96, 13),
    ("rec-ipa-001",  "PASS",    0.92, "INFRA_VALIDATED",     0.96, 11),
    ("rec-ipa-004",  "PASS",    0.93, "INFRA_VALIDATED",     0.96, 9),
    ("rec-ipa-001",  "PASS",    0.93, "INFRA_VALIDATED",     0.96, 7),
    ("rec-ipa-002",  "WARNING", 0.69, "TAGGING",             0.96, 6),
    ("rec-ipa-001",  "PASS",    0.92, "INFRA_VALIDATED",     0.96, 4),
    ("rec-ipa-004",  "PASS",    0.93, "INFRA_VALIDATED",     0.96, 2),
    # ── FinOps Optimization ────────────────────────────────────────────────
    ("rec-fin-001",  "PASS",    0.94, "FINOPS_VALIDATED",    0.96, 26),
    ("rec-fin-004",  "PASS",    0.95, "FINOPS_VALIDATED",    0.96, 23),
    ("rec-fin-001",  "PASS",    0.93, "FINOPS_VALIDATED",    0.96, 20),
    ("rec-fin-002",  "WARNING", 0.70, "COST_DATA",           0.96, 17),
    ("rec-fin-004",  "PASS",    0.95, "FINOPS_VALIDATED",    0.96, 15),
    ("rec-fin-001",  "PASS",    0.94, "FINOPS_VALIDATED",    0.96, 11),
    ("rec-fin-005",  "WARNING", 0.68, "TELEMETRY_COMPLETENESS", 0.96, 8),
    ("rec-fin-001",  "PASS",    0.94, "FINOPS_VALIDATED",    0.96, 6),
    ("rec-fin-004",  "PASS",    0.93, "FINOPS_VALIDATED",    0.96, 5),
    ("rec-fin-003",  "FAIL",    0.25, "SAVINGS_ESTIMATE",    0.96, 3),
    ("rec-fin-006",  "FAIL",    0.27, "SAVINGS_ESTIMATE",    0.96, 2),
    ("rec-fin-002",  "WARNING", 0.67, "COST_DATA",           0.96, 1),
    # ── Project Management ─────────────────────────────────────────────────
    ("rec-pm-003",   "FAIL",    0.40, "SPRINT_CONSISTENCY",  0.96, 27),
    ("rec-pm-002",   "WARNING", 0.64, "ACCEPTANCE_CRITERIA", 0.96, 24),
    ("rec-pm-001",   "PASS",    0.86, "PROJECT_VALIDATED",   0.96, 21),
    ("rec-pm-004",   "PASS",    0.87, "PROJECT_VALIDATED",   0.96, 20),
    ("rec-pm-005",   "WARNING", 0.63, "ACCEPTANCE_CRITERIA", 0.96, 15),
    ("rec-pm-006",   "FAIL",    0.42, "SPRINT_CONSISTENCY",  0.96, 12),
    ("rec-pm-001",   "PASS",    0.85, "PROJECT_VALIDATED",   0.96, 9),
    ("rec-pm-002",   "WARNING", 0.65, "ACCEPTANCE_CRITERIA", 0.96, 6),
    ("rec-pm-004",   "PASS",    0.88, "PROJECT_VALIDATED",   0.96, 4),
    ("rec-pm-001",   "PASS",    0.86, "PROJECT_VALIDATED",   0.96, 3),
    ("rec-pm-004",   "PASS",    0.88, "PROJECT_VALIDATED",   0.96, 1),
]

# Agent routing map
_REC_AGENT_MAP: dict[str, tuple[str, str]] = {
    "rec-pipe-001": ("PIPELINE_TROUBLESHOOTING", "pipeline_troubleshooting_tool"),
    "rec-pipe-002": ("PIPELINE_TROUBLESHOOTING", "pipeline_troubleshooting_tool"),
    "rec-pipe-003": ("PIPELINE_TROUBLESHOOTING", "pipeline_troubleshooting_tool"),
    "rec-pipe-004": ("PIPELINE_TROUBLESHOOTING", "pipeline_troubleshooting_tool"),
    "rec-pipe-005": ("PIPELINE_TROUBLESHOOTING", "pipeline_troubleshooting_tool"),
    "rec-pipe-006": ("PIPELINE_TROUBLESHOOTING", "pipeline_troubleshooting_tool"),
    "rec-ipa-001":  ("INFRA_PROVISIONING",        "infrastructure_provisioning_tool"),
    "rec-ipa-002":  ("INFRA_PROVISIONING",        "infrastructure_provisioning_tool"),
    "rec-ipa-003":  ("INFRA_PROVISIONING",        "infrastructure_provisioning_tool"),
    "rec-ipa-004":  ("INFRA_PROVISIONING",        "infrastructure_provisioning_tool"),
    "rec-ipa-005":  ("INFRA_PROVISIONING",        "infrastructure_provisioning_tool"),
    "rec-ipa-006":  ("INFRA_PROVISIONING",        "infrastructure_provisioning_tool"),
    "rec-fin-001":  ("FINOPS_OPTIMIZATION",       "finops_optimization_tool"),
    "rec-fin-002":  ("FINOPS_OPTIMIZATION",       "finops_optimization_tool"),
    "rec-fin-003":  ("FINOPS_OPTIMIZATION",       "finops_optimization_tool"),
    "rec-fin-004":  ("FINOPS_OPTIMIZATION",       "finops_optimization_tool"),
    "rec-fin-005":  ("FINOPS_OPTIMIZATION",       "finops_optimization_tool"),
    "rec-fin-006":  ("FINOPS_OPTIMIZATION",       "finops_optimization_tool"),
    "rec-pm-001":   ("PROJECT_MANAGEMENT",        "project_management_tool"),
    "rec-pm-002":   ("PROJECT_MANAGEMENT",        "project_management_tool"),
    "rec-pm-003":   ("PROJECT_MANAGEMENT",        "project_management_tool"),
    "rec-pm-004":   ("PROJECT_MANAGEMENT",        "project_management_tool"),
    "rec-pm-005":   ("PROJECT_MANAGEMENT",        "project_management_tool"),
    "rec-pm-006":   ("PROJECT_MANAGEMENT",        "project_management_tool"),
}

# Sample rule results per verdict (minimal — just enough for the insights analytics)
_RULE_SAMPLES: dict[str, list[dict]] = {
    "PASS": [
        {"code": "PIPE-001", "name": "Pipeline run ID exists", "sev": "CRITICAL", "passed": True,  "tag": "PIPELINE_DATA_MISSING"},
        {"code": "PIPE-005", "name": "Logs or stack trace exists", "sev": "CRITICAL", "passed": True,  "tag": "LOG_EVIDENCE"},
        {"code": "PIPE-010", "name": "No secret exposure", "sev": "CRITICAL", "passed": True,  "tag": "REMEDIATION_SAFETY"},
    ],
    "WARNING": [
        {"code": "PIPE-007", "name": "RCA references log evidence", "sev": "HIGH", "passed": False, "tag": "LOG_EVIDENCE"},
        {"code": "PIPE-013", "name": "PR metadata valid", "sev": "MEDIUM", "passed": False, "tag": "PR_STRUCTURE"},
        {"code": "PIPE-001", "name": "Pipeline run ID exists", "sev": "CRITICAL", "passed": True,  "tag": "PIPELINE_DATA_MISSING"},
    ],
    "FAIL": [
        {"code": "PIPE-010", "name": "No secret exposure", "sev": "CRITICAL", "passed": False, "tag": "REMEDIATION_SAFETY"},
        {"code": "PIPE-011", "name": "No unsafe shell command", "sev": "CRITICAL", "passed": False, "tag": "REMEDIATION_SAFETY"},
        {"code": "PIPE-007", "name": "RCA references log evidence", "sev": "HIGH",     "passed": False, "tag": "RCA_QUALITY"},
    ],
}

# Infra rule samples
_INFRA_RULES: dict[str, list[dict]] = {
    "PASS": [
        {"code": "INFRA-003", "name": "Generated IaC exists", "sev": "CRITICAL", "passed": True,  "tag": "IaC_COMPLETENESS"},
        {"code": "INFRA-005", "name": "Naming conventions pass", "sev": "HIGH",     "passed": True,  "tag": "NAMING"},
        {"code": "INFRA-008", "name": "Security baseline present", "sev": "HIGH",   "passed": True,  "tag": "SECURITY_BASELINE"},
    ],
    "WARNING": [
        {"code": "INFRA-005", "name": "Naming conventions pass", "sev": "HIGH",   "passed": False, "tag": "NAMING"},
        {"code": "INFRA-006", "name": "Required tags exist", "sev": "HIGH",      "passed": False, "tag": "TAGGING"},
        {"code": "INFRA-009", "name": "Approval state exists", "sev": "HIGH",    "passed": True,  "tag": "APPROVAL"},
    ],
    "FAIL": [
        {"code": "INFRA-008", "name": "Security baseline present", "sev": "CRITICAL", "passed": False, "tag": "SECURITY_BASELINE"},
        {"code": "INFRA-013", "name": "No hardcoded credentials", "sev": "CRITICAL", "passed": False, "tag": "CREDENTIAL_EXPOSURE"},
        {"code": "INFRA-006", "name": "Required tags exist", "sev": "HIGH",           "passed": False, "tag": "TAGGING"},
    ],
}

# FinOps rule samples
_FINOPS_RULES: dict[str, list[dict]] = {
    "PASS": [
        {"code": "FIN-001", "name": "Scope exists", "sev": "CRITICAL",          "passed": True,  "tag": "TELEMETRY_COMPLETENESS"},
        {"code": "FIN-004", "name": "Utilisation data exists", "sev": "CRITICAL","passed": True,  "tag": "TELEMETRY_COMPLETENESS"},
        {"code": "FIN-009", "name": "Savings not above cost", "sev": "CRITICAL", "passed": True,  "tag": "SAVINGS_ESTIMATE"},
    ],
    "WARNING": [
        {"code": "FIN-005", "name": "Cost data when savings claimed", "sev": "HIGH", "passed": False, "tag": "COST_DATA"},
        {"code": "FIN-003", "name": "Telemetry period exists", "sev": "HIGH",       "passed": False, "tag": "TELEMETRY_COMPLETENESS"},
        {"code": "FIN-013", "name": "Chart data valid", "sev": "LOW",               "passed": False, "tag": "VISUALIZATION_DATA"},
    ],
    "FAIL": [
        {"code": "FIN-009", "name": "Savings not above cost", "sev": "CRITICAL", "passed": False, "tag": "SAVINGS_ESTIMATE"},
        {"code": "FIN-011", "name": "Deletion has evidence", "sev": "CRITICAL",  "passed": False, "tag": "RECOMMENDATION_QUALITY"},
        {"code": "FIN-004", "name": "Utilisation data exists", "sev": "CRITICAL","passed": False, "tag": "TELEMETRY_COMPLETENESS"},
    ],
}

# PM rule samples
_PM_RULES: dict[str, list[dict]] = {
    "PASS": [
        {"code": "PM-001", "name": "Sprint ID and goal exist", "sev": "CRITICAL", "passed": True,  "tag": "SPRINT_DATA"},
        {"code": "PM-002", "name": "Acceptance criteria testable", "sev": "HIGH", "passed": True,  "tag": "ACCEPTANCE_CRITERIA"},
        {"code": "PM-006", "name": "Velocity valid", "sev": "MEDIUM",             "passed": True,  "tag": "VELOCITY"},
    ],
    "WARNING": [
        {"code": "PM-002", "name": "Acceptance criteria testable", "sev": "HIGH", "passed": False, "tag": "ACCEPTANCE_CRITERIA"},
        {"code": "PM-005", "name": "Blocker evidence exists", "sev": "MEDIUM",    "passed": False, "tag": "BLOCKER_EVIDENCE"},
        {"code": "PM-001", "name": "Sprint ID and goal exist", "sev": "CRITICAL", "passed": True,  "tag": "SPRINT_DATA"},
    ],
    "FAIL": [
        {"code": "PM-003", "name": "Status aligns with issues", "sev": "HIGH",   "passed": False, "tag": "SPRINT_CONSISTENCY"},
        {"code": "PM-007", "name": "No duplicate story", "sev": "HIGH",          "passed": False, "tag": "STORY_QUALITY"},
        {"code": "PM-008", "name": "No overcommitment", "sev": "MEDIUM",         "passed": False, "tag": "CAPACITY"},
    ],
}

_AGENT_RULES_MAP = {
    "PIPELINE_TROUBLESHOOTING": _RULE_SAMPLES,
    "INFRA_PROVISIONING": _INFRA_RULES,
    "FINOPS_OPTIMIZATION": _FINOPS_RULES,
    "PROJECT_MANAGEMENT": _PM_RULES,
}


def _get_rules(agent_code: str, verdict: str) -> list[dict]:
    return _AGENT_RULES_MAP.get(agent_code, _RULE_SAMPLES).get(verdict, _RULE_SAMPLES["PASS"])


# ── Rich narrative samples for realistic drill-downs ─────────────────────────
_REASONS: dict[str, dict[str, str]] = {
    "PIPELINE_TROUBLESHOOTING": {
        "PASS": "Root-cause analysis is grounded in log evidence and the proposed remediation is safe and low-risk.",
        "WARNING": "Root-cause is plausible but weakly evidenced; PR metadata is incomplete. Human review recommended.",
        "FAIL": "Remediation proposes an unsafe shell command and the RCA contradicts the log evidence. Blocked.",
    },
    "INFRA_PROVISIONING": {
        "PASS": "Generated IaC matches the request, passes naming, tagging, and security baseline with approval recorded.",
        "WARNING": "Required governance tags are missing and the approval state is not recorded. Review before merge.",
        "FAIL": "Hardcoded credential detected in generated IaC and public network access violates the security baseline.",
    },
    "FINOPS_OPTIMIZATION": {
        "PASS": "Right-sizing recommendation is backed by sustained low-utilisation telemetry with consistent currency.",
        "WARNING": "Savings are claimed but the billing export is incomplete for the lookback window. Review recommended.",
        "FAIL": "Estimated savings exceed the current resource cost and the deletion lacks idle evidence. Blocked.",
    },
    "PROJECT_MANAGEMENT": {
        "PASS": "Generated story has testable acceptance criteria and the sprint summary aligns with issue statuses.",
        "WARNING": "Acceptance criteria are missing or untestable and a blocker lacks a traceable source. Review.",
        "FAIL": "Sprint summary contradicts repository state and a duplicate story was generated. Blocked.",
    },
}

_FINDINGS: dict[str, dict[str, list[dict]]] = {
    "PIPELINE_TROUBLESHOOTING": {
        "WARNING": [{"severity": "HIGH", "tag": "LOG_EVIDENCE", "message": "RCA does not cite a specific log line for the failing stage."}],
        "FAIL": [
            {"severity": "CRITICAL", "tag": "REMEDIATION_SAFETY", "message": "Proposed remediation contains an unsafe 'rm -rf' command."},
            {"severity": "HIGH", "tag": "RCA_QUALITY", "message": "Stated root-cause contradicts the permission-denied error in the logs."},
        ],
    },
    "INFRA_PROVISIONING": {
        "WARNING": [{"severity": "HIGH", "tag": "TAGGING", "message": "Missing required 'owner' and 'cost_center' tags on generated resources."}],
        "FAIL": [
            {"severity": "CRITICAL", "tag": "CREDENTIAL_EXPOSURE", "message": "Hardcoded admin password present in generated IaC."},
            {"severity": "CRITICAL", "tag": "SECURITY_BASELINE", "message": "Public network access enabled on a production resource."},
        ],
    },
    "FINOPS_OPTIMIZATION": {
        "WARNING": [{"severity": "HIGH", "tag": "COST_DATA", "message": "Savings claimed while current monthly cost is unavailable for 21 days of the window."}],
        "FAIL": [
            {"severity": "CRITICAL", "tag": "SAVINGS_ESTIMATE", "message": "Estimated monthly savings ($500) exceed the resource's current monthly cost ($100)."},
            {"severity": "CRITICAL", "tag": "RECOMMENDATION_QUALITY", "message": "Immediate deletion recommended without idle/unattached evidence."},
        ],
    },
    "PROJECT_MANAGEMENT": {
        "WARNING": [{"severity": "MEDIUM", "tag": "ACCEPTANCE_CRITERIA", "message": "Generated story has no testable acceptance criteria."}],
        "FAIL": [
            {"severity": "HIGH", "tag": "SPRINT_CONSISTENCY", "message": "Sprint marked complete while deployment status is failed."},
            {"severity": "HIGH", "tag": "STORY_QUALITY", "message": "Generated story duplicates an existing backlog item."},
        ],
    },
}


def _reason_for(agent_code: str, verdict: str) -> str:
    return _REASONS.get(agent_code, {}).get(
        verdict,
        {
            "PASS": "All mandatory checks passed and the LLM Judge found the output supported.",
            "WARNING": "Human review recommended: one or more HIGH/MEDIUM severity rules failed.",
            "FAIL": "Critical validation failure detected. Agent output is unsafe or materially incomplete.",
        }[verdict],
    )


def _findings_for(agent_code: str, verdict: str) -> list[dict]:
    return _FINDINGS.get(agent_code, {}).get(verdict, [])


def seed_excel(path: str) -> None:
    initialize_excel_workbook(path, reset=True)
    store = ExcelDataStore(path)
    timestamp = now_iso()
    try:
        # ── Agent registry ────────────────────────────────────────────────
        for agent_id, code, name, description, lifecycle, tool_code in AGENTS:
            store.insert(
                "agent_registry",
                {
                    "id": agent_id,
                    "agent_code": code,
                    "agent_name": name,
                    "description": description,
                    "lifecycle_status": lifecycle,
                    "tool_code": tool_code,
                    "enabled": True,
                    "created_at": timestamp,
                    "updated_at": timestamp,
                },
            )
        # ── Validation records ────────────────────────────────────────────
        for rec_id, ext, source, rtype, title, agent, payload, record_metadata in RECORDS:
            store.insert(
                "validation_record",
                {
                    "id": rec_id,
                    "external_reference": ext,
                    "source_system": source,
                    "record_type": rtype,
                    "record_title": title,
                    "expected_agent_code": agent,
                    "payload": json_dumps(payload),
                    "metadata": json_dumps(record_metadata),
                    "active": True,
                    "created_at": timestamp,
                },
            )
        # ── Demo user ─────────────────────────────────────────────────────
        store.insert(
            "application_user",
            {
                "id": _DEMO_USER_ID,
                "google_subject_id": "demo-local-user",
                "email": _DEMO_USER_EMAIL,
                "display_name": "Demo User",
                "profile_image_url": None,
                "created_at": timestamp,
                "last_login_at": timestamp,
            },
        )
        # ── Historical validation runs ────────────────────────────────────
        for rec_id, verdict, confidence, final_tag, routing_conf, days_ago in _HISTORY:
            agent_code, tool_code = _REC_AGENT_MAP.get(rec_id, ("PIPELINE_TROUBLESHOOTING", "pipeline_troubleshooting_tool"))
            run_id = str(uuid4())
            started = _past(days_ago, hours_ago=1)
            completed = _past(days_ago)

            reason = _reason_for(agent_code, verdict)
            findings = _findings_for(agent_code, verdict)

            store.insert(
                "validation_run",
                {
                    "id": run_id,
                    "record_id": rec_id,
                    "initiated_by_user_id": _DEMO_USER_ID,
                    "comments": None,
                    "execution_status": "COMPLETED",
                    "detected_agent_code": agent_code,
                    "selected_tool_code": tool_code,
                    "routing_reason": f"Record routed by deterministic source/type match.",
                    "routing_confidence": routing_conf,
                    "final_verdict": verdict,
                    "final_reason": reason,
                    "final_tag": final_tag,
                    "final_confidence": confidence,
                    "started_at": started,
                    "completed_at": completed,
                    "error_message": None,
                },
            )

            # Insert rule results
            for rule in _get_rules(agent_code, verdict):
                store.insert(
                    "rule_result",
                    {
                        "id": str(uuid4()),
                        "run_id": run_id,
                        "rule_code": rule["code"],
                        "rule_name": rule["name"],
                        "severity": rule["sev"],
                        "passed": rule["passed"],
                        "evidence": json_dumps({}),
                        "message": (
                            f"{rule['name']} is present." if rule["passed"]
                            else f"{rule['name']} check failed."
                        ),
                        "tag": rule["tag"],
                        "created_at": completed,
                    },
                )

            # Insert LLM judgement
            judge_verdict = verdict
            store.insert(
                "llm_judgement",
                {
                    "id": str(uuid4()),
                    "run_id": run_id,
                    "model_name": "seed-mock",
                    "judge_verdict": judge_verdict,
                    "confidence": confidence,
                    "reason": reason,
                    "findings": json_dumps(findings),
                    "raw_response": json_dumps({"seeded": True, "verdict": judge_verdict, "findings": findings}),
                    "prompt_version": "seed-v1",
                    "created_at": completed,
                },
            )

            # Insert audit events
            for event_type in ("validation_started", "routing_completed", "tool_completed", "llm_completed", "validation_completed"):
                store.insert(
                    "audit_event",
                    {
                        "id": str(uuid4()),
                        "run_id": run_id,
                        "user_id": _DEMO_USER_ID,
                        "event_type": event_type,
                        "event_details": json_dumps({"seeded": True}),
                        "created_at": completed,
                    },
                )

        store.upsert("_meta", "key", "seed_version", {"key": "seed_version", "value": SEED_VERSION, "updated_at": timestamp})
        store.upsert("_meta", "key", "record_count", {"key": "record_count", "value": len(RECORDS), "updated_at": timestamp})
        store.upsert("_meta", "key", "history_run_count", {"key": "history_run_count", "value": len(_HISTORY), "updated_at": timestamp})
        store.save()
    finally:
        store.close()


def seed_postgres(database_url: str) -> None:
    engine = create_engine(database_url, future=True)
    with engine.begin() as conn:
        for row in AGENTS:
            conn.execute(
                text("""
                    INSERT INTO agent_registry (id, agent_code, agent_name, description, lifecycle_status, tool_code, enabled)
                    VALUES (:id, :agent_code, :agent_name, :description, :lifecycle_status, :tool_code, true)
                    ON CONFLICT (agent_code) DO UPDATE SET
                        agent_name = EXCLUDED.agent_name,
                        description = EXCLUDED.description,
                        lifecycle_status = EXCLUDED.lifecycle_status,
                        tool_code = EXCLUDED.tool_code,
                        enabled = true,
                        updated_at = now()
                """),
                {"id": row[0], "agent_code": row[1], "agent_name": row[2], "description": row[3], "lifecycle_status": row[4], "tool_code": row[5]},
            )
        for rec_id, ext, source, rtype, title, agent, payload, record_metadata in RECORDS:
            conn.execute(
                text("""
                    INSERT INTO validation_record (id, external_reference, source_system, record_type, record_title, expected_agent_code, payload, metadata, active)
                    VALUES (:id, :external_reference, :source_system, :record_type, :record_title, :expected_agent_code, CAST(:payload AS JSONB), CAST(:metadata AS JSONB), true)
                    ON CONFLICT (external_reference) DO UPDATE SET
                        source_system = EXCLUDED.source_system,
                        record_type = EXCLUDED.record_type,
                        record_title = EXCLUDED.record_title,
                        expected_agent_code = EXCLUDED.expected_agent_code,
                        payload = EXCLUDED.payload,
                        metadata = EXCLUDED.metadata,
                        active = true
                """),
                {
                    "id": rec_id,
                    "external_reference": ext,
                    "source_system": source,
                    "record_type": rtype,
                    "record_title": title,
                    "expected_agent_code": agent,
                    "payload": j(payload),
                    "metadata": j(record_metadata),
                },
            )


def main() -> None:
    load_dotenv()
    settings = get_settings()
    if settings.storage_backend.lower() == "excel":
        seed_excel(settings.excel_store_path)
        print(
            f"Seeded {len(AGENTS)} agents, {len(RECORDS)} records, "
            f"and {len(_HISTORY)} historical validation runs into: {settings.excel_store_path}"
        )
        return
    seed_postgres(settings.database_url)
    print(f"Seeded {len(AGENTS)} agents and {len(RECORDS)} records into PostgreSQL.")


if __name__ == "__main__":
    main()
