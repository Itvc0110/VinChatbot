# Live-feedback remediation — detailed per-phase plans (Phases 1.9 → 1.18)

> This is the **detailed reference plan** (approved). The live status board + per-phase results live in
> [LIVE_FEEDBACK_TRACKER.md](LIVE_FEEDBACK_TRACKER.md); each phase also gets its own `PHASE1.x_LOG.md`
> as it executes.

## Context
VinChatbot was deployed to real student testers and **10 concrete failure cases** came back. Each
problem is its own phase, executed **one by one** until fixed, with status flipped to done **only after
user verification**. Phase 1.8 (cross-lingual VI↔EN expansion) already shipped, so the new phases run
**1.9 → 1.18**.

**Two cross-cutting realities** drive the ordering:
- Eval is **noise-dominated (~±3 cases / ±2% single-run)**. So the eval-rigor + consistency phase
  (multi-run averaging) lands **before** the A/B-dependent phases (calendar re-ingest, embedding swap)
  — otherwise no later result is trustworthy. Order = dependency order, not issue order.
- **House rules (every phase):** `ENABLE_*`/config-gated · fail-open · **one eval at a time** · never
  trust a run with network errors · **guards (adversarial/safety/unanswerable) must stay 1.000** ·
  scratch Qdrant collection for any re-index · promote only winners · secrets stay in `.env`.
- **Production reference:** `0.885 / 130 cases`; Qdrant `vinuni_documents` (~7,957 pts); models
  `gpt-4o-mini` · `text-embedding-3-small` (1536-d) · `cohere/rerank-v3.5` · `qwen-2.5-7b` (guard).

**Per-phase loop:** implement → offline gates (`pytest -m "not live"` + `ruff`) green → A/B (multi-run
once 1.11 lands) → report to user → user verifies → mark done → next phase.

## Issue → phase map (execution order = dependency order)
| Phase | Issue | Title | Type | Re-index? |
|---|---|---|---|---|
| 1.9  | #1  | Time / current-date awareness | quick win | no |
| 1.10 | #2  | Chat-time rate limiting | ops quick win | no |
| 1.11 | #5  | Consistency: reduce nondeterminism + multi-run eval | **prerequisite** | no |
| 1.12 | #4  | Expansion overhaul: EN↔VI + date-format normalization | medium | no |
| 1.13 | #3  | Calendar correctness: crawler + chunk reshape + year-aware lookup | **large** | yes (scratch) |
| 1.14 | #6  | Embedding A/B for VI+EN | **large** | yes (scratch) |
| 1.15 | #7  | Mass caching + async/parallelization | cost/perf | no |
| 1.16 | #8  | Multi-domain reasoning (single wide retrieval, O(1) rerank) | medium-large | no |
| 1.17 | #9  | Agent-decided expansion (no extra LLM call) | refactor | no |
| 1.18 | #10 | Clarification path (ReAct-decided, no extra LLM call) | UX | no |

---

# Phase 1.9 — Time / current-date awareness (Issue #1)

**Problem.** "What semester am I currently in?" / "how long until add-drop?" fail — the bot has no
notion of *now*.
**Root cause.** Zero current-date injection: `prompts.py` BASE_PRINCIPLES, specialist prompts,
`vinuni_agent.py:chat()` (only a language directive), `tools.py` — none see `datetime.now()`. The
Sep→Aug AY-boundary logic exists in `parsers._date_token_to_iso` but is unused at serving time.
**Plan.** (A) inject "today + current AY + term" into the turn message + frame it in BASE_PRINCIPLES;
(B) a `get_current_datetime` tool for date arithmetic. New `app/core/timeutils.py:current_academic_context`
reuses the Sep→Aug boundary; tz Asia/Ho_Chi_Minh; flag `enable_time_awareness`.
**Live-test learning (built in):** a current-semester answer is uncited (derived from the clock), and
`should_gracefully_degrade` (guardrails.py:470) refuses uncited answers → added a **deterministic
responder**: `is_pure_time_question()` intercepts ONLY pure "which term/year/date is it now?" questions
and answers from `current_time_context()` (no LLM, citing the Academic Calendar); calendar-DATA
questions still flow to the agent.
**Gate.** Unit-test the AY/term boundaries + the detector (positive/adversarial); live smoke
"what semester am I in?"; full eval no regression (additive).

# Phase 1.10 — Chat-time rate limiting (Issue #2)
**Problem.** No protection against a client hammering `/chat` (cost + abuse).
**Root cause.** No limiter in `main.py`/`routes_chat.py`; only ingest has `crawl_rate_limit_seconds`.
**Plan.** Hand-rolled in-process sliding-window middleware (mirrors `request_id_middleware` in
`main.py:19`), keyed by IP/conversation, returns **429** + `Retry-After`, fail-open, `/health` exempt.
Config: `rate_limit_enabled` (default off) + rpm/window/key; Redis noted for multi-replica.
**Gate.** Unit test N→pass, N+1→429, window reset; off-flag = passthrough; eval unaffected.

# Phase 1.11 — Consistency: reduce nondeterminism + multi-run eval (Issue #5) — *prerequisite*
**Problem.** Same question → different answers.
**Root cause.** temp 0.1 hardcoded (`openrouter_chat.py:33`); LLM expansion variants differ per call;
reranker nondeterminism; dynamic-k boundary flips. **User decision: reduce + measure.**
**Plan (reduce).** Per-call `temperature` (0.0 for supervisor routing / expansion / point-lookup strict
extraction; prose configurable via `llm_temperature`); cache `expand_query` by
`(query,model,mode,max_variants)`. **(measure)** `run_eval.py --runs N` → mean ± stdev + a consistency
metric; re-establish a multi-run baseline.
**Gate.** Same 10 cases ×5 → answer-stability ↑; overall mean ≥ 0.885; guards 1.000.

# Phase 1.12 — EN↔VI date-format normalization (Issue #4) — DONE (code), VALIDATED WITH 1.13
**Status.** Shipped: `normalize_date_phrases(query)` (pure regex, no LLM) adds the other canonical
month+year forms ("tháng 6 năm 2026" ↔ "June 2026" ↔ "6/2026") to the query set; gated
`ENABLE_DATE_NORMALIZATION` (default on). Unit-tested (cross-form convergence + no false positives);
live-verified that VI "tháng 10 năm 2026" and "10/2026" return identical events.
**Scope proven (not via the noisy eval):** fires on exactly **2/130** golden cases (both calendar,
passing); the other 128 are byte-identical to pre-1.12 → all non-calendar domains untouched **by
construction**. The single-run 0.869 eval was exonerated as run-to-run noise.
**Why validation is merged into 1.13:** date-norm (query-side) and the calendar chunk-reshape (doc-side)
scope the **same date↔calendar matching problem** — so the *answer-correctness* gate (e.g. June 2026 →
right year) is tested **together** in 1.13's combined re-ingest + multi-run A/B, not measured separately
through the noise. (The date-norm code itself is already live and safe.)

# Phase 1.13 — Calendar correctness (date-norm + chunk reshape + year-aware + crawler) (Issue #3 + #4) — *large, re-index*
**Now also owns Phase 1.12** (query-side date normalization, already shipped): date-norm and the calendar
data fix scope the **same date↔calendar matching problem**, so they are **tested together** here — one
combined re-ingest + multi-run A/B clears the noise band better than measuring each tiny piece.
**Harder calendar test set (user ask):** year-disambiguation (June 2026 vs 2027), adjacent-row
(evaluation-vs-exam, drop-vs-add deadline), publish-date-vs-event-date, cross-lingual date, multi-event
listing, term boundaries, holidays (Hung King / Vietnam Culture Day), cross-AY comparison, and
honest-no-data for un-ingested years — source-verified, added to the golden set.
**Problem.** AY2026-27 calendar (Sep 2026→Aug 2027); asking for June 2026 returns June 2027.
**Root cause (chunk shape, not the date parser).** `_calendar_event_to_text` (chunker.py:356) leads
with ambiguous "2026-2027" + relative "15-Jun" (absolute year buried in the ISO tail); `apply_metadata_boosts`
(context.py:162) boosts when "2026" ⊂ "2026-2027"; only the AY2026-27 calendar is ingested (21 events).
**Plan (do 1+2 first — they're the actual fix).**
1. **Reshape chunk** to lead with absolute "Tháng 6 năm 2027 (2027-06-15)" both languages (vs 1b
   LLM-rewrite to a clean markdown table / 1c retry markdown ingest — A/B these on scratch).
2. **Year/term-aware retrieval:** exact AY/month boost (not substring); optional `academic_year`/`term`
   filter in `search_academic_calendar` (both are Qdrant-indexed); optional deterministic `(month,year)`
   lookup over structured records; combine with 1.9's current-date.
3. **Crawler coverage:** add seeds for all AY calendars — AY24-25 PDF
   (`vinuni.edu.vn/wp-content/uploads/2020/07/VinUni-Academic-Calendar_AY24-25_vF.pdf`), the policy PDF,
   HTML calendar pages; find AY23-24/25-26; **verify each PDF's true span** (URL labeling is unreliable;
   harden `infer_academic_year` to prefer the in-doc title span).
**Fallback (user's idea, only if the universal fix fails the golden gate):** hand-author one clean,
unambiguous doc per AY and ingest those. **Do the universal way FIRST, prove with golden tests, confirm.**
**Gate.** Scratch-collection A/B (multi-run); "6/2026" → correct AY2025-26 or honest "no data" (never
AY2026-27 June); "6/2027" → June 2027; `forbidden_facts` = wrong-year date; calendar ≥ baseline.
Production untouched until a verified winner.

# Phase 1.14 — Embedding A/B for VI+EN (Issue #6) — *large, re-index*
**Problem/goal.** Stronger VI+EN embedding; A/B with & without bilingual expansion vs baseline.
**Grounding.** `build_embeddings` (embeddings/openrouter_embeddings.py:6) = LangChain `OpenAIEmbeddings`
via OpenRouter; dim change ⇒ new (scratch) collection. We already use Cohere for reranking; OpenAI keys
present.
**Research (June 2026).** Cohere **embed-v4** (MTEB 65.2, 100+ langs, strongest cross-lingual, same
vendor as our reranker); OpenAI **text-embedding-3-large** (MTEB 64.6, drop-in, 3072-d); **BGE-M3** free
self-hosted fallback.
**Plan.** Arm 1 = 3-large (cheap to wire, scratch re-index). Arm 2 = Cohere embed-v4 (new adapter,
`input_type`, COHERE_API_KEY). Provider-pluggable config; scratch collection per arm; multi-run eval ×
{bilingual ON/OFF}.
**Folded in (from the 1.11 noise finding): test dropping the LLM cross-lingual translation.** The
always-on VI↔EN *translation* variant is the dominant run-to-run **nondeterminism** source (an LLM call
that varies even at temp=0 → different retrieval → eval swings ~±8). A strong multilingual embedding may
make a VI query vector match EN docs **directly**, so the translation variant becomes unnecessary. So
the A/B grid gains a third axis: **cross-lingual translation ON vs OFF** per embedding arm. If an arm
holds recall with translation OFF, we **remove the translation call** → retrieval becomes deterministic
*by construction* (the real cure for the consistency noise, not a cache/seed mask). Metric: recall +
**run-to-run stability** (reuse `consistency_probe.py`), not just pass-rate.
**Gate.** Promote only if mean beats the current reference by > noise band AND cost acceptable; guards
1.000; **prefer the config that lets translation be turned OFF without losing VI recall** (determinism
win). Decision + cost recorded before any production re-index. Revert = repoint `qdrant_collection`.

# Phase 1.15 — Mass caching + async/parallelization (Issue #7)
**Problem/goal.** Little is cached (only conversation history); find async wins.
**Plan (flag-gated, cold-cache-transparent).** (a) ~~expansion/translation cache~~ **CUT** — it would be
throwaway if 1.14 removes the translation (translation-OFF via multilingual embedding); (b) ingest
embedding content-hash cache (~25-30% re-index saving); (c) rerank cache by `(query, candidate chunk_ids)`;
(d) optional hot-Q&A answer cache (TTL, off by default). Async: overlap safe guard/retrieval; document
serial routing→specialist. Cache-hit counts in `_log_turn`.
**Gate.** Eval no regression on a cold cache; measure latency/cost delta.

# Phase 1.16 — Multi-domain reasoning (Issue #8)
**Problem.** "học phí trên mỗi tín chỉ các ngành?" fails (per-credit tuition across all programs);
"tổng số tín chỉ các ngành" and "học phí các ngành học" each work.
**Root cause.** Single-intent routing; 8-chunk cap (`retrieval_max_k`); `fee_record` has no
per-credit/credits fields → needs cross-dimension compute or a full per-program list.
**Cost model (user-confirmed).** Decomposition into N sub-questions = **O(N) rerank** (each sub-question
reranks), and a detector tuned not to miss aggregation over-triggers → **rejected**.
**Better lever (no heuristic, O(1) rerank).** Cohere bills per *search call* (≤100 docs), not per doc →
a **single wide retrieval with larger `candidate_k`/`max_k`, reranked ONCE** surfaces all program rows
in one context at the same rerank price. "List mode" (bigger pool/k) is set via the **agent's existing
tool-call argument** — no regex heuristic, no extra LLM call. Optional `fee_record` per-credit fields
for the compute case. Decomposition only a rare, bounded last resort.
**Gate.** All three queries pass (multi-run); **rerank calls/turn stay O(1)** (`_log_turn`);
single-domain financial no regression; guards 1.000.

# Phase 1.17 — Agent-decided expansion (Issue #9)
**Problem/goal.** Expansion is always-on in `_search` (tools.py:58-65); the agent should decide.
**Cost constraint (user): no unnecessary LLM calls — fold into the agent's existing call.**
**Plan.** Separate expansion sub-tools (each an extra ReAct loop / LLM call) → **rejected**. Instead:
expansion options as **arguments on the existing search tool call** (`search(query, expand={...})`),
optionally informed by the supervisor's widened routing JSON. Deterministic helpers (1.12 dates,
`is_point_lookup`) run free inside `_search`. Auto-expansion stays the default behind the flag until the
A/B clears. **Depends on 1.12 + 1.16.**
**Gate.** Correct expansion choices with **no increase in LLM calls/turn** (`_log_turn`) and no added
latency on simple queries; multi-run A/B ≥ baseline.

# Phase 1.18 — Clarification path + don't-over-refuse (Issue #10 + guard-precision)
**Problem/goal.** Two sides of "the bot wrongly declines to help": (a) when context is missing it guesses
instead of asking back; (b) the scope guard **over-refuses legitimate in-scope questions**.
**Cost/efficiency constraint (user): "react and reasoning when to ask back, make it efficient."** The
ask-vs-answer decision rides the agent's **existing ReAct reasoning** — no separate ambiguity-classifier
LLM call.
**Plan (a) clarification.** A prompt rule (BASE_PRINCIPLES/specialists): "before answering, reason whether
a required scope is missing (which AY? which program? unresolved 'này/đó'?) — if so ask ONE concise
clarifying question, else answer." Free rule-only guards sharpen the known cases (calendar year, fee
program); a `clarification` action for the frontend. Tuned to **avoid over-asking**.
**Plan (b) guard over-refusal (moved here from the 1.12 finding).** Reproducible bug: "What deadlines or
events are there in October 2026?" is **deterministically refused as out_of_scope** — the **rule tier**
returns `needs_scope_router` for that EN "events/deadlines" phrasing → the LLM scope classifier then
wrongly rejects it (VI equivalent + "When is the course drop deadline?" pass). Fix = raise the rule-tier
in-scope recall for legitimate EN calendar/academic phrasings (and/or tighten the LLM scope-classifier
prompt) so genuine student questions aren't refused — **without** lowering adversarial/safety/out-of-scope
recall. (Guards run at temp 0.1, untouched — a residual nondeterminism source to keep in mind.)
**Gate.** Ambiguous → one clarifying question; clear → answers directly (no over-ask); the EN-calendar
phrasing + a small set of legit in-scope EN/VI questions now **pass** the guard; no extra LLM calls/turn;
**adversarial/safety/unanswerable guards stay 1.000**.

---

## Cross-phase verification & discipline
- **Per phase:** offline `pytest -m "not live"` + `ruff` green → multi-run A/B (from 1.11) → report →
  user verifies → flip tracker. **One eval at a time.**
- **Hard gate every phase:** guards = **1.000**; overall mean ≥ current reference; no prose pass→fail
  flips in `--diff`.
- **Re-index phases (1.13, 1.14):** scratch collection only; production untouched until verified.
- **Docs:** each completed phase → its `PHASE1.x_LOG.md` + tracker checkbox; at arc end, fold outcomes
  into `worklog.md` / `PROJECT_JOURNAL.md` / `UPDATE_PLAN.md`.
