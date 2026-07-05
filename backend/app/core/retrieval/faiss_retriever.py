"""
FAISS-backed query retriever — Uses the sub-agent's FAISSVectorStore.

Works without Docker/PostgreSQL. Requires the index built by:
    python scripts/build_index.py
"""

from __future__ import annotations

import json, os
from pathlib import Path
from typing import Optional

from app.utils.logging import get_logger

logger = get_logger(__name__)


class FAISSRetriever:
    """
    Retrieves chunks using the FAISSVectorStore from vector_store.py.

    Uses sentence-transformers for local embeddings (free, no API key).
    Requires a pre-built index at FAISS_INDEX_PATH.

    Build the index:  python scripts/build_index.py
    """

    def __init__(self):
        self._store = None
        self._embedder = None
        self._index_path = Path(os.environ.get(
            "FAISS_INDEX_PATH",
            str(Path(__file__).resolve().parent.parent.parent.parent.parent / "data" / "faiss_index")
        ))

    @property
    def is_ready(self) -> bool:
        return (self._index_path / "faiss.index").exists()

    def _load(self):
        if self._store is not None:
            return

        from app.core.retrieval.vector_store import FAISSVectorStore, LocalEmbedder

        index_file = self._index_path / "faiss.index"
        if not index_file.exists():
            raise FileNotFoundError(
                f"FAISS index not found at {index_file}. Run: python scripts/build_index.py"
            )

        logger.info("Loading FAISSVectorStore from %s", self._index_path)
        self._store = FAISSVectorStore.load(self._index_path)

        # Load info for embedding dimension
        info_path = self._index_path / "store_info.json"
        if info_path.exists():
            with open(info_path) as f:
                info = json.load(f)
            model_dim = info.get("dimension", 384)
            # Map dimension to model name
            model_map = {384: "all-MiniLM-L6-v2", 768: "all-mpnet-base-v2", 1024: "BAAI/bge-m3"}
            model_name = os.environ.get("LOCAL_EMBEDDING_MODEL", model_map.get(model_dim, "all-MiniLM-L6-v2"))
        else:
            model_name = os.environ.get("LOCAL_EMBEDDING_MODEL", "all-MiniLM-L6-v2")

        logger.info("Loading embedder: %s", model_name)
        self._embedder = LocalEmbedder(model_name=model_name)

        logger.info("FAISS ready: %d chunks, %d-dim vectors", self._store.size, self._store.dimension)

    def search(self, query: str, top_k: int = 8, min_score: float = 0.0) -> list[dict]:
        """Search for chunks relevant to the query."""
        self._load()

        query_emb = self._embedder.embed_query(query)
        results = self._store.search(query_emb, top_k=top_k)

        return [
            {
                "content_text": r.content_text,
                "section_number": r.section_number,
                "section_title": r.section_title,
                "hierarchy_path": r.hierarchy_path,
                "citation_header": r.citation_header,
                "document_title": r.document_short_title,
                "document_tier": r.document_tier,
                "page_start": r.page_start,
                "page_end": r.page_end,
                "score": r.score,
            }
            for r in results if r.score >= min_score
        ]

    def get_chunk_count(self) -> int:
        if self._store is None:
            try: self._load()
            except FileNotFoundError: return 0
        return self._store.size


_retriever: Optional[FAISSRetriever] = None

def get_retriever() -> FAISSRetriever:
    global _retriever
    if _retriever is None:
        _retriever = FAISSRetriever()
    return _retriever
