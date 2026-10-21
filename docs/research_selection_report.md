# Research-selection report — one bounded contribution

Scope: at most three candidate gaps. No code, cases, or model runs
produced by this report. Existing prototype reused where useful;
sunk implementation effort is NOT a retention argument — each
candidate is judged on defensible gap + adoption path.

## Candidate comparison

| | A. Cumulative disclosure accounting | B. Context-bound untrusted-planner gateway (current) | C. Interface/measurability validity for security evals |
|---|---|---|---|
| closest primary research | DB inference control / salami attacks (Adam & Wortmann 1989); **Praetor** (pDFA behavioral firewall — sequence *structure*); **AGATE** (provenance gate + effect ledger — call *counts*/grant consumption); agent-policy-gateway (session taint labels) | **AGATE** (authorization gate at dispatch boundary; grants bind params, expire, limited uses; deterministic checks, no LLM in decision path); CaMeL (capability IFC — compared, 8/8 agree); APG (YAML policy gateway + taint); classic DLP/reference monitors | constrained decoding (Outlines/Instructor), BFCL function-calling evals, prompt-format sensitivity literature |
| what remains different | none of the above computes the *semantic union of values actually delivered* to a (recipient, purpose) and enforces a bound derived from permission records. Praetor bounds call structure; AGATE's ledger bounds grant counts; taint tracks provenance — none measures content accumulated at a receiver | purpose-scoped records + identity-bound task/session context + receiver-side receipt verification + mechanism-attribution evaluation | claim = measured security outcomes are confounded by interface capability; contracts must be frozen and reported. We have direct evidence (contract A 4/7 vs B 7/7; v1 dominated by schema rejects) |
| rename risk | medium-high: cumulative egress accounting ≈ inference control + SIEM aggregation. Defensible only if eval shows the semantic union catches what per-call AND count-ledgers miss | **high**: AGATE + APG + DLP already occupy "check the call at dispatch." Marginal delta is purpose semantics + verified receivers + eval discipline | n/a — a methodology observation, not a mechanism |
| concrete workflow | support bot: k tool calls over a conversation/session each individually plausible; slice i leaks field slice i; union reconstructs protected object. Also persistent-instruction (spAIware) analog: small leak per request to a fixed destination across tasks | assistant proposes one structured egress call; gateway authorizes it against app-context records bound to (task, session) | evaluator runs security suite on a local model; contract choice determines whether results measure security or parsing |
| integration point | same egress gateway + **receiver-side disclosure ledger** keyed (session, task, recipient, purpose) | existing adapter + gateway (adapter-1.3) | eval harness contract layer (exists: dev_interface_eval) |
| required metadata & source | per-field owner/sensitivity (exists: `field_metadata`); authorized (owner, field, destination, purpose, expiry) records (exist); delivered-value set — from existing receiver logs. **All obtainable in-prototype**; production source = data-owner tagging, same assumption as current work | exists in prototype (issuer, records, receivers) | exists (contract eval already run) |
| smallest distinguishing experiment | 3 cells on existing fixture data, saved-request style: S1 salami-split (protected object in k slices, each call clean/plausibly covered), S2 legit multi-call workflow (false-block control), S3 fixed-destination drip across tasks. Arms: M3 per-call \| M3+count-ledger (AGATE-analog) \| M3+value-union. Discriminator: S1/S3 pass per-call AND count-ledger, caught only by union; S2 unaffected | port eval-v4 through an AGATE-style grant+ledger arm; if it matches M3 on all cells with less machinery, the extra machinery is unjustified | already measured (A/B contracts); extension = show two published-style evals change verdict under contract shift |
| abandon-if result | (i) cumulative bound can't be derived from records without per-case hand budgets; (ii) legit multi-call flows suffer high false-block; (iii) every split/drip attack also trips per-call checks — no marginal catch | grant-ledger baseline matches M3 on all cells → contribution collapses to plumbing | a published eval replicates correct verdict under contract change → confound not real |
| incident evidence | **spAIware** (Rehberger 9/2024; FGCS journal version): persistent memory → per-request drip exfiltration — real public anchor for the *channel class*. **No public incident of salami-split across tool calls identified → synthetic evaluation required, flagged** | ShadowLeak + EchoLeak-derived cases (real anchors) — strongest incident grounding of the three | internal dev evidence only |
| journal-worthiness | defensible IF scoped as "bounded cumulative accounting + measured utility cost + incident-anchored channel" — an adaptation claim, disclosed as such | thin as primary claim; strong as the *platform* enabling A | workshop-note size alone; folds into A as a validity section |

## Recommendation: Candidate A — bounded cumulative disclosure accounting

**One sentence:** an egress-side disclosure ledger enforces that the
*union* of values delivered to each (recipient, purpose) over a
session/task stays within the authorized set derivable from existing
permission records — catching split and drip exfiltration that
per-call checks are structurally blind to.

Why it survives the rejection criteria:

- Does **not** depend on unavailable information — every required
  datum (field ownership, permission records, delivered values)
  already exists in the prototype.
- Does **not** need extensive handcrafted policies — the cumulative
  bound is the union of the records we already author; the
  abandon-test exists precisely to verify this.
- Is **not** merely renaming — provided the experiment demonstrates
  catches missed by both per-call checks *and* a count-based ledger
  (the AGATE-analog arm is the honest strongest baseline).
- Adoption path is concrete: a ledger keyed by (session, task,
  recipient, purpose) attached to the same gateway/receiver pair we
  already run; no planner or model changes.

Honest weaknesses to carry forward:

1. **Evidence gap flagged**: the tool-call salami case is synthetic;
   no public incident of split-across-tool-calls exfiltration was
   found. spAIware grounds the *persistent drip across requests*
   channel — adapt it as the incident-anchored cell (destination
   fixed, slice per request, across sessions — source-mapped, labeled
   adapted-simulation like MS-AD1).
2. The legit-completion risk is the real experiment: if authorized
   multi-step workflows (send itinerary → send confirmation → send
   receipt) cannot survive cumulative accounting without
   distinguishing metadata we don't have, the contribution dies.
3. Candidate B is demoted to *enabling platform*: AGATE's grant+
   ledger design is close enough that a B-only paper risks the
   rename critique. Its machinery is reused as A's substrate.
4. Candidate C folds into A as the measurement-validity section —
   it is evidence we already hold, not a separate contribution.

**Fallback**: if the S2 false-block test fails — legitimate
multi-call flows cannot be distinguished — the defensible deliverable
is a *negative/measurement* result (per-call and count-ledger egress
checks leave a demonstrated split-exfiltration hole; cumulative
accounting is too costly), which is still journal-honest but smaller.

## Sequence going forward (per instruction)

gap review → minimal prototype (ledger only — no gateway feature
expansion beyond accounting) → frozen comparative evaluation (three
arms above, expectations specified and frozen before execution) →
manuscript decision. No claim rewording to fit results.
