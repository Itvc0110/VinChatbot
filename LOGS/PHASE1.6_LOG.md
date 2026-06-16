# Phase 1.6 — Rerank cost reduction — Plan + Log

Goal: cut **rerank spend** (Cohere `rerank-v3.5` via OpenRouter, **$0.001 per "search"** = 1 query,
≤100 docs) without regressing the proven eval band. Motivated by the Phase 1.5 cost finding: rerank
is often the **largest single per-turn cost line** — comparable to or above the answer model.

Legend: [ ] todo · [~] in progress · [x] done · [-] deferred.
House rules: `ENABLE_*`-gated; **no regression** to the current **0.930 / floor 0.919 (80-subset
0.912)** band ([PHASE1.4_LOG.md](PHASE1.4_LOG.md), [PHASE1.5_LOG.md](PHASE1.5_LOG.md)); A/B before
promotion; **one eval at a time** (PHASE1.4 quota lesson); build on existing code.

> **Status: SHIPPED ON (2026-06-16, user decision).** `ENABLE_RERANK_AFTER_FUSION` default flipped to
> `true`: the user accepted the **~1-case tradeoff (0.930→0.919, on the floor)** for the **>66.7%
> rerank-cost cut** (3→1 calls/multi-query turn). Guards stay 1.000.
> **Caveat from the root-cause dive (below):** one of the two lost calendar cases is a *confidently
> wrong adjacent date* (worse than a miss) — calendar point-lookups are the sensitive spot.
> **Follow-ups requested by user:** (1) enhance the (too-small, 86-case) eval set; (2) the calendar
> point-lookup precision loss is the prime candidate for a **calendar-scoped** refinement.

---

## Root cause (traced 2026-06-15)

- Query expansion (`expand_query`, `ENABLE_QUERY_EXPANSION=true`, `max_variants=2`) → up to **3 query
  variants** ([query_engineering.py](../vinchatbot/app/rag/query_engineering.py)).
- `_search()` ([tools.py:39-58](../vinchatbot/app/agents/tools.py#L39)) runs `retriever.search()` once
  **per variant** (`asyncio.gather`); each `search()` reranks its own 40-doc candidate pool
  ([retriever.py:159-169](../vinchatbot/app/rag/retriever.py#L159)). RRF fusion happens **after**
  per-variant rerank → **~3 rerank calls per tool invocation**.
- Cohere bills per *search* (≤100 docs), so reranking 40 vs 20 docs is the same price — **the lever is
  the number of rerank calls, not pool size**.
- Net ≈ 3 rerank/tool-call × (tool calls/turn) ≈ **$0.003–0.006/turn** vs the measured chat-model
  ~$0.0013–0.0045/turn. `get_source_detail` also reranks (its `limit=5` → `candidate_k=40`).

## Fix #1 — rerank once, after RRF fusion (primary)

Make reranking happen a **single time on the fused pool** instead of per variant:
1. Per variant: retrieve candidates **without** reranking (vector+BM25 only — no Cohere call).
2. RRF-fuse the per-variant lists → dedup.
3. **Rerank the fused pool once**, keyed on the *original* user query (best signal), bounded `top_n`.
4. metadata boost → dynamic-k → LITM reorder (unchanged tail).

Effect: **3 rerank calls → 1** per tool invocation (~67% rerank cut), plausibly *better* quality
(rerank sees the fused, more diverse candidate set). The single-query path is already 1 rerank →
unchanged.

### Implementation (as built)
- [x] `QdrantHybridRetriever.search()` split into `_fetch_candidates()` (vector/BM25, `score=None`) +
  `_finalize()` (rerank → dedup → boost → dynamic-k → parent-doc → LITM). `search()` =
  `_fetch_candidates` → `_finalize` (output-equivalent; baseline eval confirmed identical 0.930).
- [x] Added public `search_candidates()` (= `_fetch_candidates` + dedup, **no rerank**) and
  `rerank_fused()` (= `_finalize` on a passed-in fused list) to the `Retriever` Protocol +
  `QdrantHybridRetriever`; trivial impls on `InMemoryRetriever`.
- [x] `_search()` multi-query branch ([tools.py](../vinchatbot/app/agents/tools.py)): when the flag is
  on, `gather(search_candidates(v))` → `reciprocal_rank_fusion` → `dedup_by_text` → cap to
  `retrieval_candidate_k` → `rerank_fused(original_query, fused)`. Flag-off path kept verbatim.
- [x] Gated behind `ENABLE_RERANK_AFTER_FUSION` ([config.py](../vinchatbot/app/core/config.py),
  default `false`; `.env.example`). Fail-open via the unchanged flag-off fallback.
- [x] **Measurement:** per-turn rerank-call counter (contextvar in
  [observability.py](../vinchatbot/app/core/observability.py), incremented in
  [reranker.py](../vinchatbot/app/rag/reranker.py), reset per turn) surfaced as `rerank_calls` in the
  `_log_turn` line ([vinuni_agent.py](../vinchatbot/app/agents/vinuni_agent.py)).

### Files
- [retriever.py](../vinchatbot/app/rag/retriever.py) · [tools.py](../vinchatbot/app/agents/tools.py) ·
  [reranker.py](../vinchatbot/app/rag/reranker.py) · [vinuni_agent.py](../vinchatbot/app/agents/vinuni_agent.py)
  (turn-log field) · [config.py](../vinchatbot/app/core/config.py) + `.env.example`.

## Validation
- [x] Unit ([tests/test_retrieval.py](../tests/test_retrieval.py)): counting fake retriever +
  monkeypatched 3-variant `expand_query` — flag-on path calls `rerank_fused` **exactly once**
  (`search_candidates` ×3, `search` ×0); flag-off path calls `search` ×3. Both pass.
- [x] `pytest -m "not live"` → **112 passed**, 2 failed (pre-existing `test_chunker.py` docx/markdown,
  unrelated — verified clean-HEAD identical in 1.5a); `ruff check .` clean.
- [x] A/B live eval (sequential): **baseline flag-off `eval_20260615T175500Z.json` = 0.930**
  (identical to pre-refactor → refactor is behavior-equivalent); **candidate flag-on
  `eval_20260615T180623Z.json` = 0.919**.

## Secondary levers (documented; only if #1 underwhelms)
- `max_variants` 2 → 1 (independent config knob; smaller recall hit, halves expansion+rerank).
- Per-turn rerank/result cache for repeated queries.
- Adaptive skip of expansion+rerank for simple lookups → ties to Adaptive-RAG in
  [../FUTURE_IMPROVEMENTS.md](../FUTURE_IMPROVEMENTS.md) §B.

## Risks
- Reranking the fused pool vs per-variant shifts ranking → **must A/B**; mitigated by flag + fallback.
- `get_source_detail`'s rerank left as-is (minor; note for later).

---

## Execution log

### 2026-06-15 — implemented + A/B-tested; kept default-off (not promoted)

**Built** the rerank-after-fusion path exactly as in "Implementation (as built)" above, default-off,
fail-open. Offline gates green (112 passed; rerank-once unit test confirms 3→1).

**A/B (86 cases, gpt-4o-mini, serving collection, one eval at a time):**

| Category | Baseline OFF (`…175500Z`) | Candidate ON (`…180623Z`) | Δ |
|---|---|---|---|
| **overall** | **0.930** | **0.919** | **−1 case** |
| calendar (28) | 0.929 | 0.857 | −2 |
| services (5) | 0.800 | 1.000 | +1 |
| financial / policy_conduct / conduct / multiturn | 0.875 / 0.714 / 1.0 / 1.0 | = | = |
| adversarial / safety / unanswerable (guards) | 1.000 | 1.000 | = |
| facts_ok / citation_ok | 0.953 / 0.977 | 0.930 / 0.988 | citations ↑ |

Baseline OFF = **0.930, identical to the pre-refactor run** → the `search()` split is
behavior-equivalent (no hidden regression from refactoring).

**Exact cases that flipped (report diff):**
- **Lost (calendar, VI point-lookups):** `calendar-fall-final-schedule-vi`,
  `calendar-summer-final-exams-vi`. Reranking the *fused* pool once changes which exam-schedule chunk
  ranks top; calendar is point-lookup tabular data (exact chunk matters) and the VI/EN cross-lingual
  gap compounds it.
- **Gained (thin domain):** `svc-library-services`. The broader fused candidate pool surfaces the
  library chunk that per-variant rerank kept burying.

**This is the parent-doc pattern again (PHASE1.4):** helps services/library, hurts calendar
point-lookups, **net wash-to-slightly-negative**. Mechanism understood, not noise (calendar 0.857 is
below the observed 0.893–0.929 nondeterminism band).

**Decision: keep `ENABLE_RERANK_AFTER_FUSION=false` (default) — NOT promoted.** Per "promote only
winners," a −1 net with a real calendar regression doesn't flip the default, even though it sits on
the 0.919 floor and the **cost win is real (~67% rerank reduction, 3→1)**. The flag is validated and
available for cost-sensitive deployments that accept the calendar tradeoff. No production change.

**Recommended next step:** a **calendar-scoped** variant — keep per-variant rerank for the
`search_academic_calendar` tool, use fusion elsewhere — directly mirrors the proven
`PARENT_DOC_SKIP_SUBCATEGORIES=calendar` precedent. Plausibly captures the +services win and the cost
cut **without** the −2 calendar loss. Needs its own A/B.

### 2026-06-16 — SHIPPED ON (user decision) + root-cause deep-dive

**Decision reversed → ship:** user accepted the ~1-case quality cost for the >66.7% rerank saving.
`enable_rerank_after_fusion` default → `true` ([config.py](../vinchatbot/app/core/config.py)),
`.env.example` → `true`. Offline gates re-confirmed green (ruff clean; retrieval tests pass). Current
default behavior is now the fused-rerank path at the **0.919** band.

**Root-cause of the two lost calendar cases (report diff, baseline vs candidate):**
- `calendar-fall-final-schedule-vi` — Q: when is the Fall-2026 exam schedule *published*? (required
  "7 tháng 12 năm 2026"). Baseline answered the **publish date + exam window**; candidate dropped the
  publish-date chunk → answered only the exam window → **missing required fact**.
- `calendar-summer-final-exams-vi` — Q: Summer-2027 exam dates (required Aug 23–27). Baseline:
  **"23 đến 27 tháng 8"** ✓. Candidate: **"16 đến 20 tháng 8"** — a **confidently WRONG adjacent
  date** (a neighbouring row of the calendar grid). This is the dangerous point-lookup failure mode.

**Insight:** fusing 3 variants then a *single* rerank dilutes the precise top-1 that per-variant
rerank nailed; for point-lookup tabular data (many near-identical "exam: <range>" rows) "a different
chunk" becomes "a different (wrong/adjacent) date." This is precision loss, **not scorer noise**
(calendar 0.857 sits below the observed 0.893–0.929 band), and case 2 is a correctness regression
worse than a refusal. **Strengthens the calendar-scoped refinement** as the right fix, and motivates
the eval-set expansion (86 cases ⇒ ±1.2% per case; the calendar bucket needs more point-lookup cases
to make this signal robust).
