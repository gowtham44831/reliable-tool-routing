# Review package — pre-release checklist

Prepared for internal review only. **Nothing has been published,
uploaded, or sent to editors.**

## Delivered

| item | location |
|---|---|
| Updated README (install, deps, licenses, third-party attribution, AI-assistance note) | `README.md` |
| Reproducible demonstration (3 scripted scenes → traces) | `scripts/demo_showcase.py` → `results/demo_showcase/` |
| Technical report (mechanism, baselines, what actually exercised authorization, failures, limits, repro commands) | `docs/technical_report.md` |
| Publication-pitch abstract (208 words, two-lesson lead) | `docs/publication_abstract.md` |
| Labeled archive | `archive/` (+ `archive/README.md`) |
| MIT license file | `LICENSE` — holder: **Sai Gowtham Reddi** (git author of record) |
| Third-party notices | `THIRD_PARTY_NOTICES` (created — was missing) |
| Claim-supporting artifacts (228 KB) | `artifacts/` — copies of the `results/` dirs cited by the report |

## Licensing verification

- MIT `LICENSE` now names the actual copyright holder (git author of
  record).
- `src/third_party/camel_policy/LICENSE` = Apache-2.0 verbatim;
  per-file `Copyright 2025 Google LLC` headers intact; upstream
  commit `f083b6b`; modifications limited to import-path rewrites.
- Right to publish: all fixtures/PII are fictional; ToolRet raw data
  was never committed (git-ignored `data/`); the only third-party
  code in-tree is the Apache-2.0 vendored closure. No ownership is
  assumed beyond that.

## Scan results (clean)

- No credentials/keys/tokens in code, docs, or git history (single
  base commit scanned too).
- Only non-placeholder e-mail in tree: `security@facebook.com`
  (AgentDojo fixture value quoted in `camel_smoke_report.md`).
- `/private/tmp/camel-smoke-venv` referenced in docs — scratch env
  path, retained intentionally for honesty of the record.
- Git history: single base commit + working tree; no secrets found.

## Remaining open items

- [ ] `CITATION.cff` `repository-code` — fill in the real URL at
  publish time.
- [ ] Decide whether `results/` stays git-ignored (recommended) —
  `artifacts/` is the curated public subset; if release tarballs are
  preferred, attach them at release time instead.
- [ ] Git history: single base commit + uncommitted tree — decide
  commit strategy for the release snapshot.

## Pitch wording verified against evidence

- 4/7 vs 7/7 → described as "a small interface-development
  comparison (7 tasks)" — not a general validity rate.
- 8/8 → "policy-component comparison … compatibility, not system
  equivalence"; CaMeL planner/provenance/control-flow unevaluated.
- Demonstration "illustrates mechanisms; it estimates no real-world
  prevention rate" — stated in the abstract, the report, and the
  demo script header.

## Explicitly NOT done (per instruction)

Publish repo, Zenodo upload, editor contact — deferred until the
documents are reviewed.
