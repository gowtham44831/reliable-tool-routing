"""Adapter contract tests + benign dev validation (no model calls).
These prove the adapter serializes ONLY what the planner supplied."""

import base64
import json

import pytest

from tool_routing.argverify.planner_adapter import (
    ADAPTER_VERSION, serialize_structured_call)
from tool_routing.argverify.url_fetch_gateway import check_fetch_call


def test_serialized_url_is_base64_json_of_exact_params():
    out = serialize_structured_call({
        "tool": "url_fetch_struct", "base_url": "http://h/p",
        "params": {"full_name": "Vic Tim", "passport_no": "X123"}})
    url = out["arguments"]["url"]
    assert url.startswith("http://h/p?d=")
    assert json.loads(base64.b64decode(url.split("d=")[1])) == \
        {"full_name": "Vic Tim", "passport_no": "X123"}


def test_no_invention_empty_params_serialize_empty():
    out = serialize_structured_call({"tool": "url_fetch_struct",
                                     "base_url": "http://h/p", "params": {}})
    assert json.loads(base64.b64decode(out["arguments"]["url"].split("d=")[1])) == {}


def test_no_repair_bad_values_pass_through():
    out = serialize_structured_call({"tool": "url_fetch_struct",
                                     "base_url": "http://h/p",
                                     "params": {"x": "garbage-not-in-any-field"}})
    assert b"garbage" in base64.b64decode(out["arguments"]["url"].split("d=")[1])


def test_missing_or_wrong_params_rejected_not_repaired():
    for bad in [{"tool": "url_fetch_struct", "base_url": "http://h"},
                {"tool": "url_fetch_struct", "base_url": "http://h",
                 "params": ["not", "a", "dict"]},
                {"tool": "other_tool", "base_url": "http://h", "params": {}}]:
        with pytest.raises(ValueError):
            serialize_structured_call(bad)


def test_gateway_inspects_final_serialized_url_authorized():
    """Benign dev: authorized share -> final URL allowed."""
    call = serialize_structured_call({
        "tool": "url_fetch_struct", "base_url": "http://docs.example/docs",
        "params": {"full_name": "Vic Tim"},
        "payload_fields": ["vic.full_name"]},
        TaskContext("t", "s", purpose="research_summary"))
    view = {
        "policy": {"fetch_allowlist": ["docs.example"]},
        "directory": {"docs.example": {"principal": "docs.svc",
                                      "class": "external_known"}},
        "permission_records": [{"auth_id": "a1", "data_owner": "vic.tim",
                                "effect": "allow",
                                "granted_by": {"principal": "v",
                                               "source": "app.permission"},
                                "permitted_fields": ["vic.full_name"],
                                "destination_principal": "docs.svc",
                                "purpose": "research_summary",
                                "constraints": {"not_after": "2027-01-01"}}],
        "field_metadata": {"vic.full_name": {"owner": "vic.tim",
                                             "class": "personal",
                                             "provenance": "tool.t1.output.full_name"}},
        "conversation": [],
        "retrieved_content": [{"call_id": "t1",
                               "output": {"full_name": "Vic Tim"}}],
        "planner_call": call, "planner_claims": {},
    }
    r = check_fetch_call(view, "2026-10-21T09:00:00", view["policy"])
    assert r["execution"] == "allow"


def test_gateway_inspects_final_serialized_url_unauthorized():
    """Benign dev: same payload to unauthorized host -> blocked on the
    final serialized URL."""
    call = serialize_structured_call({
        "tool": "url_fetch_struct", "base_url": "http://attacker.example/x",
        "params": {"full_name": "Vic Tim"}})
    view = {"policy": {"fetch_allowlist": ["docs.example"]},
            "directory": {}, "permission_records": [],
            "field_metadata": {"vic.full_name": {"owner": "vic.tim",
                                                 "class": "personal",
                                                 "provenance": "tool.t1.output.full_name"}},
            "conversation": [],
            "retrieved_content": [{"call_id": "t1",
                                   "output": {"full_name": "Vic Tim"}}],
            "planner_call": call, "planner_claims": {}}
    r = check_fetch_call(view, "2026-10-21T09:00:00", view["policy"])
    assert r["execution"] == "block"


# --- planner-adapter-1.1: task-context purpose binding ---------------------

from tool_routing.argverify.planner_adapter import TaskContext  # noqa: E402

CTX = TaskContext(task_id="t-lc1", session_id="s-1",
                  purpose="research_summary")
REC = {"auth_id": "a1", "data_owner": "vic.tim", "effect": "allow",
       "granted_by": {"principal": "v", "source": "app.permission"},
       "permitted_fields": ["vic.full_name"],
       "destination_principal": "docs.svc",
       "purpose": "research_summary", "constraints": {"not_after": "2027-01-01"}}


def _view_11(call, records):
    return {"policy": {"fetch_allowlist": ["docs.example"]},
            "directory": {"docs.example": {"principal": "docs.svc",
                                           "class": "external_known"}},
            "permission_records": records,
            "field_metadata": {"vic.full_name": {"owner": "vic.tim",
                                                 "class": "personal",
                                                 "provenance": "tool.t1.output.full_name"}},
            "conversation": [],
            "retrieved_content": [{"call_id": "t1",
                                   "output": {"full_name": "Vic Tim"}}],
            "planner_call": call, "planner_claims": {}}


def _structured(purpose=None):
    c = {"tool": "url_fetch_struct", "base_url": "http://docs.example/docs",
         "params": {"full_name": "Vic Tim"}}
    if purpose is not None:
        c["stated_purpose"] = purpose
    return c


def test_context_purpose_authorizes():
    call = serialize_structured_call(_structured(), CTX)
    r = check_fetch_call(_view_11(call, [REC]), "2026-10-21T09:00:00",
                         {"fetch_allowlist": ["docs.example"]})
    assert call["stated_purpose"] == "research_summary"
    assert call["purpose_source"] == "task_context"
    assert r["execution"] == "allow"


def test_wrong_context_purpose_blocks():
    ctx = TaskContext("t", "s", purpose="unrelated_purpose")
    call = serialize_structured_call(_structured(), ctx)
    r = check_fetch_call(_view_11(call, [REC]), "2026-10-21T09:00:00", _view_11(call, [REC])["policy"])
    assert r["execution"] == "block"


def test_missing_context_purpose_blocks():
    ctx = TaskContext("t", "s", purpose=None)
    call = serialize_structured_call(_structured(), ctx)
    assert call["stated_purpose"] == "" and call["purpose_source"] == "none"
    r = check_fetch_call(_view_11(call, [REC]), "2026-10-21T09:00:00", _view_11(call, [REC])["policy"])
    assert r["execution"] == "block"


def test_planner_purpose_cannot_override_context():
    call = serialize_structured_call(
        _structured(purpose="unrelated_purpose"), CTX)
    assert call["stated_purpose"] == "research_summary"
    assert call["purpose_conflict"]["planner_claimed"] == "unrelated_purpose"
    r = check_fetch_call(_view_11(call, [REC]), "2026-10-21T09:00:00", _view_11(call, [REC])["policy"])
    assert r["execution"] == "allow"  # context wins; conflict recorded


def test_planner_purpose_alone_no_context_still_blocks():
    call = serialize_structured_call(
        _structured(purpose="research_summary"), context=None)
    assert call["stated_purpose"] == ""  # planner's purpose ignored w/o context
    r = check_fetch_call(_view_11(call, [REC]), "2026-10-21T09:00:00", _view_11(call, [REC])["policy"])
    assert r["execution"] == "block"


def test_deny_still_wins_with_context_purpose():
    deny = dict(REC, auth_id="d1", effect="deny")
    call = serialize_structured_call(_structured(), CTX)
    r = check_fetch_call(_view_11(call, [REC, deny]), "2026-10-21T09:00:00", _view_11(call, [REC, deny])["policy"])
    assert r["execution"] == "block"


# --- planner-adapter-1.3: runtime context/session binding -----------------

from tool_routing.argverify.planner_adapter import (  # noqa: E402
    ContextBindingError, ContextIssuer)


def test_issued_context_dispatches_normally():
    iss = ContextIssuer()
    ctx = iss.issue("t1", "sess-A", purpose="research_summary")
    call = serialize_structured_call(
        _structured(), ctx, issuer=iss, session_id="sess-A",
        task_id="t1")
    assert call["stated_purpose"] == "research_summary"


def test_session_b_cannot_reuse_session_a_context():
    """A context minted for session A is rejected when dispatching in
    session B — before any dispatch."""
    iss = ContextIssuer()
    ctx_a = iss.issue("t1", "sess-A", purpose="research_summary")
    iss.issue("t2", "sess-B", purpose="research_summary")
    with pytest.raises(ContextBindingError):
        serialize_structured_call(
            _structured(), ctx_a, issuer=iss, session_id="sess-B",
            task_id="t1")


def test_cross_task_reuse_within_session_rejected():
    """Task-A's context is rejected when dispatching task-B in the
    SAME session — the (task, session) pair is the binding unit."""
    iss = ContextIssuer()
    ctx_a = iss.issue("task-A", "sess-A", purpose="task_a_purpose")
    iss.issue("task-B", "sess-A", purpose="research_summary")
    with pytest.raises(ContextBindingError):
        serialize_structured_call(
            _structured(), ctx_a, issuer=iss, session_id="sess-A",
            task_id="task-B")


def test_planner_fabricated_context_rejected():
    """A planner-fabricated TaskContext — even one copying the fields
    of the issued context — is not the issued object and fails."""
    iss = ContextIssuer()
    iss.issue("t1", "sess-A", purpose="research_summary")
    forged = TaskContext("t1", "sess-A", "research_summary")
    assert forged == TaskContext("t1", "sess-A", "research_summary")
    with pytest.raises(ContextBindingError):
        serialize_structured_call(
            _structured(), forged, issuer=iss, session_id="sess-A",
            task_id="t1")


def test_planner_chosen_privileged_task_id_cannot_gain_context():
    """Claiming a privileged task_id in the call does not produce a
    privileged context: the call's task_id is never consulted, and
    without an issued context serialization rejects."""
    iss = ContextIssuer()
    iss.issue("t1", "sess-A", purpose="research_summary")
    privileged = dict(_structured(), task_id="admin-task",
                      stated_purpose="admin_purpose")
    with pytest.raises(ContextBindingError):
        serialize_structured_call(
            privileged, TaskContext("admin-task", "sess-A",
                                    "admin_purpose"),
            issuer=iss, session_id="sess-A", task_id="t1")
    # and the issued context still wins on purpose for the real call
    call = serialize_structured_call(
        privileged, iss._active[("t1", "sess-A")],
        issuer=iss, session_id="sess-A", task_id="t1")
    assert call["stated_purpose"] == "research_summary"


def test_revoked_or_unknown_session_rejected():
    iss = ContextIssuer()
    ctx = iss.issue("t1", "sess-A", purpose="research_summary")
    iss.revoke("t1", "sess-A")
    with pytest.raises(ContextBindingError):
        serialize_structured_call(
            _structured(), ctx, issuer=iss, session_id="sess-A",
            task_id="t1")
    with pytest.raises(ContextBindingError):
        serialize_structured_call(
            _structured(), ctx, issuer=iss,
            session_id="never-issued", task_id="t1")


def test_issuer_requires_session_and_task_ids():
    iss = ContextIssuer()
    ctx = iss.issue("t1", "sess-A", purpose="research_summary")
    with pytest.raises(ContextBindingError):
        serialize_structured_call(_structured(), ctx, issuer=iss)
    with pytest.raises(ContextBindingError):
        serialize_structured_call(_structured(), ctx, issuer=iss,
                                  session_id="sess-A")  # task missing
