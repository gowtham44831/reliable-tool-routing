"""Reclassify clarification requests from a SAVED eval run into:
affirmative / declined / unanswered / invalid_reply.

The frozen runner's `resolved` flag conflates declined with unanswered
(resolved only means "the request produced what was needed"). This
script reads results.json + the fixture's environment_replies and
reclassifies post-hoc — no methods are re-run.

    python scripts/report_clarifications.py \
        --fixture .../disclosure_cases_mnd_eval2_v1.json \
        --results results/disclosure_mnd_eval2_v1/results.json
"""
from __future__ import annotations

import argparse
import json
from pathlib import Path


def classify(c: dict, reply: dict | None) -> str:
    if reply is None:
        return "unanswered" if not c.get("resolved") else "affirmative"
    kind = c.get("kind")
    if kind == "ref_acceptance":
        if reply.get("kind") != "ref_acceptance":
            return "invalid_reply"
        return "affirmative" if reply.get("accepts") is True \
            else "declined"
    if kind == "record_selection":
        if reply.get("kind") != "record_selection":
            return "invalid_reply"
        # resolved already encodes "named an eligible record"
        return "affirmative" if c.get("resolved") else "invalid_reply"
    # grant-style clarify (recover_episode): a consumed reply that
    # grants nothing is answered-but-not-authorizing
    if reply.get("kind"):  # reply was for a different question type
        return "invalid_reply"
    if c.get("resolved") and not reply.get("grants_fields"):
        return "invalid_reply"  # consumed but authorized nothing
    if c.get("resolved"):
        return "affirmative"
    if reply.get("denies_fields") or not reply.get("grants_fields"):
        return "declined"
    if "does not match this action" in (c.get("note") or ""):
        return "invalid_reply"
    return "declined" if c.get("resolved") is False else "affirmative"


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--fixture", required=True)
    ap.add_argument("--results", required=True)
    args = ap.parse_args()
    fix = json.loads(Path(args.fixture).read_text())
    replies = {e["episode_id"]: e["environment_replies"]
               for e in fix["episodes"]}
    res = json.loads(Path(args.results).read_text())
    table = {}
    details = []
    for method, rows in res.items():
        if not isinstance(rows, list):
            continue
        counts = {"affirmative": 0, "declined": 0, "unanswered": 0,
                  "invalid_reply": 0}
        for row in rows:
            for c in row.get("clarifications", []):
                target = c.get("to") or c.get("from")
                cls = classify(c, replies[row["episode_id"]].get(target))
                counts[cls] += 1
                details.append({"episode": row["episode_id"],
                                "method": method, "target": target,
                                "kind": c.get("kind", "grant"),
                                "class": cls})
        table[method] = counts
    hdr = ["method", "affirmative", "declined", "unanswered",
           "invalid_reply"]
    print("  ".join(h.ljust(16) for h in hdr))
    for m, c in table.items():
        print("  ".join([m.ljust(16)] +
                        [str(c[k]).ljust(16) for k in hdr[1:]]))
    Path(args.results).with_name("clarification_classes.json") \
        .write_text(json.dumps({"summary": table,
                                "details": details}, indent=2))
    print("wrote clarification_classes.json")


if __name__ == "__main__":
    main()
