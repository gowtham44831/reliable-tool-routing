# Reliable Neural Tool Selection When Available Tools Change

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

41 tests, all against the toy fixture and small inline fixtures (no
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
evaluation yet), and the next experiment justified by observed failures
(baseline top-1 accuracy of ~43-52% on the original catalog means
selective-risk-based abstention collapses coverage to near zero at
reasonable risk targets -- motivating a trained/calibrated approach as
the next step, not yet attempted here).
