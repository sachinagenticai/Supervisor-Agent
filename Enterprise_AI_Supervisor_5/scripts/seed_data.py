from __future__ import annotations

from datetime import datetime, timedelta, timezone
from pathlib import Path
import sys
from uuid import uuid4

ROOT_DIR = Path(__file__).resolve().parents[1]
SRC_DIR = ROOT_DIR / "src"
if str(SRC_DIR) not in sys.path:
    sys.path.insert(0, str(SRC_DIR))

from dotenv import load_dotenv

from supervisor_control_tower.agent_registry import AgentRegistry
from supervisor_control_tower.config import get_settings
from supervisor_control_tower.excel_store import ExcelDataStore, initialize_excel_workbook, now_iso
from supervisor_control_tower.seed_records import RECORDS, SEED_VERSION

SEED_USER_ID = "seed-google-user-001"
SEED_USER_EMAIL = "supervisor.user@example.com"


def _past(days_ago: int, minute_offset: int = 0) -> str:
    value = datetime.now(timezone.utc) - timedelta(days=days_ago, minutes=minute_offset)
    return value.isoformat(timespec="seconds")


def _business_decision(verdict: str) -> str:
    return {"PASS": "READY", "WARNING": "NEEDS_REVIEW", "FAIL": "BLOCKED"}[verdict]


def _assurance_band(score: float) -> str:
    if score >= 0.85:
        return "HIGH"
    if score >= 0.65:
        return "MEDIUM"
    return "LOW"


def _seed_reason(agent_code: str, verdict: str) -> str:
    domain = {
        "PIPELINE_TROUBLESHOOTING": "pipeline output",
        "INFRA_PROVISIONING": "infrastructure proposal",
        "FINOPS_OPTIMIZATION": "cost recommendation",
        "PROJECT_MANAGEMENT": "delivery-management output",
        "ENTERPRISE_DOCUMENT_REVIEW": "document review",
    }.get(agent_code, "agent output")
    if verdict == "PASS":
        return f"The {domain} is sufficiently grounded, complete, safe, and consistent with configured controls."
    if verdict == "WARNING":
        return f"The {domain} is usable but has incomplete evidence or governance metadata that requires human review."
    return f"The {domain} contains a critical safety, accuracy, or governance failure and must not progress."


def _recommended_action(verdict: str) -> str:
    return {
        "PASS": "Proceed to the next controlled approval or execution stage.",
        "WARNING": "Assign the identified gaps to the accountable owner and re-evaluate after evidence is updated.",
        "FAIL": "Block execution, escalate the critical finding, and require an approved corrective action before re-evaluation.",
    }[verdict]


def _rule_templates(agent_code: str, verdict: str) -> list[dict[str, object]]:
    prefixes = {
        "PIPELINE_TROUBLESHOOTING": "PIPE",
        "INFRA_PROVISIONING": "IPA",
        "FINOPS_OPTIMIZATION": "FIN",
        "PROJECT_MANAGEMENT": "PM",
        "ENTERPRISE_DOCUMENT_REVIEW": "DOC",
    }
    prefix = prefixes.get(agent_code, "GEN")
    if verdict == "PASS":
        return [
            {"code": f"{prefix}-001", "name": "Mandatory identity and scope evidence", "severity": "CRITICAL", "passed": True, "mandatory": True, "tag": "EVIDENCE_COMPLETENESS"},
            {"code": f"{prefix}-002", "name": "Evidence-grounded conclusion", "severity": "HIGH", "passed": True, "mandatory": True, "tag": "EVIDENCE_GROUNDING"},
            {"code": f"{prefix}-003", "name": "Safety and policy compliance", "severity": "CRITICAL", "passed": True, "mandatory": True, "tag": "SAFETY"},
            {"code": f"{prefix}-004", "name": "Actionable recommendation", "severity": "MEDIUM", "passed": True, "mandatory": False, "tag": "ACTIONABILITY"},
        ]
    if verdict == "WARNING":
        return [
            {"code": f"{prefix}-001", "name": "Mandatory identity and scope evidence", "severity": "CRITICAL", "passed": True, "mandatory": True, "tag": "EVIDENCE_COMPLETENESS"},
            {"code": f"{prefix}-002", "name": "Evidence-grounded conclusion", "severity": "HIGH", "passed": False, "mandatory": True, "tag": "EVIDENCE_GROUNDING"},
            {"code": f"{prefix}-003", "name": "Safety and policy compliance", "severity": "CRITICAL", "passed": True, "mandatory": True, "tag": "SAFETY"},
            {"code": f"{prefix}-004", "name": "Actionable recommendation", "severity": "MEDIUM", "passed": False, "mandatory": False, "tag": "ACTIONABILITY"},
        ]
    return [
        {"code": f"{prefix}-001", "name": "Mandatory identity and scope evidence", "severity": "CRITICAL", "passed": False, "mandatory": True, "tag": "EVIDENCE_COMPLETENESS"},
        {"code": f"{prefix}-002", "name": "Evidence-grounded conclusion", "severity": "HIGH", "passed": False, "mandatory": True, "tag": "EVIDENCE_GROUNDING"},
        {"code": f"{prefix}-003", "name": "Safety and policy compliance", "severity": "CRITICAL", "passed": False, "mandatory": True, "tag": "SAFETY"},
        {"code": f"{prefix}-004", "name": "Actionable recommendation", "severity": "MEDIUM", "passed": False, "mandatory": False, "tag": "ACTIONABILITY"},
    ]


def _scores_for(case_profile: str, sequence: int) -> tuple[str, float, float]:
    if case_profile == "pass":
        return "PASS", min(0.96, 0.87 + (sequence % 5) * 0.018), 0.96
    if case_profile == "warning":
        return "WARNING", 0.66 + (sequence % 4) * 0.018, 0.91
    return "FAIL", 0.28 + (sequence % 4) * 0.025, 0.94


def _agent_row(profile, timestamp: str) -> dict[str, object]:
    return {
        "id": f"agent-{profile.code.lower().replace('_', '-')}",
        "agent_code": profile.code,
        "agent_name": profile.name,
        "description": profile.description,
        "version": profile.version,
        "owner": profile.owner,
        "lifecycle_status": profile.lifecycle_status,
        "capabilities": profile.capabilities,
        "source_systems": profile.source_systems,
        "record_types": profile.record_types,
        "routing_key_hints": profile.routing_key_hints,
        "rule_pack_id": profile.rule_pack_id,
        "tool_code": profile.tool_code,
        "plugin": profile.plugin,
        "judge_rubric": profile.judge_rubric,
        "success_tag": profile.success_tag,
        "thresholds": profile.thresholds.model_dump(),
        "required_evidence": profile.required_evidence,
        "escalation_policy": profile.escalation_policy,
        "enabled": profile.enabled,
        "created_at": timestamp,
        "updated_at": timestamp,
    }


def seed_excel(path: str, *, reset: bool = True) -> None:
    initialize_excel_workbook(path, reset=reset)
    store = ExcelDataStore(path)
    timestamp = now_iso()
    try:
        for sheet in (
            "application_user", "agent_registry", "validation_record", "validation_run",
            "rule_result", "llm_judgement", "audit_event", "connector_sync",
        ):
            store.delete_all(sheet)

        registry = AgentRegistry.from_json(ROOT_DIR / "config" / "agents.json")
        for profile in registry.list_enabled():
            store.insert("agent_registry", _agent_row(profile, timestamp))

        store.insert(
            "application_user",
            {
                "id": SEED_USER_ID,
                "google_subject_id": "seed-google-subject",
                "email": SEED_USER_EMAIL,
                "display_name": "Supervisor User",
                "profile_image_url": "",
                "created_at": timestamp,
                "last_login_at": timestamp,
            },
        )

        for rec_id, external_reference, source, record_type, title, agent, payload, metadata in RECORDS:
            store.insert(
                "validation_record",
                {
                    "id": rec_id,
                    "external_reference": external_reference,
                    "source_system": source,
                    "record_type": record_type,
                    "record_title": title,
                    "expected_agent_code": agent,
                    "payload": payload,
                    "metadata": metadata,
                    "active": True,
                    "created_at": timestamp,
                },
            )

        # Two evaluations per record, spread over 48 days. This gives enough history
        # for dashboard trends, readiness, drift, structured memory, and audit review.
        historical_run_count = 0
        for record_index, record in enumerate(RECORDS):
            rec_id, _, _, _, _, agent_code, _, metadata = record
            profile = registry.get(agent_code)
            case_profile = str(metadata.get("case_profile", "warning"))
            for occurrence in range(2):
                verdict, assurance, routing_confidence = _scores_for(case_profile, record_index + occurrence)
                days_ago = max(0, 47 - ((record_index * 3 + occurrence * 11) % 48))
                started_at = _past(days_ago, 4)
                completed_at = _past(days_ago, 0)
                run_id = str(uuid4())
                decision = _business_decision(verdict)
                reason = _seed_reason(agent_code, verdict)
                action = _recommended_action(verdict)
                quality = {
                    "evidence_grounding": 0.93 if verdict == "PASS" else 0.63 if verdict == "WARNING" else 0.25,
                    "completeness": 0.91 if verdict == "PASS" else 0.68 if verdict == "WARNING" else 0.32,
                    "logical_consistency": 0.94 if verdict == "PASS" else 0.72 if verdict == "WARNING" else 0.35,
                    "safety": 0.98 if verdict != "FAIL" else 0.15,
                    "policy_compliance": 0.92 if verdict == "PASS" else 0.66 if verdict == "WARNING" else 0.22,
                    "actionability": 0.89 if verdict == "PASS" else 0.61 if verdict == "WARNING" else 0.28,
                }
                score_breakdown = {
                    "rule_score": round(min(1.0, assurance + 0.03), 3),
                    "judge_confidence": round(max(0.0, assurance - 0.02), 3),
                    "quality_dimension_score": round(sum(quality.values()) / len(quality), 3),
                    "data_completeness": 0.95 if verdict == "PASS" else 0.72 if verdict == "WARNING" else 0.41,
                    "routing_confidence": routing_confidence,
                    "penalties": 0.0 if verdict == "PASS" else 0.05 if verdict == "WARNING" else 0.2,
                }
                store.insert(
                    "validation_run",
                    {
                        "id": run_id,
                        "record_id": rec_id,
                        "initiated_by_user_id": SEED_USER_ID,
                        "comments": "Seeded production-like assurance evaluation.",
                        "execution_status": "COMPLETED",
                        "detected_agent_code": agent_code,
                        "selected_tool_code": profile.tool_code,
                        "routing_reason": "Matched configured source system, record type, and payload capability hints.",
                        "routing_confidence": routing_confidence,
                        "routing_method": "CONFIGURATION",
                        "routing_candidates": [{"agent_code": agent_code, "score": routing_confidence, "matched_signals": ["source_system", "record_type", "routing_key_hints"]}],
                        "final_verdict": verdict,
                        "business_decision": decision,
                        "final_reason": reason,
                        "final_tag": profile.success_tag if verdict == "PASS" else "HUMAN_REVIEW_REQUIRED" if verdict == "WARNING" else "CRITICAL_CONTROL_FAILURE",
                        "final_confidence": assurance,
                        "assurance_band": _assurance_band(assurance),
                        "recommended_action": action,
                        "data_completeness": score_breakdown["data_completeness"],
                        "score_breakdown": score_breakdown,
                        "disagreement_detected": False,
                        "degraded_mode": False,
                        "context_snapshot": {"policies": ["AI-GOV-001", "HUMAN-OVERSIGHT-002"], "business_unit": "Global Digital Technology"},
                        "memory_snapshot": {"references": [], "summary": "Historical runs were available for trend context."},
                        "governance": {"approved": verdict != "FAIL", "blocked_by": [] if verdict != "FAIL" else ["critical_control_failure"], "dependency_count": 0},
                        "remediation": {"mode": "ADVISORY_ONLY", "approval_required": verdict != "PASS", "actions": []},
                        "started_at": started_at,
                        "completed_at": completed_at,
                        "error_message": "",
                    },
                )

                for rule in _rule_templates(agent_code, verdict):
                    store.insert(
                        "rule_result",
                        {
                            "id": str(uuid4()),
                            "run_id": run_id,
                            "rule_code": rule["code"],
                            "rule_name": rule["name"],
                            "severity": rule["severity"],
                            "passed": rule["passed"],
                            "mandatory": rule["mandatory"],
                            "evidence": {"seeded": True, "record_id": rec_id},
                            "message": f"{rule['name']} {'passed' if rule['passed'] else 'failed'} for the supplied evidence.",
                            "tag": rule["tag"],
                            "created_at": completed_at,
                        },
                    )

                findings = [] if verdict == "PASS" else [{
                    "severity": "HIGH" if verdict == "WARNING" else "CRITICAL",
                    "tag": "EVIDENCE_GAP" if verdict == "WARNING" else "CONTROL_FAILURE",
                    "finding": reason,
                    "evidence": [rec_id],
                }]
                recommendations = [{
                    "priority": "MEDIUM" if verdict == "PASS" else "HIGH" if verdict == "WARNING" else "CRITICAL",
                    "action": action,
                    "owner": profile.owner,
                }]
                store.insert(
                    "llm_judgement",
                    {
                        "id": str(uuid4()),
                        "run_id": run_id,
                        "model_name": "seeded-evaluation-model",
                        "judge_verdict": verdict,
                        "confidence": max(0.1, assurance - 0.02),
                        "reason": reason,
                        "analysis": "The seeded assessment applies common assurance dimensions and the configured agent-specific rubric.",
                        "findings": findings,
                        "recommendations": recommendations,
                        "quality_dimensions": quality,
                        "focus_area_addressed": True,
                        "degraded_mode": False,
                        "raw_response": {"seeded": True, "schema_version": "judge-v2"},
                        "prompt_version": "generic-judge-v2",
                        "created_at": completed_at,
                    },
                )

                events = [
                    ("evaluation_started", {"record_id": rec_id}),
                    ("routing_completed", {"agent_code": agent_code, "confidence": routing_confidence}),
                    ("deterministic_controls_completed", {"verdict": verdict}),
                    ("llm_judgement_completed", {"confidence": assurance - 0.02}),
                    ("evaluation_completed", {"business_decision": decision, "assurance_score": assurance}),
                ]
                for event_type, details in events:
                    store.insert(
                        "audit_event",
                        {
                            "id": str(uuid4()),
                            "run_id": run_id,
                            "user_id": SEED_USER_ID,
                            "event_type": event_type,
                            "event_details": details,
                            "created_at": completed_at,
                        },
                    )
                historical_run_count += 1

        store.insert(
            "connector_sync",
            {
                "id": str(uuid4()),
                "connector_code": "excel_validation_record_connector",
                "sync_status": "COMPLETED",
                "records_read": len(RECORDS),
                "records_written": len(RECORDS),
                "details": {"mode": "seed", "source": "production-like synthetic dataset"},
                "started_at": timestamp,
                "completed_at": timestamp,
            },
        )
        store.upsert("_meta", "key", "seed_version", {"key": "seed_version", "value": SEED_VERSION, "updated_at": timestamp})
        store.upsert("_meta", "key", "record_count", {"key": "record_count", "value": len(RECORDS), "updated_at": timestamp})
        store.upsert("_meta", "key", "history_run_count", {"key": "history_run_count", "value": historical_run_count, "updated_at": timestamp})
        store.save()
    finally:
        store.close()


def main() -> None:
    load_dotenv()
    settings = get_settings()
    if settings.storage_backend.lower() != "excel":
        raise RuntimeError("This release is intentionally Excel-first. Set STORAGE_BACKEND=excel.")
    if settings.app_env.strip().upper() in {"PROD", "PRODUCTION"} and not settings.allow_data_reset:
        raise RuntimeError(
            "Production data reset is disabled. Seed a separate workbook or set ALLOW_DATA_RESET=true "
            "only during an approved initialization window."
        )
    seed_excel(settings.excel_store_path, reset=True)
    print(f"Seeded {len(RECORDS)} records and {len(RECORDS) * 2} historical runs into {settings.excel_store_path}")


if __name__ == "__main__":
    main()
