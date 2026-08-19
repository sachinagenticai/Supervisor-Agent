from __future__ import annotations

import json
import logging
from datetime import datetime, timezone

from supervisor_control_tower.agent_registry import AgentRegistry
from supervisor_control_tower.config import Settings
from supervisor_control_tower.connectors import ConnectorRegistry, ExcelRecordConnector
from supervisor_control_tower.context import BusinessContextProvider
from supervisor_control_tower.db import Database
from supervisor_control_tower.governance import GovernanceEngine
from supervisor_control_tower.judge import LlmJudge
from supervisor_control_tower.llm_client import LlmJsonClient
from supervisor_control_tower.memory import StructuredMemoryProvider
from supervisor_control_tower.models import AppUser, ValidationRunResult
from supervisor_control_tower.orchestrator import SupervisorOrchestrator
from supervisor_control_tower.repositories import SupervisorRepository
from supervisor_control_tower.rules.registry import RuleRegistry
from supervisor_control_tower.synthesizer import FinalSynthesizer
from supervisor_control_tower.tools import build_tool_registry

logger = logging.getLogger(__name__)


class ValidationService:
    """Coordinates a complete assurance evaluation.

    Persistence operations use short Excel transactions. Network-bound LLM work
    is deliberately performed outside the file lock so a slow model response does
    not block dashboard reads or unrelated users in a controlled single-instance
    deployment.
    """

    def __init__(self, settings: Settings, database: Database):
        self.settings = settings
        self.database = database
        self.agent_registry = AgentRegistry.from_json(settings.resolve_path(settings.agent_config_path))
        self.rule_registry = RuleRegistry.from_json(
            self.agent_registry,
            settings.resolve_path(settings.rule_config_path),
        )
        self.llm_client = LlmJsonClient(settings)
        self.orchestrator = SupervisorOrchestrator(self.llm_client, self.agent_registry)
        self.tool_registry = build_tool_registry(self.agent_registry, self.rule_registry)
        self.judge = LlmJudge(self.llm_client, self.agent_registry)
        self.synthesizer = FinalSynthesizer(settings)
        self.context_provider = BusinessContextProvider(
            settings.resolve_path(settings.business_context_path)
        )
        self.memory_provider = StructuredMemoryProvider(settings.memory_reference_limit)
        self.governance_engine = GovernanceEngine()

    def run_validation(
        self,
        record_id: str,
        comments: str | None,
        user: AppUser,
    ) -> ValidationRunResult:
        run_id: str | None = None
        db_user: AppUser | None = None
        started_at = datetime.now(timezone.utc)
        try:
            # Persist a RUNNING audit record before any model or rule execution.
            with self.database.transaction() as connection:
                repository = SupervisorRepository(connection)
                db_user = repository.upsert_user(user)
                connector = ConnectorRegistry([ExcelRecordConnector(repository)]).get("excel_records")
                record = connector.get_record(record_id, comments)
                run_id = repository.create_validation_run(record_id, db_user.id, comments)

            payload_size = len(
                json.dumps(
                    {"payload": record.payload, "metadata": record.metadata},
                    default=str,
                    ensure_ascii=False,
                )
            )
            if payload_size > self.settings.max_payload_characters:
                raise ValueError(
                    f"Record payload size {payload_size:,} characters exceeds the configured limit "
                    f"of {self.settings.max_payload_characters:,}."
                )

            routing = self.orchestrator.route(record)
            definition = self.agent_registry.get(routing.detected_agent_code)
            context = self.context_provider.build(record, definition)

            # Memory and governance are read-only. They use a short lock and do not
            # save the workbook. Routing is persisted with the final result to avoid
            # repeated full-workbook writes.
            with self.database.transaction() as connection:
                repository = SupervisorRepository(connection)
                memory = self.memory_provider.retrieve(repository, record, definition.code)
                governance = self.governance_engine.assess(record, repository)

            tool = self.tool_registry.get(routing.selected_tool)
            tool_result = tool.run(record)
            judgement = self.judge.evaluate(
                record,
                tool_result,
                definition=definition,
                context=context,
                memory=memory,
            )
            final = self.synthesizer.synthesize(
                tool_result,
                judgement,
                routing_confidence=routing.confidence,
                agent_definition=definition,
                governance=governance,
            )

            # Persist the complete immutable evaluation result atomically.
            with self.database.transaction() as connection:
                repository = SupervisorRepository(connection)
                repository.update_routing(run_id, routing, db_user.id)
                repository.insert_rule_results(run_id, tool_result.rule_results, db_user.id)
                repository.insert_llm_judgement(
                    run_id,
                    self.judge.model_name,
                    self.judge.prompt_version,
                    judgement,
                    db_user.id,
                )
                repository.complete_run(
                    run_id,
                    final,
                    db_user.id,
                    context=context,
                    memory=memory,
                )

            return ValidationRunResult(
                run_id=run_id,
                record=record,
                routing=routing,
                tool_result=tool_result,
                llm_judgement=judgement,
                final=final,
                context=context,
                memory=memory,
                started_at=started_at,
                initiated_by=db_user.email,
            )
        except Exception as exc:
            logger.exception("Validation failed for run %s", run_id or "not-created")
            if run_id and db_user:
                try:
                    with self.database.transaction() as connection:
                        SupervisorRepository(connection).mark_run_error(
                            run_id, db_user.id, str(exc)
                        )
                except Exception:
                    logger.exception("Unable to persist failure state for run %s", run_id)
            raise

