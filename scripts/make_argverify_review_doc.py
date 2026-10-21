"""Generate a blinded human-review document for argument-verification cases.

    python scripts/make_argverify_review_doc.py

Writes docs/argument_verification_review_round1.md plus an empty response
CSV at results/argverify_review/round1_responses.csv. Expected findings,
expected actions, label rules and explanations are NOT rendered -- the
reviewer sees only what a verifier would see, and answers in the CSV.

Reviewer fields per case: per-argument finding
(supported|missing|contradicted|wrong_entity|unresolved), next action
(proceed|retrieve|clarify|reject_proposed_call), free-text reasoning.
"""
from __future__ import annotations

import csv
import json
from pathlib import Path

from tool_routing.argverify.schema import FIXTURE_PATH, load_cases

REVIEW_IDS = ["TB-01b", "TB-08b", "TB-02b", "TB-05b", "TB-09b"]
OUT_DOC = Path("docs/argument_verification_review_round1.md")
OUT_CSV = Path("results/argverify_review/round1_responses.csv")

FINDINGS = "supported | missing | contradicted | wrong_entity | unresolved"
ACTIONS = "proceed | retrieve | clarify | reject_proposed_call"


def render(case) -> str:
    lines = [f"## Case {case.case_id}", ""]
    lines.append("**Conversation:**")
    for t in case.conversation:
        lines.append(f"- turn {t['turn']} ({t.get('speaker', '?')}): {t['text']}")
    lines += ["", "**Tool contract:**", "```json",
              json.dumps(case.tool_schema, indent=2), "```",
              "", "**Prior tool results:**", "```json",
              json.dumps(case.prior_tool_results, indent=2), "```",
              "", "**Proposed call:**", "```json",
              json.dumps(case.proposed_tool_call, indent=2), "```",
              "", "**Claimed evidence manifest:**", "```json",
              json.dumps([{
                  "argument_name": e.argument_name,
                  "proposed_value": e.proposed_value,
                  "source_references": [
                      {"ref": s.ref, "entity": s.entity, "tier": s.tier,
                       "timestamp": s.timestamp, "match": s.match}
                      for s in e.source_references],
                  "transformation_or_default": e.transformation_or_default,
              } for e in case.evidence_manifest], indent=2), "```",
              "", "**Context:**", "```json",
              json.dumps(case.context, indent=2), "```", ""]
    lines.append(f"### Reviewer answers for {case.case_id}")
    for arg in case.proposed_tool_call.get("arguments", {}):
        lines.append(f"- `{arg}` finding ({FINDINGS}):")
    lines.append(f"- next action ({ACTIONS}):")
    lines.append("- reasoning:")
    lines.append("")
    return "\n".join(lines)


def main() -> None:
    import argparse
    ap = argparse.ArgumentParser()
    ap.add_argument("--fixture", default=str(FIXTURE_PATH))
    ap.add_argument("--ids", nargs="*", default=None,
                    help="case ids to include (default: REVIEW_IDS or all)")
    ap.add_argument("--title", default="Argument verification -- human review, round 1 (5 cases)")
    ap.add_argument("--out-doc", default=str(OUT_DOC))
    ap.add_argument("--out-csv", default=str(OUT_CSV))
    ap.add_argument("--disclosure", default=(
        "**Disclosure:** these five cases were previously shown and "
        "discussed (with labels) in the project conversation, so this "
        "review validates task interpretation and label sanity — it is "
        "NOT a blind evaluation. Results remain exploratory."))
    args = ap.parse_args()
    ids = args.ids or REVIEW_IDS
    cases_all = load_cases(args.fixture)
    if args.ids is None and args.fixture != str(FIXTURE_PATH):
        ids = [c.case_id for c in cases_all]
    cases = {c.case_id: c for c in cases_all}
    out_doc, out_csv = Path(args.out_doc), Path(args.out_csv)
    doc = [f"<!-- ATTACHMENT: {out_doc.name} -->",
           f"# {args.title}", "",
           "Each case shows only verifier-visible inputs: conversation, tool",
           "contract, prior tool results, proposed call, claimed evidence",
           "manifest, and context. Expected labels are intentionally absent.", "",
           "**Disclosure:** these five cases were previously shown and",
           "discussed (with labels) in the project conversation, so this",
           "review validates task interpretation and label sanity — it is",
           "NOT a blind evaluation. Results remain exploratory.", "",
           "For every proposed argument mark one finding:",
           f"  {FINDINGS}", "",
           "Then pick one next action:",
           f"  {ACTIONS}", "",
           "Record answers in results/argverify_review/round1_responses.csv",
           "(columns: case_id, argument_findings as `arg:finding;...`,",
           "next_action, reasoning, reviewer_id).", ""]
    for cid in REVIEW_IDS:
        doc.append(render(cases[cid]))
    OUT_DOC.write_text("\n".join(doc))

    OUT_CSV.parent.mkdir(parents=True, exist_ok=True)
    with OUT_CSV.open("w", newline="") as f:
        w = csv.writer(f)
        w.writerow(["case_id", "argument_findings", "next_action",
                    "reasoning", "reviewer_id"])
        for cid in REVIEW_IDS:
            w.writerow([cid, "", "", "", ""])
    print(f"Wrote {OUT_DOC} and {OUT_CSV}")


if __name__ == "__main__":
    main()
