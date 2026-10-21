# Novelty assessment — "Evidence-Bound Authorization for Data Disclosure in AI Agents"

Candidate question: *Can independently checking evidence and binding
authorization to a specific outgoing action prevent unauthorized
disclosures while reducing unnecessary clarification and preserving
legitimate task completion?*

Basis: full texts (arXiv HTML) of CaMeL, Fides, RTBAS, AirGapAgent,
AgentDojo, plus the public repositories. Section numbers refer to the
arXiv versions cited. Where I could not find a capability I say
"not found in full text", not "absent".

## Bibliographic / release verification

| work | citation | release |
|---|---|---|
| **CaMeL** | Debenedetti, Shumailov, Fan, Hayes, Carlini, Fabian, Kern, Shi, Terzis, Tramèr. *Defeating Prompt Injections by Design.* arXiv:2503.18813v2, 24 Jun 2025 | code: github.com/google-research/camel-prompt-injection (stated in abstract) |
| **Fides** | Costa, Köpf, Kolluri, Paverd, Russinovich, Salem, Tople, Wutschitz, Zanella-Béguelin. *Securing AI Agents with Information-Flow Control.* arXiv:2505.23643v2, 3 Sep 2025 | github.com/microsoft/fides — **tutorial notebook only** (README: "Jupyter notebook to accompany the paper"; tested on GPT-4o/4.1 via Azure); not an evaluation harness |
| **RTBAS** | Zhong, Chen, Wang, McCall, Titzer, Miller, Gibbons (CMU). *RTBAS: Defending LLM Agents Against Prompt Injection and Privacy Leakage.* arXiv:2502.08966v2, 14 Feb 2025 | **no public code found** (web search returns only the paper) |
| **AirGapAgent** | Bagdasarian, Yi, Ghalebikesabi, Kairouz, Gruteser, Oh, Balle, Ramage. CCS 2024; arXiv:2405.05175v2 | no code release found in paper |
| **AgentDojo** | Debenedetti, Zhang, Balunović, Beurer-Kellner, Fischer, Tramèr. NeurIPS 2024 D&B; arXiv:2406.13352v2 | github.com/ethz-spylab/agentdojo; docs at agentdojo.spylab.ai |

## Comparison matrix (with section citations)

Legend: ✔ present and evaluated · ◐ present by design/assumption, not evaluated · ✗ not found in full text · n/a not applicable to the design

| capability | CaMeL | Fides | RTBAS | AirGapAgent | AgentDojo | this proposal |
|---|---|---|---|---|---|---|
| **Verification of planner-supplied evidence references** | n/a — provenance is *computed* by the interpreter's data-flow graph (§5.4 "Maintaining the data flow graph"); the P-LLM writes code, there are no free-text citations to verify | n/a — labels propagate mechanically through planner memory (§4.2); planner cannot assert provenance | ◐ — provenance is *inferred* by dependency screeners (LM-judge §7.1, attention §7.2), accuracy reported (§8.3.1: 81% test accuracy for the attention screener); not a claim-then-verify scheme | n/a — single-agent minimizer (§4.1) | n/a | claim-then-resolve against trusted records; for **black-box planners** that cannot be restructured as CaMeL/Fides programs |
| **Data ownership + recipient authorization** | ✔ — capabilities = provenance + *allowed readers* (§5.3); Appendix E policies: "send email: recipients must come from the user, email body, subject and attachments must be readable by all recipients" | ✔ — confidentiality labels as reader sets, per-field via `metadata` nodes (§4.1 "Attaching labels to data"); egress policies P-F (§4.3) | ✔ — confidentiality lattice; §6.2 notes it can be "the set of channels allowed to access information" | ◐ — contextual-integrity appropriateness per (task, directive, field) (§2.2); recipient is the single third party | n/a (benchmark) | same as CaMeL/Fides — **replication** |
| **Field-level disclosure restrictions** | ✔ — per-value capabilities; §5.3 passport-number example | ✔ — per-field labels in tool-result tree (§4.1) | ◐ — region-level labels within messages (§7.3) | ✔ — field-level minimization (§4.1) | n/a | same — **replication** |
| **Binding approval to the exact action** | ◐ — policies checked on the actual argument values at tool-call time (§5.4 "Enforcing security policies"); structurally bound because the interpreter executes what it checked. User confirmation on violation (§5.4, footnote 3). No atomicity/rollback (§5.4 "Error handling"). Re-verification after user-edited payload: ✗ | ◐ — deterministic per-call enforcement (§4.3); re-verification semantics after modification: ✗ | ◐ — halt for confirmation (Alg. in §7.3); confirmations **not modelled in evaluation** — violating calls simply skipped (§8.1.1: "we do not model user confirmations… skipped and unperformed") | n/a | n/a | gateway-controlled approval record + fingerprint, re-check on any recipient/payload change — a **TOCTOU concern that only arises for a gateway separate from the executor**; not present in the integrated designs |
| **Missing, conflicting, or forged metadata** | ◐ — assumes user prompt trusted (§3); tools assign capabilities (§5.3); no evaluation of wrong/missing capabilities found | ◐ — "we ensure that all untrusted tools have trusted wrappers, so that we can assume that all tools label their outputs correctly" (§4.1); safe default suggested, not measured ("In the absence of labels… resort to safe defaults", §4.1) | ◐ — labels assumed provided (§6.2: "we assume these labels… are provided… an open problem in IFC"); **unlabeled regions default to most permissive (public, trusted)** (§7); §8.1.2: one user-labelled high-integrity text contained an injection — "guarantees… only as good as the labels provided" | ◐ — assumes context provided by user before interaction (§4.1) | n/a | **measured degradation** under missing / wrong labels and forged planner claims — not found as an experiment in any of the five |
| **Recovery via clarification or payload revision** | ◐ — user confirmation (§5.4); discusses declassification + fatigue (§9.2); avoiding unnecessary prompts is a stated goal (§3.1); no automatic payload revision found | ◐ — hiding/revealing applies to *planner inputs* (§5.1–5.2), not outbound payloads | ✔ (clarification burden measured, §8 RQ3, Fig. 7) — **input-side** redaction of history regions (§7.3); outbound payload revision: ✗ | ◐ — minimization *before* the conversation (§4.1); no post-hoc revision | n/a | redact-and-recheck of the outbound payload; clarification valid only from a principal with authority over the data owner's fields — **owner ≠ requester** case not found in any of the five (CaMeL footnote 3 lets the *user* approve sharing a document Bob cannot read) |
| **Actual disclosure measured at destination** | ✔ — via AgentDojo environment-state checks | ✔ — via AgentDojo | ✔ — via AgentDojo + own privacy benchmark (§8.2) | ◐ — MCQ/open-ended answer scoring (§5.3), not destination state | ✔ — "formal utility checks computed over the environment state" (§1; §3.1 "Environments and state") | same — **standard practice, not novel** |
| **Stated limitations / assumptions** | user prompt trusted, memory uncompromised (§3); text-to-text attacks and phishing out of scope (§3.1); side channels (§7); not fully autonomous (§3.1) | agent configuration trusted (§2.1); tool wrappers label correctly (§4.1); explicit secrecy not full non-interference for confidentiality (§4.4) | labels provided by developer (§6.2); unlabeled = permissive (§7); confirmations not modelled (§8.1.1); Slack suite utility 22–33% (§8.1.2) | context provided a priori; single third party | benchmark only | — |

## What the matrix shows

1. **Ownership/recipient authorization and field-level restrictions are
   solved in CaMeL (§5.3, App. E) and Fides (§4.1, §4.3).** Our
   deterministic policy method would be a re-implementation of CaMeL's
   send-email policy in a gateway. No contribution there.
2. **"Evidence verification" is not a capability those systems lack —
   they make it unnecessary** by computing provenance structurally
   (CaMeL §5.4, Fides §4.2). It only matters for a *black-box planner*
   that cannot be rewritten as a CaMeL program. RTBAS is the one
   design that, like ours, must *infer* provenance for an unmodified
   planner (§7.1–7.2) — and it reports screener accuracy (§8.3.1).
3. **Measured dependence on metadata correctness is genuinely absent**
   from all five full texts: each assumes labels are provided and
   correct (CaMeL §3; Fides §4.1; RTBAS §6.2/§7), RTBAS explicitly
   defaults unlabeled data to *public, trusted* (§7), and RTBAS
   itself names this "a major limitation… as with any other IFC
   technique" (§8.1.2). Nobody quantifies it.
4. **Recovery is confirmation-only** in all three defenses, and RTBAS
   does not even model it in its evaluation (§8.1.1). Outbound payload
   revision with re-check, and the owner-authority condition on who may
   clarify, were not found.
5. **Destination-state measurement is standard** (AgentDojo §1, §3.1);
   claiming it as a contribution would be wrong.
6. **Action binding** is structural in integrated designs; it is a real
   problem only for a separate gateway — i.e., a problem our
   architecture *introduces* and then solves. That is engineering
   hygiene, not a research contribution.

## Recommendation: **the proposed contribution needs narrowing**

Not "justified as proposed": the mechanism (evidence + ownership +
recipient + field-level policy at egress) duplicates CaMeL/Fides.
Not "pure replication": items 3 and 4 are unmeasured axes, with
citations above showing where each prior work assumes them away.

**Narrowed, measurable question:**

> For an egress gateway over an *unmodified* planner, how much
> disclosure safety and task completion are lost, relative to an oracle
> with correct metadata, when (a) sensitivity/owner labels are missing
> or wrong on a controlled fraction of fields, and (b) planner-supplied
> provenance claims are mistaken or forged — and does owner-authority-
> aware recovery (redact-and-recheck; clarification only from a
> principal with authority) recover completion without re-introducing
> leaks?

This is an **evaluation contribution** about the conditional nature of
IFC-style guarantees, using CaMeL-style policies as the deterministic
baseline (cite, do not claim), with RTBAS's screener accuracy (§8.3.1)
as the closest prior number. Expected scale: small (fixtures of ~40
episodes), and the result may be "degradation is linear in label
error and nothing clever helps" — which would still be a reportable
finding. Novelty remains **unverified** until the experiment shows the
gap matters.

**Do not** frame the gateway, action fingerprinting, or destination
measurement as contributions. **Do** cite CaMeL App. E as the source of
the policy set.
