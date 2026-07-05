"""
Custom exceptions for the Moose Knowledge Assistant.
"""


class MooseAssistantError(Exception):
    """Base exception for the application."""
    pass


class DocumentLoadError(MooseAssistantError):
    """Failed to load or parse a document file."""
    pass


class OCRError(MooseAssistantError):
    """OCR processing failed."""
    pass


class StructureExtractionError(MooseAssistantError):
    """Failed to extract document structure."""
    pass


class ChunkingError(MooseAssistantError):
    """Failed to chunk document content."""
    pass


class EmbeddingError(MooseAssistantError):
    """Failed to generate embeddings."""
    pass


class RetrievalError(MooseAssistantError):
    """Failed to retrieve relevant chunks."""
    pass


class LLMError(MooseAssistantError):
    """LLM API call failed."""
    pass


class CitationValidationError(MooseAssistantError):
    """Citation could not be verified."""
    pass


class AuthenticationError(MooseAssistantError):
    """User authentication failed."""
    pass


class AuthorizationError(MooseAssistantError):
    """User lacks required permissions."""
    pass


class DocumentNotFoundError(MooseAssistantError):
    """Requested document does not exist."""
    pass
