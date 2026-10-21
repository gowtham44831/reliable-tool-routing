"""Controlled clarification arms — mnd-clar-1.0 (new milestone).

THREE arms sharing ONE safety core (all enforce: authorization,
deny-wins, expiry, disclosure restrictions, eligible-record filtering,
re-verification). All support reference substitution. ONLY the
clarification capability differs:

- clar_none (A):            no clarification — verified evidence only;
                            already-authorized fallback or stop.
- clar_owner (B):           + ask the OWNER (record_selection +
                            scoped field_grant).
- clar_owner_recipient (C): + ask the RECIPIENT (ref_acceptance).

Typed reply protocol (fix over previous runs): requests carry an
explicit kind {record_selection, field_grant, ref_acceptance}; a
request consumes ONLY a reply whose inferred kind matches. A grant
request can never accidentally consume a selection reply, etc.
Silence / refusal / wrong-authority / mismatched replies are explicit
outcomes, classified at ask time: affirmative | declined | unanswered
| invalid_reply.

Budget: each (kind, target) may be asked at most once per episode.
Termination: deliver, exhaust the permitted request set, or no legal
step remains -> partial-authorized delivery or stop.
"""
from __future__ import annotations

import copy

from tool_routing.argverify.disclosure import PROTECTED_CLASSES
from tool_routing.argverify.min_disclosure import (
    REF_CLASS, _acceptance_entry, _eligible_records, _ref_field_for,
    _ref_records, _restriction_violates, _substitute,
    _valid_sharing_auth, mnd_check_episode)

CAPS = {
    "clar_none": {"owner_selection": False, "owner_grant": False,
                  "recipient_acceptance": False},
    "clar_owner": {"owner_selection": True, "owner_grant": True,
                   "recipient_acceptance": False},
    "clar_owner_recipient": {"owner_selection": True,
                             "owner_grant": True,
                             "recipient_acceptance": True},
}


def _infer_kind(reply: dict | None) -> str | None:
    if not reply:
        return None
    if reply.get("kind"):
        return reply["kind"]
    if "selects_app_ref" in reply:
        return "record_selection"
    if "accepts" in reply:
        return "ref_acceptance"
    return "field_grant"


def _question_payload(kind: str, ctx: dict) -> dict:
    """Build the outbound clarification message. Clarification messages
    ARE outbound disclosures: they may carry only task/reference-type
    information unless sharing more is already authorized. Field and
    record identifiers may go to their OWNER; an acceptance question to
    a recipient carries ref_type+purpose only — never field names,
    values, or candidate IDs."""
    if kind == "ref_acceptance":
        return {"kind": kind, "ref_type": REF_CLASS,
                "purpose": ctx["purpose"]}
    if kind == "record_selection":
        return {"kind": kind, "candidates": ctx["candidates"],
                "purpose": ctx["purpose"],
                "destination": ctx["dest_p"]}
    if kind == "field_grant":
        return {"kind": kind, "fields": ctx["fields"],
                "purpose": ctx["purpose"],
                "destination": ctx["dest_p"]}
    return {"kind": kind}


def _payload_disclosed_fields(kind: str, payload: dict,
                              target_owner: bool,
                              meta: dict) -> list[str]:
    """Which protected-data fields does this message actually disclose?
    Field NAMES to the field owner are metadata; a non-owner recipient
    must never receive protected field names or values."""
    if target_owner:
        return []                       # owner may see own field names
    if kind == "field_grant":
        return [f for f in payload.get("fields", [])
                if meta.get(f, {}).get("class") in PROTECTED_CLASSES]
    return []                           # selection/acceptance carry IDs


def _ask(kind: str, target: str, replies: dict, asked: set,
         clarifications: list, ctx: dict) -> tuple[str, dict | None]:
    """Typed, scoped, disclosure-checked request.

    - message built by _question_payload (disclosure rules apply);
    - binds a reply to request_id + kind + principal + destination +
      purpose: kind mismatch or scope mismatch -> invalid_reply (it is
      an answered request, never silently 'unanswered');
    - budget: each (kind,target) asked once per episode."""
    req_id = f"req-{len(clarifications) + 1}"
    meta = ctx["meta"]
    payload = _question_payload(kind, ctx)
    disclosed = _payload_disclosed_fields(
        kind, payload, target_owner=ctx["is_owner_target"], meta=meta)
    message = {"request_id": req_id, "kind": kind, "to": target,
               "payload": payload, "disclosed_fields": disclosed,
               "dest_p": ctx["dest_p"], "purpose": ctx["purpose"]}
    if (kind, target) in asked:
        clarifications.append({"request_id": req_id, "to": target,
                               "request_kind": kind, "message": message,
                               "outcome": "budget_exhausted"})
        return "unanswered", None
    asked.add((kind, target))
    reply = replies.get(target)
    rkind = _infer_kind(reply)
    if reply is None:
        outcome = "unanswered"
    elif reply.get("request_id") and reply["request_id"] != req_id:
        outcome = "invalid_reply"        # bound to a different request
    elif rkind != kind:
        outcome = "invalid_reply"        # answered a different question
    elif reply.get("destination_principal") \
            and reply["destination_principal"] != ctx["dest_p"]:
        outcome = "invalid_reply"        # wrong-authority scope
    elif reply.get("purpose") and reply["purpose"] != ctx["purpose"]:
        outcome = "invalid_reply"
    elif kind == "ref_acceptance":
        outcome = "affirmative" if reply.get("accepts") is True \
            else "declined"
    elif kind == "field_grant":
        if reply.get("grants_fields"):
            outcome = "affirmative"
        elif reply.get("denies_fields"):
            outcome = "declined"
        else:
            outcome = "invalid_reply"    # empty grant authorizes nothing
    elif kind == "record_selection":
        outcome = "candidate"            # caller knows the eligible set
    else:
        outcome = "invalid_reply"
    clarifications.append({"request_id": req_id, "to": target,
                           "request_kind": kind, "reply_kind": rkind,
                           "message": message, "outcome": outcome})
    return outcome, reply


def _apply_grant_reply(view_work: dict, reply: dict, owner: str,
                       dest_p: str, purpose: str) -> bool:
    """Append permission records from a scoped owner grant reply.
    Scoped: destination + purpose must match the pending action."""
    if reply.get("destination_principal") != dest_p \
            or reply.get("purpose") != purpose:
        return False
    nxt = max((t["turn"] for t in view_work["conversation"]),
              default=0) + 1
    view_work["conversation"].append(
        {"turn": nxt, "speaker": owner, "authenticated": True,
         "text": reply.get("text", "")})
    for f in reply.get("grants_fields", []):
        view_work["permission_records"].append({
            "auth_id": f"turn.{nxt}-grant", "data_owner": owner,
            "permitted_fields": [f], "destination_principal": dest_p,
            "purpose": purpose, "effect": "allow",
            "granted_by": {"principal": owner, "source": f"turn.{nxt}"}})
    for f in reply.get("denies_fields", []):
        view_work["permission_records"].append({
            "auth_id": f"turn.{nxt}-deny", "data_owner": owner,
            "permitted_fields": [f], "destination_principal": dest_p,
            "purpose": purpose, "effect": "deny",
            "granted_by": {"principal": owner, "source": f"turn.{nxt}"}})
    return True


def clar_arm_episode(view: dict, clock: str, policy: dict, arm: str,
                     env: dict | None = None) -> dict:
    """Shared-core episode; `arm` selects only clarification caps."""
    caps = CAPS[arm]
    replies = (env or {}).get("replies", {})
    restriction = view.get("disclosure_restriction")
    restricted = bool(restriction
                      and restriction.get("type") == "reference_only")
    call = view["planner_call"]
    purpose = call["stated_purpose"]
    meta = view["field_metadata"]
    steps, clarifications, asked = [], [], set()

    first = mnd_check_episode(view, clock, policy)
    if first["execution"] == "allow" \
            and not _restriction_violates(view, restriction):
        return {"execution": "allow", "recovery": "allow", "steps": steps,
                "final_call": call, "fields_dropped": [],
                "clarifications": clarifications, "first": first}

    dest = first["destination"]
    dest_p = dest["principal"] if dest else None
    view_work = copy.deepcopy(view)

    target = [f for f in call["payload_fields"]
              if meta.get(f, {}).get("class") in PROTECTED_CLASSES] \
        if restricted else \
        [f["field"] for f in first["findings"]
         if f["finding"] == "no_authorization"
         and meta.get(f["field"], {}).get("class") in PROTECTED_CLASSES]
    subjects = sorted({meta[f]["owner"] for f in target})

    # ---- ref path (all arms; identical safety checks) ----------------
    for subject in subjects:
        cands = _eligible_records(view_work, subject, dest_p, purpose,
                                  clock)
        rec = None
        if len(cands) == 1:
            rec = cands[0]
        elif len(cands) > 1:
            if not caps["owner_selection"]:
                steps.append({"action": "ref_lookup", "subject": subject,
                              "result": "ambiguous_no_clarify"})
                continue
            outcome, reply = _ask(
                "record_selection", subject, replies, asked,
                clarifications,
                {"meta": meta, "purpose": purpose, "dest_p": dest_p,
                 "is_owner_target": True,
                 "candidates": sorted(c["app_ref"] for c in cands)})
            sel = reply.get("selects_app_ref") if reply else None
            eligible_ids = {c["app_ref"] for c in cands}
            if outcome != "candidate" or sel not in eligible_ids:
                if outcome == "candidate":
                    clarifications[-1]["outcome"] = "invalid_reply"
                steps.append({"action": "request_clarification",
                              "kind": "record_selection",
                              "resolved": False})
                continue
            clarifications[-1]["outcome"] = "affirmative"
            steps.append({"action": "request_clarification",
                          "kind": "record_selection", "resolved": True})
            rec = next(c for c in cands if c["app_ref"] == sel)
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
            if not caps["recipient_acceptance"]:
                steps.append({"action": "ref_lookup", "subject": subject,
                              "result": "acceptance_unknown_no_clarify"})
                continue
            outcome, reply = _ask(
                "ref_acceptance", dest_p, replies, asked, clarifications,
                {"meta": meta, "purpose": purpose, "dest_p": dest_p,
                 "is_owner_target": False})
            steps.append({"action": "request_clarification",
                          "kind": "ref_acceptance",
                          "resolved": outcome == "affirmative"})
            if outcome == "affirmative":
                dent = view_work["directory"].setdefault(
                    dest["address"], {})
                dent.setdefault("reference_acceptance", []).append(
                    {"ref_type": REF_CLASS, "purpose": purpose,
                     "subjects": [subject]})
                acc = "permitted"
            else:
                continue
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
                          "result": "restriction_blocks_partial"})
            continue
        revised = _substitute(call, covered, ref_field, rec["app_ref"])
        steps.append({"action": "substitute_reference",
                      "dropped": covered, "added": ref_field})
        v2 = copy.deepcopy(view_work)
        v2["planner_call"] = revised
        recheck = mnd_check_episode(v2, clock, policy)
        steps.append({"action": "reverify",
                      "execution": recheck["execution"]})
        if recheck["execution"] == "allow" \
                and not (restricted and _restriction_violates(
                    v2, restriction)):
            return {"execution": "allow",
                    "recovery": "min_disclosure_substitution",
                    "steps": steps, "final_call": revised,
                    "fields_dropped": covered,
                    "clarifications": clarifications, "first": first}

    # ---- field path -------------------------------------------------
    if restricted:
        steps.append({"action": "hold_restriction"})
        return {"execution": "block", "recovery": "hold_restriction",
                "steps": steps, "final_call": None, "fields_dropped": [],
                "clarifications": clarifications, "first": first}

    # owner-grant clarification (B and C only); A uses only already-
    # authorized evidence
    if caps["owner_grant"]:
        for owner in subjects:
            outcome, reply = _ask(
                "field_grant", owner, replies, asked, clarifications,
                {"meta": meta, "purpose": purpose, "dest_p": dest_p,
                 "is_owner_target": True,
                 "fields": [f for f in target
                            if meta.get(f, {}).get("owner") == owner]})
            steps.append({"action": "request_clarification",
                          "kind": "field_grant",
                          "resolved": outcome == "affirmative"})
            if outcome in ("affirmative", "declined") and reply:
                _apply_grant_reply(view_work, reply, owner, dest_p,
                                   purpose)
        recheck = mnd_check_episode(view_work, clock, policy)
        steps.append({"action": "reverify",
                      "execution": recheck["execution"]})
    else:
        recheck = first

    # deliver the currently-authorized subset (drop what remains
    # unauthorized), then reverify — same safety core for every arm
    blocked_now = {f["field"] for f in recheck["findings"]
                   if f["finding"] != "permitted"}
    if blocked_now:
        revised = copy.deepcopy(call)
        revised["payload_fields"] = [f for f in call["payload_fields"]
                                     if f not in blocked_now]
        revised["arguments"]["body"] = "\n".join(
            l for l in call["arguments"]["body"].split("\n")
            if l.split(":")[0] not in
            {f.split(".")[-1] for f in blocked_now})
        v2 = copy.deepcopy(view_work)
        v2["planner_call"] = revised
        recheck = mnd_check_episode(v2, clock, policy)
        steps.append({"action": "drop_unauthorized",
                      "dropped": sorted(blocked_now)})
        steps.append({"action": "reverify",
                      "execution": recheck["execution"]})
        if not revised["payload_fields"]:
            return {"execution": "block", "recovery": "no_authorized",
                    "steps": steps, "final_call": None,
                    "fields_dropped": sorted(blocked_now),
                    "clarifications": clarifications, "first": first}
        if recheck["execution"] == "allow":
            return {"execution": "allow",
                    "recovery": "authorized_subset",
                    "steps": steps, "final_call": revised,
                    "fields_dropped": sorted(blocked_now),
                    "clarifications": clarifications, "first": first}
    elif recheck["execution"] == "allow":
        return {"execution": "allow",
                "recovery": "authorized_subset" if caps["owner_grant"]
                else "allow_after_evidence",
                "steps": steps, "final_call": view_work["planner_call"],
                "fields_dropped": [], "clarifications": clarifications,
                "first": first}
    return {"execution": "block", "recovery": "no_authorized",
            "steps": steps, "final_call": None, "fields_dropped": [],
            "clarifications": clarifications, "first": first}
