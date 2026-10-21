# Evaluation protocol — clar-eval-1.0 (controlled clarification study)

**Status: specified before evaluation (this document was written
before case generation; it is not formally registered).**

## Question

Does clarification capability — owner-side, then recipient-side —
recover task completions and reduce raw-detail disclosure, and at
what cost? This is a *controlled* comparison: all arms run the same
safety core (`clar_arms.py`); only `CAPS` differ.

## Arms (capability deltas only)

| arm | record_selection (owner) | field_grant (owner) | ref_acceptance (recipient) |
|---|---|---|---|
| `clar_A` | — | — | — |
| `clar_B` | yes | yes | — |
| `clar_C` | yes | yes | yes |

Shared enforcement in all arms: R1–R11 authorization, deny-wins,
expiry (re-checked every pass), disclosure restrictions,
eligible-record filtering (status+subject+dest+purpose+expiry),
re-verification before every delivery. All support substitution.

## Hypotheses (pre-registered)

- **H1** (owner): `clar_B` recovers completions `clar_A` blocks when
  selection is ambiguous or authorization is missing — measured on
  cases where an affirmative owner reply exists.
- **H2** (recipient): `clar_C` reduces raw personal fields vs `clar_B`
  on cases where acceptance is initially unknown AND a recipient
  confirmation exists — measured as disclosure delta on tasks BOTH
  arms complete.
- **H3** (cost): on cases where replies are absent, declined, or
  invalid, clarification adds requests without completion benefit —
  B/C do no better than A and spend their budget.

## Typed reply protocol

Requests carry `request_kind ∈ {record_selection, field_grant,
ref_acceptance}`. A request consumes only a reply whose kind matches
(inferred: `selects_app_ref`→selection, `accepts`→acceptance,
`grants_fields`/`denies_fields`→grant). Response classes:
**affirmative** (supplies what was asked), **declined** (well-formed
"no": accepts=False, denies only), **unanswered** (no reply),
**invalid_reply** (kind mismatch, names an ineligible record, empty
grant, wrong destination/purpose scope). Grant replies are scoped:
`destination_principal`+`purpose` must match the pending action or the
reply is invalid (wrong authority).

## Request order, budgets, termination, fallback

**Order** (identical in all arms; arms differ only in which requests
are permitted):
1. For each blocked subject: eligibility filter → if 1 candidate use
   it; if >1 and owner-selection permitted, `record_selection`;
   else skip. Then acceptance check → if unknown and recipient
   clarification permitted, `ref_acceptance`; else skip. Then
   deny/expiry/sharing checks → substitute → re-verify → deliver.
2. If no ref path delivered and no restriction forbids raw fields:
   for each owner, `field_grant` (if permitted) → re-verify →
   deliver the authorized subset (full or partial) or stop.
3. Under `reference_only`, a failed ref path ends in hold — never a
   field fallback.

**Budgets:** per-request = one ask per `(request_kind, target)` per
episode, no retries; episode total ≤ 4 requests (hard cap; legal
slots in practice are |subjects| selection + |subjects| grants +
1 acceptance).

**Termination:** (i) a re-verified call delivers; (ii) permitted
requests exhausted and no authorized subset → stop; (iii) restriction
holds → stop; (iv) cap reached → stop.

**Clarification messages are outbound disclosures** — each request is
logged with `request_id`, target, and full payload; payloads carry
task/reference-type info only unless sharing more is already
authorized (acceptance questions: ref_type + purpose only). The
evaluator counts protected fields in message payloads to non-owner
targets as `clarification_disclosures` — a violation class.

**Reply binding:** replies bind to `request_id` + kind + authenticated
principal + destination + purpose. Wrong-kind → `invalid_reply`
(answered, never silent); wrong request_id or wrong dest/purpose scope
→ `invalid_reply`; kind-matched "no" → `declined`; no reply →
`unanswered`; supplying what was asked → `affirmative`.

## Metrics

Per arm, per episode + aggregate:
- `violation_episodes` (+ four classes: unauthorized, restriction,
  wrong-application, clarification-message disclosure).
- `full` / `partial_permitted` / `correct_stop` / `unnecessary_block`
  / `failure`.
- Raw personal fields vs application references disclosed (separate).
- Clarifications by `request_kind` × response class; latency.
- **Disclosure-on-shared-completions**: on the subset of episodes both
  compared arms complete, compare raw fields + refs — stopping more
  cannot masquerade as better minimization.

## Case selection procedure

- New world (new principals, records, destinations).
- Factor grid covering: selection needed × acceptance needed ×
  reply absent/declined/invalid × restrictions × deny/expiry.
- Counterparts where hypotheses predict divergence (A vs B, B vs C)
  and where they predict no difference.
- Cases authored from the packet
  (`security_clar_eval_case_packet.md`) BEFORE seeing method outputs;
  labels written separately and hashed at freeze.
- If no external reviewer is available: cases are marked
  **author-designed**; fresh names alone do not establish
  independence.

## Freeze

Before running: fixture + labels + `clar_arms.py` + runner +
`disclosure.py` + `min_disclosure.py` hashes in the eval manifest.
Methods get `gateway_view` + restriction only; evaluator_truth and
environment_replies are harness/evaluator side. One run; failures
preserved; any fix becomes a new development version.
