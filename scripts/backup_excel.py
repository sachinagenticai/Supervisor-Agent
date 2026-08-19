from __future__ import annotations

import argparse
from datetime import datetime, timezone
from pathlib import Path
import shutil
import sys

from filelock import FileLock

ROOT_DIR = Path(__file__).resolve().parents[1]
SRC_DIR = ROOT_DIR / "src"
if str(SRC_DIR) not in sys.path:
    sys.path.insert(0, str(SRC_DIR))

from supervisor_control_tower.config import get_settings


def backup_excel(source: str | Path, destination: str | Path, retention: int = 20) -> Path:
    source_path = Path(source)
    if not source_path.exists():
        raise FileNotFoundError(f"Excel store not found: {source_path}")
    destination_path = Path(destination)
    destination_path.mkdir(parents=True, exist_ok=True)
    timestamp = datetime.now(timezone.utc).strftime("%Y%m%dT%H%M%SZ")
    target = destination_path / f"{source_path.stem}_{timestamp}{source_path.suffix}"

    with FileLock(str(source_path) + ".lock", timeout=60):
        shutil.copy2(source_path, target)

    backups = sorted(
        destination_path.glob(f"{source_path.stem}_*{source_path.suffix}"),
        key=lambda item: item.stat().st_mtime,
        reverse=True,
    )
    for old_backup in backups[max(1, retention):]:
        old_backup.unlink(missing_ok=True)
    return target


def main() -> None:
    parser = argparse.ArgumentParser(description="Create a locked backup of the Supervisor Excel store.")
    parser.add_argument("--destination", default="data/backups")
    parser.add_argument("--retention", type=int, default=20)
    args = parser.parse_args()
    settings = get_settings()
    target = backup_excel(settings.excel_store_path, args.destination, args.retention)
    print(f"Backup created: {target}")


if __name__ == "__main__":
    main()
