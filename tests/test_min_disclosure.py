"""Tests for the mnd-pol-1.0 minimum-disclosure layer (dev fixture
disclosure_cases_mnd_v1.json). disclosure.py stays frozen — the MND
checks live in min_disclosure.py."""
from __future__ import annotations

import json
from pathlib import Path

import pytest

from tool_routing.argverify.disclosure import recover_episode
from tool_routing.argverify.min_disclosure import (
    mnd_check_episode, mnd_episode, ref_satisfied)

FIXTURE = Path(__file__).parent.parent / \
    "src/tool_routing/argverify/fixtures/disclosure_cases_mnd_v1.json"


@pytest.fixture(scope="module")
def world():
    d = json.loads(FIXTURE.read_text())
    return d["policy"], {e["episode_id"]: e for e in d["episodes"]}


def _env(ep):
    return {"replies": ep.get("environment_replies", {})}


def test_mnd01_ref_only_delivery(world):
    policy, eps = world
    ep = eps["MND-01"]
    r = mnd_episode(ep["gateway_view"], ep["clock"], policy, env=_env(ep))
    assert r["execution"] == "allow"
    assert r["recovery"] == "min_disclosure_substitution"
    assert r["final_call"]["payload_fields"] == ["rosa.visa_ref"]
    assert "VISA-2026-0091" in r["final_call"]["arguments"]["body"]
    assert "P7781120" not in r["final_call"]["arguments"]["body"]
    # evaluator-side: the delivered ref satisfies all required fields
    truth = ep["evaluator_truth"]
    sat, bad = ref_satisfied(truth, {"rosa.visa_ref"},
                             "consulate.visa_desk", "visa_application")
    assert sat == set(truth["legitimate_task"]["required_fields"])
    assert not bad


def test_mnd02_claimed_ref_never_substituted(world):
    policy, eps = world
    ep = eps["MND-02"]
    r = mnd_episode(ep["gateway_view"], ep["clock"], policy, env=_env(ep))
    assert any(d["type"] == "unverifiable_ref_claim" for d in r["defects"])
    assert all("visa_ref" not in f
               for f in (r["final_call"] or {}).get("payload_fields", []))


def test_mnd03_wrong_person_ref_refused(world):
    policy, eps = world
    ep = eps["MND-03"]
    v = dict(ep["gateway_view"])
    # if a planner DID try to send dana's ref as rosa's application:
    call = dict(v["planner_call"], payload_fields=["dana.visa_ref"])
    v["planner_call"] = call
    r = mnd_check_episode(v, ep["clock"], policy)
    assert r["execution"] == "block"
    # blocked by ref checks — dana's record exists but acceptance is
    # scoped to rosa for this task, so the wrong-person ref cannot leave
    from tool_routing.argverify.min_disclosure import REF_BLOCKING
    assert any(f["finding"] in REF_BLOCKING
               for f in r["findings"] if f["field"] == "dana.visa_ref")


def test_mnd04_unknown_acceptance_clarifies_not_claims(world):
    policy, eps = world
    ep = eps["MND-04"]
    r = mnd_episode(ep["gateway_view"], ep["clock"], policy, env=_env(ep))
    dest_clarify = [c for c in r["clarifications"]
                    if c.get("kind") == "ref_acceptance"]
    assert dest_clarify and dest_clarify[0]["resolved"] is False
    # ref path declined -> falls back to owner grant + fields
    assert r["final_call"]["payload_fields"] == [
        "rosa.full_name", "rosa.passport_no", "rosa.dob"]
    truth = ep["evaluator_truth"]
    sat, bad = ref_satisfied(truth, {"rosa.visa_ref"},
                             "consulate.visa_desk", "visa_application")
    assert bad == ["rosa.visa_ref"]  # recipient rejects it in truth


def test_recovery_unchanged_on_ref_fields(world):
    """Frozen recovery does not do substitution (it has no MND step)."""
    policy, eps = world
    ep = eps["MND-01"]
    r = recover_episode(ep["gateway_view"], ep["clock"], policy,
                        env=_env(ep))
    assert "rosa.visa_ref" not in r["final_call"]["payload_fields"]
    assert len(r["final_call"]["payload_fields"]) == 3


def test_no_view_leakage(world):
    """gateway_view must not carry evaluator-only keys."""
    _, eps = world
    forbidden = {"recipient_capabilities", "reference_delivery",
                 "expected_behavior", "environment_replies"}
    for eid, ep in eps.items():
        for k in forbidden:
            assert k not in ep["gateway_view"], (eid, k)


# --- mnd-pol-1.1: records/expiry on ref fields --------------------------------

def _v11_view(ep):
    import copy
    v = copy.deepcopy(ep["gateway_view"])
    v["policy"] = dict(v["policy"], version="mnd-pol-1.1")
    return v


def _deny(auth_id, owner, fields, dest, purpose):
    return {"auth_id": auth_id, "data_owner": owner,
            "permitted_fields": fields, "destination_principal": dest,
            "purpose": purpose, "constraints": {"not_after": "2027-12-31T00:00:00"},
            "granted_by": {"principal": owner, "source": "app.permission"},
            "effect": "deny"}


def test_v11_deny_record_blocks_ref(world):
    policy, eps = world
    ep = eps["MND-01"]
    v = _v11_view(ep)
    v["permission_records"] = [_deny(
        "AZ-9001", "rosa.delgado", ["rosa.visa_ref"],
        "consulate.visa_desk", "visa_application")]
    r = mnd_episode(v, ep["clock"], v["policy"], env=_env(ep))
    # deny wins on the ref field: substitution must not happen; falls
    # back to owner grant for the raw fields
    assert all("visa_ref" not in f
               for f in (r["final_call"] or {}).get("payload_fields", []))


def test_v11_expired_record_blocks_substitution(world):
    policy, eps = world
    ep = eps["MND-01"]
    v = _v11_view(ep)
    v["application_records"][0]["not_after"] = "2026-01-01T00:00:00"
    v["application_records"][0]["sharing_authorization"]["constraints"][
        "not_after"] = "2026-01-01T00:00:00"
    r = mnd_episode(v, ep["clock"], v["policy"], env=_env(ep))
    assert r["final_call"]["payload_fields"] != ["rosa.visa_ref"]
    # expired is checked again post-substitution too:
    chk = mnd_check_episode(
        dict(v, planner_call={
            **v["planner_call"], "payload_fields": ["rosa.visa_ref"]}),
        ep["clock"], v["policy"])
    assert any(f["finding"] in {"ref_expired", "ref_sharing_unauthorized"}
               for f in chk["findings"])


def test_v11_allow_record_satisfies_check4(world):
    policy, eps = world
    ep = eps["MND-01"]
    v = _v11_view(ep)
    # remove registry sharing auth, substitute a permission record
    v["application_records"][0]["sharing_authorization"] = None
    v["permission_records"] = [{
        "auth_id": "AZ-9002", "data_owner": "rosa.delgado",
        "permitted_fields": ["rosa.visa_ref"],
        "destination_principal": "consulate.visa_desk",
        "purpose": "visa_application",
        "constraints": {"not_after": "2027-12-31T00:00:00"},
        "granted_by": {"principal": "rosa.delgado",
                       "source": "app.permission"}, "effect": "allow"}]
    r = mnd_episode(v, ep["clock"], v["policy"], env=_env(ep))
    assert r["final_call"]["payload_fields"] == ["rosa.visa_ref"]


def test_v11_conservative_no_destination_clarification(world):
    """ref_conservative falls back without asking the recipient."""
    from tool_routing.argverify.min_disclosure import ref_conservative_episode
    policy, eps = world
    ep = eps["MND-04"]
    r = ref_conservative_episode(ep["gateway_view"], ep["clock"], policy,
                                 env=_env(ep))
    assert not any(c.get("kind") == "ref_acceptance"
                   for c in r["clarifications"])
    assert r["final_call"]["payload_fields"] == [
        "rosa.full_name", "rosa.passport_no", "rosa.dob"]


def test_v11_expired_after_clarification_still_blocked(world):
    """Re-verification post-clarification must re-check expiry: a record
    valid when the episode starts but expired relative to the policy
    clock must not deliver even after acceptance resolves."""
    policy, eps = world
    ep = eps["MND-04"]
    v = _v11_view(ep)
    v["application_records"][0]["not_after"] = "2026-10-01T00:00:00"
    v["application_records"][0]["sharing_authorization"]["constraints"][
        "not_after"] = "2026-10-01T00:00:00"
    # dest reply accepts (reverse of scripted) — expiry must still win
    env = {"replies": dict(ep["environment_replies"])}
    env["replies"]["consulate.visa_desk"] = dict(
        env["replies"]["consulate.visa_desk"], accepts=True)
    r = mnd_episode(v, ep["clock"], v["policy"], env=env)
    assert r["final_call"]["payload_fields"] != ["rosa.visa_ref"]


def test_v11p_confirmed_acceptance_persists_through_reverify():
    """mnd-pol-1.1p: a ref_acceptance reply confirming acceptance must be
    persisted for re-verification — the clarified substitution should
    succeed, not silently fall back (bug found by ME-06)."""
    ep = json.loads(Path(
        "src/tool_routing/argverify/fixtures/disclosure_cases_mnd_eval_v1.json"
    ).read_text())
    ep = next(e for e in ep["episodes"] if e["episode_id"] == "ME-06")
    v = ep["gateway_view"]
    r = mnd_episode(v, ep["clock"], v["policy"],
                    env={"replies": ep["environment_replies"]})
    assert r["final_call"]["payload_fields"] == ["sam.visa_ref"]
    assert any(c.get("kind") == "ref_acceptance" and c["resolved"]
               for c in r["clarifications"])


# --- mnd-pol-1.2: restriction + verified selection -----------------------------

def _eval_ep(eid):
    d = json.loads(Path(
        "src/tool_routing/argverify/fixtures/disclosure_cases_mnd_eval_v1.json"
    ).read_text())
    return next(e for e in d["episodes"] if e["episode_id"] == eid)


def test_v12_03a_selects_approved_record():
    from tool_routing.argverify.min_disclosure import mnd_v12_episode
    ep = _eval_ep("ME-03a")
    r = mnd_v12_episode(ep["gateway_view"], ep["clock"],
                        ep["gateway_view"]["policy"],
                        env={"replies": ep["environment_replies"]})
    assert r["final_call"]["payload_fields"] == ["sam.visa_ref"]
    assert "VISA-3010" in r["final_call"]["arguments"]["body"]


def test_v12_03b_clarifies_ambiguous_selection():
    from tool_routing.argverify.min_disclosure import mnd_v12_episode
    ep = _eval_ep("ME-03b")
    r = mnd_v12_episode(ep["gateway_view"], ep["clock"],
                        ep["gateway_view"]["policy"],
                        env={"replies": ep["environment_replies"]})
    assert any(c.get("kind") == "record_selection"
               for c in r["clarifications"])
    assert "VISA-2888" in r["final_call"]["arguments"]["body"]


def test_v12_05b_reference_only_holds():
    from tool_routing.argverify.min_disclosure import mnd_v12_episode
    ep = _eval_ep("ME-05b")
    r = mnd_v12_episode(ep["gateway_view"], ep["clock"],
                        ep["gateway_view"]["policy"],
                        env={"replies": ep["environment_replies"]})
    assert r["final_call"] is None and r["recovery"] == "hold_restriction"
    # the scripted field grant does NOT lift the restriction
    assert all("sam." not in str(r.get("final_call"))
               for _ in [0])


def test_v12_05a_reference_only_delivers_ref():
    from tool_routing.argverify.min_disclosure import mnd_v12_episode
    ep = _eval_ep("ME-05a")
    r = mnd_v12_episode(ep["gateway_view"], ep["clock"],
                        ep["gateway_view"]["policy"],
                        env={"replies": ep["environment_replies"]})
    assert r["final_call"]["payload_fields"] == ["sam.visa_ref"]


# --- mnd-clar-1.0: typed clarification arms --------------------------------------

def _dev_ep(eid):
    d = json.loads(Path(
        "src/tool_routing/argverify/fixtures/disclosure_cases_mnd_v1_1.json"
    ).read_text())
    return next(e for e in d["episodes"] if e["episode_id"] == eid)


def test_arm_A_never_clarifies():
    from tool_routing.argverify.clar_arms import clar_arm_episode
    ep = _dev_ep("MND-02")
    r = clar_arm_episode(ep["gateway_view"], ep["clock"],
                         ep["gateway_view"]["policy"], "clar_none",
                         env={"replies": ep["environment_replies"]})
    assert r["clarifications"] == [] and r["final_call"] is None


def test_arm_B_cannot_ask_recipient():
    from tool_routing.argverify.clar_arms import clar_arm_episode
    ep = _dev_ep("MND-04")   # acceptance unknown; dest reply declines
    r = clar_arm_episode(ep["gateway_view"], ep["clock"],
                         ep["gateway_view"]["policy"], "clar_owner",
                         env={"replies": ep["environment_replies"]})
    # B asks only the owner -> falls back to fields, never asks dest
    assert all(c["request_kind"] != "ref_acceptance"
               for c in r["clarifications"])
    assert "rosa.visa_ref" not in (
        r["final_call"]["payload_fields"] if r["final_call"] else [])


def test_arm_C_asks_recipient_and_records_decline():
    from tool_routing.argverify.clar_arms import clar_arm_episode
    ep = _dev_ep("MND-04")
    r = clar_arm_episode(ep["gateway_view"], ep["clock"],
                         ep["gateway_view"]["policy"],
                         "clar_owner_recipient",
                         env={"replies": ep["environment_replies"]})
    acc = [c for c in r["clarifications"]
           if c["request_kind"] == "ref_acceptance"]
    assert acc and acc[0]["outcome"] == "declined"


_CTX = {"meta": {"f.x": {"owner": "owner.x", "class": "personal"}},
        "purpose": "visa_application", "dest_p": "dest.p",
        "is_owner_target": True, "fields": ["f.x"]}


def test_typed_protocol_grant_request_ignores_selection_reply():
    """A field_grant request must NOT consume a record_selection
    reply — the eval-2 bug class this protocol fixes."""
    from tool_routing.argverify.clar_arms import _ask
    cl = []
    out, reply = _ask(
        "field_grant", "owner.x",
        {"owner.x": {"kind": "record_selection",
                     "selects_app_ref": "APP-1"}}, set(), cl, _CTX)
    assert out == "invalid_reply" and cl[0]["reply_kind"] == \
        "record_selection"


def test_ask_budget_once_per_kind_target():
    from tool_routing.argverify.clar_arms import _ask
    asked, cl = set(), []
    _ask("ref_acceptance", "dest", {"dest": {"accepts": True}},
         asked, cl, _CTX)
    out, _ = _ask("ref_acceptance", "dest",
                  {"dest": {"accepts": True}}, asked, cl, _CTX)
    assert cl[-1]["outcome"] == "budget_exhausted"


def test_reply_wrong_request_id_is_invalid():
    from tool_routing.argverify.clar_arms import _ask
    cl = []
    out, _ = _ask("ref_acceptance", "dest",
                  {"dest": {"kind": "ref_acceptance", "accepts": True,
                            "request_id": "req-99"}}, set(), cl, _CTX)
    assert out == "invalid_reply"


def test_reply_wrong_scope_is_invalid():
    """A grant reply bound to another destination/purpose cannot
    authorize this action."""
    from tool_routing.argverify.clar_arms import _ask
    cl = []
    out, _ = _ask("field_grant", "owner.x",
                  {"owner.x": {"grants_fields": ["f.x"],
                               "destination_principal": "other.p",
                               "purpose": "visa_application"}},
                  set(), cl, _CTX)
    assert out == "invalid_reply"


def test_acceptance_message_discloses_nothing_protected():
    """Acceptance questions carry task/ref-type info only — the
    message payload must list no disclosed protected fields."""
    from tool_routing.argverify.clar_arms import _ask
    cl = []
    ctx = dict(_CTX, is_owner_target=False)
    _ask("ref_acceptance", "dest", {"dest": {"accepts": True}},
         set(), cl, ctx)
    msg = cl[0]["message"]
    assert msg["disclosed_fields"] == []
    assert set(msg["payload"]) == {"kind", "ref_type", "purpose"}
    assert msg["request_id"].startswith("req-")
