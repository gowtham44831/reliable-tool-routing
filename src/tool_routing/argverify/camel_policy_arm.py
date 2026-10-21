"""CaMeL released policy-component arms — NOT a CaMeL reproduction.

Two arms over the vendored policy component
(third_party/camel_policy, upstream f083b6b):

- ``camel_base_policy_arm`` — the RELEASED ``base_security_policy``
  verbatim. Descriptive comparison only.
- ``camel_m3_intent_arm`` — a custom ``SecurityPolicy`` through the
  released interface expressing M3's authorization intent
  (docs/camel_policy_assessment.md).

Capability inputs (readers/sources on CaMeLValues) are supplied by
THIS adapter, computed from trusted permission records — never from
M3 decisions, expected labels, or evaluator truth. CaMeL's own
provenance propagation, planner, and control-flow protections are
not exercised.

Inspection separation: field extraction uses the shared
decode_url_payload/match_candidates pipeline; policy evaluation is
timed and reported separately. A comparison that shares our
inspection pipeline cannot establish an advantage over CaMeL's own
information-flow tracking — stated in every report.
"""

from __future__ import annotations

import time
import urllib.parse

from third_party.camel_policy import security_policy
from third_party.camel_policy.capabilities import (
    Capabilities, can_readers_read_value, readers, sources)
from third_party.camel_policy.interpreter.value import CaMeLStr
from tool_routing.argverify.url_fetch_gateway import (
    decode_url_payload, match_candidates, retrieved_value_index)

ARM_VERSION = "camel-arms-1.0"
FIELD_PREFIX = "field."


def _principal(view: dict, host: str) -> str:
    return view.get("directory", {}).get(host, {}).get(
        "principal", host)


def field_readers(view: dict, purpose: str,
                  clock: str) -> dict[str, frozenset]:
    """field_id -> authorized destination principals, computed from
    trusted permission_records ONLY: allow record covering
    (owner, field, dest, purpose, unexpired) adds dest; a covering
    deny removes it (deny-wins). Missing metadata -> no readers."""
    readers_by_field: dict[str, set] = {}
    records = view.get("permission_records", [])
    meta = view.get("field_metadata", {})
    for rec in records:
        if rec.get("purpose") != purpose:
            continue
        not_after = rec.get("constraints", {}).get("not_after")
        if not_after is not None and clock > not_after:
            continue
        owner = rec.get("data_owner")
        dest = rec.get("destination_principal")
        for fid in rec.get("permitted_fields", []):
            if meta.get(fid, {}).get("owner") != owner:
                continue
            s = readers_by_field.setdefault(fid, set())
            if rec.get("effect") == "allow":
                s.add(dest)
            elif rec.get("effect") == "deny":
                s.discard(dest)
    return {f: frozenset(s) for f, s in readers_by_field.items()}


def inspect_call(url: str, view: dict) -> dict:
    """Shared inspection stage: decode the URL carrier and exact-match
    against retrieved values. Returns matched fields + unaccounted
    flag. Decoder/matcher failures are reported separately — they are
    NOT policy decisions."""
    dec = decode_url_payload(url)
    if dec["errors"] or dec["parsed"] is None:
        return {"ok": False, "decode_errors": dec["errors"],
                "fields": [], "unaccounted": False}
    matches = match_candidates(dec["candidates"],
                               retrieved_value_index(view))
    fields = [(m["field_id"], m["matched_value"]) for m in matches]
    # unaccounted (mirrors F5): a query carrier produced no matched
    # fields at all — blocked conservatively. Path segments are
    # structural, not carriers.
    accounted = {m["carrier"] for m in matches}
    unaccounted = any(c["where"] == "query" and c["key"] not in accounted
                      for c in dec["candidates"])
    return {"ok": True, "decode_errors": dec["errors"],
            "fields": fields, "unaccounted": unaccounted,
            "decode_log": dec["decode_log"]}


def _kwargs(view: dict, purpose: str, clock: str,
            fields: list[tuple[str, str]]) -> dict:
    """Build CaMeLValues: readers per field computed from trusted
    records (deny already removed). Public for unlabeled/public
    values; empty frozenset when no authorization exists."""
    fr = field_readers(view, purpose, clock)
    meta = view.get("field_metadata", {})
    kwargs = {}
    for fid, val in fields:
        if fid.startswith("<unlabeled:") or meta.get(
                fid, {}).get("class") in ("personal", "credential",
                                          "health_financial"):
            r = fr.get(fid, frozenset())
        else:
            r = readers.Public()
        kwargs[f"{FIELD_PREFIX}{fid}"] = CaMeLStr.from_raw(
            val, Capabilities(frozenset({sources.SourceEnum.User}),
                              r), ())
    return kwargs


class _Engine(security_policy.SecurityPolicyEngine):
    def __init__(self, policies):
        self.policies = policies
        self.no_side_effect_tools = set()


def camel_base_policy_arm(url: str, view: dict, purpose: str,
                          clock: str) -> dict:
    """Released base_security_policy verbatim. Descriptive only."""
    ins = inspect_call(url, view)
    if not ins["ok"]:
        return {"arm": "camel-base-policy", "decision": "inspect_failure",
                "decode_errors": ins["decode_errors"], "policy_ms": 0.0}
    kwargs = _kwargs(view, purpose, clock, ins["fields"])
    t0 = time.perf_counter()
    eng = _Engine([("url_fetch", lambda n, k: security_policy.
                    base_security_policy(n, k, set()))])
    res = eng.check_policy("url_fetch", kwargs, ())
    ms = (time.perf_counter() - t0) * 1000
    allowed = isinstance(res, security_policy.Allowed)
    return {"arm": "camel-base-policy",
            "decision": "allow" if allowed else "block",
            "reason": getattr(res, "reason", ""), "policy_ms": ms,
            "unaccounted": ins["unaccounted"],
            "fields_checked": len(ins["fields"])}


def camel_m3_intent_arm(url: str, view: dict, purpose: str,
                        clock: str) -> dict:
    """Custom policy via the released interface expressing M3's
    intent: every matched protected field's readers must include the
    destination principal; unaccounted carrier content -> Denied
    (mirrors F5). Readers are adapter-supplied from trusted records."""
    ins = inspect_call(url, view)
    if not ins["ok"]:
        return {"arm": "camel-m3-intent", "decision": "inspect_failure",
                "decode_errors": ins["decode_errors"], "policy_ms": 0.0}
    host = urllib.parse.urlsplit(url).hostname or ""
    dest = _principal(view, host)
    kwargs = _kwargs(view, purpose, clock, ins["fields"])
    if ins["unaccounted"]:
        kwargs["_unaccounted_carrier"] = CaMeLStr.from_raw(
            "1", Capabilities(frozenset({sources.SourceEnum.CaMeL}),
                              readers.Public()), ())

    def m3_intent(tool_name: str, kw):
        if "_unaccounted_carrier" in kw:
            return security_policy.Denied(
                "unaccounted payload in carrier")
        for name, v in kw.items():
            if not name.startswith(FIELD_PREFIX):
                continue
            if not can_readers_read_value({dest}, v):
                return security_policy.Denied(
                    f"destination {dest} is not an authorized reader "
                    f"of {name[len(FIELD_PREFIX):]}")
        return security_policy.Allowed()

    t0 = time.perf_counter()
    eng = _Engine([("url_fetch", m3_intent)])
    res = eng.check_policy("url_fetch", kwargs, ())
    ms = (time.perf_counter() - t0) * 1000
    allowed = isinstance(res, security_policy.Allowed)
    return {"arm": "camel-m3-intent",
            "decision": "allow" if allowed else "block",
            "reason": getattr(res, "reason", ""), "policy_ms": ms,
            "dest_principal": dest,
            "unaccounted": ins["unaccounted"],
            "fields_checked": len(ins["fields"]),
            "readers": {f[len(FIELD_PREFIX):]:
                        sorted(getattr(v.metadata, "readers_set",
                                       frozenset()) or [])
                        if not isinstance(
                            getattr(v.metadata, "readers_set", None),
                            readers.Public) else ["<public>"]
                        for f, v in kwargs.items()
                        if f.startswith(FIELD_PREFIX)}}
