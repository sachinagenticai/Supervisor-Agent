from __future__ import annotations

from dataclasses import asdict, dataclass
from typing import Any


@dataclass(frozen=True)
class RecordComplexityProfile:
    payload_top_level_keys: int
    metadata_top_level_keys: int
    nested_object_count: int
    list_item_count: int
    max_depth: int
    text_character_count: int

    def to_dict(self) -> dict[str, int]:
        return asdict(self)


class RecordProfiler:
    """Small deterministic profiler for production-like validation records.

    The values are not used to decide PASS/WARNING/FAIL. They provide an
    explainable data-science/quality lens for demo records and help prove that
    the Supervisor is validating rich, nested agent outputs rather than toy rows.
    """

    def profile(self, payload: dict[str, Any], metadata: dict[str, Any]) -> RecordComplexityProfile:
        combined = {"payload": payload, "metadata": metadata}
        nested_count, list_items, max_depth, text_chars = self._walk(combined, depth=0)
        return RecordComplexityProfile(
            payload_top_level_keys=len(payload),
            metadata_top_level_keys=len(metadata),
            nested_object_count=nested_count,
            list_item_count=list_items,
            max_depth=max_depth,
            text_character_count=text_chars,
        )

    def _walk(self, value: Any, depth: int) -> tuple[int, int, int, int]:
        if isinstance(value, dict):
            totals = [self._walk(v, depth + 1) for v in value.values()]
            nested = 1 + sum(item[0] for item in totals)
            list_items = sum(item[1] for item in totals)
            max_depth = max([depth] + [item[2] for item in totals])
            text_chars = sum(item[3] for item in totals)
            return nested, list_items, max_depth, text_chars
        if isinstance(value, list):
            totals = [self._walk(v, depth + 1) for v in value]
            nested = sum(item[0] for item in totals)
            list_items = len(value) + sum(item[1] for item in totals)
            max_depth = max([depth] + [item[2] for item in totals])
            text_chars = sum(item[3] for item in totals)
            return nested, list_items, max_depth, text_chars
        if isinstance(value, str):
            return 0, 0, depth, len(value)
        return 0, 0, depth, 0
