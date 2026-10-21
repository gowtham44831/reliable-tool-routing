"""Tests for the argument-verification dev prototype."""
import pytest

from tool_routing.argverify.evidence import extract_candidates, resolve_ref
from tool_routing.argverify.methods import (cross_argument_baseline,
                                            rule_baseline, schema_baseline)
from tool_routing.argverify.schema import FINDINGS, FIXTURE_PATH, load_cases


@pytest.fixture(scope="module")
def cases():
    return load_cases(FIXTURE_PATH)


def test_fixture_structure(cases):
    assert len(cases) == 20
    pairs = {}
    for c in cases:
        pairs.setdefault(c.pair_id, []).append(c)
    assert len(pairs) == 10
    # within a pair the proposed call is identical
    for pid, members in pairs.items():
        assert len(members) == 2
        assert members[0].proposed_tool_call == members[1].proposed_tool_call, pid
        assert members[0].expected_next_action != "" and members[1].expected_next_action
    # every expected finding is a legal label
    for c in cases:
        assert set(c.expected_argument_findings.values()) <= FINDINGS


def test_public_view_hides_labels(cases):
    pub = cases[0].public_view()
    assert pub.expected_next_action == ""
    assert pub.expected_argument_findings == {}
    assert pub.ground_truth_explanation == ""
    assert pub.evidence_manifest  # evidence pointers are visible


def test_source_refs_resolve(cases):
    """Refs must be well-formed and point at a real turn or a real tool
    call -- field paths MAY dangle (that absence is what 'missing'
    evidence means; TB-04b exercises exactly that)."""
    import re
    for c in cases:
        turn_ids = {t["turn"] for t in c.conversation}
        call_ids = {t["call_id"] for t in c.prior_tool_results}
        for ev in c.evidence_manifest:
            for s in ev.source_references:
                r = resolve_ref(c, s)
                if re.fullmatch(r"turn\.\d+", s.ref):
                    assert int(s.ref.split(".")[1]) in turn_ids, f"{c.case_id}:{s.ref}"
                elif s.ref.startswith("tool."):
                    assert r.exists or r.prospective or s.ref.split(".")[1] in call_ids, \
                        f"{c.case_id}:{s.ref} points at no real tool call"
                else:
                    assert r.exists or s.ref.startswith("schema."), f"{c.case_id}:{s.ref}"


def test_match_spans_verified(cases):
    for c in cases:
        for ev in c.evidence_manifest:
            for s in ev.source_references:
                if s.match is not None:
                    r = resolve_ref(c, s)
                    assert r.exists and str(s.match) in str(r.content), \
                        f"{c.case_id}:{ev.argument_name} match={s.match!r} not in {s.ref}"


def test_schema_baseline_blindness(cases):
    """The schema baseline proceeds on every schema-valid call — including
    the unsafe ones; that blindness is the point of the comparison."""
    res = [schema_baseline(c.public_view()) for c in cases]
    for c, r in zip(cases, res):
        assert r["action"] in {"proceed", "reject_proposed_call", "clarify", "retrieve"}
    # TB-05 cases lack a required field -> schema catches it
    b = {c.case_id: r for c, r in zip(cases, res)}
    assert b["TB-05a"]["findings"]["passenger_dob"] == "missing"
    # but wrong-person data is schema-valid -> allowed (the failure mode)
    assert b["TB-01b"]["action"] == "proceed"


def test_rule_baseline_actions(cases):
    """On this dev fixture the deterministic rule matches all 20 actions.
    Argument-level: everything except TB-08b flight_id (needs cross-arg
    consistency: the flight exists only on the superseded date)."""
    for c in cases:
        r = rule_baseline(c.public_view())
        assert r["action"] == c.expected_next_action, c.case_id
    b = {c.case_id: rule_baseline(c.public_view()) for c in cases}
    assert b["TB-01b"]["findings"]["traveler_name"] == "wrong_entity"
    assert b["TB-03b"]["findings"]["cabin"] == "contradicted"
    assert b["TB-04b"]["findings"]["meal"] == "missing"
    assert b["TB-07b"]["findings"]["flight_id"] == "unresolved"
    assert b["TB-05a"]["action"] == "retrieve" and b["TB-05b"]["action"] == "clarify"


def test_cross_argument_baseline(cases):
    """Cross-arg checks see what slot-level rules cannot: TB-08b's
    flight_id resolves to a real flight record, but that flight only
    exists on the superseded date -> contradicted."""
    b = {c.case_id: cross_argument_baseline(c.public_view()) for c in cases}
    assert b["TB-08b"]["findings"]["flight_id"] == "contradicted"
    # the consistent member of the pair stays supported
    assert b["TB-08a"]["findings"]["flight_id"] == "supported"
    # wrong-person case still caught via traveler-vs-record identity
    assert b["TB-01b"]["findings"]["traveler_name"] == "wrong_entity"
    for c in cases:
        assert b[c.case_id]["action"] == c.expected_next_action, c.case_id


def test_last_mention_enum(cases):
    c = next(c for c in cases if c.case_id == "TB-03a")
    assert extract_candidates(c.conversation[0]["text"], "enum:cabin", c)[-1] == "economy"
    c = next(c for c in cases if c.case_id == "TB-03b")
    assert extract_candidates(c.conversation[0]["text"], "enum:cabin", c)[-1] == "business"


def test_missing_ref_is_not_evidence(cases):
    c = next(c for c in cases if c.case_id == "TB-04b")
    r = resolve_ref(c, c.evidence_manifest[0].source_references[0])
    assert not r.exists  # profile has no meal_preference field
