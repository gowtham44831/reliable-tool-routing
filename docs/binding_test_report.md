# Context-binding test report — planner-adapter-1.3

Mechanism under test: `ContextIssuer` (in-process registry keyed by
`(task_id, session_id)` → issued `TaskContext` object) + identity
verification inside `serialize_structured_call` — checked BEFORE
serialization completes, hence before any dispatch.

## Where runtime identity is checked

`serialize_structured_call(call, context, issuer, session_id,
task_id)` — the dispatched `session_id`/`task_id` come from
application code arguments, never from fields inside the planner's
call. `issuer.verify` requires ALL of:

1. `context is not None`
2. `context.session_id == session_id` (dispatched session)
3. `context.task_id == task_id` (dispatched task)
4. `self._active[(task_id, session_id)] is context` — **object
   identity**, so a field-copied `TaskContext` fails

On failure → `ContextBindingError` raised during serialization:
the call never produces a URL, so nothing reaches the gateway or
dispatcher. Rejection is therefore strictly pre-dispatch.

## Misuse matrix — all PASSED (19 adapter tests; 171 suite)

| misuse | test | result |
|---|---|---|
| session-B dispatch presents session-A context | `test_session_b_cannot_reuse_session_a_context` | rejected pre-dispatch |
| task-A context reused for task-B in same session | `test_cross_task_reuse_within_session_rejected` | rejected — binding unit is (task, session), not session alone |
| planner-fabricated `TaskContext` copying issued fields | `test_planner_fabricated_context_rejected` | rejected — identity ≠ equality |
| call claims `task_id="admin-task"` + `stated_purpose="admin_purpose"` | `test_planner_chosen_privileged_task_id_cannot_gain_context` | call's claims never consulted; fabricated context rejected; issued context's purpose wins |
| planner `stated_purpose` vs context purpose | `test_planner_purpose_cannot_override_context` | context wins; conflict recorded |
| revoked / never-issued session | `test_revoked_or_unknown_session_rejected` | rejected |
| missing dispatch ids | `test_issuer_requires_session_and_task_ids` | rejected |

## Failures preserved — none this run

All misuse classes rejected. The earlier real failure remains
documented: adapter-1.1 verified by equality (`==`), which a
field-copied context would defeat; identity checking (1.2) and
(task, session) keying (1.3) close it.

## Honest scope

`ContextIssuer` is an in-process registry in the adapter's trust
domain — it binds issued objects to dispatch coordinates, but it is
NOT cryptographic attestation: code holding the issued object can
still present it for its own (task, session) only; it cannot mint
or transplant contexts. Reuse across process restarts, distributed
dispatch, or a compromised application runtime is out of scope.
