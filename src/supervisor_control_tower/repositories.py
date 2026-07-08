from __future__ import annotations

import json
from datetime import datetime, timezone
from typing import Any
from uuid import uuid4

from sqlalchemy import Connection, text

from supervisor_control_tower.excel_store import ExcelDataStore, json_dumps, json_loads, now_iso
from supervisor_control_tower.models import (
    AppUser,
    ExecutionStatus,
    FinalSynthesis,
    LlmJudgementResult,
    NormalizedRecord,
    RoutingDecision,
    RuleResultModel,
    ValidationRecordSummary,
)


def _json(value: Any) -> str:
    return json.dumps(value, default=str)


def _row_to_dict(row: Any) -> dict[str, Any]:
    return dict(row._mapping)


def _truthy(value: Any) -> bool:
    if isinstance(value, bool):
        return value
    if value is None:
        return False
    return str(value).strip().lower() in {"true", "1", "yes", "y"}


def _as_float(value: Any) -> float | None:
    if value in (None, ""):
        return None
    return float(value)


class SqlSupervisorRepository:
    def __init__(self, conn: Connection):
        self.conn = conn

    def upsert_user(self, user: AppUser) -> AppUser:
        row = self.conn.execute(
            text(
                """
                INSERT INTO application_user (id, google_subject_id, email, display_name, profile_image_url, created_at, last_login_at)
                VALUES (:id, :google_subject_id, :email, :display_name, :profile_image_url, now(), now())
                ON CONFLICT (google_subject_id) DO UPDATE SET
                    email = EXCLUDED.email,
                    display_name = EXCLUDED.display_name,
                    profile_image_url = EXCLUDED.profile_image_url,
                    last_login_at = now()
                RETURNING id, google_subject_id, email, display_name, profile_image_url
                """
            ),
            user.model_dump(),
        ).one()
        return AppUser(**_row_to_dict(row))

    def add_audit_event(self, run_id: str | None, user_id: str | None, event_type: str, details: dict[str, Any]) -> None:
        self.conn.execute(
            text(
                """
                INSERT INTO audit_event (id, run_id, user_id, event_type, event_details, created_at)
                VALUES (:id, :run_id, :user_id, :event_type, CAST(:event_details AS JSONB), now())
                """
            ),
            {
                "id": str(uuid4()),
                "run_id": run_id,
                "user_id": user_id,
                "event_type": event_type,
                "event_details": _json(details),
            },
        )

    def list_active_records(self) -> list[ValidationRecordSummary]:
        rows = self.conn.execute(
            text(
                """
                SELECT id, external_reference, record_title, source_system, record_type, expected_agent_code
                FROM validation_record
                WHERE active = true
                ORDER BY external_reference
                """
            )
        ).all()
        return [ValidationRecordSummary(**_row_to_dict(r)) for r in rows]

    def get_record(self, record_id: str, comments: str | None = None) -> NormalizedRecord:
        row = self.conn.execute(
            text(
                """
                SELECT id AS record_id, external_reference, source_system, record_type, record_title, payload, metadata
                FROM validation_record
                WHERE id = :id AND active = true
                """
            ),
            {"id": record_id},
        ).one_or_none()
        if row is None:
            raise ValueError("Selected validation record was not found or is inactive.")
        data = _row_to_dict(row)
        data["comments"] = comments
        return NormalizedRecord(**data)

    def create_validation_run(self, record_id: str, user_id: str, comments: str | None) -> str:
        run_id = str(uuid4())
        self.conn.execute(
            text(
                """
                INSERT INTO validation_run (
                    id, record_id, initiated_by_user_id, comments, execution_status, started_at
                ) VALUES (:id, :record_id, :initiated_by_user_id, :comments, :execution_status, now())
                """
            ),
            {
                "id": run_id,
                "record_id": record_id,
                "initiated_by_user_id": user_id,
                "comments": comments,
                "execution_status": ExecutionStatus.RUNNING.value,
            },
        )
        self.add_audit_event(run_id, user_id, "validation_started", {"record_id": record_id})
        return run_id

    def update_routing(self, run_id: str, routing: RoutingDecision, user_id: str) -> None:
        self.conn.execute(
            text(
                """
                UPDATE validation_run SET
                    detected_agent_code = :detected_agent_code,
                    selected_tool_code = :selected_tool_code,
                    routing_reason = :routing_reason,
                    routing_confidence = :routing_confidence
                WHERE id = :run_id
                """
            ),
            {
                "run_id": run_id,
                "detected_agent_code": routing.detected_agent_code.value,
                "selected_tool_code": routing.selected_tool.value,
                "routing_reason": routing.reason,
                "routing_confidence": routing.confidence,
            },
        )
        self.add_audit_event(run_id, user_id, "routing_completed", routing.model_dump(mode="json"))

    def insert_rule_results(self, run_id: str, results: list[RuleResultModel], user_id: str) -> None:
        for result in results:
            self.conn.execute(
                text(
                    """
                    INSERT INTO rule_result (
                        id, run_id, rule_code, rule_name, severity, passed, evidence, message, tag, created_at
                    ) VALUES (
                        :id, :run_id, :rule_code, :rule_name, :severity, :passed,
                        CAST(:evidence AS JSONB), :message, :tag, now()
                    )
                    """
                ),
                {
                    "id": str(uuid4()),
                    "run_id": run_id,
                    "rule_code": result.rule_code,
                    "rule_name": result.rule_name,
                    "severity": result.severity.value,
                    "passed": result.passed,
                    "evidence": _json(result.evidence),
                    "message": result.message,
                    "tag": result.tag,
                },
            )
        self.add_audit_event(run_id, user_id, "tool_completed", {"rule_count": len(results)})

    def insert_llm_judgement(self, run_id: str, model_name: str, prompt_version: str, judgement: LlmJudgementResult, user_id: str) -> None:
        self.conn.execute(
            text(
                """
                INSERT INTO llm_judgement (
                    id, run_id, model_name, judge_verdict, confidence, reason, findings,
                    raw_response, prompt_version, created_at
                ) VALUES (
                    :id, :run_id, :model_name, :judge_verdict, :confidence, :reason,
                    CAST(:findings AS JSONB), CAST(:raw_response AS JSONB), :prompt_version, now()
                )
                """
            ),
            {
                "id": str(uuid4()),
                "run_id": run_id,
                "model_name": model_name,
                "judge_verdict": judgement.verdict.value,
                "confidence": judgement.confidence,
                "reason": judgement.reason,
                "findings": _json([f.model_dump(mode="json") for f in judgement.findings]),
                "raw_response": _json(judgement.raw_response or judgement.model_dump(mode="json")),
                "prompt_version": prompt_version,
            },
        )
        self.add_audit_event(run_id, user_id, "llm_completed", {"verdict": judgement.verdict.value})

    def complete_run(self, run_id: str, final: FinalSynthesis, user_id: str) -> None:
        self.conn.execute(
            text(
                """
                UPDATE validation_run SET
                    execution_status = :status,
                    final_verdict = :final_verdict,
                    final_reason = :final_reason,
                    final_tag = :final_tag,
                    final_confidence = :final_confidence,
                    completed_at = now(),
                    error_message = null
                WHERE id = :run_id
                """
            ),
            {
                "run_id": run_id,
                "status": ExecutionStatus.COMPLETED.value,
                "final_verdict": final.verdict.value,
                "final_reason": final.reason,
                "final_tag": final.primary_tag,
                "final_confidence": final.confidence,
            },
        )
        self.add_audit_event(run_id, user_id, "validation_completed", final.model_dump(mode="json"))

    def mark_run_error(self, run_id: str, user_id: str, message: str) -> None:
        self.conn.execute(
            text(
                """
                UPDATE validation_run SET execution_status = :status, error_message = :message, completed_at = now()
                WHERE id = :run_id
                """
            ),
            {"run_id": run_id, "status": ExecutionStatus.ERROR.value, "message": message[:1000]},
        )
        self.add_audit_event(run_id, user_id, "validation_error", {"message": message[:1000]})

    def dashboard_metrics(self) -> dict[str, Any]:
        row = self.conn.execute(
            text(
                """
                SELECT
                    COUNT(*) FILTER (WHERE execution_status = 'COMPLETED') AS total_validations,
                    COUNT(*) FILTER (WHERE final_verdict = 'PASS') AS pass_count,
                    COUNT(*) FILTER (WHERE final_verdict = 'FAIL') AS fail_count,
                    COUNT(*) FILTER (WHERE final_verdict = 'WARNING') AS warning_count
                FROM validation_run
                """
            )
        ).one()
        data = _row_to_dict(row)
        total = int(data["total_validations"] or 0)
        data["pass_rate"] = round((int(data["pass_count"] or 0) / total) * 100, 1) if total else 0.0
        data["fail_rate"] = round((int(data["fail_count"] or 0) / total) * 100, 1) if total else 0.0
        data["agents_supported"] = self.conn.execute(text("SELECT COUNT(*) FROM agent_registry WHERE enabled = true")).scalar_one()
        return data

    def recent_activity(self, limit: int = 15) -> list[dict[str, Any]]:
        rows = self.conn.execute(
            text(
                """
                SELECT vr.completed_at AS time, vr.detected_agent_code, rec.record_title AS record,
                       vr.final_verdict AS verdict, vr.final_tag AS tag, vr.final_confidence AS confidence
                FROM validation_run vr
                JOIN validation_record rec ON rec.id = vr.record_id
                WHERE vr.execution_status = 'COMPLETED'
                ORDER BY vr.completed_at DESC NULLS LAST
                LIMIT :limit
                """
            ),
            {"limit": limit},
        ).all()
        return [_row_to_dict(r) for r in rows]

    def history(self, verdict: str | None = None, agent: str | None = None, search: str | None = None) -> list[dict[str, Any]]:
        conditions = ["1=1"]
        params: dict[str, Any] = {}
        if verdict and verdict != "All":
            conditions.append("vr.final_verdict = :verdict")
            params["verdict"] = verdict
        if agent and agent != "All":
            conditions.append("vr.detected_agent_code = :agent")
            params["agent"] = agent
        if search:
            conditions.append("(vr.id ILIKE :search OR rec.record_title ILIKE :search OR rec.external_reference ILIKE :search)")
            params["search"] = f"%{search}%"
        sql = f"""
            SELECT vr.id AS run_id, vr.completed_at AS timestamp, rec.record_title AS record,
                   vr.detected_agent_code, vr.final_verdict AS verdict, vr.final_tag AS tag,
                   vr.final_confidence AS confidence, au.email AS initiated_by
            FROM validation_run vr
            JOIN validation_record rec ON rec.id = vr.record_id
            JOIN application_user au ON au.id = vr.initiated_by_user_id
            WHERE {' AND '.join(conditions)}
            ORDER BY vr.started_at DESC
            LIMIT 200
        """
        rows = self.conn.execute(text(sql), params).all()
        return [_row_to_dict(r) for r in rows]

    def run_detail(self, run_id: str) -> dict[str, Any]:
        run = self.conn.execute(
            text(
                """
                SELECT vr.*, rec.external_reference, rec.record_title, rec.source_system, rec.record_type, au.email AS initiated_by
                FROM validation_run vr
                JOIN validation_record rec ON rec.id = vr.record_id
                JOIN application_user au ON au.id = vr.initiated_by_user_id
                WHERE vr.id = :run_id
                """
            ),
            {"run_id": run_id},
        ).one_or_none()
        if run is None:
            raise ValueError("Validation run not found.")
        rules = self.conn.execute(
            text("SELECT rule_code, rule_name, severity, passed, message, tag, evidence FROM rule_result WHERE run_id = :run_id ORDER BY created_at, rule_code"),
            {"run_id": run_id},
        ).all()
        llm = self.conn.execute(
            text("SELECT model_name, judge_verdict, confidence, reason, findings, prompt_version, created_at FROM llm_judgement WHERE run_id = :run_id ORDER BY created_at DESC LIMIT 1"),
            {"run_id": run_id},
        ).one_or_none()
        audit = self.conn.execute(
            text("SELECT event_type, event_details, created_at FROM audit_event WHERE run_id = :run_id ORDER BY created_at"),
            {"run_id": run_id},
        ).all()
        return {
            "run": _row_to_dict(run),
            "rules": [_row_to_dict(r) for r in rules],
            "llm": _row_to_dict(llm) if llm else None,
            "audit": [_row_to_dict(r) for r in audit],
        }


class ExcelSupervisorRepository:
    def __init__(self, store: ExcelDataStore):
        self.store = store

    def upsert_user(self, user: AppUser) -> AppUser:
        existing = self.store.find_one("application_user", lambda row: row.get("google_subject_id") == user.google_subject_id)
        timestamp = now_iso()
        if existing:
            values = {
                "id": existing["id"],
                "google_subject_id": user.google_subject_id,
                "email": user.email,
                "display_name": user.display_name,
                "profile_image_url": user.profile_image_url,
                "created_at": existing.get("created_at") or timestamp,
                "last_login_at": timestamp,
            }
        else:
            values = {
                "id": user.id,
                "google_subject_id": user.google_subject_id,
                "email": user.email,
                "display_name": user.display_name,
                "profile_image_url": user.profile_image_url,
                "created_at": timestamp,
                "last_login_at": timestamp,
            }
        saved = self.store.upsert("application_user", "google_subject_id", user.google_subject_id, values)
        return AppUser(
            id=str(saved["id"]),
            google_subject_id=str(saved["google_subject_id"]),
            email=str(saved["email"]),
            display_name=str(saved["display_name"]),
            profile_image_url=saved.get("profile_image_url"),
        )

    def add_audit_event(self, run_id: str | None, user_id: str | None, event_type: str, details: dict[str, Any]) -> None:
        self.store.insert(
            "audit_event",
            {
                "id": str(uuid4()),
                "run_id": run_id,
                "user_id": user_id,
                "event_type": event_type,
                "event_details": json_dumps(details),
                "created_at": now_iso(),
            },
        )

    def list_active_records(self) -> list[ValidationRecordSummary]:
        rows = [row for row in self.store.rows("validation_record") if _truthy(row.get("active"))]
        rows.sort(key=lambda row: str(row.get("external_reference") or ""))
        return [
            ValidationRecordSummary(
                id=str(row["id"]),
                external_reference=str(row["external_reference"]),
                record_title=str(row["record_title"]),
                source_system=str(row["source_system"]),
                record_type=str(row["record_type"]),
                expected_agent_code=row.get("expected_agent_code") or None,
            )
            for row in rows
        ]

    def get_record(self, record_id: str, comments: str | None = None) -> NormalizedRecord:
        row = self.store.find_one("validation_record", lambda item: item.get("id") == record_id and _truthy(item.get("active")))
        if row is None:
            raise ValueError("Selected validation record was not found or is inactive.")
        return NormalizedRecord(
            record_id=str(row["id"]),
            external_reference=str(row["external_reference"]),
            source_system=str(row["source_system"]),
            record_type=str(row["record_type"]),
            record_title=str(row["record_title"]),
            payload=json_loads(row.get("payload")),
            metadata=json_loads(row.get("metadata")),
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
                "execution_status": ExecutionStatus.RUNNING.value,
                "started_at": now_iso(),
            },
        )
        self.add_audit_event(run_id, user_id, "validation_started", {"record_id": record_id})
        return run_id

    def update_routing(self, run_id: str, routing: RoutingDecision, user_id: str) -> None:
        self.store.update(
            "validation_run",
            "id",
            run_id,
            {
                "detected_agent_code": routing.detected_agent_code.value,
                "selected_tool_code": routing.selected_tool.value,
                "routing_reason": routing.reason,
                "routing_confidence": routing.confidence,
            },
        )
        self.add_audit_event(run_id, user_id, "routing_completed", routing.model_dump(mode="json"))

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
                    "evidence": json_dumps(result.evidence),
                    "message": result.message,
                    "tag": result.tag,
                    "created_at": now_iso(),
                },
            )
        self.add_audit_event(run_id, user_id, "tool_completed", {"rule_count": len(results)})

    def insert_llm_judgement(self, run_id: str, model_name: str, prompt_version: str, judgement: LlmJudgementResult, user_id: str) -> None:
        self.store.insert(
            "llm_judgement",
            {
                "id": str(uuid4()),
                "run_id": run_id,
                "model_name": model_name,
                "judge_verdict": judgement.verdict.value,
                "confidence": judgement.confidence,
                "reason": judgement.reason,
                "findings": json_dumps([f.model_dump(mode="json") for f in judgement.findings]),
                "raw_response": json_dumps(judgement.raw_response or judgement.model_dump(mode="json")),
                "prompt_version": prompt_version,
                "created_at": now_iso(),
            },
        )
        self.add_audit_event(run_id, user_id, "llm_completed", {"verdict": judgement.verdict.value})

    def complete_run(self, run_id: str, final: FinalSynthesis, user_id: str) -> None:
        self.store.update(
            "validation_run",
            "id",
            run_id,
            {
                "execution_status": ExecutionStatus.COMPLETED.value,
                "final_verdict": final.verdict.value,
                "final_reason": final.reason,
                "final_tag": final.primary_tag,
                "final_confidence": final.confidence,
                "completed_at": now_iso(),
                "error_message": None,
            },
        )
        self.add_audit_event(run_id, user_id, "validation_completed", final.model_dump(mode="json"))

    def mark_run_error(self, run_id: str, user_id: str, message: str) -> None:
        self.store.update(
            "validation_run",
            "id",
            run_id,
            {
                "execution_status": ExecutionStatus.ERROR.value,
                "completed_at": now_iso(),
                "error_message": message[:1000],
            },
        )
        self.add_audit_event(run_id, user_id, "validation_error", {"message": message[:1000]})

    def dashboard_metrics(self) -> dict[str, Any]:
        runs = self.store.rows("validation_run")
        completed = [row for row in runs if row.get("execution_status") == ExecutionStatus.COMPLETED.value]
        pass_count = sum(1 for row in completed if row.get("final_verdict") == "PASS")
        fail_count = sum(1 for row in completed if row.get("final_verdict") == "FAIL")
        warning_count = sum(1 for row in completed if row.get("final_verdict") == "WARNING")
        total = len(completed)
        agents_supported = sum(1 for row in self.store.rows("agent_registry") if _truthy(row.get("enabled")))
        return {
            "total_validations": total,
            "pass_count": pass_count,
            "fail_count": fail_count,
            "warning_count": warning_count,
            "pass_rate": round((pass_count / total) * 100, 1) if total else 0.0,
            "fail_rate": round((fail_count / total) * 100, 1) if total else 0.0,
            "agents_supported": agents_supported,
        }

    def recent_activity(self, limit: int = 15) -> list[dict[str, Any]]:
        records = {row.get("id"): row for row in self.store.rows("validation_record")}
        rows = []
        for run in self.store.rows("validation_run"):
            if run.get("execution_status") != ExecutionStatus.COMPLETED.value:
                continue
            rec = records.get(run.get("record_id"), {})
            rows.append(
                {
                    "time": run.get("completed_at"),
                    "detected_agent_code": run.get("detected_agent_code"),
                    "record": rec.get("record_title"),
                    "verdict": run.get("final_verdict"),
                    "tag": run.get("final_tag"),
                    "confidence": _as_float(run.get("final_confidence")),
                }
            )
        rows.sort(key=lambda row: str(row.get("time") or ""), reverse=True)
        return rows[:limit]

    def history(self, verdict: str | None = None, agent: str | None = None, search: str | None = None) -> list[dict[str, Any]]:
        records = {row.get("id"): row for row in self.store.rows("validation_record")}
        users = {row.get("id"): row for row in self.store.rows("application_user")}
        term = (search or "").lower().strip()
        rows = []
        for run in self.store.rows("validation_run"):
            rec = records.get(run.get("record_id"), {})
            if verdict and verdict != "All" and run.get("final_verdict") != verdict:
                continue
            if agent and agent != "All" and run.get("detected_agent_code") != agent:
                continue
            searchable = " ".join(str(x or "") for x in [run.get("id"), rec.get("record_title"), rec.get("external_reference")]).lower()
            if term and term not in searchable:
                continue
            user = users.get(run.get("initiated_by_user_id"), {})
            rows.append(
                {
                    "run_id": run.get("id"),
                    "timestamp": run.get("completed_at"),
                    "record": rec.get("record_title"),
                    "detected_agent_code": run.get("detected_agent_code"),
                    "verdict": run.get("final_verdict"),
                    "tag": run.get("final_tag"),
                    "confidence": _as_float(run.get("final_confidence")),
                    "initiated_by": user.get("email"),
                }
            )
        rows.sort(key=lambda row: str(row.get("timestamp") or ""), reverse=True)
        return rows[:200]

    # ── Analytics / Insights methods ────────────────────────────────────────

    def agent_health_metrics(self) -> dict[str, Any]:
        """Aggregate pass/warn/fail counts per detected agent from all completed runs."""
        from collections import defaultdict
        bucket: dict[str, dict[str, Any]] = defaultdict(
            lambda: {"total": 0, "pass_count": 0, "fail_count": 0, "warning_count": 0, "last_run": None}
        )
        for run in self.store.rows("validation_run"):
            if str(run.get("execution_status") or "") != "COMPLETED":
                continue
            code = str(run.get("detected_agent_code") or "").strip()
            if not code:
                continue
            bucket[code]["total"] += 1
            verdict = str(run.get("final_verdict") or "")
            if verdict == "PASS":
                bucket[code]["pass_count"] += 1
            elif verdict == "FAIL":
                bucket[code]["fail_count"] += 1
            elif verdict == "WARNING":
                bucket[code]["warning_count"] += 1
            completed = str(run.get("completed_at") or "")
            last = str(bucket[code]["last_run"] or "")
            if completed and (not last or completed > last):
                bucket[code]["last_run"] = completed
        return dict(bucket)

    def rule_failure_stats(self) -> list[dict[str, Any]]:
        """Return per-rule failure frequency with agent attribution."""
        from collections import defaultdict
        run_agent: dict[str, str] = {
            str(r.get("id") or ""): str(r.get("detected_agent_code") or "")
            for r in self.store.rows("validation_run")
        }
        stats: dict[str, dict[str, Any]] = defaultdict(
            lambda: {"rule_code": "", "rule_name": "", "total": 0, "fail_count": 0, "tag": "", "agent_code": ""}
        )
        for rule in self.store.rows("rule_result"):
            key = str(rule.get("rule_code") or "")
            if not key:
                continue
            stats[key]["rule_code"] = key
            stats[key]["rule_name"] = str(rule.get("rule_name") or "")
            stats[key]["tag"] = str(rule.get("tag") or "")
            stats[key]["total"] += 1
            if not _truthy(rule.get("passed")):
                stats[key]["fail_count"] += 1
            run_id = str(rule.get("run_id") or "")
            agent = run_agent.get(run_id, "")
            if agent:
                stats[key]["agent_code"] = agent
        result = list(stats.values())
        for r in result:
            r["fail_rate"] = round(r["fail_count"] / r["total"] * 100, 1) if r["total"] else 0.0
        return sorted(result, key=lambda x: x["fail_count"], reverse=True)

    def recent_runs_for_drift(self, limit: int = 40) -> list[dict[str, Any]]:
        """Most-recent validation runs for drift analysis (newest first)."""
        runs = list(self.store.rows("validation_run"))
        runs.sort(key=lambda r: str(r.get("completed_at") or r.get("started_at") or ""), reverse=True)
        return runs[:limit]

    def trend_data(self, days: int = 14) -> list[dict[str, Any]]:
        """Daily aggregated validation counts for the trend chart."""
        from collections import defaultdict
        daily: dict[str, dict[str, Any]] = defaultdict(
            lambda: {"pass_count": 0, "warning_count": 0, "fail_count": 0, "total": 0, "confidence_sum": 0.0}
        )
        for run in self.store.rows("validation_run"):
            if str(run.get("execution_status") or "") != "COMPLETED":
                continue
            ts = str(run.get("completed_at") or "")
            if not ts:
                continue
            date = ts[:10]
            daily[date]["total"] += 1
            verdict = str(run.get("final_verdict") or "")
            if verdict == "PASS":
                daily[date]["pass_count"] += 1
            elif verdict == "WARNING":
                daily[date]["warning_count"] += 1
            elif verdict == "FAIL":
                daily[date]["fail_count"] += 1
            conf = _as_float(run.get("final_confidence"))
            if conf is not None:
                daily[date]["confidence_sum"] += conf
        result = []
        for date, data in sorted(daily.items()):
            avg_conf = data["confidence_sum"] / data["total"] if data["total"] else 0.0
            result.append({
                "date": date,
                "pass_count": data["pass_count"],
                "warning_count": data["warning_count"],
                "fail_count": data["fail_count"],
                "total": data["total"],
                "avg_confidence": round(avg_conf, 3),
            })
        return result[-days:]

    def verdict_distribution(self) -> dict[str, int]:
        """Overall PASS/WARNING/FAIL/ERROR counts across all completed runs."""
        dist = {"PASS": 0, "WARNING": 0, "FAIL": 0}
        for run in self.store.rows("validation_run"):
            verdict = str(run.get("final_verdict") or "")
            if verdict in dist:
                dist[verdict] += 1
        return dist

    # ────────────────────────────────────────────────────────────────────────

    def run_detail(self, run_id: str) -> dict[str, Any]:
        run = self.store.find_one("validation_run", lambda row: row.get("id") == run_id)
        if run is None:
            raise ValueError("Validation run not found.")
        record = self.store.find_one("validation_record", lambda row: row.get("id") == run.get("record_id")) or {}
        user = self.store.find_one("application_user", lambda row: row.get("id") == run.get("initiated_by_user_id")) or {}
        rules = [row for row in self.store.rows("rule_result") if row.get("run_id") == run_id]
        rules.sort(key=lambda row: (str(row.get("created_at") or ""), str(row.get("rule_code") or "")))
        llm_rows = [row for row in self.store.rows("llm_judgement") if row.get("run_id") == run_id]
        llm_rows.sort(key=lambda row: str(row.get("created_at") or ""), reverse=True)
        audit = [row for row in self.store.rows("audit_event") if row.get("run_id") == run_id]
        audit.sort(key=lambda row: str(row.get("created_at") or ""))
        run_detail = dict(run)
        run_detail.update(
            {
                "external_reference": record.get("external_reference"),
                "record_title": record.get("record_title"),
                "source_system": record.get("source_system"),
                "record_type": record.get("record_type"),
                "initiated_by": user.get("email"),
            }
        )
        rule_detail = [
            {
                "rule_code": row.get("rule_code"),
                "rule_name": row.get("rule_name"),
                "severity": row.get("severity"),
                "passed": _truthy(row.get("passed")),
                "message": row.get("message"),
                "tag": row.get("tag"),
                "evidence": json_loads(row.get("evidence")),
            }
            for row in rules
        ]
        llm = llm_rows[0] if llm_rows else None
        llm_detail = None
        if llm:
            llm_detail = {
                "model_name": llm.get("model_name"),
                "judge_verdict": llm.get("judge_verdict"),
                "confidence": _as_float(llm.get("confidence")),
                "reason": llm.get("reason"),
                "findings": json_loads(llm.get("findings"), []),
                "prompt_version": llm.get("prompt_version"),
                "created_at": llm.get("created_at"),
            }
        audit_detail = [
            {
                "event_type": row.get("event_type"),
                "event_details": json_loads(row.get("event_details")),
                "created_at": row.get("created_at"),
            }
            for row in audit
        ]
        return {"run": run_detail, "rules": rule_detail, "llm": llm_detail, "audit": audit_detail}


class SupervisorRepository:
    """Repository facade. Keeps the rest of the app unchanged across storage backends."""

    def __init__(self, conn: Connection | ExcelDataStore):
        # Duck-typed check in addition to isinstance: Streamlit hot-reloading can
        # produce a second ExcelDataStore class identity, which would make a strict
        # isinstance check silently fail and wrongly route to the SQL backend.
        is_excel = isinstance(conn, ExcelDataStore) or type(conn).__name__ == "ExcelDataStore"
        if is_excel:
            self._impl: SqlSupervisorRepository | ExcelSupervisorRepository = ExcelSupervisorRepository(conn)
        else:
            self._impl = SqlSupervisorRepository(conn)

    def __getattr__(self, name: str) -> Any:
        return getattr(self._impl, name)