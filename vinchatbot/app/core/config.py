from functools import lru_cache

from pydantic import Field
from pydantic_settings import BaseSettings, SettingsConfigDict


class Settings(BaseSettings):
    """Runtime configuration loaded from environment variables."""

    model_config = SettingsConfigDict(env_file=".env", env_file_encoding="utf-8", extra="ignore")

    app_name: str = "VinChatbot"
    app_env: str = Field(default="development", validation_alias="APP_ENV")
    default_answer_language: str = Field(default="vi", validation_alias="DEFAULT_ANSWER_LANGUAGE")

    openrouter_api_key: str | None = Field(default=None, validation_alias="OPENROUTER_API_KEY")
    openrouter_base_url: str = Field(
        default="https://openrouter.ai/api/v1", validation_alias="OPENROUTER_BASE_URL"
    )
    openrouter_chat_model: str = Field(
        default="openai/gpt-4o-mini", validation_alias="OPENROUTER_CHAT_MODEL"
    )
    openrouter_embedding_model: str = Field(
        default="openai/text-embedding-3-small", validation_alias="OPENROUTER_EMBEDDING_MODEL"
    )
    openrouter_rerank_model: str = Field(
        default="cohere/rerank-v3.5", validation_alias="OPENROUTER_RERANK_MODEL"
    )
    openrouter_app_referer: str | None = Field(
        default="http://localhost:8000", validation_alias="OPENROUTER_APP_REFERER"
    )
    openrouter_app_title: str | None = Field(
        default="VinChatbot", validation_alias="OPENROUTER_APP_TITLE"
    )

    qdrant_url: str | None = Field(default=None, validation_alias="QDRANT_URL")
    qdrant_api_key: str | None = Field(default=None, validation_alias="QDRANT_API_KEY")
    qdrant_collection: str = Field(
        default="vinuni_documents", validation_alias="QDRANT_COLLECTION"
    )
    qdrant_local_path: str = Field(default="data/qdrant", validation_alias="QDRANT_LOCAL_PATH")
    qdrant_timeout_seconds: int = Field(default=120, validation_alias="QDRANT_TIMEOUT_SECONDS")
    qdrant_batch_size: int = Field(default=16, validation_alias="QDRANT_BATCH_SIZE")
    vector_store_backend: str = Field(default="qdrant", validation_alias="VECTOR_STORE_BACKEND")
    chroma_collection: str = Field(default="vinuni_documents", validation_alias="CHROMA_COLLECTION")
    chroma_persist_dir: str = Field(default="data/chroma", validation_alias="CHROMA_PERSIST_DIR")
    pinecone_api_key: str | None = Field(default=None, validation_alias="PINECONE_API_KEY")
    pinecone_index_name: str = Field(default="vinuni-documents", validation_alias="PINECONE_INDEX_NAME")
    pinecone_namespace: str | None = Field(default=None, validation_alias="PINECONE_NAMESPACE")

    checkpointer_backend: str = Field(default="memory", validation_alias="CHECKPOINTER_BACKEND")
    postgres_uri: str | None = Field(default=None, validation_alias="POSTGRES_URI")

    # Retrieval tuning (Phase 1). Toggle-gated so each lever can be A/B-measured.
    enable_litm_reorder: bool = Field(default=True, validation_alias="ENABLE_LITM_REORDER")
    retrieval_candidate_k: int = Field(default=40, validation_alias="RETRIEVAL_CANDIDATE_K")
    retrieval_min_k: int = Field(default=3, validation_alias="RETRIEVAL_MIN_K")
    retrieval_max_k: int = Field(default=8, validation_alias="RETRIEVAL_MAX_K")
    retrieval_score_ratio: float = Field(default=0.5, validation_alias="RETRIEVAL_SCORE_RATIO")
    enable_dynamic_k: bool = Field(default=True, validation_alias="ENABLE_DYNAMIC_K")
    enable_result_dedup: bool = Field(default=True, validation_alias="ENABLE_RESULT_DEDUP")
    enable_query_expansion: bool = Field(default=True, validation_alias="ENABLE_QUERY_EXPANSION")
    enable_metadata_boost: bool = Field(default=True, validation_alias="ENABLE_METADATA_BOOST")
    enable_soft_routing: bool = Field(default=True, validation_alias="ENABLE_SOFT_ROUTING")

    # Parent-document retrieval (Phase 4). At retrieval time, collapse the fine chunks that
    # share a (parent_doc_id, section_id) into one chunk carrying the full section text:
    # small-chunk match precision, full-section context for the LLM. Retrieval-time only —
    # no re-ingest, A/B-testable on the serving collection. The principled fix for the
    # over-fragmentation that sank the markdown pipeline (Phase 3).
    enable_parent_doc: bool = Field(default=False, validation_alias="ENABLE_PARENT_DOC")
    parent_doc_max_chars: int = Field(default=4000, validation_alias="PARENT_DOC_MAX_CHARS")
    parent_doc_max_siblings: int = Field(default=6, validation_alias="PARENT_DOC_MAX_SIBLINGS")
    # Subcategories opted out of section stitching (comma-separated). Calendar is point-lookup
    # tabular data where expanding the section makes the model over-share adjacent dates.
    parent_doc_skip_subcategories: str = Field(
        default="calendar", validation_alias="PARENT_DOC_SKIP_SUBCATEGORIES"
    )

    # Ingestion v2 (Phase 3) — markdown-first parsing + token/header chunking.
    # Validated and SHELVED: even tuned (PDF-as-text, 1024-token, h1/h2) it netted ~81%
    # vs the proven plain-text pipeline's 92.5% (HTML markdown fragments policy; over-answers).
    # Kept here, OFF by default; flip ENABLE_MARKDOWN_PARSING=true to experiment. See PHASE3_LOG.md.
    enable_markdown_parsing: bool = Field(default=False, validation_alias="ENABLE_MARKDOWN_PARSING")
    enable_pdf_markdown: bool = Field(default=False, validation_alias="ENABLE_PDF_MARKDOWN")
    chunk_max_tokens: int = Field(default=1024, validation_alias="CHUNK_MAX_TOKENS")
    chunk_overlap_tokens: int = Field(default=96, validation_alias="CHUNK_OVERLAP_TOKENS")
    chunk_header_levels: int = Field(default=2, validation_alias="CHUNK_HEADER_LEVELS")

    # Guardrails. Layered: regex/deobf (always) -> safety API (non-confident) -> small-LLM
    # injection+scope classifier. The rule tier runs first so most turns never call an API.
    enable_llm_guard: bool = Field(default=True, validation_alias="ENABLE_LLM_GUARD")
    guard_model: str = Field(
        default="qwen/qwen-2.5-7b-instruct", validation_alias="GUARD_MODEL"
    )
    enable_indirect_injection_scan: bool = Field(
        default=True, validation_alias="ENABLE_INDIRECT_INJECTION_SCAN"
    )
    enable_output_moderation: bool = Field(default=False, validation_alias="ENABLE_OUTPUT_MODERATION")

    # Safety tier (content moderation). Default OpenAI omni-moderation (free/cheapest).
    safety_guard_backend: str = Field(
        default="openai_moderation", validation_alias="SAFETY_GUARD_BACKEND"
    )  # openai_moderation | llama_guard | off
    enable_safety_on_all: bool = Field(default=False, validation_alias="ENABLE_SAFETY_ON_ALL")
    openai_api_key: str | None = Field(default=None, validation_alias="OPENAI_API_KEY")
    openai_base_url: str = Field(
        default="https://api.openai.com/v1", validation_alias="OPENAI_BASE_URL"
    )
    openai_moderation_model: str = Field(
        default="omni-moderation-latest", validation_alias="OPENAI_MODERATION_MODEL"
    )
    llama_guard_model: str = Field(
        default="meta-llama/llama-guard-4-12b", validation_alias="LLAMA_GUARD_MODEL"
    )

    crawl_user_agent: str = Field(
        default="VinChatbotBot/0.1 (+https://vinuni.edu.vn)",
        validation_alias="CRAWL_USER_AGENT",
    )
    crawl_timeout_seconds: float = Field(default=30.0, validation_alias="CRAWL_TIMEOUT_SECONDS")
    crawl_rate_limit_seconds: float = Field(default=1.0, validation_alias="CRAWL_RATE_LIMIT_SECONDS")
    crawl_max_pages_total: int = Field(default=500, validation_alias="CRAWL_MAX_PAGES_TOTAL")
    crawl_max_vinuni_pages_per_domain: int = Field(
        default=50, validation_alias="CRAWL_MAX_VINUNI_PAGES_PER_DOMAIN"
    )
    crawl_max_external_pages_per_domain: int = Field(
        default=10, validation_alias="CRAWL_MAX_EXTERNAL_PAGES_PER_DOMAIN"
    )
    crawl_vinuni_max_depth: int = Field(default=2, validation_alias="CRAWL_VINUNI_MAX_DEPTH")
    crawl_external_max_depth: int = Field(default=1, validation_alias="CRAWL_EXTERNAL_MAX_DEPTH")

    enable_ocr: bool = Field(default=False, validation_alias="ENABLE_OCR")
    ocr_engine: str = Field(default="paddleocr", validation_alias="OCR_ENGINE")
    ocr_lang: str = Field(default="en", validation_alias="OCR_LANG")
    ocr_model: str = Field(default="PP-OCRv5", validation_alias="OCR_MODEL")
    ocr_max_image_mb: int = Field(default=5, validation_alias="OCR_MAX_IMAGE_MB")
    ocr_max_pdf_pages: int = Field(default=20, validation_alias="OCR_MAX_PDF_PAGES")
    ocr_min_text_chars_per_page: int = Field(
        default=40, validation_alias="OCR_MIN_TEXT_CHARS_PER_PAGE"
    )
    ocr_store_text: bool = Field(default=True, validation_alias="OCR_STORE_TEXT")
    ocr_store_boxes: bool = Field(default=False, validation_alias="OCR_STORE_BOXES")

    enable_image_asset_extraction: bool = Field(
        default=True, validation_alias="ENABLE_IMAGE_ASSET_EXTRACTION"
    )
    image_download_enabled: bool = Field(default=False, validation_alias="IMAGE_DOWNLOAD_ENABLED")
    image_max_asset_mb: int = Field(default=5, validation_alias="IMAGE_MAX_ASSET_MB")
    image_description_mode: str = Field(default="context", validation_alias="IMAGE_DESCRIPTION_MODE")

    raw_data_dir: str = Field(default="data/raw", validation_alias="RAW_DATA_DIR")
    processed_data_dir: str = Field(default="data/processed", validation_alias="PROCESSED_DATA_DIR")


@lru_cache
def get_settings() -> Settings:
    return Settings()
