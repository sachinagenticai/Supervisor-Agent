from __future__ import annotations

import json
from pathlib import Path
from typing import Any, Callable

from supervisor_control_tower.agent_registry import AgentRegistry
from supervisor_control_tower.models import Severity
from supervisor_control_tower.rules.engine import Rule, build_config_evaluator, no_prompt_injection


class RuleConfigurationError(RuntimeError):
    pass


class RuleRegistry:
    """Resolves both built-in Python rule packs and configuration-only packs."""

    def __init__(self, agent_registry: AgentRegistry, configurable_packs: dict[str, list[dict[str, Any]]] | None = None):
        self.agent_registry = agent_registry
        self._factories: dict[str, Callable[[], list[Rule]]] = {}
        self._configured = configurable_packs or {}
        self._register_builtin_factories()

    @classmethod
    def from_json(cls, agent_registry: AgentRegistry, path: str | Path) -> "RuleRegistry":
        config_path = Path(path)
        if not config_path.exists():
            raise RuleConfigurationError(f"Rule configuration not found: {config_path}")
        try:
            raw = json.loads(config_path.read_text(encoding="utf-8"))
            packs = raw.get("rule_packs", {})
            if not isinstance(packs, dict):
                raise ValueError("rule_packs must be an object")
        except (OSError, json.JSONDecodeError, ValueError) as exc:
            raise RuleConfigurationError(f"Invalid rule configuration: {exc}") from exc
        return cls(agent_registry, packs)

    def _register_builtin_factories(self) -> None:
        from supervisor_control_tower.tools.finops import build_finops_rules
        from supervisor_control_tower.tools.infrastructure import build_infrastructure_rules
        from supervisor_control_tower.tools.pipeline import build_pipeline_rules
        from supervisor_control_tower.tools.project_management import build_project_rules

        self._factories.update(
            {
                "pipeline_rules": build_pipeline_rules,
                "infrastructure_rules": build_infrastructure_rules,
                "finops_rules": build_finops_rules,
                "project_management_rules": build_project_rules,
            }
        )

    def get_rules(self, rule_pack_id: str, tool_code: str) -> list[Rule]:
        if rule_pack_id in self._factories:
            rules = self._factories[rule_pack_id]()
        elif rule_pack_id in self._configured:
            rules = [self._build_rule(item, tool_code) for item in self._configured[rule_pack_id]]
        else:
            raise RuleConfigurationError(f"Unknown rule pack: {rule_pack_id}")

        # A common prompt-injection control applies to every registered agent.
        common_rule = Rule(
            code="COMMON-001",
            name="No prompt injection pattern",
            description="Agent output must not attempt to override the supervisor or reveal protected instructions.",
            severity=Severity.CRITICAL,
            tool_code=tool_code,
            evaluator=no_prompt_injection,
            failure_message="Potential prompt-injection content was detected.",
            tag="PROMPT_INJECTION",
            mandatory=True,
        )
        if not any(rule.code == common_rule.code for rule in rules):
            rules.append(common_rule)
        return rules

    @staticmethod
    def _build_rule(item: dict[str, Any], tool_code: str) -> Rule:
        try:
            return Rule(
                code=str(item["code"]),
                name=str(item["name"]),
                description=str(item.get("description", "")),
                severity=Severity(str(item["severity"]).upper()),
                tool_code=tool_code,
                evaluator=build_config_evaluator(item),
                failure_message=str(item["failure_message"]),
                tag=str(item["tag"]),
                mandatory=bool(item.get("mandatory", False)),
            )
        except (KeyError, ValueError, TypeError) as exc:
            raise RuleConfigurationError(f"Invalid configured rule {item.get('code', '<unknown>')}: {exc}") from exc
