from __future__ import annotations

import pytest

from supervisor_control_tower.models import ToolCode
from supervisor_control_tower.tools import build_tool_registry


def test_invalid_tool_rejection():
    registry = build_tool_registry()
    with pytest.raises(ValueError):
        registry.get("not_a_tool")  # type: ignore[arg-type]


def test_registry_contains_all_tools():
    registry = build_tool_registry()
    for tool in ToolCode:
        assert registry.get(tool).tool_code == tool
