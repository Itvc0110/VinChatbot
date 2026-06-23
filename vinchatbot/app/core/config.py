from functools import lru_cache

from pydantic import Field
from pydantic_settings import BaseSettings, SettingsConfigDict


class Settings(BaseSettings):
    """Runtime configuration loaded from environment variables."""

    model_config = SettingsConfigDict(env_file=".env", env_file_encoding="utf-8", extra="ignore")

    app_name: str = "VinChatbot"
    app_env: str = Field(default="development", validation_alias="APP_ENV")
    default_answer_language: str = Field(default="vi", validation_alias="DEFAULT_ANSWER_LANGUAGE")

    # Time awareness (Phase 1.9). Inject today's date + current academic year/term into each turn so
    # the bot can answer "what semester am I in?" / "how long until X?". Fail-open: a tz/lookup error
    # just skips the preamble. Also exposes a get_current_datetime tool + a deterministic responder.
    enable_time_awareness: bool = Field(default=True, validation_alias="ENABLE_TIME_AWARENESS")

    # Rate limiting (Phase 1.10). Per-process sliding window on the API to curb abuse / runaway cost.
    # OFF by default (eval/CI unaffected); keyed by client IP. Multi-replica → use a shared store (Redis).
    rate_limit_enabled: bool = Field(default=False, validation_alias="RATE_LIMIT_ENABLED")
    rate_limit_max_requests: int = Field(default=30, validation_alias="RATE_LIMIT_MAX_REQUESTS")
    rate_limit_window_seconds: int = Field(default=60, validation_alias="RATE_LIMIT_WINDOW_SECONDS")

    # Observability (Phase 1.5a). Structured logging + per-turn cost/token capture. All
    # fail-open and behavior-preserving; log_format=auto -> json in prod, text in dev.
    log_format: str = Field(default="auto", validation_alias="LOG_FORMAT")  # auto | json | text
    log_level: str = Field(default="INFO", validation_alias="LOG_LEVEL")
    log_redact_pii: bool = Field(default=True, validation_alias="LOG_REDACT_PII")
    enable_cost_tracking: bool = Field(default=True, validation_alias="ENABLE_COST_TRACKING")

    # Langfuse tracing (Phase 1.5b). Fail-open: off unless enabled AND both keys are present.
    enable_langfuse: bool = Field(default=False, validation_alias="ENABLE_LANGFUSE")
    langfuse_public_key: str | None = Field(default=None, validation_alias="LANGFUSE_PUBLIC_KEY")
    langfuse_secret_key: str | None = Field(default=None, validation_alias="LANGFUSE_SECRET_KEY")
    langfuse_host: str = Field(
        default="https://cloud.langfuse.com", validation_alias="LANGFUSE_HOST"
    )

    openrouter_api_key: str | None = Field(default=None, validation_alias="OPENROUTER_API_KEY")
    openrouter_base_url: str = Field(
        default="https://openrouter.ai/api/v1", validation_alias="OPENROUTER_BASE_URL"
    )
    openrouter_chat_model: str = Field(
        default="openai/gpt-4o-mini", validation_alias="OPENROUTER_CHAT_MODEL"
    )
    # Answer/routing temperature (Phase 1.11). 0.0 = deterministic answers (the consistency fix);
    # the proven root of "same question, different answer" was sampling. Raise toward 0.1–0.3 only if
    # answer diversity is wanted at the cost of run-to-run stability. Guard models keep their own temp.
    llm_temperature: float = Field(default=0.0, validation_alias="LLM_TEMPERATURE")
    # ReAct loop bound (Phase 1.17): max LangGraph super-steps per specialist turn. Agent-decided
    # cross-lingual adds ~one retry tool call (~2 steps); this caps runaway loops while leaving room for
    # native-search → cross_lingual retry → get_source_detail → answer. ~2 super-steps per tool call.
    agent_recursion_limit: int = Field(default=18, validation_alias="AGENT_RECURSION_LIMIT")
    # Embedding model (Phase 1.14): multilingual-e5-large via OpenRouter is the production default —
    # 12/12 on the VI↔EN cross-lingual probe (vs 11/12 for OpenAI 3-small/3-large), no extra key, 1024-d.
    openrouter_embedding_model: str = Field(
        default="intfloat/multilingual-e5-large", validation_alias="OPENROUTER_EMBEDDING_MODEL"
    )
    # Embedding backend (Phase 1.14): "openrouter" = OPENROUTER_EMBEDDING_MODEL via OpenRouter API;
    # "fastembed_local" = a local multilingual model (no key, no per-query cost, deterministic).
    # The probe showed multilingual-e5-large beats OpenAI 3-small/3-large on VI<->EN cross-lingual.
    embedding_backend: str = Field(default="openrouter", validation_alias="EMBEDDING_BACKEND")
    local_embedding_model: str = Field(
        default="intfloat/multilingual-e5-large", validation_alias="LOCAL_EMBEDDING_MODEL"
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
    # Phase 1.23d (determinism): Qdrant hybrid (HNSW dense + sparse + RRF) returns a slightly different
    # candidate SET at the candidate_k boundary across runs (approximate-search jitter; search_params like
    # hnsw_ef/exact don't reach the dense leg through the langchain hybrid path). That set churn busts the
    # rerank + answer caches → run-to-run noise. Fix: OVER-FETCH `candidate_k + margin` then deterministically
    # truncate back to `candidate_k` (after the rounded-score+chunk_id sort) so the jitter lives in the
    # DISCARDED tail and the reranked pool is stable. Default 0 = OFF = byte-identical (no over-fetch, no
    # truncate). Empirically margin>=16 stabilized the worst-jitter query over 12 runs; 24 gives headroom.
    retrieval_overfetch_margin: int = Field(default=0, validation_alias="RETRIEVAL_OVERFETCH_MARGIN")
    retrieval_min_k: int = Field(default=3, validation_alias="RETRIEVAL_MIN_K")
    retrieval_max_k: int = Field(default=8, validation_alias="RETRIEVAL_MAX_K")
    # Phase 1.27/A6 list mode: multi-row "list" questions ("tuition for ALL programs") need a WIDER context
    # to surface every row, the opposite of the point-lookup narrowing. When enable_list_mode + is_list_lookup,
    # the search uses retrieval_list_max_k instead of retrieval_max_k. Default off → byte-identical.
    enable_list_mode: bool = Field(default=False, validation_alias="ENABLE_LIST_MODE")
    retrieval_list_max_k: int = Field(default=20, validation_alias="RETRIEVAL_LIST_MAX_K")
    retrieval_score_ratio: float = Field(default=0.5, validation_alias="RETRIEVAL_SCORE_RATIO")
    enable_dynamic_k: bool = Field(default=True, validation_alias="ENABLE_DYNAMIC_K")
    enable_result_dedup: bool = Field(default=True, validation_alias="ENABLE_RESULT_DEDUP")
    enable_query_expansion: bool = Field(default=True, validation_alias="ENABLE_QUERY_EXPANSION")
    enable_metadata_boost: bool = Field(default=True, validation_alias="ENABLE_METADATA_BOOST")
    enable_soft_routing: bool = Field(default=True, validation_alias="ENABLE_SOFT_ROUTING")
    # Rerank-after-fusion (Phase 1.6): on multi-query turns, retrieve each variant WITHOUT
    # reranking, RRF-fuse, then rerank the fused pool ONCE (1 Cohere call instead of one per
    # variant — ~67% rerank-cost cut). SHIPPED ON: A/B accepted a ~1-case tradeoff (0.930->0.919)
    # for the cost cut. Known sensitive spot: calendar point-lookups (see PHASE1.6_LOG.md).
    enable_rerank_after_fusion: bool = Field(
        default=True, validation_alias="ENABLE_RERANK_AFTER_FUSION"
    )
    # Adaptive retrieval (Phase 1.7, SHIPPED): route point-lookup queries to full-section reading +
    # a strict extraction prompt so exact-row answers stop losing to adjacent distractor rows.
    # Domain split: calendar point-lookups drop query expansion (precision); financial/other keep it
    # and add a cross-lingual variant (recall). A/B fixed the calendar wrong-date + VI→EN fee misses,
    # guards 1.000 (overall is eval-noise-band; see PHASE1.6/1.7 logs).
    enable_adaptive_retrieval: bool = Field(
        default=True, validation_alias="ENABLE_ADAPTIVE_RETRIEVAL"
    )
    # Structured lookup (CODEX P0, default off → A/B before promote): for exact date/amount point-lookups
    # (calendar now; fees in Stage 2), consult a DETERMINISTIC record index BEFORE vector search and
    # return the one exact row — never the adjacent near-identical row that vector retrieval leaks. Reads
    # the structured records already produced at ingest (no re-embedding). Fail-open: any miss/error →
    # the existing vector path runs unchanged. Empty path → <processed_data_dir>/structured_records.json.
    enable_structured_lookup: bool = Field(
        default=False, validation_alias="ENABLE_STRUCTURED_LOOKUP"
    )
    structured_lookup_records_path: str = Field(
        default="", validation_alias="STRUCTURED_LOOKUP_RECORDS_PATH"
    )
    # Cross-lingual policy retrieval (Phase 1.20, default off → A/B): VI policy questions systematically
    # rank the (often EN) canonical policy doc below VI governance PDFs — the EN twin retrieves it #1. For a
    # VI question routed to the policy domain, force the EN cross-lingual variant so the canonical doc is
    # RRF-fused in. Calendar/financial are excluded (structured lookup / precision-sensitive).
    enable_crosslingual_policy: bool = Field(
        default=False, validation_alias="ENABLE_CROSSLINGUAL_POLICY"
    )
    # Canonical policy-page boost (Phase 1.20, default off → A/B): for policy-domain queries, boost the
    # canonical all-policies detail pages (document_type policy_html / financial_policy) over governance-reg
    # PDFs (policy_pdf), so the dedicated policy page ranks above general regulations.
    enable_canonical_policy_boost: bool = Field(
        default=False, validation_alias="ENABLE_CANONICAL_POLICY_BOOST"
    )
    # Policy doc-pin (Phase 1.21, default off → A/B): the canonical-boost (above) was rejected — a score
    # nudge can't move which DOCUMENT is cited (the magnet PDF / the page's own PDF twin / on-topic
    # non-policy pages out-rank the canonical page with gaps too large for any boost). Instead, when a
    # policy question confidently names ONE curated student-facing topic, fetch that canonical page by
    # source_url and PIN it to the front of the context (deterministic doc selection, mirrors structured
    # lookup). Single-winner + fail-open: 0 or >1 topic matches ⇒ unchanged vector path.
    enable_policy_doc_pin: bool = Field(
        default=False, validation_alias="ENABLE_POLICY_DOC_PIN"
    )
    # Policy auto-index (Phase 1.24, default off → A/B): when on, the doc-pin's curated 17-topic map gets an
    # ingest-built FALLBACK (data/processed/policy_topic_index.json — title-overlap single-winner) covering
    # all ~155 canonical pages + future uploads. Default OFF: the 155-page index over-matches some
    # adversarial/safety/unanswerable queries (guards run independently of retrieval so should still refuse,
    # but that needs A/B confirmation) — kept inert until then. Curated map is always the precedence path.
    enable_policy_auto_index: bool = Field(
        default=False, validation_alias="ENABLE_POLICY_AUTO_INDEX"
    )
    # Mass cache (Phase A2c): exact-match Redis cache of LLM responses + rerank scores, keyed on the FULL
    # prompt/content (→ reproducible A/Bs AND cheaper). Fail-open: no REDIS_URL / any redis error ⇒ cache
    # MISS, never an exception. Keys namespaced by CACHE_VERSION (bump to invalidate after a logic-only
    # change that doesn't alter the keyed inputs). TTL bounds growth under the 30 MB DB.
    redis_url: str | None = Field(default=None, validation_alias="REDIS_URL")
    enable_llm_cache: bool = Field(default=False, validation_alias="ENABLE_LLM_CACHE")
    enable_rerank_cache: bool = Field(default=False, validation_alias="ENABLE_RERANK_CACHE")
    cache_version: str = Field(default="v1", validation_alias="CACHE_VERSION")
    cache_ttl_seconds: int = Field(default=2592000, validation_alias="CACHE_TTL_SECONDS")  # 30d; 0 = no expiry
    # Router v2 (Phase 1.23c, default off → A/B): hardened SUPERVISOR_SYSTEM (route by INTENT — "WHEN does X
    # happen" → calendar vs "is there a rule/process for X" → policy; fixes the courseeval-vi mis-route) +
    # deterministic-first gate (a strong, unambiguous keyword signal routes WITHOUT the LLM). Fail-safe: off
    # = current router behaviour byte-identical.
    enable_router_v2: bool = Field(default=False, validation_alias="ENABLE_ROUTER_V2")
    # Cross-lingual expansion (Phase 1.8). ALWAYS-ON translation, default OFF since Phase 1.14: the e5
    # multilingual embedding matches VI↔EN natively, so the always-on LLM translation is unnecessary
    # noise + the dominant run-to-run nondeterminism source (it hurt VI calendar in the 1.14 A/B). Set
    # True only to force translation on every query. Cross-lingual is instead AGENT-DECIDED + applied as
    # the deterministic REACTIVE second loop (only when the native pass is weak) — see tools._search.
    enable_crosslingual_expansion: bool = Field(
        default=False, validation_alias="ENABLE_CROSSLINGUAL_EXPANSION"
    )
    # Reactive expansion (Phase 1.11): ONE deterministic query first (single-query retrieval is proven
    # stable run-to-run), keeping the VI<->EN cross-lingual translation ON for recall but gating the
    # same-language PARAPHRASE flood — fan out to paraphrases ONLY when the result is weak (top score <
    # reactive_expansion_min_score). Fixes the substance-inconsistency root (expansion churn) + cuts
    # cost. SHIPPED ON: A/B 0.885 -> 0.923 (guards 1.000), probe substance 8/9 stable citations.
    enable_reactive_expansion: bool = Field(
        default=True, validation_alias="ENABLE_REACTIVE_EXPANSION"
    )
    reactive_expansion_min_score: float = Field(
        default=0.35, validation_alias="REACTIVE_EXPANSION_MIN_SCORE"
    )
    # Date-format normalization (Phase 1.12): for a date query, deterministically add the other
    # canonical month+year forms ("tháng 6 năm 2026" <-> "June 2026" <-> "6/2026") to the multi-query
    # set so retrieval is phrasing-independent. Pure regex (no LLM); no-op for non-date queries.
    enable_date_normalization: bool = Field(
        default=True, validation_alias="ENABLE_DATE_NORMALIZATION"
    )

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
    # Soft scope (Phase 1.18, default off): stop hard-refusing on SCOPE. Security tiers
    # (injection/restricted/abuse + safety moderation + injection classifier) still hard-block; only the
    # scope verdict is downgraded to allow, so off-topic falls through to the agent and is refused by
    # graceful-degradation instead of a brittle keyword gate. Off-topic turns still pass the safety +
    # LLM-security tiers first. A/B before flipping (guards must stay 1.000).
    enable_soft_scope: bool = Field(default=False, validation_alias="ENABLE_SOFT_SCOPE")
    enable_output_moderation: bool = Field(default=False, validation_alias="ENABLE_OUTPUT_MODERATION")
    # Output-audit critic (Phase 1.25/B): an LLM groundedness judge (guard_model) that converts
    # confidently-wrong answers into safe graceful-degradations. Scoped to high-stakes point-lookups,
    # fail-OPEN on critic error. Default off; A/B before flipping (guards must stay 1.000, no passing
    # case may degrade).
    enable_output_audit: bool = Field(default=False, validation_alias="ENABLE_OUTPUT_AUDIT")
    # Model for the output-audit critic. Empty → fall back to guard_model (qwen-2.5-7b). Decoupled from
    # guard_model so the groundedness judge can use a more capable model than the input guard without
    # disturbing the input-guard A/B history. Accepts any OpenRouter chat model id.
    output_audit_model: str = Field(default="", validation_alias="OUTPUT_AUDIT_MODEL")

    # Safety tier (content moderation). Default OpenAI omni-moderation (free/cheapest).
    # Content-safety tier (Phase 1.18). openai_moderation (omni-moderation-latest) — FREE + fast; in a
    # head-to-head with a valid key it blocked 8/8 safety cases incl. multilingual harassment that
    # Llama-Guard MISSED, with 0 false positives. (It had silently FAILED OPEN earlier on an invalid
    # OpenAI key — that error is now logged at WARNING in safety_guard, not swallowed.) llama_guard
    # (Llama-Guard-4 via OpenRouter) is the fallback when no valid OpenAI key is present; the qwen
    # injection/scope guard runs alongside as the injection backstop.
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
