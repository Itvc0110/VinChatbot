# VinChatbot — Update Plan / Roadmap (single source of truth)

> Canonical engineering roadmap **and** AI-depth backlog — the single source of truth. The former separate
> backlog (2026-06-17) and the detailed Track-A/B execution plan (`NEXT_UPDATES_PLAN.md`) are **consolidated
> into this file** (2026-06-23, all content kept). **Current detailed state + remaining Track-A/B + deferrals:
> [LOGS/SESSION_CLOSEOUT.md](LOGS/SESSION_CLOSEOUT.md)**; per-sub-phase logs in [LOGS/](LOGS/PHASE1.27_LOG.md).
> Pairs with [PRD.md](PRD.md) / [BRIEF.md](BRIEF.md) / [worklog.md](worklog.md) (submission). **Baseline:
> 0.968/188 golden** ([data/eval/baseline.json](../data/eval/baseline.json)); guards 1.000. Last updated: 2026-06-23.

> **Phase scheme (major phase = a big change):** **Phase 1 — core RAG chatbot (DONE, sub-phases
> 1.0–1.27)** · **Phase 2 — personalization** · **Phase 3 — product & platform**.

Ordering principle: **make it correct and measurable before making it smart.** Every (sub-)phase
ends with a check you can run. Legend: 🔴 blocking bug · 🟠 quality gap · 🟢 new capability.

---

## Phase 1 — Core RAG chatbot (DONE — eval-gated; logs in `LOGS/`)

Built and validated end-to-end (crawl → ingest → chat → eval). **Current: 0.968 on the 188-case golden set**
(`data/eval/baseline.json`), plain-text pipeline, `gpt-4o-mini`, Qdrant Cloud `vinuni_full_e5` (e5-large,
1024-d, ~10,967 points); guards (adversarial/safety/unanswerable) 1.000. Full narrative in
[worklog.md](worklog.md); current state in [LOGS/SESSION_CLOSEOUT.md](LOGS/SESSION_CLOSEOUT.md).

- ✅ **1.0 — Foundation** ([PHASE1.0_LOG.md](LOGS/PHASE1.0_LOG.md)): 761-doc corpus, LangGraph
  supervisor→4 specialists, two-tier CI, eval harness. **0.472**.
- ✅ **1.1 — Quality & Safety** ([PHASE1.1_LOG.md](LOGS/PHASE1.1_LOG.md)): language honoring, LITM
  reorder, dynamic-k, dedup, multi-query+RRF, small-LLM guard + de-obfuscation + indirect-injection
  scan, calendar/fee clean chunks. **0.931** (58).
- ✅ **1.2 — Metadata, layered guards, eval, viz** ([PHASE1.2_LOG.md](LOGS/PHASE1.2_LOG.md)): metadata
  engineering, layered API guard, eval→80, ARCHITECTURE.md. **0.925**, index −33%.
- ⚖️ **1.3 — Ingestion v2: REVERTED** ([PHASE1.3_LOG.md](LOGS/PHASE1.3_LOG.md)): markdown chunking
  ≤81% < 92.5% (broke calendar extraction). Markdown gated off; DOCX kept.
- ✅ **1.4 — Retrieval/eval/fixes** ([PHASE1.4_LOG.md](LOGS/PHASE1.4_LOG.md)): faithfulness
  false-positive fix; conversational-handling fix; parent-doc/gpt-4o/prompt-tightening gated-off or
  rejected; +6 conduct cases (→86). **0.919**.
- ✅ **1.5 — Observability** ([PHASE1.5_LOG.md](LOGS/PHASE1.5_LOG.md)): structured JSON logging +
  `X-Request-ID` + PII redaction + per-turn token/cost; **Langfuse** tracing (opt-in). No regression
  (0.930). 1.5c (Prometheus/Grafana/alerts) deferred — see Ongoing + §H.
- ✅ **1.6 — Rerank cost** ([PHASE1.6_LOG.md](LOGS/PHASE1.6_LOG.md)): rerank the RRF-fused pool
  **once** (~67% fewer rerank calls). Shipped on; accepted a ~1-case tradeoff for cost.
- ✅ **1.7 — Eval expansion + adaptive retrieval** ([PHASE1.7_LOG.md](LOGS/PHASE1.7_LOG.md)): eval
  **86→130** + `run_eval.py --diff`; **adaptive point-lookup routing** (full-section + strict prompt;
  calendar drops paraphrase expansion). Fixed the 1.6 calendar wrong-date. Baseline 0.846.
- ✅ **1.8 — Cross-lingual expansion** (logged in PHASE1.7_LOG.md): bidirectional **VI↔EN** query
  variant, all domains. Production **0.885** — best of the arc; recovered VI→EN fee misses; guards 1.000.

### Phase 1.13–1.27 — quality arc (e5 embeddings → structured lookup → determinism → list mode)
> Per-phase detail in `LOGS/PHASE1.1x–1.27_LOG.md`; current state + deferrals in `LOGS/SESSION_CLOSEOUT.md`.
> Conventions: every behavior `ENABLE_*`-gated + fail-open, guards stay 1.000, one eval at a time, promote
> only winners, log every update (incl. rejections). Baseline climbed 0.885 → **0.968/188**.
- ✅ **1.13/1.14** e5-large embeddings (`vinuni_full_e5`, 1024-d) — best VI↔EN; **1.19–1.21** deterministic
  **structured lookup** (calendar+fee) + **policy doc-pin**; **1.20** cross-lingual policy escalation.
- ✅ **1.22** eval de-noise (`--runs N`, stable-vs-noisy); **1.23a/b** determinism + **Redis LLM/rerank cache**
  (`ENABLE_LLM_CACHE`); **1.23c router-v2 REJECTED**, **1.23d over-fetch SHELVED**.
- ✅ **1.24** policy ingest **auto-index** + long-tail golden; **1.25 Phase A** output-guard hardening
  (de-obfuscated secret scan, `resolve_output_decision`) shipped; **1.25 Phase B critic REJECTED** (gated off,
  kept for future security).
- ✅ **1.27a/b** **list mode** (`ENABLE_LIST_MODE`): fee-matrix + calendar aggregation for "all/each" questions.
- ✅ **1.33** multi-domain **fan-out** PROMOTED (`ENABLE_FAN_OUT` default **ON**): dispatch planner
  (SINGLE / DECOMPOSE / HEDGE) → parallel specialists → synthesis + L2 reactive retry; single path byte-identical
  (single-assignment defers to `route_intent`), same-intent over-fire collapsed. Neutral on the single-domain
  scored set (no regression after the over-fire fix) + adds the multi-domain coverage the single router can't;
  reversible via the flag. Also shipped: fee-lookup **negation-awareness** + chat-client **request
  timeout/retries** (a hung LLM call previously froze the turn). Log `LOGS/PHASE1.33_LOG.md`.
- ⏸ **DEFERRED** (paused for teammate merge): **1.26/A5** refusal & don't-over-refuse (restricted_data hybrid
  → `record-privacy-vi`; soft-scope A/B; clarification → merge) — plan `LOGS/PHASE1.26_PLAN.md`;
  **1.28/A7** contextual retrieval; multi-question decomposition (ReAct covers it) +
  output PII scan; **Track B perf** (1.29 async, B2 semantic cache). Resume order in `SESSION_CLOSEOUT.md`.

---

## Phase 2 — Personalization (mock student system) — NEXT major change

Goal: an authenticated student can ask about themselves, with strict isolation. (BRIEF §5 / PRD §10.)

- 🟢 **Mock student DB.** Postgres schema (PRD §10): `students`, `enrollments`, `student_fees`,
  `student_deadlines` + a realistic seed.
- 🟢 **Profile tools.** `get_student_profile`, `get_student_enrollments`, `get_student_fees`,
  `get_student_deadlines` — each takes the **authenticated** `student_id` from the session, never from
  the prompt.
- 🟢 **Personal vs general intent.** Router decides personal (→ profile tools, +RAG for the governing
  rule) vs general (→ RAG). Personal answers still cite the relevant policy.
- 🟢 **Isolation tests.** Prove user A can never read user B's data via prompt tricks.
- 🟢 **(Extensions, BRIEF §5):** auto-ticket escalation for complex questions; conversation→staff
  handoff summary; deadline reminders/notifications.
- ✅ Acceptance: personalized answers correct against seed data; isolation suite green.

---

## Phase 3 — Product & platform (deployable web app) — FOCUS (graded; currently ~0% built)

Goal: meet the brief's "deployed app with login, roles, history, admin." Build checklist mapped to the
BRIEF user stories / FRs; detailed API/data contracts in **Part 2** below. The current backend exposes
only `/chat`, `/ingest/run`, `/sources`, `/health` (the latter two unauthenticated); `ChatRequest` has
no `user_id`; `agent.ainvoke` is synchronous; the Postgres checkpointer is scaffolded but unused.

- 🟢 **Auth + RBAC** (US3/FR6): `users(id,email,hash,role)`; email/password→JWT/session; FastAPI
  dependency guards — gate the currently-open `/ingest/*` + `/sources` + admin routes; student vs admin.
- 🟢 **Per-user chat history** (FR8): add `user_id` to the session; switch checkpointer to **Postgres**
  (scaffolding in `vinuni_agent.py`); `conversations`/`messages` tables; `GET /conversations`,
  `GET /conversations/{id}`; add migrations (no Alembic yet).
- 🟢 **Admin document management** (US4/FR7): multipart upload (PDF/DOCX/URL) → object storage; a
  `documents` **source registry** (status pending/indexed/failed, chunk_count, updated_at) +
  reindex/delete; admin-gated. (`/ingest/run` exists but is crawl-only + open.)
- 🟢 **SSE streaming** (NFR latency): `agent.ainvoke` → `astream`; also unlocks TTFT (deferred 1.5 metric).
- 🟢 **Frontend** (React/Next + Tailwind): login; student chat (sidebar history, citation cards,
  **procedure cards** US2/FR5, quick-prompt chips, 👍/👎 feedback); admin dashboard tabs
  Documents/Upload/Chat-Logs/Unanswered.
- 🟢 **Ops hardening:** readiness probe (Qdrant/OpenRouter reachability vs the always-200 `/health`),
  rate limiting, structured error envelopes, retry/timeout wrappers, lifespan warmup.
- 🟢 **Deploy:** Dockerfile + docker-compose (api + Postgres; Qdrant Cloud hosted) → Render/Railway/Fly
  + Vercel; **public URL + demo account**; README per BRIEF §4.2.
- ✅ Acceptance: a student logs in, chats, sees history; an admin uploads a doc and sees it indexed;
  reachable at a public URL.

---

## Ongoing — eval, observability, hardening (runs continuously)

- 🟢 **Eval framework:** retrieval recall@k / nDCG, LLM-as-judge tier, run-over-run regression diff
  (`--diff` done 1.7), **multi-run averaging** (single-run noise ~±3 cases), latency/cost capture,
  held-out non-circular set. (See §A.)
- 🟢 **Observability:** Langfuse tracing + token/cost capture **(done 1.5)**; remaining 1.5c = Prometheus
  `/metrics` + Grafana + alerts/SLO + readiness probe + feedback loop. (See §H.)
- 🟢 **Red-team suite** for injection/abuse/secret-leak/private-data, run in CI.
- 🟢 **CI:** `pytest`, `ruff`, `compileall`, nightly eval with a regression gate.

---

## Suggested sequencing (product)

> Confirmed 2026-06-13: ~1–2 month horizon, **public Q&A first**, personalization a stretch.

1. **Phase 1 (1.0–1.8)** — DONE.
2. **Phase 3 (platform)** in parallel (teammates) — auth + minimal UI + deploy on the current backend;
   the brief's graded requirement.
3. **Phase 2 (personalization)** once public Q&A is solid and the mock DB is ready (stretch).
4. **Ongoing** eval/observability/hardening throughout — every change re-scored on the golden set.

---

# Optimization brainstorm (multi-dimension)

Forward-looking levers across cost / performance / quality / features / data / reliability, grounded in
a full repo sweep (2026-06-17). Effort/impact tags are rough. Detailed AI-depth write-ups in Part 1.

### Cost
- 🟢 **Swap answer model** `gpt-4o-mini` → **Gemini 2.5 Flash-Lite** (~33% cheaper, bigger context;
  A/B-gated on the golden set). *(low effort / medium impact)*
- 🟢 **Embedding content-hash cache** — re-index currently re-embeds unchanged chunks (~25–30% waste).
- 🟢 **Embeddings OpenAI-direct / Batch API** (50% off bulk; same vectors → no re-index).
- 🟢 Rerank-once-after-fusion **(done 1.6, ~67% rerank cut)**; consider per-turn rerank cache.
- 🟢 Prompt + hot-Q&A caching; cheaper/free guard model; adaptive **skip-retrieval for chit-chat**;
  skip OCR on 1px tracking pixels.

### Performance / latency
- 🟢 **SSE streaming** (`astream`) — perceived latency + TTFT; needed by the UI.
- 🟢 **Lifespan warmup** — build vector store / warm agent at boot (kills cold-start).
- 🟢 **Retry/timeout + circuit-breaker** on OpenRouter (chat/embed/rerank) + Qdrant.
- 🟢 Fewer ReAct loops (iteration budget); surface P50/95/99 from Langfuse.

### Quality / RAG  (see §A, §B)
- 🟢 **Structured calendar/fee lookup tool** — the persistent calendar "period" + financial fix;
  `calendar_event`/`fee_record` records already exist (currently under-extracted: ~21 calendar vs ~59
  in the PDF, ~36 fee). Pair with **better extraction** (spreadsheet/table → structured records).
- 🟢 **Eval rigor** (highest leverage): scorer morphology/lemmatize + multi-source/language-aware
  `expected_source` (recovers the `policy_conduct` artifact fails), **LLM-judge** tier, **multi-run
  averaging**, retrieval recall@k.
- 🟢 **Calendar-source boost** (Academic Calendar PDF over registrar blogs for calendar queries).
- 🟢 **Contextual Retrieval** (Anthropic) — −49% retrieval failures; near-dup dedup; reflection loop;
  revisit markdown chunking (h1-only).

### New features  (BRIEF §5)
- 🟢 Phase-2 **personalization** (SIS / mock DB); **auto-ticket escalation**; **conversation→staff
  handoff** summary; **deadline reminders/notifications**; **international multilingual**; admin **eval
  dashboard**; **suggested next questions**; 👍/👎 **feedback → held-out eval set**; **GraphRAG** (if
  multi-hop reasoning across regulations becomes necessary).

### Data / coverage  (see §D)
- 🟢 **Headless/JS crawl + VI OCR + image OCR** for `experience.vinuni.edu.vn`
  (health/counseling/career/housing/student-life — unreachable today).
- 🟢 Index-time near-dup dedup; image-clutter quality filter; add `policy_code`/`academic_year`/`term`
  to Qdrant indexed payload fields for filtered retrieval.

### Reliability / ops / security
- 🟢 Auth/RBAC; rate limiting; error envelopes; readiness probe; Postgres history; **secret rotation**
  (live keys currently sit in `.env`).

---

# Project assessment & AI-depth backlog

> Whole-project assessment with research-backed improvement ideas. Focus is **depth on the
> AI/RAG/eval/backend parts**; the platform layer is the graded Phase 3 above (hand-off specs in Part 2).

## Where the project stands

The RAG/agent core is production-grade (**0.885** on 130 golden cases; guards 1.000). The platform the
course brief mandates (deployed web app with login/roles/admin/chat-history) is **~0% built** (Phase 3).
The highest-leverage *AI-side* gaps are **evaluation rigor**, **retrieval depth (contextual + structured
lookup)**, **data-quality at index time**, the **1.5c observability tail**, and **backend resilience** —
not the core agent loop, which is strong.

### Maturity scorecard

| Subsystem | Maturity | One-line state |
|---|---|---|
| Core RAG + multi-agent | ●●●●○ | Hybrid+RRF+**fuse-rerank-once (1.6)**+boosts+dynamic-k+LITM+**adaptive point-lookup routing & full-section (1.7)**+**cross-lingual (1.8)**; supervisor→4 specialists. Strong. |
| Guardrails / safety | ●●●●○ | Layered regex→moderation→LLM injection/scope + output checks. Strong. |
| Generation / prompts | ●●●○○ | Versioned specialist prompts (+ flag-gated strict point-lookup suffix); EN→VI language leak + no structured procedure output. |
| **Evaluation / testing** | ●●●○○ | **130 cases** + `run_eval.py --diff`. Still token-match only; **no retrieval recall, LLM-judge, multi-run averaging** (single-run noise ~±3 cases); `policy_conduct` scoring artifacts. |
| Data quality / ingest | ●●●○○ | Rich extraction; **dedup exact-hash only, heuristic metadata, OCR off (EN-only), regex-fragile + under-triggering calendar/fee.** |
| Backend / API | ●●○○○ | Minimal FastAPI; request IDs added (1.5a); still no lifespan, streaming, retries, rate limiting, auth. |
| Observability | ●●●○○ | **1.5a/b done:** JSON logs + correlation IDs + per-turn cost/tokens + Langfuse tracing. Remaining (1.5c): metrics endpoint, dashboards, alerts/SLO, feedback loop. |
| Platform (auth/UI/admin/deploy) | ○○○○○ | **Not started — graded Phase 3.** |

---

## PART 1 — AI / RAG / backend deep-dives

### A. Evaluation & Testing — *highest priority (it gates every other improvement)*

**Now:** `scripts/run_eval.py` — token-subset fact matching + citation-substring + refusal detection;
**130 golden cases** incl. a `calendar_pointlookup` category with adjacent-date distractors +
cross-lingual fee + multilingual guard cases; **`--diff <report>`** prints per-case flips +
per-category deltas; nightly `eval.yml`. **Gaps:** **single-run noise ~±3 cases** (a 30-case category
swung ±0.10 on identical logic) → need **multi-run averaging / lower-variance harness**; **scorer
brittleness** (morphology "temporary"≠"temporarily"; `expected_source` exact + language-blind → false
fails, esp. `policy_conduct`); no retrieval metrics (recall@k/nDCG/MRR), no LLM-as-judge, partly
circular golden set, no per-specialist scores; thin/skewed categories (services 5; policy_conduct 7,
LOA-heavy).

**Why it's #1:** improvements are measured against a noisy ±2-case token matcher; we can't see *where*
retrieval fails (recall) vs *where* generation fails. 2026 practice treats eval infra as a
prerequisite, with the RAGAS four-metric pattern (faithfulness, answer relevance, context precision,
context recall) + LLM-as-judge as the standard ([RAGAS/TruLens/DeepEval — Atlan](https://atlan.com/know/llm-evaluation-frameworks-compared/),
[RAG eval metrics 2026 — PremAI](https://blog.premai.io/rag-evaluation-metrics-frameworks-testing-2026/),
[Future AGI](https://futureagi.com/blog/what-is-rag-evaluation-2026)).

**Proposals**
- **Scorer fairness fixes (cheap, high-leverage):** stem/lemmatize for morphology; `expected_source` as
  a **set** of acceptable slugs incl. EN/VI language variants. Recovers the `policy_conduct` artifact
  fails and de-noises VI/morphology edges across all categories.
- **Retrieval-layer metrics:** `recall@k`, `MRR`, `nDCG` by annotating golden cases with
  `expected_chunk`/`expected_source`, scoring the retriever *before* generation.
- **LLM-as-judge tier:** optional judge (gpt-4o-mini/Claude) scoring faithfulness + answer relevance for
  semantic equivalence, gated behind `--judge` so the cheap tier stays the CI default.
- **Multi-run averaging** to beat the ±3-case noise; **per-specialist + per-category** recall breakdown.
- **Regression tracking:** `baseline.json` + `--diff` (done) — extend to a trend file.
- **Latency + token/cost capture** per case → trend file.
- **Held-out non-circular set:** author cases from *student questions*/paraphrases, not source docs.
- **Adopt a framework selectively:** wrap RAGAS/DeepEval metrics; keep our harness as the runner.

### B. Retrieval & RAG — *biggest quality lever after eval*

**Now:** adaptive (1.7/1.8) — router (`is_point_lookup`) → expansion (calendar paraphrase OFF / others
ON) + **cross-lingual VI↔EN variant (1.8, all domains)** → per-variant candidates → RRF fuse →
**rerank ONCE (1.6)** → boosts → dynamic-k → **full-section reading for point-lookups** → LITM →
injection scan. **Done in 1.6/1.7/1.8:** fuse-rerank-once (cost), point-lookup precision (calendar
wrong-date fixed), cross-lingual fee recall (VI→EN nursing misses fixed). **Remaining gaps:** (1)
calendar "period"/grade-release **persistent fails** — wrong-document (calendar PDF loses to registrar
blogs) + cross-term confusion → wants a **structured calendar lookup** (records exist) and/or a
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
- **Structured calendar/fee KB / lookup tool:** store calendar_event/fee_record as queryable rows
  (date-range, program filter) so "next deadline after Sept 15" and program-fee disambiguation become
  deterministic lookups. Also **improve extraction** (spreadsheet/table rows → calendar_event/fee_record
  — currently under-triggering: ~21 calendar vs ~59 in the PDF).
- **Calendar-source boost / off-category penalty** in `apply_metadata_boosts` so the Academic Calendar
  PDF / routed-domain docs stop losing to registrar blogs / off-domain pages — measure carefully.
- **Cross-lingual** retrieval **(done 1.8)**; consider multilingual rerank as a follow-up.
- **Parent-document retrieval** built+gated (`ENABLE_PARENT_DOC`); now used for point-lookups via
  adaptive routing.

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
heuristic `infer_category`; regex calendar/fee extraction; boilerplate static list; OCR off
(EN-only); image download off; crude language detection.
**Gaps:** near-dup policy PDF/HTML copies survive to index; calendar/fee extraction **fragile +
under-triggering** (~21 calendar, ~36 fee records); VN OCR absent; noisy outlinks (`link_reference`
~4,261 records) not pruned; **JS-rendered sites return only stubs** to the `httpx` crawler;
**image-borne content is not read** (OCR + image download both off); no embedding cache; OCR runs on
tracking pixels.

**Proposals**
- **Index-time near-dup dedup** (MinHash/SimHash or embedding-cosine) so PDF/HTML twins collapse before
  embedding ([Databricks data-quality for RAG](https://docs.databricks.com/aws/en/generative-ai/tutorials/ai-cookbook/quality-data-pipeline-rag)).
- **Harden + widen structured extraction** → the structured KB (B); table/spreadsheet → calendar_event
  & fee_record; table-aware fee parsing for prose-embedded amounts.
- **Quality filter:** drop low-signal chunks (nav stubs; low-confidence image assets) via a
  length/entropy heuristic at ingest.
- **Embedding content-hash cache**; **skip OCR on tracking pixels**.
- **VN OCR** (PaddleOCR `OCR_LANG=vi`, auto-detect) for scanned VN policy PDFs; evaluate on a sample.
- **Headless-fetch for JS-rendered sites + image OCR — `experience.vinuni.edu.vn` (NEW SEED):** the
  student-life hub is JavaScript-rendered (the `httpx` crawler got only a ~393-char "Quick links"
  stub) **and** its substance is in *contextful images*. Needs three things together: (1) a
  **headless/Playwright fetch path** for JS-heavy hosts, (2) `IMAGE_DOWNLOAD_ENABLED=true`, and (3)
  `ENABLE_OCR=true` with `OCR_LANG=vi` (the `assets.py`/`ocr.py` PaddleOCR PP-OCRv5 pipeline already
  exists, just disabled). The path to health/counseling/career/housing/student-life domains.
- **Contextual chunks** (shared with B) is also a data-quality upgrade.

### E. Guardrails & Safety

**Now:** regex/deobf → OpenAI omni-moderation (non-confident only) → qwen injection/scope; output =
secret-leak + citation + faithfulness (fixed) + indirect-injection scan on retrieved text.
**Gaps:** `ENABLE_OUTPUT_MODERATION=false`; jailbreak set small. *(The reranker already fails open.)*

**Proposals**
- **Expand the adversarial/jailbreak eval set** (multilingual role-play, many-shot, encoded payloads);
  track guard recall as a metric.
- **Decide output-moderation policy** (cost vs safety) — measure latency/cost of turning it on.
- **Guard observability:** log guard decisions + costs into the tracing layer (H).

### F. Generation & Prompts

**Now:** versioned prompts (`phase0-v1`), 4 specialist prompts (+ flag-gated point-lookup suffix).
**Findings:** larger model (gpt-4o) was a wash vs gpt-4o-mini; prompt tightening was net-negative; an
**EN-question→VN-answer leak** exists when retrieved docs are VN.

**Proposals**
- **Fix the language leak:** enforce answer language from the *question* — post-generation language
  check/repair.
- **Structured procedure output** (User Story 2 / FR5): typed schema (conditions → steps → documents →
  contact → notes → sources) the frontend renders as cards.
- **Prompt registry + versioning** tied to eval runs.
- Stay on **gpt-4o-mini** (proven) — or A/B **Gemini 2.5 Flash-Lite** for cost (see brainstorm).

### G. Backend / API / Serving

**Now:** minimal `create_app()`; `/health`, `/chat`, `/ingest/run`, `/sources`; no lifespan, auth,
streaming, retries, rate limiting; checkpointer in-memory by default. (Request IDs added 1.5a.)

**Proposals**
- **Lifespan startup:** build the vector store / warm the agent at boot (currently lazy → cold-start).
- **Streaming responses (SSE)** for chat — needed for the UI and the latency target.
- **Resilience:** retry+timeout wrappers on OpenRouter (chat/embed/rerank) and Qdrant. *The OpenRouter
  outages this project hit would have been caught by a retry/clear-error path.*
- **Structured error envelopes** (code, message, request_id); **readiness probe**.
- **Switch checkpointer to Postgres** for real chat-history persistence (scaffolding in `vinuni_agent.py`).
- Expose the **integration seams teammates need** (Part 2).

### H. Observability & Ops — *cheap, high-leverage*

**Done — Phase 1.5a/b** ([PHASE1.5_LOG.md](LOGS/PHASE1.5_LOG.md)): structured JSON logging +
`X-Request-ID` correlation + PII redaction; per-turn token/cost capture (structured `chat_turn` line);
**Langfuse tracing** wired at `build_chat_model` (every LLM call) with session grouping + email/phone
masking. `langfuse` is an `observability` optional extra; all fail-open.

**Remaining — Phase 1.5c (the full SRE stack):**
- **`/metrics` Prometheus endpoint**: request rate, latency histogram P50/95/99, error counter +
  custom token/cost/guardrail/tool-success metrics. Gated `ENABLE_METRICS`.
- **Grafana dashboard** (3-layer: golden signals → AI metrics → per-route), JSON committed under `ops/`.
- **≥3 symptom-based alerts** (P95 latency, error rate, daily-cost spike) + **1 SLO + error budget** +
  Slack webhook (`SLACK_WEBHOOK_URL`).
- **Readiness probe** checking Qdrant + OpenRouter reachability (current `/health` always 200).
- **Online feedback endpoint** (`POST /chat/feedback`, 👍/👎 keyed by `request_id`) → online quality
  proxy feeding the held-out eval set (A).
- **TTFT** needs SSE streaming (see G) — stretch.

Research refs: [Langfuse](https://langfuse.com/docs/observability/overview),
[LLM observability 2026 comparison](https://explore.n1n.ai/blog/llm-observability-langfuse-langsmith-opentelemetry-2026-05-17).

---

## PART 2 — Platform hand-off specs (graded Phase 3; concrete contracts)

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
- **Deployment (BRIEF §4.3):** `Dockerfile` + `docker-compose` (app + Postgres; Qdrant Cloud already
  hosted); backend → Render/Railway/Fly, frontend → Vercel; secrets via platform env (key-rotation
  discipline matters).

---

## PART 3 — Suggested sequence (AI-depth first)

1. **Eval framework (A)** — do first; everything else is measured by it (start with scorer-fairness +
   multi-run averaging; the cheapest, highest-leverage).
2. **Observability 1.5c (H)** — metrics/readiness/feedback; cheap.
3. **Structured calendar/fee lookup + extraction (B/D)** — fixes the persistent calendar/financial core.
4. **Contextual Retrieval (B)** — headline retrieval lift; measure with the upgraded eval.
5. **Adaptive routing + reflection (B/C)** — cost-aware, improves hard queries.
6. **Data-quality at index (D)** — near-dup dedup, quality filter, embedding cache, JS/OCR coverage.
7. **Backend resilience + streaming + Postgres history (G)** — also unblocks the platform team.
8. **Generation polish (F)** — language-repair, structured procedure output.
9. **Guardrail hardening (E)** — output-moderation policy, jailbreak set.
10. **Phase 2 — personalization** (mock student DB) and **Phase 3 — platform** (teammates; Part 2).

Each item: toggle-gated where it touches serving, A/B-measured on the upgraded eval, `pytest -m "not
live"` + `ruff` green, scratch-collection discipline, **one eval at a time** (lessons in PHASE1.4_LOG.md).

---

## Consolidated TODO checklist
- [~] **Eval:** [x] eval set 86→130 + `--diff` regression tooling (1.7) — [ ] remaining: scorer
  morphology/lemmatize + multi-source/lang-aware `expected_source`; **multi-run averaging** (noise);
  retrieval recall@k/MRR/nDCG; LLM-judge tier; held-out set
- [~] **Observability:** [x] JSON logs + correlation IDs + per-turn cost/tokens + Langfuse (1.5a/b) —
  [ ] remaining (1.5c): Prometheus `/metrics` + Grafana; ≥3 alerts + SLO/error-budget; readiness probe;
  feedback endpoint
- [~] **Retrieval:** [x] fuse-rerank-once (1.6); adaptive point-lookup router + full-section (1.7);
  cross-lingual VI↔EN (1.8); structured calendar lookup (1.19 Stage 1); cross-lingual policy escalation
  (1.20 Lever 1); deterministic policy doc-pin (1.21/1.21b) — [ ] remaining: fee structured lookup A/B
  (1.19 Stage 2); **ingest-time policy topic index — generality/upload-coverage fix for the doc-pin
  ([Phase 1.24 plan](LOGS/PHASE1.24_PLAN.md))**; universal magnet down-weighting backstop; contextual
  chunks; off-category penalty; calendar-source boost
- [ ] **Cost:** Gemini 2.5 Flash-Lite A/B; embedding content-hash cache; prompt/hot-Q&A cache; skip-OCR pixels
- [ ] **Agents:** complexity gate + iteration budget; reflection step
- [ ] **Data:** index-time near-dup dedup; quality filter; VN OCR; table/spreadsheet→structured records;
  headless/JS fetch + image OCR for `experience.vinuni.edu.vn`
- [ ] **Backend:** lifespan warmup; SSE streaming; LLM/Qdrant retries; error envelopes; Postgres checkpointer
- [ ] **Generation:** language-repair; structured procedure schema; prompt registry
- [ ] **Guardrails:** expand jailbreak set; output-moderation cost eval
- [ ] **Platform (Phase 3, teammates):** auth/roles; chat-history; admin doc mgmt + source registry;
  frontend; SSE; Docker+deploy; readiness probe; rate limiting
- [ ] **Stretch:** mock student DB personalization; auto-ticket; deadline reminders; GraphRAG

---

## Appendix — CODEX backlog (consolidated from CODEX_IDEAS.md, 2026-06-23)

> Folded here so all update ideas live in one file. **Status:** most P0/P1 items were SHIPPED or DEFERRED in
> the Phase 1.19–1.27 arc — eval ledger, structured calendar/fee lookup, prompt/response caching = **done**;
> retrieval planner, contextual retrieval, embedding/rerank A/B = **deferred** (A7/Track B). See
> [LOGS/SESSION_CLOSEOUT.md](LOGS/SESSION_CLOSEOUT.md) for current state. Original backlog preserved below.


## Summary

This backlog is quality-first, but it also ranks ideas by latency and money cost.

Current architecture is strong for an MVP: FastAPI API layer, LangGraph supervisor and
specialists, LangChain tools, Qdrant hybrid retrieval, OpenRouter chat/embedding/rerank,
and guardrails. The main architecture improvement is to evolve it into a measured,
tiered RAG system:

1. Deterministic shortcuts and structured lookup first.
2. Retrieval and rerank second.
3. Agent reasoning only when needed.
4. Observability around every expensive step.

The goal is not just "faster." It is higher correctness, fewer unnecessary model calls,
lower p95 latency, lower eval/reingest cost, and clearer failure diagnosis.

## Current Architecture Notes

- API flow: `/chat` runs pre-agent guardrails, then `VinUniAgentService`.
- Agent flow: `START -> supervisor -> one specialist -> END`, with calendar, policy,
  financial, and services ReAct agents.
- Retrieval flow: agent tools expand queries, fuse variants, rerank once, then Qdrant
  hybrid retrieval finalizes with dynamic-k, parent-section expansion, metadata boosts,
  and lost-in-the-middle reordering.
- Current baseline is `0.923 / 130`, with weaker categories around calendar point
  lookups and policy conduct.
- Current update status: Phase 1.13 calendar correctness and Phase 1.18 guard precision
  are in progress; Phase 1.14 embedding A/B, Phase 1.15 caching/async, Phase 1.16
  multi-domain reasoning, and Phase 1.17 agent-decided expansion are still pending.

## Architecture Advice

### Split Knowledge Access From Agent Reasoning

Calendar dates, tuition rows, policy codes, source freshness, and known official links
should live behind deterministic lookup/query services. The agent should call them
instead of rediscovering them through vector search every turn.

This is especially important for calendar and financial questions because many rows are
near-identical. Vector retrieval can easily surface a neighboring date or fee. A
structured lookup layer can apply exact filters for academic year, term, event type,
program, fee type, and source.

### Add A Retrieval Orchestration Layer

Query expansion, point-lookup decisions, RRF, rerank, parent-section expansion, and
metadata boosts are currently spread across tools, retriever, and context helpers. A
`RetrievalPlanner` or `RetrievalOrchestrator` would make this easier to test and tune.

Suggested responsibility:

- Classify retrieval mode: structured point lookup, policy prose, services, comparison,
  wide list, or clarification.
- Choose query expansion: none, date variants, cross-lingual, paraphrase, or agent-decided.
- Execute retrieval through one interface.
- Record retrieval metrics: candidate count, rerank count, selected k, source mix,
  latency, and cache status.
- Return evidence chunks plus a structured trace for eval and debugging.

### Make Cost And Latency First-Class Product Metrics

Current cost tracking is useful but partial. The architecture should meter each expensive
step: guardrail, supervisor, query expansion, retrieval, rerank, specialist LLM, output
scan, token usage, cache hits, and p50/p95 latency.

This matters because cost-saving work is otherwise guesswork. The system should know
which step is expensive before optimizing it.

### Use FastAPI Lifespan For Warm Startup

Build and cache the agent graph, Qdrant clients, sparse embedding object, reusable HTTP
clients, and optional tracing callbacks during startup. This avoids paying cold
initialization during the first real chat turn and gives one clean place to close clients
on shutdown.

Reference: https://fastapi.tiangolo.com/advanced/events/

### Prefer Structured Correctness Before Model Upgrades

The weakest current area is exact calendar point lookup. A bigger model may make prose
answers nicer, but it will not reliably fix wrong neighboring rows. Structured calendar
and fee lookup should come before defaulting to larger chat models.

## Prioritized Backlog

### P0: Full Eval Plus Cost/Latency Ledger

Expand `scripts/run_eval.py` to record answer score, retrieval recall, citation source
match, token usage, rerank count, model calls, cache status, and latency per phase.

Why:

- Prevents speed improvements that secretly hurt quality.
- Makes cost-saving measurable.
- Turns eval into the scoreboard for every later idea.

Acceptance target:

- Every live eval report includes quality, latency, and estimated cost fields per case.
- Every optimization can be compared against `data/eval/baseline.json`.

### P0: Structured Calendar And Fee Lookup

Finish Phase 1.13 by making calendar events and fee rows queryable as structured records.
Route exact date, amount, deadline, tuition, penalty, scholarship, term, and academic-year
questions there before vector search.

Why:

- Directly attacks the weakest current category.
- Reduces hallucinated neighboring dates/amounts.
- Saves tokens by returning compact exact evidence.

Acceptance target:

- `calendar_pointlookup >= 0.950`.
- No regression in financial, citation, or safety categories.

### P0: Reduce Unnecessary Agent Calls

Keep pure time questions, greetings, unsupported requests, guardrail responses, and simple
source/listing requests out of the agent path. Add deterministic handlers for high-confidence
facts and official links.

Why:

- Saves model calls.
- Reduces latency.
- Reduces nondeterminism.

Acceptance target:

- Common non-RAG requests return without building or invoking the agent.
- Eval records show fewer model calls for shortcut cases.

### P1: Retrieval Planner

Centralize retrieval-mode selection behind a planner. The planner should decide between
structured lookup, point lookup, wide retrieval, comparison retrieval, policy prose,
services retrieval, or clarification.

Why:

- Supports Phase 1.16 multi-domain reasoning and Phase 1.17 agent-decided expansion.
- Keeps retrieval behavior testable instead of scattered across tools and prompts.

Acceptance target:

- Unit tests cover planner decisions for calendar, financial, policy, services,
  multi-domain, and ambiguous questions.

### P1: Contextual Retrieval Index

Add short document/section context to chunks before embedding and BM25 indexing, especially
for calendar and policy chunks.

Why:

- Ambiguous chunks often lack year, program, policy, or section context when embedded alone.
- Contextual retrieval can improve recall without needing a larger chat model.

Reference: https://www.anthropic.com/engineering/contextual-retrieval

Acceptance target:

- Retrieval recall improves on held-out calendar/policy cases.
- No regression in citation quality or answer faithfulness.

### P1: Embedding And Rerank A/B

Compare current OpenRouter `openai/text-embedding-3-small` against stronger multilingual
embedding options. Test cross-lingual expansion on/off for each candidate.

Candidates:

- Current baseline: `openai/text-embedding-3-small`.
- Higher-quality OpenAI embedding model if available through the chosen provider.
- Cohere Embed v4 or another strong multilingual model.
- BGE-M3 if local/open-source deployment becomes attractive.

Why:

- Better multilingual embeddings may reduce translation/expansion calls.
- Fewer expansion calls can save both money and latency.

Reference: https://docs.cohere.com/docs/cohere-embed

Acceptance target:

- Winner improves retrieval recall and eval pass rate without increasing p95 latency beyond
  an agreed threshold.

### P1: Prompt And Response Caching

Use provider-supported caching where possible, especially for repeated deterministic evals,
multi-turn sessions, and stable system prompts.

Ideas:

- Use OpenRouter `session_id` for provider stickiness and prompt-cache benefits in multi-turn
  workflows.
- Consider OpenRouter response caching for deterministic repeated requests.
- Add local TTL cache for query expansion, cross-lingual translation, rerank inputs, and
  structured lookup results.

Why:

- Repeated evals and common questions are expensive if every step is recomputed.
- Query expansion and rerank are good cache candidates because they are deterministic at
  temperature 0.

Reference: https://openrouter.ai/docs/guides/features/response-caching

Acceptance target:

- Repeated deterministic prompts show cache hits.
- Freshness-sensitive tests can bypass or clear caches.
- No cached answer is returned after the indexed source version changes.

### P2: Streaming And Perceived Latency

Add a streaming chat path so users see answer tokens earlier while the backend still does
the same correctness checks.

Why:

- Streaming improves perceived speed even when total backend latency is unchanged.
- Useful once answer quality is stable.

Reference: https://docs.langchain.com/langsmith/streaming

Acceptance target:

- Streaming endpoint or mode emits tokens progressively.
- Final response still includes citations and safety checks.

### P2: Qdrant Native Hybrid Query Experiments

Test Qdrant Query API prefetch/RRF instead of doing all dense/sparse fusion in Python.

Why:

- May reduce client-side round trips and simplify retrieval code.
- Gives more native control over multi-stage dense and sparse search.

Reference: https://qdrant.tech/documentation/search/hybrid-queries/

Acceptance target:

- Same or better retrieval quality on golden cases.
- Lower retrieval-stage latency on repeated eval runs.

### P2: Offline Batch Cost Cuts

Move offline-heavy work to batch jobs where possible: eval judging, embedding experiments,
large reindex jobs, and non-urgent data enrichment.

Why:

- Batch APIs can lower cost for non-interactive workloads.
- Keeps online chat path focused on user latency.

Reference: https://developers.openai.com/api/docs/guides/batch

Acceptance target:

- Batch path can run without changing online chat behavior.
- Offline results are linked back to eval reports and source versions.

### P3: Vector Storage Optimization

Only after recall metrics exist, test Qdrant quantization for memory and search-speed
improvements.

Why:

- Quantization can improve memory and speed, but it can also hurt recall.
- It should be gated behind retrieval-quality metrics.

Reference: https://qdrant.tech/documentation/manage-data/quantization/

Acceptance target:

- Quantized collection preserves retrieval recall within the chosen tolerance.
- Search latency or memory footprint improves enough to justify the tradeoff.

## Suggested Interface And Config Additions

- `ENABLE_RESPONSE_CACHE`
- `CACHE_TTL_SECONDS`
- `OPENROUTER_SESSION_ID_MODE`
- `RETRIEVAL_PLANNER_MODE`
- `ENABLE_STRUCTURED_LOOKUP_FIRST`
- `ENABLE_EVAL_COST_LEDGER`
- `ENABLE_STREAMING_CHAT`

Suggested eval report fields:

- `latency_ms_by_stage`
- `model_calls`
- `tokens_by_stage`
- `estimated_cost_usd`
- `cache_hit`
- `rerank_calls`
- `retrieval_mode`
- `structured_lookup_used`
- `retrieval_candidate_count`
- `retrieval_selected_k`

No public `/chat` schema change is required immediately. If debugging metadata is exposed,
put it behind a development-only flag.

## Test And Acceptance Plan

Offline gate:

```powershell
py -m pytest -m "not live" -q
```

Live eval gate:

```powershell
py scripts/run_eval.py --min-pass 0.923 --diff data/eval/baseline.json
```

Quality gates:

- No regression in safety, refusal, citation, or faithfulness categories.
- `calendar_pointlookup >= 0.950`.
- `policy_conduct >= 0.950`.
- Overall pass rate stays at or above the current baseline.

Performance gates:

- Record p50 and p95 latency before optimization.
- Record estimated cost per eval run before optimization.
- Every cost-saving change must show no quality regression.

Cache gates:

- Repeated deterministic eval prompts should show cache hits where enabled.
- Freshness-sensitive tests must be able to bypass or clear caches.
- Cache keys must include source/index version when answer content depends on indexed data.

## Research Anchors

- Anthropic Contextual Retrieval: https://www.anthropic.com/engineering/contextual-retrieval
- RAGAS evaluation metrics: https://docs.ragas.io/en/stable/concepts/metrics/available_metrics/
- Qdrant hybrid Query API: https://qdrant.tech/documentation/search/hybrid-queries/
- Qdrant quantization: https://qdrant.tech/documentation/manage-data/quantization/
- Cohere Embed v4 multilingual docs: https://docs.cohere.com/docs/cohere-embed
- OpenAI Batch API: https://developers.openai.com/api/docs/guides/batch
- LangGraph streaming: https://docs.langchain.com/langsmith/streaming
- FastAPI lifespan: https://fastapi.tiangolo.com/advanced/events/
- OpenRouter response caching: https://openrouter.ai/docs/guides/features/response-caching

## Assumptions

- Quality remains the primary ranking criterion.
- Cost saving means both money cost and user time/latency.
- Architecture changes should be implemented incrementally, not as one large rewrite.
- Existing dirty worktree changes are preserved and not touched by this document.
