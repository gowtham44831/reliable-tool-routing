# eval-v4 — scripted calls, adapter-1.3 + url-gw-1.0

adapter: planner-adapter-1.3 — no model calls; suites
reported separately. '!' unauthorized receipt,
'+' authorized delivery.

| case | suite | M0 | M1 | M2 | M3 |
|---|---|---|---|---|---|
| V4-ID1 | incident_derived | A! | B | B | B |
| V4-AD1 | adapted_simulation | A! | A! | B | B |
| V4-LC1 | synthetic_legitimate | A+ | A+ | B | A+ |
| V4-LC2 | synthetic_legitimate | A! | A! | B | B |
| V4-LC3 | synthetic_legitimate | A! | A! | B | B |
| V4-SY1 | synthetic_control | A! | B | B | B |
| V4-SY2 | synthetic_control | A | A | B | B |
| V4-SY3 | synthetic_control | A+ | A+ | B | A+ |

## Context-binding checks (pre-dispatch)

| check | result |
|---|---|
| CB1_cross_session_reuse | rejected_pre_dispatch |
| CB2_fabricated_context | rejected_pre_dispatch |
| CB3_privileged_task_claim | rejected_pre_dispatch |
| CB3_context_purpose_wins | pass |
| CB4_revoked_session | rejected_pre_dispatch |
| CB5_cross_task_same_session | rejected_pre_dispatch |
| CB6_task_replacement_invalidates_prior | rejected_pre_dispatch |

binding failures: none
enforcement failures: none