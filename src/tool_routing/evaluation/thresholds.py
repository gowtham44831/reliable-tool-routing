"""Abstention policies and validation-only threshold selection.

Policies:

* ``always_top1``     -- never abstain, always return the top-1 tool.
* ``score_threshold`` -- abstain if the top-1 score is below a threshold.
* ``margin_threshold``-- abstain if (top1 - top2) score margin is below a
                         threshold. If there is only one candidate (no
                         margin defined), this policy does NOT abstain on
                         that basis alone.

Thresholds MUST be selected on validation data only and then frozen before
touching test data -- see ``select_threshold`` and
``evaluation/pipeline.py`` / ``cli.py`` for where this boundary is
enforced.
"""
from __future__ import annotations

from dataclasses import dataclass

from tool_routing.evaluation.records import PredictionRecord

ALWAYS_TOP1 = "always_top1"
SCORE_THRESHOLD = "score_threshold"
MARGIN_THRESHOLD = "margin_threshold"
POLICIES = (ALWAYS_TOP1, SCORE_THRESHOLD, MARGIN_THRESHOLD)


@dataclass(frozen=True)
class AbstentionPolicy:
    kind: str
    threshold: float = 0.0

    def should_abstain(self, record: PredictionRecord) -> bool:
        if not record.top_k_tool_ids:
            return True
        if self.kind == ALWAYS_TOP1:
            return False
        if self.kind == SCORE_THRESHOLD:
            score = record.top1_score
            return score is None or score < self.threshold
        if self.kind == MARGIN_THRESHOLD:
            if record.margin is None:
                return False
            return record.margin < self.threshold
        raise ValueError(f"Unknown abstention policy kind: {self.kind}")


def _coverage_and_risk(records: list[PredictionRecord], policy: AbstentionPolicy) -> tuple[float, float, int]:
    accepted = [r for r in records if not policy.should_abstain(r)]
    n_accepted = len(accepted)
    coverage = n_accepted / len(records) if records else 0.0
    if n_accepted == 0:
        return coverage, 0.0, 0
    n_incorrect = sum(1 for r in accepted if r.is_top1_correct() is False)
    risk = n_incorrect / n_accepted
    return coverage, risk, n_accepted


def select_threshold(
    val_records: list[PredictionRecord],
    kind: str,
    max_risk: float = 0.1,
    candidate_thresholds: list[float] | None = None,
) -> AbstentionPolicy:
    """Select a threshold on validation data only.

    Among thresholds achieving selective risk <= ``max_risk`` on
    ``val_records``, returns the one with the highest coverage. If none
    achieve ``max_risk``, returns the threshold with the lowest risk
    (reported explicitly; callers should treat this as "no threshold met
    the target" rather than silently reporting success).
    """
    if kind == ALWAYS_TOP1:
        return AbstentionPolicy(ALWAYS_TOP1, 0.0)

    if candidate_thresholds is None:
        if kind == SCORE_THRESHOLD:
            values = sorted({r.top1_score for r in val_records if r.top1_score is not None})
        else:
            values = sorted({r.margin for r in val_records if r.margin is not None})
        candidate_thresholds = [float("-inf")] + values

    best_meeting_target: tuple[float, float, int] | None = None  # (coverage, -risk, threshold)
    best_overall: tuple[float, float] | None = None  # (risk, threshold) lowest risk fallback

    for t in candidate_thresholds:
        policy = AbstentionPolicy(kind, t)
        coverage, risk, n_accepted = _coverage_and_risk(val_records, policy)
        if n_accepted == 0:
            continue
        if risk <= max_risk:
            key = (coverage, -risk, t)
            if best_meeting_target is None or key > best_meeting_target:
                best_meeting_target = key
        if best_overall is None or risk < best_overall[0]:
            best_overall = (risk, t)

    if best_meeting_target is not None:
        return AbstentionPolicy(kind, best_meeting_target[2])
    if best_overall is not None:
        return AbstentionPolicy(kind, best_overall[1])
    # No threshold ever accepted a single query (e.g. empty val set).
    return AbstentionPolicy(kind, float("inf"))
