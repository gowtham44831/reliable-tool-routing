# Auditable verifier inputs — argument-verification milestone

Exactly what each method receives, who supplies each piece of metadata, and
what is withheld. Companion to `docs/argument_verification_spec.md`.

## What a verifier receives

`Case.public_view()` (`src/tool_routing/argverify/schema.py`) returns a Case
containing only:

| field | supplied by | notes |
|---|---|---|
| `case_id`, `pair_id` | fixture author | identifiers only; pair_id used only for pairing metrics |
| `context` | fixture author (stands in for the host application) | `current_time`, `requester`, `flying_person`, `persons`, `profile_authorized`. Entity identities (who is the traveler vs. requester) come from here — application-supplied ground facts, not model interpretations. |
| `conversation` | fixture author | the literal turns; `turn.<n>` refs resolve here |
| `tool_schema` | fixture author | required fields, types, formats, enums, documented defaults, flight-id validity window |
| `prior_tool_results` | fixture author | tool outputs; `tool.<id>.<path>` refs resolve here |
| `proposed_tool_call` | fixture author (stands in for the planner) | the call under review |
| `evidence_manifest` | fixture author (stands in for the planner's claimed provenance) | per argument: `source_references` (ref, entity, tier, timestamp, match span), `transformation_or_default` |

`public_view()` drops `label_rules`, `expected_argument_findings`,
`expected_next_action`, and `ground_truth_explanation`. Verified by
`test_public_view_hides_labels` in `tests/test_argverify.py` and by grepping
the rendered review doc — none of those fields reach any verifier or the
human-review document.

## Metadata provenance: supplied vs. inferred

All fixture-supplied metadata (entity identities, tiers, timestamps,
`match` spans, context flags) is **manually authored** in these
development cases; in production it would come from the session/auth
layer, the orchestrator, and real tool-result timestamps. The experiment
is therefore *verification conditional on that metadata* — see
`docs/argument_verification_ai_audit.md` §7 for the full table.

- **Supplied (application/fixture):** entity identities in `context`
  (`requester`, `flying_person`, `persons`), source `tier` (the precedence
  label), `timestamp`, `entity` tag on each source ref, `match` span,
  `transformation_or_default`. These are claims *about* the evidence the
  planner cites — the verifier may use them but must still resolve the ref.
- **Inferred (verifier's job):** whether the resolved content actually
  contains the proposed value; whether the cited entity is the right person;
  whether a timestamp is stale under the contract's validity window; whether
  two refs conflict. A manifest claiming tier `user_current` does not make a
  value supported — the ref must resolve and match.
- **Precedence is declared, not inferred from recency.** `TIER_ORDER` ranks
  user_current > user_prior > tool_result > profile > schema_default. Within
  a tier, cases state precedence in their (hidden) label rules — e.g. a
  later correcting turn overrides an earlier turn. Newer timestamps alone do
  NOT override; a fresh search result does not beat a current user
  instruction.
- Missing timestamps and `entity: "unknown"` are permitted; the verifier
  must treat unverifiable recency as `unresolved`, not as evidence.

## Per-method inputs

- **schema baseline** — reads `tool_schema` + `proposed_tool_call` only.
  Checks required presence, type, format/pattern, enum. No evidence access.
- **rule baseline (frozen)** — additionally resolves each manifest
  `source_reference` via `evidence.resolve_ref`, checks literal/`match`-span
  containment, entity vs. `context`, tier precedence, timestamp freshness
  against the contract's validity window, and permitted transformations.
  Slot-level only: each argument judged independently.
- **cross-argument rule baseline** — same inputs; adds joint checks: the
  record behind `flight_id` must agree with proposed `date`,
  `origin_airport`, `destination_airport`, `departure_time`; the passenger
  name/DOB must agree with the cited profile/passenger record. Reported
  separately from the slot-level rules.
- **AI verifier** — receives a JSON dump of the same `public_view()`
  fields plus `missing_required_args` (a deterministic listing, same one
  `policy.py` computes — not a label). Model, endpoint, temperature are
  env-configured; raw responses are persisted per case.

## Credential handling

`ARGVERIFY_BASE_URL`, `ARGVERIFY_API_KEY`, `ARGVERIFY_MODEL` are read from
the environment only. No credentials appear in fixtures, docs, or committed
files; `results/` is git-ignored.
