# Verifier-output validation status

## What the frozen v1 verifier enforced (`llm.py`, run 3)

- Response must parse to JSON with a non-empty `argument_findings` dict.
- Values that are not legal finding strings are **silently dropped**;
  arguments with no finding are **silently absent**.
- Any ≥1 surviving finding → action computed by the shared policy.

Consequence: a partial response (e.g. findings for 6 of 8 arguments)
produced a *real* action. With the policy's "no bad finding → proceed"
default, a model that simply omitted the problematic argument could
authorize execution.

## Did run 3 cover every in-scope argument?

**Yes, by inspection of the saved rows** — for all 20 cases the finding
keys equal the in-scope set exactly, including the *absent* required
`passenger_dob` on TB-05a/TB-05b (labelled `missing`). But this was not
enforced; it is a property of that model's output, not of the code.

Replaying strict validation over the saved raw responses (no model
calls):

| run | responses v2 would reject | failure types |
|---|---|---|
| run 1 (qwen3:0.6b) | **11/20** | 8 partial, 2 malformed values (`"unsupported"`, `"missing_required_args"`), 1 empty |
| run 2 (qwen3:0.6b) | **11/20** | 6 partial, 4 malformed (nested objects, inverted key/value), 1 **duplicate key** (`date` twice in TB-08b) |
| run 3 (qwen3:14b) | **0/20** | — |

So the 0.6b runs' metrics mixed model misjudgment with technical
non-conformance; only 9/20 responses per run were well-formed. The
qwen3:14b run is clean under the strict rules.

## v2 (`llm_v2.py`) — new version, frozen v1 preserved

Same transport, prompt (sha `68efada2872c58b9`), settings and policy.
Adds `validate()`:

- **In scope** = args present in the call ∪ required args absent from it.
- Reject → `verifier_error` (blocks execution, findings `{}`) when:
  partial (any in-scope arg lacks a finding), unknown (finding for an
  out-of-scope arg), malformed (non-string or non-legal value),
  duplicate key in the raw `argument_findings` object, or an absent
  required arg labelled anything other than `missing`.
- `verifier_error` is reported in its own column (`verifier fail`) and
  excluded from both "unsupported allowed" and "unsupported detected".

Tests: `tests/test_argverify_llm_v2.py` (7 cases: complete accepted,
absent-required in scope, partial / unknown / malformed / duplicate /
empty rejected). Runner method name: `ai_v2`.

## Reporting changes (evaluate.py)

New columns: `unsup. detected` (blocked by a *judgment*, not a failure)
and `verifier fail` (n/20, with case ids in `verifier_failure_cases`).
`sup. blocked` excludes failures. Technical failures are therefore never
counted as detections.

v2 has **not** been run against a model yet; it is the version to use
for the post-label evaluation.
