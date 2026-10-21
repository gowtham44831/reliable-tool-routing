# Task-preserving minimization — feasibility report (go/no-go)

Engineering study only. Fictional users and places; no incident
reproduction; no paid calls; no manuscript changes. All security
code/fixtures/results untouched — work lives in
`archive/exploratory/task_min/`.

## 1. Gap statement (source-backed)

ToolMinimize (arXiv:2608.24957, PST 2026 — Li & Xu, CWRU) rewrites
tool-call arguments to minimum-necessary: removal, generalization,
substitution, truncation; schema `minimum_necessary` annotations;
optional LLM content-necessity layer; `task_context` retention;
fail-prompt mode. **Its own end-to-end validation: 16/20 mock-endpoint
scenarios pass; all four failures are maps scenarios where required
addresses were removed for lack of `minimum_necessary` annotations —
"the over-shared field is also the task payload."** Its reported TCR
is *argument-level validity*, explicitly not end-to-end task utility.

Gap that survives scrutiny: **nothing in the pipeline checks whether
a rewrite still satisfies the task's constraints before dispatch** —
annotations assert, they don't verify; the LLM content layer judges
necessity, not constraint satisfaction; fail-prompt punts to the user.

Prior work (short comparison): query-generalization / location
cloaking (Casper, CliqueCloak, MobiMix-class systems) already does
superset retrieval + client-side refinement for k-anonymity;
API/schema minimization (Progent; GDPR minimum-necessary practice);
PII tooling (Presidio) misses implicit PSD (paper's point). Our
check adds **constraint-verified dispatch** — the rewrite must
*demonstrate* task preservation, not merely look schema-valid.

## 2. Baseline availability

**No author-linked implementation or artifacts found** (searched
paper, arXiv pages, author GitHub) → arm B is a *paper-based
reimplementation* (deterministic; PSD fields declared, no classifier,
no LLM layer, no PC metric). We do **not** claim to reproduce its
exact four failures — we reproduce the *mechanism class* they
document (annotation-guided over-coarsening).

## 3. Executable backend + repro command

`archive/exploratory/task_min/dataset.py` — 14 fictional venues, real
haversine + attribute filtering, schema with annotations; a 6 km
service radius cap stands in for real service limits. Fictional
data — no external location data used, no license needed.

    cd archive/exploratory/task_min && python3 run_diag.py

## 4. Results (diag_traces.json)

| task | A orig | B minimizer | C + check | D superset+refilter |
|---|---|---|---|---|
| T1 grid works | 2 | dispatched ✓ | dispatched ✓ | dispatched (2) |
| T2 grid breaks | 1 | **dispatched broken** | escalated | **dispatched (1, exact)** |
| T3 exact payload | 1 | escalated (fail-prompt) | escalated | escalated — cap infeasible |
| T4 multi-constraint | 1 | dispatched ✓ | dispatched ✓ | dispatched (1) |
| T5 city breaks | 1 | **dispatched broken** | escalated | escalated — cap infeasible |

- B reproduced the paper's failure mechanism: annotation says
  "coarse is fine," task needs finer → schema-valid but task-dead
  calls dispatched (T2, T5).
- The pre-dispatch check (C) catches both — executed the rewrite
  locally, verified against true constraints; zero false blocks on
  T1/T4.
- Arm D (coarsen + radius inflation by generalization-error bound +
  local refiltering) recovered the *exact* task answer for T2 with
  coarse disclosure — and hit the service cap on T3/T5, correctly
  escalating. **Blocked tasks counted as blocked, not completions.**
- Disclosed fields: arms B–D send only `{category, lat, lon(coarse),
  radius}` vs original's `{…, lat, lon(exact), user_name, note}`.
- Latency: all arms < 1 ms local (latencies meaningless beyond
  plumbing, per instruction — recorded, not inferred from).

## 5. What the candidate adds — honest accounting

- The **check** needs a locally evaluable backend model — here the
  real dataset. For general services that's a replica: heavy
  deployment cost, documented.
- The **superset+refilter** construction needs only a *geometry
  bound*, no replica — for monotone range constraints it is
  self-verifying. But it **is** classical location-cloaking
  architecture (superset query → client refinement) applied to
  tool args — an adaptation, not a new mechanism.
- Marginal delta over ToolMinimize's own mitigations: fail-prompt
  already catches T3-type conflicts; the check uniquely catches
  *silent* task-breaking rewrites (T2/T5) that annotations can't.
  That class was their documented 4/20 — real, but narrow.

## Recommendation: STOP as a research direction

Stop-criteria met: (i) the strongest version (arm D) is the existing
LBS-cloaking superset architecture — closing it as a *novel*
contribution fails the rename test; (ii) the residual check has
value only where a local replica or bound exists, narrowing adoption;
(iii) annotation + fail-prompt already cover the common cases.
Feasibility is *established* (the mechanism works and is cheap), but
the remaining claim is "cloaking + a constraint gate applied to tool
calls" — an engineering integration, not a journal contribution.
Reopen only as a bounded engineering component if a future paper
needs it.
