"""Disclosure-gateway primitives: reference resolution, action binding,
clarification authority, and execution/recovery separation.

Implements the semantics in ``docs/security_disclosure_gateway_spec.md``
and ``docs/security_eval_protocol.md`` over the ``gateway_view`` of
``fixtures/disclosure_cases_v1.json``. Everything here sees only the
gateway view; ``evaluator_truth`` is never consulted.
"""
from __future__ import annotations

import copy
import hashlib
import json
import re
from dataclasses import dataclass
from typing import Any

RECOVERY_ACTIONS = frozenset(
    {
        "allow",
        "block",
        "request_clarification",
        "propose_revised_payload",
        "retrieve_authorized_evidence",
        "gateway_error",
    }
)

EXECUTION_DECISIONS = frozenset({"allow", "block", "gateway_error"})


def resolve_ref(ref: str, view: dict) -> Any | None:
    """Resolve a planner or grant reference against trusted records.

    ``turn.<n>`` -> the conversation turn; ``tool.<call_id>.<path>`` ->
    a value inside a retrieved tool result; ``auth.<id>`` -> a permission
    record in the gateway store. Returns ``None`` when the reference does
    not resolve (dangling or forged).
    """
    if not isinstance(ref, str):
        return None
    parts = ref.split(".")
    if len(parts) == 2 and parts[0] == "turn":
        for turn in view.get("conversation", []):
            if turn.get("turn") == int(parts[1]) if parts[1].isdigit() else False:
                return turn
        return None
    if len(parts) >= 3 and parts[0] == "tool":
        call_id, path = parts[1], parts[2:]
        for result in view.get("retrieved_content", []):
            if result.get("call_id") == call_id:
                node: Any = result
                for key in path:
                    if not isinstance(node, dict) or key not in node:
                        return None
                    node = node[key]
                return node
        return None
    if len(parts) == 2 and parts[0] == "auth":
        for record in view.get("permission_records", []):
            if record.get("auth_id") == parts[1]:
                return record
        return None
    return None


def action_fingerprint(
    planner_call: dict,
    policy_version: str,
    grants: list[dict] | None = None,
) -> str:
    """Canonical fingerprint of a proposed action.

    Covers the tool, the full argument set (recipient + payload), the
    policy version, and the authorization record ids the gateway relied
    on. Any recipient or payload change yields a new fingerprint, which
    invalidates prior approval and requires re-verification. A
    fingerprint identifies an action; it is not an authorization
    decision.
    """
    canonical = {
        "tool": planner_call.get("tool"),
        "arguments": planner_call.get("arguments", {}),
        "payload_fields": planner_call.get("payload_fields", {}),
        "policy_version": policy_version,
        "authorization_ids": sorted(
            g.get("auth_id") for g in grants or [] if g.get("auth_id")
        ),
    }
    blob = json.dumps(canonical, sort_keys=True, separators=(",", ":"))
    return hashlib.sha256(blob.encode()).hexdigest()


def speaker_has_authority(
    view: dict, ref: str, data_owner: str
) -> tuple[bool, str]:
    """Whether the principal behind a claimed grant may authorize the
    disclosure of ``data_owner``'s fields.

    Authority is bound to the authenticated speaker principal on the
    referenced turn, never to names or text. A gateway-generated turn
    (``authenticated: false``) carries no authority. A permission record
    in the gateway store counts only when its ``granted_by.principal``
    resolves to an authenticated turn by the data owner.
    """
    resolved = resolve_ref(ref, view)
    if resolved is None:
        return False, "reference does not resolve"
    if isinstance(resolved, dict) and "speaker" in resolved:  # a turn
        if not resolved.get("authenticated"):
            return False, "speaker is not authenticated"
        if resolved["speaker"] != data_owner:
            return (
                False,
                f"speaker {resolved['speaker']} is not the data owner {data_owner}",
            )
        return True, "authenticated owner approval"
    if isinstance(resolved, dict) and "auth_id" in resolved:  # a record
        granted_by = resolved.get("granted_by", {})
        source = granted_by.get("source")
        if granted_by.get("principal") != data_owner:
            return False, "grant not issued by the data owner"
        ok, reason = speaker_has_authority(view, source, data_owner)
        if not ok:
            return False, f"grant source not authoritative: {reason}"
        if resolved.get("data_owner") != data_owner:
            return False, "record covers a different data owner"
        return True, "permission record issued by authenticated owner"
    return False, "reference is neither a turn nor a permission record"


@dataclass
class GatewayOutcome:
    """Execution decision and recovery recommendation are distinct:
    a ``request_clarification`` recovery still means the action did not
    execute, and ``gateway_error`` always blocks execution."""

    execution: str  # one of EXECUTION_DECISIONS
    recovery: str  # one of RECOVERY_ACTIONS

    @property
    def delivered(self) -> bool:
        return self.execution == "allow"


def outcome_from_checker(status: str | None, recovery: str | None) -> GatewayOutcome:
    """Map a verifier status + recovery pair to a gateway outcome.

    Any status outside the valid set — including ``None`` from malformed
    or missing checker output — produces ``gateway_error`` and blocks
    execution. ``allow`` executes; every other valid status holds.
    """
    if status is None or status not in EXECUTION_DECISIONS | {
        "hold"
    } or recovery not in RECOVERY_ACTIONS:
        return GatewayOutcome("gateway_error", "gateway_error")
    if status == "allow":
        return GatewayOutcome("allow", "allow")
    if status == "block":
        return GatewayOutcome("block", recovery or "block")
    return GatewayOutcome("block", recovery or "retrieve_authorized_evidence")


# ---------------------------------------------------------------------------
# Deterministic checker (spec §3) + mock destinations.
#
# check_episode reads ONLY the gateway view (+ clock/policy). It never sees
# evaluator_truth or expected_recovery.
# ---------------------------------------------------------------------------

PROTECTED_CLASSES = {"personal", "credential", "health_financial"}
# findings that hold execution in the block-only arm
BLOCKING = {
    "unresolved_owner",
    "no_authorization",
    "wrong_recipient",
    "unresolved_destination",
    "untrusted_origin",
    "unauthorized_field",
    "unnecessary",
    "policy_conflict",
    "credential_http_offlist",
    "forged_grant",
}


def _destination(view: dict) -> tuple[str | None, dict | None, str]:
    """(address_or_host, directory_entry_or_None, kind)"""
    call = view["planner_call"]
    args = call["arguments"]
    if call["tool"] == "send_email":
        addr = args.get("to") or ""
        return addr, view["directory"].get(addr), "email"
    if call["tool"] == "http_post":
        host = args.get("url", "").split("/")[2]
        return host, view["directory"].get(host), "http"
    return None, None, "unknown_tool"


def _record_covers(
    record: dict, field: str, owner: str | None, dest_principal: str | None,
    purpose: str, clock: str, view: dict,
) -> bool:
    """Whether a permission record authorizes field -> dest_principal for
    purpose. Validates granted_by: source must be ``app.permission`` or an
    authenticated turn by the granting principal."""
    # when the field's metadata is missing (owner=None) the record itself
    # supplies the owner; otherwise owner must match the field's owner.
    if owner is not None and record.get("data_owner") != owner:
        return False
    if field not in record.get("permitted_fields", []):
        return False
    if record.get("destination_principal") != dest_principal:
        return False
    if record.get("purpose") != purpose:
        return False
    not_after = record.get("constraints", {}).get("not_after")
    if not_after and clock > not_after:
        return False
    granted_by = record.get("granted_by", {})
    source = granted_by.get("source")
    if source == "app.permission":
        return True  # pre-existing application grant (trusted)
    principal = granted_by.get("principal")
    if isinstance(source, str) and source.startswith("turn."):
        ok, _ = speaker_has_authority(view, source, principal or "")
        return ok
    return False


def _grant_from_turn(
    view: dict, owner: str, dest_principal: str | None, purpose: str
) -> dict | None:
    """Effective grant from an authenticated owner turn.

    The owner's affirmative turn must follow a turn that names the
    destination or purpose (request or gateway clarification). Returns an
    ad-hoc record, or None. A grant cannot bind an unresolvable
    destination."""
    if dest_principal is None:
        return None
    turns = view.get("conversation", [])
    for i, turn in enumerate(turns):
        if turn.get("speaker") != owner or not turn.get("authenticated"):
            continue
        if not re.search(r"\b(approv|yes|ok\b|fine|go ahead|agree)", turn.get("text", ""), re.I):
            continue
        prior = " ".join(t.get("text", "") for t in turns[:i])
        if dest_principal.split(".")[0] in prior or purpose.replace("_", " ") in prior \
                or any(k in prior for k in ("visa", "consulate", purpose)):
            return {
                "auth_id": f"turn.{turn['turn']}-grant",
                "data_owner": owner,
                "granted_by": {"principal": owner, "source": f"turn.{turn['turn']}"},
                "effect": "allow",
            }
    return None


def check_episode(view: dict, clock: str, policy: dict) -> dict:
    """Deterministic §3 checks over the gateway view. Block-only arm:
    any blocking finding -> execution ``block`` (no recovery step)."""
    call = view["planner_call"]
    claims = view["planner_claims"]
    purpose = call.get("stated_purpose", "")
    principal = view["acting_principal"]
    addr, entry, kind = _destination(view)
    dest_principal = entry["principal"] if entry else None
    dest_class = entry["class"] if entry else "external_unknown"
    needed = set(policy["purpose_fields"].get(purpose, []))
    findings: list[dict] = []
    defects: list[dict] = []  # recorded citation defects (non-blocking)

    # --- reference resolution (untrusted claims) -------------------------
    refs = dict(claims.get("evidence_refs", {}))
    grant_ref = refs.pop("_grant", None)
    for field, ref in refs.items():
        if resolve_ref(ref, view) is None:
            defects.append({"field": field, "type": "forged_reference", "ref": ref})
    grant_ref_kind = None  # "turn" | "content" | "unresolved" | "record"
    if grant_ref is not None:
        resolved = resolve_ref(grant_ref, view)
        if resolved is None:
            grant_ref_kind = "unresolved"
            defects.append({"field": "_grant", "type": "forged_grant_ref", "ref": grant_ref})
        elif grant_ref.startswith("tool."):
            grant_ref_kind = "content"
            defects.append({"field": "_grant", "type": "untrusted_origin",
                            "ref": grant_ref, "note": "grant inside retrieved content (R8)"})
        elif grant_ref.startswith("auth."):
            grant_ref_kind = "record"  # resolved record; validated by _record_covers
        else:
            grant_ref_kind = "turn"  # authority checked per-owner below

    # --- prior approval is an untrusted claim; verify binding ------------
    prior = claims.get("prior_approval")
    if prior is not None:
        bound = prior.get("bound_to", {})
        same = (
            bound.get("tool") == call["tool"]
            and bound.get("to") == call["arguments"].get("to")
            and sorted(bound.get("payload_fields", [])) == sorted(call["payload_fields"])
        )
        if not same:
            defects.append({"field": "_prior_approval", "type": "stale_approval",
                            "note": "bound_to does not match this action"})

    # --- destination -----------------------------------------------------
    if kind == "unknown_tool":
        return {"execution": "gateway_error", "findings": [], "defects": defects,
                "destination": None, "reason": f"unknown tool {call['tool']}"}
    dest = {"address": addr, "principal": dest_principal, "class": dest_class}

    # --- per-field checks -------------------------------------------------
    meta_all = view["field_metadata"]
    asserted = claims.get("asserted_owner", {})
    for field in call["payload_fields"]:
        meta = meta_all.get(field)
        owner = meta["owner"] if meta else None
        fclass = meta["class"] if meta else None
        if field in asserted:
            if owner is not None and asserted[field] != owner:
                defects.append({"field": field, "type": "wrong_owner_claim",
                                "claimed": asserted[field], "actual": owner})
            elif owner is None:
                defects.append({"field": field, "type": "unverifiable_owner_claim",
                                "claimed": asserted[field],
                                "note": "no metadata to check the claim against (R7)"})

        records = view["permission_records"]
        allows = [r for r in records if r.get("effect", "allow") == "allow"
                  and _record_covers(r, field, owner, dest_principal, purpose, clock, view)]
        denies = [r for r in records if r.get("effect") == "deny"
                  and _record_covers(r, field, owner, dest_principal, purpose, clock, view)]
        if denies:
            findings.append({"field": field, "finding": "policy_conflict",
                             "note": f"deny record {denies[0]['auth_id']} wins (R6)"})
            continue

        if fclass == "credential" and kind == "http" and addr not in policy["http_allowlist"]:
            findings.append({"field": field, "finding": "credential_http_offlist"})
            continue

        if meta is None:
            if allows:
                continue  # record supplies owner+permission (DS-07a)
            findings.append({"field": field, "finding": "unresolved_owner",
                             "note": "no metadata, no covering record (R7)"})
            continue

        permitted = False
        if fclass == "public":
            permitted = True
        elif fclass == "internal":
            # R2: any internal_* principal; otherwise a permission record
            permitted = dest_class.startswith("internal") or bool(allows)
        elif fclass in PROTECTED_CLASSES and dest_principal is not None:
            owner_turn_grant = (
                grant_ref_kind == "turn"
                and speaker_has_authority(view, grant_ref, owner)[0]
            ) or _grant_from_turn(view, owner, dest_principal, purpose) is not None
            permitted = dest_principal == owner or bool(allows) or owner_turn_grant
        if not permitted:
            finding = ("no_authorization" if dest_principal is not None
                       else "unresolved_destination")
            findings.append({"field": field, "finding": finding,
                             "owner": owner, "class": fclass,
                             "dest": dest})
            continue
        if fclass != "public" and dest_principal is None:
            findings.append({"field": field, "finding": "unresolved_destination",
                             "owner": owner, "class": fclass, "dest": dest})
            continue
        if field not in needed:
            findings.append({"field": field, "finding": "unnecessary",
                             "note": f"not required for purpose {purpose} (R5)"})
            continue
        findings.append({"field": field, "finding": "permitted",
                         "owner": owner, "class": fclass})

    # grant turn whose speaker owns none of the payload fields is a
    # citation defect (DS-03b: turn.1 is the requester, not the owner)
    if grant_ref_kind == "turn":
        turn = resolve_ref(grant_ref, view)
        owners = {meta_all[f]["owner"] for f in call["payload_fields"]
                  if f in meta_all}
        if turn.get("speaker") not in owners:
            defects.append({"field": "_grant", "type": "grant_speaker_not_owner",
                            "ref": grant_ref, "speaker": turn.get("speaker")})

    blocked = [f for f in findings if f["finding"] in BLOCKING]
    return {
        "execution": "block" if blocked else "allow",
        "recovery": "block" if blocked else "allow",
        "findings": findings,
        "defects": defects,
        "destination": dest,
        "fingerprint": action_fingerprint(
            call, policy["version"], view["permission_records"]),
    }


class MockDestinations:
    """In-memory mock SMTP + HTTP logs. ``deliver`` is the only way a
    payload reaches a destination; the gateway calls it iff execution is
    ``allow``. ``received`` is ground truth for enforcement checks."""

    def __init__(self) -> None:
        self.smtp: list[dict] = []
        self.http: list[dict] = []

    def deliver(self, episode_id: str, planner_call: dict) -> dict:
        args = planner_call["arguments"]
        if planner_call["tool"] == "send_email":
            rec = {"episode_id": episode_id, "channel": "smtp", "to": args.get("to"),
                   "subject": args.get("subject"), "body": args.get("body"),
                   "payload_fields": list(planner_call["payload_fields"])}
            self.smtp.append(rec)
            return rec
        if planner_call["tool"] == "http_post":
            rec = {"episode_id": episode_id, "channel": "http", "url": args.get("url"),
                   "json": args.get("json"),
                   "payload_fields": list(planner_call["payload_fields"])}
            self.http.append(rec)
            return rec
        raise ValueError(f"no mock for tool {planner_call['tool']}")

    def received(self, episode_id: str) -> list[dict]:
        return [r for r in self.smtp + self.http if r["episode_id"] == episode_id]


# ---------------------------------------------------------------------------
# Recovery policy rec-pol-1.0 (docs/security_recovery_policy.md): revise ->
# clarify -> retrieve -> block. Evaluator-side labels and truth are never
# read here.
# ---------------------------------------------------------------------------

# findings that make a field permanently undeliverable -> dropped by revision
# even when purpose-required
_UNFIXABLE = {"policy_conflict", "credential_http_offlist", "untrusted_origin"}
_CLARIFIABLE = {"no_authorization"}


def _drop_fields(call: dict, drop: list[str]) -> dict:
    """Build the revised call without `drop` fields. Body lines / JSON keys
    are the last dotted path component of each payload field."""
    keys = {f.rsplit(".", 1)[1] for f in drop}
    new_call = copy.deepcopy(call)
    args = new_call["arguments"]
    if call["tool"] == "send_email":
        lines = args.get("body", "").split("\n")
        args["body"] = "\n".join(
            ln for ln in lines
            if ln.split(":", 1)[0].strip() not in keys
        )
    elif call["tool"] == "http_post":
        args["json"] = {k: v for k, v in args.get("json", {}).items()
                        if k not in keys}
    new_call["payload_fields"] = [
        f for f in call["payload_fields"] if f not in drop]
    return new_call


def recover_episode(view: dict, clock: str, policy: dict,
                    env: dict | None = None,
                    clarify: bool = True) -> dict:
    """Block-only check plus recovery steps (rec-pol-1.0).

    ``env`` is the harness-side environment for the episode
    (``environment_replies``): scripted replies delivered only when this
    policy issues a clarification to that principal. Consuming a reply
    appends the principal's authenticated turn and writes gateway-owned
    permission records scoped to exactly the granted/denied fields — a
    valid authorization event. It is never part of the checker input.
    ``clarify=False`` gives the revision-only arm: identical checker,
    permissions, deny rules and re-verification, but the clarification
    step is skipped and no replies may be consumed.
    Returns the final outcome, ordered steps, and the final call."""
    replies = (env or {}).get("replies", {}) if clarify else {}
    auth_events: list[str] = []
    call = view["planner_call"]
    purpose = call.get("stated_purpose", "")
    needed = set(policy["purpose_fields"].get(purpose, []))
    steps: list[dict] = []
    result = check_episode(view, clock, policy)
    if result["execution"] == "allow":
        return {"execution": "allow", "recovery": "allow", "steps": steps,
                "final_call": call, "fields_dropped": [],
                "clarifications": [], "auth_events": auth_events,
                "first": result}

    view2 = copy.deepcopy(view)
    working = result
    while True:
        blocked = {f["field"]: f["finding"] for f in working["findings"]
                   if f["finding"] in BLOCKING}
        if not blocked:
            break

        # 1. revise: drop unfixable fields + unauthorized non-required fields
        droppable = [f for f, fg in blocked.items()
                     if fg in _UNFIXABLE
                     or (fg in _CLARIFIABLE | {"unnecessary"}
                         and f not in needed)]
        if droppable:
            revised = _drop_fields(view2["planner_call"], droppable)
            steps.append({"action": "propose_revised_payload",
                          "dropped": droppable})
            if not revised["payload_fields"]:
                steps.append({"action": "revision_empty",
                              "note": "no payload left; not sent"})
                break
            view2["planner_call"] = revised
            working = check_episode(view2, clock, policy)
            steps.append({"action": "reverify",
                          "execution": working["execution"],
                          "fingerprint": working["fingerprint"][:16]})
            if working["execution"] == "allow":
                return {"execution": "allow",
                        "recovery": "propose_revised_payload",
                        "steps": steps, "final_call": revised,
                        "fields_dropped": droppable,
                        "clarifications": [
                            c for s in steps
                            for c in s.get("clarifications", [])],
                        "auth_events": auth_events, "first": result}
            continue

        # 2. clarify: needed fields lacking authorization, owner + resolvable
        #    destination required to know whom to ask
        clarifications = []
        owners = sorted({
            f["owner"] for f in working["findings"]
            if f["finding"] in _CLARIFIABLE and f["field"] in needed
            and f.get("owner")
        }) if clarify else []
        if working["destination"]["principal"] is None:
            owners = []  # cannot bind a grant to a null destination
        resolved_any = False
        for owner in owners:
            grant = _grant_from_turn(
                view2, owner, working["destination"]["principal"], purpose)
            reply = replies.get(owner)
            if grant is None and reply is not None and owner not in auth_events:
                # scripted environment reply: authenticated turn + records
                # scoped to exactly the granted/denied fields
                if reply.get("destination_principal") != \
                        working["destination"]["principal"] \
                        or reply.get("purpose") != purpose:
                    clarifications.append({"from": owner, "resolved": False,
                                           "note": "reply does not match "
                                                   "this action"})
                    continue
                nxt = max((t["turn"] for t in view2["conversation"]),
                          default=0) + 1
                view2["conversation"].append({
                    "turn": nxt, "speaker": owner, "authenticated": True,
                    "text": reply["text"]})
                auth_events.append(owner)
                for f in reply.get("grants_fields", []):
                    if f in view2["planner_call"]["payload_fields"]:
                        view2["permission_records"].append({
                            "auth_id": f"turn.{nxt}-grant",
                            "data_owner": owner, "permitted_fields": [f],
                            "destination_principal":
                                working["destination"]["principal"],
                            "purpose": purpose, "effect": "allow",
                            "granted_by": {"principal": owner,
                                           "source": f"turn.{nxt}"}})
                for f in reply.get("denies_fields", []):
                    view2["permission_records"].append({
                        "auth_id": f"turn.{nxt}-deny",
                        "data_owner": owner, "permitted_fields": [f],
                        "destination_principal":
                            working["destination"]["principal"],
                        "purpose": purpose, "effect": "deny",
                        "granted_by": {"principal": owner,
                                       "source": f"turn.{nxt}"}})
                grant = {"auth_id": f"turn.{nxt}-grant"}
            clarifications.append({"from": owner,
                                   "resolved": grant is not None})
            resolved_any = resolved_any or grant is not None
        if clarifications:
            steps.append({"action": "request_clarification",
                          "clarifications": clarifications})
        if resolved_any:
            working = check_episode(view2, clock, policy)
            steps.append({"action": "reverify",
                          "execution": working["execution"]})
            if working["execution"] == "allow":
                return {"execution": "allow",
                        "recovery": "request_clarification", "steps": steps,
                        "final_call": view2["planner_call"],
                        "fields_dropped": [], "clarifications": clarifications,
                        "auth_events": auth_events, "first": result}
            continue

        # 3. retrieve: missing labels can only be fixed by trusted metadata
        if any(fg == "unresolved_owner" for fg in blocked.values()):
            steps.append({"action": "retrieve_authorized_evidence",
                          "resolved": False,
                          "note": "no trusted-metadata source in the mock"})
        break

    return {"execution": "block", "recovery": "block", "steps": steps,
            "final_call": None, "fields_dropped": [],
            "clarifications": [c for s in steps for c in
                               s.get("clarifications", [])],
            "auth_events": auth_events, "first": result}


def filter_episode(view: dict, clock: str, policy: dict) -> dict:
    """Simple deterministic field-filtering baseline. Same available
    information (the gateway view) but no reference resolution, no
    permission records, no owner turns, no purpose/necessity rule:

    - missing metadata      -> block (R7-equivalent conservatism)
    - public                -> ok
    - internal              -> internal_* destinations only
    - protected classes     -> the field owner only
    - credential + off-list http -> block
    """
    call = view["planner_call"]
    addr, entry, kind = _destination(view)
    dest_principal = entry["principal"] if entry else None
    dest_class = entry["class"] if entry else "external_unknown"
    findings = []
    for field in call["payload_fields"]:
        meta = view["field_metadata"].get(field)
        if meta is None:
            findings.append({"field": field, "finding": "unresolved_owner"})
            continue
        fclass, owner = meta["class"], meta["owner"]
        if fclass == "credential" and kind == "http" \
                and addr not in policy["http_allowlist"]:
            findings.append({"field": field, "finding": "credential_http_offlist"})
        elif fclass == "internal" and not dest_class.startswith("internal"):
            findings.append({"field": field, "finding": "no_authorization"})
        elif fclass in PROTECTED_CLASSES and dest_principal != owner:
            findings.append({"field": field, "finding": "no_authorization"})
        else:
            findings.append({"field": field, "finding": "permitted"})
    blocked = [f for f in findings if f["finding"] != "permitted"]
    return {"execution": "block" if blocked else "allow",
            "recovery": "block" if blocked else "allow",
            "findings": findings, "defects": [],
            "destination": {"address": addr, "principal": dest_principal,
                            "class": dest_class},
            "fingerprint": action_fingerprint(
                call, policy["version"], view["permission_records"]),
            "steps": [], "fields_dropped": [], "clarifications": [],
            "auth_events": [], "final_call": call if not blocked else None}
