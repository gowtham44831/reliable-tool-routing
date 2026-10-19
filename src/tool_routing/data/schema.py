"""Normalized data model for tools and requests.

These dataclasses are the single internal representation used by every
downstream component (retrieval, scenarios, evaluation). Adapters for a
given raw dataset (e.g. ToolRet, or the toy fixture) are responsible for
mapping their own raw schema onto this one; see ``toolret_adapter.py`` and
``toy_fixture.py``.
"""
from __future__ import annotations

import json
from dataclasses import dataclass, field
from typing import Any, Literal

AnswerabilityStatus = Literal["answerable", "unanswerable", "uncertain", "unreviewed"]


@dataclass(frozen=True)
class Tool:
    """A single callable tool/API as it would appear in a catalog.

    Attributes:
        tool_id: Stable, globally unique identifier, preserved from the
            source dataset where possible (prefixed with ``source_dataset``
            to guarantee global uniqueness across combined sources).
        name: Short human/machine readable tool name.
        description: Free-text description of what the tool does.
        parameters: Raw parameter/schema block as provided by the source,
            kept as an opaque dict (schemas vary a lot across sources).
        source_dataset: Which raw dataset/subset this tool came from.
        tool_family: Best-effort grouping key (e.g. shared API provider or
            source subset) used to reduce tool-family leakage across
            splits. ``None`` when no reliable grouping is available.
        raw: The untouched raw record, kept for provenance/debugging.
    """

    tool_id: str
    name: str
    description: str
    parameters: dict[str, Any] = field(default_factory=dict)
    source_dataset: str = "unknown"
    tool_family: str | None = None
    raw: dict[str, Any] = field(default_factory=dict)

    def serialized_text(self) -> str:
        """Deterministic text serialization used by BM25 and embeddings.

        Raw retrieval scores computed from this text are NOT probabilities;
        they are uncalibrated similarity/overlap scores (see evaluation
        docs).
        """
        params = self.parameters or {}
        try:
            params_text = json.dumps(params, sort_keys=True, ensure_ascii=False)
        except TypeError:
            params_text = str(params)
        return f"{self.name}\n{self.description}\n{params_text}".strip()

    def to_dict(self) -> dict[str, Any]:
        return {
            "tool_id": self.tool_id,
            "name": self.name,
            "description": self.description,
            "parameters": self.parameters,
            "source_dataset": self.source_dataset,
            "tool_family": self.tool_family,
        }


@dataclass(frozen=True)
class Request:
    """A single user request/query with its known-valid tool annotations.

    Attributes:
        query_id: Stable identifier, prefixed with source_dataset.
        query_text: The natural-language request text.
        known_valid_tool_ids: Tool IDs annotated as relevant in the source
            benchmark. This is a known-incomplete positive set: tools not
            listed are NOT guaranteed to be invalid (see docs/dataset.md).
        source_dataset: Which raw dataset/subset this came from.
        split: One of "dev", "val", "test" once splits are assigned, or
            "unassigned" before that.
        answerability_review_status: Whether a human has audited whether
            the catalog genuinely contains a valid tool for this request.
            Defaults to "unreviewed"; only audited subsets may be used for
            unanswerable/abstention claims (see docs/review_workflow.md).
        raw: Untouched raw record for provenance/debugging.
    """

    query_id: str
    query_text: str
    known_valid_tool_ids: tuple[str, ...]
    source_dataset: str = "unknown"
    split: str = "unassigned"
    answerability_review_status: AnswerabilityStatus = "unreviewed"
    raw: dict[str, Any] = field(default_factory=dict)

    def to_dict(self) -> dict[str, Any]:
        return {
            "query_id": self.query_id,
            "query_text": self.query_text,
            "known_valid_tool_ids": list(self.known_valid_tool_ids),
            "source_dataset": self.source_dataset,
            "split": self.split,
            "answerability_review_status": self.answerability_review_status,
        }
