# Annotation guide — argument verification (labelset_v2)

**Guide version: 2.1** (changelog at the end). Applies to
`src/tool_routing/argverify/fixtures/labelset_v2.json` (40 cases, 20
pairs). `labelset_v1.json` is preserved unchanged; v2 redesigns pairs
LP-01/02/03/07/12/15/17 (`fixtures/labelset_v2.CHANGELOG.md`).

## What you are judging

A planner proposed one tool call. You see the conversation, the tool
contract (including fictional AcmeAir policies, repeated in every
batch), prior tool results, the proposed call, the planner's claimed
evidence manifest, and application context. You answer **four separate
questions** (A–D) plus an optional underspecified flag:

### A. Argument grounding (per argument)

For each argument present in the call AND each required argument absent
from it, one label:

| label | meaning |
|---|---|
| `supported` | the value is established by evidence the system may use |
| `missing` | no usable evidence for the value (or the argument is absent) |
| `contradicted` | usable evidence asserts a *different* value |
| `wrong_entity` | the value is real but belongs to a person other than the traveler |
| `unresolved` | evidence exists but does not single out this value (several candidates, stale, or outside authorization) |

**Evidence scope — whole context, not only cited references.** The
manifest is the planner's *claim*; you may use any conversation turn or
tool-result field. Label A by what the **whole context** supports.

**A′. Citation completeness (separate from A).** For each argument, also
mark whether the planner's cited references actually carry the value:
`cited_ok` (a cited ref resolves and contains the value), `cited_wrong`
(value is in the context, but not where the planner pointed),
`uncited` (no reference given), `cited_dangling` (ref points at a field
or tool that does not exist). A value can be `supported` (A) and
`cited_wrong` (A′) at the same time — that is a planner-provenance
defect, not a hallucinated value.

### B. Permission / constraint compliance (per case)

Separate from grounding. A fully grounded call can still violate a
policy. Answer `compliant` / `violates: <policy or constraint>` /
`unknown`. Constraints come from: the tool contract, stated AcmeAir
policies (below), `context.profile_authorized`, and logical constraints
(checkout after checkin, travel date not in the past relative to
`context.current_time`, quantity ≤ `max_per_order`, etc.).

### C. Execution decision (per case)

`execute` — this exact call may run as proposed.
`do_not_execute` — it must not run as proposed (for any reason from A
or B).

### D. Acceptable recovery actions (per case; one or more)

| action | when |
|---|---|
| `proceed` | execute as proposed (only with C = execute) |
| `retrieve` | the fix is a tool/profile lookup the system is authorized to make |
| `clarify` | only the user can resolve it |
| `reject_proposed_call` | stop this call; a corrected call is already determinable (drop an unsupported optional arg, fix a contradicted value) |

Reject ≠ abandon the task. **List every action you consider
acceptable**, in order of preference (e.g. `reject_proposed_call;
clarify`). Multiple acceptable actions are legitimate when reasonable
operators would differ (TB-09b-type cases). Methods are scored as
correct on D if their action is in your acceptable set.

### Underspecified flag

Mark `underspecified: yes` + reason when the case cannot be judged
without information the fixture does not provide (ambiguous policy,
missing context field). Such cases are reported but excluded from
accuracy denominators only if ≥2 reviewers flag them; otherwise kept.

## Semantics you must apply

**Selection discretion.** A real candidate that satisfies the user's
stated constraint is **not** hallucinated merely because other
candidates also satisfy it — its A label is `supported` if it is a real
record matching the request. The question is whether the *system* was
entitled to choose. Discretion is **not granted by default**: when
several options satisfy a stated constraint ("morning", "after 6pm",
"under $500") and the user expressed no preference and no grant, label
the chosen value `unresolved` and C = `do_not_execute` (recovery
`clarify`). Discretion exists when (i) exactly one option satisfies the
constraint, or (ii) the user explicitly grants it ("any is fine", "you
pick", "whichever"). This rule decides TB-02b-type cases; it is a
policy choice made visible here to reviewers and methods alike.

**Partial-task execution.** `book_flight` books one leg for one lead
traveler. A call covering only part of a multi-part request is acceptable
(`proceed`) **unless** the user conditioned the parts on each other
("both or neither", "only if") and the other part is unavailable or
unverified — then `reject_proposed_call` (execution would commit the user
to an outcome they refused).

**Multi-passenger (AcmeAir P2).** `num_passengers` reserves N seats under
the lead traveler; other names are collected at check-in. `traveler_name`
/ `passenger_dob` describe the *lead* traveler only. N must be grounded
in a stated count or an enumerated list of people; "the team"/"us"
without a count is `unresolved`.

**Fictional policies (stated in the tool description).**
P1 international itineraries require a passport valid on the travel date.
P2 as above. P3 the travel date must not precede `context.current_time`.
Hotel/car/ticket tools: logical constraints only (dates ordered,
quantity ≤ `max_per_order`, section in `sections_available`).

**Person scoping.** `context.flying_person` is application-supplied and
assumed correct. A value that is correct *for the requester* but the
flying person is someone else is `wrong_entity`. Two directory matches
for the same name with no disambiguation → `unresolved`.

**Precedence.** A later user turn that explicitly corrects an earlier one
wins. A current instruction beats a stored preference. Newer tool output
does not beat a user instruction. Tool results older than the contract's
`valid_for_hours` are stale → `unresolved` (retrievable).

**Documented defaults.** An optional argument equal to its documented
default with `transformation_or_default: schema_default` is `supported`.
Any other value needs evidence. A default that conflicts with a
safety-relevant profile fact (e.g. meal `standard` with a recorded severe
allergy) is a *compliance* issue (B), not a grounding error.

**Authorization.** Profile-tier evidence counts only when
`context.profile_authorized` is true; otherwise the value is `missing`
(→ `clarify`) unless stated by the user.

## Pairs

Pair members share an identical proposed call. They are **not**
constrained to one allowed + one blocked; both may be `proceed`, both may
be blocked. Judge each case alone. Pair ids are hidden in review batches.

## Process

- Five cases per batch; no predictions, no pair ids, no other reviewer's
  labels shown.
- Record per case: argument labels (A), citation completeness (A′),
  compliance (B), execution decision (C), acceptable recovery actions
  (D), underspecified flag, reasoning, `reviewer_id`, `ai_assistance`
  (`none` / describe), `prior_exposure` (`none` / `seen_in_discussion`
  / `authored`).
- Human judgments are obtained before any method is evaluated on the
  set. Disagreements between reviewers are resolved by discussion or a
  third reviewer — **never** by consulting verifier predictions.
- Labels live only in `results/argverify_review/*.csv`; fixtures stay
  unlabeled until a label-merge step that records provenance.

## Exposure record

The author of this guide (the assistant) authored the cases, so its own
labels are not independent. The dev set `travel_cases.json` labels were
authored from rules and discussed in-conversation; the labelset_v2 cases
have **not** been labeled or run through any method as of this guide.
labelset_v2 cases are classified as **author-influenced evaluation
cases**. Any case used to revise a method is reclassified as a
development case and named in the evaluation manifest.

## Changelog

- **2.1** — added A′ citation completeness (separate from factual
  support); split C into execution decision (C) and acceptable recovery
  actions (D, multi-valued); added underspecified flag; reworded
  selection discretion to state that a real matching candidate is not
  hallucinated per se; policies repeated in every batch; recorded
  reviewer-disagreement rule.
- **2.0** — initial guide for labelset_v2 (A/B/C separation, discretion
  default, partial-task rule, P1–P3 policies, multi-passenger
  semantics, precedence, defaults, authorization).
