# MND dev run 2 — `disclosure_mnd_dev2` (with substitution baseline)

Post-freeze run (new run ID; `disclosure_mnd_dev` + FREEZE.md preserved).
Same fixture (`mnd-v1`, hash unchanged). Adds **`ref_optimistic`** — a
substitution-capable baseline using the SAME registry records and the
SAME `mnd_check_episode` checks as `mnd`; the only difference is check
3: absent `reference_acceptance` is *assumed* instead of clarified.
Comparing against a method that cannot substitute would not establish
any advantage beyond adding the capability — this arm isolates what the
acceptance check + clarification actually buy.

## Results

| metric | block_only | recovery | ref_optimistic | mnd |
|---|---|---|---|---|
| allowed | 0 | 4 | 4 | 4 |
| full completions | 0/4 | 4/4 | **3/4** | 4/4 |
| failures | 4 | 0 | **1** | 0 |
| prohibited deliveries | 0 | 0 | 0 | 0 |
| personal fields disclosed | 0 | 12 | 6 | 9 |
| refs disclosed | 0 | 0 | **2** | 1 |
| clarifications | 0 | 4 | 2 | 4 |

## Per-episode

- **MND-01**: `ref_optimistic` and `mnd` identical — acceptance was
  explicitly listed, so nothing was assumed. Both deliver the ref only;
  full completion; 0 personal fields.
- **MND-02 / MND-03**: all substitution methods refuse equally (no
  record / subject mismatch) → fallback → identical to recovery.
- **MND-04** — the isolation case: `ref_optimistic` assumes acceptance
  → delivers `rosa.visa_ref` → the recipient **cannot resolve it in
  truth** → `unresolved_refs_delivered`, task **failure**, and an
  identifier disclosed for zero benefit. `mnd` clarifies → declined →
  falls back to fields → full completion at 3 personal fields + 1 extra
  clarification.

## Reading

- mnd vs recovery shows the capability gain (−3 personal fields,
  MND-01); mnd vs ref_optimistic shows the *verification* gain
  (MND-04: assumed acceptance produces a task failure plus a wasted
  identifier disclosure; clarified acceptance avoids both).
- **Personal details and references are reported separately on
  purpose**: fewer raw fields does not mean proportionately less
  privacy risk — a reference is itself an identifier and reveals that
  an application exists. The honest metric is both counts, plus
  whether each disclosure accomplished the task.
- Scope unchanged: 4 development cases, fictional data, disclosed
  expectations. No novelty/generality claim.

Manifest: `results/disclosure_mnd_dev2/MANIFEST.txt`. Frozen milestone
unchanged: `results/disclosure_mnd_dev/FREEZE.md`.
