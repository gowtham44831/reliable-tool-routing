# camel component eval freeze — executed once

- Input: saved eval-v4 serialized requests (`results/eval_v4/traces.json`
  sha256 `9f6f626f88a3cc...`, untouched).
- Vendored: CaMeL policy component @ upstream `f083b6b396399d3b3c7f2ddaf613a5945eaf32d8`,
  `src/third_party/camel_policy/` — mechanical `camel.` → `third_party.camel_policy.`
  import rewrite ONLY; no semantic changes. Apache-2.0 LICENSE
  carried. See docs/camel_vendor_record.md.
- New dep: pydantic==2.11.5.
- Arms: `camel-arms-1.0` (camel-base-policy descriptive,
  camel-m3-intent mechanism comparison). Capability inputs
  adapter-supplied; CaMeL planner/provenance/control-flow not
  evaluated. Inspection shared — cannot establish advantage over
  CaMeL's own IFC tracking.
- Result: camel-m3-intent agrees with M3 on 8/8; base policy blocks
  all protected egress (descriptive); SY2 divergence on the empty
  carrier is the conservative F5 mirror. Zero enforcement failures.
- Hashes: manifest.json.
- Reproduce: `.venv/bin/python scripts/run_camel_component_eval.py`
