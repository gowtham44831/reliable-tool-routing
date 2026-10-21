"""Development-set metrics for argument verification.

All metrics are computed against labels generated from per-case rules.
"Unsupported call" = expected action is not ``proceed`` (the call must
not execute as proposed). "Supported call" = expected ``proceed``.
20 development cases; every count is reported alongside its percentage.
"""
from __future__ import annotations

import time
from collections import defaultdict
from typing import Any, Callable


def evaluate(cases, verifier: Callable, name: str) -> dict:
    rows = []
    lat = []
    usage = []
    run_config = None
    for c in cases:
        pub = c.public_view()
        t0 = time.perf_counter()
        out = verifier(pub)
        dt = time.perf_counter() - t0
        if out is None:  # e.g. AI verifier not configured
            return {"method": name, "status": "not_run"}
        lat.append(out.get("latency_s", dt))
        if out.get("usage"):
            usage.append(out["usage"])
        if run_config is None and out.get("config"):
            run_config = out["config"]
        rows.append({
            "case_id": c.case_id, "pair_id": c.pair_id,
            "expected_action": c.expected_next_action,
            "pred_action": out["action"],
            "action_ok": out["action"] == c.expected_next_action,
            "arg_findings": out["findings"],
            "expected_findings": c.expected_argument_findings,
            "details": out.get("details", {}),
            "latency_s": out.get("latency_s", dt),
            "error": out.get("error"),
            "parse_ok": out.get("parse_ok"),
            "model": out.get("model"),
            "raw": out.get("raw"),
            "usage": out.get("usage"),
            "finish_reason": out.get("finish_reason"),
        })

    # verifier failures are reported separately: they block execution but
    # are NOT detections, and they are not model judgments either
    failures = [r for r in rows if r["pred_action"] == "verifier_error"]
    supported = [r for r in rows if r["expected_action"] == "proceed"]
    unsupported = [r for r in rows if r["expected_action"] != "proceed"]
    blocked = [r for r in supported
               if r["pred_action"] not in ("proceed", "verifier_error")]
    allowed = [r for r in unsupported if r["pred_action"] == "proceed"]
    detected = [r for r in unsupported
                if r["pred_action"] not in ("proceed", "verifier_error")]
    unnecessary_clarify = [r for r in rows
                           if r["expected_action"] != "clarify" and r["pred_action"] == "clarify"]

    # argument-level accuracy over expected finding labels, per expected category
    n_args = n_args_correct = 0
    conf = defaultdict(int)
    by_cat: dict[str, list[int]] = defaultdict(lambda: [0, 0])
    for r in rows:
        for arg, exp in r["expected_findings"].items():
            pred = r["arg_findings"].get(arg)
            n_args += 1
            n_args_correct += pred == exp
            conf[(exp, pred)] += 1
            by_cat[exp][0] += pred == exp
            by_cat[exp][1] += 1

    pairs = defaultdict(list)
    for r in rows:
        pairs[r["pair_id"]].append(r["action_ok"])
    pair_both = sum(1 for v in pairs.values() if v and all(v))

    return {
        "method": name, "status": "ok",
        "run_config": run_config,
        "n_cases": len(rows),
        "rows": rows,
        "unsupported_calls_allowed": (len(allowed), len(unsupported)),
        "unsupported_calls_detected": (len(detected), len(unsupported)),
        "supported_calls_blocked": (len(blocked), len(supported)),
        "verifier_failures": (len(failures), len(rows)),
        "verifier_failure_cases": [r["case_id"] for r in failures],
        "next_action_accuracy": (sum(r["action_ok"] for r in rows), len(rows)),
        "unnecessary_clarification": (len(unnecessary_clarify), len(rows)),
        "arg_level": (n_args_correct, n_args),
        "arg_by_category": {k: {"correct": v[0], "total": v[1]}
                            for k, v in sorted(by_cat.items())},
        "arg_confusion": {f"{e}->{p}": n for (e, p), n in
                          sorted(conf.items(), key=lambda kv: str(kv[0]))},
        "pair_both_correct": (pair_both, len(pairs)),
        "latency_s_mean": sum(lat) / len(lat),
        "latency_s_median": sorted(lat)[len(lat) // 2],
        "latency_s_p95": sorted(lat)[max(0, int(0.95 * len(lat)) - 1)],
        "latency_s_max": max(lat),
        "n_parse_errors": sum(1 for r in rows
                            if r["error"] or r.get("parse_ok") is False),
        "token_usage_total": {
            k: sum(u.get(k, 0) for u in usage if isinstance(u.get(k), (int, float)))
            for k in {kk for u in usage for kk in u}
        } if usage else None,
        "token_usage_per_case": usage if usage else None,
    }


def _frac(t: tuple[int, int] | None) -> str:
    if not t:
        return "n/a"
    return f"{t[0]}/{t[1]} ({(t[0] / t[1] if t[1] else 0):.0%})"


def format_report(results: list[dict]) -> str:
    lines = ["# Argument-verification development results (20 paired dev cases)",
             "", "Counts are numerator/denominator; percentages are on n=20 development cases, not a benchmark.",
             ""]
    hdr = ["method", "status", "next-action", "unsup. allowed", "unsup. detected",
           "sup. blocked", "verifier fail", "unnec. clarify", "arg findings",
           "pairs both correct", "lat mean/median/p95/max (s)", "tokens"]
    lines.append("| " + " | ".join(hdr) + " |")
    lines.append("|" + "---|" * len(hdr))
    for r in results:
        if r["status"] != "ok":
            lines.append(f"| {r['method']} | {r['status']} |" + " — |" * (len(hdr) - 2))
            continue
        lat = "{:.4f}/{:.4f}/{:.4f}/{:.4f}".format(
            r["latency_s_mean"], r["latency_s_median"],
            r["latency_s_p95"], r["latency_s_max"])
        tok = r.get("token_usage_total")
        tok_s = ", ".join(f"{k}={v}" for k, v in tok.items()) if tok else "—"
        lines.append("| {} | ok | {} | {} | {} | {} | {} | {} | {} | {}/{} | {} | {} |".format(
            r["method"], _frac(r["next_action_accuracy"]),
            _frac(r["unsupported_calls_allowed"]), _frac(r["unsupported_calls_detected"]),
            _frac(r["supported_calls_blocked"]), _frac(r["verifier_failures"]),
            _frac(r["unnecessary_clarification"]), _frac(r["arg_level"]),
            *r["pair_both_correct"], lat, tok_s))
    for r in results:
        if r["status"] != "ok":
            continue
        lines += ["", f"### {r['method']}: argument findings by expected category"]
        for cat, v in r["arg_by_category"].items():
            lines.append(f"- {cat}: {v['correct']}/{v['total']}")
    return "\n".join(lines)
