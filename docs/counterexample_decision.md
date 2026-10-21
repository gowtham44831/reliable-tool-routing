# Counterexample decision — candidate A (cumulative disclosure)

## OCELOT added to the comparison

arXiv 2606.12341 (Xie & Li, 2026-06 preprint): **"Inference-Leakage
Budgets for Privacy-Preserving LLM Agents"** — runtime mediator that
budgets posterior-risk improvement per release across a trajectory;
Witness-Verified Declassification (untrusted defender model emits
labeled atoms + declassification operators; deterministic verifier
charges certified min-entropy cost; tamper-evident ledger;
sink-trust-weighted budget). OCELOT is the **inference-control**
mechanism — it subsumes, in its general model, all four
sub-mechanisms below, at the cost of an LLM in the evidence path,
min-entropy costing, and an inference model.

## The four sub-mechanisms, distinguished

| mechanism | definition | existing-semantics status |
|---|---|---|
| **value accounting** | union of literal delivered values vs authorized set | **redundant** — see below |
| **reconstruction** | slices delivered across calls reassemble a protected value at the receiver | **live — but a matching failure** |
| **combination constraints** | individually-permitted fields jointly forbidden to a recipient | no clause exists → new policy required |
| **inference control** | deliveries enable inferring an undelivered secret | needs an inference model → OCELOT's space |

### Value accounting — no counterexample

Record `a1`: `{"data_owner":"vic.tim", "effect":"allow",
"permitted_fields":["vic.full_name","vic.passport_no"],
"destination_principal":"docs.svc",
"purpose":"research_summary", "constraints":{"not_after":"2027-01-01"}}`.

Call 1 `{name:"Vic Tim"}` → matched field, covering record → allow.
Call 2 `{passport:"X123"}` → same → allow. Union = both fields to
docs.svc — **exactly the authorized set**. Union of per-call-allowed
values is always ⊆ union of authorized fields, so pure value
accounting catches nothing the per-call check misses → redundant
under existing semantics. (Adding a use-count *quota* would be a new
policy — and AGATE's "grants permit a limited number of uses"
already implements it.)

### Reconstruction — counterexample exists; failure class = matching

- **Permission record** (only one): `a2`: allow `vic.full_name` →
  `billing.svc`, purpose `invoice_lookup`, unexpired. **No** record
  covers `vic.passport_no` → `billing.svc`.
- **Call 1**: `https://billing.example/i?name=Vic Tim&d=WDEy`
  (`WDEy` = base64 `"X12"`), declared `["vic.full_name"]`.
- **Call 2**: `https://billing.example/i?name=Vic Tim&d=Mw==`
  (`Mw==` = base64 `"3"`), declared `["vic.full_name"]`.
- **Why M3 legitimately allows each**: host on allowlist; `name`
  exactly matches `vic.full_name` and `a2` covers it → `permitted`.
  Carrier `d` produces no match → `unaccounted`, **but**
  `url_fetch_gateway.py:307` suppresses the finding whenever
  `declared & matched_ids` is non-empty — one authorized field
  launders an arbitrary extra carrier. No blocking finding → allow +
  deliver.
- **Clause the combined deliveries violate**: **R3/F3** —
  `vic.passport_no` (protected class) delivered to `billing.svc`
  with no covering permission record. The union of the two `d`
  carriers decodes to `X123`; neither call alone contained it.
- **New assumption required**: a **reconstruction matcher** —
  cross-call concatenation of carrier payloads per
  (destination, purpose) with decode+match over the accumulated
  bytes. This is new detection machinery, NOT metadata already
  available. A plain union ledger of *matched* values records
  nothing here — `d` never matched.

## Decision (per the stated rules)

**Counterexample exists; failure class = matching failure.** Per the
rule: *investigate reconstruction coverage; a union ledger alone is
not the solution.*

Consequently:

- **Candidate A as "value accounting" is closed — redundant** under
  existing record semantics.
- The surviving gap is **deterministic reconstruction coverage**:
  accumulate delivered carrier bytes per (recipient, purpose) and
  re-run the existing decode+match machinery over the accumulation.
  Distinct from OCELOT (deterministic exact-reconstruction vs
  probabilistic min-entropy budget; no LLM in the path, no inference
  model) — "simpler" remains a **hypothesis** until the comparison
  runs.
- **Not pursued**: combination-constraint policies and inference
  budgets — each needs new policy machinery already substantially
  occupied by OCELOT (inference budgets, declassification operators)
  and AGATE (use-limited grants). Record, don't build, unless
  reconstruction coverage fails first.
- Immediate non-research item found incidentally: the F5 suppression
  (`unaccounted` suppressed when any declared field matches) was a
  *per-call* coverage hole — one authorized field laundered extra
  carriers in a single call. **Resolved**: reproduced with receiver
  traces (`results/f5_coverage_repro/`), corrected as
  `url-gw-1.1` (`f5_mode="strict"`, `f5_mode="legacy"` preserves the
  frozen-evaluated behavior). Under the corrected baseline the split
  example is blocked per-call: *"this example does not establish
  additional protection from cumulative reconstruction over corrected
  per-call enforcement."* Residual analysis: reconstruction adds no
  protection without unacceptable legitimate blocking within the
  bounded interface → **direction closed under existing semantics**
  (see `results/f5_coverage_repro/REPORT.md`).
