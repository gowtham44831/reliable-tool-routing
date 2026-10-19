"""Glue: run every retriever over every catalog scenario for every request.

This module does not execute or call any tool; it only ranks text
descriptions for retrieval.
"""
from __future__ import annotations

from collections.abc import Callable

from tool_routing.data.schema import Request, Tool
from tool_routing.evaluation.records import PredictionRecord
from tool_routing.retrieval.base import BaseRetriever
from tool_routing.scenarios.catalog import (
    CatalogManifest,
    DistractorPicker,
    build_catalog_scenarios,
)


def run_predictions(
    requests: list[Request],
    tools_by_id: dict[str, Tool],
    pool_fn: Callable[[Request], list[str]],
    distractor_picker: DistractorPicker | None,
    retrievers: dict[str, BaseRetriever],
    n_distractors: int = 3,
    top_k: int = 10,
) -> tuple[list[PredictionRecord], list[CatalogManifest]]:
    predictions: list[PredictionRecord] = []
    manifests: list[CatalogManifest] = []

    for request in requests:
        pool_ids = [tid for tid in pool_fn(request) if tid in tools_by_id]
        scenarios = build_catalog_scenarios(request, pool_ids, distractor_picker, n_distractors)
        for scenario_name, manifest in scenarios.items():
            manifests.append(manifest)
            tools_list = [tools_by_id[tid] for tid in manifest.tool_ids]
            for method_name, retriever in retrievers.items():
                retriever.prepare_catalog(manifest.catalog_id, tools_list)
                result = retriever.rank(manifest.catalog_id, request.query_text, top_k=top_k)
                predictions.append(
                    PredictionRecord(
                        query_id=request.query_id,
                        catalog_id=manifest.catalog_id,
                        scenario=scenario_name,
                        method=method_name,
                        top_k_tool_ids=result.tool_ids,
                        top1_score=result.top1_score,
                        margin=result.margin,
                        known_valid_tool_ids=request.known_valid_tool_ids,
                        answerability_review_status=request.answerability_review_status,
                        query_prep_seconds=result.query_prep_seconds,
                        retrieval_seconds=result.retrieval_seconds,
                    )
                )
    return predictions, manifests
