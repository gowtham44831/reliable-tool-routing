# Pre-evaluation freeze checklist (labelset_v2)

Every box must be checked, in order, before `run_argverify_eval.py` is
invoked on NV cases. Each check is recorded by hash in `MANIFEST.json`.

- [ ] **Dataset** — `labelset_v2.json` sha recorded; CHANGELOG final.
- [ ] **Policies** — AcmeAir P1–P3 + discretion/partial-task/authorization text in the shared schema and batch header are identical (diff checked); policy version string set.
- [ ] **Annotation guide** — version pinned (2.1 or later); no edits after the last label is returned, except versioned ones flagged per case.
- [ ] **Labels** — all 8 batches returned; disagreements adjudicated in `ADJUDICATION.md`; `labelset_v2_LABELS.csv` merged once; sha recorded.
- [ ] **Implementations** — sha of `schema.py`, `evidence.py`, `methods.py`, `policy.py`, `llm.py`, `llm_v2.py`, `llm_providers.py`, `evaluate.py`, `run_argverify_eval.py` recorded; `git status` clean on these files.
- [ ] **Prompt** — `PROMPT_SHA` = `68efada2872c58b9` (or a new versioned prompt, recorded).
- [ ] **Model configs** — ids pinned (`qwen3:14b` digest `bdbd181c33f2` Q4_K_M; `gpt-5.4-2026-03-05`; `claude-sonnet-5-5`), max_tokens 2048, reasoning setting per provider, timeout 300 s, retries 0.
- [ ] **Smoke tests** — each provider adapter exercised on TB-01a/TB-01b only; outcomes and any adaptation noted in the protocol §7.
- [ ] **Budget** — paid-call authorization recorded (currently **pending**; proposed ceiling $10).
- [ ] **Development cases list** — any NV case touched during debugging listed in `MANIFEST.development_cases_excluded_from_test_claims`.
- [ ] **Scope statement** — results will be reported as grounding + execution + recovery on static calls; **not** as compliance or security systems; B and A′ reported human-only.

After the run: no edits to any hashed artifact. New work → new version → new future evaluation.
