from __future__ import annotations

from supervisor_control_tower.data_science.record_profile import RecordProfiler
from supervisor_control_tower.seed_records import RECORDS, SEED_VERSION


def test_seed_records_are_production_like_and_metadata_rich():
    assert len(RECORDS) == 24
    profiler = RecordProfiler()
    for record in RECORDS:
        rec_id, ext, source, rtype, title, agent, payload, metadata = record
        profile = profiler.profile(payload, metadata)
        assert metadata["seed_version"] == SEED_VERSION
        assert metadata["record_contract_version"]
        assert metadata["correlation_id"]
        assert metadata["owner"]
        assert profile.payload_top_level_keys >= 10, ext
        assert profile.nested_object_count >= 5, ext
        assert profile.max_depth >= 3, ext
        assert profile.text_character_count >= 400, ext
