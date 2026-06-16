# VinChatbot — Project Assessment & Future Improvements

> **Status: forward-looking reference, not an active work plan.** A whole-project assessment with
> research-backed improvement ideas and TODOs, to look into later. Focus is **depth on the
> AI/RAG/eval/backend parts**; the platform layer (auth/UI/admin/deploy) is a **course-brief
> requirement owned by teammates** and appears here as hand-off specs, not detailed implementation.
> Authored 2026-06-14. Companion to [PROJECT_JOURNAL.md](PROJECT_JOURNAL.md),
> [UPDATE_PLAN.md](UPDATE_PLAN.md), and the phase logs.

## Where the project stands

The RAG/agent core is production-grade (**0.919** on 86 golden cases; the faithfulness output-gate
bug was fixed — see [PHASE1.4_LOG.md](LOGS/PHASE1.4_LOG.md)). The platform the course brief mandates (deployed
web app with login/roles/admin/chat-history) is **~0% built**. The highest-leverage *AI-side* gaps are
**evaluation rigor**, **retrieval depth (contextual + adaptive)**, **data-quality at index time**,
**observability**, and **backend resilience** — not the core agent loop, which is strong.

### Maturity scorecard

| Subsystem | Maturity | One-line state |
|---|---|---|
| Core RAG + multi-agent | ●●●●○ | Hybrid+RRF+**fuse-rerank-once (1.6)**+boosts+dynamic-k+LITM+**adaptive point-lookup routing & full-section reading (1.7)**; supervisor→4 specialists. Strong. |
| Guardrails / safety | ●●●●○ | Layered regex→moderation→LLM injection/scope + output checks. Strong. |
| Generation / prompts | ●●●○○ | Versioned specialist prompts (+ flag-gated strict point-lookup suffix, 1.7); EN→VI language leak + no structured procedure output. |
| **Evaluation / testing** | ●●●○○ | **130 cases (1.7)** + `run_eval.py --diff` (per-case flips/deltas). Still token-match only; **no retrieval recall, LLM-judge, multi-run averaging** (single-run noise ~±3 cases). |
| Data quality / ingest | ●●●○○ | Rich extraction; **dedup exact-hash only, heuristic metadata, OCR off, regex-fragile calendar/fee.** |
| Backend / API | ●●○○○ | Minimal FastAPI; request IDs added (1.5a); still no lifespan, streaming, retries, rate limiting. |
| Observability | ●●●○○ | **1.5a/b done:** JSON logs + correlation IDs + per-turn cost/tokens + Langfuse tracing. Remaining (1.5c): metrics endpoint, dashboards, alerts/SLO, feedback loop. |
| Platform (auth/UI/admin/deploy) | ○○○○○ | **Not started — brief requirement, teammates own.** |

---

## PART 1 — AI / RAG / backend deep-dives (the focus)

### A. Evaluation & Testing — *highest priority (it gates every other improvement)*

**Now:** `scripts/run_eval.py` — token-subset fact matching + citation-substring + refusal detection;
**130 golden cases (1.7)** incl. a `calendar_pointlookup` category with adjacent-date distractors +
cross-lingual fee + multilingual guard cases; **`--diff <report>`** prints per-case flips +
per-category deltas (1.7); nightly `eval.yml`. **Gaps:** **single-run noise ~±3 cases** (a 30-case
category swung ±0.10 on identical logic) → need **multi-run averaging / lower-variance harness**; no
retrieval metrics (recall@k/nDCG/MRR), no LLM-as-judge, partly circular golden set, no per-specialist
scores.

**Why it's #1:** improvements are measured against a noisy ±2-case token matcher; we can't see *where*
retrieval fails (recall) vs *where* generation fails. 2026 practice treats eval infra as a
prerequisite, with the RAGAS four-metric pattern (faithfulness, answer relevance, context precision,
context recall) + LLM-as-judge as the standard ([RAGAS/TruLens/DeepEval — Atlan](https://atlan.com/know/llm-evaluation-frameworks-compared/),
[RAG eval metrics 2026 — PremAI](https://blog.premai.io/rag-evaluation-metrics-frameworks-testing-2026/),
[Future AGI](https://futureagi.com/blog/what-is-rag-evaluation-2026)).

**Proposals**
- **Retrieval-layer metrics:** `recall@k`, `MRR`, `nDCG` by annotating golden cases with
  `expected_chunk`/`expected_source`, scoring the retriever *before* generation — separates retrieval
  failures from generation failures.
- **LLM-as-judge tier:** optional judge (gpt-4o-mini/Claude) scoring faithfulness + answer relevance for
  semantic equivalence, alongside the cheap token matcher; gate behind `--judge` so the cheap tier stays
  the CI default. Kills morphological/format false-fails.
- **Per-specialist + per-category** retrieval-recall breakdown.
- **Regression tracking:** persist `baseline.json`; `run_eval.py` diffs vs baseline and flags per-case
  flips (done by hand all session — automate it).
- **Latency + token/cost capture** per case → trend file.
- **Held-out non-circular set:** author cases from *student questions*/paraphrases, not the source docs.
- **Adopt a framework selectively:** wrap RAGAS/DeepEval metrics; keep our harness as the runner.

### B. Retrieval & RAG — *biggest quality lever after eval*

**Now:** adaptive (1.7) — router (`is_point_lookup`) → expansion (calendar OFF / financial ON +
**cross-lingual EN variant**) → per-variant candidates → RRF fuse → **rerank ONCE (1.6)** → boosts →
dynamic-k → **full-section reading for point-lookups** → LITM → injection scan. **Done in 1.6/1.7:**
fuse-rerank-once (cost), point-lookup precision (calendar wrong-date fixed), cross-lingual fee recall
(VI→EN nursing misses fixed). **Remaining gaps:** (1) calendar "period"/grade-release **persistent
fails** — wrong-document (calendar PDF loses to registrar blogs) + cross-term confusion → wants a
**structured calendar lookup** (calendar_event records already exist, PHASE1.0) and/or a
**calendar-source boost**; (2) off-domain pages outrank routed docs (soft-routing boost weak);
(3) **Contextual Retrieval not implemented**.

**Proposals (research-backed)**
- **Contextual Retrieval (Anthropic):** prepend a 1–2 sentence LLM context to each chunk before
  embed/BM25 → **−49% retrieval failures (−67% with rerank)**
  ([Anthropic](https://www.anthropic.com/news/contextual-retrieval)). One-time ingest cost;
  `ENABLE_CONTEXTUAL_CHUNKS`; cache by `content_hash`. **Highest single retrieval lift.**
- **Adaptive RAG (query-complexity router):** classify each query → *skip retrieval* (chit-chat),
  *single-hop* (most factual lookups, 60–70% of traffic), or *agentic multi-hop* with a tight iteration
  budget ([Agentic RAG survey arXiv:2501.09136](https://arxiv.org/abs/2501.09136),
  [Adaptive RAG patterns 2026](https://www.digitalapplied.com/blog/agentic-rag-patterns-multi-step-reasoning-guide),
  [MarsDevs 2026 guide](https://www.marsdevs.com/guides/agentic-rag-2026-guide)).
- **Cross-lingual fix:** add an EN translation of VN queries to the multi-query set (or multilingual
  rerank) so VN questions match EN tariff/policy tables. Targets the financial miss.
- **Routed-domain sharpening:** add a mild *off-category penalty* (not just an in-category boost) in
  `apply_metadata_boosts` so off-domain pages stop outranking the routed doc — measure carefully.
- **Structured calendar/fee KB:** store calendar_event/fee_record as queryable rows (date-range, program
  filter) so "next deadline after Sept 15" and program-fee disambiguation become lookups.
- **Parent-document retrieval** already built+gated (`ENABLE_PARENT_DOC`) — revisit once contextual+
  markdown are in.

### C. Agents & Orchestration

**Now:** supervisor → 1 of 4 ReAct specialists, in-process LangGraph, no MCP/A2A. **Gaps:** every query
runs the full agent loop (no complexity gating); no reflection/self-correction; iteration cost unbounded.

**Proposals**
- **Wire the adaptive router** (B) as the supervisor's first step → skip/single-hop/agentic with explicit
  **iteration budgets** (agentic RAG is 3–10× tokens / 2–5× latency, worth it only on hard queries —
  [MarsDevs](https://www.marsdevs.com/guides/agentic-rag-2026-guide)).
- **Reflection loop** for low-confidence answers: one self-check "is this fully supported by context?"
  before the output gate.
- Keep **MCP/A2A deferred** (future hooks); not worth it for an in-process single service.

### D. Data Quality & Ingestion

**Now:** `httpx` crawler (no JS execution); exact content-hash dedup + post-retrieval Jaccard@0.9;
heuristic `infer_category`; regex calendar/fee extraction; boilerplate static list; OCR off; image
download off; English-only language detection.
**Gaps:** near-dup policy PDF/HTML copies survive to index; calendar/fee regex fragile; VN OCR absent;
noisy outlinks (link_references 22MB) not pruned; **JS-rendered sites return only stubs** to the
`httpx` crawler; **image-borne content is not read** (OCR + image download both off).

**Proposals**
- **Index-time near-dup dedup** (MinHash/SimHash or embedding-cosine) so PDF/HTML twins collapse before
  embedding ([Databricks data-quality for RAG](https://docs.databricks.com/aws/en/generative-ai/tutorials/ai-cookbook/quality-data-pipeline-rag)).
- **Harden structured extraction** → the structured KB (B); table-aware fee parsing for prose-embedded
  amounts.
- **Quality filter:** drop low-signal chunks (nav stubs like the `Quick links` 393-char page) via a
  length/entropy heuristic at ingest.
- **VN OCR** (PaddleOCR `OCR_LANG=vi`) for scanned VN policy PDFs; evaluate accuracy on a sample.
- **Headless-fetch for JS-rendered sites + image OCR — `experience.vinuni.edu.vn` (NEW SEED):** the
  student-life hub is promising but JavaScript-rendered (the `httpx` crawler got only a 393-char
  "Quick links" stub) **and** its substance is in *contextful images*. To ingest it needs three things
  together: (1) a **headless/Playwright fetch path** in the crawler for JS-heavy hosts, (2)
  `IMAGE_DOWNLOAD_ENABLED=true`, and (3) `ENABLE_OCR=true` with `OCR_LANG=vi` (the
  `assets.py`/`ocr.py` PaddleOCR PP-OCRv5 pipeline already exists, just disabled). This is the path to
  the health/counseling/career/housing/student-life domains that the policy-site crawl can't reach.
- **Contextual chunks** (shared with B) is also a data-quality upgrade.

### E. Guardrails & Safety

**Now:** regex/deobf → OpenAI omni-moderation (non-confident only) → qwen injection/scope; output =
secret-leak + citation + faithfulness (fixed) + indirect-injection scan on retrieved text.
**Gaps:** `ENABLE_OUTPUT_MODERATION=false`; jailbreak set small. *(Note: the reranker already
fails open — `OpenRouterReranker.rerank` catches all errors and falls back to original order.)*

**Proposals**
- **Expand the adversarial/jailbreak eval set** (multilingual role-play, many-shot, encoded payloads);
  track guard recall as a metric.
- **Decide output-moderation policy** (cost vs safety) — measure latency/cost of turning it on.
- **Guard observability:** log guard decisions + costs into the tracing layer (H).

### F. Generation & Prompts

**Now:** versioned prompts (`phase0-v1`), 4 specialist prompts. **Findings:** larger model (gpt-4o) was a
wash vs gpt-4o-mini; prompt tightening was net-negative; an **EN-question→VN-answer leak** exists when
retrieved docs are VN.

**Proposals**
- **Fix the language leak:** enforce answer language from the *question* (the directive exists but the
  model follows retrieved-doc language) — post-generation language check/repair.
- **Structured procedure output** (User Story 2 / FR5): typed schema (conditions → steps → documents →
  contact → notes → sources) the frontend renders as cards.
- **Prompt registry + versioning** tied to eval runs (which prompt version scored what).
- Stay on **gpt-4o-mini** (proven; upgrade not worth cost).

### G. Backend / API / Serving

**Now:** minimal `create_app()`; `/health`, `/chat`, `/ingest/run`, `/sources`; no lifespan, middleware,
streaming, retries, request IDs, rate limiting; checkpointer in-memory by default.

**Proposals**
- **Lifespan startup:** build the vector store / warm the agent at boot (currently lazy → cold-start).
- **Streaming responses (SSE)** for chat — needed for the UI and the latency target.
- **Resilience:** retry+timeout wrappers on OpenRouter (chat/embed/rerank) and Qdrant. *The OpenRouter
  `403 Key limit` hit this session would have been caught by a retry/clear-error path.*
- **Request IDs + structured logs** (feeds H); **exception handlers** → typed error envelopes.
- **Switch checkpointer to Postgres** for real chat-history persistence (scaffolding already in
  `vinuni_agent.py`).
- Expose the **integration seams teammates need** (see Part 2).

### H. Observability & Ops — *cheap, high-leverage, enables everything else*

**Done — Phase 1.5a/b** (see [LOGS/PHASE1.5_LOG.md](LOGS/PHASE1.5_LOG.md)): structured JSON logging +
`X-Request-ID` correlation + PII redaction; per-turn token/cost capture (structured `chat_turn` line);
**Langfuse tracing** wired at `build_chat_model` (every LLM call) with session grouping + email/phone
masking. `langfuse` is an `observability` optional extra; all fail-open.

**Remaining — Phase 1.5c (the full SRE stack; deferred here as future work):**
- **`/metrics` Prometheus endpoint** (`prometheus-fastapi-instrumentator`): request rate, latency
  histogram P50/95/99, error counter + custom token/cost/guardrail/tool-success metrics. Gated
  `ENABLE_METRICS`.
- **Grafana dashboard** (3-layer: golden signals → AI metrics → per-route), JSON committed under `ops/`.
- **≥3 symptom-based alerts** (P95 latency, error rate, daily-cost spike) + **1 SLO + error budget** +
  Slack webhook (`SLACK_WEBHOOK_URL`).
- **Readiness probe** checking Qdrant + OpenRouter reachability (current `/health` always 200).
- **Online feedback endpoint** (`POST /chat/feedback`, 👍/👎 keyed by `request_id`) → online quality
  proxy feeding the held-out eval set (A). *(Langfuse can also capture scores via its API.)*
- **TTFT** needs SSE streaming (see G) — stretch.

Research refs: [Langfuse](https://langfuse.com/docs/observability/overview),
[LLM observability 2026 comparison](https://explore.n1n.ai/blog/llm-observability-langfuse-langsmith-opentelemetry-2026-05-17).

---

## PART 2 — Platform hand-off specs (teammates own; brief requirement)

Concise contracts so teammates can build in parallel against a stable backend.

- **Auth/roles (FR6, User Story 3):** email/password → JWT; roles `student` | `admin`; FastAPI dependency
  guards (`/chat` student+, `/ingest/*` and `/sources` admin-only). Backend exposes `/auth/login`,
  `/auth/me`. Postgres `users(id,email,hash,role)`.
- **Chat history (FR8):** Postgres `conversations` + `messages(conversation_id,user_id,role,content,
  citations_json,ts)`; persist each `/chat` turn (switch checkpointer to Postgres). `GET /conversations`,
  `GET /conversations/{id}`.
- **Admin doc management (FR7, User Story 4):** `/ingest/run` exists — add an **admin gate** + a
  `documents` source-registry table (`status: pending|indexed|failed`, `chunk_count`, `updated_at`) +
  `POST /admin/documents` (upload PDF/DOCX/URL), `POST /admin/documents/{id}/reindex`, `DELETE`. Object
  storage (Supabase/S3) for uploads.
- **Frontend (React/Next + Tailwind):** consume the **existing stable contract** — `ChatRequest`
  `{message,conversation_id,filters}` → `ChatResponse` `{answer,citations[],confidence,tool_trace,
  needs_human_review}`. Build: login, student chat (sidebar history, citation cards, quick-prompt chips,
  feedback buttons), admin dashboard (Documents/Upload/Chat-logs/Unanswered tabs). Needs **SSE streaming**
  (G).
- **Deployment (brief §4.3):** `Dockerfile` + `docker-compose` (app + Postgres; Qdrant Cloud already
  hosted); backend → Render/Railway/Fly, frontend → Vercel; secrets via platform env (key-rotation
  discipline matters).

---

## PART 3 — Suggested sequence (AI-depth first)

1. **Eval framework (A)** — do first; everything else is measured by it.
2. **Observability (H)** — Langfuse tracing + cost capture; cheap, prevents another quota blind-spot.
3. **Contextual Retrieval (B)** — headline retrieval lift; measure with the new eval.
4. **Adaptive routing + reflection (B/C)** — cost-aware, improves hard queries.
5. **Data-quality at index (D)** — near-dup dedup, quality filter, structured KB.
6. **Cross-lingual + routed-domain retrieval fixes (B)** — closes the financial/VN gaps.
7. **Backend resilience + streaming + Postgres history (G)** — also unblocks the platform team.
8. **Generation polish (F)** — language-repair, structured procedure output.
9. **Guardrail hardening (E)** — reranker fail-open, jailbreak set.
10. **Phase 2 — personalization** (mock student DB, PRD §10) and **Phase 3 — platform** (teammates; Part 2).

Each item: toggle-gated where it touches serving, A/B-measured on the upgraded eval, `pytest -m "not live"`
+ `ruff` green, scratch-collection discipline, **one eval at a time** (lessons in LOGS/PHASE1.4_LOG.md).

---

## Consolidated TODO checklist
- [~] **Eval:** [x] eval set 86→130 + `--diff` regression tooling (1.7) — [ ] remaining: **multi-run averaging** (single-run noise ~±3 cases); retrieval recall@k/MRR/nDCG; LLM-judge tier; held-out set
- [x] **Observability (1.5a/b done):** JSON logging + correlation IDs + per-turn cost/tokens + Langfuse tracing — [ ] remaining (1.5c): Prometheus `/metrics` + Grafana dashboard; ≥3 alerts + SLO/error-budget; readiness probe; feedback endpoint
- [~] **Retrieval:** [x] fuse-rerank-once (1.6); adaptive point-lookup router + full-section + cross-lingual query (1.7) — [ ] remaining: structured calendar lookup; calendar-source boost; contextual chunks; off-category penalty
- [ ] **Agents:** complexity gate + iteration budget; reflection step
- [ ] **Data:** index-time near-dup dedup; quality filter; VN OCR; table-aware fee parse; headless/JS fetch + image OCR for `experience.vinuni.edu.vn` (student-life/health/career/housing seed)
- [ ] **Backend:** lifespan warmup; SSE streaming; LLM/Qdrant retries; request IDs; Postgres checkpointer
- [ ] **Generation:** language-repair; structured procedure schema; prompt registry
- [ ] **Guardrails:** expand jailbreak set; output-moderation cost eval; resilience retries on guard/LLM calls
- [ ] **Platform (teammates):** auth/roles; chat-history; admin doc mgmt + source registry; frontend; Docker+deploy
- [ ] **Stretch:** mock student DB personalization
