from __future__ import annotations

from supervisor_control_tower.agent_registry import AgentRegistry
from supervisor_control_tower.rules.registry import RuleRegistry
from supervisor_control_tower.tools.base import GenericValidationTool, ToolRegistry
from supervisor_control_tower.tools.finops import FinOpsOptimizationTool
from supervisor_control_tower.tools.infrastructure import InfrastructureProvisioningTool
from supervisor_control_tower.tools.pipeline import PipelineTroubleshootingTool
from supervisor_control_tower.tools.project_management import ProjectManagementTool


_BUILTIN_PLUGINS = {
    "pipeline": PipelineTroubleshootingTool,
    "infrastructure": InfrastructureProvisioningTool,
    "finops": FinOpsOptimizationTool,
    "project_management": ProjectManagementTool,
}


def build_tool_registry(
    agent_registry: AgentRegistry | None = None,
    rule_registry: RuleRegistry | None = None,
) -> ToolRegistry:
    # Default loading is configuration-driven so direct callers see every
    # enabled agent, including agents with no custom Python plugin.
    if agent_registry is None:
        root = __import__("pathlib").Path(__file__).resolve().parents[3]
        agent_registry = AgentRegistry.from_json(root / "config" / "agents.json")
    if rule_registry is None:
        root = __import__("pathlib").Path(__file__).resolve().parents[3]
        rule_registry = RuleRegistry.from_json(agent_registry, root / "config" / "rule_packs.json")

    tools = []
    for definition in agent_registry.list_enabled():
        if definition.plugin in _BUILTIN_PLUGINS:
            tool = _BUILTIN_PLUGINS[definition.plugin]()
            # Validate that the config and plugin contract agree.
            if str(tool.tool_code) != definition.tool_code or str(tool.agent_code) != definition.code:
                raise ValueError(
                    f"Agent profile {definition.code} does not match plugin {definition.plugin}: "
                    f"expected ({definition.tool_code}, {definition.code}), "
                    f"plugin exposes ({tool.tool_code}, {tool.agent_code})"
                )
            # Add the common enterprise rules resolved by the registry.
            configured_rules = rule_registry.get_rules(definition.rule_pack_id, definition.tool_code)
            existing_codes = {rule.code for rule in tool.rule_engine.rules}
            tool.rule_engine.rules.extend(rule for rule in configured_rules if rule.code not in existing_codes)
            tools.append(tool)
        else:
            tools.append(
                GenericValidationTool(
                    definition,
                    rule_registry.get_rules(definition.rule_pack_id, definition.tool_code),
                )
            )
    return ToolRegistry(tools)


__all__ = ["build_tool_registry", "ToolRegistry", "GenericValidationTool"]
