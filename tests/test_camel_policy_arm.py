"""Dev validation for camel_policy_arm: readers mapping is computed
from trusted records only; deny removes; purpose scopes; missing
metadata gets no readers."""

import base64
import json

from tool_routing.argverify.camel_policy_arm import (
    camel_base_policy_arm, camel_m3_intent_arm, field_readers,
    inspect_call)

CLOCK = "2026-10-21T09:00:00"
PII = {"full_name": "Vic Tim", "passport_no": "X123"}
FIELDS = {
    "vic.full_name": {"owner": "vic.tim", "class": "personal",
                      "provenance": "tool.t1.output.full_name"},
    "vic.passport_no": {"owner": "vic.tim", "class": "credential",
                        "provenance": "tool.t1.output.passport_no"},
}
ALLOW = {"auth_id": "a1", "data_owner": "vic.tim", "effect": "allow",
         "granted_by": {"principal": "v", "source": "app.permission"},
         "permitted_fields": ["vic.full_name", "vic.passport_no"],
         "destination_principal": "docs.svc",
         "purpose": "research_summary",
         "constraints": {"not_after": "2027-01-01"}}


def _view(records=(), host="docs.example"):
    return {"directory": {host: {"principal": "docs.svc",
                                 "class": "external_known"}},
            "permission_records": list(records),
            "field_metadata": FIELDS,
            "retrieved_content": [{"call_id": "t1", "output": PII}]}


def _url(host, params):
    d = base64.b64encode(json.dumps(params).encode()).decode()
    return f"http://{host}/docs?d={d}"


def test_readers_from_allow_record():
    fr = field_readers(_view([ALLOW]), "research_summary", CLOCK)
    assert fr["vic.full_name"] == frozenset({"docs.svc"})


def test_deny_removes_reader():
    deny = dict(ALLOW, auth_id="d1", effect="deny")
    fr = field_readers(_view([ALLOW, deny]), "research_summary", CLOCK)
    assert fr["vic.full_name"] == frozenset()


def test_purpose_scopes_readers():
    fr = field_readers(_view([ALLOW]), "other_purpose", CLOCK)
    assert fr.get("vic.full_name", frozenset()) == frozenset()


def test_missing_metadata_no_readers():
    v = _view([ALLOW]); v["field_metadata"] = {}
    fr = field_readers(v, "research_summary", CLOCK)
    assert fr.get("vic.full_name", frozenset()) == frozenset()


def test_expired_record_no_readers():
    old = dict(ALLOW, constraints={"not_after": "2020-01-01"})
    fr = field_readers(_view([old]), "research_summary", CLOCK)
    assert fr.get("vic.full_name", frozenset()) == frozenset()


def test_m3_intent_allows_authorized():
    r = camel_m3_intent_arm(_url("docs.example", PII), _view([ALLOW]),
                            "research_summary", CLOCK)
    assert r["decision"] == "allow"


def test_m3_intent_blocks_no_authorization():
    r = camel_m3_intent_arm(_url("docs.example", PII), _view([]),
                            "research_summary", CLOCK)
    assert r["decision"] == "block"


def test_m3_intent_blocks_deny():
    deny = dict(ALLOW, auth_id="d1", effect="deny")
    r = camel_m3_intent_arm(_url("docs.example", PII),
                            _view([ALLOW, deny]), "research_summary",
                            CLOCK)
    assert r["decision"] == "block"


def test_m3_intent_blocks_wrong_purpose():
    r = camel_m3_intent_arm(_url("docs.example", PII), _view([ALLOW]),
                            "other_purpose", CLOCK)
    assert r["decision"] == "block"


def test_base_policy_descriptive_denies_protected():
    r = camel_base_policy_arm(_url("docs.example", PII),
                              _view([ALLOW]), "research_summary", CLOCK)
    assert r["decision"] == "block"


def test_empty_carrier_unaccounted_block():
    url = "http://docs.example/docs?d=" + base64.b64encode(b"{}").decode()
    r = camel_m3_intent_arm(url, _view([ALLOW]), "research_summary",
                            CLOCK)
    assert r["decision"] == "block" and r["unaccounted"]


def test_inspection_separate_from_policy():
    ins = inspect_call("http://x/y?d=%%%not-base64%%%", _view([]))
    assert ins["ok"]  # undecodable candidate is a coverage finding,
    # not an inspect failure; errors list tracks parse-level issues
