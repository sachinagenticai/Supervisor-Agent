from __future__ import annotations

from collections import Counter, defaultdict
from datetime import datetime, timezone
from typing import Any
from uuid import uuid4

from supervisor_control_tower.excel_store import ExcelDataStore, json_dumps, json_loads, now_iso
from supervisor_control_tower.models import (
    AppUser,
    ContextSnapshot,
    FinalSynthesis,
    LlmJudgementResult,
    MemorySnapshot,
    NormalizedRecord,
    RoutingDecision,
    RuleResultModel,
    ValidationRecordSummary,
)


def _truthy(value: Any) -> bool:
    if isinstance(value, bool):
        return value
    if value is None:
        return False
    return str(value).strip().lower() in {"true", "1", "yes", "y"}


def _as_float(value: Any, default: float = 0.0) -> float:
    try:
        return float(value)
    except (TypeError, ValueError):
        return default


class ExcelSupervisorRepository:
    def __init__(self, store: ExcelDataStore):
        self.store = store

    def upsert_user(self, user: AppUser) -> AppUser:
        timestamp = now_iso()
        existing = self.store.find_one(
            "application_user",
            lambda row: str(row.get("google_subject_id")) == user.google_subject_id
            or str(row.get("email", "")).lower() == user.email.lower(),
        )
        user_id = str(existing.get("id")) if existing else user.id
        created_at = existing.get("created_at") if existing else timestamp
        row = {
            "id": user_id,
            "google_subject_id": user.google_subject_id,
            "email": user.email.lower(),
            "display_name": user.display_name,
            "profile_image_url": user.profile_image_url,
            "created_at": created_at,
            "last_login_at": timestamp,
        }
        self.store.upsert("application_user", "id", user_id, row)
        return AppUser(**{**user.model_dump(), "id": user_id})

    def add_audit_event(
        self,
        run_id: str | None,
        user_id: str | None,
        event_type: str,
        event_details: dict[str, Any],
    ) -> None:
        self.store.insert(
            "audit_event",
            {
                "id": str(uuid4()),
                "run_id": run_id,
                "user_id": user_id,
                "event_type": event_type,
                "event_details": event_details,
                "created_at": now_iso(),
            },
        )

    def list_active_records(self) -> list[ValidationRecordSummary]:
        rows = [row for row in self.store.rows("validation_record") if _truthy(row.get("active"))]
        rows.sort(key=lambda row: (str(row.get("expected_agent_code")), str(row.get("external_reference"))))
        return [
            ValidationRecordSummary(
                id=str(row["id"]),
                external_reference=str(row["external_reference"]),
                record_title=str(row["record_title"]),
                source_system=str(row["source_system"]),
                record_type=str(row["record_type"]),
                expected_agent_code=str(row.get("expected_agent_code") or "") or None,
            )
            for row in rows
        ]

    def get_record(self, record_id: str, comments: str | None = None) -> NormalizedRecord:
        row = self.store.find_one("validation_record", lambda item: str(item.get("id")) == record_id)
        if not row:
            raise ValueError(f"Validation record not found: {record_id}")
        metadata = json_loads(row.get("metadata"), {})
        if row.get("expected_agent_code") and "expected_agent_code" not in metadata:
            metadata["expected_agent_code"] = row.get("expected_agent_code")
        return NormalizedRecord(
            record_id=str(row["id"]),
            external_reference=str(row["external_reference"]),
            source_system=str(row["source_system"]),
            record_type=str(row["record_type"]),
            record_title=str(row["record_title"]),
            payload=json_loads(row.get("payload"), {}),
            metadata=metadata,
            comments=comments,
        )

    def create_validation_run(self, record_id: str, user_id: str, comments: str | None) -> str:
        run_id = str(uuid4())
        self.store.insert(
            "validation_run",
            {
                "id": run_id,
                "record_id": record_id,
                "initiated_by_user_id": user_id,
                "comments": comments,
                "execution_status": "RUNNING",
                "started_at": now_iso(),
            },
        )
        self.add_audit_event(run_id, user_id, "evaluation_started", {"record_id": record_id})
        return run_id

    def update_routing(self, run_id: str, routing: RoutingDecision, user_id: str) -> None:
        self.store.update(
            "validation_run",
            "id",
            run_id,
            {
                "detected_agent_code": routing.detected_agent_code,
                "selected_tool_code": routing.selected_tool,
                "routing_reason": routing.reason,
                "routing_confidence": routing.confidence,
                "routing_method": routing.routing_method,
                "routing_candidates": [candidate.model_dump() for candidate in routing.candidates],
            },
        )
        self.add_audit_event(run_id, user_id, "routing_completed", routing.model_dump())

    def insert_rule_results(self, run_id: str, results: list[RuleResultModel], user_id: str) -> None:
        for result in results:
            self.store.insert(
                "rule_result",
                {
                    "id": str(uuid4()),
                    "run_id": run_id,
                    "rule_code": result.rule_code,
                    "rule_name": result.rule_name,
                    "severity": result.severity.value,
                    "passed": result.passed,
                    "mandatory": result.mandatory,
                    "evidence": result.evidence,
                    "message": result.message,
                    "tag": result.tag,
                    "created_at": now_iso(),
                },
            )
        self.add_audit_event(
            run_id,
            user_id,
            "deterministic_controls_completed",
            {
                "total": len(results),
                "failed": len([result for result in results if not result.passed]),
            },
        )

    def insert_llm_judgement(
        self,
        run_id: str,
        model_name: str,
        prompt_version: str,
        judgement: LlmJudgementResult,
        user_id: str,
    ) -> None:
        self.store.insert(
            "llm_judgement",
            {
                "id": str(uuid4()),
                "run_id": run_id,
                "model_name": model_name,
                "judge_verdict": judgement.verdict.value,
                "confidence": judgement.confidence,
                "reason": judgement.reason,
                "analysis": judgement.analysis,
                "findings": [finding.model_dump() for finding in judgement.findings],
                "recommendations": [recommendation.model_dump() for recommendation in judgement.recommendations],
                "quality_dimensions": judgement.quality_dimensions,
                "focus_area_addressed": judgement.focus_area_addressed,
                "degraded_mode": judgement.degraded_mode,
                "raw_response": judgement.raw_response,
                "prompt_version": prompt_version,
                "created_at": now_iso(),
            },
        )
        self.add_audit_event(
            run_id,
            user_id,
            "llm_judgement_completed",
            {
                "verdict": judgement.verdict.value,
                "confidence": judgement.confidence,
                "degraded_mode": judgement.degraded_mode,
            },
        )

    def complete_run(
        self,
        run_id: str,
        final: FinalSynthesis,
        user_id: str,
        context: ContextSnapshot | None = None,
        memory: MemorySnapshot | None = None,
    ) -> None:
        self.store.update(
            "validation_run",
            "id",
            run_id,
            {
                "execution_status": "COMPLETED",
                "final_verdict": final.verdict.value,
                "business_decision": final.business_decision.value,
                "final_reason": final.reason,
                "final_tag": final.primary_tag,
                "final_confidence": final.assurance_score,
                "assurance_band": final.assurance_band.value,
                "recommended_action": final.recommended_action,
                "data_completeness": final.data_completeness,
                "score_breakdown": final.score_breakdown,
                "disagreement_detected": final.disagreement_detected,
                "degraded_mode": final.degraded_mode,
                "context_snapshot": context.model_dump() if context else {},
                "memory_snapshot": memory.model_dump() if memory else {},
                "governance": final.governance.model_dump(),
                "remediation": final.remediation.model_dump(),
                "completed_at": now_iso(),
                "error_message": None,
            },
        )
        self.add_audit_event(
            run_id,
            user_id,
            "evaluation_completed",
            {
                "business_decision": final.business_decision.value,
                "assurance_score": final.assurance_score,
                "primary_tag": final.primary_tag,
            },
        )

    def mark_run_error(self, run_id: str, user_id: str, error_message: str) -> None:
        self.store.update(
            "validation_run",
            "id",
            run_id,
            {
                "execution_status": "ERROR",
                "completed_at": now_iso(),
                "error_message": error_message[:1000],
            },
        )
        self.add_audit_event(
            run_id,
            user_id,
            "evaluation_failed",
            {"error": error_message[:500]},
        )

    def dashboard_metrics(self) -> dict[str, Any]:
        completed = [
            row for row in self.store.rows("validation_run")
            if str(row.get("execution_status")) == "COMPLETED"
        ]
        total = len(completed)
        decisions = Counter(str(row.get("business_decision") or "") for row in completed)
        scores = [_as_float(row.get("final_confidence")) for row in completed]
        return {
            "total_validations": total,
            "ready_count": decisions["READY"],
            "needs_review_count": decisions["NEEDS_REVIEW"],
            "blocked_count": decisions["BLOCKED"],
            "ready_rate": round(decisions["READY"] / total, 3) if total else 0.0,
            "average_assurance": round(sum(scores) / len(scores), 3) if scores else 0.0,
            "active_agents": len([row for row in self.store.rows("agent_registry") if _truthy(row.get("enabled"))]),
        }

    def recent_activity(self, limit: int = 8) -> list[dict[str, Any]]:
        return self.history(limit=limit)

    def history(
        self,
        search: str | None = None,
        agent_code: str | None = None,
        decision: str | None = None,
        limit: int = 200,
    ) -> list[dict[str, Any]]:
        records = {str(row["id"]): row for row in self.store.rows("validation_record")}
        users = {str(row["id"]): row for row in self.store.rows("application_user")}
        rows: list[dict[str, Any]] = []
        for run in self.store.rows("validation_run"):
            record = records.get(str(run.get("record_id")), {})
            user = users.get(str(run.get("initiated_by_user_id")), {})
            row = {
                "run_id": str(run.get("id")),
                "record_id": str(run.get("record_id")),
                "external_reference": str(record.get("external_reference") or ""),
                "record_title": str(record.get("record_title") or ""),
                "source_system": str(record.get("source_system") or ""),
                "record_type": str(record.get("record_type") or ""),
                "agent_code": str(run.get("detected_agent_code") or record.get("expected_agent_code") or ""),
                "business_decision": str(run.get("business_decision") or ""),
                "final_verdict": str(run.get("final_verdict") or ""),
                "assurance_score": _as_float(run.get("final_confidence")),
                "assurance_band": str(run.get("assurance_band") or ""),
                "primary_tag": str(run.get("final_tag") or ""),
                "reason": str(run.get("final_reason") or ""),
                "recommended_action": str(run.get("recommended_action") or ""),
                "execution_status": str(run.get("execution_status") or ""),
                "initiated_by": str(user.get("email") or ""),
                "started_at": str(run.get("started_at") or ""),
                "completed_at": str(run.get("completed_at") or ""),
                "degraded_mode": _truthy(run.get("degraded_mode")),
            }
            if search:
                haystack = " ".join(str(value).lower() for value in row.values())
                if search.lower() not in haystack:
                    continue
            if agent_code and row["agent_code"] != agent_code:
                continue
            if decision and row["business_decision"] != decision:
                continue
            rows.append(row)
        rows.sort(key=lambda row: row.get("completed_at") or row.get("started_at") or "", reverse=True)
        return rows[:limit]

    def run_detail(self, run_id: str) -> dict[str, Any] | None:
        run = self.store.find_one("validation_run", lambda row: str(row.get("id")) == run_id)
        if not run:
            return None
        record = self.store.find_one("validation_record", lambda row: str(row.get("id")) == str(run.get("record_id"))) or {}
        user = self.store.find_one("application_user", lambda row: str(row.get("id")) == str(run.get("initiated_by_user_id"))) or {}
        rule_results = [row for row in self.store.rows("rule_result") if str(row.get("run_id")) == run_id]
        judgement = self.store.find_one("llm_judgement", lambda row: str(row.get("run_id")) == run_id)
        audit = [row for row in self.store.rows("audit_event") if str(row.get("run_id")) == run_id]
        return {
            "run": {**run, **{
                key: json_loads(run.get(key), {})
                for key in (
                    "routing_candidates", "score_breakdown", "context_snapshot", "memory_snapshot",
                    "governance", "remediation",
                )
            }},
            "record": {**record, "payload": json_loads(record.get("payload"), {}), "metadata": json_loads(record.get("metadata"), {})},
            "user": user,
            "rule_results": [
                {**row, "passed": _truthy(row.get("passed")), "mandatory": _truthy(row.get("mandatory")), "evidence": json_loads(row.get("evidence"), {})}
                for row in rule_results
            ],
            "llm_judgement": (
                {
                    **judgement,
                    "findings": json_loads(judgement.get("findings"), []),
                    "recommendations": json_loads(judgement.get("recommendations"), []),
                    "quality_dimensions": json_loads(judgement.get("quality_dimensions"), {}),
                    "raw_response": json_loads(judgement.get("raw_response"), {}),
                }
                if judgement else None
            ),
            "audit_events": [
                {**row, "event_details": json_loads(row.get("event_details"), {})}
                for row in sorted(audit, key=lambda item: str(item.get("created_at") or ""))
            ],
        }

    def agent_health_metrics(self) -> list[dict[str, Any]]:
        agents = [row for row in self.store.rows("agent_registry") if _truthy(row.get("enabled"))]
        history = self.history(limit=10_000)
        grouped: dict[str, list[dict[str, Any]]] = defaultdict(list)
        for row in history:
            if row["execution_status"] == "COMPLETED":
                grouped[row["agent_code"]].append(row)
        result = []
        for agent in agents:
            code = str(agent.get("agent_code"))
            rows = grouped.get(code, [])
            total = len(rows)
            ready = len([row for row in rows if row["business_decision"] == "READY"])
            blocked = len([row for row in rows if row["business_decision"] == "BLOCKED"])
            result.append(
                {
                    "agent_code": code,
                    "agent_name": str(agent.get("agent_name") or code),
                    "lifecycle_status": str(agent.get("lifecycle_status") or ""),
                    "total_runs": total,
                    "ready_rate": round(ready / total, 3) if total else 0.0,
                    "blocked_count": blocked,
                    "average_assurance": round(sum(row["assurance_score"] for row in rows) / total, 3) if total else 0.0,
                    "last_evaluated_at": rows[0]["completed_at"] if rows else None,
                }
            )
        return sorted(result, key=lambda item: item["agent_name"])

    def rule_failure_stats(self, limit: int = 10) -> list[dict[str, Any]]:
        failed = [row for row in self.store.rows("rule_result") if not _truthy(row.get("passed"))]
        counts = Counter((str(row.get("rule_code")), str(row.get("rule_name")), str(row.get("severity")), str(row.get("tag"))) for row in failed)
        return [
            {"rule_code": key[0], "rule_name": key[1], "severity": key[2], "tag": key[3], "failure_count": count}
            for key, count in counts.most_common(limit)
        ]

    def recent_runs_for_drift(self, limit: int = 500) -> list[dict[str, Any]]:
        return self.history(limit=limit)

    def trend_data(self, days: int = 30) -> list[dict[str, Any]]:
        rows = [row for row in self.history(limit=10_000) if row["execution_status"] == "COMPLETED"]
        grouped: dict[str, dict[str, Any]] = {}
        cutoff = datetime.now(timezone.utc).timestamp() - days * 86400
        for row in rows:
            raw = row.get("completed_at") or row.get("started_at")
            try:
                dt = datetime.fromisoformat(str(raw).replace("Z", "+00:00"))
                if dt.timestamp() < cutoff:
                    continue
            except ValueError:
                continue
            day = dt.date().isoformat()
            bucket = grouped.setdefault(day, {"date": day, "total": 0, "ready": 0, "needs_review": 0, "blocked": 0, "assurance_sum": 0.0})
            bucket["total"] += 1
            decision_key = str(row["business_decision"]).lower()
            if decision_key in bucket:
                bucket[decision_key] += 1
            bucket["assurance_sum"] += row["assurance_score"]
        result = []
        for day in sorted(grouped):
            bucket = grouped[day]
            result.append({
                "date": day,
                "total": bucket["total"],
                "ready": bucket["ready"],
                "needs_review": bucket["needs_review"],
                "blocked": bucket["blocked"],
                "average_assurance": round(bucket["assurance_sum"] / bucket["total"], 3) if bucket["total"] else 0.0,
            })
        return result

    def verdict_distribution(self) -> dict[str, int]:
        metrics = self.dashboard_metrics()
        return {
            "READY": metrics["ready_count"],
            "NEEDS_REVIEW": metrics["needs_review_count"],
            "BLOCKED": metrics["blocked_count"],
        }

    def recent_memory(
        self,
        *,
        agent_code: str,
        source_system: str,
        limit: int,
        exclude_record_id: str | None = None,
    ) -> list[dict[str, Any]]:
        rows = [
            row for row in self.history(agent_code=agent_code, limit=500)
            if row["source_system"] == source_system
            and row["execution_status"] == "COMPLETED"
            and row["record_id"] != exclude_record_id
        ]
        return rows[:limit]

    def latest_decision_for_external_reference(self, external_reference: str) -> dict[str, Any] | None:
        matches = [
            row for row in self.history(search=external_reference, limit=100)
            if row["external_reference"] == external_reference and row["execution_status"] == "COMPLETED"
        ]
        return matches[0] if matches else None

    def list_registered_agents(self) -> list[dict[str, Any]]:
        rows = self.store.rows("agent_registry")
        result = []
        for row in rows:
            result.append({
                **row,
                "capabilities": json_loads(row.get("capabilities"), []),
                "source_systems": json_loads(row.get("source_systems"), []),
                "record_types": json_loads(row.get("record_types"), []),
                "routing_key_hints": json_loads(row.get("routing_key_hints"), []),
                "judge_rubric": json_loads(row.get("judge_rubric"), []),
                "thresholds": json_loads(row.get("thresholds"), {}),
                "enabled": _truthy(row.get("enabled")),
            })
        return result


class SupervisorRepository:
    """Repository facade.

    Excel is the controlled deployment backend for this release. PostgreSQL is
    intentionally rejected here instead of silently running with incomplete
    parity. The interface is kept stable for a later database implementation.
    """

    def __init__(self, connection: Any):
        if isinstance(connection, ExcelDataStore):
            self._impl = ExcelSupervisorRepository(connection)
        else:
            raise NotImplementedError(
                "This release is Excel-first. Set STORAGE_BACKEND=excel. "
                "Use PostgreSQL before horizontal scaling or multi-instance deployment."
            )

    def __getattr__(self, name: str) -> Any:
        return getattr(self._impl, name)
