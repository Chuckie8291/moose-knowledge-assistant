"""
Query API Endpoint — The main Q&A interface.

POST /api/v1/query
  - Accepts a question
  - Retrieves relevant chunks
  - Generates a cited answer via LLM
  - Returns formatted response with citations and confidence
"""

from __future__ import annotations

from fastapi import APIRouter, Depends, HTTPException
from pydantic import BaseModel, Field

from app.config import settings
from app.core.retrieval.hybrid_retriever import (
    HybridRetriever, ContextAssembler, RankedChunk
)
from app.core.generation.llm_adapter import (
    get_llm_adapter, build_query_prompt, ConfidenceScorer, LLMResponse
)
from app.utils.logging import get_logger

logger = get_logger(__name__)
router = APIRouter()


# ── Request / Response Schemas ───────────────────────────────

class QueryRequest(BaseModel):
    query: str = Field(
        ..., min_length=3, max_length=2000,
        description="The question to ask about Moose governing documents.",
        examples=["Can a governor fire a bartender?"]
    )
    session_id: str | None = Field(
        default=None, description="Optional session ID for conversation continuity."
    )


class CitationOut(BaseModel):
    number: int
    document_title: str
    section_number: str
    section_title: str = ""
    page_start: int = 1
    page_end: int | None = None
    quoted_text: str = ""
    verified: bool = True
    warning: str | None = None


class ConfidenceOut(BaseModel):
    score: int
    level: str  # HIGH, MEDIUM, LOW, INCONCLUSIVE
    icon: str = "●●●●○"
    color: str = "green"


class QueryResponse(BaseModel):
    answer: str
    confidence: ConfidenceOut
    citations: list[CitationOut] = []
    retrieval_count: int = 0
    model_used: str | None = None
    has_conflicts: bool = False
    error: str | None = None


# ── Endpoint ─────────────────────────────────────────────────

@router.post("", response_model=QueryResponse)
async def ask_question(request: QueryRequest) -> QueryResponse:
    """
    Ask a question about the Moose organization.

    The system will:
    1. Analyze the query intent
    2. Retrieve relevant passages from governing documents
    3. Generate a cited answer using AI
    4. Validate citations and calculate confidence
    """
    logger.info("Query received: %s", request.query[:100])

    try:
        # 1. Retrieve relevant chunks — try FAISS first, fall back to stub
        from app.core.retrieval.faiss_retriever import get_retriever
        retriever = get_retriever()

        if retriever.is_ready:
            faiss_results = retriever.search(request.query, top_k=8)
            retrieval_count = len(faiss_results)
            logger.info("FAISS search returned %d chunks", retrieval_count)

            # Convert FAISS results to context string
            if faiss_results:
                context_parts = []
                for r in faiss_results:
                    context_parts.append(
                        f"{r.get('citation_header', '[SOURCE]')}\n{r['content_text']}"
                    )
                context = "\n\n".join(context_parts)
            else:
                context = ""
        else:
            # FAISS index not built yet — return helpful message
            logger.warning("FAISS index not available")
            return QueryResponse(
                answer=(
                    "### CONCISE ANSWER\n"
                    "The knowledge base is being set up.\n\n"
                    "### DETAILED EXPLANATION\n"
                    "The Moose document index hasn't been built yet. An administrator "
                    "needs to run:\n\n"
                    "```\npython scripts/demo.py --build-only\n```\n\n"
                    "This will download the General Laws, process them into searchable "
                    "chunks, and build the vector index. Once complete, you'll be able "
                    "to ask questions about Moose governance.\n\n"
                    "### CITATIONS\n"
                    "No index available.\n\n"
                    "### CONFIDENCE\n"
                    "INCONCLUSIVE — Knowledge base not yet initialized."
                ),
                confidence=ConfidenceOut(score=0, level="INCONCLUSIVE", icon="○○○○○", color="red"),
                citations=[],
                retrieval_count=0,
            )
        # 2. Handle no results
        if not context:
            return QueryResponse(
                answer=(
                    "### CONCISE ANSWER\n"
                    "I could not find information about this topic in the Moose "
                    "governing documents.\n\n"
                    "### DETAILED EXPLANATION\n"
                    f"I searched all available Moose documents for information "
                    f'about "{request.query}" but did not find relevant passages. '
                    "This could mean:\n"
                    "- The topic is not covered in the documents currently in the system.\n"
                    "- The topic may be a matter of local lodge practice.\n"
                    "- Try rephrasing your question or being more specific.\n\n"
                    "### CITATIONS\n"
                    "No relevant sources found.\n\n"
                    "### CONFIDENCE\n"
                    "INCONCLUSIVE — No sources were found to support an answer."
                ),
                confidence=ConfidenceOut(score=0, level="INCONCLUSIVE", icon="○○○○○", color="red"),
                citations=[],
                retrieval_count=0,
            )

        retrieval_count = len(faiss_results)

        # 3. Build prompt
        system_prompt, user_prompt = build_query_prompt(request.query, context)

        # 4. Generate answer via LLM
        llm = get_llm_adapter()
        llm_response: LLMResponse = await llm.generate(system_prompt, user_prompt)

        if not llm_response.success:
            return QueryResponse(
                answer=llm_response.text,
                confidence=ConfidenceOut(score=0, level="INCONCLUSIVE", icon="○○○○○", color="red"),
                citations=[],
                retrieval_count=retrieval_count,
                error=llm_response.error,
            )

        # 5. Calculate confidence
        scorer = ConfidenceScorer()
        confidence = scorer.calculate(
            citations=llm_response.citations,
            retrieved_chunks=[],  # FAISS results don't have RankedChunk format
            llm_text=llm_response.text,
        )

        # 6. Format citations
        formatted_citations = [
            CitationOut(
                number=i + 1,
                document_title=c.document_name,
                section_number=c.section_number,
                quoted_text=c.quoted_text[:300],
                verified=True,
            )
            for i, c in enumerate(llm_response.citations)
        ]

        # 7. Build confidence display
        confidence_out = ConfidenceOut(
            score=confidence.score,
            level=confidence.level,
            icon={
                "HIGH": "●●●●○", "MEDIUM": "●●●○○",
                "LOW": "●●○○○", "INCONCLUSIVE": "○○○○○",
            }.get(confidence.level, "●●●○○"),
            color={
                "HIGH": "green", "MEDIUM": "yellow",
                "LOW": "orange", "INCONCLUSIVE": "red",
            }.get(confidence.level, "yellow"),
        )

        return QueryResponse(
            answer=llm_response.text,
            confidence=confidence_out,
            citations=formatted_citations,
            retrieval_count=retrieval_count,
            model_used=llm_response.model_used,
        )

    except Exception as e:
        logger.exception("Query processing failed: %s", e)
        return QueryResponse(
            answer="I encountered an error while processing your question. Please try again.",
            confidence=ConfidenceOut(score=0, level="INCONCLUSIVE", icon="○○○○○", color="red"),
            citations=[],
            error=str(e),
        )
