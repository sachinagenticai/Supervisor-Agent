from __future__ import annotations

import logging
from datetime import datetime, timezone
from typing import Callable

from supervisor_control_tower.config import Settings
from supervisor_control_tower.db import Database
from supervisor_control_tower.judge import LlmJudge
from supervisor_control_tower.llm_client import LlmJsonClient
from supervisor_control_tower.models import AppUser, ValidationRunResult
from supervisor_control_tower.orchestrator import SupervisorOrchestrator
from supervisor_control_tower.repositories import SupervisorRepository
from supervisor_control_tower.synthesizer import FinalSynthesizer
from supervisor_control_tower.tools import build_tool_registry

logger = logging.getLogger(__name__)


class ValidationService:
    def __init__(self, settings: Settings, database: Database):
        self.settings = settings
        self.database = database
        self.llm_client = LlmJsonClient(settings)
        self.orchestrator = SupervisorOrchestrator(self.llm_client)
        self.tool_registry = build_tool_registry()
        self.judge = LlmJudge(self.llm_client)
        self.synthesizer = FinalSynthesizer(settings)

    def run_validation(self, record_id: str, comments: str | None, user: AppUser) -> ValidationRunResult:
        error: Exception | None = None
        with self.database.transaction() as conn:
            repo = SupervisorRepository(conn)
            db_user = repo.upsert_user(user)
            run_id = repo.create_validation_run(record_id, db_user.id, comments)
            started_at = datetime.now(timezone.utc)
            try:
                record = repo.get_record(record_id, comments)
                routing = self.orchestrator.route(record)
                repo.update_routing(run_id, routing, db_user.id)
                tool = self.tool_registry.get(routing.selected_tool)
                tool_result = tool.run(record)
                repo.insert_rule_results(run_id, tool_result.rule_results, db_user.id)
                judgement = self.judge.evaluate(record, tool_result)
                repo.insert_llm_judgement(run_id, self.judge.model_name, self.judge.prompt_version, judgement, db_user.id)
                final = self.synthesizer.synthesize(tool_result, judgement)
                repo.complete_run(run_id, final, db_user.id)
                return ValidationRunResult(
                    run_id=run_id,
                    record=record,
                    routing=routing,
                    tool_result=tool_result,
                    llm_judgement=judgement,
                    final=final,
                    started_at=started_at,
                    initiated_by=db_user.email,
                )
            except Exception as exc:
                logger.exception("Validation failed for run %s", run_id)
                repo.mark_run_error(run_id, db_user.id, str(exc))
                error = exc
        if error is not None:
            raise error
        raise RuntimeError("Validation ended without a result.")
