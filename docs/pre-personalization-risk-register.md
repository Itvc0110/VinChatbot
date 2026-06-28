# Pre-personalization risk register (failure-mode brainstorm)

**How this was produced:** an automated multi-agent scan (7 reviewers, one per subsystem) of the
**pre-Phase-5** VinChatbot code, surfacing **82 candidate failure modes**, distilled below.
**Verification status:** headline items spot-checked against the code (marked ✅); the rest are
**candidates — confirm before fixing** (the automated verify pass wasn't run). This is a backlog/triage
aid, not a list of confirmed bugs. Severity = impact × likelihood.

> Two items are already documented elsewhere: the out-of-scope-task guardrail gap (being fixed next) and
> the academic-vs-portal course inconsistency (see `docs/data-model-inconsistency.md`).

## P0 — fix soon (security, low effort)

- ✅ **`/ingest/run` and `/sources` are fully UNAUTHENTICATED** (`routes_ingest.py:26,70` — no `Depends`).
  Anyone who can reach the API can trigger a full crawl + re-ingest (cost blowup, DoS, **index/data
  poisoning**) or enumerate sources. **Fix:** require an admin/service role (or an internal-only network).
  *Quick win.*
- **Login has no rate-limit / lockout** (`routes_auth` + `AuthRepository`) → unrestricted password
  brute-force. **Fix:** per-account + per-IP attempt limiting + backoff. *Quick win.*
- **Rate-limit trusts `X-Forwarded-For` unconditionally** → trivially spoofed to bypass the limiter; and
  it's in-process only (bypassed across replicas). **Fix:** trust XFF only from known proxies; use a shared
  store for multi-replica.
- **`/chat` + `/chat/stream` accept anonymous requests** (`get_optional_current_user`). Given Vinnie is
  auth-only (see memory), enforce a verified session server-side. *Quick win.* (Also closes the personal
  path defensively.)
- **`conversation_id` (LangGraph `thread_id`) is client-controlled with no ownership check** — a caller
  who guesses/reuses another thread id could read its in-memory turn history. **Fix:** namespace the
  graph thread id by authenticated user id, or verify ownership.

## P1 — input guardrails (the "answers out-of-scope tasks" cluster — precision target)

- **Out-of-scope tasks bypass the guard via `SCOPE_TERMS` coincidence** (`assess_user_message`): "write
  code about the exam schedule", "make a rhythm about tuition" contain an in-scope keyword → fast-allowed.
  This is the gap the user reported. **Fix (next task):** an explicit out-of-scope-TASK detector
  (code/poem/song/rhythm/story/translate/solve-math/roleplay) that fires BEFORE the scope fast-allow —
  precision-first, never catching a legit student question.
- **LLM scope-guard fails OPEN** (`resolve_guardrail_decision` / `classify_with_llm`): on an OpenRouter
  error or missing key it silently allows everything. **Fix:** fail to the deterministic verdict, not allow.
- **Gray-scope router prompt is over-permissive** (`route_gray_scope_with_model`): instructs the model to
  prefer "allow" when unsure → off-topic leaks through.
- **`INJECTION_PATTERNS` miss Unicode / mixed-script / indirect phrasing**; **`RESTRICTED_DATA_PATTERNS`
  miss possessive/implicit references**. (The latter is partly intentional now for the authenticated
  own-data path.)
- **Safety guard is off by default for confident allows** (`enable_safety_on_all`) and fails open → abuse/
  threats inside an in-scope message aren't moderated.

## P1 — output guard / faithfulness (silent wrong answers)

- **`output_audit.audit_output` fails OPEN** — a transient OpenRouter error/rate-limit silently passes a
  potentially wrong answer. **Fix:** fail-closed (degrade) on auditor error.
- **`assess_faithfulness` is lenient** (any-overlap heuristic) → grounded-but-wrong answers pass; the
  **year ±1 tolerance** lets an answer about an adjacent year not in the docs through.
- **LLM-auditor evidence cap (8000 chars)** can truncate the relevant chunk → false "ungrounded".
- **`should_gracefully_degrade` false-positives** on any no-citation answer (mitigated for personal by
  `trusted_app_data`, but order-sensitive).
- **Secret-scan markers (`SENSITIVE_OUTPUT_MARKERS`) are narrow** — only literal config-key names.

## P1 — RAG retrieval correctness/robustness

- **Structured fee lookup: first `table_record` row wins** — later authoritative rows silently dropped.
- **Structured calendar lookup false-match** — event-type classifier returns the wrong type on bilingual
  mixed queries.
- **Structured-lookup global singleton never refreshes after an index rebuild** → stale answers until
  process restart.
- **Canonical doc-pin returns empty context for a stale/404 pinned URL** → silently degrades to vector-only.
- **Empty-retrieval not distinguished from low-score retrieval** — if the vector store is unavailable the
  agent may hallucinate instead of declining.
- Lower: cross-lingual miss when reactive expansion doesn't trigger; dedup Jaccard 0.9 too lenient for
  bilingual near-dupes; dynamic-k can collapse to min_k=3 on reranker fallback; metadata boost can push
  scores >1.0 and confuse the audit threshold.

## P2 — robustness / infra

- **`InMemorySaver` (default checkpointer) grows unboundedly and is never purged** — memory leak in a
  long-running process. **Fix:** TTL/size cap, or use the Postgres saver in prod.
- **`PostgresSaver` opened via a sync context-manager inside the async service** — leaks a thread; its
  `__exit__` is never called on shutdown (dangling connection).
- **Session lookup runs ~3 DB queries per authenticated request** (N+1 on a hot path). **Fix:** single
  join / cache.
- **Duplicate guardrail run** — `resolve_guardrail_decision` runs once in `routes_chat._resolve_chat` and
  again in `vinuni_agent.chat()` (double cost/latency per turn). *Quick win: run once.*
- **Unbounded result sets** in `list_topics` / `list_messages` / `get_student_transcript` / `get_courses`
  (no LIMIT/pagination).
- **Suspended/inactive users keep usable sessions** until natural expiry (up to 7 days).

## P2 — data quality / persistence

- **Academic-vs-portal course inconsistency** — see `docs/data-model-inconsistency.md`.
- **Fan-out citation list can include irrelevant sources** — `fanout_node` passes ALL subtask
  ToolMessages' citations to the output guard even if the synthesized answer doesn't use them.
- **Guardrail-blocked turns persist the user message but not the assistant reply** → orphan user-message
  rows in conversation history.
- **`append_message` ownership re-check inside the transaction is a TOCTOU race**; `list_messages` orders
  by second-resolution `created_at` → non-deterministic order for rapid inserts.
- **PII in Langfuse traces** — `student_id`, `full_name`, `advisor_email` not masked by the scrubber; and
  `get_my_profile` echoes `advisor_email` (a PII field) with no redaction check.

## Likely false positives (de-prioritized)

- "SQL injection via `target_type` in forum_votes" — `target_type` is a **literal** `'topic'`/`'comment'`
  in those queries, not interpolated user input. The real forum SQL surface is **`list_topics` building
  sort/field names via f-string** (whitelist the allowed columns/sort keys).

## Cross-cutting themes

1. **Fail-OPEN everywhere** — LLM scope-guard, safety guard, and output-auditor all default to "allow/pass"
   on error or when disabled. For an auth-only student assistant, several should fail-CLOSED (or to the
   deterministic verdict).
2. **Unauthenticated/again-checked endpoints** — `/ingest`, `/sources`, anonymous `/chat`, client-set
   `conversation_id`: the API layer is more open than the product (sign-in-only) assumes.
3. **Heuristic guards are keyword-coincidence-fragile** — both under-block (out-of-scope tasks with an
   in-scope keyword) and over-block (legit questions); the LLM tiers that should catch the residue are
   over-permissive or fail-open.
