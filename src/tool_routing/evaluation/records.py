"""Per-query prediction records: the unit evaluation operates on."""
from __future__ import annotations

from dataclasses import dataclass, field


@dataclass(frozen=True)
class PredictionRecord:
    """One (query, catalog scenario, method) evaluation outcome.

    ``is_correct`` is only meaningful relative to the (known-incomplete)
    ``known_valid_tool_ids`` label set -- see docs/dataset.md. It is
    ``None`` when the method abstained (no selection was made).

    ``answerability_review_status`` mirrors the originating Request; only
    "answerable"/"unanswerable" (i.e. audited) records may be used for
    false-action-rate / abstention-rate-on-answerable claims.
    """

    query_id: str
    catalog_id: str
    scenario: str
    method: str
    top_k_tool_ids: tuple[str, ...]
    top1_score: float | None
    margin: float | None
    known_valid_tool_ids: tuple[str, ...]
    answerability_review_status: str
    query_prep_seconds: float = 0.0
    retrieval_seconds: float = 0.0

    def top1_tool_id(self) -> str | None:
        return self.top_k_tool_ids[0] if self.top_k_tool_ids else None

    def is_top1_correct(self) -> bool | None:
        top1 = self.top1_tool_id()
        if top1 is None:
            return None
        return top1 in self.known_valid_tool_ids

    def recall_at_k(self, k: int) -> bool | None:
        if not self.top_k_tool_ids:
            return None
        return any(tid in self.known_valid_tool_ids for tid in self.top_k_tool_ids[:k])

    def to_dict(self) -> dict:
        return {
            "query_id": self.query_id,
            "catalog_id": self.catalog_id,
            "scenario": self.scenario,
            "method": self.method,
            "top_k_tool_ids": list(self.top_k_tool_ids),
            "top1_score": self.top1_score,
            "margin": self.margin,
            "known_valid_tool_ids": list(self.known_valid_tool_ids),
            "answerability_review_status": self.answerability_review_status,
        }
