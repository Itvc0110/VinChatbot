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

    checkpointer_backend: str = Field(default="memory", validation_alias="CHECKPOINTER_BACKEND")
    postgres_uri: str | None = Field(default=None, validation_alias="POSTGRES_URI")

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
