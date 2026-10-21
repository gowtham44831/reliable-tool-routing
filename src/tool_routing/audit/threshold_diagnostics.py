"""Exact-count diagnostics for abstention-threshold selection.

Re-derives, from saved prediction records and frozen thresholds, the
numbers needed to understand *why* a threshold policy accepts what it
accepts:

* per (method, policy, scenario, split): n, accepted, correct/incorrect
  accepted, coverage and selective risk (both with Wilson intervals and
  explicit ``None`` when undefined);
* a full trace of the validation-only selection procedure, reproducing
  ``evaluation.thresholds.select_threshold`` candidate by candidate;
* a structured explanation of zero test coverage.

"Correct" throughout means "top-1 is in the annotated (known-incomplete)
label set". Nothing here changes a threshold.
"""
from __future__ import annotations

import math
import random
from collections import defaultdict

from tool_routing.evaluation.binomial_ci import wilson_ci
from tool_routing.evaluation.metrics import query_grouped_bootstrap_ci
from tool_routing.evaluation.records import PredictionRecord
from tool_routing.evaluation.thresholds import (
    ALWAYS_TOP1,
    MARGIN_THRESHOLD,
    SCORE_THRESHOLD,
    AbstentionPolicy,
    select_threshold,
)

ALL_SCENARIOS = "ALL (mixed)"

SELECTION_OBJECTIVE = {
    ALWAYS_TOP1: "none: never abstains (no threshold)",
    SCORE_THRESHOLD: (
        "validation-only: maximize coverage subject to empirical val selective risk <= {max_risk}; "
        "candidates = -inf + every distinct val top-1 score; accept iff score >= t; "
        "if no candidate meets the target, fall back to the minimum-val-risk candidate"
    ),
    MARGIN_THRESHOLD: (
        "validation-only: maximize coverage subject to empirical val selective risk <= {max_risk}; "
        "candidates = -inf + every distinct val (top1 - top2) margin; accept iff margin >= t "
        "(records with undefined margin are always accepted); fallback as for score_threshold"
    ),
}


def _signal(record: PredictionRecord, kind: str) -> float | None:
    return record.top1_score if kind == SCORE_THRESHOLD else record.margin


def _fmt_threshold(t: float) -> float | str:
    if math.isinf(t):
        return "-inf" if t < 0 else "+inf"
    return t


def count_row(records: list[PredictionRecord], policy: AbstentionPolicy) -> dict:
    n = len(records)
    accepted = [r for r in records if not policy.should_abstain(r)]
    n_acc = len(accepted)
    n_correct = sum(1 for r in accepted if r.is_top1_correct() is True)
    n_incorrect = sum(1 for r in accepted if r.is_top1_correct() is False)
    cov = wilson_ci(n_acc, n)
    risk = wilson_ci(n_incorrect, n_acc)
    return {
        "n_queries": n,
        "n_accepted": n_acc,
        "n_correct_accepted": n_correct,
        "n_incorrect_accepted": n_incorrect,
        "coverage": cov.rate,
        "coverage_ci95_low": cov.ci_low,
        "coverage_ci95_high": cov.ci_high,
        "selective_risk": risk.rate,
        "selective_risk_ci95_low": risk.ci_low,
        "selective_risk_ci95_high": risk.ci_high,
        "selective_risk_status": "defined" if n_acc else "UNDEFINED (0 accepted)",
    }


def _mixed_coverage(records: list[PredictionRecord], policy: AbstentionPolicy) -> float:
    return sum(1 for r in records if not policy.should_abstain(r)) / len(records)


def _mixed_selective_risk(records: list[PredictionRecord], policy: AbstentionPolicy) -> float | None:
    accepted = [r for r in records if not policy.should_abstain(r)]
    if not accepted:
        return None
    return sum(1 for r in accepted if r.is_top1_correct() is False) / len(accepted)


def diagnostics_table(
    records_by_split: dict[str, list[PredictionRecord]],
    policies_by_method: dict[str, dict[str, AbstentionPolicy]],
    max_risk: float,
    threshold_scope: str,
    cluster_bootstrap_resamples: int = 1000,
) -> list[dict]:
    """One row per (method, policy, scenario incl. mixed, split).

    Selective risk is always the DECISION-level rate: incorrect accepted
    decisions / accepted decisions (each scenario row is one decision).

    Interval columns: single-scenario rows have one record per query, so
    the Wilson interval from ``count_row`` is on independent trials
    (``selective_risk_ci95_method`` = "wilson_independent_rows"). Mixed
    "ALL" rows contain 3 correlated records per query; for them the
    primary interval is a QUERY-CLUSTER bootstrap that resamples whole
    queries so all scenario variants of a query move together
    (``selective_risk_ci95_method`` = "query_cluster_bootstrap_1000",
    coverage likewise). The row-level Wilson is retained in
    ``*_rw_*`` columns for reference, marked as ignoring correlation.

    A separate QUERY-LEVEL metric is also reported for mixed rows in
    ``qlev_*`` columns: aggregation rule = a query counts once if it has
    >=1 accepted decision, and once more as "error" if >=1 of its
    accepted decisions is incorrect; Wilson interval on those
    distinct-query counts. This is a DIFFERENT metric (worst-case per
    request), not a replacement for decision-level risk.

    Caveat: a bootstrap CI is degenerate [0,0] when all resampled
    accepted decisions are correct -- it is not evidence of zero
    population risk; see the qlev_ Wilson bound for an honest upper
    limit when accepted counts are tiny.
    """
    rows = []
    for method, policies in sorted(policies_by_method.items()):
        for policy_name, policy in policies.items():
            for split, recs in records_by_split.items():
                mrecs = [r for r in recs if r.method == method]
                scenarios = sorted({r.scenario for r in mrecs})
                for scenario in scenarios + [ALL_SCENARIOS]:
                    srecs = mrecs if scenario == ALL_SCENARIOS else [r for r in mrecs if r.scenario == scenario]
                    row = {
                        "method": method,
                        "policy": policy_name,
                        "threshold_scope": threshold_scope if policy_name != ALWAYS_TOP1 else "n/a",
                        "threshold": _fmt_threshold(policy.threshold) if policy_name != ALWAYS_TOP1 else "n/a",
                        "selection_objective": SELECTION_OBJECTIVE[policy_name].format(max_risk=max_risk),
                        "scenario": scenario,
                        "split": split,
                    }
                    row.update(count_row(srecs, policy))
                    row["selective_risk_ci95_method"] = "wilson_independent_rows"
                    if scenario == ALL_SCENARIOS:
                        # Decision-level risk stays row-level; its CI must
                        # respect query clustering, so resample queries.
                        cov_ci = query_grouped_bootstrap_ci(
                            srecs, policy, _mixed_coverage,
                            n_resamples=cluster_bootstrap_resamples, seed=0,
                        )
                        risk_ci = query_grouped_bootstrap_ci(
                            srecs, policy, _mixed_selective_risk,
                            n_resamples=cluster_bootstrap_resamples, seed=0,
                        )
                        row["selective_risk_ci95_rw_low"] = row["selective_risk_ci95_low"]
                        row["selective_risk_ci95_rw_high"] = row["selective_risk_ci95_high"]
                        row["coverage_ci95_rw_low"] = row["coverage_ci95_low"]
                        row["coverage_ci95_rw_high"] = row["coverage_ci95_high"]
                        if srecs and any(r.is_top1_correct() is not None for r in srecs):
                            row["selective_risk"] = _mixed_selective_risk(srecs, policy)
                            row["selective_risk_ci95_low"] = risk_ci["ci_low"]
                            row["selective_risk_ci95_high"] = risk_ci["ci_high"]
                            row["selective_risk_ci95_method"] = "query_cluster_bootstrap_1000"
                        row["coverage_ci95_low"] = cov_ci["ci_low"]
                        row["coverage_ci95_high"] = cov_ci["ci_high"]
                        row["coverage_ci95_method"] = "query_cluster_bootstrap_1000"
                        # Separate query-level metric (see docstring).
                        accepted = [r for r in srecs if not policy.should_abstain(r)]
                        q_acc = {r.query_id for r in accepted}
                        q_err = {r.query_id for r in accepted if r.is_top1_correct() is False}
                        qr = wilson_ci(len(q_err), len(q_acc))
                        row["qlev_n_queries_with_accepted"] = len(q_acc)
                        row["qlev_n_queries_with_incorrect"] = len(q_err)
                        row["qlev_rate"] = qr.rate
                        row["qlev_ci95_low"] = qr.ci_low
                        row["qlev_ci95_high"] = qr.ci_high
                        row["qlev_rule"] = "query counts once if >=1 accepted decision; error if >=1 accepted decision is incorrect"
                    rows.append(row)
    return rows


def selection_trace(val_records: list[PredictionRecord], kind: str, max_risk: float) -> list[dict]:
    """Every candidate threshold that ``select_threshold`` considers, with
    its validation counts. Mirrors the candidate set and acceptance rule of
    ``evaluation.thresholds.select_threshold`` exactly."""
    values = sorted({v for r in val_records if (v := _signal(r, kind)) is not None})
    out = []
    for t in [float("-inf")] + values:
        policy = AbstentionPolicy(kind, t)
        c = count_row(val_records, policy)
        out.append(
            {
                "threshold": t,
                "n_accepted": c["n_accepted"],
                "n_incorrect_accepted": c["n_incorrect_accepted"],
                "coverage": c["coverage"],
                "selective_risk": c["selective_risk"],
                "meets_target": c["n_accepted"] > 0 and c["selective_risk"] <= max_risk,
            }
        )
    return out


def explain_threshold(
    val_records: list[PredictionRecord],
    test_records: list[PredictionRecord],
    kind: str,
    frozen_threshold: float,
    max_risk: float,
) -> dict:
    """Answer, with counts, the four 'why is test coverage zero?' questions."""
    trace = selection_trace(val_records, kind, max_risk)
    reselected = select_threshold(val_records, kind, max_risk=max_risk).threshold
    meeting = [t for t in trace if t["meets_target"]]
    nonzero_meeting = [t for t in meeting if t["n_accepted"] > 0]
    policy = AbstentionPolicy(kind, frozen_threshold)
    val_c = count_row(val_records, policy)
    test_c = count_row(test_records, policy)

    val_sig = [v for r in val_records if (v := _signal(r, kind)) is not None]
    test_sig = [v for r in test_records if (v := _signal(r, kind)) is not None]
    n_undefined_val = sum(1 for r in val_records if _signal(r, kind) is None)
    n_undefined_test = sum(1 for r in test_records if _signal(r, kind) is None)

    # Ties / boundary: how many signals sit exactly at the threshold, and
    # how many top-1 predictions are exact score ties with top-2
    # (margin == 0), i.e. decided by sort order rather than by the model.
    ties_val = sum(1 for v in val_sig if v == frozen_threshold)
    ties_test = sum(1 for v in test_sig if v == frozen_threshold)
    zero_margin_val = sum(1 for r in val_records if r.margin == 0)
    zero_margin_test = sum(1 for r in test_records if r.margin == 0)

    # Largest coverage achievable on val at each risk level (for context).
    best_cov_by_target = {}
    for target in (0.1, 0.2, 0.3, 0.5):
        ok = [t for t in trace if t["n_accepted"] > 0 and t["selective_risk"] <= target]
        best_cov_by_target[str(target)] = max((t["coverage"] for t in ok), default=0.0)

    winners = [t for t in trace if t["threshold"] == frozen_threshold]
    winner = winners[0] if winners else None
    return {
        "kind": kind,
        "frozen_threshold": _fmt_threshold(frozen_threshold),
        "reselected_threshold_matches_frozen": reselected == frozen_threshold,
        "n_val_records": len(val_records),
        "n_candidates": len(trace),
        "n_candidates_meeting_target": len(meeting),
        "n_nonzero_coverage_candidates_meeting_target": len(nonzero_meeting),
        "fallback_used": len(meeting) == 0,
        "selected_val_counts": val_c,
        "selected_val_was_zero_coverage": val_c["n_accepted"] == 0,
        "val_rank_of_threshold_from_top": (sorted(val_sig, reverse=True).index(frozen_threshold) + 1)
        if frozen_threshold in val_sig
        else None,
        "test_counts": test_c,
        "test_rejected_everything": test_c["n_accepted"] == 0,
        "val_signal_max": max(val_sig, default=None),
        "test_signal_max": max(test_sig, default=None),
        "test_signal_quantiles": _quantiles(test_sig),
        "val_signal_quantiles": _quantiles(val_sig),
        "n_undefined_signal_val": n_undefined_val,
        "n_undefined_signal_test": n_undefined_test,
        "n_val_exactly_at_threshold": ties_val,
        "n_test_exactly_at_threshold": ties_test,
        "n_zero_margin_top1_ties_val": zero_margin_val,
        "n_zero_margin_top1_ties_test": zero_margin_test,
        "best_val_coverage_at_risk_target": best_cov_by_target,
        "winner_trace_row": winner,
    }


def _quantiles(values: list[float]) -> dict | None:
    if not values:
        return None
    s = sorted(values)

    def q(p: float) -> float:
        return s[min(len(s) - 1, int(p * (len(s) - 1) + 0.5))]

    return {"min": s[0], "p25": q(0.25), "p50": q(0.5), "p75": q(0.75), "p90": q(0.9), "max": s[-1]}


def paired_accuracy_difference(
    records_a: list[PredictionRecord],
    records_b: list[PredictionRecord],
    n_resamples: int = 2000,
    seed: int = 0,
    alpha: float = 0.05,
) -> dict:
    """Paired, query-grouped bootstrap of (label-agreement@1 of A) - (of B).

    Records are paired by ``query_id`` (e.g. same queries, two scenarios
    or two methods). Also reports the discordant-pair counts (McNemar
    b/c) so the numerators behind the difference are visible.
    """
    a = {r.query_id: bool(r.is_top1_correct()) for r in records_a}
    b = {r.query_id: bool(r.is_top1_correct()) for r in records_b}
    qids = sorted(set(a) & set(b))
    n = len(qids)
    if n == 0:
        return {"n_paired_queries": 0, "diff": None, "ci95_low": None, "ci95_high": None}
    diffs = [int(a[q]) - int(b[q]) for q in qids]
    point = sum(diffs) / n
    rng = random.Random(seed)
    boots = sorted(sum(diffs[rng.randrange(n)] for _ in range(n)) / n for _ in range(n_resamples))
    lo = boots[int((alpha / 2) * n_resamples)]
    hi = boots[min(n_resamples - 1, int((1 - alpha / 2) * n_resamples))]
    return {
        "n_paired_queries": n,
        "a_correct": sum(a[q] for q in qids),
        "b_correct": sum(b[q] for q in qids),
        "a_only_correct": sum(1 for q in qids if a[q] and not b[q]),
        "b_only_correct": sum(1 for q in qids if b[q] and not a[q]),
        "diff": point,
        "ci95_low": lo,
        "ci95_high": hi,
        "n_resamples": n_resamples,
    }


def scenario_specific_policies(
    val_records: list[PredictionRecord], kind: str, max_risk: float
) -> dict[str, AbstentionPolicy]:
    """DIAGNOSTIC ONLY: thresholds selected separately per scenario on
    validation. Not deployable (a deployed router does not know which
    scenario it is in) and must not be used to pick a method."""
    by_scen: dict[str, list[PredictionRecord]] = defaultdict(list)
    for r in val_records:
        by_scen[r.scenario].append(r)
    return {s: select_threshold(recs, kind, max_risk=max_risk) for s, recs in sorted(by_scen.items())}
