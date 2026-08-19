from __future__ import annotations

import compileall
import os
import subprocess
import sys
from pathlib import Path

ROOT_DIR = Path(__file__).resolve().parent
SRC_DIR = ROOT_DIR / "src"


def _step(message: str) -> None:
    print(f"\n=== {message} ===", flush=True)


def _environment() -> dict[str, str]:
    env = os.environ.copy()
    existing = env.get("PYTHONPATH", "")
    paths = [str(SRC_DIR), str(ROOT_DIR)]
    if existing:
        paths.append(existing)
    env["PYTHONPATH"] = os.pathsep.join(paths)
    return env


def _run(command: list[str]) -> None:
    completed = subprocess.run(command, cwd=ROOT_DIR, env=_environment(), check=False)
    if completed.returncode:
        raise SystemExit(completed.returncode)


def main() -> None:
    if str(SRC_DIR) not in sys.path:
        sys.path.insert(0, str(SRC_DIR))
    if str(ROOT_DIR) not in sys.path:
        sys.path.insert(0, str(ROOT_DIR))

    from scripts.seed_data import seed_excel
    from supervisor_control_tower.config import get_settings

    settings = get_settings()
    if settings.storage_backend != "excel":
        raise SystemExit("This release requires STORAGE_BACKEND=excel.")
    if settings.app_env.strip().upper() in {"PROD", "PRODUCTION"}:
        raise SystemExit("run_all.py resets seed data and must not be executed in production.")

    _step("Initializing and seeding production-like Excel data")
    seed_excel(settings.excel_store_path, reset=True)

    _step("Compiling Python sources")
    targets = [ROOT_DIR / "app.py", ROOT_DIR / "healthcheck.py", ROOT_DIR / "src", ROOT_DIR / "scripts", ROOT_DIR / "tests"]
    if not all(
        compileall.compile_file(str(target), quiet=1) if target.is_file() else compileall.compile_dir(str(target), quiet=1)
        for target in targets
    ):
        raise SystemExit("Compile check failed.")

    _step("Running automated tests")
    _run([sys.executable, "-m", "pytest"])

    _step("Ready")
    print("UI:  streamlit run app.py")
    print("Container: docker build -t enterprise-ai-supervisor .")


if __name__ == "__main__":
    main()
