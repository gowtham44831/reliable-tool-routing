# Model comparison plan (prepared; paid calls NOT yet made)

## Methods in the comparison

| id | method | implementation | status |
|---|---|---|---|
| `schema` | schema validation | `methods.schema_baseline` (frozen) | ready |
| `rule` | deterministic evidence rules (slot-level) | `methods.rule_baseline` (frozen) | ready |
| `crossrule` | cross-argument rules | `methods.cross_argument_baseline` (frozen) | ready |
| `ai_provider` @ qwen3:14b | local Ollama | `llm_providers.ai_verifier_provider`, v2 validation | ready (smoke-tested on local path) |
| `ai_provider` @ OpenAI | `gpt-5.4-2026-03-05` | same | awaiting budget authorization |
| `ai_provider` @ Anthropic | `claude-sonnet-5-5` | same | awaiting budget authorization |

All six see identical inputs (`Case.public_view()` incl. the policy text
in the tool contract) and go through the same `llm_v2.validate` scope
(args in the call ∪ required args absent from it — derived from the call
and contract, never from labels) and the same `policy.next_action`.

## Proposed exact model IDs (verified against official docs on the day of writing)

| provider | ID | source | pricing (per 1M tokens) | reasoning control |
|---|---|---|---|---|
| OpenAI | `gpt-5.4-2026-03-05` (pinned snapshot of `gpt-5.4`) | platform.openai.com/docs/models/gpt-5.4 | input $2.50 / cached $0.25 / output $15.00 | `reasoning_effort`: none (default), low, medium, high, xhigh; Chat Completions supported |
| Anthropic | `claude-sonnet-5-5` | platform.claude.com/docs/en/models/overview | input $2 / output $10 | `output_config.effort`: low/medium/high/… ; thinking adaptive (cannot be fully disabled by effort) |
| local | `qwen3:14b` digest `bdbd181c33f2`, Q4_K_M | `ollama show` | $0 | `think:false` (not honored on /v1); thinking tokens appear in output budget |

Why these: mid-tier, non-"pro" models from each provider, with a
documented explicit reasoning control so the reasoning budget can be
recorded. Alternatives if cost must be lower: `gpt-5.4-mini`
($0.75/$4.50), `claude-haiku-5-5` (from $0.10/$0.50).

## Proposed settings (identical across providers where the API allows)

- `max_tokens` / `max_completion_tokens` = **2048**
- reasoning: OpenAI `reasoning_effort=none`; Anthropic `effort=low`;
  qwen `think:false` (ineffective). **This is a known asymmetry** — the
  three models do not get an equal reasoning budget. It is recorded per
  run in `run_config.reasoning` and must be stated with results.
- `temperature=0` where accepted (Ollama, Anthropic); omitted for GPT-5
  family (reasoning models reject non-default temperature).
- timeout 300 s; retries 0.

## Cost estimate (before any paid call)

Measured: a dev-case prompt is ~1,970 tokens (Ollama tokenizer).
labelset_v2 prompts are ~2.2× longer in characters (policy text, larger
schema) → **~2,500–3,000 input tokens/case**. qwen3:14b produced
400–1,800 output tokens/case on dev; assume **1,000 output tokens/case**,
2,048 cap worst case.

| model | 40 cases input | 40 cases output | est. cost | worst case (2,048 out) |
|---|---|---|---|---|
| gpt-5.4 | 120k × $2.50/M = $0.30 | 40k × $15/M = $0.60 | **≈ $0.90** | $1.53 |
| claude-sonnet-5-5 | 120k × $2/M = $0.24 | 40k × $10/M = $0.40 | **≈ $0.64** | $1.06 |
| smoke tests (2 dev cases × 2 providers) | | | ≈ $0.08 | |
| **total** | | | **≈ $1.60** | **≈ $2.70** |

Requested authorization: **$10** ceiling (≈4× worst case) to cover
retries of transport failures and one possible rerun on a new version.
No paid call is made until this is approved.

## Smoke-test protocol (development cases only)

Per provider, run TB-01a and TB-01b once through `ai_provider`; check
HTTP 200, parseable JSON, v2 validation pass, usage and finish reason
recorded. Record any provider-specific error (parameter rejections) and
the adaptation made, in `docs/argument_verification_eval_protocol.md`
§"Provider adaptations". Smoke tests do not touch NV cases.

## Credentials

Only `ARGVERIFY_API_KEY` from the environment; never written to results,
logs, manifests, or git. HTTP error bodies are truncated to 500 chars
and never include the Authorization header.

## Known limitation: compliance labels (B)

The frozen methods emit grounding findings and an action only. None
emits a compliance (B) label; the AI prompt does not ask for one. For
the first frozen evaluation, **B is reported as "not produced by any
method"** and scored only on human labels (inter-reviewer agreement).
Adding B to methods is a versioned extension (v3 prompt / `methods_v2`)
for a *later* evaluation — not a silent change to the current task.
