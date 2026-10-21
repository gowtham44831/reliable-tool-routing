# Recovery arm variant — `revision_only` (addendum to rec-pol-1.0)

**Disclosed as post-hoc:** this arm was specified *after* viewing the
exploratory block-only / full-recovery results, to isolate the marginal
contribution of clarification. Frozen in `results/disclosure_cmp_FREEZE.md`.

Definition: **rec-pol-1.0 with step 2 (clarification) removed.** Identical
checker (`check_episode`), permission records, deny-wins, re-verification,
and revision semantics — drop unfixable (`policy_conflict`,
`credential_http_offlist`, `untrusted_origin`) and unauthorized
non-required fields, rebuild the payload as a new action, re-verify,
execute iff it verifies non-empty. `retrieve_authorized_evidence` still
fails closed; no `environment_replies` may be consumed. Everything else →
`block`.

Naming in reports: `block_only` · `revision_only` ·
`revision_plus_clarification` (= rec-pol-1.0) · `field_filter` (secondary).
