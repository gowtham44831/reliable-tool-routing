# CaMeL integration feasibility assessment (v2 — deep inspection)

Inspected: github.com/google-research/camel-prompt-injection
(cloned /tmp/camel-repo, main). Revised verdict after reading the
model, interpreter, and policy layers: **a faithful partial
integration is feasible; the full system is not runnable unchanged
in our current local setup — provider dependencies and AgentDojo
coupling establish integration work, and a local adaptation has
not been validated. Nothing here is technically impossible.**

## Architecture (from source)

- `src/camel/interpreter/` — self-contained Python interpreter
  executing LLM-written CaMeL programs (restricted subset);
  capabilities (readers/sources) attached to `CaMeLValue`s during
  execution. Imports only `camel.*` internals + pydantic.
- `src/camel/security_policy.py` — `SecurityPolicyEngine.check_policy
  (tool_name, kwargs, dependencies)`; deny-by-default; per-tool
  glob-matched policy functions; `base_security_policy` denies any
  non-public data reaching a state-changing tool.
- `src/camel/pipeline_elements/security_policies/travel.py` —
  `send_email_policy`: recipients ⊇ readers of body/subject/
  attachments (`can_readers_read_value`); trusted-recipient
  short-circuit. **Reader-set authorization is semantically close
  to our permission records.**
- `models.py` — three pipelines: original LLM agent;
  `PrivilegedLLM` (model writes CaMeL code, interpreter enforces);
  `PrivilegedLLMReplayer` — **replays saved privileged-LLM outputs
  through the policy engine with no live model call**.
- Only `anthropic`/`openai`/`genai` clients are instantiated —
  but `openai.OpenAI()` accepts `base_url`; Ollama exposes an
  OpenAI-compatible endpoint.

## Smoke test (executed) — see `docs/camel_smoke_report.md`

A full smoke run was executed in a separate venv against the local
Ollama endpoint. Results:

- Interpreter, AgentDojo workspace env, and
  `WorkspaceSecurityPolicyEngine` **work locally**: benign
  `send_email` allowed; a send with recipients derived from untrusted
  email data correctly raised `SecurityPolicyDeniedError`.
- `PrivilegedLLM` via `OpenAILLM(openai.OpenAI(base_url=ollama),
  "qwen3:14b")` connected and retried, but **qwen3:14b exhausted
  max_attempts without emitting a valid CaMeL program** (generic
  Python, forbidden `def`s, commentary). Concrete blocker: DSL
  generation, not plumbing.
- Semantic finding: `is_trusted(recipients)` short-circuit means
  literal program recipients are trusted by design (privileged-LLM
  assumption) — a threat-model divergence from our gateway, which
  distrusts planner call content.
- **Shared-task evaluation on the local endpoint: not feasible.**
  The policy-component comparison remains the evidence limit.

## Feasibility matrix

| integration level | feasible? | required adaptations |
|---|---|---|
| policy-intent arm: their `SecurityPolicy` protocol + `base_security_policy` run on our calls | **yes, today** | construct `CaMeLValue`s with readers attached from our provenance; label "camel-policy-intent" |
| interpreter arm: hand-written CaMeL program for our scenario, their interpreter enforces | **likely yes** | `agentdojo>=0.1.34` dep for env/tool objects; write the program ourselves — label "CaMeL-interpreter, scripted program" |
| replay arm: `PrivilegedLLMReplayer` on saved model outputs | **yes, model-free** | our saved v2 calls → their replay format; evaluates policies on real model outputs without new calls |
| full pipeline w/ local model (PrivilegedLLM via Ollama) | **not runnable unchanged in our current local setup; an adaptation has not been validated** | `openai.OpenAI(base_url="http://localhost:11434/v1")` + `agent_pipeline.OpenAILLM` + entry in `_supported_model_names`; whether qwen3:14b can emit parseable CaMeL DSL is UNKNOWN — likely the hard part, not the plumbing |
| full AgentDojo suite comparison | **not runnable unchanged in our current local setup; integration work, not technical impossibility** | re-encode our scenario as an AgentDojo task suite — a real port, labeled approximation |

## Shared task/policy subset (feasible)

"Private data may not reach an egress call" is expressible in BOTH:
- CaMeL: `send_email_policy`-style — destination (recipients/URL
  host) must be ⊇ readers of all transmitted args.
- Ours: F3 — matched protected fields need a covering permission
  record for this destination+purpose.

Semantic delta: CaMeL attaches readers at value-flow time (the
interpreter knows who may read); we attach permission records at
policy time. With `base_security_policy`, CaMeL denies ALL
non-public egress — no authorization layer — so its published
policy can't express our authorized-share case (V4-LC1); a custom
`SecurityPolicy` function would be needed, making it a
policy-intent comparison.

## Local-model compatibility — honest status

- Plumbing: small patch (base_url + model registry entry). **Verified
  working** — `OpenAILLM` connected to Ollama's OpenAI-compatible
  endpoint and completed chat requests (smoke test).
- Capability: **measured and failing** — qwen3:14b produced no valid
  CaMeL program in 3 attempts (see smoke report). A larger/different
  model may close this; unvalidated.
  PrivilegedLLMReplayer partially bypasses this by replaying.
- Paid-call equivalence: none needed if using OpenAI-compatible
  local endpoint; their evaluation used frontier models — results
  would NOT be comparable to their published numbers.

## Recorded adaptation debts

1. Capabilities constructed by our code, not interpreter-tracked.
2. Scripted program ≠ model-generated program (control-flow
   guarantees unexercised).
3. Local-model DSL capability unknown.
4. Any suite port is an approximation.
