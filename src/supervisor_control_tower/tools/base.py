from __future__ import annotations

from abc import ABC, abstractmethod

from supervisor_control_tower.data_science.record_profile import RecordProfiler
from supervisor_control_tower.models import AgentCode, NormalizedRecord, ToolCode, ToolResult
from supervisor_control_tower.rules.engine import Rule, RuleEngine


class ToolNode(ABC):
    tool_code: ToolCode
    agent_code: AgentCode
    summary: str

    def __init__(self, rules: list[Rule]):
        self.rule_engine = RuleEngine(rules)
        self.record_profiler = RecordProfiler()

    def run(self, record: NormalizedRecord) -> ToolResult:
        rule_results = self.rule_engine.run(record, self.tool_code)
        failed = [r for r in rule_results if not r.passed]
        profile = self.record_profiler.profile(record.payload, record.metadata)
        return ToolResult(
            tool_code=self.tool_code,
            agent_code=self.agent_code,
            execution_success=True,
            summary=self.summary,
            rule_results=rule_results,
            derived_metrics={
                "rules_total": len(rule_results),
                "rules_passed": len(rule_results) - len(failed),
                "rules_failed": len(failed),
                "record_profile": profile.to_dict(),
            },
            warnings=[r.message for r in failed if r.severity.value in {"HIGH", "MEDIUM", "LOW"}],
        )


class ToolRegistry:
    def __init__(self, tools: list[ToolNode]):
        self._tools = {tool.tool_code: tool for tool in tools}

    def get(self, tool_code: ToolCode) -> ToolNode:
        if tool_code not in self._tools:
            raise ValueError(f"Unsupported tool selected: {tool_code}")
        return self._tools[tool_code]
