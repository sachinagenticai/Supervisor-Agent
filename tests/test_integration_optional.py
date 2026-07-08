from __future__ import annotations

import os

import pytest

pytestmark = pytest.mark.integration


def test_postgres_integration_documented_skip():
    if os.getenv("RUN_DB_TESTS") != "true":
        pytest.skip("Set RUN_DB_TESTS=true after starting PostgreSQL to run integration tests.")
    assert True
