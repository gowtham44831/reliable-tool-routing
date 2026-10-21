# MND dev run 3 — `disclosure_mnd_dev3` (mnd-pol-1.1, 5 methods)

New run ID; `disclosure_mnd_dev` and `disclosure_mnd_dev2` preserved.
Fixture `mnd-v1.1` — same four episodes re-versioned to `mnd-pol-1.1`
(v1 frozen byte-identical).

**Policy delta (1.0 → 1.1):** permission records are consulted on ref
fields — deny-wins (R6 → `policy_conflict`), unexpired allow records
may satisfy check 4 — and application-record expiry is checked on
**every** verification pass, including post-clarification.

**Methods:**
- `block_only`, `recovery` — frozen, unchanged.
- `ref_conservative` — **new baseline**: substitutes only on verified
  acceptance; otherwise authorized fallback WITHOUT recipient
  clarification. Tests the value of the clarification step.
- `ref_optimistic` — **acceptance-check ablation** (intentionally
  weaker): assumes unknown acceptance. Not a proposed method.
- `mnd` — `mnd-pol-1.1`.

## Results

| metric | block_only | recovery | ref_conservative | ref_optimistic | mnd |
|---|---|---|---|---|---|
| full completions | 0/4 | 4/4 | 4/4 | 3/4 | 4/4 |
| failures | 4 | 0 | 0 | 1 | 0 |
| prohibited deliveries | 0 | 0 | 0 | 0 | 0 |
| personal fields disclosed | 0 | 12 | 9 | 6 | 9 |
| refs disclosed | 0 | 0 | 1 | 2 | 1 |
| clarifications | 0 | 4 | 3 | 2 | 4 |

## What each comparison isolates

- **mnd vs recovery** — capability: substitution reduces personal
  disclosure (−3 fields on MND-01) at equal completion.
- **mnd vs ref_optimistic** (ablation) — check-3 consequence: assumed
  acceptance on MND-04 → ref delivered that the recipient cannot
  resolve → task failure + wasted identifier. Narrow supported claim:
  *checking acceptance avoided one unsuccessful ref-only delivery in
  the development set.* Whether the benefit persists beyond the
  designed case is what `mnd-eval-1.0` tests.
- **mnd vs ref_conservative** — clarification value: on MND-04
  identical outcomes except +1 clarification for mnd (the dest clarify
  that declined). The benefit of asking shows only when acceptance is
  unknown to the gateway but true in the world — no such dev case
  exists yet; eval spec covers it.

Targeted tests added (`test_min_disclosure.py`, now 121 total): deny-
wins on ref fields, expired record blocked at substitution AND at
re-verification, allow record satisfying check 4 without registry
auth, conservative arm issuing no destination clarification, expiry
winning even after an accepting reply.
