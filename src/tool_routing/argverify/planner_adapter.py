"""planner-adapter-1.0 — structured-params serialization adapter.

Development-version trusted application code: the planner supplies
STRUCTURED query values; this module performs the mechanical
serialization (JSON -> base64 -> ?d= query param) and produces the
final serialized URL that the gateway inspects.

Contract (enforced, tested):
- Serializes EXACTLY the params the planner supplied — no invented
  fields, no repaired identities/values, no defaults filled in.
- Never touches permission_records, field_metadata, or the directory;
  supplies no authorization.
- Output is the FINAL url passed to the gateway as
  planner_call.arguments.url — the checked object is what would go
  on the wire (F1).
- Interface change relative to planner-pilot-v1 is DISCLOSED: v1
  required the model to compute base64 itself; here serialization is
  trusted code, matching how a real client SDK would form the
  request. Results through this interface are reported separately.
"""

from __future__ import annotations

import base64
import json
from dataclasses import dataclass

ADAPTER_VERSION = "planner-adapter-1.3"
PARAM_KEY = "d"  # single carrier param, matching the evaluated cases


@dataclass(frozen=True)
class TaskContext:
    """Application-owned task context established BEFORE the planner
    runs and bound to the current task/session. Purpose is part of
    the trusted context — never inferred from the proposed
    destination, injected content, or evaluator labels. A
    planner-supplied purpose must not override it.

    NOTE (v1.2): immutability alone does not bind a context to a
    session — verification happens at issue/serialize time via
    ``ContextIssuer`` below.
    """
    task_id: str
    session_id: str
    purpose: str | None  # None = unknown -> downstream block


class ContextIssuer:
    """Runtime binding between a task context and its live session.

    The application issues exactly one active context per
    (task_id, session_id) BEFORE the planner runs. Serialization
    verifies the presented context is the issuer's ACTIVE context for
    that session — a context minted for a different session, or a
    planner-fabricated context, is rejected before dispatch.

    This is an in-process registry (same trust domain as the
    adapter); it is NOT cryptographic attestation — documented as
    such.
    """

    def __init__(self) -> None:
        # keyed by (task_id, session_id): one active context per
        # task-in-session — cross-task reuse within a session is
        # rejected, not just cross-session reuse
        self._active: dict[tuple[str, str], TaskContext] = {}

    def issue(self, task_id: str, session_id: str,
              purpose: str | None) -> TaskContext:
        ctx = TaskContext(task_id=task_id, session_id=session_id,
                          purpose=purpose)
        self._active[(task_id, session_id)] = ctx
        return ctx

    def verify(self, context: TaskContext | None,
               task_id: str, session_id: str) -> bool:
        """True iff ``context`` is the active context bound to
        ``(task_id, session_id)`` by THIS issuer."""
        return (context is not None
                and context.session_id == session_id
                and context.task_id == task_id
                # identity, not equality: a planner-fabricated
                # TaskContext with copied fields must NOT verify
                and self._active.get((task_id, session_id)) is context)

    def revoke(self, task_id: str, session_id: str) -> None:
        self._active.pop((task_id, session_id), None)


class ContextBindingError(ValueError):
    """Raised when a presented context is not bound to the session
    being dispatched — the call is rejected BEFORE dispatch."""


def serialize_structured_call(call: dict,
                              context: TaskContext | None = None,
                              issuer: ContextIssuer | None = None,
                              session_id: str | None = None,
                              task_id: str | None = None) -> dict:
    """Map a structured planner call to a serialized url_fetch call.

    Input:  {"tool": "url_fetch_struct",
             "base_url": "http://host/path",
             "params": {"k": "v", ...},
             "payload_fields": [...] (optional claim, passed through)}
    Output: {"tool": "url_fetch",
             "arguments": {"url": "<base_url>?d=<base64(json(params))>"},
             "payload_fields": [...]}

    Raises ValueError on non-dict params or missing base_url — the
    adapter serializes, it does not repair.

    v1.1: ``context`` supplies the purpose from the application-owned
    task context. A planner-supplied ``stated_purpose`` is ignored
    (recorded as a conflict when it disagrees) — never an override.
    Missing/unknown context purpose serializes as "" which cannot
    match any purpose-bound permission record -> downstream block.
    """
    if call.get("tool") != "url_fetch_struct":
        raise ValueError(f"not a structured call: {call.get('tool')}")
    base_url = call.get("base_url")
    params = call.get("params")
    if not isinstance(base_url, str) or not base_url.startswith("http"):
        raise ValueError("base_url must be an http(s) URL string")
    if not isinstance(params, dict):
        raise ValueError("params must be a dict of supplied values")
    if issuer is not None:
        # v1.3 runtime binding: the presented context must be the
        # issuer's ACTIVE context for the (task, session) being
        # dispatched. The dispatched task/session come from
        # application code — never from planner fields in the call.
        if session_id is None or task_id is None:
            raise ContextBindingError(
                "issuer requires session_id and task_id")
        if not issuer.verify(context, task_id, session_id):
            raise ContextBindingError(
                f"context not bound to task {task_id} "
                f"in session {session_id}")
    encoded = base64.b64encode(
        json.dumps(params, separators=(",", ":")).encode()).decode()
    sep = "&" if "?" in base_url else "?"
    ctx_purpose = context.purpose if context else None
    planner_purpose = call.get("stated_purpose")
    out = {
        "tool": "url_fetch",
        "arguments": {"url": f"{base_url}{sep}{PARAM_KEY}={encoded}"},
        "payload_fields": list(call.get("payload_fields", [])),
        "stated_purpose": ctx_purpose or "",
        "purpose_source": "task_context" if ctx_purpose else "none",
    }
    if planner_purpose and planner_purpose != ctx_purpose:
        out["purpose_conflict"] = {"planner_claimed": planner_purpose,
                                   "context_bound": ctx_purpose}
    return out


def planner_call_for_view(call: dict,
                          context: TaskContext | None = None) -> dict:
    """Serialize a structured call into the planner_call dict the
    gateway view expects. The checked URL is the adapter's final
    serialization — nothing is rewritten after this point."""
    return serialize_structured_call(call, context)
