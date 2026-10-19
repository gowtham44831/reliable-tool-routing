"""Subset classification notes for the ToolRet benchmark.

Source: https://github.com/mangopy/tool-retrieval-benchmark (Apache-2.0 code
license; see docs/dataset.md for the full license/provenance discussion).
Dataset: https://huggingface.co/datasets/mangopy/ToolRet-Queries and
https://huggingface.co/datasets/mangopy/ToolRet-Tools.

ToolRet-Queries ships 35 "subsets" (one per upstream source benchmark it
was built from). Each query's ``labels`` list gives the tool(s) considered
relevant, but the dataset does not explicitly flag whether a query requires
a single tool, a choice between alternative tools, or a composition of
multiple distinct tools used together. We were not able to find a field in
the released parquet schema or dataset card that distinguishes this.

Per the task instructions, we only use subsets that are, based on the
*name and known purpose of their upstream source benchmark*, single
API/tool-lookup tasks (optionally with multiple valid alternatives), and we
exclude subsets whose upstream benchmark is explicitly about multi-step
tool/agent planning or program synthesis over several tools. This is a
heuristic, subset-level classification -- it has NOT been verified by
manually reading every query, so some residual multi-tool queries may
remain in the included subsets, and some includable single-tool queries may
have been excluded. This is a documented limitation (see docs/dataset.md).
"""
from __future__ import annotations

# Subsets whose upstream benchmark is a single API/tool lookup task
# (possibly with several alternative valid tools per query).
SINGLE_TOOL_SUBSETS: tuple[str, ...] = (
    "apibank",
    "apigen",
    "gorilla-huggingface",
    "gorilla-pytorch",
    "gorilla-tensor",
    "metatool",
    "reversechain",
    "rotbench",
    "tool-be-honest",
    "toolace",
    "toolalpaca",
    "toolbench",
    "toolbench-sam",
    "toolemu",
    "tooleyes",
    "toolink",
    "toollens",
    "ultratool",
)

# Subsets whose upstream benchmark is explicitly about multi-step tool use,
# tool composition/planning, or program synthesis over several tools, and
# are therefore excluded from this single-tool pilot.
MULTI_TOOL_SUBSETS: tuple[str, ...] = (
    "appbench",
    "autotools-food",
    "autotools-music",
    "autotools-weather",
    "craft-math-algebra",
    "craft-tabmwp",
    "craft-vqa",
    "gpt4tools",
    "gta",
    "mnms",
    "restgpt-spotify",
    "restgpt-tmdb",
    "t-eval-dialog",
    "t-eval-step",
    "taskbench-daily",
    "taskbench-huggingface",
    "taskbench-multimedia",
)

ALL_SUBSETS: tuple[str, ...] = SINGLE_TOOL_SUBSETS + MULTI_TOOL_SUBSETS

TOOLS_SUBSETS: tuple[str, ...] = ("code", "customized", "web")

QUERIES_REPO = "mangopy/ToolRet-Queries"
TOOLS_REPO = "mangopy/ToolRet-Tools"
