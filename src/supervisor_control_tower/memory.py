from __future__ import annotations

from supervisor_control_tower.models import BusinessDecision, MemoryReference, MemorySnapshot, NormalizedRecord


class StructuredMemoryProvider:
    """Safe, explainable memory backed by prior persisted evaluations.

    This intentionally avoids embeddings while Excel is the storage backend.
    It provides relevant prior outcomes without sending unrelated enterprise data
    to the LLM.
    """

    def __init__(self, reference_limit: int = 5):
        self.reference_limit = reference_limit

    def retrieve(self, repository: object, record: NormalizedRecord, agent_code: str) -> MemorySnapshot:
        if self.reference_limit <= 0 or not hasattr(repository, "recent_memory"):
            return MemorySnapshot()
        rows = repository.recent_memory(
            agent_code=agent_code,
            source_system=record.source_system,
            limit=self.reference_limit,
            exclude_record_id=record.record_id,
        )
        references: list[MemoryReference] = []
        for row in rows:
            try:
                references.append(
                    MemoryReference(
                        run_id=str(row["run_id"]),
                        external_reference=str(row["external_reference"]),
                        agent_code=str(row["agent_code"]),
                        decision=BusinessDecision(str(row["business_decision"])),
                        assurance_score=float(row.get("assurance_score") or 0.0),
                        primary_tag=str(row.get("primary_tag") or "UNKNOWN"),
                        completed_at=str(row.get("completed_at") or "") or None,
                    )
                )
            except (KeyError, ValueError, TypeError):
                continue
        if not references:
            return MemorySnapshot()
        ready = sum(reference.decision == BusinessDecision.READY for reference in references)
        blocked = sum(reference.decision == BusinessDecision.BLOCKED for reference in references)
        summary = (
            f"Retrieved {len(references)} relevant previous evaluations: "
            f"{ready} ready, {len(references) - ready - blocked} needs review and {blocked} blocked."
        )
        return MemorySnapshot(references=references, summary=summary)
