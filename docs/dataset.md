# Dataset notes: ToolRet

## Source and revision

* Project/code: https://github.com/mangopy/tool-retrieval-benchmark (Apache-2.0
  license on the code repository). Paper: Shi et al., "Retrieval Models
  Aren't Tool-Savvy: Benchmarking Tool Retrieval for Large Language
  Models" (ACL 2025), arXiv:2503.01763.
* Data: Hugging Face datasets
  [`mangopy/ToolRet-Queries`](https://huggingface.co/datasets/mangopy/ToolRet-Queries)
  and [`mangopy/ToolRet-Tools`](https://huggingface.co/datasets/mangopy/ToolRet-Tools).
* Revisions actually downloaded for this milestone's pilot (see
  `data/raw/toolret/manifest.json`, not committed to git):
  * `ToolRet-Queries` commit `b8c76ad3349ff17497b6bdb28bb5b8f61a0f6445`
  * `ToolRet-Tools` commit `e06c38c75612b6536bd959e08cdd345894aba6a7`
  * Per-file SHA-256 checksums are recorded in the same manifest.

## License / redistribution

The HF dataset cards for `ToolRet-Queries` and `ToolRet-Tools` do **not**
carry an explicit `license:` tag in their YAML metadata (checked via
`.../raw/main/README.md` on both repos). The code repository that
produced them is Apache-2.0. ToolRet itself aggregates **35 upstream
benchmarks** (ToolBench, APIBank, Gorilla, ToolAlpaca, RestGPT, TaskBench,
etc.), each of which has its own original license. We were not able to
verify a single blanket redistribution license for the combined corpus in
the time available for this milestone.

**Consequence for this repo:** raw ToolRet files are downloaded on demand
by `scripts/download_toolret.py` into `data/raw/` and are **git-ignored**,
never committed. Treat ToolRet as "available for research use via the
official Hugging Face dataset", not as freely redistributable; verify the
relevant upstream license before any redistribution of derived data beyond
local research use.

## Schema (as actually observed in the downloaded parquet files)

`ToolRet-Queries` (one subset/config per upstream source benchmark, split
name `"queries"`):

| field | type | notes |
|---|---|---|
| `id` | string | unique within a subset, e.g. `apibank_query_5` |
| `query` | string | natural-language request |
| `instruction` | string | an LLM-authored task description, not used here |
| `labels` | string | **JSON-encoded** list of `{"id", "doc", "relevance"}` |
| `category` | string | `"web"` \| `"code"` \| `"customized"` -- which `ToolRet-Tools` corpus bucket the referenced tools live in |

`ToolRet-Tools` (3 configs: `code`, `customized`, `web`; split name
`"tools"`):

| field | type | notes |
|---|---|---|
| `id` | string | e.g. `apibank_tool_33`, `gorilla_tensor_tool_0` |
| `documentation` | string | **JSON-encoded** dict; schema varies by source (see below) |

`documentation` schema varies a lot across the 35 upstream sources. Two
observed shapes:
* flat: `{"name", "description", "parameters": {...}}`
* API-call style (seen for `code` / Gorilla-TensorHub-like entries):
  `{"domain", "framework", "functionality", "api_call", "api_arguments", ...}`

`src/tool_routing/data/toolret_adapter.py::_parse_tool_doc` normalizes both
into `(name, description, parameters)`, with graceful fallbacks (covered
by `tests/test_toolret_adapter.py`).

### Relevance labels

In every sampled row, `relevance` was `1` for every listed label (we did
not observe `0`/negative entries in `labels` -- negatives, if the ToolRet
protocol uses any, are implicit: "everything else in the corpus"). We
treat `relevance >= 1` as "known valid" and anything else (including
missing/unparseable) as not valid. **This is a known-incomplete positive
label set**: a tool absent from `labels` is not proven invalid, only
unannotated. All "accuracy"/"risk" metrics in this repo carry that caveat
(see `docs/review_workflow.md` for how to get an audited, trustworthy
unanswerable set).

### Single-tool vs. multi-tool requests

We could not find a field in the released schema, nor a clear statement in
the dataset card, that marks whether a query requires one tool, a choice
between several alternative tools, or a *combination* of several distinct
tools used together. Per the task instructions, we made a **heuristic,
subset-level** classification based on the name/known purpose of each
subset's *upstream* benchmark (see
`src/tool_routing/data/toolret_constants.py` for the full list and
reasoning):

* Treated as single-tool / alternatives-only: `apibank`, `apigen`,
  `gorilla-*`, `metatool`, `reversechain`, `rotbench`, `tool-be-honest`,
  `toolace`, `toolalpaca`, `toolbench*`, `toolemu`, `tooleyes`, `toolink`,
  `toollens`, `ultratool`.
* Excluded as explicitly multi-step/compositional: `appbench`,
  `autotools-*`, `craft-*`, `gpt4tools`, `gta`, `mnms`, `restgpt-*`,
  `t-eval-*`, `taskbench-*`.

This is **not verified per-query** -- it is entirely plausible some
"single-tool" subsets still contain a few composite requests, and vice
versa. Treat the single/multi-tool split as a documented limitation, not a
ground truth.

### Known limitations of the labels

* Known-incomplete positives (see above): absence from `labels` != proven
  invalid.
* Relevance semantics beyond binary `1` were not observed/explored further
  given time constraints.
* Tool `documentation` schema heterogeneity means the auto-extracted
  `name`/`description` is sometimes a best-effort fallback (e.g. derived
  from an `api_call` string) rather than a clean human-written name.
* Per-subset tool "family" grouping (`Tool.tool_family`, derived by
  splitting the tool ID on `_tool_`) is a heuristic over ID strings, not a
  verified ontology. ID prefixes do **not** line up 1:1 with
  `ToolRet-Queries` subset names (e.g. the subset `gorilla-huggingface`
  maps to tool-ID family `gorilla_huggingface`; the subset
  `tool-be-honest` maps to family `tool_be_honest`; some `autotools-*`
  query subsets map to differently-named `webtools_*` tool families). We
  resolve this in `cli.py::_load_toolret` by deriving each subset's actual
  family set from the real labels on its own queries (not by guessing a
  name transform), which is exact but still only as good as the
  underlying ID-splitting heuristic.

## Catalog scope: reduced-catalog pilot vs. official full-corpus evaluation

ToolRet's official protocol retrieves over an entire `code`/`customized`/
`web` corpus bucket (3.8k / 3.4k / 37.3k tools respectively) per query.
For this milestone's pilot (`configs/pilot_toolret.yaml`), each query's
"original" catalog is instead **all tools sharing the query's own source
subset's tool family** (e.g. all ~3.6k `apigen` tools, or all 101
`apibank` tools) -- a **reduced-catalog pilot**, as explicitly allowed by
the task instructions when the full corpus is the "natural" catalog. The
held-out distractor pool is every other downloaded tool (other subsets),
genuinely absent from a query's own original catalog.

We did **not** run the official full-corpus (`web`/`code`/`customized`)
evaluation in this milestone: with up to 37k tools per query it is a
substantially heavier embedding/indexing job, and the task instructions
ask not to run expensive jobs without first reporting their size. This is
left as explicit future work (see the final handoff notes).

## Pilot subsets actually downloaded

`apibank` (101), `apigen` (1000), `gorilla-huggingface` (500),
`toolalpaca` (94), `metatool` (200) -- 1895 queries total before the
~500-query pilot cap. See `configs/pilot_toolret.yaml`.
