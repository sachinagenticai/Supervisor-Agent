from __future__ import annotations

from pathlib import Path
import json
import sys

ROOT_DIR = Path(__file__).resolve().parents[1]
SRC_DIR = ROOT_DIR / "src"
if str(SRC_DIR) not in sys.path:
    sys.path.insert(0, str(SRC_DIR))

from supervisor_control_tower.agent_registry import AgentRegistry
from supervisor_control_tower.config import get_settings
from supervisor_control_tower.db import Database
from supervisor_control_tower.models import NormalizedRecord
from supervisor_control_tower.orchestrator import SupervisorOrchestrator
from supervisor_control_tower.repositories import SupervisorRepository
from supervisor_control_tower.rules.registry import RuleRegistry
from supervisor_control_tower.tools import build_tool_registry


def main() -> None:
    settings = get_settings()
    workbook = Path(settings.excel_store_path)
    if not workbook.exists():
        raise SystemExit(f"Excel store does not exist: {workbook}")

    agents = AgentRegistry.from_json(settings.resolve_path(settings.agent_config_path))
    rules = RuleRegistry.from_json(agents, settings.resolve_path(settings.rule_config_path))
    tools = build_tool_registry(agents, rules)
    orchestrator = SupervisorOrchestrator(agent_registry=agents)
    database = Database(settings)

    with database.transaction() as connection:
        repository = SupervisorRepository(connection)
        records = repository.list_active_records()
        metrics = repository.dashboard_metrics()
        registered = repository.list_registered_agents()

    failures: list[str] = []
    for summary in records:
        with database.transaction() as connection:
            record = SupervisorRepository(connection).get_record(summary.id)
        decision = orchestrator.route(record)
        try:
            tools.get(decision.selected_tool)
        except ValueError as exc:
            failures.append(f"{summary.external_reference}: {exc}")

    result = {
        "status": "healthy" if not failures else "failed",
        "workbook": str(workbook.resolve()),
        "registered_agents": len([item for item in registered if item.get("enabled")]),
        "configured_agents": len(agents.list_enabled()),
        "active_records": len(records),
        "completed_evaluations": metrics["total_validations"],
        "routing_failures": failures,
        "external_writeback_enabled": settings.external_writeback_enabled,
    }
    print(json.dumps(result, indent=2))
    if failures:
        raise SystemExit(1)


if __name__ == "__main__":
    main()
