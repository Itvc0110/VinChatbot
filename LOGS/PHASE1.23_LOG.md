# Phase 1.23 — Determinism & mass cache

> Roadmap: `UPDATE_PLAN.md` (step A2). Plan: `.claude/plans/can-we-try-to-merry-mango.md`
> (1.23b mass-cache deep-dive). Goal: reduce run-to-run noise at the *generation* source — both by removing
> float-edge nondeterminism (1.23a) and by making LLM/rerank calls reproducible via cache (1.23b). Sub-parts:
> **1.23a** retrieval/rerank determinism · **1.23b** exact-match Redis cache · **1.23c** routing determinism (next).

## 1.23a — Retrieval & rerank determinism  (DONE, offline-verified)
**Trial:** float-edge nondeterminism (rerank ties, dynamic-k cutoff) + (discovered during 1.23b) a
non-deterministic **candidate order** from Qdrant were shuffling retrieval run-to-run.
**Changes ([retriever.py](../vinchatbot/app/rag/retriever.py)):**
- `stable_rerank_order` + `_round_score` (`_SCORE_NDIGITS=3`): rerank sort = rounded-score DESC, ties by
  index; the stored chunk score is rounded so the reactive-trigger + dynamic-k cutoffs don't flip on jitter.
- **`_fetch_candidates` now fetches WITH scores and sorts by `(round(score) DESC, chunk_id)`** — the root fix
  for the cache cascade (below). Qdrant hybrid returns the same SET in a non-deterministic ORDER; this makes
  the relevance order reproducible (RRF still gets relevance-ranked lists; rerank gets a stable input).
**Verify:** `search_candidates ×3` → **identical** (was diverging at rank 3). One determinism unit test
(`tests/test_determinism.py`). Behavior-neutral by design (rerank still determines final relevance).

## 1.23b — Exact-match Redis cache of LLM + rerank  (DONE code; cross-run hits confirmed)
**Trial:** LLM calls (route/expansion/answer/guards) + cohere rerank are the only nondeterministic +
expensive steps → cache them keyed on the FULL input → reproducible (kills noise) + cheaper.
**Changes:** new [cache.py](../vinchatbot/app/core/cache.py) (fail-open redis client + `redis_get/set` +
`RedisLLMCache(BaseCache)`); `install_llm_cache` wired lazily in `build_chat_model` (covers server + eval);
rerank wrapped in [reranker.py](../vinchatbot/app/rag/reranker.py) (cache before cohere, fail-open). Config +
`.env` (`REDIS_URL`, `ENABLE_LLM_CACHE`, `ENABLE_RERANK_CACHE`, `CACHE_VERSION=v1`, 30-day TTL). `redis` dep
added. Keys = `{CACHE_VERSION}:{ns}:{blake2(prompt/content)}` → A/B-safe (a real change alters the prompt →
miss → recompute) + version-safe; **fail-open** everywhere.
**Experiment / the bug we hit + fixed:**
- Live 2-call LLM probe: hit (243 ms vs 1759 ms). ✓ async path works.
- First `--runs 3` eval test: cache keys kept **GROWING** run-to-run (302→635…) → **no cross-run hits.**
- **Diagnosis (offline, no costly eval):** `embed_query ×2` identical (0 diff → embeddings NOT the cause);
  `search_candidates ×2` = same set, **different order** (diverge @ rank 3) → the shuffled candidate list
  drifted the rerank `documents` (order-sensitive key) + the answer context → cache misses cascaded.
- **Fix = the 1.23a deterministic candidate sort.** Re-verified end-to-end (2 fresh agent turns, same Q):
  **run 2 added 0 LLM + 0 rerank keys (100% hits)**, identical answer, 2.0× faster. ✓
**Verify:** full offline suite **318 green**, ruff clean; `tests/test_cache.py` (4: fail-open ×2, version
namespacing, LLM round-trip).
**Progress / honest scope (per review):**
- Cache now hits cross-run. **Value = eval determinism + clean A/B diffs** (unchanged cases freeze → no
  spurious noise flips) **+ fast dev re-runs.** It is **NOT a production cost play** (paraphrases/novel
  queries miss → recompute) and does **NOT** justify ×3-with-cache (runs 2–3 trivially replay → **workflow =
  N=1**). The residual noise it can't remove = the *changed* cases in an A/B (cache miss → single live sample).
- **Kept** (it's free + helps A/B integrity). `.env` cache ON.
- **NOT yet measured:** the eval-score impact of the 1.23a/b determinism changes (a full run is costly — the
  user paused runs). The changes are behavior-neutral by design; a clean cached baseline run is **deferred**.
- Redis is the user-provided public endpoint (rotate the pasted credential; set `allkeys-lru` in the
  dashboard). ElastiCache swap deferred (VPC-private → not reachable from local eval). No git commit.

## 1.23c — Routing determinism  (CODE DONE, offline-verified; A/B deferred)
**Trial:** `courseeval-vi` is a stable-fail because the supervisor mis-routes a *policy* question ("is there
an end-of-course evaluation?") to **calendar** (it shares the "evaluation" topic with "when is the eval
period?"). Also: keep the LLM out of obviously-keyworded routings.
**Changes (flag `ENABLE_ROUTER_V2`, default off, fail-safe = current behaviour):**
- **Hardened prompt** `SUPERVISOR_SYSTEM_V2` ([prompts.py](../vinchatbot/app/agents/prompts.py)): explicit
  **route-by-INTENT** rule — "asks WHEN (date/period) → calendar; asks WHETHER a rule exists / HOW a process
  works → policy; asks an amount → financial" — + few-shot incl. both course-evaluation directions.
- **Deterministic-first gate** ([supervisor.py](../vinchatbot/app/agents/supervisor.py)):
  `classify_intent_confident` returns an intent only on a strong unambiguous keyword signal (top ≥2 hits AND
  clear lead) → routes WITHOUT the LLM; else the (hardened) LLM decides. `route_intent` branches on the flag.
- Note: routing *determinism* is now mostly covered by the 1.23b LLM cache (routing calls cached); the gate's
  remaining value is latency/cost on cold/uncached calls. The **real win here is the prompt fix** (correctness).
**Verify:** unit tests (`tests/test_supervisor.py`); full suite 322 green, ruff clean.

**A/B (router_v2 ON vs the 0.959 baseline, k=24, cache on) — REJECTED, major regression.**
`eval_20260622T050506Z`: **0.959 → 0.878 (+1 / −15)**, policy **0.912 → 0.588**, policy_conduct **1.0 →
0.714**; `courseeval-vi` did NOT even flip. Root cause (diagnosed offline on the 13 lost policy cases):
- **Deterministic gate mis-routes 4** — policy questions containing calendar keywords route confidently to
  **calendar** (`exchange-credits-en/vi`: "exchange *semester*"/"academic year" → 2–3 calendar hits;
  `mdattend-vi` → 3). The keyword gate is fundamentally unsafe: policy questions routinely carry calendar/
  financial keywords → confident WRONG routes → the doc-pin (gated to `student_affairs`) stops firing → the
  cases revert to the magnet failure.
- **V2 prompt mis-routes the other 9** (deferred to the LLM) — the "WHEN→calendar / route-by-intent"
  hardening **backfired**, biasing the LLM to pull policy questions out of `policy` (loa-fulltime, loa-return,
  lib-loan, res-curfew, genai, intern, progchange, sexmis, acadint).
**VERDICT: REJECT router-v2.** `ENABLE_ROUTER_V2` stays OFF (`.env` unchanged; run used an inline override);
code kept inert + flagged (do NOT enable). Baseline remains the 0.959 router-off run. **`courseeval-vi`
remains an open residual** — its routing fix needs a SURGICAL approach (e.g. add ONLY the course-evaluation
disambiguation example to the prompt, drop the broad "WHEN→calendar" rule + the keyword gate), or handle it
outside routing. Lesson: keyword-confidence routing + broad prompt rewrites both over-route; the supervisor
LLM (V1) was already better than this "hardening."

## Results of the two runs (both done)
- **Baseline refresh (router off, cache on, new scorer + 1.23a):** `eval_20260622T044124Z` = **0.959**,
  guards 1.000. vs the old 0.955 aggregate: **+loa-return-vi** (scorer numeral fix) / **−visa-travel-vi**
  (1 borderline case — possible 1.23a candidate-reorder nudge or residual noise). **`baseline.json` refreshed
  to this 0.959 run** (the current promoted config). Determinism/cache cost ledger ~flat.
- **Router-v2 A/B:** REJECTED (above) — 0.959 → 0.878. Flag stays off.

## Open
- **`courseeval-vi`** routing mis-route — still open; needs a SURGICAL retry (not router-v2).
- **`visa-travel-vi`** — RESOLVED: stably passes in the de-noised 0.964/182 baseline (`eval_20260622T081140Z`).
- Phase 1.23 (1.23a determinism + 1.23b cache) is the promoted state; 1.23c rejected. No git commit.

## 1.23d — Candidate-set determinism via over-fetch+truncate  (CODE DONE, gated OFF; SHELVED as a free win)
**Trial:** the 1.23a comment assumed Qdrant hybrid returns "the same SET in a non-deterministic ORDER."
A probe (2026-06-22, `_fetch_candidates ×3/×12`) **corrected this**: the candidate **SET itself jitters** at
the candidate_k boundary — `"tuition 2031"` returned **2 distinct top-40 sets over 12 fetches** (2 of 41 ids
drift in/out; HNSW approximate-search boundary). That set churn busts the rerank+answer cache → a (rare)
run-to-run noise source. Hypothesis: over-fetch `candidate_k + margin`, sort, truncate back to `candidate_k`
→ jitter lands in the discarded tail → stable reranked pool.
**Changes (gated):** `core/config.py` `retrieval_overfetch_margin` (default **0 = OFF = byte-identical**);
`rag/retriever._fetch_candidates` over-fetches then truncates when margin>0. 2 unit tests
(`tests/test_retrieval.py`: jitter absorbed at margin>0; byte-identical + jitters at margin=0). Full suite
**328 green**, ruff clean. `search_params=exact=True`/`hnsw_ef=512` had **no effect** (langchain's hybrid
path doesn't forward them to the dense leg).
**Experiment (cheap retrieval-equivalence probe, margin=24, all 182 golden queries — NO LLM):**
- margin=24 **does** make the top-40 stable (12-run sizing: fetch≥56 → 1 distinct set). ✓ determinism.
- BUT the top-40 set **CHANGES on 137/182 queries (75%)** vs margin-off — systematic symmetric `−N/+N` swaps
  (1–5 docs), **not** the rare 2-doc jitter. **Root cause: Qdrant hybrid RRF is k-dependent** — fetching 64
  vs 40 changes each leg's ranks + which docs fuse, so `fetch-64→truncate-40 ≠ fetch-40`. So it is **NOT
  behaviour-neutral**; it's a real retrieval-quality change needing a full A/B, not a free determinism tweak.
**VERDICT: SHELVED (not promoted).** (1) The determinism payoff is **marginal** — the de-noised baseline's
only noisy case (`calendar-fall-grade-release-en`) has *byte-stable retrieval* (generation noise, not
jitter), so retrieval jitter contributes ~0–1 rare eval flips. (2) Not worth a 75%-of-retrievals behaviour
change. **Code kept, gated OFF** (`.env` unchanged → ships nothing) for a *future* retrieval-quality A/B
(bigger-pool RRF may improve recall — revisit with A7). The true determinism fix (exact dense leg) needs
bypassing langchain's hybrid wrapper — deeper, also marginal. De-noising stays on `--runs N`. No git commit.