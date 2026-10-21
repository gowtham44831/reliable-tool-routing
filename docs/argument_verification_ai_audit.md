# Audit of the AI-verifier run (argverify_dev_run1) and re-run (argverify_dev_run2)

## 1. Run configuration (as executed, run 1)

| item | value |
|---|---|
| provider | local Ollama, OpenAI-compatible endpoint `http://localhost:11434/v1/chat/completions` |
| model | `qwen3:0.6b` (`ollama show`: 751.63M params, Q4_K_M, context 40,960, thinking default **true**) |
| prompt | fixed template `PROMPT` in `src/tool_routing/argverify/llm.py` + serialized public case JSON (verbatim request bodies exported per case in `docs/argument_verification_ai_traces.md`) |
| generation settings | `temperature=0`, `"think": false` (Ollama-native field; not guaranteed honored on the `/v1` compat endpoint), **no `max_tokens`** (unbounded output) |
| output-token limit | none configured — see defect D2 |
| retry policy | none — exactly one attempt per case, no retries |
| timeout | 300 s per case (single `urlopen` call) |

## 2. Input parity check (AI vs. rules)

Verified programmatically that the serialized case the model received
contained: conversation turns, `context` (requester / flying_person /
persons / profile_authorized / current_time), the full tool schema, prior
tool results, the proposed call, and the claimed evidence manifest.

**Defect found and fixed (D1):** the manifest sent to the AI omitted the
`match` span — the planner's claimed literal evidence string — which the
rule baseline verifies against resolved content. The AI therefore had
strictly less provenance metadata than the rules. `match` is now included
in `_public_case_dict`.

**Human-authored interpretations supplied to BOTH methods** (application-
supplied metadata, part of the audited input contract): `entity` and
`tier` tags on each source reference, timestamps, `match` spans, and
`transformation_or_default`. These are claims to be checked, not labels;
neither method treats them as ground truth. `missing_required_args` is a
deterministic derived listing (`policy.missing_required_args`), identical
computation for all methods.

## 3. Empty/unparseable-response audit

### TB-08b (run 1) — empty response (context exhaustion inferred, not verified)

- **Raw output:** `content` was the **empty string** `""` (full body:
  `raw=""`, `finish_reason` not recorded in run 1).
- **Token usage:** prompt 1,938, **completion 40,960** — exactly the
  model's context length — total 42,898. Latency **211.17 s**, zero
  retries, did not hit the 300 s timeout. The whole generation was a
  reasoning trace (qwen3 thinking default `true`; `think:false` not
  honored on the `/v1` compat endpoint; no `max_tokens` bound).
- **Parser result:** `_parse_json("")` → `{}` → zero findings.
- **Policy decision (run 1):** absent `next_action` silently fell back
  to `clarify` — a fabricated decision from a malformed response. The
  case was scored as if the verifier had *chosen* `clarify` (it happened
  to be wrong vs expected `reject_proposed_call`, but the mechanism was
  the defect).
- **Metric treatment (run 1):** counted as a normal wrong prediction;
  `parse_ok=False` recorded but not surfaced in the summary.

### TB-03a (run 2) — schema-nonconforming response

- **Raw output:** complete, valid JSON (`finish_reason="stop"`, 599
  completion tokens, closes cleanly) but with nested finding objects —
  `{"argument_findings": {"cabin": {"supported": true}, ...}}` instead
  of `"cabin": "supported"`. (An earlier draft called this "truncated";
  that was wrong — see `results/argverify_dev_RECONCILIATION.md` §5.)
- **Parser result:** type-checked filter discarded every value → zero
  valid findings.
- **Policy decision (run 2):** `verifier_error`, `error="unparseable/
  empty response"` — **surfaced, not fabricated**.
- **Metric treatment (run 2):** reported separately in
  `n_parse_errors`; the row counts as an incorrect action (it is a
  verifier failure — a supported call was not verified), and
  `pred_action="verifier_error"` can never equal `proceed`, so a
  malformed response can never authorize execution.

**Guarantee now enforced in `ai_verifier`:** an action is emitted only
when at least one legal finding parsed; otherwise the case returns
`verifier_error` + `error` + `finish_reason`. `verifier_error` ∉
`{proceed, retrieve, clarify, reject_proposed_call}`, so it cannot
silently authorize execution — it appears as its own row/category.

## 4. Findings → action conversion

Run 1 took the model's declared `next_action` verbatim, while schema/rule
methods derive the action from findings through the shared
`policy.next_action`. That asymmetry hid attribution.

Attribution for the 10 allowed unsupported calls in run 1 — **model
output**, not parsing or policy: all 10 (TB-01b, 02b, 03b, 04b, 05a,
05b, 06b, 07b, 09b, 10b) had `parse_ok=true` and the model labeled every
present argument `supported` with a declared `proceed`. TB-08b (the
parse failure) was **not** among the allowed calls — its fabricated
`clarify` blocked execution by accident; it is a verifier failure, not a
detection. The policy layer was never the problem — it was bypassed.
(Recount in `results/argverify_dev_RECONCILIATION.md` §2.)

**Fix (D3):** the AI's action is now derived through the same
`next_action` policy from the model's findings; the model's declared
action is preserved in `details.model_declared_action` for diagnosis.
Run 2 shows the consequences: TB-08a — model said `proceed` while
flagging `flight_id` unresolved → policy yields `clarify`; TB-05a —
model declared `retrieve`, policy yields `clarify` from its
supported/unresolved findings.

## 5. Other defects fixed in the same pass

- `evaluate.py` crashed sorting the confusion matrix when a prediction
  was `None` (mixed types) — now sorted on string keys.
- Token-usage aggregation crashed on nested dict usage fields (Ollama's
  `prompt_tokens_details`) — now sums numeric values only and keeps
  per-case usage.
- Nested/non-string finding values (`{"arg": {"finding": ...}}`) crashed
  the FINDINGS filter — now type-checked.
- `run_config` (provider, model, temperature, max_tokens, timeout,
  retries, prompt SHA) is recorded per method result for auditability.

## 6. Run 2 result (same 20 dev cases, new run dir)

| | run 1 | run 2 |
|---|---|---|
| next-action | 9/20 | 8/20 |
| unsupported allowed | 10/11 | 9/11 |
| supported blocked | 0/9 | 2/9 |
| arg findings | 137/164 | 120/164 |
| pairs | 0/10 | 0/10 |
| parse/verifier errors | 1 (hidden as "clarify") | 1 (surfaced as verifier_error) |
| max latency | 211.2 s (40,960 tok) | 4.2 s (bounded) |

The AI result remains poor — *worse* by these numbers after the honest
fixes — because **in this run, this configuration, this model**
(`qwen3:0.6b` Q4_K_M via Ollama `/v1`, temperature 0) labeled almost
everything `supported`. All 9 remaining allowed calls are model-output
errors: it asserted support for wrong-entity (TB-01b), contradicted
(TB-03b, TB-08b), invented (TB-02b, TB-09b), stale (TB-07b), ambiguous
(TB-06b, TB-10b) and unfetchable (TB-05b, TB-04b) arguments alike. This
is a statement about qwen3:0.6b under these exact settings on these 20
dev cases — not about small models in general. We preserve the result
rather than prompt-tune it into the appearance of competence.

## 7. Metadata provenance: real mechanism vs. fixture-supplied

| input | source | status |
|---|---|---|
| `context.requester` / `flying_person` / `persons` | fixture author | manually supplied; in production would come from the session/auth layer |
| `context.profile_authorized`, `current_time` | fixture author | manually supplied; production: permission flags + clock |
| source `entity` tags (`traveler`/`requester`) | fixture author | manually supplied; production: the tool layer that produced each result knows which profile it returned |
| source `tier` (precedence labels) | fixture author | manually supplied; production: assigned by the orchestrator that knows where each datum came from |
| source `timestamp` | fixture author | manually supplied; production: real tool-result timestamps |
| `match` spans, `transformation_or_default` | fixture author | manually supplied; production: the planner's own citation of what it read |
| `missing_required_args` | `policy.missing_required_args` | **real code**, computed identically for all methods |
| ref resolution, candidate extraction, precedence arbitration, staleness vs `valid_for_hours` | `evidence.py` / `methods.py` / `policy.py` | **real code** — the verifier's job |

**This experiment is verification conditional on that supplied
metadata, and the evaluation assumes it is available and correct.**
Where the fixture supplies traveler identity (`flying_person`,
`persons`) or source precedence tiers, results are valid only under the
assumption that a real application would supply the same, accurately.
The fixtures simulate that application-provided context; what is being
tested is whether the verifier, *given* those identities and tiers,
checks evidence correctly — not whether it can infer them.

## 8. Stronger-model comparison (run 3 — executed)

Same inputs (`public_view`), same prompt (sha `68efada2872c58b9`), same
findings→action policy. Run config recorded in `results.json`:
`qwen3:14b` (Q4_K_M, ~14.8B params) via local Ollama `/v1`,
`temperature=0`, `max_tokens=2048`, `timeout=300s`, `retries=0`.
Ollama loaded it with a 4096-token context window — prompts are ~1,940
tokens, leaving ~2.1k for output; one response could have been clipped
but none were (`n_parse_errors=0`).

Smoke test before the full run (TB-01b): correctly returned
`wrong_entity` for traveler_name/passenger_dob in 41.9 s — config
verified before running all 20.

| | run 2 (qwen3:0.6b) | run 3 (qwen3:14b) |
|---|---|---|
| next-action | 8/20 | **16/20** |
| unsupported allowed | 9/11 | **3/11** |
| supported blocked | 2/9 | 0/9 |
| arg findings | 120/164 | **157/164** |
| pairs | 0/10 | 6/10 |
| parse/verifier errors | 1 | 0 |
| latency mean/max | 2.3 s / 4.2 s | 43.4 s / 77.7 s |
| tokens (total) | 46,830 | 55,871 |

Remaining failures, all "ambiguity blindness": TB-02b (invented 09:15
among real candidates → model said supported), TB-06b, TB-10b (ambiguous
airport/origin → supported instead of unresolved), TB-09b (`num_bags`
unresolved instead of missing — right direction, wrong label; clarify vs
reject). It detects entity/staleness/contradiction errors the 0.6B model
missed entirely, but still treats "one of several candidates" as
supported rather than unresolved.

Implementations frozen after this run — hashes in
`results/argverify_dev_run3_qwen14b/FREEZE.md`.

Original run preserved at `results/argverify_dev_run1/`; re-run at
`results/argverify_dev_run2/`.
