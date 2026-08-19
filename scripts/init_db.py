from __future__ import annotations

from pathlib import Path
import sys

ROOT_DIR = Path(__file__).resolve().parents[1]
SRC_DIR = ROOT_DIR / "src"
if str(SRC_DIR) not in sys.path:
    sys.path.insert(0, str(SRC_DIR))

from dotenv import load_dotenv

from supervisor_control_tower.config import get_settings
from supervisor_control_tower.excel_store import initialize_excel_workbook


def main() -> None:
    load_dotenv()
    settings = get_settings()
    if settings.storage_backend.lower() != "excel":
        raise RuntimeError("This release is configured for Excel storage only.")
    initialize_excel_workbook(settings.excel_store_path, reset=False)
    print(f"Excel store initialized or migrated: {settings.excel_store_path}")


if __name__ == "__main__":
    main()
