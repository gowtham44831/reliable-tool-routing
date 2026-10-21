# Available Is Not Applicable: Evidence-Aware Verification of Tool Arguments

Short research specification. Novelty is **unverified** — see the related-work
comparison before claiming anything.

## Problem definition

Tool-calling pipelines evaluate whether the *right tool* was called with
*schema-valid* arguments. They rarely check whether each argument value is
**supported by available evidence**: a call can be structurally valid and
still be wrong — a DOB copied from the requester's profile instead of the
traveler's, a departure time invented to fill a required slot, a stored
preference overriding the current instruction, a month-old flight quote
treated as current.

Given a proposed tool call, the verifier must produce, **per argument**:

- `supported` — a cited source actually contains the value
- `missing` — required value absent / no resolvable source
- `contradicted` — higher-precedence evidence asserts a different value
- `wrong_entity` — value is sourced from a different person's data
- `unresolved` — multiple real candidates, or only stale evidence

and then one **next action**: `proceed` / `retrieve` / `clarify` /
`reject_proposed_call` (reject = this call must not execute; it does not
abandon the user's task).

## Intended contribution

1. **Provenance as a first-class input.** Each argument carries a claimed
   source reference that must *resolve* to conversation text or a tool-result
   field. "The model says it's supported" is not evidence.
2. **A paired evaluation design**: identical proposed calls whose verdict
   flips on a single evidence difference (10 pairs, 20 dev cases). This
   isolates evidence sensitivity from tool-selection ability — pairs must
   be kept together in any future split.
3. **Findings separated from actions**, so argument-level detection quality
   and policy quality are measured independently.

## Information available to the verifier

- Conversation turns, `context` (current time, requester, who is flying,
  whether profile lookup is authorized, known persons/roles).
- The tool contract: required fields, types, enums, documented defaults,
  per-argument validity windows, person-scoping flags.
- Prior tool results (with timestamps).
- The proposed call plus the planner's claimed evidence manifest
  (per argument: source references, entity, tier, timestamp, and any
  transformation/default used). Claims are *checked*, not trusted.
- Explicitly NOT available: expected findings, label rules, ground-truth
  explanations (`Case.public_view()` strips them).

## Decisions and metrics

Development metrics (20 paired dev cases — not a benchmark):

- Unsupported calls allowed / all unsupported calls (primary safety axis)
- Supported calls blocked / all supported calls (over-blocking)
- Argument-level finding accuracy
- Next-action accuracy; unnecessary-clarification rate
- Both-cases-correct per pair
- Latency per case; token usage for the AI verifier when run

## Assumptions and limitations

- `context.flying_person` and `profile_authorized` are declared per case;
  deriving who is flying from dialogue is upstream NLU, out of scope here.
- Extraction from free text uses contract-declared `hint`s and optional
  `match` spans; that is a stand-in for real semantic parsing.
- Precedence (current instruction > prior turn > tool result > profile >
  schema default) is a declared policy, not learned; within a turn the
  last mention wins.
- Timestamps may be absent; missing timestamps must not be assumed fresh.
- Authorization is a deterministic executor check, never inferred.
- 20 dev cases sized to exercise mechanisms, not to estimate rates; every
  count is reported with its denominator.
- The fixture is hand-authored English with ISO-style literals; real
  conversations are noisier.

## Related work (primary sources checked 2026-10-19)

| | What it does | Evidence/provenance | Entity matching | Conflicting info | Clarification decision | Released code/data |
|---|---|---|---|---|---|---|
| **When2Call** (Ross et al., NAACL 2025) | Benchmark for *when* to call a tool vs. ask follow-up vs. admit unanswerable; multiple-choice; trained with preference optimization | Judge decides among options; no per-argument provenance required | No | No | Yes — follow-up questions are a scored option | Benchmark + training data + eval scripts released (per abstract) |
| **BFCL V3** (Mao et al., 2024 blog) | Multi-turn/multi-step function calling; verified via post-execution API *state*; includes Missing-Parameters and Missing-Functions categories | State-based correctness, not provenance | No | No | Missing-parameter cases require clarification instead of guessing | HF dataset + Gorilla repo (per blog) |
| **Structured Uncertainty / SAGE-Agent + ClarifyBench** (Suri et al., Findings ACL 2026) | Structured uncertainty over tool params and domains; separates specification vs. model uncertainty; EVPI picks which question to ask; also a GRPO training signal | Uncertainty is over parameter values, not evidence provenance | No | Specification ambiguity, yes | Yes — EVPI-driven, cost-aware question selection | ClarifyBench announced; code availability not verified |
| **Latent Critic** (Vijayvargiya & Lokesh, arXiv 2608.10430, Aug 2026 preprint — unverified) | LoRA adapter runs alongside a frozen generator, localizes ungrounded arguments (e.g. "ungrounded: date"), intercepts before execution in a ReAct loop | Yes — closest: argument-level "ungrounded" detection, but learned from latent signals rather than resolved provenance | Not reported | Not reported | Interception/self-correction, not a proceed/retrieve/clarify policy | Not verified (arXiv page lists no code link as of check) |

**Overlap:** clarification-as-an-action (all four), argument-level
localization (Latent Critic), missing-parameter handling (BFCL V3),
uncertainty-driven question choice (Suri et al.).

**What might distinguish this experiment** (hypothesis, unverified):
- Verification is against *resolvable evidence pointers* — a claimed source
  must exist in conversation text or a tool-result field — rather than
  uncertainty scores, latent probes, or end-state matching.
- The failure classes are typed per argument (`wrong_entity`, `contradicted`,
  stale-evidence `unresolved`), and the action layer is a separate policy —
  so "which detection is reliable vs. which action is right" can be
  measured independently.
- The paired design holds the proposed call fixed and flips one evidence
  fact, isolating evidence sensitivity rather than tool selection.
- Authentication/authorization stays a deterministic executor check, not
  something the model infers.

None of this is claimed novel yet; a real related-work pass would be needed
before publication.
