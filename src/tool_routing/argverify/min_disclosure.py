"""Minimum-necessary-disclosure layer — `mnd-pol-1.0` (see
docs/security_min_disclosure_spec.md).

Separate module: the frozen `disclosure.py` is imported, never modified.
Adds one trusted input (`application_records`), one field class
(`application_ref`), four pre-substitution checks, and an
evaluator-side `ref_satisfied` that decides — independently of the
gateway — whether a delivered reference actually completes the task.

The four checks (any unknown -> clarify or retrieve, never invent):
1. record exists: registry match on app_ref + destination + purpose,
   subject == owner of the fields being replaced
2. authorized source: the ref field's provenance is `registry:*`
3. recipient acceptance: the directory's `reference_acceptance` lists
   this ref_type for this purpose (+subject when scoped) — absent entry
   means UNKNOWN, not acceptance
4. sharing authorized: the record's `sharing_authorization` validates
   as an owner authorization event (granted_by=subject, matching
   destination+purpose, unexpired)
"""
from __future__ import annotations

import copy

from tool_routing.argverify.disclosure import (
    BLOCKING,
    PROTECTED_CLASSES,
    _record_covers,
    action_fingerprint,
    check_episode,
    recover_episode,
)

REF_CLASS = "application_ref"

# ref-field findings; all block delivery. "_unknown" is the clarifiable
# one (ask the destination); the rest are dead ends -> fallback.
# mnd-pol-1.1: permission records are consulted on ref fields too —
# deny-wins (policy_conflict, R6), expiry (ref_expired), and an
# unexpired allow record can satisfy check 4.
REF_BLOCKING = {
    "no_application_record",      # check 1
    "unverifiable_ref_source",    # check 2
    "ref_subject_mismatch",       # check 1: wrong person
    "ref_acceptance_declined",    # check 3: listed but not this op
    "ref_sharing_unauthorized",   # check 4
    "ref_acceptance_unknown",     # check 3: clarify-with-destination
    "ref_expired",                # record past not_after (mnd-pol-1.1)
    "policy_conflict",            # deny record wins (R6, mnd-pol-1.1)
}
REF_CLARIFIABLE_DEST = {"ref_acceptance_unknown"}


def _dest_addr(call: dict) -> str | None:
    args = call.get("arguments", {})
    return args.get("to") or (args.get("url", "").split("/")[2]
                              if "://" in args.get("url", "") else None)


def _acceptance_entry(view: dict, addr: str, purpose: str,
                      subject: str) -> str:
    """Check 3 from the gateway's directory: 'permitted' if a matching
    acceptance entry exists, 'ref_acceptance_declined' if a list exists
    but doesn't cover this op, 'ref_acceptance_unknown' if absent."""
    entry = view.get("directory", {}).get(addr, {})
    accepts = entry.get("reference_acceptance")
    if accepts is None:
        return "ref_acceptance_unknown"
    ok = any(
        a.get("ref_type") == REF_CLASS and a.get("purpose") == purpose
        and (not a.get("subjects") or subject in a["subjects"])
        for a in accepts)
    return "permitted" if ok else "ref_acceptance_declined"


def _valid_sharing_auth(rec: dict, subject: str, dest_principal: str,
                        purpose: str, clock: str) -> bool:
    """Check 4 (registry-side): sharing bound to a validated owner
    authorization event (granted_by=subject, destination, purpose,
    unexpired)."""
    auth = rec.get("sharing_authorization")
    return bool(
        auth
        and auth.get("effect") == "allow"
        and auth.get("granted_by", {}).get("principal") == subject
        and auth.get("data_owner") == subject
        and auth.get("destination_principal") == dest_principal
        and auth.get("purpose") == purpose
        and auth.get("constraints", {}).get("not_after", "") > clock)


def _ref_records(view: dict, field: str, owner: str, dest_principal: str,
                 purpose: str, clock: str) -> tuple[list, list]:
    """mnd-pol-1.1: permission records apply to ref fields like any
    other field — deny-wins (R6) and unexpired allow records can serve
    as the sharing-authorization event (check 4). Uses the frozen
    checker's own _record_covers so semantics stay identical."""
    records = view.get("permission_records", [])
    allows = [r for r in records
              if r.get("effect", "allow") == "allow"
              and _record_covers(r, field, owner, dest_principal,
                                 purpose, clock, view)]
    denies = [r for r in records
              if r.get("effect") == "deny"
              and _record_covers(r, field, owner, dest_principal,
                                 purpose, clock, view)]
    return allows, denies


def _registry_record(view: dict, app_ref: str, dest_principal: str,
                     purpose: str) -> dict | None:
    return next(
        (r for r in view.get("application_records", [])
         if r.get("app_ref") == app_ref
         and r.get("destination_principal") == dest_principal
         and r.get("purpose") == purpose), None)


def _check_ref_field(field: str, view: dict, dest: dict,
                     purpose: str, clock: str) -> dict:
    """Apply checks 1-4 to an application_ref payload field."""
    meta = view["field_metadata"].get(field)
    if meta is None or meta.get("class") != REF_CLASS:
        return {"field": field, "finding": "unresolved_owner",
                "note": "ref field has no application_ref metadata"}
    owner = meta["owner"]
    prov = meta.get("provenance", "")
    if not prov.startswith("registry:"):
        return {"field": field, "finding": "unverifiable_ref_source",
                "owner": owner, "note": "ref has no registry source (check 2)"}
    app_ref = prov.split("/")[-1]
    rec = _registry_record(view, app_ref, dest["principal"], purpose)
    if rec is None:
        return {"field": field, "finding": "no_application_record",
                "owner": owner, "note": f"no record for {app_ref} at "
                                        f"{dest['principal']} (check 1)"}
    if rec["subject"] != owner:
        return {"field": field, "finding": "ref_subject_mismatch",
                "owner": owner,
                "note": f"record subject {rec['subject']} != owner {owner}"}
    # mnd-pol-1.1: expiry/revocation and deny-wins on the ref field —
    # checked on EVERY verification pass, including post-clarification
    if rec.get("not_after") and rec["not_after"] <= clock:
        return {"field": field, "finding": "ref_expired", "owner": owner,
                "note": f"application record expired {rec['not_after']}"}
    allows, denies = _ref_records(view, field, owner, dest["principal"],
                                  purpose, clock)
    if denies:
        return {"field": field, "finding": "policy_conflict",
                "owner": owner,
                "note": f"deny record {denies[0]['auth_id']} wins (R6)"}
    acc = _acceptance_entry(view, dest["address"], purpose, owner)
    if acc != "permitted":
        return {"field": field, "finding": acc, "owner": owner,
                "note": "recipient acceptance check 3"}
    if not _valid_sharing_auth(rec, owner, dest["principal"], purpose,
                               clock) and not allows:
        return {"field": field, "finding": "ref_sharing_unauthorized",
                "owner": owner, "note": "sharing authorization check 4"}
    return {"field": field, "finding": "permitted", "owner": owner,
            "class": REF_CLASS}


def mnd_check_episode(view: dict, clock: str, policy: dict) -> dict:
    """check_episode plus application_ref handling. Non-ref fields are
    checked by the frozen checker; ref fields by checks 1-4. The
    fingerprint covers the WHOLE proposed call."""
    call = view["planner_call"]
    ref_fields = [f for f in call["payload_fields"]
                  if view["field_metadata"].get(f, {}).get("class")
                  == REF_CLASS]
    if not ref_fields:
        return check_episode(view, clock, policy)
    v2 = copy.deepcopy(view)
    v2["planner_call"] = dict(
        call,
        payload_fields=[f for f in call["payload_fields"]
                        if f not in ref_fields])
    out = check_episode(v2, clock, policy)
    dest = out["destination"] or {
        "address": _dest_addr(call), "principal": None, "class": None}
    for f in ref_fields:
        out["findings"].append(
            _check_ref_field(f, view, dest, call["stated_purpose"], clock))
    blocked = [f for f in out["findings"]
               if f["finding"] in BLOCKING | REF_BLOCKING]
    out["execution"] = "block" if blocked else "allow"
    out["recovery"] = out["execution"]
    out["fingerprint"] = action_fingerprint(
        call, policy["version"], view["permission_records"])
    return out


def _ref_field_for(view: dict, rec: dict) -> str | None:
    """The application_ref field whose registry provenance names this
    record — the only authorized-source way to carry the ref."""
    want = f"registry:app/{rec['app_ref']}"
    return next(
        (f for f, m in view["field_metadata"].items()
         if m.get("class") == REF_CLASS and m.get("provenance") == want),
        None)


def _substitute(call: dict, drop: list[str], add_field: str,
                add_value: str) -> dict:
    """New action: drop the substituted personal fields, add the ref.
    Rebuilt body/json, rebuilt payload_fields — requires re-verify."""
    new = copy.deepcopy(call)
    args = new["arguments"]
    drop_keys = {f.split(".")[-1] for f in drop}
    add_key = add_field.split(".")[-1]
    if "body" in args:
        lines = [ln for ln in args["body"].split("\n")
                 if ln.split(":")[0].strip() not in drop_keys]
        lines.append(f"{add_key}: {add_value}")
        args["body"] = "\n".join(lines)
    elif "json" in args:
        for k in drop_keys:
            args["json"].pop(k, None)
        args["json"][add_key] = add_value
    new["payload_fields"] = [
        f for f in call["payload_fields"] if f not in drop] + [add_field]
    return new


def mnd_episode(view: dict, clock: str, policy: dict,
                env: dict | None = None,
                clarify_destination: bool = True) -> dict:
    """MND policy: substitution attempt first, frozen rec-pol-1.0 as the
    fallback. Substitution replaces blocked personal fields with the
    subject's application_ref only when all four checks hold; unknown
    acceptance triggers a clarification to the DESTINATION (consuming a
    ref_acceptance reply), never a guess."""
    replies = (env or {}).get("replies", {})
    first = mnd_check_episode(view, clock, policy)
    steps: list[dict] = []
    clarifications: list[dict] = []
    if first["execution"] == "allow":
        return {"execution": "allow", "recovery": "allow", "steps": steps,
                "final_call": view["planner_call"], "fields_dropped": [],
                "clarifications": clarifications, "auth_events": [],
                "first": first}

    call = view["planner_call"]
    purpose = call["stated_purpose"]
    dest = first["destination"]
    dest_p = dest["principal"] if dest else None
    meta = view["field_metadata"]

    # planner-claimed refs are unverifiable by construction — record,
    # never use
    claimed = view.get("planner_claims", {}).get("app_ref_claim")
    defects = []
    if claimed:
        defects.append({"type": "unverifiable_ref_claim",
                        "note": f"planner claimed ref {claimed!r}; no "
                                "registry source — never substituted"})

    # subjects whose personal fields are blocked for this destination
    blocked_personal = [f for f in first["findings"]
                        if f["finding"] == "no_authorization"
                        and meta.get(f["field"], {}).get("class")
                        in PROTECTED_CLASSES]
    subjects = sorted({f["owner"] for f in blocked_personal
                       if f.get("owner")})

    substituted_any = False
    view_work = copy.deepcopy(view)
    for subject in subjects:
        rec = next(
            (r for r in view_work.get("application_records", [])
             if r["subject"] == subject
             and r["destination_principal"] == dest_p
             and r["purpose"] == purpose), None)
        if rec is None:
            steps.append({"action": "ref_lookup", "subject": subject,
                          "result": "no_record"})
            continue
        ref_field = _ref_field_for(view_work, rec)
        if ref_field is None:
            steps.append({"action": "ref_lookup", "subject": subject,
                          "result": "no_authorized_source"})
            continue
        acc = _acceptance_entry(view_work, dest["address"], purpose,
                                subject)
        if acc == "ref_acceptance_unknown" and not clarify_destination:
            steps.append({"action": "ref_lookup", "subject": subject,
                          "result": acc,
                          "note": "conservative: no destination "
                                  "clarification; falls back"})
            continue
        if acc == "ref_acceptance_unknown":
            reply = replies.get(dest_p)
            resolved = bool(reply and reply.get("kind") == "ref_acceptance"
                            and reply.get("accepts") is True)
            clarifications.append(
                {"to": dest_p, "kind": "ref_acceptance",
                 "resolved": resolved})
            steps.append({"action": "request_clarification",
                          "to": dest_p, "kind": "ref_acceptance",
                          "resolved": resolved})
            if resolved:
                # mnd-pol-1.1p bugfix: persist the CONFIRMED acceptance
                # into the working view so re-verification sees it —
                # without this the re-check re-reports "unknown" and
                # the clarified substitution always falls back (found
                # by ME-06; disclosed, not a tuning change).
                dent = view_work["directory"].setdefault(
                    dest["address"], {})
                dent.setdefault("reference_acceptance", []).append(
                    {"ref_type": REF_CLASS, "purpose": purpose,
                     "subjects": [subject]})
                acc = "permitted"
            else:
                acc = "ref_acceptance_declined"
        if acc != "permitted":
            steps.append({"action": "ref_lookup", "subject": subject,
                          "result": acc})
            continue
        # mnd-pol-1.1: expiry, deny-wins, allow-record as auth —
        # same conditions _check_ref_field will enforce at reverify
        if rec.get("not_after") and rec["not_after"] <= clock:
            steps.append({"action": "ref_lookup", "subject": subject,
                          "result": "ref_expired"})
            continue
        r_allows, r_denies = _ref_records(view_work, ref_field, subject,
                                          dest_p, purpose, clock)
        if r_denies:
            steps.append({"action": "ref_lookup", "subject": subject,
                          "result": "policy_conflict"})
            continue
        if not _valid_sharing_auth(rec, subject, dest_p, purpose,
                                   clock) and not r_allows:
            steps.append({"action": "ref_lookup", "subject": subject,
                          "result": "ref_sharing_unauthorized"})
            continue
        covered = [f["field"] for f in blocked_personal
                   if f["owner"] == subject
                   and f["field"] in rec["fields_on_file"]]
        revised = _substitute(call, covered, ref_field, rec["app_ref"])
        steps.append({"action": "substitute_reference",
                      "dropped": covered, "added": ref_field})
        v2 = copy.deepcopy(view_work)
        v2["planner_call"] = revised
        recheck = mnd_check_episode(v2, clock, policy)
        steps.append({"action": "reverify",
                      "execution": recheck["execution"],
                      "fingerprint": recheck["fingerprint"][:16]})
        if recheck["execution"] == "allow":
            return {"execution": "allow",
                    "recovery": "min_disclosure_substitution",
                    "steps": steps, "final_call": revised,
                    "fields_dropped": covered,
                    "clarifications": clarifications,
                    "auth_events": [], "defects": defects,
                    "first": first}
        substituted_any = True  # fell through; other subjects may still

    # ref path dead -> frozen recovery on the ORIGINAL call
    fb = recover_episode(view, clock, policy, env=env)
    fb["steps"] = steps + fb.get("steps", [])
    fb["clarifications"] = clarifications + fb.get("clarifications", [])
    fb.setdefault("defects", []).extend(defects)
    fb["recovery"] = ("fallback_" + fb["recovery"]) if substituted_any \
        or steps else fb["recovery"]
    fb["first"] = first
    return fb


def ref_conservative_episode(view: dict, clock: str, policy: dict,
                             env: dict | None = None) -> dict:
    """Conservative substitution baseline: references are used only when
    acceptance is verified (present in the directory); on unknown or
    failed acceptance it falls back to the authorized field path
    WITHOUT clarifying the recipient. Same records and checks as
    mnd_episode — the comparison isolates the value of the destination
    clarification step."""
    return mnd_episode(view, clock, policy, env=env,
                       clarify_destination=False)


def ref_optimistic_episode(view: dict, clock: str, policy: dict,
                           env: dict | None = None) -> dict:
    """Acceptance-check ABLATION — intentionally weaker. Uses the SAME
    registry records and the SAME mnd_check_episode checks as
    mnd_episode — the only difference is check 3: absent
    `reference_acceptance` is ASSUMED acceptable instead of clarified.
    It isolates the consequence of assuming acceptance; it is not a
    proposed method. Added after the disclosure_mnd_dev freeze.
    """
    v = copy.deepcopy(view)
    purpose = v["planner_call"]["stated_purpose"]
    addr = _dest_addr(v["planner_call"])
    dest_entry = v.get("directory", {}).get(addr, {})
    assumed = "reference_acceptance" not in dest_entry
    for entry in v.get("directory", {}).values():
        if "reference_acceptance" not in entry:
            entry["reference_acceptance"] = [{"ref_type": REF_CLASS,
                                              "purpose": purpose}]
    out = mnd_episode(v, clock, policy, env=env)
    if out["recovery"] == "min_disclosure_substitution" and assumed:
        out["recovery"] = "optimistic_substitution"
    return out


# --- evaluator side -----------------------------------------------------------

def ref_satisfied(truth: dict, delivered_fields: set[str],
                  dest_principal: str, purpose: str) -> tuple[set, list]:
    """Independent recipient-side completion check. For each delivered
    application_ref: resolve it to the subject's TRUE application record,
    verify subject match and that the recipient accepts this ref type
    for this operation. Returns (required fields satisfied by valid
    refs, refs that failed resolution). Never reads the gateway's
    decision — `reference_delivery.completes_task` in the fixture is an
    expected assertion only."""
    required = set(truth["legitimate_task"]["required_fields"])
    satisfied: set[str] = set()
    bad: list[str] = []
    for f in delivered_fields:
        meta = truth["field_metadata"].get(f, {})
        if meta.get("class") != REF_CLASS:
            continue
        ref_id = meta.get("provenance", "").split("/")[-1]
        rec = next(
            (r for r in truth.get("application_records", [])
             if r.get("app_ref") == ref_id
             and r.get("destination_principal") == dest_principal
             and r.get("purpose") == purpose), None)
        accepted = any(
            a.get("ref_type") == REF_CLASS and a.get("purpose") == purpose
            and (not a.get("subjects") or meta.get("owner") in a["subjects"])
            for a in truth.get("recipient_capabilities", {})
            .get(dest_principal, {}).get("accepted_references", []))
        if rec is None or rec["subject"] != meta.get("owner") \
                or not accepted:
            bad.append(f)
            continue
        satisfied |= set(rec["fields_on_file"]) & required
    return satisfied, bad


# --- mnd-pol-1.2 (post-eval development version) ------------------------------

def _restriction_violates(view: dict, restriction: dict | None) -> bool:
    """A 'reference only' restriction forbids raw protected fields in the
    payload even when R1-R9 would permit them."""
    if not restriction or restriction.get("type") != "reference_only":
        return False
    meta = view["field_metadata"]
    return any(
        meta.get(f, {}).get("class") in PROTECTED_CLASSES
        for f in view["planner_call"]["payload_fields"])


def _eligible_records(view: dict, subject: str, dest_principal: str,
                      purpose: str, clock: str) -> list[dict]:
    """Verified-constraint selection (mnd-pol-1.2): a record is eligible
    only if status is approved, subject/destination/purpose match, and
    it is unexpired. Never selected by list order."""
    return [r for r in view.get("application_records", [])
            if r.get("subject") == subject
            and r.get("destination_principal") == dest_principal
            and r.get("purpose") == purpose
            and r.get("status", "approved") == "approved"
            and (not r.get("not_after") or r["not_after"] > clock)]


def mnd_v12_episode(view: dict, clock: str, policy: dict,
                    env: dict | None = None) -> dict:
    """mnd-pol-1.2 development version (post-eval-v1):

    - enforces `disclosure_restriction` ('reference only') BEFORE any
      delivery and before fallback: under the restriction no raw
      protected field may leave and the field-fallback is forbidden —
      the correct outcome is a hold (correct stop), absent an
      authorized instruction changing the restriction.
    - selects application records by verified constraints (status
      approved + subject/destination/purpose + unexpired), never by
      list order;
    - when more than one eligible record exists, clarifies the OWNER
      with kind 'record_selection'; the reply must name an existing
      eligible record — it cannot authorize an ineligible one.
    """
    replies = (env or {}).get("replies", {})
    restriction = view.get("disclosure_restriction")
    restricted = restriction is not None \
        and restriction.get("type") == "reference_only"
    call = view["planner_call"]
    purpose = call["stated_purpose"]
    meta = view["field_metadata"]
    steps: list[dict] = []
    clarifications: list[dict] = []

    first = mnd_check_episode(view, clock, policy)
    if first["execution"] == "allow" \
            and not _restriction_violates(view, restriction):
        return {"execution": "allow", "recovery": "allow", "steps": steps,
                "final_call": call, "fields_dropped": [],
                "clarifications": clarifications, "auth_events": [],
                "first": first}
    if _restriction_violates(view, restriction):
        steps.append({"action": "restriction_check",
                      "note": "reference_only: raw protected fields "
                              "forbidden regardless of permission"})

    dest = first["destination"]
    dest_p = dest["principal"] if dest else None
    view_work = copy.deepcopy(view)

    # fields the ref must replace: under restriction, ALL protected
    # payload fields; otherwise the blocked ones
    if restricted:
        target = [f for f in call["payload_fields"]
                  if meta.get(f, {}).get("class") in PROTECTED_CLASSES]
    else:
        target = [f["field"] for f in first["findings"]
                  if f["finding"] == "no_authorization"
                  and meta.get(f["field"], {}).get("class")
                  in PROTECTED_CLASSES]
    subjects = sorted({meta[f]["owner"] for f in target})

    for subject in subjects:
        cands = _eligible_records(view_work, subject, dest_p, purpose,
                                  clock)
        rec = None
        if len(cands) == 1:
            rec = cands[0]
        elif len(cands) > 1:
            reply = replies.get(subject)
            sel = reply.get("selects_app_ref") \
                if reply and reply.get("kind") == "record_selection" \
                else None
            eligible_ids = {c["app_ref"] for c in cands}
            resolved = sel in eligible_ids
            clarifications.append({"from": subject,
                                   "kind": "record_selection",
                                   "resolved": resolved})
            steps.append({"action": "request_clarification",
                          "kind": "record_selection",
                          "candidates": sorted(eligible_ids),
                          "resolved": resolved})
            if resolved:
                rec = next(c for c in cands if c["app_ref"] == sel)
            else:
                continue  # ambiguous -> hold, never first-match
        else:
            steps.append({"action": "ref_lookup", "subject": subject,
                          "result": "no_eligible_record"})
            continue
        ref_field = _ref_field_for(view_work, rec)
        if ref_field is None:
            steps.append({"action": "ref_lookup", "subject": subject,
                          "result": "no_authorized_source"})
            continue
        acc = _acceptance_entry(view_work, dest["address"], purpose,
                                subject)
        if acc == "ref_acceptance_unknown":
            reply = replies.get(dest_p)
            resolved = bool(reply and reply.get("kind") == "ref_acceptance"
                            and reply.get("accepts") is True)
            clarifications.append({"to": dest_p,
                                   "kind": "ref_acceptance",
                                   "resolved": resolved})
            steps.append({"action": "request_clarification",
                          "to": dest_p, "kind": "ref_acceptance",
                          "resolved": resolved})
            if resolved:
                dent = view_work["directory"].setdefault(
                    dest["address"], {})
                dent.setdefault("reference_acceptance", []).append(
                    {"ref_type": REF_CLASS, "purpose": purpose,
                     "subjects": [subject]})
                acc = "permitted"
            else:
                acc = "ref_acceptance_declined"
        if acc != "permitted":
            steps.append({"action": "ref_lookup", "subject": subject,
                          "result": acc})
            continue
        r_allows, r_denies = _ref_records(view_work, ref_field, subject,
                                          dest_p, purpose, clock)
        if r_denies:
            steps.append({"action": "ref_lookup", "subject": subject,
                          "result": "policy_conflict"})
            continue
        if not _valid_sharing_auth(rec, subject, dest_p, purpose,
                                   clock) and not r_allows:
            steps.append({"action": "ref_lookup", "subject": subject,
                          "result": "ref_sharing_unauthorized"})
            continue
        covered = [f for f in target if f in rec["fields_on_file"]]
        if restricted and len(covered) < len(target):
            steps.append({"action": "ref_lookup", "subject": subject,
                          "result": "restriction_blocks_partial",
                          "note": "record covers a subset; restriction "
                                  "forbids the raw remainder"})
            continue
        revised = _substitute(call, covered, ref_field, rec["app_ref"])
        steps.append({"action": "substitute_reference",
                      "dropped": covered, "added": ref_field})
        v2 = copy.deepcopy(view_work)
        v2["planner_call"] = revised
        recheck = mnd_check_episode(v2, clock, policy)
        steps.append({"action": "reverify",
                      "execution": recheck["execution"],
                      "fingerprint": recheck["fingerprint"][:16]})
        if recheck["execution"] == "allow" \
                and not (restricted and _restriction_violates(v2,
                                                            restriction)):
            return {"execution": "allow",
                    "recovery": "min_disclosure_substitution",
                    "steps": steps, "final_call": revised,
                    "fields_dropped": covered,
                    "clarifications": clarifications,
                    "auth_events": [], "first": first}

    # ref path dead
    if restricted:
        # 'reference only' forbids raw fields; no authorized change to
        # the restriction occurred -> hold is the CORRECT outcome
        steps.append({"action": "hold_restriction",
                      "note": "no eligible ref path; restriction forbids "
                              "raw-field fallback"})
        return {"execution": "block", "recovery": "hold_restriction",
                "steps": steps, "final_call": None, "fields_dropped": [],
                "clarifications": clarifications, "auth_events": [],
                "first": first}
    fb = recover_episode(view, clock, policy, env=env)
    fb["steps"] = steps + fb.get("steps", [])
    fb["clarifications"] = clarifications + fb.get("clarifications", [])
    fb["first"] = first
    return fb
