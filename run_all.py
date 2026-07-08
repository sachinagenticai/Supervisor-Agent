from __future__ import annotations

import compileall
import os
import subprocess
import sys
from pathlib import Path

ROOT_DIR = Path(__file__).resolve().parent
SRC_DIR = ROOT_DIR / "src"


def _print_step(message: str) -> None:
    print(f"\n=== {message} ===", flush=True)


def _run(command: list[str], *, env: dict[str, str] | None = None) -> None:
    result = subprocess.run(command, cwd=ROOT_DIR, env=env, text=True)
    if result.returncode != 0:
        raise SystemExit(result.returncode)


def _prepare_pythonpath() -> dict[str, str]:
    env = os.environ.copy()
    existing = env.get("PYTHONPATH", "")
    env["PYTHONPATH"] = str(SRC_DIR) if not existing else f"{SRC_DIR}{os.pathsep}{existing}"
    return env


def _initialize_and_seed() -> None:
    if str(SRC_DIR) not in sys.path:
        sys.path.insert(0, str(SRC_DIR))
    from scripts.init_db import main as init_main
    from scripts.seed_data import main as seed_main

    _print_step("Initializing Excel data store")
    init_main()
    _print_step("Loading production-like seed data")
    seed_main()


def _run_compile_check() -> None:
    _print_step("Running Python compile check")
    paths = [
        ROOT_DIR / "app.py",
        ROOT_DIR / "run_all.py",
        ROOT_DIR / "src",
        ROOT_DIR / "scripts",
        ROOT_DIR / "tests",
    ]
    ok = True
    for path in paths:
        if not path.exists():
            continue
        if path.is_file():
            ok = compileall.compile_file(str(path), quiet=1) and ok
        else:
            ok = compileall.compile_dir(str(path), quiet=1) and ok
    if not ok:
        raise SystemExit("Compile check failed.")
    print("Compile check passed.")


def _run_tests() -> None:
    _print_step("Running automated tests")
    _run([sys.executable, "-m", "pytest", "-q"], env=_prepare_pythonpath())


def main() -> None:
    print("Supervisor Agent Control Tower - setup and validation check")
    _initialize_and_seed()
    _run_compile_check()
    _run_tests()
    _print_step("Ready")
    print("Terminal checks passed. Start the app with: streamlit run app.py")


if __name__ == "__main__":
    main()
