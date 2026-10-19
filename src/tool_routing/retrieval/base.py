"""Common retrieval interface shared by all baselines.

Scores returned by any retriever are uncalibrated relevance/similarity
scores (BM25 term-overlap scores or cosine similarities), NOT
probabilities. Do not interpret them as calibrated confidence.
"""
from __future__ import annotations

from dataclasses import dataclass, field

from tool_routing.data.schema import Tool


@dataclass(frozen=True)
class RankedResult:
    """One query's ranked output against one catalog."""

    tool_ids: tuple[str, ...]
    scores: tuple[float, ...]
    query_prep_seconds: float
    retrieval_seconds: float

    @property
    def top1_tool_id(self) -> str | None:
        return self.tool_ids[0] if self.tool_ids else None

    @property
    def top1_score(self) -> float | None:
        return self.scores[0] if self.scores else None

    @property
    def top2_score(self) -> float | None:
        return self.scores[1] if len(self.scores) > 1 else None

    @property
    def margin(self) -> float | None:
        """top1 - top2 score margin, or None if fewer than 2 candidates."""
        if self.top1_score is None:
            return None
        if self.top2_score is None:
            return None
        return self.top1_score - self.top2_score

    def to_record(self, k: int = 5) -> dict:
        return {
            "top_k_tool_ids": list(self.tool_ids[:k]),
            "top_k_scores": [round(s, 6) for s in self.scores[:k]],
            "top1_tool_id": self.top1_tool_id,
            "top1_score": self.top1_score,
            "top2_score": self.top2_score,
            "margin": self.margin,
            "query_prep_seconds": self.query_prep_seconds,
            "retrieval_seconds": self.retrieval_seconds,
        }


class BaseRetriever:
    """Interface for a retriever over an arbitrary, swappable tool catalog.

    Implementations build/cache a per-catalog index on first use (keyed by
    the catalog's tool IDs) and expose ``rank`` to score+order those tools
    for a given query. Index preparation time and per-query latency are
    tracked separately so callers can report them (see evaluation docs).
    """

    name: str = "base"

    def prepare_catalog(self, catalog_id: str, tools: list[Tool]) -> float:
        """Build (or fetch from cache) the index for ``tools``.

        Returns wall-clock seconds spent preparing the index (0.0 if
        served entirely from cache).
        """
        raise NotImplementedError

    def rank(self, catalog_id: str, query_text: str, top_k: int = 10) -> RankedResult:
        raise NotImplementedError
