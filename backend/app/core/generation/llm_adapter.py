"""
LLM Adapter — Abstract interface with OpenAI and Anthropic implementations.

Handles:
  - Prompt construction (system + user + context)
  - Model selection with fallback chain
  - Response parsing (citations, confidence)
  - Circuit breaker for provider failures
"""

from __future__ import annotations

from dataclasses import dataclass, field
from typing import Optional

from app.config import settings
from app.utils.logging import get_logger

logger = get_logger(__name__)


# ── Prompts ──────────────────────────────────────────────────

SYSTEM_PROMPT = """# Moose Knowledge Assistant — System Instructions

## Identity
You are the Moose Knowledge Assistant, an AI system that answers questions about
the Loyal Order of Moose (Moose Fraternity). You have access to official Moose
governing documents, ritual books, officer handbooks, policy manuals, newsletters,
and other authorized publications.

## Absolute Rules

1. **NEVER answer from your own knowledge.** ONLY use the SOURCES provided below.

2. **BE EXTREMELY BRIEF.** Users want fast answers, not essays.
   - CONCISE ANSWER: 1-2 sentences. This is the full answer.
   - BRIEF EXPLANATION: 2-4 sentences max. Only the most relevant facts.
   - Maximum 3 citations total. Only cite sources that DIRECTLY answer the question.
   - If a source is tangentially related but doesn't answer the question, SKIP IT.

3. **STAY ON TOPIC.** Do not discuss:
   - Officer compensation unless the question is about pay.
   - Convention rules unless the question is about conventions.
   - Bill payment procedures unless the question is about finances.
   - General background about the Moose unless asked for it.
   - "The General Laws say..." as filler. Go straight to the point.

4. **If sources are insufficient, say so in one sentence.** Example:
   "The governing documents do not address this specifically."

5. **If sources conflict, state each position in one sentence, then which prevails.**

6. **Every factual claim must be cited.** Use EXACT format:
   [Cite: {document_name}, §{section_number} — "{direct quote}"]

7. **Do not offer legal advice.**

## Document Hierarchy (Highest to Lowest Authority)

When documents conflict, the higher-tier document controls:
1. General Laws of the Moose Fraternity — SUPREME.
2. International Policies & Procedures Manuals
3. Ritual & Ceremonial (binding for ceremonial matters only)
4. Women of the Moose General Laws and Moose Legion Manual
5. State/Provincial Association Bylaws
6. Local Lodge Bylaws
7. Local Lodge House Rules

## Citation Contract

Every factual statement you make that derives from a source MUST be immediately
followed by a citation in this EXACT format:

[Cite: {document_name}, §{section_number} — "{direct quote from source}"]

Rules:
- Quote the exact text from the source, enclosed in quotation marks.
- Do NOT paraphrase and then cite.
- Do NOT cite section numbers that don't appear in the sources provided.
- If you reference the same source multiple times, cite it each time.

## Response Format

Your response MUST follow this structure EXACTLY:

### CONCISE ANSWER
[1-2 sentences. This IS the answer.]

### BRIEF EXPLANATION
[2-4 sentences max. Only the most critical supporting facts. Do NOT ramble.]

### CITATIONS
[A numbered list of every source referenced, with full details:
1. {document_title} ({year}), §{section_number} "{section_title}", p. {page}
...]

### CONFIDENCE
[One of: HIGH | MEDIUM | LOW | INCONCLUSIVE]
[Brief explanation of why.]

## Edge Cases

- NO RESULTS: Say "I could not find information about this topic in the Moose documents."
- PARTIAL INFO: Answer what you can, state what's missing.
- CONFLICT: Quote both, explain which prevails and why.
- AMBIGUOUS: Distinguish mandatory ("shall") from discretionary ("may").
"""

USER_PROMPT_TEMPLATE = """## SOURCES

{context}

## QUESTION

{query}

## INSTRUCTIONS

Answer the question using ONLY the sources provided above. Every factual claim
needs a [Cite: ...] immediately after it. Use the exact response format:
CONCISE ANSWER, DETAILED EXPLANATION, CITATIONS, CONFIDENCE."""


# ── Data Structures ──────────────────────────────────────────

@dataclass
class ParsedCitation:
    """A citation extracted from LLM output."""
    document_name: str
    section_number: str
    quoted_text: str
    raw_match: str = ""
    position: int = 0


@dataclass
class LLMResponse:
    """Structured response from the LLM."""
    text: str
    success: bool
    model_used: str = ""
    citations: list[ParsedCitation] = field(default_factory=list)
    usage: dict = field(default_factory=dict)
    error: Optional[str] = None


@dataclass
class ConfidenceScore:
    """Calculated confidence score for an answer."""
    score: int           # 0-100
    level: str           # HIGH, MEDIUM, LOW, INCONCLUSIVE
    breakdown: dict = field(default_factory=dict)


# ── LLM Adapter ──────────────────────────────────────────────

class LLMAdapter:
    """Abstract LLM interface."""

    async def generate(self, system_prompt: str, user_prompt: str) -> LLMResponse:
        raise NotImplementedError


class OpenAIAdapter(LLMAdapter):
    """OpenAI / DeepSeek adapter (OpenAI-compatible API)."""

    def __init__(self, base_url: str | None = None, api_key: str | None = None):
        self.base_url = base_url
        self.api_key = api_key

    async def generate(self, system_prompt: str, user_prompt: str) -> LLMResponse:
        from openai import AsyncOpenAI

        client = AsyncOpenAI(
            api_key=self.api_key or settings.openai_api_key,
            base_url=self.base_url or None,
        )

        try:
            response = await client.chat.completions.create(
                model=settings.llm_model,
                messages=[
                    {"role": "system", "content": system_prompt},
                    {"role": "user", "content": user_prompt},
                ],
                temperature=settings.llm_temperature,
                max_tokens=settings.llm_max_tokens,
            )

            text = response.choices[0].message.content or ""
            citations = self._parse_citations(text)

            return LLMResponse(
                text=text,
                success=True,
                model_used=f"{'deepseek' if self.base_url else 'openai'}/{settings.llm_model}",
                citations=citations,
                usage={
                    "prompt_tokens": response.usage.prompt_tokens if response.usage else 0,
                    "completion_tokens": response.usage.completion_tokens if response.usage else 0,
                },
            )
        except Exception as e:
            logger.error("LLM API error: %s", e)
            return LLMResponse(
                text="I'm unable to process your question right now. Please try again shortly.",
                success=False,
                error=str(e),
            )

    @staticmethod
    def _parse_citations(text: str) -> list[ParsedCitation]:
        """Parse [Cite: ...] tokens from LLM output."""
        import re
        pattern = re.compile(
            r'\[Cite:\s*'
            r'([^,]+?)\s*'
            r',\s*'
            r'§?\s*(\d+(?:\.\d+)*(?:\([a-z]\))*)\s*'
            r'(?:—|–|-)\s*'
            r'"([^"]+)"'
            r'\]',
            re.IGNORECASE
        )
        citations = []
        for match in pattern.finditer(text):
            citations.append(ParsedCitation(
                document_name=match.group(1).strip(),
                section_number=match.group(2).strip(),
                quoted_text=match.group(3).strip(),
                raw_match=match.group(0),
                position=match.start(),
            ))
        return citations


class AnthropicAdapter(LLMAdapter):
    """Anthropic Claude adapter (stub)."""

    async def generate(self, system_prompt: str, user_prompt: str) -> LLMResponse:
        logger.warning("Anthropic adapter is a stub — requires API key")
        return LLMResponse(
            text="Anthropic adapter not configured.",
            success=False,
            error="Not implemented",
        )


# ── Confidence Scoring ───────────────────────────────────────

class ConfidenceScorer:
    """Calculate confidence score based on retrieval and citation quality."""

    def calculate(
        self,
        citations: list[ParsedCitation],
        retrieved_chunks: list["RankedChunk"],
        llm_text: str,
    ) -> ConfidenceScore:
        """
        Calculate a confidence score (0-100).

        Factors:
          - How many chunks were retrieved? (quantity)
          - What tiers are the sources from? (quality)
          - Are there any hedging phrases? (LLM uncertainty)
        """
        score = 50  # Start at neutral

        # Source quantity bonus
        unique_sections = len(set(
            c.section_number for c in retrieved_chunks
            if hasattr(c, 'section_number')
        ))
        if unique_sections >= 5:
            score += 15
        elif unique_sections >= 3:
            score += 10
        elif unique_sections >= 1:
            score += 5

        # Source quality bonus (lower tier = higher authority)
        tiers = [
            c.document_tier for c in retrieved_chunks
            if hasattr(c, 'document_tier')
        ]
        if tiers:
            min_tier = min(tiers)
            if min_tier <= 1:
                score += 20
            elif min_tier <= 3:
                score += 15
            elif min_tier <= 6:
                score += 10
            else:
                score += 5

        # Citation count bonus
        if citations:
            score += min(15, len(citations) * 5)

        # Hedging penalty
        hedging_phrases = [
            "may be", "might be", "could be", "possibly",
            "it appears", "it seems", "typically", "generally",
            "I believe", "I think", "not entirely clear",
        ]
        hedging_count = sum(
            1 for phrase in hedging_phrases
            if phrase in llm_text.lower()
        )
        score -= min(30, hedging_count * 5)

        # Clamp
        score = max(0, min(100, score))

        # Determine level
        if score >= 80:
            level = "HIGH"
        elif score >= 50:
            level = "MEDIUM"
        elif score >= 20:
            level = "LOW"
        else:
            level = "INCONCLUSIVE"

        return ConfidenceScore(score=score, level=level)


# ── Factory ──────────────────────────────────────────────────

def get_llm_adapter() -> LLMAdapter:
    """Factory: return the appropriate LLM adapter based on config."""
    if settings.llm_provider == "deepseek":
        return OpenAIAdapter(
            base_url=settings.deepseek_base_url,
            api_key=settings.deepseek_api_key,
        )
    elif settings.llm_provider == "openai":
        return OpenAIAdapter()
    elif settings.llm_provider == "anthropic":
        return AnthropicAdapter()
    else:
        return OpenAIAdapter()


def build_query_prompt(query: str, context: str) -> tuple[str, str]:
    """Build system and user prompts for a query."""
    return (
        SYSTEM_PROMPT,
        USER_PROMPT_TEMPLATE.format(context=context, query=query),
    )
