from __future__ import annotations

from collections.abc import Iterable

from supervisor_control_tower.models import AgentDefinition
from supervisor_control_tower.rules.engine import Rule


def humanize_identifier(value: str) -> str:
    return str(value).replace("_", " ").replace("-", " ").strip().title()


def agent_search_text(agent: AgentDefinition) -> str:
    values: list[str] = [
        agent.code,
        agent.name,
        agent.description,
        agent.owner,
        agent.lifecycle_status,
        agent.rule_pack_id,
        agent.tool_code,
        agent.glossary.business_purpose,
    ]
    values.extend(agent.capabilities)
    values.extend(agent.supported_task_types)
    values.extend(agent.source_systems)
    values.extend(agent.record_types)
    values.extend(agent.required_evidence)
    values.extend(agent.glossary.business_outcomes)
    values.extend(agent.glossary.example_use_cases)
    return " ".join(values).lower()


def filter_agents(
    agents: Iterable[AgentDefinition],
    search_text: str = "",
    lifecycle_statuses: Iterable[str] | None = None,
) -> list[AgentDefinition]:
    query = search_text.strip().lower()
    allowed_statuses = {str(item) for item in (lifecycle_statuses or [])}
    return [
        agent
        for agent in agents
        if (not query or query in agent_search_text(agent))
        and (not allowed_statuses or agent.lifecycle_status in allowed_statuses)
    ]


def agent_summary_row(agent: AgentDefinition, rules: list[Rule]) -> dict[str, object]:
    return {
        "Agent": agent.name,
        "Purpose": agent.description,
        "Owner": agent.owner,
        "Stage": agent.lifecycle_status,
        "Version": agent.version,
        "Capabilities": len(agent.capabilities),
        "Controls": len(rules),
        "Sources": ", ".join(humanize_identifier(item) for item in agent.source_systems),
    }
