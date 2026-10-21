# Journal research plan — evidence-bound egress authorization for LLM agents

Status: draft for review. No new experiments are authorized by this
document. All prior runs remain frozen (`url-gw-1.0-isolation`,
`clar_arms_freeze`, mnd-eval-1.0/2.0, `_r2`).

## 1. Research question

> For an LLM agent whose planner is *unmodified and untrusted*, can an
> egress gateway that (a) inspects serialized outbound content, (b)
> binds payload values to their retrieval provenance, and (c) enforces
> per-field owner/destination/purpose authorization, prevent
> unauthorized disclosure while preserving legitimate task completion
> — and what does bounded clarification add or cost?

Sub-questions, ranked by current evidence:

- **RQ1 (preliminary evidence from synthetic controls only)**: does
  content inspection add enforcement beyond destination filtering on
  url_fetch-style egress? Current support is 5 synthetic cells, no
  incident-derived cases run yet.
- **RQ2 (untested)**: does provenance-based authorization (rather than
  host rules or planner claims) separate authorized from unauthorized
  egress *across incident-derived mechanisms*?
- **RQ3 (paused)**: do owner/recipient clarification protocols
  recover utility without adding disclosure (H1/H2/H3 from
  `security_clar_eval_protocol.md`)?
- **RQ4 (boundary)**: which documented attack classes are provably
  outside this enforcement point (deceived-but-valid authorization,
  UI-side channels, platform cache)?

## 2. Threat model

- **Adversary**: controls content in retrievable sources (emails,
  documents, pages) — indirect prompt injection — and may register
  external destinations. Cannot forge authenticated turns, permission
  records, or application metadata.
- **Protected**: fields with `owner`+`class` metadata in trusted
  application records; disclosure = protected value reaches a
  destination lacking authorization.
- **Trusted**: authenticated principal identities, `field_metadata`,
  `permission_records`, `directory`, gateway code.
- **Untrusted**: planner output (tool choice, args, `payload_fields`,
  `evidence_refs`, `prior_approval` claims), retrieved content,
  clarification reply content (bound by request, not trusted).
- **Out of scope (documented, not claimed)**: deceived-but-valid
  grants (INC-09/10 OAuth), UI-rendered channels, platform bugs,
  payload encodings outside the bounded decode set, values that
  never passed through retrieved content.

## 3. Assumptions

1. Application supplies correct owner/class metadata (disclosed as an
   assumption in every run; mislabeled metadata → measured failure
   mode, not silent success).
2. Permission records exist and are well-formed; missing records are
   "no authorization", not an error.
3. Egress channels are enumerable tool calls — coverage is bounded by
   the toolset (send_email, http_post, url_fetch today).
4. Encoded payloads use encodings in the decode set; others are
   recorded as `unsupported_encoding`, never silently allowed.
5. Loopback/local destinations model real destinations; the URL is
   inspected verbatim before dispatch.

## 4. Candidate contributions and refuters

| # | Claim (precise scope) | Evidence that refutes it |
|---|---|---|
| C1 | **Scope: url_fetch egress, synthetic+adapted cells.** Content inspection blocks at least one private-payload delivery that host filtering passes, without breaking the benign case. | Receiver-verified private receipt *through the full gate* on a control; or inspection differing from host-filter on zero controls. (Note: a single leak refutes any zero-leak claim — it does NOT refute "inspection adds enforcement", which is comparative.) **Status: established at mechanism level (AD-1; U1/U3 prior) — small n.** |
| C2 | **Scope: prepared manifest.** Provenance-bound authorization yields strictly better protection-utility trade than M2 block-on-any-protected-match — i.e., allows the synthetic legitimate counterpart while blocking the incident payload. | M3 blocks an authorized delivery M2 also blocks (no utility gain); or M3 allows a payload the incident's documented policy prohibits. **Status: established on LC-1/LC-2 + AD-1; incident grounding thin.** |
| C3 | **Scope: architectural property only today.** The gateway consumes planner calls as untrusted input and does not require planner cooperation. | Nothing yet — an actual planner connection test is REQUIRED before claiming demonstrated integration. Any claim beyond "the interface takes a planner_call dict" is premature. |
| C4 | **Scope: clarification benefit.** PAUSED — no claim; no incident evidence supports it. | — |
| C5 | **Scope: boundary catalogue.** Documented out-of-scope classes actually bypass/are invisible to the gate. | An out-of-scope-class case unexpectedly caught (catalogue too pessimistic) or an in-scope-class case silently passing (catalogue wrong) — recorded, not retuned mid-run. |

Scope is fixed at manifest freeze; failures observed later do not
redefine scope — they are reported against it.

**Explicitly allowed conclusion**: if related-work overlap is total
(Fides/CaMeL cover the same enforcement point with formal guarantees),
the contribution re-scopes to replication + incident-derived evaluation
methodology — and even THAT may not be novel; prior incident-derived
evaluations (e.g., red-team write-ups replayed as benchmarks) must be
checked in related work before any novelty statement.

## 5. Demonstrated findings vs hypotheses

**Demonstrated (frozen artifacts, synthetic scope only)**:
- Preliminary evidence: on 5 synthetic cells, content inspection added
  enforcement vs host filtering (U1/U3 diverged; allowlist-only
  delivered the private payload). Not a broad demonstration — see
  `docs/security_url_gw_evidence.md`, `results/url_gw_isolation/`.
- Value-matching recovers payload→field binding under base64;
  uncertainty/unsupported encodings are recorded, not hidden.
- No block-followed-by-receipt on any control; checked URL ==
  dispatched URL == receiver-observed target.

**Hypotheses (no supporting evidence yet)**:
- RQ2 generalization beyond synthetic payloads — untested.
- RQ3 clarification benefit — H1/H2 paused; no public report
  documents reply behavior; synthetic probes only.
- Any claim about real deployments — nothing tested on real systems.

## 6. Related work — primary-source comparison

Examined: papers and available implementations (GitHub for CaMeL,
Fides, AgentDojo). **Overlap/gap per row.**

| Work | Enforcement point | Mechanism | Planner | Overlap with ours | Remaining difference |
|---|---|---|---|---|---|
| **CaMeL** (Debenedetti et al., arXiv:2503.18813, Google/ETH; impl: google-research/camel-prompt-injection) | Tool-call boundary inside a custom secure interpreter | Capability-based policies on control+data flow extracted from trusted query; structured queries | **Replaced** — trusted query compiled to a program | Per-action authorization checks at egress; exfiltration prevention | Guarantees: CaMeL claims provable security under its threat model; ours offers empirical evidence only. Assumptions: CaMeL needs queries compilable to programs (their eval: 77% tasks solvable vs 84% undefended); ours needs correct app metadata. Channels: both bounded to tool calls in the toolset. Integration: CaMeL replaces the planner; ours wraps egress of an unmodified planner — the only axis where ours may differ favorably, pending C3's actual planner test. |
| **Fides** (Costa et al., arXiv:2505.23643, Microsoft; impl: microsoft/fides) | Planner instrumentation | Dynamic taint: confidentiality+integrity labels; policy engine; hide/reveal primitives; formal model of enforceable properties | **Is** a planner | Label-driven egress blocking; deterministic policies | True taint-tracking vs our value matching (ours can be evaded by transforms outside decode set — disclosed). Fides gives guarantees; we give empirical boundary mapping for unmodified planners. |
| **RTBAS** (Zhong et al., arXiv:2502.08966, CMU) | Tool-call screening | IFC adapted to TBAS; LM-judge + attention-saliency dependency screeners; asks user when safeguards fail | Wrapped | "Ask when uncertain" ≈ our clarification; per-call confidentiality check | Screeners are probabilistic (near-oracle, not oracle); ours is deterministic matching + explicit reply binding. Also evaluated on AgentDojo. |
| **AirGapAgent** (Bagdasarian et al., arXiv:2405.05175, Google, CCS'24) | **Input** side — context minimization | Restricts data agent can access to task-necessary subset (contextual integrity) | Unmodified agent | Minimum-necessary principle shared with our MND work | Complementary: minimizes what the agent *sees*; we check what it *sends*. Direct comparison feasible (both measurable on same tasks). |
| **AgentDojo** (Debenedetti et al., NeurIPS'24; impl: ethz-spylab/agentdojo) | Benchmark | 97 tasks, 629 attack cases, extensible | — | Evaluation framework; our incident-derived cases target the same failure class | Not a defense. Adopting it would require LLM calls (out of scope: no paid calls); feasible as local-LLM variant — flagged, not planned. |
| **Classic IFC** — DLM (Myers & Liskov, TOCS'00), HiStar (OSDI'06), Flume (SOSP'07) | OS/language labels | Decentralized labels, taint at syscall level | — | Conceptual basis | Weaker mechanism (value matching ≠ taint). Cite as lineage; do not claim IFC. |
| **Commercial DLP** (egress content inspection: Symantec/Broadcom, Forcepoint, Microsoft Purview) | Network/endpoint egress | Regex/fingerprint/classifier content matching | — | Content inspection at egress is established practice | DLP lacks per-principal authorization binding to a *specific action* and reply-bound clarification — that's our narrower delta. Whether it's novel vs an implementation detail is a review question. |

**Gap statement**: the occupied territory is "policy-checked tool
calls" (CaMeL/Fides/RTBAS) and "egress content matching" (DLP). The
defensible niche — *if any* — is measuring, on incident-derived
mechanisms, how far a provenance-binding egress proxy gets with an
**unmodified planner and no new query language**, including an honest
boundary catalogue (which attack classes it cannot see). If that
niche reads as thin after review, the paper becomes an
evaluation/replication contribution.

**Comparable published implementation**: CaMeL's policy engine is the
closest runnable comparator. Feasibility: run our episode format
through an adapted CaMeL-style policy *as an approximation* —
explicitly NOT a reproduction (their system requires the program
representation). Alternative: implement the published AgentDojo
"tool filter" defense baseline locally. Decide after protocol review.

## 7. Evaluation protocol (designed before further implementation)

### 7.1 Suites — strictly separated

- **Incident-derived suite** (primary evidence): cases built only
  from public incident reports (`security_clar_eval_incident_sources.md`,
  `security_clar_eval_source_mapping.md`). Each case preserves the
  documented mechanism; every substitution listed as an adaptation
  with its source-evidence gap. Demonstrations vs confirmed incidents
  stay labeled. Missing essential facts → excluded, reason preserved.
- **Synthetic engineering-controls suite** (secondary, separate
  metrics): U1–U3-style controlled variants, malformed-input tests,
  benign paths. **Generated variants are never counted as independent
  incidents** — reported as variants of a parent control.
- Prior synthetic sets (mnd-eval-1.0/2.0) remain a third, explicitly
  author-designed class.

### 7.2 Arms (isolation mapping)

| arm | adds | isolates |
|---|---|---|
| M0 no_gateway | dispatch only | mechanism reality check (does the receiver get it) |
| M1 host_filter | F2 allowlist | destination filtering alone |
| M2 content_inspect | + bounded decode + value match + `unaccounted_payload` | what inspection alone stops, WITHOUT authorization semantics |
| M3 full_gateway | + per-field authorization, deny-wins, metadata classes | what authorization adds on top of matching |

**M2 defined operationally** (same decoder, matching logic, metadata
view, and dispatcher as M3 — `decode_url_payload`,
`retrieved_value_index`, `match_candidates`, `dispatch_fetch`
imported from the frozen `url-gw-1.0`):

> M2 blocks iff (a) host offlist, OR (b) any matched carrier resolves
> to a protected-class field (`personal`/`credential`/
> `health_financial`) or an unlabeled value, OR (c) any query carrier
> is unaccounted. **No permission records are consulted** — a matched
> protected field blocks regardless of permits. `public`/`internal`
> classes pass (internal to internal-class destinations only).

Central comparison — **does field-level authorization improve
legitimate sharing over content blocking while retaining protection
host filtering misses**: U2-style authorized deliveries where M2
blocks and M3 allows measure the utility gain; U1/U3 measure retained
protection. (M1 vs M3 done on U1–U3; M2 completes the isolation.)

### 7.3 Outcomes and error taxonomy

Primary metrics per cell:
- **Unauthorized info actually received** (receiver-observed decoded
  values, not decisions) — the safety metric.
- **Legitimate task completion** — full / permitted-partial / stopped.
- **False blocks** — blocked deliveries that were authorized.
- **Inspection coverage** — carriers decoded+accounted vs total.
- **Errors** — separate buckets: `unsupported_encoding`,
  `unparseable/oversized`, `metadata_missing` (F4/R7), `ambiguous_match`
  — never merged into authorization failures.
- **Latency** — wall time per check; clarification asks count.
- **Enforcement integrity** — block-followed-by-receipt = failure,
  always surfaced.

Denominators: **distinct source incidents** and **generated variants**
reported as separate counts in every table.

## 8. Paper outline + evidence table

Sections: 1 Intro (agent exfiltration via documented incidents) ·
2 Threat model & enforcement-point taxonomy · 3 Gateway design
(binding: request→action, value→provenance, reply→request) ·
4 Evaluation (§7) · 5 Boundary analysis (what it cannot see) ·
6 Related work (§6) · 7 Limits & honest conclusions.

| claim | supporting artifact today | missing evidence |
|---|---|---|
| C1 inspection adds enforcement | `results/url_gw_isolation/` (frozen) | incident-derived suite (§7.1), M2 baseline cell |
| C2 provenance auth separates egress | mechanism demo (`run_shadowleak_mechanism_demo.py`) | incident-derived cases; non-literal-payload behavior |
| C3 unmodified-planner property | module design; planner claims treated as untrusted | adversarial-planner probe suite |
| C4 clarification utility | protocol + frozen harness (unrun) | human-authored cases — H1/H2 paused pending Sai's packet |
| C5 boundary catalogue | source mapping (INC-09/10/13/15/16 documented as out-of-scope) | per-class confirmation demos |

**Preservation rule**: all frozen runs, including failures (the `_r2`
rerun, unresolved clarifications, enforcement failures if they occur)
are kept and reported; no results invented, no novelty claimed beyond
what the evidence table supports.
