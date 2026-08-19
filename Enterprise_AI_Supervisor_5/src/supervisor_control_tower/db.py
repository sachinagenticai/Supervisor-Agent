from __future__ import annotations

from contextlib import contextmanager
from typing import Iterator

from supervisor_control_tower.config import Settings
from supervisor_control_tower.excel_store import ExcelDataStore, ExcelTransaction

StorageConnection = ExcelDataStore


class Database:
    """Excel-first controlled-deployment storage gateway.

    The repository boundary is intentionally stable for a future PostgreSQL
    implementation, but this release does not expose an incomplete database path.
    """

    def __init__(self, settings: Settings):
        self.settings = settings
        if settings.storage_backend != "excel":
            raise ValueError("This release supports STORAGE_BACKEND=excel only.")

    @property
    def is_excel(self) -> bool:
        return True

    @contextmanager
    def transaction(self) -> Iterator[StorageConnection]:
        with ExcelTransaction(
            self.settings.excel_store_path,
            self.settings.excel_lock_timeout_seconds,
        ) as store:
            yield store

    def close(self) -> None:
        return None
