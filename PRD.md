# VinChatbot — Product Requirements Document (v0.2)

> Status: Working draft. Supersedes the PRD section of [BRIEF.md](BRIEF.md) and is the
> canonical product spec. Engineering execution is tracked in [UPDATE_PLAN.md](UPDATE_PLAN.md).
> Last updated: 2026-06-13.

---

## 1. Vision

A 24/7 AI assistant that answers any VinUni student's question about academic
policies, the academic calendar, deadlines, events, fees, and student services —
grounded in official VinUni sources, with citations, and with explicit refusal when
the data is not there. A later phase adds **personalization**: once a student is
authenticated against a (initially mock) student system, the bot can answer questions
about *their own* program, schedule, deadlines, fees, and status.

The product is not "a RAG demo." It is a deployed web app with login, roles, chat
history, an admin surface for managing sources, and a measurable answer-quality bar.

## 2. Problem statement

VinUni academic/service information is scattered across multiple websites (`vinuni.edu.vn`,
`policy.vinuni.edu.vn`, `registrar.vinuni.edu.vn`, `experience.vinuni.edu.vn`), PDFs,
and notices. Students waste time searching, read stale versions, or ask the wrong
office — and support staff are only available in office hours. We want one fast,
accurate, always-on channel that cites its sources and never invents a deadline,
fee, or rule.

## 3. Goals & non-goals

### Goals
- G1 — Answer public academic/service questions in VI or EN with at least one valid
  citation when an answer is given.
- G2 — Refuse cleanly and route to official sources/offices when evidence is
  insufficient (no hallucinated fees/deadlines/policies).
- G3 — Step-by-step procedural answers (conditions → steps → documents → where to
  submit → notes → sources).
- G4 — Defend against prompt injection, abuse, out-of-scope, and private-data probes
  on **both input and output**.
- G5 — Deployed web app: login, Student/Admin roles, persisted chat history, admin
  document management.
- G6 — A measurable eval harness (accuracy, citation validity, correct-refusal rate,
  latency) wired into CI.
- G7 (Phase 2) — Personalized answers for an authenticated student against a mock
  student database, with strict per-user data isolation.

### Non-goals (for now)
- Production integration with the real SIS/Canvas.
- Performing actions on the student's behalf (registering, paying, submitting forms).
- Replacing the registrar / student-services staff.
- Answering questions with no official source.

## 4. Current state (honest snapshot)

What exists today (backend MVP scaffold):

- FastAPI app: `POST /chat`, `POST /ingest/run`, `GET /sources`, `GET /health`
  ([main.py](vinchatbot/app/main.py), [routes_chat.py](vinchatbot/app/api/routes_chat.py),
  [routes_ingest.py](vinchatbot/app/api/routes_ingest.py)).
- LangChain `create_agent` ReAct loop with a LangGraph checkpointer keyed on
  `conversation_id` → in-session memory **does** exist, but only `InMemorySaver`
  (lost on restart, not multi-worker safe) ([vinuni_agent.py](vinchatbot/app/agents/vinuni_agent.py)).
- Four retrieval tools, each hard-coding a category filter
  ([tools.py](vinchatbot/app/agents/tools.py)).
- Hybrid dense+sparse retrieval over Qdrant (BM25 sparse via FastEmbed) with a single
  rerank pass to a fixed `k=8` ([retriever.py](vinchatbot/app/rag/retriever.py),
  [reranker.py](vinchatbot/app/rag/reranker.py)).
- Regex input guardrails + an LLM "scope router" for the gray zone; a light output
  check for leaked secrets and a citation-presence degrade
  ([guardrails.py](vinchatbot/app/agents/guardrails.py)).
- Domain-aware crawler with frontier/dedupe/robots/caps, three-tier metadata, and
  structured-record extraction ([crawler.py](vinchatbot/app/ingest/crawler.py),
  [parsers.py](vinchatbot/app/ingest/parsers.py)).
- 30-case bilingual calendar golden set ([calendar_golden_qa.json](data/eval/calendar_golden_qa.json)).

Known gaps / defects (these were fixed in sub-phase 1.0 — see [UPDATE_PLAN.md](UPDATE_PLAN.md) Phase 1):

- **Config drift:** [.env.example](.env.example) ships `VECTOR_STORE_BACKEND=pinecone`
  with an empty Pinecone key, while the code default and README assume Qdrant. A fresh
  clone fails to retrieve.
- **Agent coverage hole:** every tool forces a `category`, so library
  (`student_services`), registrar (`academic/registrar`), and student-life content is
  unreachable by the agent. There is no general semantic-search tool.
- **Crawler crash on spreadsheets:** `pd.read_excel(...)` with no engine + optional
  `openpyxl` not installed raises `ValueError: Excel file format cannot be determined`
  (recorded in [todo.md](todo.md)).
- **No automated eval:** `eval_rag.py` only prints 4 answers; the golden set is not
  scored.
- **Thin data cleaning & chunking:** `normalize_text` only collapses whitespace;
  HTML is extracted by trafilatura as plain text (no headings → empty `section_path`);
  the dense one-page calendar PDF is not table-aware, which is exactly the case the
  eval set stresses (Course Drop vs Add/Transfer deadlines).
- **Output guardrail is shallow:** checks for leaked secrets + citation presence, but
  no faithfulness/grounding verification of claims against retrieved text.
- **Reranking is single-stage, fixed-k**, and silently degrades to original order when
  the rerank call has no key.
- No frontend, no auth, no roles, no persisted chat history, no admin dashboard, not
  deployed.

## 5. Users & personas

- **Student (primary).** Asks academic/service questions in VI/EN; in Phase 2, asks
  about their own record. Needs fast, correct, cited answers and clear "I don't know."
- **Student-services / registrar staff (secondary).** Use it to deflect repeat
  questions; review answer quality; see what's missing.
- **Admin (operator).** Manages sources, triggers re-crawl/re-index, reviews chat logs
  and unanswered questions, watches eval dashboards.

## 6. Scope

### 6.1 MVP (public Q&A, deployed)
Public, source-grounded Q&A; citations; procedural answers; input+output guardrails;
login + Student/Admin roles; persisted chat history; admin document management;
deployed URL; eval harness.

### 6.2 Phase 2 (personalization, mock student system)
Authenticated student profile; tools that read the mock student DB; personalized
answers about the student's program/schedule/deadlines/fees/status; strict per-user
isolation; "personal" vs "general" intent handling.

### 6.3 Phase 3+ (future)
Real SIS/Canvas integration, ticket creation/handoff, deadline reminders/notifications,
broader multilingual support, GraphRAG if cross-document reasoning demands it.

## 7. Functional requirements

### Ingestion & data (FR-I)
- FR-I1 Crawl/refresh official VinUni public sources (gateway, calendar, policy
  library, registrar, experience) on an admin-triggered or scheduled basis. Chat
  runtime never crawls.
- FR-I2 Parse HTML/PDF/DOCX/Markdown/CSV/XLSX into normalized text + structured
  records, preserving section structure where available.
- FR-I3 Clean content: strip nav/boilerplate, normalize unicode/whitespace, drop
  empty/duplicate/near-duplicate chunks, preserve headings as `section_path`.
- FR-I4 Chunk semantically and structure-aware; tables (esp. the academic calendar)
  must be chunked so each event/deadline row is independently retrievable with its
  term/date/type.
- FR-I5 Attach three-tier metadata (source / chunk / structured-record) and the filter
  keys in §9.
- FR-I6 Idempotent indexing: skip unchanged `content_hash`; on change, delete old
  chunks by `parent_doc_id` and upsert; record `indexed_at`/`index_status`/`chunk_count`.
- FR-I7 Private/login-required pages are stored as link references only, never indexed.

### Retrieval (FR-R)
- FR-R1 Hybrid dense+sparse retrieval over the vector store.
- FR-R2 Metadata-aware routing: map query intent (calendar / fee / policy / registrar /
  library / student-life) to source-kind/category filters before retrieval, with a
  general fallback that searches the whole corpus.
- FR-R3 Two-stage ranking: wide candidate recall → cross-encoder/LLM rerank → **dynamic
  k** (score-threshold + diversity, not a fixed 8).
- FR-R4 Metadata boosts/penalties: boost `official_high` trust and exact
  `policy_code`/`term`/`academic_year`/`event_type` matches; penalize `external_low`.
- FR-R5 Return chunk text + full metadata for citation rendering.

### Agent & conversation (FR-A)
- FR-A1 ReAct agent: classify question type, call the right tool(s), observe, answer.
- FR-A2 Tool calling beyond retrieval — at minimum: general search, source-detail
  lookup, calendar-event lookup, and (Phase 2) student-profile tools.
- FR-A3 In-session short-term memory across turns of one `conversation_id`, with
  history trimming/summarization to bound context.
- FR-A4 Conversation history is context only — never the source of truth for
  fees/deadlines/policy; those require a fresh tool result with citation.
- FR-A5 Strong, versioned system prompt with explicit grounding, refusal, citation,
  deadline-disambiguation, and procedural-answer rules.

### Guardrails (FR-G)
- FR-G1 Input guardrail (compute-efficient): fast deterministic checks for injection,
  abuse, restricted-data probes; cheap classifier for scope; allow-leaning for
  ambiguous in-domain questions.
- FR-G2 Output guardrail: block leaked system prompt/secrets/config; enforce that
  fee/deadline/policy claims carry a citation; **verify answer claims are grounded in
  retrieved text** (faithfulness check) and degrade gracefully otherwise.
- FR-G3 Treat all user and retrieved content as untrusted; never follow embedded
  instructions.
- FR-G4 Refusal responses are friendly, bilingual, and route to official sources.

### Personalization — Phase 2 (FR-P)
- FR-P1 A mock student database (schema in §10) seeded with realistic students.
- FR-P2 Authenticated students get a `student_id` bound to their session/token; tools
  may only read **that** student's data.
- FR-P3 Intent split: "general" → RAG; "personal" → profile tools (+ RAG for the rule
  behind the answer). Personal answers still cite the governing policy where relevant.
- FR-P4 Personal data never leaks across users and is never written to logs in the
  clear beyond what's needed.

### Application & platform (FR-X)
- FR-X1 Email/password login (MVP); SSO later. JWT/session auth.
- FR-X2 Roles: Student (chat + own history) and Admin (sources, logs, unanswered,
  settings). Students cannot reach admin routes.
- FR-X3 Persist chat history per user (Postgres), retrievable in the UI.
- FR-X4 Admin document management: upload PDF/DOCX or add URL; see status
  (pending/indexed/failed), chunk counts; re-index/delete.
- FR-X5 Web chat UI: message stream, citation cards, quick-prompt chips, procedure
  cards, feedback (helpful / not helpful), streaming responses.
- FR-X6 Deployed at a public URL with a demo account.

### Eval & observability (FR-E)
- FR-E1 Golden-set eval scorer (required/forbidden facts, citation validity, refusal
  correctness) over ≥70 cases across calendar / conduct-policy / financial /
  adversarial-private.
- FR-E2 Structured logs + latency metrics for crawl / retrieval / rerank / LLM.
- FR-E3 Capture unanswered/low-confidence questions for the admin "gaps" view.
- FR-E4 Eval runs in CI and on a schedule; regressions are visible.

## 8. Non-functional requirements

- **Accuracy first:** answers grounded + cited; wrong-but-confident is the worst
  outcome. Track and minimize it.
- **Latency:** p50 < 5 s, p95 < 8 s for a typical Q&A turn.
- **Availability:** deployed, single public URL, basic uptime monitoring.
- **Security:** auth + RBAC; per-user data isolation; secrets never in responses/logs;
  admin routes protected.
- **Privacy:** collect the minimum; redact PII in logs; Phase-2 personal data scoped to
  the owner.
- **Maintainability:** sources re-crawlable/re-indexable; idempotent ingestion;
  config in one place; no backend drift between `.env.example` and code.
- **Scalability:** stateless API workers; shared vector + relational stores; memory and
  history in Postgres so multiple workers are safe.
- **Cost control:** cheap models for routing/classification, stronger model for final
  generation; cache embeddings; bounded candidate pools.

## 9. Canonical metadata / filter keys

Indexed on every chunk and usable as retrieval filters:
`source_kind`, `category`, `subcategory`, `policy_code`, `security_classification`,
`academic_year`, `term`, `event_type`, `fee_type`, `source_trust`, `document_type`,
`original_language`. (Schema lives in
[document.py](vinchatbot/app/schemas/document.py); `event_type`/`fee_type` to be added.)

## 10. Mock student data model (Phase 2)

Initial relational schema (Postgres) for personalization — illustrative, to be refined:

- `students` — `student_id`, `full_name`, `email`, `program`, `college`, `cohort`,
  `enrollment_status`, `academic_standing`, `gpa`, `credits_earned`, `advisor`.
- `enrollments` — `student_id`, `term`, `course_code`, `course_title`, `credits`,
  `status`, `grade`.
- `student_fees` — `student_id`, `term`, `fee_type`, `amount`, `currency`, `due_date`,
  `status`.
- `student_deadlines` — `student_id`, `term`, `event_type`, `event_name`, `date`,
  `personalized_note`.

Personal answers are produced by profile tools reading these tables for the
authenticated `student_id`, optionally combined with RAG for the governing rule.

## 11. Target architecture

```
Browser (React/Next chat UI)
        │  HTTPS / JWT
        ▼
FastAPI  ── auth/RBAC ──► Postgres (users, roles, chat history, mock student DB,
        │                          ingest registry, LangGraph checkpoints)
        ├─ Input guardrail (regex + cheap classifier)
        ├─ ReAct agent (LangGraph, per-user memory)
        │     ├─ retrieval tools ─► Qdrant (hybrid dense+sparse) ─► reranker ─► dynamic-k
        │     └─ profile tools (Phase 2) ─► Postgres mock student DB
        ├─ Output guardrail (secrets + citation + faithfulness)
        └─ LLM (OpenRouter: cheap router model + strong generator)

Offline/admin: Crawler ─► Parsers/Cleaning ─► Chunker ─► Embeddings ─► Qdrant
                                                   └─► ingest registry in Postgres
Eval harness (golden sets) ─► CI + scheduled runs
```

## 12. Success metrics

- ≥ 90% of answered questions carry ≥ 1 valid citation.
- ≥ 85% golden-set accuracy (required facts present, forbidden facts absent).
- ≥ 95% correct refusal on the adversarial/private/unsupported subset.
- Zero secret/system-prompt leaks across the red-team suite.
- p95 latency < 8 s.
- Phase 2: zero cross-user data leaks in the isolation test suite.

## 13. Risks & open questions

- **Calendar table fidelity** is the highest-risk retrieval problem; the whole calendar
  eval depends on table-aware chunking. (R)
- **Crawl coverage/quality** of `policy.vinuni.edu.vn` HTML vs PDF versions; which is
  authoritative when both exist?
- **Model choice/cost** on OpenRouter — pick a strong generator and a cheap
  router/classifier; confirm the chosen embedding + rerank model ids are valid on
  OpenRouter and dimension-stable.
- **Mock vs real data** boundary for Phase 2 — keep mock data clearly labeled so it is
  never mistaken for authoritative.
- **Deadline/demo timeline & team size** — confirmed 2026-06-13: ~1–2 month horizon,
  **MVP-public first, personalization (Phase 2) as a stretch goal**. Team size TBC.

## 14. Out of scope (restated)
Real SIS/Canvas writes, acting on the student's behalf, answering without an official
source, and replacing human staff.
