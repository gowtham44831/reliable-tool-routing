"""Local BM25 baseline retriever (rank_bm25, deterministic tokenization)."""
from __future__ import annotations

import hashlib
import re
import time
from collections import OrderedDict
from dataclasses import dataclass

from rank_bm25 import BM25Okapi

from tool_routing.data.schema import Tool
from tool_routing.retrieval.base import BaseRetriever, RankedResult

_TOKEN_RE = re.compile(r"[a-z0-9]+")


def _content_hash(tools: list[Tool]) -> str:
    h = hashlib.sha256()
    for t in sorted(tools, key=lambda x: x.tool_id):
        h.update(t.tool_id.encode())
        h.update(b"\x00")
        h.update(t.serialized_text().encode())
        h.update(b"\x01")
    return h.hexdigest()


def tokenize(text: str) -> list[str]:
    """Deterministic lowercase alphanumeric tokenizer, no stemming/stopwords.

    Kept intentionally simple and dependency-free so tokenization is 100%
    reproducible across machines/python versions.
    """
    return _TOKEN_RE.findall(text.lower())


@dataclass
class _CatalogIndex:
    tool_ids: tuple[str, ...]
    bm25: BM25Okapi


class _LRUCache(OrderedDict):
    """Bounded cache so memory doesn't grow unbounded across thousands of
    distinct (mostly near-identical) per-query catalogs in a long pilot
    run."""

    def __init__(self, maxsize: int = 32):
        super().__init__()
        self.maxsize = maxsize

    def __setitem__(self, key, value):
        if key in self:
            super().move_to_end(key)
        super().__setitem__(key, value)
        if len(self) > self.maxsize:
            super().popitem(last=False)


class BM25Retriever(BaseRetriever):
    """BM25 index is cached by tool-content hash (not just catalog_id), so
    many catalog_ids that happen to contain the exact same tool set (e.g.
    the unmodified "original" catalog shared by every query in a source
    subset) only get indexed once.
    """

    name = "bm25"

    def __init__(self) -> None:
        self._indexes_by_content: _LRUCache = _LRUCache(maxsize=32)
        self._catalog_to_content: dict[str, str] = {}

    def prepare_catalog(self, catalog_id: str, tools: list[Tool]) -> float:
        content_key = _content_hash(tools)
        self._catalog_to_content[catalog_id] = content_key
        if content_key in self._indexes_by_content:
            return 0.0
        start = time.perf_counter()
        tool_ids = tuple(t.tool_id for t in tools)
        corpus = [tokenize(t.serialized_text()) for t in tools]
        bm25 = BM25Okapi(corpus) if corpus else None
        elapsed = time.perf_counter() - start
        self._indexes_by_content[content_key] = _CatalogIndex(tool_ids=tool_ids, bm25=bm25)
        return elapsed

    def rank(self, catalog_id: str, query_text: str, top_k: int = 10) -> RankedResult:
        content_key = self._catalog_to_content.get(catalog_id)
        index = self._indexes_by_content.get(content_key) if content_key else None
        if index is None or index.bm25 is None or not index.tool_ids:
            return RankedResult((), (), 0.0, 0.0)

        prep_start = time.perf_counter()
        query_tokens = tokenize(query_text)
        prep_seconds = time.perf_counter() - prep_start

        retr_start = time.perf_counter()
        scores = index.bm25.get_scores(query_tokens)
        order = sorted(range(len(scores)), key=lambda i: scores[i], reverse=True)[:top_k]
        retr_seconds = time.perf_counter() - retr_start

        ranked_ids = tuple(index.tool_ids[i] for i in order)
        ranked_scores = tuple(float(scores[i]) for i in order)
        return RankedResult(ranked_ids, ranked_scores, prep_seconds, retr_seconds)
