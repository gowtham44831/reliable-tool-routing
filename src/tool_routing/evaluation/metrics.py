"""Metrics for the catalog-change tool-selection evaluation.

All "accuracy"/"correct" notions are relative to the known-valid-tool
label set, which is a known-incomplete positive set (see
docs/dataset.md): a prediction outside that set is not proven wrong, only
unconfirmed. We still call it "incorrect" for the purposes of selective
risk, following the task's evaluation protocol, and flag this caveat
wherever accuracy/risk is reported.
"""
from __future__ import annotations

import random
from dataclasses import dataclass, field

import numpy as np

from tool_routing.evaluation.records import PredictionRecord
from tool_routing.evaluation.thresholds import AbstentionPolicy


@dataclass
class MetricsResult:
    n_total: int = 0
    n_answerable: int = 0
    n_accepted: int = 0
    coverage: float = 0.0
    top1_accuracy: float | None = None  # on accepted, answerable-labeled queries
    recall_at_k: dict[int, float] = field(default_factory=dict)
    selective_risk: float | None = None  # None if n_accepted == 0 (explicit, not 0.0)
    false_action_rate: float | None = None  # on audited-unanswerable, accepted queries
    abstention_rate_on_answerable: float | None = None  # on audited-answerable queries
    n_audited_unanswerable: int = 0
    n_audited_answerable: int = 0
    latency_p50_ms: float | None = None
    latency_p95_ms: float | None = None

    def to_dict(self) -> dict:
        return {
            "n_total": self.n_total,
            "n_answerable": self.n_answerable,
            "n_accepted": self.n_accepted,
            "coverage": self.coverage,
            "top1_accuracy": self.top1_accuracy,
            "recall_at_k": self.recall_at_k,
            "selective_risk": self.selective_risk,
            "false_action_rate": self.false_action_rate,
            "abstention_rate_on_answerable": self.abstention_rate_on_answerable,
            "n_audited_unanswerable": self.n_audited_unanswerable,
            "n_audited_answerable": self.n_audited_answerable,
            "latency_p50_ms": self.latency_p50_ms,
            "latency_p95_ms": self.latency_p95_ms,
        }


def compute_metrics(
    records: list[PredictionRecord],
    policy: AbstentionPolicy,
    ks: tuple[int, ...] = (1, 3, 5),
) -> MetricsResult:
    result = MetricsResult(n_total=len(records))
    if not records:
        return result

    accepted = [r for r in records if not policy.should_abstain(r)]
    result.n_accepted = len(accepted)
    result.coverage = len(accepted) / len(records)

    # Top-1 accuracy / recall@k on *answerable* queries only (per spec),
    # restricted to accepted (non-abstained) queries, since an abstained
    # query makes no selection to score.
    answerable_accepted = [
        r for r in accepted if r.answerability_review_status != "unanswerable"
    ]
    result.n_answerable = sum(
        1 for r in records if r.answerability_review_status != "unanswerable"
    )
    if answerable_accepted:
        correct = [r.is_top1_correct() for r in answerable_accepted]
        correct = [c for c in correct if c is not None]
        if correct:
            result.top1_accuracy = sum(correct) / len(correct)
        for k in ks:
            hits = [r.recall_at_k(k) for r in answerable_accepted]
            hits = [h for h in hits if h is not None]
            if hits:
                result.recall_at_k[k] = sum(hits) / len(hits)

    if accepted:
        incorrect = [r for r in accepted if r.is_top1_correct() is False]
        result.selective_risk = len(incorrect) / len(accepted)
    else:
        result.selective_risk = None  # explicit: zero accepted, not zero risk

    audited_unanswerable = [
        r for r in records if r.answerability_review_status == "unanswerable"
    ]
    result.n_audited_unanswerable = len(audited_unanswerable)
    if audited_unanswerable:
        accepted_unanswerable = [r for r in audited_unanswerable if not policy.should_abstain(r)]
        result.false_action_rate = len(accepted_unanswerable) / len(audited_unanswerable)

    audited_answerable = [
        r for r in records if r.answerability_review_status == "answerable"
    ]
    result.n_audited_answerable = len(audited_answerable)
    if audited_answerable:
        abstained_answerable = [r for r in audited_answerable if policy.should_abstain(r)]
        result.abstention_rate_on_answerable = len(abstained_answerable) / len(audited_answerable)

    latencies_ms = [
        (r.query_prep_seconds + r.retrieval_seconds) * 1000.0 for r in records
    ]
    if latencies_ms:
        result.latency_p50_ms = float(np.percentile(latencies_ms, 50))
        result.latency_p95_ms = float(np.percentile(latencies_ms, 95))

    return result


def risk_coverage_curve(
    records: list[PredictionRecord],
    kind: str,
    thresholds: list[float],
) -> list[dict]:
    """Return [{"threshold": t, "coverage": c, "selective_risk": r}, ...]."""
    curve = []
    for t in thresholds:
        policy = AbstentionPolicy(kind, t)
        metrics = compute_metrics(records, policy)
        curve.append(
            {
                "threshold": t,
                "coverage": metrics.coverage,
                "selective_risk": metrics.selective_risk,
            }
        )
    return curve


def query_grouped_bootstrap_ci(
    records: list[PredictionRecord],
    policy: AbstentionPolicy,
    metric_fn,
    n_resamples: int = 1000,
    seed: int = 0,
    alpha: float = 0.05,
) -> dict:
    """Bootstrap CI for a scalar metric, resampling whole query_id groups.

    Scenario variants (original/known_removed/distractors_added) of the
    same base query share a query_id prefix before "::"; we resample at
    the level of the base query so that all of a query's scenario variants
    move together, avoiding pseudo-replication across correlated rows.

    ``metric_fn(records, policy) -> float | None``. Resamples where the
    metric is undefined (e.g. zero accepted queries) are skipped and the
    skip count is reported.
    """
    by_group: dict[str, list[PredictionRecord]] = {}
    for r in records:
        base_query = r.query_id
        by_group.setdefault(base_query, []).append(r)
    group_ids = sorted(by_group.keys())

    point_estimate = metric_fn(records, policy)

    if not group_ids:
        return {"point_estimate": point_estimate, "ci_low": None, "ci_high": None, "n_resamples_used": 0, "n_resamples_skipped": n_resamples}

    rng = random.Random(seed)
    values = []
    skipped = 0
    for _ in range(n_resamples):
        sampled_groups = [rng.choice(group_ids) for _ in group_ids]
        resampled_records = [r for g in sampled_groups for r in by_group[g]]
        v = metric_fn(resampled_records, policy)
        if v is None:
            skipped += 1
            continue
        values.append(v)

    if not values:
        return {
            "point_estimate": point_estimate,
            "ci_low": None,
            "ci_high": None,
            "n_resamples_used": 0,
            "n_resamples_skipped": skipped,
        }

    values.sort()
    lo_idx = int((alpha / 2) * len(values))
    hi_idx = min(len(values) - 1, int((1 - alpha / 2) * len(values)))
    return {
        "point_estimate": point_estimate,
        "ci_low": values[lo_idx],
        "ci_high": values[hi_idx],
        "n_resamples_used": len(values),
        "n_resamples_skipped": skipped,
    }
