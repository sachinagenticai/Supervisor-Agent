from __future__ import annotations

from pathlib import Path
import sys

ROOT_DIR = Path(__file__).resolve().parents[1]
SRC_DIR = ROOT_DIR / "src"
if str(SRC_DIR) not in sys.path:
    sys.path.insert(0, str(SRC_DIR))

from dotenv import load_dotenv
from sqlalchemy import create_engine

from supervisor_control_tower.config import get_settings
from supervisor_control_tower.excel_store import initialize_excel_workbook


def main() -> None:
    load_dotenv()
    settings = get_settings()
    if settings.storage_backend.lower() == "excel":
        initialize_excel_workbook(settings.excel_store_path)
        print(f"Excel data store initialized: {settings.excel_store_path}")
        return

    sql_path = ROOT_DIR / "sql" / "schema.sql"
    engine = create_engine(settings.database_url, future=True)
    schema_sql = sql_path.read_text(encoding="utf-8")
    with engine.begin() as conn:
        conn.exec_driver_sql(schema_sql)
    print("PostgreSQL schema initialized successfully.")


if __name__ == "__main__":
    main()
