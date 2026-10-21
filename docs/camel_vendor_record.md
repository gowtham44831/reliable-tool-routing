# CaMeL vendor-in record — EXECUTED

Vendoring completed into `src/third_party/camel_policy/` (moved
under src/ to match the src-layout editable install). Record below
updated with as-built facts.

Required record before any upstream code enters this repo.

## Source

- Repo: https://github.com/google-research/camel-prompt-injection
- Commit: `f083b6b396399d3b3c7f2ddaf613a5945eaf32d8` (main, cloned
  to /tmp/camel-repo for inspection)
- License: Apache License 2.0 — compatible; license header must be
  preserved on every vendored file, LICENSE text carried in the
  vendor dir, attribution in NOTICE/headers.
- Support status: unmaintained research artifact (upstream README).

## Minimal file set (policy component only)

| file | needed for |
|---|---|
| `src/camel/security_policy.py` | SecurityPolicy protocol, engine, base policy |
| `src/camel/capabilities/{readers,sources,capabilities,utils}.py` | readers/sources metadata |
| `src/camel/interpreter/value.py` | CaMeLValue types carrying capabilities |
| `src/camel/interpreter/op_protocols.py` | value.py dep |
| `src/camel/conditional_cache.py` | value.py dep |

`value.py` lazily imports `camel.interpreter.library` and
`namespace` (TYPE_CHECKING) — those methods are unexercised by
policy checking; the lazy imports may need stubbing or the files
included. Total: ~8 files, vendored under
`third_party/camel_policy/` — an isolated adapter, NOT a pip
dependency on the full `camel` package (which would pull
agentdojo/anthropic/openai/genai).

## Required dependencies (as built)

- `pydantic==2.11.5` (installed into .venv for this), stdlib.
- NOT required: agentdojo, anthropic, openai, google-genai,
  vertexai, pydantic-ai.

## Modifications performed (complete list)

1. Mechanical path rewrites `camel.` → `third_party.camel_policy.`
   in `from`/`import` statements — verified no other `camel.` refs.
2. `library.py`/`namespace.py` NOT vendored — their lazy imports
   inside `.attr()` methods point at the absent path; our usage
   (`CaMeLStr.from_raw`, `get_all_readers`,
   `can_readers_read_value`, `check_policy`) never exercises them.
3. Package `__init__.py` files added at `src/third_party/` and
   `src/third_party/camel_policy/` (empty).
4. NO semantic changes to policy or capability logic — hash-
   recorded in results/camel_component_eval/manifest.json.

## Observed upstream caveat (released code, unpatched)

`base_security_policy` compares `get_all_readers(...)`'s
(readers, visited) TUPLE against `Public()` — released behavior
denies ALL kwargs, including fully-public values. Reported
verbatim in the descriptive arm; not patched.

## Attribution

Copyright 2025 Google LLC retained in headers; `THIRD_PARTY_NOTICES`
entry; arm labeled "CaMeL released base-policy component with
adapted capability inputs."

## What this does NOT exercise

CaMeL's interpreter-tracked provenance propagation, its privileged/
quarantined-LLM planner, and control-flow protections. Capability
metadata is supplied by OUR adapter.
