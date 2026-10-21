"""Build disclosure_cases_mnd_v1_1.json — the SAME four development
episodes re-versioned to mnd-pol-1.1. mnd-v1 stays frozen byte-identical.

mnd-pol-1.1 = mnd-pol-1.0 + permission-record consultation on ref fields
(deny-wins R6, unexpired allow records may satisfy check 4) + application
record expiry checked on every verification pass including
post-clarification.

    python scripts/build_disclosure_mnd_v1_1.py
"""
from __future__ import annotations

import json
from pathlib import Path

BASE = Path(__file__).resolve().parent.parent / \
    "src/tool_routing/argverify/fixtures/disclosure_cases_mnd_v1.json"
OUT = Path(__file__).resolve().parent.parent / \
    "src/tool_routing/argverify/fixtures/disclosure_cases_mnd_v1_1.json"

d = json.loads(BASE.read_text())
d["version"] = "mnd-v1.1"
d["note"] += " Re-versioned to mnd-pol-1.1 (record consultation + expiry " \
             "on ref fields); content otherwise identical to mnd-v1."

R9 = ("R9 application_ref fields: may leave only to a destination that holds "
      "the subject's application record (registry match on "
      "destination+purpose+subject), that accepts this reference type for "
      "this task, where sharing is bound to a validated owner authorization "
      "event OR an unexpired permission record, and where no deny record "
      "applies (deny wins, R6). Expired records and planner/retrieved refs "
      "are unverifiable — checked on every verification pass.")

for ep in d["episodes"]:
    pol = ep["gateway_view"]["policy"]
    pol["version"] = "mnd-pol-1.1"
    pol["rules"] = pol["rules"][:-1] + [R9]
d["policy"]["version"] = "mnd-pol-1.1"
d["policy"]["rules"] = d["policy"]["rules"][:-1] + [R9]

OUT.write_text(json.dumps(d, indent=1))
print(f"Wrote {OUT}: {len(d['episodes'])} episodes @ mnd-pol-1.1")
