from __future__ import annotations

import json
from pathlib import Path
from typing import Any

from supervisor_control_tower.models import AgentDefinition, ContextSnapshot, NormalizedRecord


class BusinessContextProvider:
    def __init__(self, path: str | Path):
        self.path = Path(path)
        self._document = self._load()

    def _load(self) -> dict[str, Any]:
        if not self.path.exists():
            return {"global_policies": [], "agent_context": {}}
        try:
            data = json.loads(self.path.read_text(encoding="utf-8"))
        except (OSError, json.JSONDecodeError) as exc:
            raise ValueError(f"Invalid business context configuration: {exc}") from exc
        return data if isinstance(data, dict) else {"global_policies": [], "agent_context": {}}

    def build(self, record: NormalizedRecord, definition: AgentDefinition) -> ContextSnapshot:
        global_policies = [str(item) for item in self._document.get("global_policies", [])]
        agent_context_map = self._document.get("agent_context", {})
        agent_context = [str(item) for item in agent_context_map.get(definition.code, [])]
        record_context = {
            "source_system": record.source_system,
            "record_type": record.record_type,
            "owner": record.metadata.get("owner"),
            "business_unit": record.metadata.get("business_unit"),
            "environment": record.metadata.get("environment"),
            "risk_tier": record.metadata.get("risk_tier"),
            "focus_area": record.comments,
        }
        return ContextSnapshot(
            global_policies=global_policies,
            agent_context=agent_context,
            record_context={key: value for key, value in record_context.items() if value not in (None, "")},
        )
