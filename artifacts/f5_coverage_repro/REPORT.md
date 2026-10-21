# F5 coverage defect — reproduction + corrected baseline

Fixtures: eval-v4 grounding (Vic Tim / X123). One record `a2`: allow
`vic.full_name` → `billing.svc` for `invoice_lookup`. `passport_no`
has **no** record to `billing.svc` (R3/F3 applies to any combined
delivery). All outcomes below are **tested**, not predicted.

## Reproduction under url-gw-1.0 (legacy mode)

| trace | call | decision | receiver got |
|---|---|---|---|
| T1 | `?name=Vic%20Tim` | **allow** (permitted) | name only — authorized |
| T2 | `?name=Vic%20Tim&d=aGVsbG8td29ybGQ=` | **allow** (permitted; `d` unaccounted, suppressed) | name + opaque b64 payload |
| T3a | `?name=Vic%20Tim&d=X12` | **allow** (same suppression) | name + fragment `X12` |
| T3b | `?name=Vic%20Tim&d=3` | **allow** (same suppression) | name + fragment `3` |

Defect confirmed: one declared+matched field launders arbitrary
sibling carriers. Receiver accumulation of all `d` params in arrival
order = `hello-worldX123` (T2's carrier included); the T3 pair alone
reconstructs `X123` = `passport_no` → R3/F3 violation M3-1.0 never saw.

## Corrected baseline — `url-gw-1.1` (`f5_mode="strict"`)

"Accounted for," defined: every non-path carrier's **atoms** must each
exact-match a retrieved value — decoded text, or each member of a
decoded JSON object/array (the serialized wrapper is structure), else
the raw value. **Partially matched** carriers (some members match,
some don't) are unaccounted → `unaccounted_payload` → block. Empty
values carry nothing. Path segments remain exempt — a recorded
coverage limitation, not a safety claim. Declarations are hints only.

| trace | strict decision |
|---|---|
| T1 | allow |
| T2 | **block** (unaccounted `d`) |
| T3a, T3b | **block** (unaccounted `d`) |

Required statement: **"This example does not establish additional
protection from cumulative reconstruction over corrected per-call
enforcement."**

## Does a residual tradeoff exist? — answer: NO (within the bounded interface)

Under strict accounting, every transmitted atom must equal a complete
retrieved value — fragments can only ride inside individually
authorized whole values. The only residual is a **composite** value
`C` assembled from individually-authorized parts. Constructing it
requires *all* of:

1. `C` present in retrieved content with metadata — else "the union
   reveals C" is an inference claim needing an inference model
   (OCELOT territory, not deterministic matching);
2. records authorizing each part to the same recipient — across
   purposes, which requires history keyed by **recipient**, not
   (recipient, purpose): purpose is an authorization scope, not a
   receiver-memory boundary — a recipient combines messages across
   purposes/tasks. Any ledger must be recipient-keyed or disclose
   that limitation;
3. a receiver-reconstruction model: decode each fragment, THEN
   concatenate (arrival order, delimiter, max history, per-encoding
   rules, repeat/concurrent-call handling) — concat-then-decode is a
   different operation and unmodelled guesses overcount risk;
4. prevention requires checking history + proposed next call
   **before** dispatch — flagging after the last fragment arrives is
   detection, not prevention.

Meeting all four: blocking the second authorized call is **itself a
denial of a demonstrated-authorized use** — the exact cost the
criterion calls unacceptable. Preventing it means treating the
composite as a separately-protected object = a **new
combination-constraint policy** (assess against OCELOT budgets, AGATE
grants, DLP compound rules before coding — not pursued now).

**Verdict: reconstruction adds no protection that corrected per-call
coverage cannot provide without unacceptable legitimate blocking →
direction closed under existing semantics.** Any future comparative
claim must additionally cite stream-reassembly / fragmented-
exfiltration detection in DLP/network inspection — "deterministic,
no LLM" is an implementation difference, not novelty.

## Notes

- 186/186 tests pass; 3 regression tests added
  (`tests/test_url_fetch_gateway.py`).
- Frozen artifacts were produced under url-gw-1.0; no frozen case had
  a matched field + sibling unaccounted carrier, so recorded outcomes
  are unchanged — documented, not re-run.
- `f5_mode="legacy"` preserves the evaluated behavior for
  reproduction; fingerprints record the active version.
