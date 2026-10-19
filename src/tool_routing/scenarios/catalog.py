"""Controlled catalog scenario generation.

For each query we build three reproducible catalog manifests, all derived
from the SAME base tool pool so that every compared retrieval method sees
identical catalogs:

* ``original``       -- the query's normal eligible tool pool.
* ``known_removed``  -- ``original`` minus every annotated known-valid tool
                         ("known-positive removal"). This does NOT imply the
                         request is truly unanswerable: unannotated valid
                         tools may remain (see docs/dataset.md).
* ``distractors_added`` -- ``original`` plus N tools drawn from a disjoint,
                         held-out pool, ranked by lexical similarity to the
                         query text (BM25 over the held-out pool). These
                         added tools are not assumed invalid for the query;
                         that must be checked by review (docs/review_workflow.md).

No tool is ever executed or called while building these manifests.
"""
from __future__ import annotations

from dataclasses import dataclass, field

from tool_routing.data.schema import Request, Tool
from tool_routing.retrieval.bm25 import BM25Retriever

ORIGINAL = "original"
KNOWN_REMOVED = "known_removed"
DISTRACTORS_ADDED = "distractors_added"
SCENARIOS = (ORIGINAL, KNOWN_REMOVED, DISTRACTORS_ADDED)


@dataclass(frozen=True)
class CatalogManifest:
    catalog_id: str
    query_id: str
    scenario: str
    tool_ids: tuple[str, ...]
    added_distractor_ids: tuple[str, ...] = field(default_factory=tuple)
    removed_known_valid_ids: tuple[str, ...] = field(default_factory=tuple)

    def to_dict(self) -> dict:
        return {
            "catalog_id": self.catalog_id,
            "query_id": self.query_id,
            "scenario": self.scenario,
            "tool_ids": list(self.tool_ids),
            "added_distractor_ids": list(self.added_distractor_ids),
            "removed_known_valid_ids": list(self.removed_known_valid_ids),
        }


class DistractorPicker:
    """Picks semantically-similar distractors from a held-out tool pool.

    Similarity is approximated with BM25 lexical overlap between the query
    text and held-out tool descriptions. This is a cheap, deterministic
    heuristic, not a guarantee of true semantic similarity; the task
    instructions require picking "distinct, semantically similar" tools,
    and lexical overlap with the request is a reasonable, auditable proxy
    given this milestone's scope (see docs/dataset.md limitations).
    """

    def __init__(self, held_out_tools: list[Tool]):
        self._tools_by_id = {t.tool_id: t for t in held_out_tools}
        self._retriever = BM25Retriever()
        self._catalog_id = "__held_out_pool__"
        self._retriever.prepare_catalog(self._catalog_id, held_out_tools)

    def pick(self, query_text: str, n: int, exclude_ids: set[str]) -> list[str]:
        if not self._tools_by_id:
            return []
        result = self._retriever.rank(self._catalog_id, query_text, top_k=n + len(exclude_ids))
        picked = [tid for tid in result.tool_ids if tid not in exclude_ids]
        return picked[:n]


def build_catalog_scenarios(
    request: Request,
    original_pool_ids: list[str],
    distractor_picker: DistractorPicker | None,
    n_distractors: int = 3,
) -> dict[str, CatalogManifest]:
    """Build the three catalog manifests for a single query.

    ``original_pool_ids`` must already be deduplicated tool IDs that exist
    in the catalog's tool index; callers are responsible for grouping (e.g.
    "all tools from the same source subset").
    """
    original_ids = tuple(sorted(set(original_pool_ids)))

    known_valid = set(request.known_valid_tool_ids)
    removed_ids = tuple(sorted(tid for tid in original_ids if tid not in known_valid))
    actually_removed = tuple(sorted(set(original_ids) & known_valid))

    added_ids: tuple[str, ...] = original_ids
    distractors: tuple[str, ...] = ()
    if distractor_picker is not None and n_distractors > 0:
        exclude = set(original_ids)
        picked = distractor_picker.pick(request.query_text, n_distractors, exclude)
        distractors = tuple(picked)
        added_ids = tuple(sorted(set(original_ids) | set(distractors)))

    def cid(scenario: str) -> str:
        return f"{request.query_id}::{scenario}"

    return {
        ORIGINAL: CatalogManifest(cid(ORIGINAL), request.query_id, ORIGINAL, original_ids),
        KNOWN_REMOVED: CatalogManifest(
            cid(KNOWN_REMOVED),
            request.query_id,
            KNOWN_REMOVED,
            removed_ids,
            removed_known_valid_ids=actually_removed,
        ),
        DISTRACTORS_ADDED: CatalogManifest(
            cid(DISTRACTORS_ADDED),
            request.query_id,
            DISTRACTORS_ADDED,
            added_ids,
            added_distractor_ids=distractors,
        ),
    }
