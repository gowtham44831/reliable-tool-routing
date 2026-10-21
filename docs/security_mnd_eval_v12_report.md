# mnd-eval-1.0 report (corrected metrics) + `mnd-pol-1.2` dev arm

This report supersedes `security_mnd_eval_v1_report.md` on metric
definitions and arithmetic; run artifacts are preserved
(`disclosure_mnd_eval_v1` run 1, `disclosure_mnd_eval_v1_r2`
**post-evaluation bugfix rerun**, `disclosure_mnd_eval_v12` this run).

## Metric corrections applied

- **"Blocked" ≠ "correct stop."** A stop counts as correct only where
  no delivery was required (labels: stop required = ME-05b, ME-07;
  stop acceptable = ME-03b). block_only's 11 no-deliveries resolve to
  **3 correct stops + 8 unnecessary blocks**.
- **Violation classes separated.** `unauthorized_disclosures` =
  ownership/permission violations only (was "prohibited deliveries").
  Added `restriction_violations` (raw fields under "reference only")
  and `wrong_application_deliveries` (authorized-class ref that
  resolves to an ineligible/wrong record — never counted as
  `partial_permitted`). `policy_violations_combined` = sum of all
  three. The earlier report's "prohibited deliveries = 0" measured
  ownership rules only.
- **Arithmetic corrections.** FOUR active methods violate ME-05b
  (recovery, ref_conservative, ref_optimistic, mnd — all deliver the
  scripted grant's 3 raw fields; earlier text said three). ME-06
  clarification cost was misreported: mnd clarifies the DESTINATION
  once; ref_conservative clarifies the OWNER once — equal count (1),
  different targets; the cost difference is in disclosure, not
  clarification count.
- **Scope.** ME-06 shows the acceptance-check benefit on *another
  deliberately constructed case* — it does not establish
  generalization beyond designed cases.
- `_r2` is a **post-evaluation bugfix rerun** (mnd-pol-1.1p, code hash
  `8e834f0ea46d…`); run 1 preserved at `disclosure_mnd_eval_v1`.

## Corrected results (11 episodes, patched methods)

| metric | block_only | recovery | ref_conservative | ref_optimistic* | mnd (1.1p) | **mnd_v1_2** |
|---|---|---|---|---|---|---|
| full completions | 0 | 7 | 7 | 7 | 7 | **9** |
| partial_permitted | 0 | 0 | 0 | 0 | 0 | 0 |
| correct stops | 3 | 2 | 1 | 1 | 1 | **2/2 required** |
| unnecessary blocks | 8 | 0 | 0 | 0 | 0 | 0 |
| unauthorized_disclosures | 0 | 0 | 0 | 0 | 0 | 0 |
| restriction_violations | 0 | 6 fields | 3 | 3 | 3 | **0** |
| wrong_application_deliveries | 0 | 0 | 2 | 2 | 2 | **0** |
| **policy_violations_combined** | 0 | 6 | 5 | 5 | 5 | **0** |
| personal fields disclosed | 0 | 27 | 15 | 12 | 12 | **9** |
| refs disclosed | 0 | 0 | 5 | 6 | 6 | 6 |
| clarifications | 0 | 11 | 5 | 4 | 5 | 5 |

*ablation, intentionally weaker.

## mnd-pol-1.2 (post-eval development version)

Three additions over 1.1p, each targeting a measured gap:

- **Restriction enforcement**: `disclosure_restriction` is checked
  before every delivery and before fallback — under "reference only"
  no raw protected field may leave; if the ref path fails the method
  holds (`hold_restriction` → correct stop). Result: ME-05a ref-only
  full; ME-05b correct stop; the ONLY arm with zero violations.
- **Verified-constraint selection**: eligible = status `approved` +
  subject/destination/purpose + unexpired — never list order.
  ME-03a selects `VISA-3010` (superseded record filtered out) →
  ref-only full, where all 1.1 arms delivered the wrong application.
- **Record-selection clarification**: on ambiguity, owner clarify with
  `kind: record_selection`; the reply must name an existing eligible
  record. ME-03b clarifies → `VISA-2888` → ref-only full; prior arms
  delivered wrong-app or stopped.

Still open capability limits: mixed ref+field payloads (ME-04 falls
back to all-fields full — disclosed pre-eval, unchanged); multi-subject
substitution untested.

## Bounded conclusion

On this designed eval set, mnd-pol-1.2 is the only arm with **zero
policy violations of any class**, 9/11 full completions, 2/2 required
stops, and the lowest raw personal disclosure (9 fields) — at 5
clarifications vs mnd's 5 (different targets: owner-selection and
destination-acceptance vs owner-grants). This is an engineering
demonstration on fictional cases designed to exercise each check, not
evidence of generalization. Next meaningful test would be cases where
the adjudicated behaviors conflict (e.g., restriction + ambiguous
records + revoked ref simultaneously).
