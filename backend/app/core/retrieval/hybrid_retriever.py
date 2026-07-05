"""
Retrieval Engine — Finds the most relevant chunks for a user query.

Implements:
  - Query analysis (intent detection, expansion)
  - Vector search via pgvector
  - Keyword search via Elasticsearch (stub — requires ES connection)
  - Reciprocal Rank Fusion (RRF)
  - Cross-encoder re-ranking
  - Context assembly with token budgeting
"""

from __future__ import annotations

import re
from dataclasses import dataclass, field
from typing import Optional

from app.config import settings
from app.utils.logging import get_logger

logger = get_logger(__name__)


# ── Query Analysis ───────────────────────────────────────────

@dataclass
class AnalyzedQuery:
    """Result of query analysis — drives retrieval strategy."""
    original: str
    doc_type_hints: list[str] = field(default_factory=list)
    section_refs: list[str] = field(default_factory=list)
    is_authority_question: bool = False
    is_procedural: bool = False
    is_comparison: bool = False
    is_temporal: bool = False
    jurisdiction_hints: list[str] = field(default_factory=list)
    complexity: str = "low"  # low, medium, high
    expanded_queries: list[str] = field(default_factory=list)


class QueryAnalyzer:
    """Analyze user query to guide retrieval."""

    AUTHORITY_PATTERNS = [
        r'can\s+(?:a|the)\s+\w+\s+\w+',
        r'who\s+has\s+authority',
        r'is\s+(?:\w+\s+)?allowed\s+to',
        r'(?:may|shall)\s+(?:a|the)\s+',
    ]
    PROCEDURAL_PATTERNS = [
        r'how\s+(?:do|can|should)\s+(?:I|we|you|a|lodge)',
        r'what\s+is\s+the\s+procedure',
        r'steps?\s+to',
    ]
    COMPARISON_PATTERNS = [
        r'compare\s+.+\s+(?:to|with|and)\s+.+',
        r'(.+)\s+vs\.?\s+(.+)',
        r'difference\s+between\s+(.+)\s+and\s+(.+)',
    ]

    DOC_TYPE_HINTS = {
        "general_laws":     [r"general\s+laws?", r"\bGL\b"],
        "wotm_general_laws":[r"women\s+of\s+the\s+moose", r"\bWOTM\b"],
        "legion_manual":    [r"moose\s+legion", r"legion\s+rules?"],
        "ritual":           [r"\britual\b", r"\bceremony\b", r"o'clock"],
        "officer_handbook": [r"officer\s+handbook", r"duties\s+of"],
        "election_handbook":[r"\belection\b", r"\bvoting\b", r"\bballot\b"],
        "social_quarters":  [r"social\s+quarters?", r"\bbar\b", r"bartender", r"liquor"],
        "sports_rules":     [r"bowling", r"darts?\b", r"golf", r"pool\b"],
    }

    def analyze(self, query: str) -> AnalyzedQuery:
        """Analyze query for intent, document type hints, and section references."""
        analyzed = AnalyzedQuery(original=query)

        # Detect document type hints
        for doc_type, patterns in self.DOC_TYPE_HINTS.items():
            if any(re.search(p, query, re.IGNORECASE) for p in patterns):
                analyzed.doc_type_hints.append(doc_type)

        # Detect section references
        section_pattern = r'(?:Section\s+)?§?\s*(\d+(?:\.\d+)*(?:\([a-z]\))*)'
        for match in re.finditer(section_pattern, query, re.IGNORECASE):
            analyzed.section_refs.append(match.group(0))

        # Detect intent
        analyzed.is_authority_question = any(
            re.search(p, query, re.IGNORECASE) for p in self.AUTHORITY_PATTERNS
        )
        analyzed.is_procedural = any(
            re.search(p, query, re.IGNORECASE) for p in self.PROCEDURAL_PATTERNS
        )
        analyzed.is_comparison = any(
            re.search(p, query, re.IGNORECASE) for p in self.COMPARISON_PATTERNS
        )

        # Detect complexity
        words = query.split()
        has_legal_terms = bool(re.search(
            r'\b(?:shall|may|must|authority|jurisdiction|quorum|majority|'
            r'ballot|motion|bylaws?|constitution|amendment|'
            r'suspension|expulsion|appeal|grievance)\b',
            query, re.IGNORECASE
        ))
        analyzed.complexity = (
            "high" if len(words) > 15 or has_legal_terms
            else "medium" if len(words) > 8
            else "low"
        )

        # Expand queries
        analyzed.expanded_queries = self._expand_query(query, analyzed)

        return analyzed

    def _expand_query(self, query: str, analyzed: AnalyzedQuery) -> list[str]:
        """Generate query variants for broader search coverage."""
        variants = [query]

        # Moose-domain synonyms
        synonyms = {
            "fire": ["terminate", "dismiss", "remove from employment"],
            "bartender": ["bar staff", "social quarters staff"],
            "governor": ["lodge governor", "presiding officer"],
            "trustee": ["board member", "lodge trustee"],
            "suspend": ["disciplinary suspension", "temporary removal"],
            "expel": ["expulsion", "permanent removal"],
            "dues": ["membership fees", "annual dues"],
            "quorum": ["minimum attendance", "voting threshold"],
            "majority": ["more than half", "simple majority"],
        }

        # Build synonym-expanded variant
        expanded_words = []
        for word in query.lower().split():
            clean = word.strip('?.!,')
            if clean in synonyms:
                expanded_words.append(synonyms[clean][0])
            else:
                expanded_words.append(clean)
        variants.append(" ".join(expanded_words))

        # Citation-style variant for exact section matches
        if analyzed.section_refs:
            variants.append(" ".join(analyzed.section_refs))

        return variants


# ── Vector Search (FAISS) ────────────────────────────────────

@dataclass
class RankedChunk:
    """A retrieved chunk with relevance metadata."""
    id: str
    content_text: str
    section_number: str
    section_title: str
    hierarchy_path: str
    document_title: str
    document_short_title: str = ""
    document_type: str = ""
    document_tier: int = 1
    page_start: int = 1
    page_end: int = 1
    version_number: int = 1
    effective_date: str = ""
    relevance_score: float = 0.0
    citation_header: str = ""


class VectorRetriever:
    """
    Semantic search using FAISS cosine similarity.

    Uses the FAISSVectorStore for local, zero-dependency vector search.
    Works without PostgreSQL, Docker, or any external service.

    Usage:
        store = FAISSVectorStore.load("data/faiss_index/")
        retriever = VectorRetriever(store)
        results = retriever.search(query_embedding, top_k=20)
    """

    def __init__(self, vector_store=None):
        """
        Args:
            vector_store: A FAISSVectorStore instance. If None, search()
                          returns empty results (no-op mode).
        """
        self._store = vector_store

    @property
    def store(self):
        """Get or lazy-load the FAISS vector store."""
        if self._store is None:
            from app.core.retrieval.vector_store import FAISSVectorStore
            from pathlib import Path
            
            # Try configured path first, then project-relative, then cwd-relative
            search_paths = []
            
            # 1. Environment variable / config override
            import os
            env_path = os.environ.get("FAISS_INDEX_PATH")
            if env_path:
                search_paths.append(Path(env_path))
            
            # 2. Project root: backend/../data/faiss_index/
            backend_root = Path(__file__).resolve().parent.parent.parent.parent
            search_paths.append(backend_root / ".." / "data" / "faiss_index")
            
            # 3. CWD-relative
            search_paths.append(Path("data/faiss_index/"))
            
            for path in search_paths:
                resolved = path.resolve()
                index_file = resolved / "faiss.index"
                if index_file.exists():
                    logger.info("Loading FAISS index from %s", resolved)
                    self._store = FAISSVectorStore.load(resolved)
                    break
            else:
                logger.warning(
                    "No FAISS index found. Searched: %s. Run scripts/build_index.py first.",
                    [str(p.resolve()) for p in search_paths]
                )
        return self._store

    def set_store(self, vector_store):
        """Set or replace the vector store."""
        self._store = vector_store

    def search(
        self,
        query_embedding: list[float],
        top_k: int = 20,
        doc_type_filter: Optional[list[str]] = None,
    ) -> list[RankedChunk]:
        """
        Perform vector similarity search using FAISS.

        Args:
            query_embedding: Query vector (list of floats).
            top_k: Number of results to return.
            doc_type_filter: Optional list of document types to include.

        Returns:
            List of RankedChunk sorted by relevance.
        """
        store = self.store
        if store is None:
            logger.warning(
                "VectorRetriever: No vector store available — "
                "run scripts/build_index.py first"
            )
            return []

        results = store.search(
            query_embedding=query_embedding,
            top_k=top_k,
            doc_type_filter=doc_type_filter,
        )

        if not results:
            return []

        return [
            RankedChunk(
                id=result.chunk_id,
                content_text=result.content_text,
                section_number=result.section_number,
                section_title=result.section_title,
                hierarchy_path=result.hierarchy_path,
                document_title=result.document_short_title,
                document_short_title=result.document_short_title,
                document_type=result.metadata.get("doc_type", ""),
                document_tier=result.document_tier,
                page_start=result.page_start,
                page_end=result.page_end,
                effective_date=result.effective_date,
                relevance_score=result.score,
                citation_header=result.citation_header,
            )
            for result in results
        ]


# ── Hybrid Retriever ─────────────────────────────────────────

class HybridRetriever:
    """
    Combines vector search and keyword search using RRF.

    Full implementation would:
      1. Run vector search and keyword search in parallel.
      2. Fuse results with Reciprocal Rank Fusion.
      3. Re-rank top candidates with cross-encoder.
      4. Apply access control filters.
      5. Return top final_k chunks.
    """

    def __init__(self):
        self.vector = VectorRetriever()
        self.embedder = None  # Set up after import

    def retrieve(
        self,
        query: str,
        top_k: int = 8,
        user_roles: Optional[list[str]] = None,
    ) -> list[RankedChunk]:
        """
        Retrieve relevant chunks for a query.

        Uses FAISS vector search + optional keyword search with RRF fusion.
        Embeddings generated locally via sentence-transformers (no API key needed).

        Args:
            query: The user's natural-language query.
            top_k: Number of final results to return.
            user_roles: Optional user roles for access filtering.

        Returns:
            List of RankedChunk sorted by relevance.
        """
        # 1. Analyze query
        analyzed = QueryAnalyzer().analyze(query)

        # 2. Generate query embedding using local model (no API key)
        from app.core.retrieval.vector_store import LocalEmbedder
        embedder = LocalEmbedder()
        query_embedding = embedder.embed_query(query)

        # 3. Vector search via FAISS
        doc_filter = analyzed.doc_type_hints if analyzed.doc_type_hints else None
        vector_results = self.vector.search(
            query_embedding,
            top_k=top_k * 2,
            doc_type_filter=doc_filter,
        )

        # 4. Keyword search — stub (no Elasticsearch)
        keyword_results = []

        # 5. RRF fusion
        fused = self._reciprocal_rank_fusion(vector_results, keyword_results)

        # 6. Return top results
        return fused[:top_k]

    @staticmethod
    def _reciprocal_rank_fusion(
        list_a: list[RankedChunk],
        list_b: list[RankedChunk],
        k: int = 60,
    ) -> list[RankedChunk]:
        """
        Fuse two ranked lists using Reciprocal Rank Fusion.

        RRF(chunk) = Σ 1 / (k + rank_in_list(chunk))
        """
        scores: dict[str, float] = {}
        chunk_map: dict[str, RankedChunk] = {}

        for rank, chunk in enumerate(list_a, start=1):
            scores[chunk.id] = scores.get(chunk.id, 0) + 1.0 / (k + rank)
            chunk_map[chunk.id] = chunk

        for rank, chunk in enumerate(list_b, start=1):
            scores[chunk.id] = scores.get(chunk.id, 0) + 1.0 / (k + rank)
            chunk_map[chunk.id] = chunk

        # Sort by RRF score and update relevance
        sorted_ids = sorted(scores.items(), key=lambda x: x[1], reverse=True)
        result = []
        for chunk_id, score in sorted_ids:
            chunk = chunk_map[chunk_id]
            chunk.relevance_score = score
            result.append(chunk)

        return result


# ── Context Assembly ─────────────────────────────────────────

class ContextAssembler:
    """Assemble retrieved chunks into a context window for the LLM."""

    MAX_TOKENS = 8_000  # Leave room for prompt + response
    MAX_CHUNKS_PER_SECTION = 3  # Diversity cap

    def assemble(self, ranked_chunks: list[RankedChunk]) -> str:
        """Build the context string from ranked chunks."""
        parts = []
        tokens_used = 0
        seen_hashes = set()
        section_counts: dict[str, int] = {}

        for chunk in ranked_chunks:
            # Diversity cap
            section_key = chunk.section_number
            if section_counts.get(section_key, 0) >= self.MAX_CHUNKS_PER_SECTION:
                continue

            # Dedup
            import hashlib
            content_hash = hashlib.md5(chunk.content_text.encode()).hexdigest()
            if content_hash in seen_hashes:
                continue

            # Format chunk
            formatted = self._format_chunk(chunk)
            est_tokens = len(formatted.split()) * 1.3

            if tokens_used + est_tokens > self.MAX_TOKENS:
                break

            parts.append(formatted)
            tokens_used += est_tokens
            seen_hashes.add(content_hash)
            section_counts[section_key] = section_counts.get(section_key, 0) + 1

        header = (
            f"RETRIEVAL SUMMARY: Found {len(ranked_chunks)} relevant passages "
            f"from {len(section_counts)} sections. "
            f"Showing top {len(parts)} below.\n\n"
        )
        return header + "\n\n".join(parts)

    @staticmethod
    def _format_chunk(chunk: RankedChunk) -> str:
        """Format a chunk for LLM consumption."""
        header = (
            f"[SOURCE: {chunk.document_short_title or chunk.document_title} | "
            f"§{chunk.section_number}"
        )
        if chunk.section_title:
            header += f' — "{chunk.section_title}"'
        header += (
            f" | Tier {chunk.document_tier} | "
            f"Page {chunk.page_start}" +
            (f"-{chunk.page_end}" if chunk.page_end != chunk.page_start else "") +
            f" | Relevance: {chunk.relevance_score:.2f}]"
        )
        return f"{header}\n{chunk.content_text}"
