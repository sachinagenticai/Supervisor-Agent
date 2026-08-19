from __future__ import annotations

from supervisor_control_tower.models import NormalizedRecord, ValidationRecordSummary
from supervisor_control_tower.repositories import SupervisorRepository
from supervisor_control_tower.connectors.base import RecordConnector


class ExcelRecordConnector(RecordConnector):
    code = "excel_records"
    display_name = "Excel enterprise record store"
    read_only = True

    def __init__(self, repository: SupervisorRepository):
        self.repository = repository

    def list_records(self) -> list[ValidationRecordSummary]:
        return self.repository.list_active_records()

    def get_record(self, record_id: str, comments: str | None = None) -> NormalizedRecord:
        return self.repository.get_record(record_id, comments)
