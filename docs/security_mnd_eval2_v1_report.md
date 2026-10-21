# mnd-eval-2.0 report — `disclosure_mnd_eval2_v1`

Author-designed evaluation set (12 episodes, separately authored world:
tomas.wei / lena.farouk / omar.haddad; combined ambiguity × restriction
× permission × acceptance factors; varied record order). **Not an
independent benchmark** — cases were designed with knowledge of
eval-v1 failures; labels authored separately and frozen before
execution (`results/disclosure_mnd_eval2_v1/EVAL_MANIFEST.md`). Single
run; no methods were fixed within the run.

Primary arms: **mnd_v1_2** vs **ref_conservative** vs **recovery**.
Historical baselines: block_only, ref_optimistic (ablation), mnd(1.1p).

## Requested breakdown (12 episodes)

| metric | recovery | ref_conservative | **mnd_v1_2** | mnd-1.1p | ref_opt* | block_only |
|---|---|---|---|---|---|---|
| full completions | 6 | 6 | **8** | 6 | 5 | 0 |
| partial_permitted | 0 | 0 | 0 | 0 | 0 | 0 |
| correct stops | 3 | 1 | **4/4** | 1 | 1 | 4 |
| unnecessary blocks | 2 | 1 | **0** | 0 | 0 | 8 |
| violation episodes | 1 | 4 | **0** | 5 | 6 | 0 |
| — unauthorized disclosures | 0 | 0 | 0 | 0 | 0 | 0 |
| — restriction violations (fields) | 3 | 0 | 0 | 0 | 0 | 0 |
| — wrong-application deliveries | 0 | 4 | 0 | 5 | 6 | 0 |
| raw personal fields | 21 | 12 | **12** | 12 | 9 | 0 |
| refs disclosed | 0 | 6 | **4** | 7 | 8 | 0 |
| clarifications | 14 | 6 | **11** | 6 | 3 | 0 |

### Clarification outcome classes (post-hoc from saved traces)

The runner's `resolved` flag conflated declines with silence.
`scripts/report_clarifications.py` reclassifies every recorded request
against the episode's `environment_replies` — no methods re-run
(`results/disclosure_mnd_eval2_v1/clarification_classes.json`):

| class | recovery | ref_conservative | mnd_v1_2 | mnd-1.1p | ref_opt |
|---|---|---|---|---|---|
| affirmative | 7 | 4 | **7** | 5 | 3 |
| declined (answered "no") | 0 | 0 | 1 | 1 | 0 |
| unanswered (silence) | 1 | 0 | 2 | 0 | 0 |
| invalid reply (wrong kind / can't authorize) | 6 | 2 | 1 | 0 | 0 |

- recovery's 6 `invalid_reply` are grant requests answered by
  `record_selection` replies (E2-04/05/08) — it consumed a reply meant
  for a question it cannot ask.
- mnd_v1_2's lone `invalid_reply` is E2-05: the owner named a
  superseded record — an answer, but it cannot authorize an
  ineligible ref.
- The 2 `unanswered` are E2-11 (silence) — correct stop either way.

*ablation.

## Capability matrix (explicit baseline differences)

| capability | block_only | recovery | ref_conservative | ref_optimistic | mnd-1.1p | mnd_v1_2 |
|---|---|---|---|---|---|---|
| substitution (ref for fields) | — | — | yes | yes | yes | yes |
| acceptance clarification (ask destination) | — | — | — | assumes | yes | yes |
| restriction enforcement (R10) | — | — | — | — | — | yes |
| eligible-record filtering (status/expiry) | — | — | — | — | — | yes |
| selection clarification (R11) | — | — | — | — | — | yes |
| owner-grant clarification | — | yes | via fallback | via fallback | via fallback | via fallback |

**For a future component comparison:** give all compared methods the
same mandatory safety checks (deny-wins, expiry, restriction
enforcement, eligibility filtering) and vary ONLY the clarification
capability — that isolates what asking buys over assuming/holding.
Today v1.2 bundles three additions, so its margin over conservative
is not attributable to any single one.

## What separated the arms

- **Wrong-application elimination**: on E2-04/05/10/11 every older
  substitution arm delivered the first-listed record — the
  **superseded** `VISA-4090` (order deliberately varied). v1.2's
  verified-constraint filter removed it: clarify → select → deliver
  `VISA-4120` (E2-04), hold correctly (E2-05 ineligible reply, E2-10
  no eligible, E2-11 silence).
- **Restriction**: only v1.2 enforces "reference only" — recovery
  violated it on E2-10 (3 raw fields); E2-04/05 it simply failed or
  stopped.
- **E2-07 nuance**: optimistic delivered a ref the destination had
  **declined** (violation); v1.2 + mnd clarified, got the decline,
  fell back to fields (full). The decline is now classified
  `declined` — an answered request (see table above).
- **E2-08**: only v1.2 ran both clarification kinds (record_selection
  + ref_acceptance) → ref-only full; conservative couldn't select and
  failed without delivering.
- **E2-09**: all arms dropped omar's wrong-subject ref correctly —
  acceptance subject-binding catches it.
- **E2-12**: purpose-specific acceptance held — ref-only full on the
  insurance_claim contract (name+dob+policy_no).

## Cost picture

v1.2 spends more clarifications (11) than conservative (6) — the price
of asking instead of assuming. It buys: 4/4 required stops, zero
violations of any class, 8/12 full including 4 ref-only deliveries.

## Honest scope

This set was authored after eval-v1 to exercise v1.2's new machinery;
it shows the mechanism works on designed cases, including combined
factors and order traps. It does not establish performance on
unanticipated structure. Unexpected outcome worth preserving:
conservative/recovery failing E2-08 entirely (record-selection replies
carry no field grants) — an interaction the spec didn't predict.
