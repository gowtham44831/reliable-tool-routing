"""Adapter from downloaded ToolRet parquet files to the normalized schema.

Expects files previously downloaded with ``scripts/download_toolret.py``
into ``<raw_dir>/queries/<subset>.parquet`` and
``<raw_dir>/tools/<code|customized|web>.parquet``, plus a ``manifest.json``
with the resolved dataset revision and checksums.

Schema notes (see docs/dataset.md for the full writeup):

* ToolRet-Queries row: ``id`` (str), ``query`` (str), ``instruction`` (str),
  ``labels`` (str: JSON-encoded list of ``{"id", "doc", "relevance"}``),
  ``category`` (str: "web" | "code" | "customized", the ToolRet-Tools
  corpus this query's tools are drawn from).
* ToolRet-Tools row: ``id`` (str), ``documentation`` (str: JSON-encoded
  dict, schema varies a lot by upstream source -- sometimes
  ``name``/``description``/``parameters``, sometimes
  ``domain``/``framework``/``functionality``/``api_call``/``api_arguments``).
* Relevance values observed in sampled rows are binary (``1`` = relevant).
  We treat any value >= 1 as a known-valid label; anything else is dropped
  with a note (see ``load_toolret_requests`` return value).
"""
from __future__ import annotations

import json
from pathlib import Path

import pandas as pd

from tool_routing.data.schema import Request, Tool

TOOL_ID_PREFIX = "toolret_"


def _family_from_tool_id(raw_tool_id: str) -> str | None:
    if "_tool_" in raw_tool_id:
        return raw_tool_id.rsplit("_tool_", 1)[0]
    return None


def _parse_tool_doc(raw_tool_id: str, documentation: str) -> tuple[str, str, dict]:
    try:
        doc = json.loads(documentation)
    except (TypeError, json.JSONDecodeError):
        doc = None
    if not isinstance(doc, dict):
        return raw_tool_id, str(documentation)[:1000], {}

    name = doc.get("name") or doc.get("api_name")
    if not name:
        api_call = doc.get("api_call", "")
        name = api_call.split("(")[0].split(".")[-1].strip() if api_call else raw_tool_id

    description = doc.get("description") or doc.get("functionality") or ""
    if not description:
        description = json.dumps(doc, sort_keys=True)[:1000]

    parameters = doc.get("parameters")
    if not isinstance(parameters, dict):
        parameters = doc.get("api_arguments") if isinstance(doc.get("api_arguments"), dict) else {}

    return str(name), str(description), parameters


def load_toolret_tools(raw_dir: str | Path) -> dict[str, Tool]:
    """Load and combine all three ToolRet-Tools corpora (code/customized/web)."""
    raw_dir = Path(raw_dir)
    tools: dict[str, Tool] = {}
    for subset_file in sorted((raw_dir / "tools").glob("*.parquet")):
        df = pd.read_parquet(subset_file)
        for row in df.itertuples(index=False):
            raw_id = row.id
            name, description, parameters = _parse_tool_doc(raw_id, row.documentation)
            tool_id = f"{TOOL_ID_PREFIX}{raw_id}"
            tools[tool_id] = Tool(
                tool_id=tool_id,
                name=name,
                description=description,
                parameters=parameters,
                source_dataset=f"toolret_{subset_file.stem}",
                tool_family=_family_from_tool_id(raw_id),
                raw={"id": raw_id, "documentation": row.documentation},
            )
    return tools


def load_toolret_requests(
    raw_dir: str | Path, subsets: list[str]
) -> tuple[list[Request], list[str]]:
    """Load query subsets. Returns (requests, warnings)."""
    raw_dir = Path(raw_dir)
    requests: list[Request] = []
    warnings: list[str] = []
    for subset in subsets:
        path = raw_dir / "queries" / f"{subset}.parquet"
        if not path.exists():
            warnings.append(f"missing queries file for subset {subset!r}: {path}")
            continue
        df = pd.read_parquet(path)
        for row in df.itertuples(index=False):
            try:
                labels = json.loads(row.labels)
            except (TypeError, json.JSONDecodeError):
                warnings.append(f"{subset}/{row.id}: could not parse labels JSON")
                labels = []
            valid_ids = []
            for label in labels:
                if not isinstance(label, dict):
                    continue
                relevance = label.get("relevance", 0)
                try:
                    is_relevant = float(relevance) >= 1
                except (TypeError, ValueError):
                    is_relevant = False
                if is_relevant and label.get("id"):
                    valid_ids.append(f"{TOOL_ID_PREFIX}{label['id']}")
            requests.append(
                Request(
                    query_id=f"{TOOL_ID_PREFIX}{subset}_{row.id}",
                    query_text=str(row.query),
                    known_valid_tool_ids=tuple(dict.fromkeys(valid_ids)),
                    source_dataset=f"toolret_{subset}",
                    answerability_review_status="unreviewed",
                    raw={
                        "id": row.id,
                        "subset": subset,
                        "instruction": row.instruction,
                        "category": row.category,
                    },
                )
            )
    return requests, warnings
