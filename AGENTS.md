# Agent notes for this repository

## Environment setup

```bash
python3.12 -m venv .venv
source .venv/bin/activate
pip install -e ".[data]"
```

On macOS Apple Silicon with a very new macOS version and a Homebrew
Python that predates it, `pip`/`ensurepip` can crash inside
`pip._vendor.truststore` (`platform.mac_ver()` returns `''`), and
`import xml.parsers.expat` can fail with `Symbol not found:
_XML_SetAllocTrackerActivationThreshold` (Homebrew Python's `pyexpat.so`
links against `/usr/lib/libexpat.1.dylib`, which on very new macOS lacks a
symbol it expects). Fix:

```bash
brew install expat
export DYLD_LIBRARY_PATH=/opt/homebrew/opt/expat/lib
```

Export `DYLD_LIBRARY_PATH` in every shell used for this project (or add it
to your shell rc) before running `pip`, `python -m tool_routing.cli`, or
`pytest`.

## Commands

* Tests: `python -m pytest -q` (fast, no network, 74 tests as of writing).
* Argument-verification dev eval (20 paired cases; methods schema, rule,
  crossrule run locally; AI verifier needs ARGVERIFY_BASE_URL
  [/API_KEY/MODEL], e.g. Ollama at http://localhost:11434/v1):
  `python scripts/run_argverify_eval.py`. Case review doc:
  `python scripts/make_case_review_doc.py`. Blinded human-review doc (5
  cases, no labels): `python scripts/make_argverify_review_doc.py`.
  Fixture: `src/tool_routing/argverify/fixtures/travel_cases.json` — keep
  pair members together in any future split. The slot-level rule baseline
  is frozen; cross-argument checks live in `cross_argument_baseline` and
  are reported separately. Input contract: docs/argument_verification_evidence_inputs.md.
* Blind labeling docs: `python scripts/make_labeling_doc.py --round 1`
  writes `results/evaluation_audit/human_labeling/bounded_labeling_round<N>.md`
  + a blank `responses/bounded_round<N>_responses.csv`;
  validate a completed round with `python scripts/validate_review.py --round N`.
  Never open `review/bounded_catalog_review_KEY_*.csv` during review.
* Evaluation audit (reads pilot outputs read-only, a few seconds, no model):
  `python scripts/audit_evaluation.py --config configs/pilot_toolret.yaml --pilot-dir results/toolret_pilot --out-dir results/evaluation_audit`.
  Write-up in `docs/evaluation_audit.md`; if you re-run it, re-copy
  `results/evaluation_audit/plots/*.png` to `docs/figures/`.
* Toy end-to-end smoke test: `python -m tool_routing.cli smoke-test`.
* Download real data: `python scripts/download_toolret.py --queries <subsets...>`
  (needs `pip install -e ".[data]"` and network access).
* Full pilot run: `python -m tool_routing.cli run --config configs/pilot_toolret.yaml`.

## Conventions

* Raw/downloaded datasets (`data/raw/`), caches (`data/cache/`), and run
  outputs (`results/`) are git-ignored. Never commit them.
* Every new metric/abstention/scenario behavior should get a test in
  `tests/` using the toy fixture (`tool_routing.data.toy_fixture`) or a
  small inline fixture -- avoid requiring real ToolRet data in tests.
* Don't claim benchmark results from the toy fixture; it exists only for
  pipeline testing (see its module docstring).
* Never overwrite `results/toolret_pilot/` (milestone-1 reference
  outputs); use `--output-dir` for new runs.
* The pilot test split is exploratory (it informed milestone 2). Do not
  tune on it. `configs/reserved_confirmatory_query_ids.json` is the fresh
  held-out pool; do not evaluate on it until the protocol is frozen.
* Pin `embedding.revision` to a full 40-hex HF commit SHA in configs.
