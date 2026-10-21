# Reliable Neural Tool Selection When Available Tools Change

> **Current project status, standing caveats, and all later milestones
> (argument verification, security extension): see
> [`docs/STATUS.md`](docs/STATUS.md).**

**Research question:** Can a compact neural approach reduce incorrect tool
selections when tools are added or removed, while maintaining useful
request coverage?

**This is milestone 1: datasets, baselines, and evaluation.** It does
**not** train or propose a new model, and it does **not** claim
publication-ready or novel results. See `results/*/REPORT.md` after a run
for measured findings, and the "Final handoff" section below for an
honest summary of what was and wasn't done.

## Scope

* Python 3.12, `pyproject.toml`, installable with plain `pip` (no `uv`
  requirement).
* CPU by default; `sentence-transformers`/`torch` will use MPS/CUDA if
  available and requested via config (`embedding.device`).
* CLI only (`tool-routing` / `python -m tool_routing.cli`) -- no web UI,
  no FastAPI/MCP server.
* No paid APIs or credentials required. No tool is ever executed/called;
  only text descriptions are ranked.

## Setup

```bash
python3.12 -m venv .venv
source .venv/bin/activate
pip install -e ".[data]"   # ".[data]" only needed for scripts/download_toolret.py
```

Core dependencies: numpy, pandas, rank-bm25, sentence-transformers (pulls
in torch and transformers), scikit-learn, matplotlib, PyYAML, pytest.
Exact versions that were verified to work together are pinned in
`requirements-lock.txt` (generated with `pip freeze`); `pyproject.toml`
uses compatible ranges around those versions.

**Expected download sizes**, so you can decide before running anything:
* `pip install -e ".[data]"`: ~350-400 MB total, dominated by `torch`
  (CPU wheel, ~130 MB) and `transformers`/`scikit-learn`/`matplotlib`.
* The default embedding model
  (`sentence-transformers/all-MiniLM-L6-v2`) is ~90 MB, downloaded once on
  first use and cached by `sentence-transformers` under `~/.cache/huggingface`.
* `scripts/download_toolret.py` (optional, real data) downloads ~10 MB of
  parquet files for the 5 pilot query subsets + all 3 ToolRet-Tools
  corpora (~44.5k tool docs total).

### macOS note (Apple Silicon, very new macOS versions)

If `pip install`/`ensurepip` crashes inside `pip._vendor.truststore` with
`ValueError: invalid literal for int() with base 10: ''`, or any `import
xml.parsers.expat` fails with `Symbol not found:
_XML_SetAllocTrackerActivationThreshold`, your Homebrew Python/libexpat
predates your macOS version and `platform.mac_ver()`/`pyexpat` break. We
worked around this locally with:

```bash
brew install expat
export DYLD_LIBRARY_PATH=/opt/homebrew/opt/expat/lib   # put in your shell rc
```

This is an environment compatibility issue, not something specific to
this repository.

## Running

```bash
# Toy fixture smoke test (no network, no real data; NOT a benchmark)
python -m tool_routing.cli smoke-test

# Download a pilot slice of the real ToolRet benchmark (network + pip install -e ".[data]")
python scripts/download_toolret.py --queries apibank apigen gorilla-huggingface toolalpaca metatool

# Validate the downloaded data
python -m tool_routing.cli validate --dataset toolret --config configs/pilot_toolret.yaml

# Run the full pilot (splits -> catalogs -> BM25+embedding retrieval -> thresholds -> metrics -> review.csv -> report)
python -m tool_routing.cli run --config configs/pilot_toolret.yaml
```

Outputs land in `output_dir` from the config (default
`results/toolret_pilot/`, git-ignored): `REPORT.md`, `risk_coverage.png`,
`metrics.json`, `predictions.jsonl`, `catalog_manifests.jsonl`,
`splits.json`, `thresholds.json`, `review.csv`, `run_metadata.json`,
`validation_report.txt`.

## Repository layout

```
src/tool_routing/
  data/        # schema, validation, toy fixture, ToolRet adapter
  retrieval/   # BM25 and frozen-embedding baselines (shared interface)
  scenarios/   # dev/val/test split construction, catalog scenario generation
  evaluation/  # prediction records, abstention policies, metrics, bootstrap CIs
  reporting/   # review CSV export, run metadata, Markdown report + plots
  cli.py
configs/       # pilot_toy.yaml, pilot_toolret.yaml
scripts/       # download_toolret.py
tests/         # pytest suite (toy-fixture based, no network)
docs/          # dataset.md, review_workflow.md
docker-compose.opensearch.yml   # optional, NOT required, NOT auto-started
```

## Design decisions worth knowing about

* **Known-incomplete labels.** `known_valid_tool_ids` on a `Request` is
  the benchmark's annotated positive set, not a verified exhaustive one.
  "Incorrect" in all metrics means "outside that set", not "confirmed
  wrong". See `docs/dataset.md`.
* **Catalog scenarios** (`scenarios/catalog.py`): for every query we build
  `original`, `known_removed` (all annotated valid tools removed -- does
  *not* imply the request becomes unanswerable), and `distractors_added`
  (BM25-lexical-similarity-to-query distractors from a disjoint held-out
  pool). All three are built from the same base pool so every retriever
  sees identical catalogs.
* **Reduced-catalog pilot.** For ToolRet, "original" = all tools sharing
  the query's own source-subset tool family, not the full `code`/
  `customized`/`web` corpus (up to 37k tools). See `docs/dataset.md` for
  why, and what full-corpus evaluation would require.
* **Abstention policies** (`evaluation/thresholds.py`): `always_top1`,
  `score_threshold`, `margin_threshold`. Thresholds are selected on
  validation only (`select_threshold`) and then frozen for test; see
  `tests/test_thresholds.py` for a test that this boundary holds.
* **Per-tool embedding caching**, not per-catalog: most catalogs in this
  project share almost all of their tools (every query in a subset shares
  the same `original` pool; `known_removed`/`distractors_added` only
  change a few tools), so `retrieval/embeddings.py` caches one vector per
  distinct tool and assembles catalog matrices from that cache. This is
  what makes the real pilot run in a few minutes instead of a few hours.
* **Query-grouped bootstrap** (`evaluation/metrics.py::query_grouped_bootstrap_ci`):
  resamples whole queries (all of a query's scenario variants move
  together), not individual prediction rows, to avoid pseudo-replication.

## Deferred: OpenSearch BM25 adapter

Not implemented in this milestone. `docker-compose.opensearch.yml` is
provided for future local experimentation (pinned image, localhost-only
ports, health check, named volume, security plugin disabled and clearly
documented as local-only -- never started automatically). Implementing an
OpenSearch-backed retriever behind the same `BaseRetriever` interface
used by BM25/embeddings is deferred: it would require documenting
OpenSearch's analyzer/scoring configuration and treating its scores as a
genuinely separate experimental backend (its BM25 is not guaranteed to
match `rank_bm25`'s scores), which is out of scope for getting the core
dataset/baseline/evaluation pipeline working first.

## Tests

```bash
python -m pytest -q
```

61 tests (41 from milestone 1, 20 added for the milestone-2 audit:
Wilson intervals, review-sample stratification, catalog invariants,
threshold-selection traces, leakage checks, embedding cache keys), all
against the toy fixture and small inline fixtures (no
network, no model download), covering: relevance-label mapping, dup
IDs/missing fields/dangling refs/conflicting-label validation, "all known
valid tools removed", "genuine additions without duplicate IDs",
validation/test threshold-selection separation, hand-computed metrics,
zero-coverage/empty-catalog behavior, and deterministic/grouped split
construction.

## Final handoff

See `docs/dataset.md` and `docs/review_workflow.md` for the dataset
writeup, and the project handoff summary below (also in the task
conversation) for: what was implemented, exact commands run, actual pilot
findings on real ToolRet data, an error-analysis sample, what's
unverified/blocked (no human review pass yet; no official full-corpus
evaluation yet), and the next experiment justified by observed failures.

**Correction (milestone 2):** an earlier version of this paragraph said
"baseline top-1 accuracy of ~43-52%". The measured test-split values in
`results/toolret_pilot/metrics.json` are **43/100 (embedding) and 48/100
(BM25)** agreement with the known relevance labels on the `original`
catalog, i.e. 43-48%. 52% is BM25's test *selective risk* (52/100), not
an accuracy. See `docs/evaluation_audit.md` for the reconciliation,
per-split numbers with confidence intervals, and the diagnosis of why the
threshold policies reach (near-)zero test coverage.

## Milestone 2: evaluation audit

```bash
python scripts/audit_evaluation.py --config configs/pilot_toolret.yaml \
    --pilot-dir results/toolret_pilot --out-dir results/evaluation_audit
```

Reads the milestone-1 pilot outputs read-only (hash-verified before and
after) and writes exact count tables, Wilson intervals, paired bootstrap
comparisons, score/margin plots, catalog/leakage checks, and human-review
CSVs. Write-up: `docs/evaluation_audit.md`; reviewer instructions:
`docs/review_workflow.md`.

## Showcase release — egress gateway (milestones 3+)

The current supported path is the **`url_fetch` egress gateway,
`url-gw-1.1` (strict F5 by default)** plus `planner-adapter-1.3`
context binding. Earlier `disclosure.py`/`min_disclosure.py`
implementations are frozen predecessors; `f5_mode="legacy"` keeps
url-gw-1.0 behavior for reproduction. Exploratory and closed
directions live under `archive/` (labeled in `archive/README.md`).
Frozen experiment artifacts remain under `results/` — never
overwrite them.

### Quick start

```bash
python3.12 -m venv .venv && source .venv/bin/activate
pip install -e .            # core; ".[data]" only for ToolRet download
python -m pytest -q         # 181 core (186 with .[data])
python scripts/demo_showcase.py   # scripted 3-scene demo ->
                                  # results/demo_showcase/traces.json
```

The demo uses **scripted calls** on fictional data (unauthorized
disclosure blocked, authorized delivery permitted, the
sibling-carrier defect before/after the F5 fix). Live-model runs
(`scripts/run_multistep_pilot.py --v2`) additionally need a local
Ollama `qwen3:14b` endpoint; no paid APIs are used anywhere.

### Dependencies and licensing

- This repository: **MIT** (`LICENSE`; `pyproject.toml`).
- Vendored third-party code: `src/third_party/camel_policy/`
  contains a dependency closure of the released CaMeL policy
  components (upstream commit `f083b6b`), **Apache-2.0** — upstream
  license and notices preserved; modifications and rationale in
  `docs/camel_vendor_record.md`. It is used for a *component*
  comparison only — not a CaMeL reproduction.
- Runtime deps: `pydantic` (vendored CaMeL closure), plus the
  milestone-1 stack pinned in `requirements-lock.txt`.

### AI assistance

This project was developed with AI coding assistance (Devin,
Cognition) for implementation, evaluation harness code, and
documentation drafting. All security-relevant claims in
`docs/`/`results/` trace to saved artifacts; exploratory and
corrected work is labeled per milestone in `docs/STATUS.md`, and the
evidence-to-claim mapping is in `docs/claim_to_evidence.md`.

### Reports

- Technical report + reproduction commands: `docs/technical_report.md`
- Publication-pitch abstract: `docs/publication_abstract.md`
- Public-release checklist: `docs/release_checklist.md`
- Full milestone log: `docs/STATUS.md`
