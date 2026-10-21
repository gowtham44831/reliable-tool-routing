# Human review workflow

There are now four review sheets. The milestone-1 `review.csv` is
described first (unchanged); the three milestone-2 sheets written by
`scripts/audit_evaluation.py` into `results/evaluation_audit/review/`
are described in "Milestone-2 review sheets" below. All sheets are
regenerated deterministically from the raw data and are git-ignored
(ToolRet text is not redistributed; see `docs/dataset.md`).

**General rules for every sheet**

* Never fill `human_reviewed` for a row you have not finished. Nothing
  in this repository fills it automatically.
* Judge from the request text and the tool documentation only. Do not
  look at model predictions or scores while judging (the milestone-2
  sheets do not show them on purpose).
* "Tool satisfies the request" means: calling this tool (with
  reasonable arguments taken from the request) would accomplish what the
  user asked, without needing another tool. Calling the *same* tool
  several times (e.g. "for January 15 and also February 20") still
  counts as single-tool.
* Use `unclear` rather than guessing. Record why in `reviewer_notes`.
* Ideally two reviewers per row; keep each reviewer's copy separate and
  record `reviewer_id` so agreement can be computed later.

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

## Milestone-2 review sheets

### A. `single_multi_tool_review_sample.csv` (+ `single_multi_tool_review_labels_long.csv`)

100 original ToolRet requests, 20 per pilot subset, drawn with a fixed
seed from all 1,895 downloaded requests (not just the 500-query pilot).
Within `apibank`, `apigen` and `metatool`, half the draws come from
requests with 2+ annotated tools (oversampled, because that is where the
alternatives-vs-joint question arises); `gorilla-huggingface` and
`toolalpaca` have only 1-label requests. `sampling_weight` =
stratum population / stratum sample size; use it to reweight any
estimate back to the subset population. `pilot_split` says whether the
request was in the pilot dev/val/test split or unused.

`annotated_tools_detail` lists every annotated tool with its name and
(truncated) description; the long CSV has the full description and
parameters, one row per annotated tool.

Fill in:

* `judgment_request_type`: `single-tool` (one tool, possibly called more
  than once, satisfies the whole request) | `multi-tool` (two or more
  *different* tools are needed together) | `unclear`.
* `judgment_label_relation`: `alternatives` (each annotated tool alone
  would satisfy the request) | `jointly_required` (the annotated tools
  are each needed for different parts) | `mixed` | 
  `not_applicable_one_label` | `unclear`. Do **not** assume
  multiple labels are alternatives.
* `judgment_labels_complete`: `yes` | `no` (you know of / can see an
  obviously valid tool that is not annotated -- note it) | `unclear`.

### B. `distractor_top1_review.csv`

One row per (val/test query, added distractor) where BM25 or the
embedding baseline ranked an *added distractor* first in the
`distractors_added` scenario. The current metrics count every such
selection as an error only because the distractor is not in the
annotated label set. Fill `judgment_distractor_satisfies_request`
(`yes` | `no` | `unclear`). `methods_with_this_top1` is shown only so
rows can be traced; ignore it when judging.

### C. Bounded-catalog answerability set (`bounded_catalog_review_items.csv`, `bounded_catalog_review_tools.csv`)

40 items (8 per subset), each a request plus a catalog of at most 15
tools, drawn only from requests **not** used in the pilot dev/val/test
splits. Read **every** tool for the item in the tools CSV, then fill in
the items CSV:

* `judgment_any_tool_satisfies`: `yes` | `no` | `unclear`.
* `judgment_satisfying_tool_ids`: every tool ID in this item's catalog
  that satisfies the request (`; `-separated), empty if none.
* `judgment_request_type`: as in sheet A.

`bounded_catalog_review_KEY_do_not_open_before_review.csv` records
which construction condition each item came from (annotated tools kept
vs. removed). Do not open it until your judgments are final. The
condition is *not* the answer: removed items can still be answerable via
another tool, and kept items can be unanswerable if the annotation is
wrong. Only this set (after review) can support true-(un)answerability
metrics, and only for these bounded catalogs -- not for full-corpus or
reduced-catalog benchmark claims.

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
