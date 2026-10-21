# eval-v4 freeze — executed once under protocol

adapter-1.3 + url-gw-1.0 (unchanged); scripted calls; no model calls.
Expectations specified and frozen in docs/security_eval_v4_protocol.md
before execution (author-designed, not a preregistration record).

- `75361cd56b0835ba6fdb8272f8e813db97517af10fcb849159e3d8d5aa62db92`  scripts/run_eval_v4.py
- `3c3c75114e810298f0e6334f6265074e2f6b60e277dc8ae778874dfd3c8162f4`  scripts/run_url_eval_v2.py
- `435e932b59fda0de6a2c2a1b6dd960a2eb01bfb11756d644e6d0acc67df6e48e`  src/tool_routing/argverify/planner_adapter.py
- `87598dfb53222f9dedef7be375c92ee6c622128c1a8e60e1ab19150ca94dfbb6`  src/tool_routing/argverify/url_fetch_gateway.py
- `9f6f626f88a3cc59c55a9f98c8ce6e0ff237fbe643e9bdcafcc6c4a37efef0b3`  results/eval_v4/traces.json
- `cbc0307bb8df3cd489ffd7ed42accdd0292d9f1a6ac31855d9182e7452499058`  docs/security_eval_v4_protocol.md

Reproduce: `.venv/bin/python scripts/run_eval_v4.py`
