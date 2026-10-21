"""Strict output validation for the v2 AI verifier. No network: validate()
is exercised directly on synthetic responses."""
import json

import pytest

from tool_routing.argverify.llm_v2 import in_scope_args, validate
from tool_routing.argverify.schema import FIXTURE_PATH, load_cases


@pytest.fixture(scope="module")
def cases():
    return {c.case_id: c.public_view() for c in load_cases(FIXTURE_PATH)}


def _resp(findings: dict, action="proceed") -> tuple[str, dict]:
    d = {"argument_findings": findings, "reasons": {}, "next_action": action}
    return json.dumps(d), d


def _complete(case, label="supported"):
    return {a: label for a in in_scope_args(case)}


def test_complete_response_accepted(cases):
    c = cases["TB-01a"]
    raw, parsed = _resp(_complete(c))
    findings, err = validate(c, raw, parsed)
    assert err is None and set(findings) == in_scope_args(c)


def test_absent_required_arg_is_in_scope(cases):
    c = cases["TB-05a"]  # passenger_dob absent from the call
    assert "passenger_dob" in in_scope_args(c)
    f = _complete(c); f["passenger_dob"] = "missing"
    assert validate(c, *_resp(f))[1] is None
    f["passenger_dob"] = "supported"
    assert "absent required" in validate(c, *_resp(f))[1]


def test_partial_rejected(cases):
    c = cases["TB-01a"]
    f = _complete(c); f.pop("cabin")
    assert "no finding for" in validate(c, *_resp(f))[1]


def test_unknown_arg_rejected(cases):
    c = cases["TB-01a"]
    f = _complete(c); f["seat_pref"] = "supported"
    assert "out-of-scope" in validate(c, *_resp(f))[1]


def test_malformed_value_rejected(cases):
    c = cases["TB-01a"]
    f = _complete(c); f["cabin"] = {"supported": True}
    assert "malformed" in validate(c, *_resp(f))[1]
    f["cabin"] = "ok"
    assert "malformed" in validate(c, *_resp(f))[1]


def test_duplicate_key_rejected(cases):
    c = cases["TB-01a"]
    f = _complete(c)
    body = ", ".join(f'"{k}": "{v}"' for k, v in f.items())
    raw = '{"argument_findings": {' + body + ', "cabin": "contradicted"}, "next_action": "proceed"}'
    parsed = json.loads(raw)
    assert "duplicate" in validate(c, raw, parsed)[1]


def test_empty_rejected(cases):
    c = cases["TB-01a"]
    assert validate(c, "", {})[1]
    assert validate(c, "{}", {"argument_findings": {}})[1]
