from __future__ import annotations

from supervisor_control_tower.config import Settings
from supervisor_control_tower.db import Database
from supervisor_control_tower.models import AppUser, Verdict
from supervisor_control_tower.repositories import SupervisorRepository
from supervisor_control_tower.validation_service import ValidationService
from scripts.seed_data import seed_excel


def test_excel_seed_and_validation_end_to_end(tmp_path):
    workbook = tmp_path / "supervisor.xlsx"
    seed_excel(str(workbook))
    settings = Settings(storage_backend="excel", excel_store_path=str(workbook), mock_llm=True, auth_enabled=False, demo_auth=True)
    db = Database(settings)
    user = AppUser(google_subject_id="demo-user", email="demo@example.com", display_name="Demo User")

    with db.transaction() as conn:
        repo = SupervisorRepository(conn)
        records = repo.list_active_records()
        baseline = repo.dashboard_metrics()["total_validations"]
    assert len(records) == 24

    result = ValidationService(settings, db).run_validation("rec-pipe-001", "focus on RCA evidence", user)
    assert result.final.verdict in {Verdict.PASS, Verdict.WARNING, Verdict.FAIL}

    with db.transaction() as conn:
        repo = SupervisorRepository(conn)
        metrics = repo.dashboard_metrics()
        history = repo.history(search="REC-PIPE-001")
    assert metrics["total_validations"] == baseline + 1
    assert history
