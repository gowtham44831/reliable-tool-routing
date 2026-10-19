# Human review workflow

`tool-routing run` writes a `review.csv` into its output directory (one
row per test-split query, `original` scenario only) with these columns:

* `query_id`, `query_text`, `scenario`, `catalog_id`
* `known_valid_tool_ids` -- the (known-incomplete) positive label set
* `bm25_top_tool_ids` / `bm25_top_descriptions` -- BM25's top-3 candidates
* `embedding_top_tool_ids` / `embedding_top_descriptions` -- embedding
  baseline's top-3 candidates
* `answerability_status` -- pre-filled as `uncertain` unless the source
  Request already had a non-"unreviewed" status
* `reviewer_relevant_tool_ids` -- **blank, for the reviewer to fill in**
* `reviewer_notes` -- **blank, for the reviewer to fill in**

## What a reviewer should do

For each row:

1. Read `query_text` and the candidate descriptions from both baselines.
2. Decide `answerability_status`:
   * `answerable` -- at least one genuinely valid tool exists in the
     catalog for this query (it does not have to be one of the shown
     candidates -- check `known_valid_tool_ids` too).
   * `unanswerable` -- after inspecting the shown candidates (and ideally
     searching the broader catalog, not just the top-3 shown here), no
     tool actually satisfies the request.
   * `uncertain` -- leave as `uncertain` if genuinely unsure; do **not**
     guess `unanswerable` just because nothing in the top-3 looks right.
3. Fill `reviewer_relevant_tool_ids` with any tool IDs (from the shown
   candidates or otherwise) the reviewer independently confirms are valid.
4. Use `reviewer_notes` for anything ambiguous, e.g. "query is multi-tool",
   "candidate looks relevant but API signature doesn't match", etc.

## Why this matters for metrics

* **False-action rate** and **abstention-rate-on-answerable** (see
  `evaluation/metrics.py`) are only computed over rows whose
  `answerability_review_status` is `answerable` or `unanswerable` --
  i.e. **audited** rows. Rows left as `unreviewed`/`uncertain` are
  excluded from those specific metrics (they still count toward
  coverage/top-1-accuracy/selective-risk, which rely only on the
  known-valid-tool label set, not on answerability review).
* Reviewing only the **top-3 candidates per baseline** does **not** prove
  the rest of the catalog has no valid tool. An `unanswerable` judgment
  should reflect a genuine best-effort look, not just "top-3 look wrong".
* Keep a running count of `uncertain` rows and report it alongside any
  answerability-based claim (`reporting/review_export.py::count_uncertain`).
  A large uncertain count means answerability claims for that run are weak.

## Current status in this milestone

No manual review pass has been performed yet in this repository -- every
query currently has `answerability_review_status = "unreviewed"` except
the toy fixture (manually authored as `"answerable"` by construction).
This means false-action-rate and abstention-rate-on-answerable report as
`n/a` in `REPORT.md` for the real ToolRet pilot run. Running an actual
review pass over `results/<run>/review.csv` and re-importing the
`answerability_status`/`reviewer_relevant_tool_ids` columns back into the
Request data is the natural next step before making any abstention claim
on real data.
