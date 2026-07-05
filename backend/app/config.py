"""
Moose Knowledge Assistant — Configuration

All settings are loaded from environment variables with sensible defaults.
Uses pydantic-settings for validation and .env file support.
"""

from __future__ import annotations

from pathlib import Path
from typing import Optional

from pydantic import Field, field_validator
from pydantic_settings import BaseSettings, SettingsConfigDict


class Settings(BaseSettings):
    model_config = SettingsConfigDict(
        env_file=".env",
        env_file_encoding="utf-8",
        case_sensitive=False,
        extra="ignore",
    )

    # ── Application ──────────────────────────────────────────
    app_name: str = "Moose Knowledge Assistant"
    app_version: str = "0.1.0"
    debug: bool = False
    secret_key: str = Field(default="change-me-in-production-please-use-a-real-key-here", min_length=32)
    cors_origins: list[str] = Field(default=["http://localhost:3000", "http://localhost:5173"])

    # ── Database ─────────────────────────────────────────────
    database_url: str = Field(
        default="postgresql+asyncpg://moose:moose@localhost:5432/moose_assistant"
    )
    database_url_sync: str = Field(
        default="postgresql+psycopg2://moose:moose@localhost:5432/moose_assistant"
    )
    db_pool_size: int = 20
    db_max_overflow: int = 10

    # ── Redis ────────────────────────────────────────────────
    redis_url: str = Field(default="redis://localhost:6379/0")

    # ── Elasticsearch ────────────────────────────────────────
    elasticsearch_url: str = Field(default="http://localhost:9200")
    elasticsearch_index: str = "moose_chunks"

    # ── Object Storage (S3 / MinIO) ──────────────────────────
    s3_endpoint: Optional[str] = Field(default=None)  # MinIO: http://localhost:9000
    s3_bucket: str = "moose-documents"
    s3_access_key: str = Field(default="minioadmin")
    s3_secret_key: str = Field(default="minioadmin")
    s3_use_ssl: bool = False

    # ── LLM ──────────────────────────────────────────────────
    llm_provider: str = Field(default="deepseek")  # openai | deepseek | anthropic | local
    llm_model: str = Field(default="deepseek-chat")
    llm_fast_model: str = Field(default="deepseek-chat")
    llm_temperature: float = Field(default=0.1, ge=0.0, le=2.0)
    llm_max_tokens: int = 4000
    llm_context_budget: int = 10_000  # Max tokens for retrieved context

    # ── DeepSeek ─────────────────────────────────────────────
    deepseek_api_key: str = Field(default="sk-change-me")
    deepseek_base_url: str = "https://api.deepseek.com"

    # ── OpenAI ───────────────────────────────────────────────
    openai_api_key: str = Field(default="sk-change-me")
    openai_embedding_model: str = "text-embedding-3-large"
    openai_embedding_dimensions: int = 3072
    openai_embedding_batch_size: int = 100

    # ── Anthropic ────────────────────────────────────────────
    anthropic_api_key: str = Field(default="sk-ant-change-me")

    # ── Embedding (self-hosted fallback) ─────────────────────
    embedding_provider: str = Field(default="openai")  # openai | local
    local_embedding_model: str = "BAAI/bge-m3"
    local_embedding_url: Optional[str] = Field(default=None)  # vLLM/TEI endpoint

    # ── Reranker ─────────────────────────────────────────────
    reranker_model: str = "BAAI/bge-reranker-v2-m3"
    reranker_top_k: int = 20
    reranker_final_k: int = 8

    # ── OCR ──────────────────────────────────────────────────
    ocr_default_engine: str = Field(default="tesseract")  # tesseract | textract
    ocr_tesseract_config: str = "--psm 6 -l eng"
    ocr_min_confidence: float = 0.85
    ocr_review_thresholds: dict = Field(default={
        "general_laws": 0.98,
        "constitution": 0.98,
        "officer_handbook": 0.95,
        "social_quarters_rules": 0.95,
        "default": 0.85,
    })

    # ── Retrieval ────────────────────────────────────────────
    retrieval_top_k_vector: int = 20
    retrieval_top_k_keyword: int = 20
    retrieval_rrf_k: int = 60
    retrieval_max_chunks_per_section: int = 3

    # ── Citation ─────────────────────────────────────────────
    citation_min_quote_similarity: float = 0.80

    # ── Auth ─────────────────────────────────────────────────
    auth0_domain: str = Field(default="change-me.auth0.com")
    auth0_audience: str = Field(default="https://api.moose-assistant.org")
    auth0_algorithms: list[str] = Field(default=["RS256"])
    access_token_expire_minutes: int = 60

    # ── Celery ───────────────────────────────────────────────
    celery_broker_url: str = Field(default="redis://localhost:6379/1")
    celery_result_backend: str = Field(default="redis://localhost:6379/2")

    # ── Chunking ─────────────────────────────────────────────
    chunk_target_tokens: int = 600
    chunk_max_tokens: int = 1000
    chunk_overlap_tokens: int = 50

    # ── Monitoring ───────────────────────────────────────────
    sentry_dsn: Optional[str] = Field(default=None)
    log_level: str = "INFO"

    @field_validator("cors_origins", mode="before")
    @classmethod
    def parse_cors_origins(cls, v):
        if isinstance(v, str):
            return [origin.strip() for origin in v.split(",")]
        return v


# Singleton
settings = Settings()
