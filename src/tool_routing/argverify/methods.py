"""Verification methods.

``schema_baseline`` checks only the tool contract (required fields,
types, enum values, patterns). It cannot see evidence, so every present,
schema-valid argument is reported ``supported`` -- that is exactly the
blindness this project measures.

``rule_baseline`` verifies provenance deterministically: every claimed
source reference must resolve to real conversation text or tool-result
fields; candidate values are extracted by the argument's contract
``hint``; precedence and staleness rules are stated below and in the
spec. It does NOT read expected findings or label rules.
"""
from __future__ import annotations

import re
from datetime import datetime
from typing import Any

from .evidence import extract_candidates, norm, resolve_ref
from .policy import missing_required_args, next_action
from .schema import TIER_ORDER, Case


def _type_ok(value: Any, p: dict) -> bool:
    t = p.get("type")
    if t == "integer":
        return isinstance(value, int)
    if t == "string":
        return isinstance(value, str)
    return True


def schema_baseline(case: Case) -> dict:
    """Required fields present, types/enum/pattern valid -> supported."""
    params = case.tool_schema["parameters"]
    args = case.proposed_tool_call.get("arguments", {})
    findings: dict[str, str] = {}
    details: dict[str, str] = {}
    for name, p in params.items():
        if name not in args:
            if p.get("required"):
                findings[name] = "missing"
                details[name] = "required field absent from the call"
            continue
        v = args[name]
        ok = _type_ok(v, p)
        if ok and "enum" in p:
            ok = v in p["enum"]
        if ok and p.get("pattern"):
            ok = bool(re.fullmatch(p["pattern"], str(v)))
        if ok:
            findings[name] = "supported"
            details[name] = "schema-valid (no evidence check performed)"
        else:
            findings[name] = "missing"
            details[name] = "fails type/enum/pattern contract"
    # unknown extra arguments count as unsupported
    for name in args:
        if name not in params:
            findings[name] = "missing"
            details[name] = "argument not in tool schema"
    return {"findings": findings, "details": details,
            "action": next_action(case, findings, missing_required_args(case))}


def _age_hours(ts: str | None, now: str) -> float | None:
    if not ts or not now:
        return None
    try:
        return (datetime.fromisoformat(now) - datetime.fromisoformat(ts)).total_seconds() / 3600
    except ValueError:
        return None


def rule_baseline(case: Case) -> dict:
    """Deterministic provenance verification.

    Rules (all stated in the spec):
    - A claim is evidence only if its ref resolves. A ref that names a
      tool never called is *prospective* -- it can support "retrieve"
      but not "supported".
    - Profile-tier sources count only when ``context.profile_authorized``.
    - Tool results older than the parameter's ``valid_for_hours`` are
      stale; an argument supported ONLY by stale sources is ``unresolved``
      (outdated, not contradicted) and retrievable.
    - Within one source, the LAST extracted candidate is the operative
      value (handles "usually X, but Y this time").
    - Across sources, the highest precedence tier wins: user_current >
      user_prior > tool_result > profile > schema_default. Two distinct
      winning values => unresolved (ambiguous); the single winning value
      differing from the proposal => contradicted.
    - Person-scoped arguments: the supporting source's entity must be
      ``traveler``. A value sourced from another person's profile is
      ``wrong_entity``.
    - Optional args with a documented default: if the proposed value
      equals the schema default it is ``supported``; any other value
      needs a real source.
    """
    params = case.tool_schema["parameters"]
    args = case.proposed_tool_call.get("arguments", {})
    ctx = case.context
    by_arg = {e.argument_name: e for e in case.evidence_manifest}
    findings: dict[str, str] = {}
    details: dict[str, str] = {}
    reasons: dict[str, str] = {}

    names = set(by_arg) | set(args) | {k for k, p in params.items() if p.get("required")}
    for name in sorted(names):
        p = params.get(name, {})
        ev = by_arg.get(name)
        proposed = args.get(name, ev.proposed_value if ev else None)
        if name not in args:
            if p.get("required"):
                findings[name] = "missing"
                details[name] = "required argument absent from the call"
            continue
        hint = p.get("hint")
        # Gather usable evidence: resolved, authorized, not stale. Each
        # usable ref asserts ONE value: a `match` span when the planner
        # pinned one (verified to occur in the content), else the last
        # candidate extracted by the contract hint.
        usable: list[tuple[int, str, str, str]] = []  # tier_rank, entity, asserted, ref
        stale = prospective = unauthorized = False
        for s in (ev.source_references if ev else []):
            res = resolve_ref(case, s)
            if s.tier == "profile" and not ctx.get("profile_authorized"):
                unauthorized = True
                continue
            if res.prospective:
                prospective = True
                continue
            if s.tier == "tool_result" and p.get("valid_for_hours"):
                age = _age_hours(res.timestamp, ctx.get("current_time"))
                if age is not None and age > p["valid_for_hours"]:
                    stale = True
                    continue
            if not res.exists:
                continue
            if s.match is not None:
                if str(s.match) not in str(res.content):
                    continue  # claimed span is not in the source: ref is false
                vals = extract_candidates(str(s.match), hint, case, name) or [s.match]
                usable.append((TIER_ORDER.get(s.tier, 0), s.entity, vals[0], s.ref))
                continue
            vals = extract_candidates(res.content, hint, case, name)
            # a structured list (candidate options) keeps ALL slot values;
            # flat text keeps the last extracted mention (operative value)
            asserted_vals = vals if isinstance(res.content, (list, dict)) else vals[-1:]
            for v in asserted_vals:
                usable.append((TIER_ORDER.get(s.tier, 0), s.entity, v, s.ref))
        pnorm = norm(proposed)
        if ev and ev.transformation_or_default == "schema_default" \
                and pnorm == norm(p.get("default")):
            findings[name] = "supported"
            details[name] = "equals documented schema default"
            continue
        if not usable:
            if stale:
                findings[name] = "unresolved"
                reasons[name] = "stale"
                details[name] = "only evidence is a tool result past its validity window"
            else:
                findings[name] = "missing"
                details[name] = ("no usable source (unauthorized profile only)"
                                 if unauthorized else "no resolvable source reference")
            continue
        top = max(t for t, _, _, _ in usable)
        top_entries = [(e, v, r) for t, e, v, r in usable if t == top]
        distinct = {norm(v) for _, v, _ in top_entries}
        if len(distinct) > 1:
            findings[name] = "unresolved"
            reasons[name] = "ambiguous"
            details[name] = f"{len(distinct)} distinct candidate values at the winning tier"
            continue
        winning_entity, winning_val, winning_ref = top_entries[0]
        if pnorm == norm(winning_val):
            if p.get("person_scoped") and winning_entity != "traveler":
                findings[name] = "wrong_entity"
                details[name] = f"value sourced from entity '{winning_entity}', not the traveler"
            else:
                findings[name] = "supported"
                details[name] = f"value found in {winning_ref}"
        else:
            findings[name] = "contradicted"
            details[name] = f"winning source asserts '{winning_val}', not '{proposed}'"
    return {"findings": findings, "details": details, "unresolved_reasons": reasons,
            "action": next_action(case, findings, missing_required_args(case), reasons)}


def cross_argument_baseline(case: Case) -> dict:
    """Slot-level rule baseline PLUS cross-argument record consistency.

    A proposed call that references a record (e.g. ``flight_id`` pointing
    at one flight option) must agree with THAT record on every shared
    field, and those fields must agree with the current-request tier of
    the evidence. A flight id matching the call's date while the current
    request superseded it is inconsistent.

    Checks (documented in the spec):
    - Find the record(s) in prior tool results whose identifier field
      equals the proposed id argument (key containing "_id").
    - The proposed call must agree with that record on all shared fields
      (alias-resolved), AND the record must agree with the user's current
      tier on every slot the user asserted. Disagreement with the record
      or with the current request => ``contradicted`` for the id argument
      (the record exists but not for these parameters).
    - If no record carries the proposed id at all, the slot-level verdict
      stands.
    - Person-scoped args must all trace to the same entity.

    Reported as a separate method (`crossrule`) so the added value over
    slot-level rules is visible per argument.
    """
    out = rule_baseline(case)
    args = case.proposed_tool_call.get("arguments", {})
    params = case.tool_schema["parameters"]
    # current-tier assertions per arg (user_current), via manifest refs
    current_tier: dict[str, str] = {}
    by_arg = {e.argument_name: e for e in case.evidence_manifest}
    for name, ev in by_arg.items():
        for s in ev.source_references:
            if s.tier == "user_current":
                res = resolve_ref(case, s)
                if res.exists:
                    src = str(s.match) if s.match else str(res.content)
                    vals = extract_candidates(src, params.get(name, {}).get("hint"), case, name)
                    if vals:
                        current_tier[name] = vals[-1]
    # collect records: dicts inside any tool result that carry an *_id key
    records: list[dict] = []

    def walk(n):
        if isinstance(n, dict):
            records.append(n)
            for v in n.values():
                walk(v)
        elif isinstance(n, list):
            for x in n:
                walk(x)

    for tr in case.prior_tool_results:
        walk(tr.get("output", {}))
    for name, p in params.items():
        if name not in args:
            continue
        if not str(name).endswith("_id"):
            continue
        matches = [r for r in records if norm(r.get("flight_id") or r.get(name)) == norm(args[name])]
        if not matches:
            continue
        inconsistent = False
        for rec in matches:
            for field, rv in rec.items():
                if field in ("flight_id",) or field == name:
                    continue
                # which arg does this record field map to?
                arg_for_field = next(
                    (a for a in params
                     if a == field or field in ALIASES.get(a, ())), None)
                if arg_for_field is None:
                    continue
                want = current_tier.get(arg_for_field, args.get(arg_for_field))
                if want is not None and norm(rv) != norm(want):
                    inconsistent = True
        if inconsistent:
            out["findings"][name] = "contradicted"
            out["details"][name] = ("record matches no current request values "
                                    "(cross-argument inconsistency)")
    out["action"] = next_action(case, out["findings"], missing_required_args(case),
                                out.get("unresolved_reasons"))
    return out


from .evidence import ALIASES  # noqa: E402  (kept at bottom to avoid clutter)
