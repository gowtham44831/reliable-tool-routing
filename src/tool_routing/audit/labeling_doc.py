"""Render bounded-catalog review items as a blind Markdown labeling form.

"Blind" means the document contains ONLY what a human needs to judge:
the request text and every tool's ID, full description, and parameter
schema. It must NOT contain model rankings, scores, the annotated
(original) labels, scenario names, or the construction condition
(kept/removed) -- the item/tools CSVs and this renderer never emit them,
and the answer-key file is never read.

Tool order is re-shuffled deterministically per item (seed + item index)
so the presentation order carries no information from catalog
construction. Tool IDs are preserved verbatim -- they are needed to
write judgments and to join results back later.
"""
from __future__ import annotations

import csv
import json
import random
from dataclasses import dataclass
from pathlib import Path

from tool_routing.data.schema import Tool

ANSWER_TEMPLATE = """\
**a. Individually satisfying tool IDs** — every tool that, ON ITS OWN,
could fully satisfy the request (repeated calls to the same tool count
as the same single tool). `;`-separated IDs, or "none":

> _(blank)_

**b. Required tool combinations** — groups of 2+ tools that must be used
TOGETHER (write `id1+id2`, separate alternative groups with `|`). Fill
this only if no single tool in a is sufficient; otherwise "none":

> _(blank)_

**c. Answerability** — answerable / no_suitable_tool /
insufficient_information:

> _(blank)_

**d. Explanation** (and your reviewer ID):

> _(blank)_
"""


@dataclass(frozen=True)
class LabelingItem:
    item_id: str
    query_text: str
    tool_ids: tuple[str, ...]


def load_items_and_catalogs(review_dir: str | Path) -> tuple[list[LabelingItem], dict[str, list[str]]]:
    """Read the BLIND CSVs only (items + tools). Never reads the key file."""
    review_dir = Path(review_dir)
    items: list[LabelingItem] = []
    tools_by_item: dict[str, list[str]] = {}
    with open(review_dir / "bounded_catalog_review_items.csv", newline="", encoding="utf-8") as f:
        for row in csv.DictReader(f):
            items.append(LabelingItem(row["item_id"], row["query_text"], ()))
    with open(review_dir / "bounded_catalog_review_tools.csv", newline="", encoding="utf-8") as f:
        for row in csv.DictReader(f):
            tools_by_item.setdefault(row["item_id"], []).append(row["tool_id"])
    items = [LabelingItem(i.item_id, i.query_text, tuple(tools_by_item[i.item_id])) for i in items]
    items.sort(key=lambda i: i.item_id)
    return items, tools_by_item


def render_labeling_doc(
    items: list[LabelingItem],
    tools_by_id: dict[str, Tool],
    title: str = "Bounded-catalog labeling",
    seed: int = 11,
    exposure_note: str | None = None,
) -> str:
    """Markdown form for ``items`` (already the desired subset/order)."""
    lines = [
        f"# {title}",
        "",
        "## Instructions",
        "",
        "- Judge from the request text and the tool documentation below. "
        "Nothing here shows model output, scores, or any prior labels.",
        "- **Field a lists alternatives.** A request answered by any one "
        "of several tools is still single-tool -- list ALL tools that are "
        "each independently sufficient. Multiple IDs in a do NOT make the "
        "request multi-tool.",
        "- **Repeated calls are allowed.** If the request needs the same "
        "tool called more than once (e.g. 'for Jan 15 and also Feb 20'), "
        "that is still a single-tool request.",
        "- **Field b is only for genuinely joint work**: no single tool "
        "covers all parts, but a set of 2+ tools does together. A request "
        "with two subquestions is NOT multi-tool if one tool can answer "
        "both.",
        "- **Distinguish capability from arguments.** Judge whether the "
        "tool *can* satisfy the request given what the request actually "
        "supplies. If a tool requires an argument the request does not "
        "provide (e.g. no recipient address is given anywhere), say so "
        "in d -- it may make that tool unusable, not the whole request "
        "unanswerable.",
        "- **c**: `answerable` = at least one entry in a or b; "
        "`no_suitable_tool` = you read every tool and none fits; "
        "`insufficient_information` = the request or the tool docs are too "
        "vague to decide.",
        "- Work through every listed tool before deciding c.",
        "- Copy each item's answers into "
        "`responses/bounded_round<N>_responses.csv` (one row per item) "
        "and set `human_reviewed` to `yes` there -- only once the row is "
        "complete.",
        "",
    ]
    if exposure_note:
        lines += ["**Reviewer exposure note:** " + exposure_note, ""]
    for idx, item in enumerate(items):
        rng = random.Random(f"{seed}:{item.item_id}")
        order = list(item.tool_ids)
        rng.shuffle(order)
        lines += [f"## Item {item.item_id}", "", "**Request:**", "", f"> {item.query_text}", ""]
        lines.append(f"**Catalog ({len(order)} tools):**")
        lines.append("")
        for slot, tid in enumerate(order, start=1):
            t = tools_by_id.get(tid)
            if t is None:
                lines += [f"### {slot}. `{tid}`", "", "_tool record missing_", ""]
                continue
            params = json.dumps(t.parameters, sort_keys=True, ensure_ascii=False, default=str)
            if params == "{}":
                params = "(no parameter schema recorded)"
            lines += [
                f"### {slot}. `{tid}` — {t.name}",
                "",
                t.description or "(no description)",
                "",
                f"Schema: `{params}`",
                "",
            ]
        lines.append(ANSWER_TEMPLATE)
        lines.append("---")
        lines.append("")
    return "\n".join(lines)


def blank_response_rows(items: list[LabelingItem]) -> list[dict]:
    return [{"item_id": i.item_id, "n_tools_shown": len(i.tool_ids), **{f: "" for f in RESPONSE_FIELDS}}
            for i in items]


RESPONSE_FIELDS = [
    "individually_satisfying_tool_ids",  # ';'-sep alternatives, each sufficient alone (or 'none')
    "required_tool_combinations",  # 'id1+id2 | id3+id4' groups of 2+ needed jointly (or 'none')
    "answerability",  # answerable | no_suitable_tool | insufficient_information
    "explanation",
    "reviewer_id",
    "human_reviewed",  # 'yes' only when the row is complete
]

ALLOWED_ANSWERABILITY = {"answerable", "no_suitable_tool", "insufficient_information"}


def parse_combinations(text: str) -> list[list[str]] | None:
    """Parse ``id1+id2 | id3+id4`` into groups. ``none``/blank -> [].
    Returns None on malformed input."""
    text = text.strip()
    if not text or text.lower() == "none":
        return []
    groups = []
    for g in text.split("|"):
        ids = [x.strip() for x in g.strip().split("+") if x.strip()]
        if len(ids) < 2:
            return None
        groups.append(ids)
    return groups


def parse_id_list(text: str) -> list[str] | None:
    """';'-separated list or 'none'. Returns [] for none/blank."""
    text = text.strip()
    if not text or text.lower() == "none":
        return []
    return [x.strip() for x in text.split(";") if x.strip()]


def validate_responses(responses_csv: str | Path, items: list[LabelingItem]) -> dict:
    """Check completeness and consistency of a submitted responses CSV.

    Completeness requires: reviewed=yes, answerability in the allowed set,
    individually_satisfying_tool_ids filled ('none' allowed),
    required_tool_combinations filled ('none' allowed), non-empty
    explanation and reviewer_id. Multiple individually-satisfying IDs are
    VALID (they are alternatives; the request stays single-tool).
    Consistency flags (issues, not auto-fails): combinations with 1 member,
    IDs outside the item's catalog, answerability='answerable' with no
    satisfying entry anywhere, no_suitable_tool/insufficient_information
    with a satisfying entry present, a tool listed both as individually
    satisfying and inside a required combination.
    """
    catalog = {i.item_id: set(i.tool_ids) for i in items}
    rows = list(csv.DictReader(open(responses_csv, newline="", encoding="utf-8")))
    issues: list[str] = []
    n_complete = 0
    seen_ids = set()
    for row in rows:
        iid = row.get("item_id", "?")
        seen_ids.add(iid)
        probs: list[str] = []
        if iid not in catalog:
            probs.append("unknown item_id")
        ans = (row.get("answerability") or "").strip()
        indiv_raw = row.get("individually_satisfying_tool_ids") or ""
        combo_raw = row.get("required_tool_combinations") or ""
        indiv = parse_id_list(indiv_raw)
        combos = parse_combinations(combo_raw)
        d = (row.get("explanation") or "").strip()
        if (row.get("human_reviewed") or "").strip() != "yes":
            probs.append("human_reviewed != yes")
        if not (row.get("reviewer_id") or "").strip():
            probs.append("reviewer_id empty")
        if ans not in ALLOWED_ANSWERABILITY:
            probs.append(f"answerability not in {sorted(ALLOWED_ANSWERABILITY)}: {ans!r}")
        if not indiv_raw.strip():
            probs.append("individually_satisfying_tool_ids empty (use 'none')")
        if not combo_raw.strip():
            probs.append("required_tool_combinations empty (use 'none')")
        if not d:
            probs.append("explanation empty")
        if indiv:
            bad = [t for t in indiv if iid in catalog and t not in catalog[iid]]
            if bad:
                probs.append(f"satisfying IDs not in this item's catalog: {bad}")
        if combos is None:
            probs.append("required_tool_combinations malformed (need 'id1+id2' groups of 2+, '|'-separated)")
        else:
            for g in combos:
                bad = [t for t in g if iid in catalog and t not in catalog[iid]]
                if bad:
                    probs.append(f"combination IDs not in this item's catalog: {bad}")
                both = set(g) & set(indiv or [])
                if both:
                    probs.append(f"tools listed both as individually satisfying and in a combination: {sorted(both)}")
        has_satisfying = bool(indiv) or bool(combos)
        if ans == "answerable" and not has_satisfying:
            probs.append("answerable but no satisfying IDs or combinations given")
        if ans in ("no_suitable_tool", "insufficient_information") and has_satisfying:
            probs.append(f"{ans} contradicts non-empty satisfying/combination fields")
        if probs:
            issues.append(f"{iid}: " + "; ".join(probs))
        else:
            n_complete += 1
    for i in items:
        if i.item_id not in seen_ids:
            issues.append(f"{i.item_id}: no response row")
    return {
        "n_rows": len(rows),
        "n_items_expected": len(items),
        "n_complete_and_consistent": n_complete,
        "issues": issues,
    }


def export_response_template(items: list[LabelingItem], out_csv: str | Path) -> None:
    fields = ["item_id", "n_tools_shown", *RESPONSE_FIELDS]
    out_csv = Path(out_csv)
    out_csv.parent.mkdir(parents=True, exist_ok=True)
    with open(out_csv, "w", newline="", encoding="utf-8") as f:
        w = csv.DictWriter(f, fieldnames=fields)
        w.writeheader()
        w.writerows(blank_response_rows(items))
