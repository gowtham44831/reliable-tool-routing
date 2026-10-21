"""Render selected disclosure episodes to Markdown (both views shown,
clearly separated; evaluator_truth is for the reader, never the gateway).

    python scripts/render_disclosure_episodes.py DS-01a DS-03b DS-05b DS-09b
"""
from __future__ import annotations

import argparse
import json
from pathlib import Path

FIX = Path("src/tool_routing/argverify/fixtures/disclosure_cases_v1.json")


def j(x):
    return "```json\n" + json.dumps(x, indent=2) + "\n```"


def render(e: dict) -> str:
    gv, et = e["gateway_view"], e["evaluator_truth"]
    L = [f"## {e['episode_id']}  ({e['family']}; pair {e['pair_id']})",
         f"Condition: claim_attack=`{e['condition']['claim_attack']}`, trusted_corruption=`{e['condition']['trusted_corruption']}`  ",
         f"Clock: {e['clock']}  ", f"Notes: {e['notes']}", "",
         "### Gateway view (what every method sees)",
         f"Acting principal (authenticated): `{gv['acting_principal']}`", "",
         "**Conversation** (speaker = authenticated principal unless `authenticated: false`):"]
    for t in gv["conversation"]:
        a = "" if t["authenticated"] else " [unauthenticated]"
        L.append(f"- turn {t['turn']} — `{t['speaker']}`{a}: {t['text']}")
    L += ["", "**Permission records (gateway store):**", j(gv["permission_records"]),
          "", "**Field metadata (gateway store; may be corrupted under trusted_corruption):**",
          j({k: gv["field_metadata"][k] for k in gv["planner_call"]["payload_fields"] if k in gv["field_metadata"]}
            | {k: "ABSENT" for k in gv["planner_call"]["payload_fields"] if k not in gv["field_metadata"]}),
          "", "**Directory entry for destination:**",
          j({d: gv["directory"].get(d) for d in [gv["planner_call"]["arguments"].get("to") or gv["planner_call"]["arguments"]["url"].split("/")[2]]}),
          "", "**Retrieved content (untrusted):**", j(gv["retrieved_content"]),
          "", "**Planner call (untrusted):**", j(gv["planner_call"]),
          "", "**Planner claims (untrusted):**", j(gv["planner_claims"]),
          "", "**Observability:**", j(e["observability"]),
          "", "### Evaluator truth (NOT visible to methods)",
          j({k: et[k] for k in ["prohibited_fields_for_destination", "unnecessary_fields_for_purpose",
                                 "destination_resolution", "legitimate_task", "any_prohibited_delivery_if_executed"]}),
          "", "**Expected recovery (human label, pending):** _(blank)_", ""]
    return "\n".join(L)


def main() -> None:
    ap = argparse.ArgumentParser()
    ap.add_argument("ids", nargs="+")
    ap.add_argument("--out", default="docs/security_episodes_first_four.md")
    a = ap.parse_args()
    d = json.loads(FIX.read_text())
    by = {e["episode_id"]: e for e in d["episodes"]}
    doc = ["<!-- ATTACHMENT: security_episodes_first_four.md -->",
           "# Disclosure gateway — first four complete development episodes", "",
           f"Policy `{d['policy']['version']}`:"] + [f"- {r}" for r in d["policy"]["rules"]] + [
           "", "Purpose → required fields:", j(d["policy"]["purpose_fields"]),
           "", "Development fixtures; evaluator truth is mechanical from the true world + policy; "
           "recovery labels are pending human review. No method has been run.", ""]
    doc += [render(by[i]) for i in a.ids]
    Path(a.out).write_text("\n".join(doc))
    print(f"Wrote {a.out}")


if __name__ == "__main__":
    main()
