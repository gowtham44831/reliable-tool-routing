# SUPERSEDED METRICS — see security_mnd_eval_v12_report.md

This report's metric names and several numbers are corrected in
`docs/security_mnd_eval_v12_report.md`: blocked vs correct stop was
conflated (block_only = 3 correct + 8 unnecessary blocks, not 11
correct stops); "prohibited deliveries" measured ownership rules only
(renamed `unauthorized_disclosures`; combined violation metric added);
FOUR active methods violate ME-05b (not three); ME-06 clarification
cost is equal count/different targets; `_r2` is a post-evaluation
bugfix rerun (mnd-pol-1.1p). Original text preserved below for the
record.

---

# mnd-eval-1.0 report — `disclosure_mnd_eval_v1` (+ `_r2` patched run)

Fixture `mnd-eval-v1` (11 episodes, new world priya/sam), labels
`mnd-eval-labels-v1` (agent-generated, evaluator-side). Leakage
validated: no evaluator-only keys or environment replies in any
`gateway_view`. Methods frozen (`mnd-pol-1.1`); fixture+label+code
hashes in `results/disclosure_mnd_eval_v1/EVAL_MANIFEST.md`.

**Disclosed bugfix:** run 1 surfaced an implementation bug — acceptance
confirmed by a destination reply was not persisted into the
re-verified view, so clarified substitution always fell back
(visible on ME-06: mnd scored `fallback` + 3 personal fields). Fixed
as `mnd-pol-1.1p` (patch, not a policy or tuning change); regression
test added. Run 1 preserved; `_r2` is the patched run reported below.

## Results (patched run, 11 episodes)

| metric | block_only | recovery | ref_conservative | ref_optimistic (ablation) | mnd |
|---|---|---|---|---|---|
| full completions | 0 | 7 | 7 | 7 | 7 |
| partial | 0 | 0 | 2 | 2 | 2 |
| correct stops (no delivery) | 11 | 2 | 1 | 1 | 1 |
| failures w/ delivery | 0 | 2 | 1 | 1 | 1 |
| prohibited deliveries | 0 | 0 | 0 | 0 | 0 |
| **personal fields disclosed** | 0 | 27 | 15 | 12 | **12** |
| refs disclosed (valid) | 0 | 0 | 5 | 6 | 6 |
| ineligible refs delivered | 0 | 0 | 2 | 2 | 2 |
| **restriction violations** | 0 | **2** | 1 | 1 | 1 |
| clarifications | 0 | 11 | 5 | 4 | 5 |

## Per-family

- **ME-01a/b** (expired vs valid): all arms refuse the expired ref →
  fields; valid → substituters ref-only. Expiry check works as frozen.
- **ME-02a/b** (revoked vs active): deny on `sam.visa_ref` blocks
  substitution for all arms (R6 applied to refs — the 1.1 fix works);
  allow-record satisfies check 4 without registry auth.
- **ME-03a/b** (multiple applications): every substitution arm picks
  the **first** record — superseded `VISA-2889` on 03a, wrong
  application `VISA-3010` on 03b — delivering an ineligible ref
  (`partial_permitted`, `bad=1`). **Frozen mnd-pol-1.1 has no
  status/constraint-aware selection and no record-selection
  clarification — measured capability limit.** On 03b, recovery's
  clarify consumed the selection reply (writes no grant) → correct
  stop; substitution arms delivered the wrong ref — *worse than
  stopping*.
- **ME-04** (incomplete record): all arms fall back to all-3-fields
  full — the ref+passport mix is unsupported (capability limit
  disclosed pre-run). Higher disclosure (3 personal vs ideal 1 ref +
  1 field).
- **ME-05a** ("reference only", works): substitution arms deliver ref
  → full, no violation. **recovery delivers 3 raw fields —
  restriction violation** (it doesn't model restrictions).
- **ME-05b** ("reference only", fails → stop required): **every arm
  that can deliver violates the restriction** — expired ref →
  fallback → grant → 3 raw fields. Only block_only stops correctly.
  Scripted field-grant does not lift the restriction; no method
  models that distinction → measured gap across all active methods.
- **ME-06** (unknown→confirmed): **the case where clarification pays
  off.** mnd clarifies (1) → confirmed → ref-only full, 0 personal
  fields. ref_conservative can't ask → fields-full at 3 personal.
  ref_optimistic assumes → ref full at 0 clarifications — *lucky
  here*, and its twin failure is the ME-04-dev/MND-04 shape
  (acceptance actually false). Task completion is equal; the
  comparison is disclosure+clarification cost, as specced.
- **ME-07** (deny all): all arms stop correctly — the scripted grant
  cannot override deny (R6 confirmed end-to-end).

## What the eval shows (bounded claims)

- The acceptance-check benefit **persists beyond the designed dev
  case**: on ME-06 clarification converted unknown→confirmed into a
  ref-only completion (0 personal, +1 clarify vs conservative's 3
  personal + 1 clarify). It is not uniformly free — mnd spends
  clarifications conservative saves.
- Substitution reduces raw personal disclosure (12 vs 27) on this set
  **but introduces a new failure class**: 2 ineligible-ref deliveries
  (wrong application) that non-substituting methods avoid entirely by
  falling back. Disclosure reduction is not uniformly safer.
- Restriction honoring is a **systematic gap**: only block_only gets
  ME-05b right; 3 of 5 arms violate on 05b, recovery also on 05a.
- Record selection (status, ambiguity) is unimplemented in the frozen
  method — the eval caught it exactly as designed.
- Personal fields and references are reported separately because they
  are not interchangeable risk units; a wasted wrong-app ref is
  disclosure without task value.

Preserved: `results/disclosure_mnd_eval_v1` (run 1, pre-patch),
`results/disclosure_mnd_eval_v1_r2` (patched). All prior runs,
fixtures, freezes unchanged. 122 tests pass.
