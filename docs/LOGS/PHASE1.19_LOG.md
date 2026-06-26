# Phase 1.19 — Structured Calendar & Fee Lookup (CODEX P0 #2)

> **Phase identity.** Not part of the original live-feedback plan (1.9–1.18). This is **UPDATE_PLAN.md CODEX-appendix P0
> #2 "Structured Calendar And Fee Lookup"**, the architectural sibling of the observability ledger
> shipped earlier this session (CODEX P0 #1, logged as the "Phase C" ledger in
> [OUTPUT_GUARDRAILS_AUDITOR_PLAN.md](OUTPUT_GUARDRAILS_AUDITOR_PLAN.md)). Numbered **1.19** to continue
> the project's `1.x` sub-phase scheme. **Staged:** Stage 1 = calendar (this log); Stage 2 = fees (next).
> Plan of record: `.claude/plans/can-we-try-to-merry-mango.md`.

## Context / problem
The weakest categories are exact-value point-lookups: `calendar_pointlookup` and program-specific fees.
Cause = **grounded-but-wrong**: vector retrieval surfaces an *adjacent* near-identical row (the
Final-Exam-Period date next to the Evaluation-Period date; the wrong program's tuition). The lenient
faithfulness check can't catch it (the wrong number *is* somewhere in the evidence). Fix per CODEX:
"separate knowledge access from agent reasoning" — route exact date/amount questions to a
**deterministic record lookup BEFORE vector search**, returning the one exact row or a clean MISS.
**No re-embedding / no re-ingest** (reads the structured records already produced at ingest).

## What shipped (Stage 1 — calendar)
- **Config** ([config.py](../../vinchatbot/app/core/config.py)): `ENABLE_STRUCTURED_LOOKUP` (default off) +
  `STRUCTURED_LOOKUP_RECORDS_PATH` (empty → `<PROCESSED_DATA_DIR>/structured_records.json`).
- **New module** [structured_lookup.py](../../vinchatbot/app/rag/structured_lookup.py): in-memory index over
  `calendar_event` records. Key design points discovered during build:
  - **Read-side date repair** — re-derives `(start,end)` from the full `event_name` (e.g. `21-Jun-02-Jul`
    → 21 Jun + **2 Jul**) because the stored `date_*_iso` are truncated/swapped.
  - **Single-winner rule** — academic-year → event-type → term (with term-window inference for term-less
    rows) → month → bilingual name-concept; returns a row ONLY when exactly one survives, else MISS.
    This is the "never the adjacent row" guarantee.
  - Bilingual (EN+VI) query parsing; valid `DocumentMetadata` (6 required fields) so citations render.
- **Seam** ([tools.py](../../vinchatbot/app/agents/tools.py) `_search`, ~line 48): gated, fail-open,
  calendar-only; records a 0-model-call `structured_lookup` ledger stage on a hit; MISS/err → vector path.
- **Tests** ([test_structured_lookup.py](../../tests/test_structured_lookup.py)): 14 — residuals,
  collisions, end-date recovery, miss/fallback, flag-off parity, metadata validity.
- **Golden cases** ([calendar_structured.json](../../data/eval/golden/calendar_structured.json)): cross-AY
  convocation (EN/VI), honest no-data Fall 2030 (EN/VI). (Per the "golden cases with features" rule.)

## Environment / collection finding
The live `.env` was **stale** — pointing at the OLD `vinuni_documents` (3-small, 1536-d) with
`OPENROUTER_EMBEDDING_MODEL=text-embedding-3-small` and `ENABLE_CROSSLINGUAL_EXPANSION=true`. Fixed `.env`
to the promoted e5 config + kept secrets + `ENABLE_STRUCTURED_LOOKUP=true`; added the two params to
`.env.example`. **Qdrant cloud inventory** (GCP australia-southeast1) confirmed the e5 collection:
`vinuni_full_e5` = **10,967 points, 1024-d** (others: `vinuni_documents` 7957/1536, `vinuni_documents_v2`
612, `vinuni_stage1_3small` 716, `vinuni_stage1_e5` 716).

## Offline gates
`ruff` clean (vinchatbot + tests); `pytest -m "not live"` = **274 passed** (260 + 14 new).

## Live A/B — controlled (fresh OFF vs fresh ON, same code + `vinuni_full_e5`, 134 cases)
Reports: OFF `eval_20260620T190951Z.json`, ON `eval_20260620T192548Z.json`.

**Overall 0.918 → 0.948 (+3.0 pts), ZERO regressions (no pass→fail).**

| Category | OFF → ON |
|---|---|
| **calendar_pointlookup** | **0.900 → 1.000** ✅ |
| calendar (general) | 0.929 → 0.929 |
| calendar_structured (new) | 0.75 → 0.75 (3/4) |
| financial / conduct / policy_conduct | 0.938 / 0.833 / 0.714 (unchanged) |
| adversarial / safety / services / multiturn | 1.0 (unchanged) |
| unanswerable | 0.8 → 1.0 (noise — see below) |

**Gained (residuals fixed):** `calendar-fall-evaluation-vi`, `calendar-spring-grade-release-en`,
`calendar-summer-grade-release-en` — each flipped its stage trace from `[…query_expansion/rerank…]` to
`[supervisor,structured_lookup,answer]` (causal proof, not luck).

**Cost/latency win (30 calendar point-lookups; 23 structured hits, 7 vector fallback):**
- mean model calls 4.23 → **3.40** (−20%); mean latency 9,897ms → **5,235ms** (−47%);
  total cost $0.106 → **$0.049** (−53%). Tail: `calendar-fall-evaluation-vi` 57,205ms/7 calls →
  3,597ms/3 calls. Whole-suite: cost −26%, p95 latency 18.9s → 15.7s, `confidently_wrong` 7 → 5.

**No harm:** every non-calendar category identical OFF→ON. The lone non-calendar flip
(`unans-future-tuition-en`, gained) is **eval noise** — the seam only fires on `subcat=="calendar"`, so
it cannot affect tuition cases. (This is why a fresh OFF control was run instead of trusting the older
`baseline.json`=0.946; the fresh OFF=0.918 differs only by the 4 new cases + noise.)

## ⚠️ Open finding — VI no-data hallucination (next to fix)
`calendar-nodata-fall2030-vi` **FAILED** (the only calendar_structured failure) — NOT caused by the
lookup. For un-ingested Fall 2030 the lookup correctly **MISSED** → fell through to vector → and then:
- EN twin: correctly **refused** ("could not find sufficiently clear official information"). ✅
- VI twin: **hallucinated** "Học kỳ Fall 2030 bắt đầu giảng dạy vào ngày 21 tháng 9 năm 2030" ❌
  (note 21-Sep is the AY2026-27 Fall instruction-begins date — the LLM grafted the asked year onto a
  retrieved different-year row).

This is a **pre-existing VI faithfulness gap in the vector-fallback path**, surfaced by the new
honest-no-data golden case. Net `confidently_wrong` still improved (7→5).

### Diagnosis (live traces) + fix
- **Root cause** (real data): the VI hallucination is **intermittent**, not a deterministic EN/VI split
  (a fresh diag had BOTH refuse). Chain: retrieval returns the nearest *wrong-year* row
  (`21-Sep Fall'26`) since no 2030 exists → the answer-LLM *sometimes* grafts the asked year onto it
  ("21 tháng 9 năm **2030**"), slightly more often in VI → the gate hole lets it through:
  `assess_faithfulness` passed on **any** number overlap ("21" is in evidence), so the fabricated **year
  2030** (not in evidence) was served.
- **Fix A (gate, the real fix)** — [guardrails.py](../../vinchatbot/app/agents/guardrails.py)
  `assess_faithfulness`: a 4-digit year asserted in the answer must be in the evidence **or within ±1**
  of an evidence year (so an AY label "2026-2027" is fine when a chunk only names 2026); a year far from
  all evidence years (2030 vs {2026,2027}) → ungrounded → degrade. Only applies when evidence itself
  names a year (no false-positive on yearless fee chunks). Unit-tested
  ([test_faithfulness_year.py](../../tests/test_faithfulness_year.py)).
- **Fix B (deterministic complement)** — [structured_lookup.py](../../vinchatbot/app/rag/structured_lookup.py):
  a calendar query naming a year outside the indexed span (e.g. 2030 > max AY 2027) returns honest
  no-data (empty results) and skips vector, so the LLM never sees a wrong-year chunk.
- Offline: **283 passed**, ruff clean (existing grounding tests unaffected).

### A/B with fixes (ON+FIX `eval_20260621T000222Z` vs prior ON `…192548Z`) — and a key finding
Single-run looked like +1 / −4 (overall 0.948 → 0.925), BUT trace analysis shows **none of the 4 losses
are caused by Fix A**: 3 are refusals with **no year asserted** (Fix A inert) that flipped due to
retrieval/LLM **noise**; the 4th (`calendar-summer-evaluation-vi`) answered the wrong adjacent row with
stages `[supervisor,rerank,answer]` — **the structured lookup didn't fire**.
- **NEW robustness finding:** the structured lookup runs on the **agent's reformulated tool-query**,
  which varies run-to-run, so it fires **intermittently** — `calendar_pointlookup` was 1.0 in run 1 but
  0.9 in run 2 (a residual re-exposed when the lookup missed). The hardening: run the calendar lookup
  **deterministically on the user's question at the service layer** (like the pure-time fast path), so it
  no longer depends on agent phrasing. Tracked as the next robustness task.
- Single-run eval has a **±3–4 noise band** (project-documented); a clean promotion number needs a
  multi-run average.

## Recommendation
Promote Stage 1 (calendar_pointlookup 1.000, zero regressions, cheaper+faster). `.env` already has the
flag on. Then: **(1)** fix the VI no-data hallucination, **(2)** Stage 2 fees, **(3)** optional compact
`calendar_index.json` so enabling the flag doesn't load the 154 MB `structured_records.json` on first
calendar turn.

## Determinism hardening (the intermittency fix)
The structured lookup now matches on the **raw user question** (threaded to `_search` via a
`user_message` contextvar set in `chat()`), not the agent's run-to-run-variable tool-query
reformulation — so it fires reliably regardless of how the agent phrases its tool call. Parent-sets-once
/ child-reads is contextvar-safe across the LangGraph task boundary. ([observability.py] `set/get_user_message`,
[vinuni_agent.py] `chat()`, [tools.py] `_search`.)

## "Would a bigger model fix it?" — empirical answer (NO)
Ran the 5 hard cases ×5 each, `gpt-4o-mini` vs `gpt-5.4-mini`, structured lookup OFF (so the MODEL faces
the failure condition). Result: **both models bad=0/5 everywhere** — the residual exact-date cases came
back "partial" (fail) on BOTH (gpt-5.4-mini was even *worse* on `summer-grade-release`), and the no-data
hallucination didn't reproduce on either (it's rare). Pricing: gpt-5.4-mini **$0.75/$4.50 per 1M vs
gpt-4o-mini $0.15/$0.60 (5×/7.5×)**. Conclusion: the grounded-but-wrong / imprecise-row class is a
**retrieval-precision problem, not a model-reasoning ceiling** — a bigger model neither fixes it nor
removes the rare graft, and costs far more. The structural fix (structured lookup + year-grounding gate)
fixes it deterministically and cheaper. (Confirms CODEX "structured correctness before model upgrades".)

## Stage 2 — fee structured lookup (implemented)
- Indexes the financial **tuition `table_record`** (subcategory=financial, header "Tuition Fee per …") into
  a `program × granularity` matrix: {nursing, medicine, other_bachelor} × {per_year, per_semester,
  per_credit} ([structured_lookup.py] `_maybe_index_fee_table`, `_match_fee`).
- Query classifier (bilingual): program {nursing/điều dưỡng, medicine/y khoa, other/standard/tiêu chuẩn},
  granularity {per credit/tín chỉ, per semester/học kỳ, per year/năm học (default)}; **single-cell rule**
  (no program named → MISS) so there's **no cross-program/granularity leakage** (copes with the loss
  risk). Currency questions → "VND". Library/admin fees fall through to vector (unchanged).
- Seam broadened to `subcat in ("calendar","financial")`; fee result carries valid `DocumentMetadata`
  (fee_type=tuition) so citations render.
- Tests: 11 fee cases added to [test_structured_lookup.py] (full matrix, no-leakage, currency, miss,
  default-granularity, metadata). Golden: [fee_structured.json] (4 new cells incl. nursing-per-semester
  174,825,000 — a value unique to one cell → strong leakage test).
- Offline: ruff clean; structured-lookup suite 21 passed; full non-live suite green.

## ⚠️ Incident & fix — structured-lookup OOM (memory), silent feature-disable

**Symptom.** The first Stage 2 live A/B showed the "ON" arm ≈ OFF (no gains) and the per-stage ledger
showed **`structured_lookup` hits = 0** across every category — the lookup never fired despite the flag
being on. The ON-arm log had: `Structured-lookup index build failed; lookups disabled.` → `MemoryError`
at `_build` (the `json.loads(read_text())` of `structured_records.json`).

**Root cause (local memory, local file — NOT cloud/Qdrant).** `StructuredLookup._build` loaded the full
**~154 MB** `data/processed/structured_records.json` (~48k records) via `read_text()` + `json.loads` →
**~1.5–2 GB** transient RAM. Inside the eval/agent process (LangGraph + fastembed sparse model + Qdrant
client + LangChain already resident) only ~1.2 GB was free → OOM. `_build` is fail-open (try/except), so
it **caught the MemoryError, logged "lookups disabled," and left the index empty** → the feature silently
no-op'd. Memory-pressure-dependent: the same load *succeeds* in an isolated process with free RAM (which
is why standalone smoke tests passed but the loaded-up process failed).

**Why this matters in production.** Cloud host machines are frequently memory-capped (small containers).
A 154 MB→2 GB parse at first-calendar-turn would silently disable the lookup on any constrained host —
and fail *open* (no crash, no alert), so it would look like the feature simply "doesn't help."

**Fix (three independent layers).**
1. **Streaming JSON reader** `stream_json_array` ([structured_lookup.py]) — reads the file in 1 MB chunks
   and `raw_decode`s **one record at a time**; peak memory ≈ one record + buffer (KB), not ~2 GB. Used by
   both `_build` and the build script. No new dependency (ijson is not installed). **Never OOMs even on
   the full file.**
2. **Compact derived index** — `scripts/build_structured_index.py` filters the 48k records → the **119**
   the lookup needs (97 calendar_event + 22 financial table_record) → `data/processed/structured_index.json`
   (**~308 KB**). `StructuredLookup.from_settings` prefers it over the 154 MB file → negligible memory +
   faster startup.
3. **Per-record resilience** — each record parsed in its own try/except so one malformed record can't
   crash `_build` and wipe the whole index.

**Operational runbook.**
- **After every ingest / re-crawl** (which rewrites `structured_records.json`), regenerate the compact
  index: `py scripts/build_structured_index.py`. Consider wiring this into the ingest pipeline so it's
  never stale. (If the compact index is absent, the streaming reader makes the full-file fallback safe
  too — just slower to scan.)
- **Detection.** The Phase-C ledger's `structured_lookup` stage-hit count is the canary: **0 hits on
  calendar/financial point-lookups = the index didn't build** (check logs for "lookups disabled"). This
  is the only reason the silent failure was caught — keep the ledger in the eval report.

**Files:** `vinchatbot/app/rag/structured_lookup.py` (streaming reader, from_settings compact-preference,
per-record try/except), `scripts/build_structured_index.py` (new), `data/processed/structured_index.json`
(new artifact).

## Golden-set update (this session) + state
- **Scorer loosened (general):** `_fact_matches` now supports **OR-synonyms** (`"a|b"` matches if any
  alternative is present) — fixes brittle single-word facts and bridges VI/EN terms. Tested.
- **`pol-loa-first-step`** required `["form"]` → `["form|application"]` (model says "application" — same
  step). Now passes.
- **Policy golden expanded 7 → 11** (better EN/VI balance, stabler n): VI twins for academic-integrity,
  sexual-misconduct, loa-purpose (OR-synonym facts) + an EN withdrawal case. `pol-loa-purpose-vi`
  `expected_source` → list `["procedure-for-requesting-a-leave-of-absence", "vuni.54"]` (it cites the
  VUNI.54 PDF form of the procedure).
- **Golden state verdict:** sound. The remaining policy failures are NOT dataset errors — they are
  legitimate cases documenting the VI retrieval gap below. (One authoring bug found+fixed: loa-purpose-vi
  EN-only slug.)

## VI policy-retrieval gap — diagnosis (live traces, pre-plan)
Final eval (corrected **0.951 / 142**, valid: 69 structured hits) left `policy_conduct` at **0.727
(8/11)**; the 3 remaining fails are ONE defect: **VI policy queries undermatch the EN canonical policy
doc.** Live retrieval traces (`scripts/_diag_vi_policy.py`, since removed):

| topic | VI canonical rank (final) | VI candidate-pool(40) | EN canonical rank |
|---|---|---|---|
| academic-integrity | **None** | **None (not in pool)** | 1 |
| sexual-misconduct | 1 (rerank promotes) | 28 | 1 |
| loa (procedure) | None | None (but VUNI.54 PDF @22) | 1 |

**Reading:** EN retrieves the canonical doc #1 every time; VI does not. academic-integrity is the hard
case — the canonical doc is **not retrieved at all** for VI. sexual-misconduct raw retrieval is actually
fine (#1) → its eval failure is an **agent-path** divergence (the ReAct tool-query differs from the user
question), not retrieval. loa's procedure exists in-pool as the VUNI.54 PDF.

**Lever assessment (answers the open questions):**
- **Cross-lingual escalation (translate VI→EN, RRF-fuse)** — the ONLY lever that fixes the *not-in-pool*
  case (academic-integrity); EN retrieval proves the doc surfaces #1 when queried in English. Highest value.
- **Alternative/multilingual reranker** — helps only *in-pool-but-low* (sexual-misconduct@28, loa@22);
  **cannot** help academic-integrity (nothing in the pool to reorder).
- **Better RRF** — only valuable *combined* with the cross-lingual variant (it needs the EN ranked list
  to fuse).
- **Metadata boost** (prefer `all-policies/<slug>/` canonical pages over governance regs) — reinforcement
  for in-pool-but-low; cannot help not-in-pool.
- **Agent-path / raw-question retrieval** — the structured-lookup determinism trick (use the raw user
  question, not the agent's reformulation) likely also helps sexual-misconduct/loa.
→ Detailed fix plan: see the plan file. Pausing implementation here per request.

## Status
- [x] Stage 1 calendar — implemented, offline-green, live A/B passed (calendar_pointlookup 0.9→1.0).
- [x] VI no-data hallucination — fixed (conservative year-grounding gate + structured no-data + determinism).
- [x] Bigger-model theory — tested empirically; structural fix wins.
- [x] Stage 2 fee lookup — implemented + offline-green.
- [x] OOM fix — streaming reader + 308 KB compact index + per-record resilience (see Incident above).
- [x] **Valid Stage 2 A/B** (OFF=eval_20260621T015401Z, ON=eval_20260621T020555Z): structured hits
      **0 → 69** (26 cal_pointlookup, 21 cal, 14 financial, 4+4 structured). Overall **0.949 → 0.957**;
      **financial 0.938 → 1.0**, **calendar_pointlookup 0.933 → 0.967**; GAINED summer-evaluation-vi +
      fin-medicine-tuition-year-vi; LOST pol-loa-first-step (brittle-scorer NOISE, not the lookup —
      policy subcat untouched). **cost −54% ($0.455→$0.211), latency −33% (7.6s→5.0s)**, confidently_wrong 5→4.
- [x] Promotion: `ENABLE_STRUCTURED_LOOKUP=true` shipped in `.env`; fee path is part of the promoted
      0.953 baseline (policy-golden expansion happened in 1.20). Commit still HELD per user.

## A2 re-confirmation (2026-06-22, roadmap step A2) — fee lookup LIVE & firing; no new A/B needed
Offline attribution over the promoted `baseline.json` (0.953): the fee structured lookup fires on **every
tuition point-lookup** — `fee_structured` 4/4 and all `fin-*tuition*`/`fin-currency-*` cases show
`structured_lookup=True` and pass `f1 c1`. So A2 ("confirm + close fee lookup") is **DONE** — it's the same
Stage-2 win above, still firing in the current baseline.
- **Only non-firing financial cases:** the `fin-library-overdue-fine` pair (a *library overdue fine* — a
  NON-tuition fee, outside the program×granularity matrix). EN twin passes via the vector path; **VI twin
  fails `f0 c1`** — and it was `f0` BEFORE the pin too (cited VU_TS03 but never surfaced the daily amount);
  post-pin it cites `library-policies` (pin matched "thư viện") but the number still isn't extracted.
- **Conclusion:** this is an **extraction** residual (right-ish doc, value not surfaced), NOT a fee-coverage
  gap — extending the fee matrix wouldn't fix it. **Reassigned to A3 (output-audit critic).** No A2 A/B.
