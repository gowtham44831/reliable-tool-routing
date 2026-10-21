"""Render the travel-booking dev fixture as a readable review document.

    python scripts/make_case_review_doc.py [--out docs/argument_verification_cases.md]

Includes the labels (this document is for a HUMAN reviewer checking the
fixture; verifiers never see it -- they get Case.public_view() only).
"""
from __future__ import annotations

import argparse
import json
from pathlib import Path

from tool_routing.argverify.schema import FIXTURE_PATH, load_cases


def render(cases) -> str:
    L = ["# Travel-booking verification cases (10 pairs, development set)",
         "",
         "Within each pair the proposed `book_flight` call is **identical**; only the evidence "
         "changes. Labels are derived from the `label_rules` stated per case. "
         "Fictional people, mocked tools, no real credentials.",
         ""]
    by_pair = {}
    for c in cases:
        by_pair.setdefault(c.pair_id, []).append(c)
    for pid, members in by_pair.items():
        a, b = sorted(members, key=lambda c: c.case_id)
        L += [f"## {pid}: {a.case_id} vs {b.case_id}", ""]
        L.append(f"Proposed call (identical in both): "
                 f"`{json.dumps(a.proposed_tool_call['arguments'])}`")
        L.append("")
        for c in (a, b):
            L += [f"### {c.case_id} — expected action: `{c.expected_next_action}`", ""]
            ctx = c.context
            L.append(f"- flying_person={ctx['flying_person']}, "
                     f"profile_authorized={ctx['profile_authorized']}, "
                     f"now={ctx['current_time']}")
            for t in c.conversation:
                L.append(f"- **{t['speaker']} t{t['turn']}:** {t['text']}")
            for tr in c.prior_tool_results:
                L.append(f"- **tool {tr['tool']}** ({tr.get('timestamp','?')}): "
                         f"`{json.dumps(tr['output'])[:400]}`")
            L.append("")
            L.append("| argument | expected finding |")
            L.append("|---|---|")
            for arg, f in c.expected_argument_findings.items():
                if f != "supported":
                    L.append(f"| {arg} | **{f}** |")
            if all(f == "supported" for f in c.expected_argument_findings.values()):
                L.append("| (all) | supported |")
            L.append("")
            L.append("**Rules:** " + " ".join(f"({i+1}) {r}" for i, r in enumerate(c.label_rules)))
            L.append("")
            L.append(f"**Why:** {c.ground_truth_explanation}")
            L.append("")
    return "\n".join(L)


def main() -> None:
    ap = argparse.ArgumentParser()
    ap.add_argument("--fixture", default=str(FIXTURE_PATH))
    ap.add_argument("--out", default="docs/argument_verification_cases.md")
    args = ap.parse_args()
    Path(args.out).write_text(render(load_cases(args.fixture)))
    print(f"Wrote {args.out}")


if __name__ == "__main__":
    main()
