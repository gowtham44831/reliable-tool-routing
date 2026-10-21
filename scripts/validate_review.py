"""Validate a submitted bounded-catalog labeling responses CSV.

    python scripts/validate_review.py --round 1

Checks completeness (all fields, all items), allowed values, catalog ID
consistency, and flags ambiguous/contradictory answers. Prints a report;
exits nonzero if issues remain.
"""
from __future__ import annotations

import argparse
import sys

from tool_routing.audit.labeling_doc import load_items_and_catalogs, validate_responses

ROUNDS = {1: (0, 10), 2: (10, 40)}


def main() -> None:
    ap = argparse.ArgumentParser()
    ap.add_argument("--review-dir", default="results/evaluation_audit/review")
    ap.add_argument("--responses", default=None,
                    help="default: results/evaluation_audit/human_labeling/responses/bounded_round<N>_responses.csv")
    ap.add_argument("--round", type=int, required=True, choices=sorted(ROUNDS))
    args = ap.parse_args()

    items, _ = load_items_and_catalogs(args.review_dir)
    lo, hi = ROUNDS[args.round]
    batch = items[lo:hi]
    path = args.responses or f"results/evaluation_audit/human_labeling/responses/bounded_round{args.round}_responses.csv"
    report = validate_responses(path, batch)
    print(f"rows={report['n_rows']} expected={report['n_items_expected']} "
          f"complete_and_consistent={report['n_complete_and_consistent']}")
    if report["issues"]:
        print("\nIssues:")
        for i in report["issues"]:
            print(f"- {i}")
        sys.exit(1)
    print("All rows complete and consistent.")


if __name__ == "__main__":
    main()
