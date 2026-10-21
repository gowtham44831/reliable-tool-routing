"""Data model for argument-verification cases.

A Case is loaded as authored (includes ground truth). ``public_view``
returns the parts a verifier may see -- expected findings, label rules,
and the explanation stay hidden during evaluation.
"""
from __future__ import annotations

import json
from dataclasses import dataclass, field
from pathlib import Path
from typing import Any

FINDINGS = {"supported", "missing", "contradicted", "wrong_entity", "unresolved"}
ACTIONS = {"proceed", "retrieve", "clarify", "reject_proposed_call"}

# Source tiers for evidence precedence. "Newer overrides older" is NOT a
# blanket rule: precedence is tier-based, and within user turns the LATER
# turn wins only because each case states so in its label_rules.
TIER_ORDER = {"user_current": 5, "user_prior": 4, "tool_result": 3, "profile": 2, "schema_default": 1}


@dataclass
class SourceRef:
    """A claimed provenance pointer for one proposed argument.

    ``ref`` must resolve against the case: ``turn.<n>`` (conversation
    turn text), ``tool.<call_id>.<dotted path>`` (a prior tool result
    field), or ``schema.default.<arg>`` (documented schema default).
    """
    ref: str
    entity: str = "unknown"  # e.g. "traveler", "requester", "relative:Priya Nair", "unknown"
    tier: str = "tool_result"
    timestamp: str | None = None  # may be absent; verifier must not assume
    match: str | None = None    # literal span inside the resolved content the planner
                                # claims carries the value; verifier checks it exists


@dataclass
class ArgumentEvidence:
    argument_name: str
    proposed_value: Any
    source_references: list[SourceRef] = field(default_factory=list)
    transformation_or_default: str | None = None  # e.g. "schema_default", "round_to_int"


@dataclass
class Case:
    case_id: str
    pair_id: str
    context: dict  # current_time, requester, flying_person, persons, profile_authorized
    conversation: list[dict]
    tool_schema: dict
    prior_tool_results: list[dict]
    proposed_tool_call: dict  # {"tool": ..., "arguments": {...}}
    evidence_manifest: list[ArgumentEvidence]
    label_rules: list[str] = field(default_factory=list)
    expected_argument_findings: dict = field(default_factory=dict)
    expected_next_action: str = ""
    ground_truth_explanation: str = ""

    def public_view(self) -> "Case":
        return Case(
            case_id=self.case_id, pair_id=self.pair_id, context=self.context,
            conversation=self.conversation, tool_schema=self.tool_schema,
            prior_tool_results=self.prior_tool_results,
            proposed_tool_call=self.proposed_tool_call,
            evidence_manifest=self.evidence_manifest,
        )


def _src_ref(d: dict) -> SourceRef:
    return SourceRef(d["ref"], d.get("entity", "unknown"), d.get("tier", "tool_result"),
                     d.get("timestamp"), d.get("match"))


def load_cases(path: str | Path) -> list[Case]:
    doc = json.loads(Path(path).read_text())
    shared_schema = doc["shared_tool_schema"]
    cases = []
    for c in doc["cases"]:
        manifest = [
            ArgumentEvidence(
                m["argument_name"], m.get("proposed_value"),
                [_src_ref(r) for r in m.get("source_references", [])],
                m.get("transformation_or_default"),
            )
            for m in c.get("evidence_manifest", [])
        ]
        schema = c.get("tool_schema") or shared_schema
        cases.append(Case(
            case_id=c["case_id"], pair_id=c["pair_id"], context=c["context"],
            conversation=c["conversation"], tool_schema=schema,
            prior_tool_results=c["prior_tool_results"],
            proposed_tool_call=c["proposed_tool_call"],
            evidence_manifest=manifest,
            label_rules=c.get("label_rules", []),
            expected_argument_findings=c.get("expected_argument_findings", {}),
            expected_next_action=c["expected_next_action"],
            ground_truth_explanation=c.get("ground_truth_explanation", ""),
        ))
    return cases


FIXTURE_PATH = Path(__file__).parent / "fixtures" / "travel_cases.json"
