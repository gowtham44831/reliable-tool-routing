# Technical report — egress gateway evidence state

Companion evidence summary for the showcase release. Every
quantitative claim links to a saved artifact. Exploratory runs are
reported separately; **no combined prevention rate is claimed**.

## What the gateway does and assumes

`src/tool_routing/argverify/url_fetch_gateway.py` (`url-gw-1.1`)
inspects a planner-proposed outbound URL *before dispatch*:

- F1: the serialized URL is the checked object (structured calls are
  Base64-serialized by `planner_adapter` first).
- F2: host allowlist.
- F3: every matched protected-class field needs a covering
  permission record for the destination principal + bound purpose +
  unexpired window; deny records win.
- F4: matched values lacking provenance metadata are unresolved —
  never default-safe.
- F5 (v1.1): every non-path carrier's atoms must each exact-match a
  retrieved value; sibling-carrier laundering removed; declarations
  are hints; path segments exempt (recorded limitation).

Assumptions, stated plainly: application-supplied `field_metadata`
provenance is trusted; `ContextIssuer` supplies (task, session,
purpose) from trusted app state — an **in-process registry, not
cryptographic attestation**; matching is exact/bounded-decode, not
full IFC; dispatch is loopback-only mocks.

## What each baseline checks

| arm | checks |
|---|---|
| M0_no_gateway | nothing — receipt baseline |
| M1_allowlist | destination host only |
| M2_content_inspect | decode + field match; **no authorization consulted** |
| M3_full_gateway | host + decode + match + permission records + context binding |
| camel-base-policy | released `base_security_policy` on adapted capability inputs — **descriptive only** |
| camel-m3-intent | custom `SecurityPolicy` expressing M3's intent — **compatibility arm, not a CaMeL reproduction** |

## Which experiments actually exercised authorization

Claim-to-evidence detail: `docs/claim_to_evidence.md`.

- **eval-v4 (scripted calls, adapter-1.3)** —
  `artifacts/eval_v4/{traces.json,REPORT.md}`: authorization decided
  V4-LC1 (permitted, delivered), V4-LC2 (deny-wins), V4-LC3
  (purpose mismatch), plus CB1–CB6 binding checks pre-dispatch.
- **adapter-1.1 corrected replay (saved model outputs)** —
  `artifacts/planner_pilot_v2_adapter11/`: the ONLY cells where field
  authorization decided *model-generated* calls (P2-AD1 block,
  P2-LC1 permitted delivery).
- **multistep-pilot-v2 (live model, dev-informed rerun)** —
  `artifacts/multistep_pilot_v2/`: real receipts incl. unauthorized
  X123 at attacker (M0) and invented-host LC deliveries (M0);
  blocks decided by **host filter and payload coverage, not
  authorization**. No adaptive retries generated.
- **multistep-pilot-v1** — `artifacts/multistep_pilot/`: dominated by
  interface failures (invalid `base_url`); schema rejection ≠
  gateway protection.

## Implementation failures and corrections

| failure | fix | evidence |
|---|---|---|
| adapter-1.0 serialized calls without purpose context | 1.1 trusted-purpose | `docs/binding_test_report.md` |
| 1.1 equality check — fabricated field-identical context passed | 1.2 identity check | same |
| 1.2 issuer keyed per-session — cross-task reuse possible | 1.3 keyed (task,session) + replacement invalidation | `artifacts/adapter_1_3_binding/` |
| url-gw-1.0 F5: declared+matched field laundered sibling carriers | 1.1 strict per-carrier accounting | `artifacts/f5_coverage_repro/` |
| contract A (text schema) 4/7 valid vs contract B 7/7 | B frozen for v2 | `artifacts/interface_dev/` |
| released `base_security_policy` denies even public args (tuple compare) | reported verbatim, unpatched | `scripts/repro_base_policy_denies_public.py` |
| qwen3:14b cannot emit CaMeL DSL in 3 attempts | full-CaMeL local eval closed as infeasible | `docs/camel_smoke_report.md` |

## Component comparison result

`camel-m3-intent` agreed with M3 on **8/8** saved eval-v4 requests —
`artifacts/camel_component_eval/{traces.json,REPORT.md}`. Interpreted
as *equivalent observed decisions on this suite* supporting policy
integration — not a new authorization mechanism. CaMeL's planner,
provenance propagation, and control-flow protections are
unevaluated.

## Limitations

Single local model (qwen3:14b); fictional data; mock receivers;
exact-match coverage (encoded/semantic variants unhandled —
1/10 split-evasion class remains); path-segment carriers exempt from
coverage; no multi-step adaptive adversary demonstrated; no
incident-derived case exercised authorization end-to-end with a live
model (replay only).

## Reproduction commands

```bash
python -m pytest -q                                   # 181 core; 186 with .[data] extra
python scripts/demo_showcase.py                       # 3-scene demo
python scripts/repro_f5_coverage.py [--strict]        # defect + fix
python scripts/run_eval_v4.py                         # scripted v4 eval
python scripts/run_multistep_pilot.py --v2            # model-in-loop (needs Ollama)
python scripts/run_camel_component_eval.py            # 8/8 comparison
python archive/exploratory/task_min/run_diag.py       # closed study
```

Frozen result directories must not be overwritten — see each
`FREEZE.md`.


## Published artifacts

`artifacts/` ships the traces/manifests/reports backing every claim
above (228 KB). Larger redundant exploratory outputs
(`results/toolret_pilot` ~99 MB, disclosure-run intermediates, the
throwaway CaMeL smoke venv) stay OUT of the repository — archived
locally under `results/` (git-ignored) and, on request, as a release
tarball rather than in-tree.

## Verified environment

- Python 3.12 (project venv, `pip install -e .`); tests: 181 pass
  (186 with the `.[data]` extra — `test_toolret_adapter` needs
  pyarrow). Verified from a clean checkout: install, demo, and
  test suite all pass.
- macOS, Apple M4 Pro, 24 GB; Ollama 0.40.6; `qwen3:14b` digest
  `bdbd181c33f2` — needed ONLY by `run_multistep_pilot.py` (v1/v2)
  and `dev_interface_eval.py`. Everything else — demo, eval-v4,
  f5 repro, CaMeL component eval, tests — runs with no model.
- CaMeL smoke used a separate scratch venv (Python 3.12,
  `/private/tmp/camel-smoke-venv`, deleted-at-will) — not shipped.
