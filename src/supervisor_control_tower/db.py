from __future__ import annotations

import logging
from contextlib import contextmanager
from typing import Iterator

from sqlalchemy import create_engine
from sqlalchemy.engine import Connection, Engine

from supervisor_control_tower.config import Settings
from supervisor_control_tower.excel_store import ExcelDataStore, ExcelTransaction

logger = logging.getLogger(__name__)

StorageConnection = Connection | ExcelDataStore


class Database:
    """Storage gateway for the POC.

    STORAGE_BACKEND=excel keeps the app lightweight for Streamlit demos.
    STORAGE_BACKEND=postgres keeps the original database path available for later.
    """

    def __init__(self, settings: Settings):
        self.settings = settings
        self._engine: Engine | None = None

    @property
    def is_excel(self) -> bool:
        return self.settings.storage_backend.lower() == "excel"

    @property
    def engine(self) -> Engine:
        if self._engine is None:
            self._engine = create_engine(
                self.settings.database_url,
                pool_pre_ping=True,
                pool_size=5,
                max_overflow=5,
                future=True,
            )
        return self._engine

    @contextmanager
    def transaction(self) -> Iterator[StorageConnection]:
        if self.is_excel:
            with ExcelTransaction(self.settings.excel_store_path) as store:
                yield store
            return
        with self.engine.begin() as conn:
            yield conn

    def close(self) -> None:
        if self._engine is not None:
            self._engine.dispose()
            self._engine = None
