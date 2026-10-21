"""AI verifier v2: frozen v1 transport + strict output validation.

v1 (``llm.py``, frozen at run 3) accepts any non-empty subset of legal
findings. v2 wraps the same request/response path and adds a validation
layer: a response is usable only if it supplies exactly one legal
finding for every argument in scope. Anything else is a ``verifier_error``
that blocks execution.

In-scope arguments = every argument present in the proposed call, plus
every required argument absent from the call (the verifier must say
``missing`` for those, not stay silent).

Rejected outputs (all -> verifier_error, findings {} ):
- partial: a scoped argument has no finding
- unknown: a finding for an argument not in scope
- malformed: a finding value that is not a legal finding string
- duplicate: the same argument key appears twice in the raw JSON
- absent-required not labelled ``missing``
"""
from __future__ import annotations

import json
import re
from typing import Any

from . import llm as _v1
from .policy import missing_required_args, next_action
from .schema import FINDINGS, Case

PROMPT = _v1.PROMPT  # same prompt, same sha


def in_scope_args(case: Case) -> set[str]:
    return set(case.proposed_tool_call.get("arguments", {})) | set(missing_required_args(case))


def _raw_duplicate_keys(text: str) -> list[str]:
    """Detect duplicate keys inside the raw ``argument_findings`` object
    (json.loads silently keeps the last one)."""
    m = re.search(r'"argument_findings"\s*:\s*\{(.*?)\}', text, re.S)
    if not m:
        return []
    keys = re.findall(r'"([^"]+)"\s*:', m.group(1))
    seen, dups = set(), []
    for k in keys:
        if k in seen:
            dups.append(k)
        seen.add(k)
    return dups


def validate(case: Case, raw: str | None, parsed: dict) -> tuple[dict[str, str], str | None]:
    """Return (findings, error). error is None iff findings are complete
    and well-formed for every in-scope argument."""
    scope = in_scope_args(case)
    af = parsed.get("argument_findings") if isinstance(parsed, dict) else None
    if not isinstance(af, dict) or not af:
        return {}, "no argument_findings object"
    dups = _raw_duplicate_keys(raw or "")
    if dups:
        return {}, f"duplicate finding keys: {sorted(dups)}"
    malformed = {k: v for k, v in af.items() if not (isinstance(v, str) and v in FINDINGS)}
    if malformed:
        return {}, f"malformed finding values: {malformed}"
    unknown = set(af) - scope
    if unknown:
        return {}, f"findings for out-of-scope arguments: {sorted(unknown)}"
    partial = scope - set(af)
    if partial:
        return {}, f"no finding for in-scope arguments: {sorted(partial)}"
    absent_req = set(missing_required_args(case))
    wrong_absent = {a: af[a] for a in absent_req if af[a] != "missing"}
    if wrong_absent:
        return {}, f"absent required args not labelled missing: {wrong_absent}"
    return dict(af), None


def ai_verifier_v2(case: Case, timeout: float | None = None) -> dict | None:
    out = _v1.ai_verifier(case, timeout)
    if out is None:
        return None
    if out.get("action") == "verifier_error":
        return out  # transport or empty-response failure already surfaced
    parsed = _v1._parse_json(out.get("raw") or "")
    findings, err = validate(case, out.get("raw"), parsed)
    if err:
        return {**out, "findings": {}, "details": {"validation_error": err,
                                                   "model_declared_action": str(parsed.get("next_action"))},
                "action": "verifier_error", "error": f"validation: {err}",
                "parse_ok": False, "validator": "v2"}
    details = dict(out.get("details", {}))
    details["validator"] = "v2"
    return {**out, "findings": findings, "details": details,
            "action": next_action(case, findings, missing_required_args(case)),
            "validator": "v2"}
