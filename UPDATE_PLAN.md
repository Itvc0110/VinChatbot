# VinChatbot — Update Plan / Roadmap

> Canonical engineering roadmap. Pairs with [PRD.md](PRD.md). Consolidates and supersedes the
> scattered backlog in [todo.md](todo.md). Last updated: 2026-06-14.

> **Phase scheme (major phase = a big change):** **Phase 1 — core RAG chatbot (DONE, sub-phases
> 1.0–1.4)** · **Phase 2 — personalization** · **Phase 3 — product & platform**. Per-sub-phase
> logs live in [LOGS/](LOGS/); the research-backed AI-quality depth backlog lives in
> [FUTURE_IMPROVEMENTS.md](FUTURE_IMPROVEMENTS.md).

Ordering principle: **make it correct and measurable before making it smart.** Every (sub-)phase
ends with a check you can run.

Legend: 🔴 blocking bug · 🟠 quality gap · 🟢 new capability.

---

## Phase 1 — Core RAG chatbot (DONE — eval-gated; logs in `LOGS/`)

Built and validated end-to-end (crawl → ingest → chat → eval). Current production: **0.919 on 86
golden cases**, plain-text pipeline, `gpt-4o-mini`, Qdrant Cloud `vinuni_documents` (7,957 points).

- ✅ **1.0 — Foundation** ([LOGS/PHASE1.0_LOG.md](LOGS/PHASE1.0_LOG.md)): 761-doc Qdrant Cloud
  corpus, LangGraph supervisor→specialist multi-agent, two-tier CI, eval harness. Baseline **47.2%**.
- ✅ **1.1 — Quality & Safety** ([LOGS/PHASE1.1_LOG.md](LOGS/PHASE1.1_LOG.md)): language honoring,
  lost-in-the-middle reorder, dynamic-k, dedup, multi-query (RRF), small-LLM guard + de-obfuscation
  + indirect-injection scan, calendar/fee clean chunks. **93.1%** (58 cases).
- ✅ **1.2 — Metadata, layered guards, eval, viz** ([LOGS/PHASE1.2_LOG.md](LOGS/PHASE1.2_LOG.md)):
  metadata engineering (event_type/fee_type, policy_code propagation, source_trust/term boosts, soft
  routing, image-chunk exclusion → 7.8K index), layered API guard (OpenAI omni-moderation → small-LLM
  injection/scope), eval → 80 cases, [ARCHITECTURE.md](ARCHITECTURE.md) flow diagrams. **92.5%**.
- ⚖️ **1.3 — Ingestion v2 experiment: REVERTED** ([LOGS/PHASE1.3_LOG.md](LOGS/PHASE1.3_LOG.md)):
  markdown-first parsing + header/token chunker netted ≤81% < 92.5% (PDF markdown broke
  `calendar_event` extraction; over-fragmentation). Markdown kept gated **off**. **Kept:** DOCX
  parsing/routing (new dtype), tiktoken/splitter deps.
- ✅ **1.4 — Retrieval/eval/coverage + fixes** ([LOGS/PHASE1.4_LOG.md](LOGS/PHASE1.4_LOG.md)):
  **faithfulness false-positive fix** (citation/policy-code digits no longer force refusals) and
  **conversational-handling fix** (rule-tier `smalltalk`/`capability` intents + full-VN
  `answer_language`); parent-document retrieval / gpt-4o / prompt-tightening built/tested but
  **gated off or rejected** with reasons; +6 Code-of-Conduct golden cases (set → 86). **0.919.**

> Process: update this section at the end of every (sub-)phase. The AI-quality depth backlog (eval
> framework, observability, contextual retrieval, near-dup dedup, cross-lingual retrieval fix) is
> tracked in [FUTURE_IMPROVEMENTS.md](FUTURE_IMPROVEMENTS.md).

---

## Phase 2 — Personalization (mock student system) — NEXT major change

Goal: an authenticated student can ask about themselves, with strict isolation. (PRD §6.2 / §10.)

- 🟢 **Mock student DB.** Postgres schema in [PRD.md](PRD.md) §10 (`students`, `enrollments`,
  `student_fees`, `student_deadlines`) + a realistic seed.
- 🟢 **Profile tools.** `get_student_profile`, `get_student_enrollments`, `get_student_fees`,
  `get_student_deadlines` — each takes the **authenticated** `student_id` from the session, never
  from the prompt.
- 🟢 **Personal vs general intent.** Router decides personal (→ profile tools, +RAG for the governing
  rule) vs general (→ RAG). Personal answers still cite the relevant policy.
- 🟢 **Isolation tests.** Prove user A can never read user B's data via prompt tricks.
- ✅ Acceptance: personalized answers correct against seed data; isolation suite green.

---

## Phase 3 — Product & platform (deployable web app) — teammates

Goal: meet the brief's "deployed app with login, roles, history, admin." Hand-off specs (API
contracts, data models) in [FUTURE_IMPROVEMENTS.md](FUTURE_IMPROVEMENTS.md) Part 2.

- 🟢 **Auth + RBAC.** Email/password, JWT/session, Student/Admin roles; protect `/ingest/run` and
  admin routes (currently open).
- 🟢 **Chat history persistence** per user in Postgres (checkpointer scaffolding already in
  `vinuni_agent.py`), exposed via API + UI.
- 🟢 **Admin document management.** Upload PDF/DOCX or add URL; status (pending/indexed/failed) +
  chunk counts; re-index/delete; backed by a source registry.
- 🟢 **Frontend.** React/Next chat UI: streaming, citation cards, quick-prompt chips, procedure
  cards, helpful/not-helpful feedback; admin dashboard (Documents / Upload / Chat Logs / Unanswered).
- 🟢 **Streaming responses** from `/chat`.
- 🟢 **Deploy.** Dockerfile + compose (API + Qdrant + Postgres); backend (Render/Railway/Fly),
  frontend (Vercel); public URL + demo account.
- ✅ Acceptance: a student logs in, chats, sees history; an admin uploads a doc and sees it indexed;
  reachable at a public URL.

---

## Ongoing — eval, observability, hardening

Runs continuously; the detailed, research-backed backlog is in
[FUTURE_IMPROVEMENTS.md](FUTURE_IMPROVEMENTS.md).

- 🟢 **Eval framework:** retrieval recall@k / nDCG, LLM-as-judge tier, run-over-run regression diff,
  latency/cost capture, held-out non-circular set.
- 🟢 **Observability:** Langfuse tracing + token/cost capture; readiness probe; user-feedback loop.
- 🟢 **Red-team suite** for injection/abuse/secret-leak/private-data, run in CI.
- 🟢 **CI:** `pytest`, `ruff`, `compileall`, nightly eval with a regression gate.

---

## Suggested sequencing

> Confirmed 2026-06-13: ~1–2 month horizon, **public Q&A first**, personalization a stretch.

1. **Phase 1 (1.0–1.4)** — DONE.
2. **Phase 3 (platform)** in parallel (teammates) — auth + minimal UI + deploy land on the current
   backend; this is the brief's graded requirement.
3. **Phase 2 (personalization)** once public Q&A is solid and the mock DB is ready (stretch).
4. **Ongoing** eval/observability/hardening throughout — every change re-scored on the golden set.
