"""Resolve evidence source references and extract candidate values.

A source reference is a pointer into the case, never a bare assertion:
- ``turn.<n>``            -> that conversation turn's text
- ``tool.<call_id>.<dotted.path>`` -> a field inside a prior tool result's output
- ``tool.<name>.*`` where name has no returned result -> prospective source
  (a lookup that COULD supply the value); resolves to None with exists=False
- ``schema.default.<arg>`` -> the documented schema default

Extraction is deterministic: per-argument ``hint`` declared in the tool
contract (NOT per case): date, time, person_name, airport_code, enum:<arg>,
flight_id, integer.
"""
from __future__ import annotations

import re
from dataclasses import dataclass
from typing import Any

from .schema import Case, SourceRef


@dataclass
class Resolved:
    ref: str
    exists: bool          # the pointer resolved to actual content
    content: Any          # raw resolved content (text / field value / list)
    prospective: bool     # names a source that has NOT been called yet
    entity: str
    tier: str
    timestamp: str | None


def resolve_ref(case: Case, sref: SourceRef) -> Resolved:
    ref = sref.ref
    m = re.fullmatch(r"turn\.(\d+)", ref)
    if m:
        n = int(m.group(1))
        for t in case.conversation:
            if t["turn"] == n:
                return Resolved(ref, True, t["text"], False, sref.entity, sref.tier, sref.timestamp)
        return Resolved(ref, False, None, False, sref.entity, sref.tier, sref.timestamp)
    m = re.fullmatch(r"tool\.([A-Za-z_0-9]+)\.(.+)", ref)
    if m:
        key, path = m.group(1), m.group(2)
        for tr in case.prior_tool_results:
            if tr["call_id"] == key or tr["tool"] == key:
                node: Any = tr.get("output", {})
                if path == "output":
                    return Resolved(ref, True, node, False, sref.entity, sref.tier,
                                    sref.timestamp or tr.get("timestamp"))
                if path.startswith("output."):
                    for part in path.split(".")[1:]:
                        if isinstance(node, dict) and part in node:
                            node = node[part]
                        else:
                            return Resolved(ref, False, None, False, sref.entity, sref.tier, sref.timestamp)
                    return Resolved(ref, True, node, False, sref.entity, sref.tier,
                                    sref.timestamp or tr.get("timestamp"))
        # tool result id not present in prior results -> prospective source
        return Resolved(ref, False, None, True, sref.entity, sref.tier, sref.timestamp)
    m = re.fullmatch(r"schema\.default\.(.+)", ref)
    if m:
        p = case.tool_schema["parameters"].get(m.group(1), {})
        return Resolved(ref, "default" in p, p.get("default"), False, sref.entity, sref.tier, sref.timestamp)
    return Resolved(ref, False, None, False, sref.entity, sref.tier, sref.timestamp)


_DATE = re.compile(r"\b\d{4}-\d{2}-\d{2}\b")
_TIME = re.compile(r"\b\d{2}:\d{2}\b")
_AIRPORT = re.compile(r"\b[A-Z]{3}\b")
_FLIGHT = re.compile(r"\bFL-\d+\b")
_INT = re.compile(r"\b\d+\b")


def _walk_values(content: Any) -> list[str]:
    """Flatten resolved content into candidate literal values."""
    out: list[str] = []
    if isinstance(content, list):
        for x in content:
            out += _walk_values(x)
    elif isinstance(content, dict):
        for v in content.values():
            out += _walk_values(v)
    elif content is not None:
        out.append(str(content))
    return out


def extract_candidates(content: Any, hint: str | None, case: Case,
                       arg_name: str | None = None) -> list[str]:
    """Deterministic candidate-value extraction from resolved content.

    Conversation text is regex-scanned by hint. Structured content (dicts,
    lists) is SLOT-KEYED: values are collected only under dict keys matching
    the argument name or its aliases, so a list of flight options yields
    the candidate values for that slot (e.g. three departure times).
    """
    if content is None:
        return []
    if not isinstance(content, str):
        vals = _slot_values(content, arg_name)
        if not vals:
            vals = _walk_values(content)
        return vals
    text = content
    if hint == "date":
        return _DATE.findall(text)
    if hint == "time":
        return _TIME.findall(text)
    if hint == "flight_id":
        return _FLIGHT.findall(text)
    if hint == "integer":
        return _INT.findall(text)
    if hint == "airport_code":
        return _AIRPORT.findall(text)
    if hint == "person_name":
        return [p["name"] for p in case.context.get("persons", []) if p["name"] in text]
    if hint and hint.startswith("enum:"):
        arg = hint.split(":", 1)[1]
        enum = case.tool_schema["parameters"].get(arg, {}).get("enum", [])
        hits = [(text.lower().rfind(v), v) for v in enum if v in text.lower()]
        return [v for _, v in sorted(hits)]  # text-position order, last = operative
    return [content]


ALIASES = {
    "origin_airport": ["origin"], "destination_airport": ["destination"],
    "departure_time": ["departure_time", "dep_time", "time"],
    "flight_id": ["flight_id", "id"], "date": ["date"],
    "passenger_dob": ["dob", "birth", "date_of_birth"],
    "traveler_name": ["full_name", "name", "passenger"],
    "cabin": ["cabin", "class"], "num_bags": ["bags", "num_bags"],
    "meal": ["meal_preference", "meal"],
}


def _slot_values(content: Any, arg_name: str | None) -> list[str]:
    keys = {arg_name, *ALIASES.get(arg_name, ())} if arg_name else set()
    out: list[str] = []

    def walk(node):
        if isinstance(node, dict):
            for k, v in node.items():
                if k in keys and not isinstance(v, (dict, list)):
                    out.append(str(v))
                elif isinstance(v, (dict, list)):
                    walk(v)
        elif isinstance(node, list):
            for x in node:
                walk(x)

    if keys:
        walk(content)
    return out


def norm(v: Any) -> str:
    return re.sub(r"\s+", " ", str(v)).strip().lower()
