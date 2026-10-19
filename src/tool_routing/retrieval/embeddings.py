"""Frozen sentence-embedding baseline retriever.

Uses a configurable pretrained sentence-transformer (no fine-tuning),
normalized embeddings, and exact cosine similarity (dot product of unit
vectors). Tool embeddings are cached **per tool** (keyed by the model's
resolved revision and a hash of that tool's own serialized content), not
per catalog -- many catalogs in this project share most of their tools
(e.g. every query in a source subset shares the same "original" pool, and
"known_removed"/"distractors_added" variants only change a handful of
tools), so per-tool caching avoids re-encoding the same tool text
thousands of times. The cache is persisted to disk once via ``save_cache``.

Raw cosine similarity scores are NOT probabilities.
"""
from __future__ import annotations

import hashlib
import json
import time
from collections import OrderedDict
from dataclasses import dataclass
from pathlib import Path

import numpy as np

from tool_routing.data.schema import Tool
from tool_routing.retrieval.base import BaseRetriever, RankedResult

DEFAULT_MODEL = "sentence-transformers/all-MiniLM-L6-v2"


def _tool_content_key(tool: Tool, doc_prefix: str) -> str:
    h = hashlib.sha256()
    h.update(tool.tool_id.encode())
    h.update(b"\x00")
    h.update((doc_prefix + tool.serialized_text()).encode())
    return h.hexdigest()


@dataclass
class _CatalogIndex:
    tool_ids: tuple[str, ...]
    embeddings: np.ndarray | None  # (n_tools, dim), L2-normalized


class _LRUCache(OrderedDict):
    """Bounded cache: each assembled catalog matrix can be several MB and
    the pipeline builds one per (query, scenario), so we only keep the
    most-recently-used few in memory instead of retaining every catalog
    ever seen (per-tool vectors, the expensive-to-compute part, are cached
    separately and kept in full)."""

    def __init__(self, maxsize: int = 16):
        super().__init__()
        self.maxsize = maxsize

    def __setitem__(self, key, value):
        if key in self:
            super().move_to_end(key)
        super().__setitem__(key, value)
        if len(self) > self.maxsize:
            super().popitem(last=False)


class EmbeddingRetriever(BaseRetriever):
    name = "embedding"

    def __init__(
        self,
        model_name: str = DEFAULT_MODEL,
        device: str = "cpu",
        cache_dir: str | Path = "data/cache/embeddings",
        query_prefix: str = "",
        doc_prefix: str = "",
        batch_size: int = 32,
    ) -> None:
        self.model_name = model_name
        self.device = device
        self.cache_dir = Path(cache_dir)
        self.query_prefix = query_prefix
        self.doc_prefix = doc_prefix
        self.batch_size = batch_size
        self._model = None
        self._model_revision: str | None = None
        self._tool_vectors: dict[str, np.ndarray] = {}  # content_key -> vector
        self._cache_loaded = False
        self._n_new_since_load = 0
        self._indexes: _LRUCache = _LRUCache(maxsize=16)  # catalog_id -> assembled index

    def _get_model(self):
        if self._model is None:
            from sentence_transformers import SentenceTransformer

            self._model = SentenceTransformer(self.model_name, device=self.device)
            self._model_revision = self._resolve_revision()
            self._load_cache()
        return self._model

    def _resolve_revision(self) -> str:
        try:
            from huggingface_hub import HfApi

            info = HfApi().model_info(self.model_name)
            return info.sha or "unknown"
        except Exception:
            return "offline-unknown"

    def _encode(self, texts: list[str]) -> np.ndarray:
        model = self._get_model()
        vecs = model.encode(
            texts,
            batch_size=self.batch_size,
            convert_to_numpy=True,
            normalize_embeddings=True,
            show_progress_bar=False,
        )
        return np.asarray(vecs, dtype=np.float32)

    def _cache_file(self) -> Path:
        model_tag = (self._model_revision or "unknown")[:12]
        model_name_safe = self.model_name.replace("/", "__")
        return self.cache_dir / model_name_safe / model_tag / "tool_embedding_cache.npz"

    def _load_cache(self) -> None:
        if self._cache_loaded:
            return
        self._cache_loaded = True
        path = self._cache_file()
        if path.exists():
            data = np.load(path, allow_pickle=True)
            keys = data["keys"].tolist()
            vectors = data["vectors"]
            for k, v in zip(keys, vectors):
                self._tool_vectors[k] = v

    def save_cache(self) -> None:
        """Persist newly-computed tool embeddings to disk. Call once after
        a batch of ``prepare_catalog`` calls (e.g. at the end of a run)."""
        if not self._tool_vectors:
            return
        path = self._cache_file()
        path.parent.mkdir(parents=True, exist_ok=True)
        keys = list(self._tool_vectors.keys())
        vectors = np.stack([self._tool_vectors[k] for k in keys])
        np.savez(path, keys=np.array(keys, dtype=object), vectors=vectors)
        path.with_suffix(".meta.json").write_text(
            json.dumps(
                {
                    "model_name": self.model_name,
                    "model_revision": self._model_revision,
                    "n_tools_cached": len(keys),
                },
                indent=2,
            )
        )
        self._n_new_since_load = 0

    def _get_or_encode_tool_vectors(self, tools: list[Tool]) -> float:
        """Ensure every tool in ``tools`` has a cached vector. Returns
        seconds spent encoding (0.0 if everything was already cached)."""
        self._get_model()
        keys = [_tool_content_key(t, self.doc_prefix) for t in tools]
        missing = [(k, t) for k, t in zip(keys, tools) if k not in self._tool_vectors]
        if not missing:
            return 0.0

        start = time.perf_counter()
        texts = [self.doc_prefix + t.serialized_text() for _, t in missing]
        vectors = self._encode(texts)
        for (k, _), vec in zip(missing, vectors):
            self._tool_vectors[k] = vec
        self._n_new_since_load += len(missing)
        elapsed = time.perf_counter() - start

        # Autosave periodically so a crash mid-run doesn't lose all encode
        # work, without paying disk I/O cost on every single catalog.
        if self._n_new_since_load >= 500:
            self.save_cache()
        return elapsed

    def prepare_catalog(self, catalog_id: str, tools: list[Tool]) -> float:
        tool_ids = tuple(t.tool_id for t in tools)
        if not tool_ids:
            self._indexes[catalog_id] = _CatalogIndex(tool_ids=(), embeddings=None)
            return 0.0

        elapsed = self._get_or_encode_tool_vectors(tools)
        keys = [_tool_content_key(t, self.doc_prefix) for t in tools]
        embeddings = np.stack([self._tool_vectors[k] for k in keys])
        self._indexes[catalog_id] = _CatalogIndex(tool_ids=tool_ids, embeddings=embeddings)
        return elapsed

    def rank(self, catalog_id: str, query_text: str, top_k: int = 10) -> RankedResult:
        index = self._indexes.get(catalog_id)
        if index is None or index.embeddings is None or not index.tool_ids:
            return RankedResult((), (), 0.0, 0.0)

        prep_start = time.perf_counter()
        query_vec = self._encode([self.query_prefix + query_text])[0]
        prep_seconds = time.perf_counter() - prep_start

        retr_start = time.perf_counter()
        scores = index.embeddings @ query_vec
        order = np.argsort(-scores)[:top_k]
        retr_seconds = time.perf_counter() - retr_start

        ranked_ids = tuple(index.tool_ids[i] for i in order)
        ranked_scores = tuple(float(scores[i]) for i in order)
        return RankedResult(ranked_ids, ranked_scores, prep_seconds, retr_seconds)
