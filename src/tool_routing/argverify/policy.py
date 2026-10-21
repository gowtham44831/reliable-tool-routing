"""Map per-argument findings to one next action.

Order of the decision, applied to the set of findings:

1. ``wrong_entity`` or ``contradicted``  -> ``reject_proposed_call``
   The call is unsafe as proposed (wrong person's data, or evidence that
   asserts a different value). Reject means this call must not execute;
   the task itself is not abandoned -- a corrected call can be proposed.
2. ``unresolved`` with a retrievable fix (evidence exists but is stale,
   or an authorized lookup could supply it) -> ``retrieve``.
3. ``unresolved`` requiring user input (multiple real candidates, or the
   evidence is outside authorized scope) -> ``clarify``.
4. ``missing`` required argument obtainable from an authorized tool
   source -> ``retrieve``; otherwise -> ``clarify``.
5. ``missing`` optional argument with a documented default ->
   ``reject_proposed_call`` (a corrected call drops the argument).
6. Otherwise -> ``proceed``.

"Retrievable" is judged from the evidence manifest: a source tier of
``profile`` is retrievable only when ``context.profile_authorized`` is
true; a ``tool_result`` tier with a prospective ref (a tool that has not
yet been called) or a stale result is retrievable by re-calling the tool.
"""
from __future__ import annotations

from .schema import Case, FINDINGS, ACTIONS


def _retrievable(case: Case, arg: str) -> bool:
    for ev in case.evidence_manifest:
        if ev.argument_name != arg:
            continue
        for s in ev.source_references:
            if s.tier == "profile" and case.context.get("profile_authorized"):
                return True
            if s.tier == "tool_result" and s.ref.startswith("tool."):
                return True  # stale or prospective tool result -> re-fetch
    return False


def next_action(case: Case, findings: dict[str, str], missing_required: list[str] | None = None,
                unresolved_reasons: dict[str, str] | None = None) -> str:
    assert all(f in FINDINGS for f in findings.values())
    required = {k for k, p in case.tool_schema["parameters"].items() if p.get("required")}
    bad = {a for a, f in findings.items() if f in ("wrong_entity", "contradicted")}
    if bad:
        return "reject_proposed_call"
    unresolved = {a for a, f in findings.items() if f == "unresolved"}
    if unresolved:
        # "ambiguous" (several real candidates) needs the user; only a
        # stale or not-yet-called source justifies retrieving instead.
        reasons = unresolved_reasons or {}
        if any(reasons.get(a) == "ambiguous" for a in unresolved):
            return "clarify"
        if any(_retrievable(case, a) for a in unresolved):
            return "retrieve"
        return "clarify"
    missing = {a for a, f in findings.items() if f == "missing"}
    if missing:
        # a required argument missing OR present-but-unsupported is the
        # same situation: the call cannot execute without a valid value
        required_missing = missing & (required | set(missing_required or []))
        if required_missing:
            if any(_retrievable(case, a) for a in required_missing):
                return "retrieve"
            return "clarify"
        return "reject_proposed_call"  # unsupported optional args
    return "proceed"


def missing_required_args(case: Case) -> list[str]:
    args = case.proposed_tool_call.get("arguments", {})
    return [k for k, p in case.tool_schema["parameters"].items() if p.get("required") and k not in args]
