from __future__ import annotations

import json
from pathlib import Path
from threading import RLock
from typing import Iterable

from pydantic import BaseModel, Field, ValidationError

from supervisor_control_tower.models import AgentDefinition, NormalizedRecord, RoutingCandidate


class AgentConfigurationError(RuntimeError):
    pass


class AgentLibraryDocument(BaseModel):
    schema_version: str = "1.0"
    agents: list[AgentDefinition] = Field(default_factory=list)


class AgentRegistry:
    """Versioned internal agent library loaded from configuration."""

    def __init__(self, agents: Iterable[AgentDefinition]):
        self._lock = RLock()
        self._agents: dict[str, AgentDefinition] = {}
        self._tools: dict[str, str] = {}
        for agent in agents:
            self.register(agent)
        if not self._agents:
            raise AgentConfigurationError("At least one enabled agent definition is required.")

    @classmethod
    def from_json(cls, path: str | Path) -> "AgentRegistry":
        config_path = Path(path)
        if not config_path.exists():
            raise AgentConfigurationError(f"Agent configuration not found: {config_path}")
        try:
            raw = json.loads(config_path.read_text(encoding="utf-8"))
            document = AgentLibraryDocument.model_validate(raw)
        except (OSError, json.JSONDecodeError, ValidationError) as exc:
            raise AgentConfigurationError(f"Invalid agent configuration: {exc}") from exc
        return cls(agent for agent in document.agents if agent.enabled)

    def register(self, agent: AgentDefinition) -> None:
        with self._lock:
            if agent.code in self._agents:
                raise AgentConfigurationError(f"Duplicate agent code: {agent.code}")
            if agent.tool_code in self._tools:
                raise AgentConfigurationError(
                    f"Tool code {agent.tool_code} is already assigned to {self._tools[agent.tool_code]}"
                )
            self._agents[agent.code] = agent
            self._tools[agent.tool_code] = agent.code

    def get(self, agent_code: str) -> AgentDefinition:
        try:
            return self._agents[str(agent_code)]
        except KeyError as exc:
            raise AgentConfigurationError(f"Unknown or disabled agent: {agent_code}") from exc

    def get_by_tool(self, tool_code: str) -> AgentDefinition:
        agent_code = self._tools.get(str(tool_code))
        if not agent_code:
            raise AgentConfigurationError(f"Unknown tool code: {tool_code}")
        return self.get(agent_code)

    def list_enabled(self) -> list[AgentDefinition]:
        return sorted(self._agents.values(), key=lambda agent: agent.name.lower())

    def allowed_agent_codes(self) -> set[str]:
        return set(self._agents)

    def rank(self, record: NormalizedRecord) -> list[RoutingCandidate]:
        source = record.source_system.strip().lower()
        record_type = record.record_type.strip().lower()
        payload_keys = _flatten_keys(record.payload)
        metadata_keys = _flatten_keys(record.metadata)
        available_keys = payload_keys | metadata_keys

        candidates: list[RoutingCandidate] = []
        for agent in self._agents.values():
            score = 0.0
            signals: list[str] = []

            sources = {item.lower() for item in agent.source_systems}
            record_types = {item.lower() for item in agent.record_types}
            hints = {item.lower() for item in agent.routing_key_hints}

            source_matched = bool(source and source in sources)
            type_matched = bool(record_type and record_type in record_types)
            if source_matched:
                score += 0.42
                signals.append(f"source_system={record.source_system}")
            if type_matched:
                score += 0.33
                signals.append(f"record_type={record.record_type}")

            matched_hints = sorted(hints & available_keys)
            if hints and matched_hints:
                key_ratio = min(1.0, len(matched_hints) / max(3, min(len(hints), 5)))
                key_weight = 0.23 if (source_matched or type_matched) else 0.78
                score += key_weight * key_ratio
                signals.append(f"payload keys: {', '.join(matched_hints[:5])}")

            expected = str(record.metadata.get("expected_agent_code") or "").upper()
            if expected and expected == agent.code:
                score += 0.02
                signals.append("metadata expectation")

            candidates.append(
                RoutingCandidate(
                    agent_code=agent.code,
                    tool_code=agent.tool_code,
                    score=round(min(score, 1.0), 4),
                    matched_signals=signals,
                )
            )

        return sorted(candidates, key=lambda candidate: candidate.score, reverse=True)


def _flatten_keys(value: object, prefix: str = "", max_depth: int = 4) -> set[str]:
    keys: set[str] = set()
    if max_depth < 0:
        return keys
    if isinstance(value, dict):
        for key, child in value.items():
            key_text = str(key).lower()
            keys.add(key_text)
            if prefix:
                keys.add(f"{prefix}.{key_text}")
            keys |= _flatten_keys(child, key_text, max_depth - 1)
    elif isinstance(value, list):
        for child in value[:10]:
            keys |= _flatten_keys(child, prefix, max_depth - 1)
    return keys
