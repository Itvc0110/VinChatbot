# VinChatbot — Project Journal (read this first)

Single read-back file for context. Last updated: 2026-06-16.
Detailed docs: [PRD.md](PRD.md) · [UPDATE_PLAN.md](UPDATE_PLAN.md) (roadmap) ·
[ARCHITECTURE.md](ARCHITECTURE.md) (flow diagrams, incl. §2b retrieval) · LOGS/PHASE1.0–1.4 ·
[PHASE1.5_LOG.md](LOGS/PHASE1.5_LOG.md) (observability) · [PHASE1.6_LOG.md](LOGS/PHASE1.6_LOG.md)
(rerank cost) · [PHASE1.7_LOG.md](LOGS/PHASE1.7_LOG.md) (eval expansion + adaptive retrieval) ·
[FUTURE_IMPROVEMENTS.md](FUTURE_IMPROVEMENTS.md) (whole-project assessment + roadmap) ·
[todo.md](todo.md) (deferred Vietnamese work).

## What this is
RAG + multi-agent chatbot answering VinUni students' questions on policies, academic
calendar, deadlines, fees, registrar, library, student life. Backend: FastAPI + LangChain
1.x / LangGraph 1.x + Qdrant Cloud (hybrid dense+sparse) + OpenRouter. Course project
(AI20K Build Cohort 2, Team 050). Public Q&A first; personalization (mock student DB) is a
stretch. Deployed-app (auth/UI/admin) required by brief but not built yet.

## System shape (see ARCHITECTURE.md)
- **Online (`/chat`)**: input guard → supervisor routes to 1 of 4 specialist ReAct agents
  (calendar/policy/financial/services) → retrieval tool → answer → output checks.
- **Retrieval** (adaptive, ARCHITECTURE §2b): a cheap router (`is_point_lookup`) splits prose vs
  point-lookups. Multi-query: per-variant candidates (no rerank) → RRF fuse → **rerank ONCE**
  (Phase 1.6, ~67% fewer rerank calls) → metadata boosts → dynamic-k → **full-section expand for
  point-lookups** → LITM → indirect-injection scan. Phase 1.7 split: calendar point-lookups drop
  expansion (precision); financial keep it + a **cross-lingual EN variant** (recall); both get a
  strict "exact value only" prompt. Toggles `ENABLE_RERANK_AFTER_FUSION` / `ENABLE_ADAPTIVE_RETRIEVAL`.
- **Guards (cost-aware, rule tier first)**: regex+deobfuscation (base64/zero-width/leet) →
  (non-confident only) OpenAI omni-moderation (safety) → qwen-2.5-7b classifier
  (injection/scope). Output: secret-leak + citation/degrade + faithfulness checks.
- **Offline ingest** (admin): crawler → parsers (HTML/PDF/CSV/XLSX/DOCX) → clean
  (strip_boilerplate) → chunk (+structured records: calendar_event/fee_record/table) →
  content-hash dedup → embed → Qdrant. Chat never crawls.
- **Multi-agent is in-process LangGraph** (supervisor+specialists). **No MCP/A2A** (deferred;
  shown as future hooks in ARCHITECTURE.md §2a).

## Phase history (eval = `scripts/run_eval.py` on golden sets in `data/eval/golden/`)
- **Phase 1.0 — foundation**: 761-doc Qdrant Cloud corpus, multi-agent graph, CI, eval. **47.2%**.
- **Phase 1.1 — quality & safety**: language honoring, LITM reorder, dynamic-k, dedup,
  multi-query+RRF, regex+small-LLM guard, de-obfuscation, indirect-injection scan,
  calendar/fee structured chunks. **93.1%** (58 cases).
- **Phase 1.2 — metadata, layered guards, eval, viz**: event_type/fee_type, policy_code
  propagation, source_trust+term boosts, soft routing, image-chunk exclusion (3957→34);
  layered API guard (omni-moderation + qwen); eval→80 cases (safety/multi-turn/unanswerable);
  ARCHITECTURE.md. **92.5%**, index 7,781 chunks. ← **current production baseline**.
- **Phase 1.3 — markdown experiment: REJECTED**. Markdown-first parsing + LangChain
  header/token chunker. Even tuned → ~81% < 92.5%. Root cause: pymupdf4llm rendered the
  **calendar PDF as a noisy markdown table** (`|||<br>`) that broke the `calendar_event`
  regex (59 clean events → 8) + over-fragmentation (2× chunks) flooded retrieval with tiny
  registrar fragments. **Markdown is OFF by default** (`ENABLE_MARKDOWN_PARSING=false`); code
  kept gated. **DOCX parsing/routing was kept** (genuine new dtype). See LOGS/PHASE1.3_LOG.md.
- **Phase 1.4 — chunking/retrieval/faithfulness**: faithfulness output-gate false-positive fix
  (shipped); parent-doc built but gated off; conversational handling fix. **0.919** (eval grew to 86).
- **Phase 1.5 — observability**: structured JSON logging + `X-Request-ID` + PII redaction + per-turn
  token/cost capture; **Langfuse** tracing (opt-in). Logging-only, no eval regression (0.919/0.930).
- **Phase 1.6 — rerank cost**: rerank the RRF-fused pool **once** (not per query variant), ~67%
  fewer rerank calls. Shipped on (`ENABLE_RERANK_AFTER_FUSION=true`); A/B accepted a ~1-case tradeoff.
- **Phase 1.7 — eval expansion + adaptive retrieval**: eval **86 → 130** (new `calendar_pointlookup`
  category + cross-lingual fee + multilingual guard cases) + `run_eval.py --diff` tooling; **adaptive
  point-lookup routing shipped** (`ENABLE_ADAPTIVE_RETRIEVAL=true`). See § Current state for numbers.

## Key decisions & rationale
- **Qdrant Cloud** canonical vector store (Pinecone/Chroma opt-in).
- **NeMo Guardrails dropped**: pins `langchain<0.4`, would break our LangChain 1.x stack.
  Guard = OpenAI omni-moderation (safety) + qwen-2.5-7b (injection/scope) behind regex.
- **Markdown shelved** (Phase 1.3): lost to plain text; parent-document retrieval is the
  planned fix before any revisit.
- All RAG/guard/ingest levers are **`ENABLE_*` toggles in `config.py`** for A/B.
- Eval scorer: token-subset matching (accent-insensitive), `expected_source` citation check,
  refusal detection, multi-turn via `turns`. **Reference baseline: 0.846 on the 130-case set**
  (`data/eval/baseline.json`, adaptive OFF); see § Current state for why this is lower than the old
  86-case ~0.92 (harder set, not a regression).

## Conventions (how to run)
- Python via **`py`** launcher (Windows 3.14). `PYTHONUTF8=1` to avoid console crashes on VN text.
- **Scratch-collection pattern** for experiments (never touch the serving index until validated):
  `RAW_DATA_DIR=data/raw_x PROCESSED_DATA_DIR=data/processed_x QDRANT_COLLECTION=vinuni_x_test`
  env overrides on `crawl_seed.py` / `ingest_documents.py` / `run_eval.py`; delete scratch after.
- Pipeline: `build_core_seeds.py` → `crawl_seed.py --seed-file data/processed/core_seeds.json`
  → `ingest_documents.py` → `run_eval.py`. Crawl is long; run in background.
- Gate: `py -m pytest -m "not live"` + `py -m ruff check .` (89 tests, must stay green).
- CI: `.github/workflows/ci.yml` (lint+pytest non-live), `eval.yml` (nightly live, secrets).

## Current state (2026-06-16)
- Production = main Qdrant collection **`vinuni_documents` (7,957 points, plain-text)**, untouched.
- **Phase 1 (sub-phases 1.0–1.8) DONE** (logs in `LOGS/`). 1.5 observability, 1.6 rerank-cost, 1.7
  adaptive retrieval, 1.8 cross-lingual expansion — all shipped (flag-gated, one-flag revert each;
  1.8 logged inside PHASE1.7_LOG.md).
- **Score baseline — READ THIS (the number changed meaning in 1.7):** the eval set grew **86 → 130**
  in Phase 1.7 with *deliberately hard* cases (calendar point-lookups w/ adjacent-date distractors,
  VI→EN cross-lingual fees, multilingual guards), so absolute scores are **NOT comparable** to the old
  86-case ~0.92. On the 130-case set: **adaptive-OFF reference = 0.846**; **production (adaptive +
  cross-lingual, 1.7 + 1.8) = 0.885** — calendar 0.929, financial 0.875, guards (adversarial/safety/
  unanswerable) 1.000. `data/eval/baseline.json` is now **re-snapshotted to this production run** (the
  diff reference for future A/Bs). Confirmed mechanistic wins: calendar wrong-date fixed, persistent
  VI→EN fee misses fixed. Single-run noise ~±3 cases → **multi-run averaging is the top open
  eval-rigor item.**
- Highlights from 1.4:
  - **Faithfulness false-positive FIX (shipped, no toggle)**: `assess_faithfulness` was extracting
    digits from the answer's citation/Source line (policy code "VUNI.54" → token `54`) and, not
    finding them in chunk text, forcing a graceful-degradation refusal over *correct* answers. It
    now grounds only the substantive body (`_grounding_body` strips links/Source lines/policy
    codes). Recovered the LOA `policy_conduct` cluster; **overall back to 0.925**, de-flaked.
  - **Parent-document retrieval (`ENABLE_PARENT_DOC`, default OFF, retained)**: helps thin
    services/library but net-neutral overall (calendar grid over-shares adjacent dates); kept gated
    + `PARENT_DOC_SKIP_SUBCATEGORIES=calendar`. The enabling lever for a future markdown revisit.
  - **Reframing insight**: a direct retrieval probe showed our recall/ranking is *strong* (the LOA
    answer chunk ranks #0). The eval losses are at the **generation/output-gate boundary**
    (over-refusal) and **eval-golden strictness** (forbidden-fact over-sharing, VI/phrasing), not
    retrieval/chunking. Bias future effort accordingly.
  - **Generation-gate A/Bs rejected**: gpt-4o = wash vs gpt-4o-mini at 15–30× cost (stay on mini);
    prompt tightening net-negative (reverted). Financial miss = cross-lingual retrieval (VN query
    vs EN tariff), logged not over-tuned.
  - **Coverage crawl was REDUNDANT** — production already had the Student Code of Conduct (verify
    the live index by Qdrant scroll BEFORE crawling). Real gain: **+6 validated Code-of-Conduct
    golden cases** (eval set now **86**, conduct 6/6). Scratch `vinuni_cov_test` deleted.
  - **Quota note**: never run evals concurrently (API contention exhausted the OpenRouter key,
    `403 Key limit exceeded`); don't re-embed to validate retrieval-time questions. User rotated key.
    **Clean baseline: 86 cases, overall ~0.919, 80-subset ~0.912 (proven band).**
  - **Conversational handling FIX (shipped)**: `answer_language` rewritten (full VN accent set +
    accent-less hints) and a rule-tier `smalltalk`/`capability` intent layer added, so greetings/
    closings/identity/social turns answer directly in the correct language **before the SLM and
    without retrieval/degradation**; real questions still flow to the agent. 102 tests + ruff green;
    eval **0.919** (no regression; adversarial/safety/unanswerable all 1.0).
- `.env` has live OpenRouter + Qdrant + OpenAI keys (user **rotated** the earlier-exposed ones).
- Nothing committed/pushed to git yet — user controls commits.

## Eval / golden-set caveats (important)
- Calendar golden set = prior team's, from the AY26-27 calendar PDF. Financial/policy/services
  facts I authored **from the crawled source docs** → eval is a **fair relative** comparison
  but **circular/narrow as an absolute** measure (fact-lookup heavy). Adversarial/safety/
  unanswerable/multi-turn hand-authored.
- 6 stubborn fails at 92.5%: 2 calendar source-inconsistency (model won't flag the PDF's own
  "Fall'26" mislabel), + VI/phrasing edges.

## Domains we can answer (and gaps)
Strong: **policies/regulations** (5,377 chunks — student affairs, conduct, academic,
financial, HR, research, governance), **academic calendar**, **fees/tuition/fines**,
**registrar procedures**, **academic integrity/appeals**, **student life**, **Student Code of
Conduct + disciplinary tiers** (VU_CTSV02 — confirmed in production, 110 conduct chunks; eval
covers it as of Phase 1.4).
Thin/missing: **library** (1 doc), **admissions**, **health/counseling**, **housing/dorm**,
**career services**, **Student Handbook/Guide**. (NOTE: always Qdrant-scroll the live index to
confirm a gap before crawling — the "conduct missing" note here was stale and cost a redundant crawl.)

## Backlog / what's next (major phases = big changes)
- **Phase 1 — Core RAG chatbot: DONE** (sub-phases 1.0–1.4; logs in `LOGS/`). Production at
  **0.919** on 86 eval cases, plain-text pipeline, conversational handling fixed.
- **Phase 2 — Personalization (NEXT major change)**: mock student DB (`students`/`enrollments`/
  `student_fees`/`student_deadlines`), profile tools keyed to the **authenticated** `student_id`
  (never from the prompt), personal-vs-general routing, strict cross-user isolation. (PRD §10.)
- **Phase 3 — Platform & deploy (teammates)**: auth/roles, chat-history persistence, admin doc
  management + source registry, frontend, Docker/deploy. Hand-off specs in FUTURE_IMPROVEMENTS.md Part 2.

AI-depth backlog (Phase 1 quality, research-backed) lives in **FUTURE_IMPROVEMENTS.md**: eval
framework (recall@k + LLM-judge + regression diff), observability (Langfuse + cost capture),
contextual retrieval, adaptive query routing, near-dup dedup, cross-lingual retrieval fix.

**Deferred**: Vietnamese coverage (todo.md — VN policy versions, VN eval cases); genuinely-new-domain
coverage (health/counseling/career/housing — needs headless fetch + image OCR for
`experience.vinuni.edu.vn`); eval/test harness; semantic chunking.

## Key files
- Agents: `vinchatbot/app/agents/{graph,supervisor,specialists,prompts,tools,vinuni_agent,guardrails,llm_guard,safety_guard}.py`
- RAG: `vinchatbot/app/rag/{retriever,reranker,context,query_engineering,citations}.py`
- Ingest: `vinchatbot/app/ingest/{crawler,parsers,normalizer,chunker,indexer,assets,ocr}.py`
- Storage/LLM: `vinchatbot/app/storage/{qdrant_store,vector_metadata}.py`, `llm/openrouter_chat.py`, `embeddings/openrouter_embeddings.py`
- Config (all toggles): `vinchatbot/app/core/config.py`
- Scripts: `scripts/{build_core_seeds,crawl_seed,ingest_documents,run_eval,eval_rag}.py`
- Eval: `data/eval/golden/*.json` + `data/eval/calendar_golden_qa.json`
