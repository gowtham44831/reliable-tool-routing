"""Validation checks for normalized Tool/Request collections.

These checks are intentionally conservative: they raise/record issues
rather than silently repairing data, so that problems in a raw dataset are
visible instead of masked.
"""
from __future__ import annotations

from collections import Counter
from dataclasses import dataclass, field

from tool_routing.data.schema import Request, Tool


@dataclass
class ValidationReport:
    n_tools: int = 0
    n_requests: int = 0
    duplicate_tool_ids: list[str] = field(default_factory=list)
    duplicate_query_ids: list[str] = field(default_factory=list)
    tools_missing_fields: list[str] = field(default_factory=list)
    requests_missing_fields: list[str] = field(default_factory=list)
    dangling_tool_refs: dict[str, list[str]] = field(default_factory=dict)
    requests_without_any_valid_tool: list[str] = field(default_factory=list)
    conflicting_labels: dict[str, list[str]] = field(default_factory=dict)

    @property
    def is_clean(self) -> bool:
        return not (
            self.duplicate_tool_ids
            or self.duplicate_query_ids
            or self.tools_missing_fields
            or self.requests_missing_fields
            or self.dangling_tool_refs
            or self.conflicting_labels
        )

    def summary(self) -> str:
        lines = [
            f"tools={self.n_tools} requests={self.n_requests}",
            f"duplicate_tool_ids={len(self.duplicate_tool_ids)}",
            f"duplicate_query_ids={len(self.duplicate_query_ids)}",
            f"tools_missing_fields={len(self.tools_missing_fields)}",
            f"requests_missing_fields={len(self.requests_missing_fields)}",
            f"dangling_tool_refs={len(self.dangling_tool_refs)}",
            f"requests_without_any_valid_tool={len(self.requests_without_any_valid_tool)}",
            f"conflicting_labels={len(self.conflicting_labels)}",
        ]
        return "\n".join(lines)


def validate_tools(tools: list[Tool]) -> tuple[list[str], list[str]]:
    """Return (duplicate_ids, ids_with_missing_fields)."""
    counts = Counter(t.tool_id for t in tools)
    duplicates = sorted(tid for tid, c in counts.items() if c > 1)
    missing = sorted(
        t.tool_id
        for t in tools
        if not t.tool_id or not t.name.strip() or not t.description.strip()
    )
    return duplicates, missing


def validate_requests(
    requests: list[Request], valid_tool_ids: set[str]
) -> ValidationReport:
    report = ValidationReport()
    report.n_requests = len(requests)

    counts = Counter(r.query_id for r in requests)
    report.duplicate_query_ids = sorted(qid for qid, c in counts.items() if c > 1)

    report.requests_missing_fields = sorted(
        r.query_id
        for r in requests
        if not r.query_id or not r.query_text.strip()
    )

    seen_labels: dict[str, set[str]] = {}
    for r in requests:
        dangling = sorted(
            tid for tid in r.known_valid_tool_ids if tid not in valid_tool_ids
        )
        if dangling:
            report.dangling_tool_refs[r.query_id] = dangling
        if not r.known_valid_tool_ids:
            report.requests_without_any_valid_tool.append(r.query_id)
        # Conflicting labels: same query_id appears more than once with a
        # different set of known-valid tool ids.
        label_set = frozenset(r.known_valid_tool_ids)
        if r.query_id in seen_labels:
            if label_set not in seen_labels[r.query_id]:
                report.conflicting_labels.setdefault(r.query_id, []).append(
                    ",".join(sorted(label_set))
                )
            seen_labels[r.query_id].add(label_set)
        else:
            seen_labels[r.query_id] = {label_set}

    report.requests_without_any_valid_tool.sort()
    return report


def validate_dataset(tools: list[Tool], requests: list[Request]) -> ValidationReport:
    dup_tools, missing_tools = validate_tools(tools)
    valid_tool_ids = {t.tool_id for t in tools}
    report = validate_requests(requests, valid_tool_ids)
    report.n_tools = len(tools)
    report.duplicate_tool_ids = dup_tools
    report.tools_missing_fields = missing_tools
    return report
