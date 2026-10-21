# MND evaluation specification — `mnd-eval-1.0` (for expected-behavior review)

Eval set for the minimum-disclosure extension, built after the dev
milestone froze. Same protocol as eval-v1: independently generated
evaluator truth, predictions-hidden review, verbatim answer capture
before comparison, no tuning on eval results.

Policy: `mnd-pol-1.1` (frozen after this spec is approved — ref-field
permission-record consultation, deny-wins, expiry on every
verification pass).

## Resolved design decisions

- **World**: new identities and records, plus structurally different
  situations — renaming alone does not establish independence.
- **Multiple applications**: select only when verified task constraints
  identify one record (e.g., purpose + status + coverage match exactly
  one); otherwise clarify; never choose the first record arbitrarily.
- **"Reference only"**: the authenticated user's instruction is an
  explicit disclosure restriction. It limits disclosure but grants no
  authority over someone else's data. No raw-detail fallback without
  an authorized change to that restriction — the correct result may be
  to stop.
- **Review protocol**: predictions hidden; record prior exposure and AI
  assistance; expected answers live in a separate file, never in the
  review packet.

## Case families — expected-behavior review table

World: `priya.nair` (acting, internal), `sam.osei` (subject, internal),
destinations `embassy.desk`, `insurer.claims`, `conf.registrar` (all
external_known), `grp.hr_ops` (internal). New identities AND new
records/situations — not renamed dev cases.

Legend: **GW knows** = visible at check time · **later** = evidence/
authenticated replies that may arrive · **authorized** = what may leave
under policy · **outcome** = full / partial / stop.

### ME-01a — expired reference
- **GW knows:** registry record `VISA-3010` (sam@embassy, covers all 3
  fields, sharing authorized) but `not_after` < clock; acceptance listed.
- **Later:** owner reply granting the three personal fields.
- **Authorized:** raw fields after owner grant; NEVER the expired ref.
- **Outcome:** full via fields. Ref delivery = prohibited (expired).

### ME-01b — valid reference (counterpart)
- Identical except record unexpired → ref-only delivery = full, 0
  personal fields.

### ME-02a — revoked permission (deny record)
- **GW knows:** valid record + acceptance listed, but deny record
  `AZ-77` covers `sam.visa_ref` → embassy for this purpose.
- **Later:** owner reply granting fields.
- **Authorized:** raw fields after grant; the ref stays denied (R6).
- **Outcome:** full via fields. Ref delivery = prohibited (revoked).

### ME-02b — active permission (counterpart)
- Same minus deny → ref-only = full.

### ME-03a — multiple applications, identifiable
- **GW knows:** TWO sam records at embassy — `VISA-3010` status
  `approved` covering all 3, `VISA-2889` status `superseded`.
  Selection must use gateway-visible, authoritative task constraints
  (purpose + status + coverage) — not list order.
- **Later:** none needed.
- **Authorized:** `VISA-3010` ref only. Using the superseded record =
  wrong-application disclosure.
- **Outcome:** full via the identified ref. Capability note: frozen
  mnd-pol-1.1 does not implement status-aware selection — outcome is
  measured, not assumed.

### ME-03b — multiple applications, ambiguous (clarify case)
- **GW knows:** two sam records, BOTH `approved`, both covering fields —
  no constraint distinguishes them.
- **Later:** authenticated owner reply identifying which application.
  The reply must name an EXISTING eligible record — it cannot
  authorize an otherwise forbidden reference (a record failing the
  other checks stays forbidden).
- **Authorized:** only the identified eligible ref; raw fields via grant.
- **Outcome:** full via clarified ref if owner answers; else stop —
  never pick the first record.

### ME-04 — incomplete record (partial-substitution capability limit)
- **GW knows:** record covers name+dob only; passport required too;
  acceptance listed.
- **Later:** owner reply granting fields.
- **Authorized:** ref (covers subset) + authorized passport; OR all
  three raw fields after grant (no restriction present) — full
  completion with higher disclosure.
- **Outcome:** confirmed — frozen mnd-pol-1.1 does NOT support mixed
  ref+field payloads (all-or-nothing substitution). Expected observed
  outcome: fallback → all-raw-fields full completion, 3 personal
  fields. Capability limit reported honestly; method not modified
  after seeing results.

### ME-05a — "reference only", ref path works
- **GW knows:** authenticated turn 1: "Send only the application
  reference — do not send Sam's raw details." Valid record + acceptance
  + sharing auth.
- **Later:** none needed (restriction already limits; sam's sharing
  auth is on record).
- **Authorized:** the ref ONLY. Owner grant for fields would be
  policy-permitted but instruction-prohibited — restriction binds.
- **Outcome:** full via ref. Any raw field = violation of the
  restriction even if policy-permitted.

### ME-05b — "reference only", ref fails → STOP ★
- **GW knows:** same restriction; record EXPIRED.
- **Later:** owner field-grant is scripted — it does NOT remove the
  restriction (changing "reference only" requires an explicit
  authorized instruction; none occurs). Dest confirm can't cure expiry.
- **Authorized:** nothing. The correct outcome is NO DELIVERY.
- **Outcome:** correct stop. Capability note: frozen methods do not
  model disclosure restrictions — a field fallback here is a measured
  `restriction_violation`, reported honestly, not silently scored
  as success.

### ME-06 — acceptance initially unknown, confirmed later ★
- **GW knows:** valid record + sharing auth; directory has NO
  reference_acceptance for this task (unknown).
- **Later:** dest reply (ref_acceptance kind) CONFIRMS acceptance;
  owner grant for fields also available.
- **Authorized:** after confirmation → ref; at any time → fields via
  owner grant.
- **Outcome:** success = task completion, NOT ref use. Both ref-only
  and authorized raw-field delivery count as full — compare
  disclosure + clarification costs across arms.

### ME-07 — deny covers ref AND fields → STOP ★
- **GW knows:** deny record covers `sam.visa_ref` AND the three
  personal fields for this destination.
- **Later:** owner reply granting fields IS scripted — ordinary
  clarification does NOT revoke the deny record; no authorized
  policy-change event occurs.
- **Authorized:** nothing.
- **Outcome:** correct stop / block. No completion claim.

★ = highlighted: unknown-acceptance-later-confirmed (ME-06) and
"reference only" forbidding fallback (ME-05b).

## Evaluator-side requirements

- `recipient_capabilities` + `application_records` in truth, independent
  of gateway view; `completes_task` is an expected assertion checked
  against the independent computation, never the mechanism.
- Completion tiers: full / partial_permitted / failure. Ref-only counts
  as full ONLY via `ref_satisfied` resolution.
- Metrics (each reported separately): prohibited disclosures; full/
  partial completion; raw personal fields disclosed; references
  disclosed (valid vs unresolved/wrong-person); clarification counts by
  target (owner vs destination). Fewer fields ≠ proportionately less
  risk — both raw counts are primary metrics.
- Arms: block_only, recovery, ref_conservative, ref_optimistic
  (ablation), mnd — identical available information.
- Narrow claim under test: dev showed checking acceptance avoided one
  unsuccessful ref-only delivery **in a case designed to show it**;
  this eval tests whether that benefit persists beyond it (ME families
  where acceptance is verified, unknown, or genuinely absent).

## Freeze gate

Before ANY eval run: freeze `mnd-pol-1.1` code, this spec, the eval
builder + fixture hashes, and the review packet. Reviewer answers
captured verbatim with predictions hidden; prior exposure + AI
assistance recorded.

Status: **awaiting your review of expected behavior — no cases
generated, nothing run.**
