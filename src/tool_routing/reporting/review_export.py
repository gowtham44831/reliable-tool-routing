"""Export a human review CSV for answerability / relevance auditing.

See docs/review_workflow.md for how reviewers should use this file. Until
a query's row has been reviewed, its ``answerability_review_status``
remains "unreviewed" / whatever was already known, and it must NOT be
treated as a definitive negative or used for false-action-rate claims.
"""
from __future__ import annotations

import csv
from pathlib import Path

REVIEW_CSV_FIELDS = [
    "query_id",
    "query_text",
    "scenario",
    "catalog_id",
    "known_valid_tool_ids",
    "bm25_top_tool_ids",
    "bm25_top_descriptions",
    "embedding_top_tool_ids",
    "embedding_top_descriptions",
    "answerability_status",  # answerable / unanswerable / uncertain
    "reviewer_relevant_tool_ids",  # to be filled in by reviewer
    "reviewer_notes",
]


def build_review_row(
    *,
    query_id: str,
    query_text: str,
    scenario: str,
    catalog_id: str,
    known_valid_tool_ids: list[str],
    bm25_top_tool_ids: list[str],
    bm25_top_descriptions: list[str],
    embedding_top_tool_ids: list[str],
    embedding_top_descriptions: list[str],
    answerability_status: str = "uncertain",
) -> dict:
    return {
        "query_id": query_id,
        "query_text": query_text,
        "scenario": scenario,
        "catalog_id": catalog_id,
        "known_valid_tool_ids": "; ".join(known_valid_tool_ids),
        "bm25_top_tool_ids": "; ".join(bm25_top_tool_ids),
        "bm25_top_descriptions": " | ".join(bm25_top_descriptions),
        "embedding_top_tool_ids": "; ".join(embedding_top_tool_ids),
        "embedding_top_descriptions": " | ".join(embedding_top_descriptions),
        "answerability_status": answerability_status,
        "reviewer_relevant_tool_ids": "",
        "reviewer_notes": "",
    }


def export_review_csv(rows: list[dict], out_path: str | Path) -> None:
    out_path = Path(out_path)
    out_path.parent.mkdir(parents=True, exist_ok=True)
    with open(out_path, "w", newline="", encoding="utf-8") as f:
        writer = csv.DictWriter(f, fieldnames=REVIEW_CSV_FIELDS)
        writer.writeheader()
        for row in rows:
            writer.writerow({k: row.get(k, "") for k in REVIEW_CSV_FIELDS})


def count_uncertain(rows: list[dict]) -> int:
    return sum(1 for r in rows if r.get("answerability_status") == "uncertain")
