"""Emit one 5-case human-labeling batch from labelset_v2.

    python scripts/make_label_batch.py --batch 1

Cases are drawn in a fixed seeded order so pair members do not land in
the same batch where avoidable; pair ids, predictions, and labels are
NOT shown. Writes docs/argverify_label_batch_<n>.md and a blank
results/argverify_review/labelset_v2_batch<n>.csv with A/B/C fields plus
reviewer provenance columns.
"""
from __future__ import annotations

import argparse
import csv
import json
import random
from pathlib import Path

from tool_routing.argverify.policy import missing_required_args
from tool_routing.argverify.schema import load_cases

FIX = Path("src/tool_routing/argverify/fixtures/labelset_v2.json")
FINDINGS = "supported | missing | contradicted | wrong_entity | unresolved"
CITATION = "cited_ok | cited_wrong | uncited | cited_dangling"
ACTIONS = "proceed | retrieve | clarify | reject_proposed_call"
GUIDE_VERSION = "2.1"

POLICIES = """## Applicable policies (fictional; apply to every item)

AcmeAir (book_flight):
- P1 International itineraries require a passport valid on the travel date.
- P2 A booking reserves `num_passengers` seats under the lead traveler;
  `traveler_name`/`passenger_dob` describe the lead traveler only; other
  names are collected at check-in. N must be grounded in a stated count or
  an enumerated list of people.
- P3 The travel date must not precede `context.current_time`.
- `flight_id` quotes are valid for 24 h after the search timestamp.

Hotel / car / ticket tools: logical constraints only — checkout after
checkin, dropoff after pickup, quantity <= `max_per_order`, section in
`sections_available`.

Selection discretion: NOT granted by default. A real candidate matching
the request is not hallucinated because others also match; but if several
options satisfy the stated constraint and the user gave no preference or
grant ("any is fine", "you pick"), the chosen value is `unresolved`.

Partial task: a call covering one leg / one traveler of a larger request
may execute UNLESS the user coupled the parts ("both or neither").

Authorization: profile-tier evidence counts only if
`context.profile_authorized` is true.

Evidence may be drawn from the WHOLE context; cite completeness is judged
separately (A').
"""


def batch_order(cases, seed=2026):
    """Deterministic order that separates pair members: shuffle pairs,
    emit all 'a' members first then all 'b' members."""
    rng = random.Random(seed)
    pairs = sorted({c.pair_id for c in cases})
    rng.shuffle(pairs)
    by_pair = {p: sorted([c for c in cases if c.pair_id == p], key=lambda c: c.case_id)
               for p in pairs}
    first = [by_pair[p][0] for p in pairs]
    second = [by_pair[p][1] for p in pairs]
    rng.shuffle(second)
    return first + second


def render(case, n: int) -> str:
    scope = list(case.proposed_tool_call.get("arguments", {})) + missing_required_args(case)
    man = [{"argument_name": e.argument_name, "proposed_value": e.proposed_value,
            "source_references": [{"ref": s.ref, "entity": s.entity, "tier": s.tier,
                                   "timestamp": s.timestamp, "match": s.match}
                                  for s in e.source_references],
            "transformation_or_default": e.transformation_or_default}
           for e in case.evidence_manifest]
    L = [f"## Item {n}  (case {case.case_id})", "", "**Conversation:**"]
    L += [f"- turn {t['turn']} ({t.get('speaker', '?')}): {t['text']}" for t in case.conversation]
    L += ["", "**Context (application-supplied; assume correct):**", "```json",
          json.dumps(case.context, indent=2), "```",
          "", "**Tool contract:**", "```json", json.dumps(case.tool_schema, indent=2), "```",
          "", "**Prior tool results:**", "```json",
          json.dumps(case.prior_tool_results, indent=2), "```",
          "", "**Proposed call:**", "```json",
          json.dumps(case.proposed_tool_call, indent=2), "```",
          "", "**Planner's claimed evidence manifest (a claim, not ground truth):**",
          "```json", json.dumps(man, indent=2), "```", "",
          f"### Answers — item {n}",
          "**A. Grounding** (one of: " + FINDINGS + ")  |  **A'. Citation** (" + CITATION + ")"]
    L += [f"- `{a}`:  A=        A'=" + ("   _(absent required argument; A' = n/a)_"
                                        if a in missing_required_args(case) else "")
          for a in scope]
    L += ["", "**B. Compliance** (compliant | violates: <policy/constraint> | unknown):", "- ",
          "", "**C. Execution decision** (execute | do_not_execute):", "- ",
          "", f"**D. Acceptable recovery actions** (one or more, preferred first; {ACTIONS}):", "- ",
          "", "**Underspecified?** (no | yes: <what is missing>):", "- ",
          "", "**Reasoning:**", "- ", ""]
    return "\n".join(L)


def main() -> None:
    ap = argparse.ArgumentParser()
    ap.add_argument("--batch", type=int, required=True)
    ap.add_argument("--size", type=int, default=5)
    args = ap.parse_args()
    cases = load_cases(FIX)
    order = batch_order(cases)
    chunk = order[(args.batch - 1) * args.size: args.batch * args.size]
    if not chunk:
        raise SystemExit("batch out of range")
    out_doc = Path(f"docs/argverify_label_batch_{args.batch}.md")
    out_csv = Path(f"results/argverify_review/labelset_v2_batch{args.batch}.csv")
    doc = [f"<!-- ATTACHMENT: {out_doc.name} -->",
           f"# Argument verification — labeling batch {args.batch} (labelset_v2, guide v{GUIDE_VERSION})", "",
           "Read docs/argument_verification_annotation_guide.md first.",
           "No predictions, labels, or pair groupings are shown. Judge each",
           "item on its own.", "",
           "**Exposure record:** these cases were authored by the assistant for",
           "this study (author-influenced evaluation cases); they have not been",
           "labeled or run through any method. Record your own `ai_assistance`",
           "and `prior_exposure` in the CSV.", "",
           POLICIES]
    doc += [render(c, i + 1) for i, c in enumerate(chunk)]
    out_doc.write_text("\n".join(doc))
    out_csv.parent.mkdir(parents=True, exist_ok=True)
    with out_csv.open("w", newline="") as f:
        w = csv.writer(f)
        w.writerow(["case_id", "guide_version", "A_grounding", "A_citation",
                    "B_compliance", "C_execution", "D_recovery_actions",
                    "underspecified", "reasoning", "reviewer_id",
                    "ai_assistance", "prior_exposure"])
        for c in chunk:
            w.writerow([c.case_id, GUIDE_VERSION] + [""] * 10)
    print(f"Wrote {out_doc} ({len(chunk)} items) and {out_csv}")
    print("cases:", [c.case_id for c in chunk])


if __name__ == "__main__":
    main()
