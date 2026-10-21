"""Run the argument-verification development evaluation.

    python scripts/run_argverify_eval.py [--methods schema,rule,ai]

Writes results/argverify_dev/{report.md,results.json}. The AI verifier
needs ARGVERIFY_BASE_URL (+ARGVERIFY_API_KEY, +ARGVERIFY_MODEL); without
them it is reported as not_run. This is a 20-case development set, not a
benchmark.
"""
from __future__ import annotations

import argparse
import json
from pathlib import Path

from tool_routing.argverify import evaluate as E
from tool_routing.argverify.llm import ai_verifier
from tool_routing.argverify.llm_providers import ai_verifier_provider
from tool_routing.argverify.llm_v2 import ai_verifier_v2
from tool_routing.argverify.methods import (cross_argument_baseline,
                                            rule_baseline, schema_baseline)
from tool_routing.argverify.schema import FIXTURE_PATH, load_cases


def main() -> None:
    ap = argparse.ArgumentParser()
    ap.add_argument("--fixture", default=str(FIXTURE_PATH))
    ap.add_argument("--methods", default="schema,rule,crossrule,ai")
    ap.add_argument("--out-dir", default="results/argverify_dev")
    args = ap.parse_args()

    cases = load_cases(args.fixture)
    fns = {"schema": schema_baseline, "rule": rule_baseline,
           "crossrule": cross_argument_baseline, "ai": ai_verifier,
           "ai_v2": ai_verifier_v2, "ai_provider": ai_verifier_provider}
    results = []
    for name in args.methods.split(","):
        results.append(E.evaluate(cases, fns[name.strip()], name))

    out = Path(args.out_dir)
    out.mkdir(parents=True, exist_ok=True)
    (out / "results.json").write_text(json.dumps(results, indent=2, default=str))
    report = E.format_report(results)
    (out / "report.md").write_text(report)
    print(report)
    print(f"\nWrote {out}/{{report.md,results.json}}")


if __name__ == "__main__":
    main()
