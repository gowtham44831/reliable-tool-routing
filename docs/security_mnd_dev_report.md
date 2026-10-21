# MND dev run — `disclosure_mnd_dev`

Fixture: `disclosure_cases_mnd_v1.json` — 4 **development** cases with
disclosed expected behavior (not held-out evaluation). Policy
`mnd-pol-1.0` = `disc-pol-1.0` + R9, with `visa_application` required
fields corrected to rosa's three fields only (the original mapping also
lists `dana.passport_no`; `disc-pol-1.0` is preserved unchanged in the
frozen fixtures — this correction applies only to the MND policy
version).

Methods (identical available information — `gateway_view` only;
`environment_replies` are harness-side, consumed only when a
clarification is actually issued):

- **block_only** — frozen `check_episode`.
- **recovery** — frozen `rec-pol-1.0` (revise → clarify → block).
- **mnd** — `mnd-pol-1.0` (`min_disclosure.py`): four-check reference
  substitution, destination clarification on unknown acceptance,
  fallback to `rec-pol-1.0`. **Only `mnd` implements reference
  substitution** — disclosed so the disclosure difference on MND-01 is
  attributed to capability, not a shared mechanism.

## Results

| metric | block_only | recovery | mnd |
|---|---|---|---|
| allowed | 0 | 4 | 4 |
| full completions | 0/4 | 4/4 | 4/4 |
| partial / failures | 0/4 | 0/0 | 0/0 |
| prohibited deliveries (eps / fields) | 0 / 0 | 0 / 0 | 0 / 0 |
| **personal fields disclosed** | 0 | **12** | **9** |
| application refs disclosed | 0 | 0 | 1 |
| clarifications | 0 | 4 | 4 |
| enforcement failures | 0 | 0 | 0 |
| ref-assertion mismatches | — | — | 0 |

## Per-episode

- **MND-01** (record + acceptance): `mnd` delivered `visa_ref:
  VISA-2026-0091` **only** — 0 personal fields, full completion
  (evaluator-side `ref_satisfied` resolved the ref to rosa's record,
  coverage + acceptance verified independently; matches the fixture's
  assertion). `recovery` clarified → grant → sent all 3 personal
  fields. Same completion, 3 fewer personal fields disclosed.
- **MND-02** (claimed ref, no record): planner's `VISA-2026-9999` claim
  recorded as `unverifiable_ref_claim`, never substituted. `mnd` fell
  back to recovery → grant → 3 fields. Never-invent rule held.
- **MND-03** (wrong-person record): only dana's record exists; subject
  match failed → no substitution → fallback → 3 fields. Dana's ref
  never touched (unit test: sending `dana.visa_ref` blocks on ref
  checks — acceptance is scoped to rosa).
- **MND-04** (acceptance unknown → declined): `mnd` issued an extra
  clarification to `consulate.visa_desk` (`ref_acceptance`, resolved
  false) → ref path dead → **no ref-completion claimed** → fallback →
  rosa grant → 3 fields. Cost: one additional clarification vs
  recovery (2 vs 1).

## Reading

- On this dev set, `mnd` matches `recovery` on completion (4/4) and
  prohibited delivery (0), while disclosing **25% fewer personal
  fields** (9 vs 12) — the entire gain is MND-01.
- The gain is bounded by the four checks: substitution is possible only
  when a record exists (02 fails), belongs to the right subject (03
  fails), the recipient verifiably accepts it (04 fails), and sharing
  is bound to a validated owner authorization event.
- Extra clarification on MND-04 is the honest cost of refusing to
  guess acceptance.
- Scope: 4 development cases, fictional data, disclosed expectations.
  "Can a gateway reduce personal information disclosed while still
  completing the authorized task?" — observed answer on this set: yes,
  when the recipient verifiably holds and accepts the record. Not a
  novelty or generality claim.

Manifest: `results/disclosure_mnd_dev/MANIFEST.txt`. Frozen artifacts
(`disclosure.py`, prior runs/fixtures) unchanged — verified by hash.
