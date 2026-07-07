"""
FAISS-based Vector Store — Zero-dependency vector search.

Stores embeddings + metadata for ChunkData objects using FAISS.
No Docker, PostgreSQL, or external APIs required.

Features:
  - Ingest ChunkData objects with embeddings and metadata
  - Cosine similarity search (normalized inner product)
  - Persist to disk (index + metadata as separate files)
  - Load from disk
  - Filter by document type / tier (post-filter)

Usage:
    store = FAISSVectorStore(dimension=384)
    store.add_chunks(chunk_datas)
    store.save("data/faiss_index/")
    
    store2 = FAISSVectorStore.load("data/faiss_index/")
    results = store2.search(query_embedding, top_k=5)
"""

from __future__ import annotations

import json
import pickle
from dataclasses import dataclass, field
from pathlib import Path
from typing import Optional

import numpy as np

from app.utils.logging import get_logger

logger = get_logger(__name__)

# Import inline to avoid hard dependency at module level
# (faiss-cpu is a new optional dependency)


@dataclass
class VectorSearchResult:
    """A single result from vector search."""
    chunk_id: str                    # Unique ID for this chunk (content hash)
    content_text: str
    section_number: str
    section_title: str
    hierarchy_path: str
    citation_header: str
    document_short_title: str
    document_tier: int
    page_start: int
    page_end: int
    effective_date: str
    score: float                     # Similarity score (higher = more relevant)
    metadata: dict = field(default_factory=dict)


class FAISSVectorStore:
    """
    FAISS-backed vector index for document chunks.

    Uses IndexFlatIP (inner product) with L2-normalized vectors
    for cosine similarity search. Stores metadata in a companion
    JSON file for persistence.
    """

    def __init__(self, dimension: int = 384):
        """
        Initialize an empty FAISS vector store.

        Args:
            dimension: Embedding vector dimension.
                       all-MiniLM-L6-v2 = 384
                       text-embedding-3-large = 3072
        """
        self.dimension = dimension
        self._index = None           # faiss.IndexFlatIP
        self._id_to_meta: dict[int, dict] = {}
        self._id_to_chunk_id: dict[int, str] = {}
        self._next_id = 0

    @property
    def size(self) -> int:
        """Number of vectors currently indexed."""
        return self._next_id

    def _ensure_index(self):
        """Lazy-init the FAISS index."""
        if self._index is None:
            import faiss
            self._index = faiss.IndexFlatIP(self.dimension)

    # ── Ingest ────────────────────────────────────────────────

    def add_chunks(self, chunk_datas: list) -> list[str]:
        """
        Add ChunkData objects to the index.

        Each ChunkData must have an 'embedding' in its metadata dict
        (populated by EmbeddingGenerator or LocalEmbedder).

        Args:
            chunk_datas: List of ChunkData objects with embeddings.

        Returns:
            List of chunk IDs that were indexed.
        """
        self._ensure_index()

        vectors = []
        chunk_ids = []

        for chunk in chunk_datas:
            embedding = chunk.metadata.get("embedding")
            if embedding is None:
                logger.warning(
                    "Skipping chunk §%s — no embedding found",
                    chunk.section_number
                )
                continue

            # Normalize for cosine similarity (FAISS IndexFlatIP)
            vec = np.array(embedding, dtype=np.float32)
            vec = self._l2_normalize(vec)
            vectors.append(vec)

            # Use content_hash as chunk ID for dedup
            chunk_id = chunk.metadata.get(
                "content_hash",
                f"{chunk.section_number}_{chunk.chunk_index}"
            )
            chunk_ids.append(chunk_id)

            # Store metadata
            self._id_to_meta[self._next_id] = {
                "content_text": chunk.content_text,
                "section_number": chunk.section_number,
                "section_title": chunk.section_title,
                "hierarchy_path": chunk.hierarchy_path,
                "citation_header": chunk.citation_header,
                "document_short_title": chunk.document_short_title,
                "document_tier": chunk.document_tier,
                "page_start": chunk.page_start,
                "page_end": chunk.page_end,
                "effective_date": chunk.effective_date or "",
                "metadata": {
                    k: v for k, v in chunk.metadata.items()
                    if k != "embedding"  # Don't store the vector in JSON
                },
            }
            self._id_to_chunk_id[self._next_id] = chunk_id
            self._next_id += 1

        if vectors:
            vec_array = np.array(vectors, dtype=np.float32)
            self._index.add(vec_array)
            logger.info(
                "Added %d vectors to FAISS index (total: %d)",
                len(vectors), self._next_id
            )

        return chunk_ids

    def add_embeddings(
        self,
        embeddings: np.ndarray,
        metadata_list: list[dict],
    ) -> list[int]:
        """
        Add raw embeddings + metadata directly (alternative to add_chunks).

        Args:
            embeddings: (N, D) numpy array of float32 embeddings.
            metadata_list: List of metadata dicts, one per embedding.

        Returns:
            List of internal IDs assigned.
        """
        self._ensure_index()

        # Normalize
        norms = np.linalg.norm(embeddings, axis=1, keepdims=True)
        norms = np.where(norms == 0, 1.0, norms)  # Avoid div-by-zero
        normalized = embeddings / norms

        self._index.add(normalized.astype(np.float32))

        ids = []
        for meta in metadata_list:
            ids.append(self._next_id)
            self._id_to_meta[self._next_id] = meta
            self._id_to_chunk_id[self._next_id] = meta.get("chunk_id", str(self._next_id))
            self._next_id += 1

        logger.info("Added %d vectors from raw array", len(metadata_list))
        return ids

    # ── Search ─────────────────────────────────────────────────

    def search(
        self,
        query_embedding: list[float] | np.ndarray,
        top_k: int = 20,
        doc_type_filter: Optional[list[str]] = None,
        tier_filter: Optional[list[int]] = None,
    ) -> list[VectorSearchResult]:
        """
        Search for chunks similar to the query embedding.

        Args:
            query_embedding: Query vector (list or numpy array).
            top_k: Number of results to return.
            doc_type_filter: Optional list of document types to include.
            tier_filter: Optional list of document tiers to include.

        Returns:
            List of VectorSearchResult sorted by similarity (descending).
        """
        if self._index is None or self._next_id == 0:
            logger.warning("FAISS index is empty — no results")
            return []

        vec = np.array(query_embedding, dtype=np.float32).reshape(1, -1)
        vec = self._l2_normalize(vec)

        # Request more results so post-filtering doesn't starve
        fetch_k = min(top_k * 4, self._next_id) if (doc_type_filter or tier_filter) else top_k

        distances, indices = self._index.search(vec, fetch_k)

        results = []
        for dist, idx in zip(distances[0], indices[0]):
            if idx < 0 or idx >= self._next_id:
                continue  # Invalid index

            meta = self._id_to_meta.get(idx)
            if meta is None:
                continue

            # Post-filter by tier
            if tier_filter and meta.get("document_tier") not in tier_filter:
                continue

            # Post-filter by doc type (stored in metadata)
            if doc_type_filter:
                chunk_meta = meta.get("metadata", {})
                chunk_doc_type = chunk_meta.get("doc_type", "")
                if chunk_doc_type not in doc_type_filter:
                    continue

            results.append(VectorSearchResult(
                chunk_id=self._id_to_chunk_id.get(idx, str(idx)),
                content_text=meta.get("content_text", ""),
                section_number=meta.get("section_number", ""),
                section_title=meta.get("section_title", ""),
                hierarchy_path=meta.get("hierarchy_path", ""),
                citation_header=meta.get("citation_header", ""),
                document_short_title=meta.get("document_short_title", meta.get("document_title", "")),
                document_tier=meta.get("document_tier", 1),
                page_start=meta.get("page_start", 0),
                page_end=meta.get("page_end", 0),
                effective_date=meta.get("effective_date", ""),
                score=float(dist),  # Cosine similarity (higher = better)
                metadata=meta.get("metadata", {}),
            ))

            if len(results) >= top_k:
                break

        return results

    # ── Persistence ────────────────────────────────────────────

    def save(self, directory: str | Path):
        """
        Persist the FAISS index and metadata to disk.

        Creates:
          {directory}/faiss.index      — Binary FAISS index
          {directory}/metadata.json    — Chunk metadata (text, sections, etc.)
          {directory}/store_info.json  — Dimension, size, etc.

        Args:
            directory: Path to save directory (created if needed).
        """
        import faiss

        directory = Path(directory)
        directory.mkdir(parents=True, exist_ok=True)

        # Save FAISS index
        if self._index is not None:
            index_path = directory / "faiss.index"
            faiss.write_index(self._index, str(index_path))
            logger.info("Saved FAISS index to %s", index_path)

        # Save metadata
        meta_path = directory / "metadata.json"
        with open(meta_path, "w", encoding="utf-8") as f:
            json.dump({
                "id_to_meta": self._id_to_meta,
                "id_to_chunk_id": self._id_to_chunk_id,
            }, f, ensure_ascii=False, indent=2)
        logger.info("Saved %d metadata entries to %s", self._next_id, meta_path)

        # Save store info
        info_path = directory / "store_info.json"
        with open(info_path, "w", encoding="utf-8") as f:
            json.dump({
                "dimension": self.dimension,
                "size": self._next_id,
                "index_type": "IndexFlatIP",
            }, f, indent=2)

        logger.info(
            "FAISSVectorStore saved to %s (%d vectors, dim=%d)",
            directory, self._next_id, self.dimension
        )

    @classmethod
    def load(cls, directory: str | Path) -> "FAISSVectorStore":
        """
        Load a FAISS vector store from disk.

        Args:
            directory: Path to the saved index directory.

        Returns:
            A loaded FAISSVectorStore instance.

        Raises:
            FileNotFoundError: If the index files don't exist.
        """
        import faiss

        directory = Path(directory)

        # Load store info
        info_path = directory / "store_info.json"
        if info_path.exists():
            with open(info_path, "r") as f:
                info = json.load(f)
            dimension = info.get("dimension", 384)
        else:
            dimension = 384  # Default; will be corrected on load

        store = cls(dimension=dimension)

        # Load FAISS index
        index_path = directory / "faiss.index"
        if index_path.exists():
            store._index = faiss.read_index(str(index_path))
            store.dimension = store._index.d
            logger.info("Loaded FAISS index from %s (d=%d)", index_path, store.dimension)
        else:
            logger.warning("No FAISS index found at %s", index_path)

        # Load metadata
        meta_path = directory / "metadata.json"
        if meta_path.exists():
            with open(meta_path, "r", encoding="utf-8") as f:
                data = json.load(f)
            # JSON keys are strings — convert back to int
            store._id_to_meta = {
                int(k): v for k, v in data.get("id_to_meta", {}).items()
            }
            store._id_to_chunk_id = {
                int(k): v for k, v in data.get("id_to_chunk_id", {}).items()
            }
            if store._id_to_meta:
                store._next_id = max(store._id_to_meta.keys()) + 1
            logger.info(
                "Loaded %d metadata entries from %s",
                len(store._id_to_meta), meta_path
            )
        else:
            logger.warning("No metadata found at %s", meta_path)

        return store

    # ── Helpers ────────────────────────────────────────────────

    @staticmethod
    def _l2_normalize(vec: np.ndarray) -> np.ndarray:
        """L2-normalize a vector for cosine similarity via inner product."""
        norm = np.linalg.norm(vec)
        if norm == 0:
            return vec
        return vec / norm

    def get_chunk_by_id(self, chunk_id: str) -> Optional[dict]:
        """Retrieve metadata for a specific chunk by its ID."""
        for idx, cid in self._id_to_chunk_id.items():
            if cid == chunk_id:
                return {
                    "internal_id": idx,
                    "chunk_id": cid,
                    **self._id_to_meta.get(idx, {}),
                }
        return None


# ── Local Embedding Generator (sentence-transformers) ──────────


class LocalEmbedder:
    """
    Generate embeddings using a local sentence-transformers model.

    No API key, no network call — runs entirely on CPU (or GPU if available).

    Default model: all-MiniLM-L6-v2 (384 dimensions, ~80 MB download)
    """

    def __init__(self, model_name: str = "all-MiniLM-L6-v2"):
        """
        Initialize the local embedder.

        Args:
            model_name: HuggingFace model name for sentence-transformers.
                         all-MiniLM-L6-v2 = 384 dims (fast, lightweight)
                         all-mpnet-base-v2 = 768 dims (more accurate)
                         BAAI/bge-m3 = 1024 dims (multilingual)
        """
        self.model_name = model_name
        self._model = None

    @property
    def model(self):
        """Lazy-load the sentence-transformers model."""
        if self._model is None:
            from sentence_transformers import SentenceTransformer
            logger.info("Loading local embedding model: %s", self.model_name)
            self._model = SentenceTransformer(self.model_name)
            logger.info(
                "Model loaded: %s (dim=%d)",
                self.model_name, self.dimension
            )
        return self._model

    @property
    def dimension(self) -> int:
        """Get the embedding dimension for this model."""
        return self.model.get_embedding_dimension()

    def embed_texts(self, texts: list[str], show_progress: bool = True) -> np.ndarray:
        """
        Generate embeddings for a batch of texts.

        Args:
            texts: List of text strings to embed.
            show_progress: Show a progress bar (tqdm).

        Returns:
            NumPy array of shape (len(texts), dimension) with float32 embeddings.
        """
        return self.model.encode(
            texts,
            show_progress_bar=show_progress,
            normalize_embeddings=True,  # For cosine similarity
            convert_to_numpy=True,
        )

    def embed_chunks(
        self,
        chunk_datas: list,
        show_progress: bool = True,
    ) -> list:
        """
        Embed ChunkData objects and store embeddings in their metadata.

        Uses prepare_embedding_text() to build rich embedding text
        that includes section numbers, hierarchy paths, etc.

        Args:
            chunk_datas: List of ChunkData objects.
            show_progress: Show progress bar.

        Returns:
            Same list with 'embedding' populated in each chunk's metadata.
        """
        from app.core.ingestion.embedder import prepare_embedding_text

        texts = [prepare_embedding_text(c) for c in chunk_datas]
        embeddings = self.embed_texts(texts, show_progress=show_progress)

        for chunk, emb in zip(chunk_datas, embeddings):
            chunk.metadata["embedding"] = emb.tolist()
            chunk.metadata["embedding_model"] = self.model_name
            chunk.metadata["embedding_dimensions"] = self.dimension

        logger.info(
            "Generated %d embeddings using %s",
            len(chunk_datas), self.model_name
        )
        return chunk_datas

    def embed_query(self, query: str) -> list[float]:
        """
        Generate embedding for a single query string.

        Args:
            query: The query text.

        Returns:
            List of floats (the embedding vector).
        """
        # Use the encode method with a single text
        emb = self.model.encode(
            [query],
            show_progress_bar=False,
            normalize_embeddings=True,
            convert_to_numpy=True,
        )
        return emb[0].tolist()
