# multistep-pilot-v2 freeze — PREPARED, NOT RUN

Same episodes/difficulty/authorization as v1; ONLY the tool
schema changed to contract B (example-based), validated on
dev tasks 7/7 vs A's 4/7 under frozen acceptance criteria.
Runner v1.1: raw output saved before parse/validate/bind on
every turn; schema rejects vs ContextBindingError separated.

- `088fa6b13079a0d99de713928bf57e01eab51b9a689de6da141b9e9f448b6de5`  scripts/run_multistep_pilot.py
- `b9fe54a006643a979007f2060ebfa3e703492809852e1c5a4af85b47e40a967b`  src/tool_routing/argverify/fixtures/multistep_cases_v2.json
- `ac12ec2ed72774ef5b95fd844890f2b847797206263286115591452b1b99cda1`  src/tool_routing/argverify/fixtures/interface_dev_cases_v1.json
- `509c410fdaf00fa8bb901c09f9a589a08eaf8a256f1f2d6e1240ed93dddd5a33`  scripts/dev_interface_eval.py
- `3bb0b741145f9b7178fde738baf5273e3c33765783de36b4957c81a05a7ac6e7`  src/tool_routing/argverify/block_feedback.py
- `435e932b59fda0de6a2c2a1b6dd960a2eb01bfb11756d644e6d0acc67df6e48e`  src/tool_routing/argverify/planner_adapter.py
- `87598dfb53222f9dedef7be375c92ee6c622128c1a8e60e1ab19150ca94dfbb6`  src/tool_routing/argverify/url_fetch_gateway.py

Run (after approval): `.venv/bin/python scripts/run_multistep_pilot.py --v2`

## Executed

- traces.json sha256 c8ed8fec10d2c0bc7e77522d66a0c4123375e1dd2efe0fa7fc1a86510774df04
- development-informed rerun (contract B); NOT a fresh independent evaluation
