from __future__ import annotations

from abc import ABC

from supervisor_control_tower.data_science.record_profile import RecordProfiler
from supervisor_control_tower.models import AgentDefinition, NormalizedRecord, ToolResult
from supervisor_control_tower.rules.engine import Rule, RuleEngine


class ToolNode(ABC):
    tool_code: str
    agent_code: str
    summary: str

    def __init__(self, rules: list[Rule]):
        self.rule_engine = RuleEngine(rules)
        self.record_profiler = RecordProfiler()

    @property
    def rules(self) -> list[Rule]:
        return self.rule_engine.rules

    def run(self, record: NormalizedRecord) -> ToolResult:
        rule_results = self.rule_engine.run(record, str(self.tool_code))
        failed = [result for result in rule_results if not result.passed]
        profile = self.record_profiler.profile(record.payload, record.metadata)
        return ToolResult(
            tool_code=str(self.tool_code),
            agent_code=str(self.agent_code),
            execution_success=True,
            summary=self.summary,
            rule_results=rule_results,
            derived_metrics={
                "rules_total": len(rule_results),
                "rules_passed": len(rule_results) - len(failed),
                "rules_failed": len(failed),
                "record_profile": profile.to_dict(),
            },
            warnings=[
                result.message
                for result in failed
                if result.severity.value in {"CRITICAL", "HIGH", "MEDIUM"}
            ],
        )


class GenericValidationTool(ToolNode):
    def __init__(self, definition: AgentDefinition, rules: list[Rule]):
        self.tool_code = definition.tool_code
        self.agent_code = definition.code
        self.summary = f"{definition.name} output was evaluated using the configured enterprise rule pack."
        self.definition = definition
        super().__init__(rules)


class ToolRegistry:
    def __init__(self, tools: list[ToolNode]):
        self._tools = {str(tool.tool_code): tool for tool in tools}

    def get(self, tool_code: str) -> ToolNode:
        normalized = str(tool_code)
        if normalized not in self._tools:
            raise ValueError(f"Unsupported tool selected: {tool_code}")
        return self._tools[normalized]

    def list_codes(self) -> list[str]:
        return sorted(self._tools)
