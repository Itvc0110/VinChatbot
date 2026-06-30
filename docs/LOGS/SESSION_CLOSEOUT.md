# Session close-out — 2026-06-23 (paused until teammate merge)

Single resume-point for when repo work restarts (post-merge). **Repo state:** 354 offline tests green, ruff
clean, **baseline `data/eval/baseline.json` = 0.968/188** (N=1, list-mode on; guards adversarial/safety/
unanswerable all 1.000). **No git commit** — working tree is uncommitted (per the standing "commit only when
asked" rule; nothing was committed this arc). Detailed per-phase logs in `LOGS/PHASE1.2x_LOG.md`.

## SHIPPED / PROMOTED (live in `.env`)
| Phase | What | Flag(s) | Log |
|---|---|---|---|
| 1.22 / A1 | eval de-noise (`--runs N`, stable-vs-noisy gating, scorer numeral fix) | (no flag) | PHASE1.22 |
| 1.23a | retrieval/rerank determinism (rounded-score+chunk_id sort, tiebreak) | (no flag) | PHASE1.23 |
| 1.23b | exact-match Redis cache (LLM + rerank), fail-open | `ENABLE_LLM_CACHE`, `ENABLE_RERANK_CACHE`, `CACHE_VERSION`, `REDIS_URL` | PHASE1.23 |
| 1.24 / A3 | ingest policy auto-index (title fallback after curated map) + long-tail golden | `ENABLE_POLICY_AUTO_INDEX` | PHASE1.24 |
| 1.25 / A4 Phase A | deterministic output hardening: `resolve_output_decision` + de-obfuscated/zero-width secret guard + bypass coverage | (no flag) | PHASE1.25 |
| 1.27a / A6 | list mode: `is_list_lookup` → widen+enumerate; structured `_match_fee` full tuition matrix | `ENABLE_LIST_MODE`, `RETRIEVAL_LIST_MAX_K` | PHASE1.27 |
| 1.27b / A6 | calendar list aggregation: `_match_calendar(list_mode)` → all matching events | (rides `ENABLE_LIST_MODE`) | PHASE1.27 |
(Also live from earlier: `ENABLE_STRUCTURED_LOOKUP`, `ENABLE_POLICY_DOC_PIN`, `ENABLE_CROSSLINGUAL_POLICY`.)

## REJECTED / SHELVED (code kept inert, gated OFF)
- **1.23c router-v2** (`ENABLE_ROUTER_V2=false`) — over-routes.
- **1.23d over-fetch+truncate** (`RETRIEVAL_OVERFETCH_MARGIN=0`) — RRF is k-dependent → 75% retrievals change; not behavior-neutral. Revisit with A7.
- **1.25 Phase B output-audit critic** (`ENABLE_OUTPUT_AUDIT=false`) — over-degraded 9 correct date answers, +26%/+44% latency, 0 benefit. **Kept for a FUTURE security use** (secret/safety-leak detection); model configurable via `OUTPUT_AUDIT_MODEL`.

## DEFERRED (resume points saved)
- **1.26 / A5 — refusal & don't-over-refuse** → plan **`LOGS/PHASE1.26_PLAN.md`** (Part 1 was built then reverted clean). **Part 1** `restricted_data` HYBRID (regex hard-block + escalate ambiguous to the LLM guard) **fixes `record-privacy-vi`** — ⚠️ probe qwen-7b reliability FIRST. **Part 2** soft-scope A/B (`ENABLE_SOFT_SCOPE`). **Part 3** clarification → **team merge**.
- ~~**1.27c cross-domain fan-out** (deferred)~~ → **BUILT + PROMOTED in Phase 1.33**: decompose / hedge → parallel specialists → synthesis + L2 retry, `ENABLE_FAN_OUT` **default ON**. Neutral on the single-domain scored set (no regression after the same-intent over-fire fix) + adds the multi-domain coverage the single router can't; reversible via the flag. Plan `.claude/plans/can-we-try-to-merry-mango.md`; outcome `LOGS/PHASE1.33_LOG.md`.
- **1.28 / A7 contextual retrieval + retrieval-planner** — heaviest; one-time re-ingest.
- **Q1 multi-question decomposition** — NOT recommended (ReAct BASE_PRINCIPLES step-2 completeness nudge covers it). **Q2 clarification** + **output PII scan** — → team merge / post-personalization. See memories `defer-input-understanding-decomposition-clarification`, `defer-output-pii-scan-until-personalization`.
- **Track B (perf):** 1.29 async, B2 LangCache semantic answer-cache.

## OPEN RESIDUALS
- `record-privacy-vi` over-refusal → **1.26/A5 Part 1** (the concrete next high-value fix when work resumes).
- `courseeval-vi` routing mis-route → needs a *surgical* retry (router-v2 rejected).
- `loa-return-vi` value-not-surfaced → structured-lookup expansion.
- `calendar-fall-grade-release-en` — the one persistently NOISY case (byte-stable retrieval, generation-layer flip); excluded from gating; not cheaply fixable.

## RESUME CHECKLIST (post-merge)
1. **Recommended first job:** 1.26/A5 Part 1 (`restricted_data` hybrid → `record-privacy-vi`) from `PHASE1.26_PLAN.md` — probe qwen-7b allow-reliability before the eval.
2. **Baseline:** currently n=188 (N=1). The golden dir now has **192** cases (4 `calendar_list` not yet in baseline.json — they pass deterministically). Refresh with `--runs 3` for a de-noised n=192 reference when convenient.
3. **Wire the team-merge items:** Q2 clarification (1.26 Part 3), output PII scan, A3 staff-keyword upload hook.
4. **SECURITY:** rotate the `REDIS_URL` credential (it was pasted in chat) and set `allkeys-lru` on the Redis instance. Secrets remain only in `.env` (gitignored).

## Conventions held this arc
Every behavior `ENABLE_*`-gated + default-off + fail-open; guards stayed 1.000; one eval at a time; promote only winners; every update logged (incl. rejections); **no git commit**.
