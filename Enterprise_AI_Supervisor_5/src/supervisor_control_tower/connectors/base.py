from __future__ import annotations

from abc import ABC, abstractmethod

from supervisor_control_tower.models import NormalizedRecord, ValidationRecordSummary


class RecordConnector(ABC):
    code: str
    display_name: str
    read_only: bool = True

    @abstractmethod
    def list_records(self) -> list[ValidationRecordSummary]:
        raise NotImplementedError

    @abstractmethod
    def get_record(self, record_id: str, comments: str | None = None) -> NormalizedRecord:
        raise NotImplementedError


class ConnectorRegistry:
    def __init__(self, connectors: list[RecordConnector]):
        self._connectors = {connector.code: connector for connector in connectors}

    def get(self, code: str) -> RecordConnector:
        if code not in self._connectors:
            raise ValueError(f"Unknown connector: {code}")
        return self._connectors[code]

    def list_codes(self) -> list[str]:
        return sorted(self._connectors)
