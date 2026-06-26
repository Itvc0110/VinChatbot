# VinChatbot — Phase 1 Worklog (submission)

VinChatbot is a 24/7 RAG + multi-agent assistant answering VinUni students' academic-services
questions from official documents, with citations and refuse-when-unsure guardrails. Stack: **FastAPI
+ LangChain/LangGraph + Qdrant Cloud (hybrid dense+BM25) + OpenRouter** (`gpt-4o-mini` answer model,
`text-embedding-3-small`, `cohere/rerank-v3.5`). Team 050, AI20K Build Cohort 2.

> **How to read the scores.** The golden eval set grew over time and got *deliberately harder*. Phases
> 1.0–1.6 are measured on the 53→86-case set; **Phase 1.7 expanded it to 130 cases** (adding hard
> point-lookup, cross-lingual, and multilingual-guard cases), so the 1.7+ numbers are **not directly
> comparable** to the earlier ones — the apparent drop (0.919 → 0.846 baseline) is the harder set, not
> a regression. Every change was `ENABLE_*`-flag-gated and A/B-measured on the golden set.

## Metrics journey

| Sub-phase | Focus | Eval (cases) | Note |
|---|---|---|---|
| 1.0 Foundation | crawl→ingest→multi-agent→eval+CI | **0.472** (53) | baseline; language-mismatch dominated |
| 1.1 Quality & safety | language honoring, RAG depth, guards, data-clean | **0.931** (58) | biggest jump |
| 1.2 Metadata, layered guards, eval, viz | boosts, soft-routing, safety API; set→80 | **0.925** (80) | harder set (+safety/multiturn/unanswerable) |
| 1.3 Markdown ingestion v2 | header/token chunking | **reverted** (73.8%) | broke calendar extraction; shelved, DOCX kept |
| 1.4 Chunking/retrieval/fixes | faithfulness fix, conversational handling | **0.919** (86) | +6 conduct cases; parent-doc gated off |
| 1.5 Observability | JSON logs + correlation IDs + cost + Langfuse | **0.930** (86) | logging-only, no regression |
| 1.6 Rerank cost | rerank-once after RRF fusion (~67% fewer rerank calls) | **0.919** (86) | shipped on; accepted ~1-case cost tradeoff |
| 1.7 Eval expansion + adaptive retrieval | set 86→130; point-lookup routing + full-section | **0.846** baseline (130) | new harder reference set |
| 1.8 Cross-lingual expansion | VI↔EN query variant, all domains | **0.885** (130) | **current production — best of the arc** |

Per-category (production, 130 cases): guards (adversarial/safety/unanswerable) **1.000**, calendar
0.929, financial 0.875, conduct 1.000, multiturn 1.000, services 1.000, policy_conduct 0.571*
(*largely eval-scorer artifacts — see caveats). Citation validity ≈ 0.98–1.00.

## Per sub-phase

- **1.0 — Foundation.** 761-doc Qdrant Cloud corpus; LangGraph supervisor→4 ReAct specialists
  (calendar/policy/financial/services); two-tier CI (offline + nightly live eval); golden-set scorer.
  Baseline 0.472 (language mismatch + strict matching diagnosed).
- **1.1 — Quality & safety.** Honor question language; lost-in-the-middle reorder; dynamic-k; near-dup
  dedup; multi-query + RRF; regex+small-LLM guard + de-obfuscation + indirect-injection scan;
  calendar/fee clean structured chunks. 0.472 → 0.931.
- **1.2 — Metadata, layered guards, eval, viz.** event_type/fee_type, policy_code propagation,
  source_trust/term boosts, soft routing, image-chunk exclusion (index −33%); layered API guard
  (OpenAI omni-moderation → small-LLM injection/scope); eval → 80 cases; ARCHITECTURE.md. 0.925.
- **1.3 — Markdown ingestion v2 (REVERTED).** pymupdf4llm markdown + header/token chunker netted
  ≤81% < 92.5% (PDF markdown broke calendar_event extraction; over-fragmentation). Markdown gated
  off; **kept** DOCX parsing/routing.
- **1.4 — Chunking/retrieval/coverage + fixes.** Shipped the **faithfulness false-positive fix**
  (citation/policy-code digits no longer force refusals; recovered the policy LOA cluster) and the
  **conversational-handling fix** (full-VN `answer_language` + rule-tier smalltalk/capability). Tested
  but rejected/gated: parent-doc retrieval, gpt-4o (wash at ~20× cost), prompt tightening. 0.919.
- **1.5 — Observability.** Structured JSON logging + `X-Request-ID` correlation + PII redaction;
  per-turn token/cost capture; **Langfuse** tracing (opt-in extra), all fail-open. No regression
  (0.930).
- **1.6 — Rerank cost reduction.** Rerank the RRF-fused pool **once** instead of once per query
  variant (~67% fewer Cohere calls). A/B was −1 case; **shipped on** (user decision) for the cost win;
  surfaced a calendar point-lookup precision risk (fixed in 1.7).
- **1.7 — Eval expansion + adaptive retrieval.** Grew the eval set **86 → 130** (new
  `calendar_pointlookup` category with adjacent-date distractors, cross-lingual fee, multilingual
  guards) + a `run_eval.py --diff` regression tool. Shipped **adaptive point-lookup routing**: a cheap
  `is_point_lookup` router sends date/fee/code queries to **full-section reading + a strict
  exact-value prompt**; calendar point-lookups drop paraphrase expansion (precision). Fixed the 1.6
  calendar wrong-date.
- **1.8 — Cross-lingual expansion.** A bidirectional **VI↔EN** query-translation variant on every
  domain, so a question in one language matches sources in the other (VI question vs the English fee
  tariff/calendar). Full 130-case eval **0.885** — best of the arc; recovered the persistent VI→EN fee
  misses; guards stayed 1.000.

## Key engineering decisions (with rationale)
- **Qdrant Cloud** as the canonical vector store (Pinecone/Chroma opt-in).
- **NeMo Guardrails dropped** — it pins `langchain<0.4`, which would break our LangChain 1.x stack;
  used OpenAI omni-moderation + a small `qwen-2.5-7b` injection/scope classifier behind a free regex tier.
- **Markdown chunking shelved** (1.3) — lost to the plain-text pipeline; kept gated for a future revisit.
- **Stayed on `gpt-4o-mini`** — `gpt-4o` was a wash at ~15–30× cost; our losses are not model-bound.
- **Cost work** — rerank-once-after-fusion (1.6) cut rerank calls ~67%; per-turn token/cost logging
  (1.5) showed the answer model is the cost driver.
- **Adaptive retrieval (1.7) + cross-lingual (1.8)** — point-lookups (dates/fees) need precision +
  full-section reading + cross-lingual recall, distinct from prose; routed accordingly.
- **Everything `ENABLE_*`-gated and A/B'd** on the golden set; one eval at a time; never trust a run
  with network errors (lesson learned from a mid-eval OpenRouter outage).

## Production state at submission (2026-06-17)
- Qdrant collection `vinuni_documents` (~7,957 points, plain-text pipeline), untouched in 1.5–1.8.
- Models: `openai/gpt-4o-mini` (answer), `openai/text-embedding-3-small`, `cohere/rerank-v3.5`,
  `qwen/qwen-2.5-7b-instruct` (guard).
- Flags on: `ENABLE_RERANK_AFTER_FUSION`, `ENABLE_ADAPTIVE_RETRIEVAL`, `ENABLE_CROSSLINGUAL_EXPANSION`,
  `ENABLE_COST_TRACKING`; Langfuse opt-in.
- Eval: **0.885 / 130 cases**; guards 1.000; reference `data/eval/baseline.json`.

## Post-submission updates

### 1.13–1.27 — quality arc (→ 0.968 / 188)
After submission the eval set + corpus were rebuilt and the baseline climbed to **0.968 / 188** on Qdrant
`vinuni_full_e5` (multilingual-e5-large, 1024-d, ~10,967 pts) — the production baseline through mid-2026-06-24
(later superseded by `vinuni_full_e5_v2`; see the 2026-06-24 entry below). Highlights
(full detail in [UPDATE_PLAN.md](UPDATE_PLAN.md) / [LOGS/SESSION_CLOSEOUT.md](LOGS/SESSION_CLOSEOUT.md),
per-sub-phase `LOGS/PHASE1.*_LOG.md`): **e5 embeddings** (1.13/1.14); deterministic **structured
calendar/fee lookup** (1.19); **policy doc-pin** + ingest auto-index (1.21/1.24); cross-lingual policy
escalation (1.20); determinism + **Redis LLM/rerank cache** (1.23); output-guard hardening (1.25A); **list
mode** (1.27). Guards stayed 1.000; every lever `ENABLE_*`-gated + A/B'd.

### 2026-06-24 — Source-tiered corpus expansion → PROMOTED to `vinuni_full_e5_v2` (+ filter overhaul + D9)
Goal: add **official student content beyond policy/calendar/fee** — admissions, the 4 colleges
(cecs/chs/cbm/cas), scholarships — while keeping the index authoritative.
- **Crawl**: new subdomains added to the crawler allowlist + seeds; external caps tuned down;
  **noise-path denylist** (`/category//tag//event//page/`). Finding: the public *student* surface is
  ~600 pages (college sites are marketing-heavy → crawling more yields news, not curriculum).
- **Cleaning**: new `infer_source_kind` kinds (admissions/faq/program/scholarship) with **first-segment
  prefix-gating** — WordPress news slugs are keyword-rich, so substring matching leaked news; prefix
  matching drops it. `--student-only` ingest filter (drops images/marketing). ~9.5k raw → **~1,200 clean docs**.
- **Robustness fix**: a merged-cell `.docx` crashed the entire crawl → the crawl loop now survives any
  single-doc parse error and docx-table parsing is tolerant.
- **C1 authoritative-source structured filter** (hybrid): calendar records kept only from real calendar
  documents (current **and** older academic years), fee records only from the official tariff host — so an
  admissions/college page merely *mentioning* a date/amount can't poison the deterministic lookup.
- **Built scratch `vinuni_full_e5_v2`** (1,208 docs / 10,933 chunks); production `vinuni_full_e5` untouched.
  First benchmark 0.953 was *confounded* (structured index rebuilt mid-run). The **clean re-benchmark
  confirmed no regression**: `calendar_structured` recovered to **1.0** (C1 fix), guards **1.000**, and the
  only existing-188 flips were **2 single-run noise cases** (`pol-loa-return-en`, `svc-library-services` —
  different from run #1's calendar flips → noise, not dilution). The **new content answers** (admissions
  IELTS 6.5, Data Science 4yr/120cr, Provost=Rohit Verma all pass); the **2 president cases fail as designed**
  (F-ENUM enumeration + F-NAME name-order gap, logged for the entity-handling roadmap) + 3 minor golden
  fixes (2 citation-source too narrow, 1 scholarship retrieval). Overall 0.935/200 only because the 8 new
  cases (incl. 2 intentional diagnostics) are in the denominator; existing-188 ≈ 0.968. **Verdict: v2 is a
  promote candidate** (no regression, real new capability) — pending a `--runs 3` noise-confirm before
  flipping `.env` → `vinuni_full_e5_v2`. New golden `data/eval/golden/expansion.json`; plan
  `LOGS/NEW_SEED_INGESTION_PLAN.md`; future roadmap `LOGS/ADAPTIVE_ORCHESTRATION_ROADMAP.md`. 364 tests green.

**Filter overhaul + D9 + PROMOTE (1.28, full detail in [LOGS/PHASE1.28_LOG.md](LOGS/PHASE1.28_LOG.md) /
[LOGS/INGEST_FILTER_AUDIT.md](LOGS/INGEST_FILTER_AUDIT.md)).** A live President-bug report exposed that the
`--student-only` filter was a **regression**: it silently dropped the entire official `vinuni.edu.vn` domain's
reference content (`/people/` 989 leadership+faculty bios, registrar **forms**, student **guides**, college
program pages, `/global_exchange/`) because `infer_source_kind` default-drops the main domain to
`external_public_page` and kept PDFs only on `policy.vinuni`. **Fix** (path-aware main-domain sections +
college-slug widening + host-aware PDF rule + `_effective_source_kind` re-derive + an **ingest drop-report**
so future false-drops surface in the log). **Rebuilt `vinuni_full_e5_v2` incrementally → ~14,200 chunks**
(Tan Yap Peng 0→5, `/people/` 65→993). **D9 intent-satisfaction auditor** (`ENABLE_INTENT_AUDIT`): extends the
groundedness critic to also check the answer satisfies the **specific role asked** — hedges the grounded-but-
wrong-role enumeration (Council-President named as Rector) instead of confidently listing wrong people; A/B +2
identity cases, **no over-fire**. **Result**: name-order + over-refusal **fixed**; enumeration now safely
hedges (affirmative answer needs leadership content + a D8 role table — roadmap). Full `--runs 1` A/B: guards
**1.000**, no D9 over-fire, only flips were 2 stale-golden artifacts (broadened: library cites the official
policy page; LOA "chính thức/full-time"). **PROMOTED 2026-06-24** — `.env` → `vinuni_full_e5_v2` +
`ENABLE_INTENT_AUDIT=true` (gpt-4o-mini judge); old collection kept as rollback. New golden
`identity_intent.json` + `recovered_content.json`; `baseline.json` refreshed on the promoted config.
**374 tests green.** Citation-precision follow-up (score-sorted `_extract_citations`) was **A/B-REJECTED**:
it recovered `datascience-vi` (+1) but regressed **5 VI policy** cite_ok (policy 0.941→0.794) because rerank
scores aren't comparable across a multi-call ReAct turn's sub-queries → reverted (372 tests green). The
cross-lingual citation dilution stays a documented open item.

**Doc-pin (1.30) + golden hygiene & calendar fix (1.31)** — full detail in [LOGS/PHASE1.30_LOG.md](LOGS/PHASE1.30_LOG.md),
[LOGS/PHASE1.31_LOG.md](LOGS/PHASE1.31_LOG.md), [LOGS/PHASE1.29_PLAN.md](LOGS/PHASE1.29_PLAN.md).
Baseline progression this phase: **0.969/226 → 0.965/199 (prune) → 0.98/199**; guards **1.000** throughout. No git commit.
- **Doc-pin (S15+S16, 1.30b, PROMOTED).** Admissions-GPA / financial-aid-% / VI program-credit answers live in
  docs out-ranked (often unretrieved) by magnet prose; a `prefer_canonical` boost was **A/B-rejected 0/6** (the
  canonical doc isn't retrieved, so a score nudge can't lift it). Generalized the policy doc-pin:
  `canonical_lookup.py` deterministically fetches the curated canonical page by `source_url` and non-evicting-
  prepends it. Two stacked bugs fixed (wrong AID URL; the structured **fee lookup early-returned BEFORE the
  pin** on the financial route → `canon_applies` gate so only the aid pin pre-empts it), then narrowed to
  credit/admission/subsidy intents (dropped duration — spec dual-degree "5/5.5yr" distractor; narrowed
  `_AID_KW` to subsidy-only — broad "scholarship" over-fired onto named scholarships/finaid deadlines).
  **0/6 → 5/6 targets.** Residual `nursing-vi` is generation-side (right doc pinned, LLM picks 86 over 126).
- **Golden hygiene (1.31 G7a).** Pruned 27 always-pass VI-duplicate cases (EN twin kept; no guards/sole-
  feature/ever-failed) → ~12% cheaper evals; `baseline.json` refreshed by filter+re-summarize → 0.965/199.
- **Multi-domain (1.31 G7b).** Authored+verified (3 subagents) 23 cross_domain/multihop cases → 27-case
  substrate, **22/27**. **G1 multi-domain orchestrator DEFERRED with evidence** — 3-case ROI; the cheap
  "2+-intent→services" rule would regress 17 passing point-lookups (stray keywords); the clean LLM-multi-label
  version is a big graph build. Substrate kept so it's instantly measurable if multi-domain regresses.
- **Calendar parser fix (1.31 Build B, PROMOTED).** The calendar event-extraction **keyword gate** dropped
  Victory Day / Labor Day / Vietnam Culture Day / Independent Study Week (no matching keyword) → absent from
  the structured index → date lookups hedged. Added the holiday keywords (EN+VN) + 2 regression tests +
  surgical index regen (additions-only, +5 events, no Qdrant re-embed). **0.965 → 0.98/199, LOST 0, guards
  1.000, cw 3→2, calendar_pointlookup 0.889→1.0.**
- **Strategic finding (logged + saved to memory).** Retrieval/doc-selection is now strong (doc-pin shipped);
  the residual eval tail is **generation-side number-disambiguation** (`nursing-vi` 86-vs-126; `pol-thesis-days`
  3mo-vs-15/30d) + hard metacognition probes. System at a **mature plateau (0.98/199, guards 1.000)**; lesson:
  re-measure a roadmap fix's actual gap before building (the system outgrew D1–D9 — D1 had 0 whole-refusal
  targets; G1 was 3 cases).

## Phase 1.33 — Multi-domain FAN-OUT (built, flag-gated OFF; pre-promotion)
- **Feature.** Supervisor `plan_dispatch` emits a PLAN: SINGLE (~90%, byte-identical single path), DECOMPOSE
  (compound → per-domain subtasks run in parallel), or HEDGE (route-ambiguous → same question to 2 candidate
  specialists). `fanout_node` runs subtasks concurrently (error-isolated), synthesis merges (citations union
  over all subtasks' ToolMessages, no service change). **L2 reactive loop**: re-run a PUNTED subtask once with
  a critique, keep the good parts, cap=1, can't fabricate. All behind `ENABLE_FAN_OUT` (default off). 19 fan-out
  unit tests; suite 394 green. See `LOGS/PHASE1.33_LOG.md`.
- **Planner calibration (lesson).** Initial decompose 3/16 was IDENTICAL across gpt-4o-mini→sonnet — a stronger
  model fixed nothing. Manual raw-output inspection: the Tier-0 keyword fast-path returned `single` BEFORE the
  LLM ran. Fixed the gate → cheap gpt-4o-mini: 76% mode-match, 0 under-fire. *Measure the raw artifact before
  blaming the model.*
- **Hard-set A/B (86 adversarial cases, --runs 1, cache-off): ON 0.721 vs OFF 0.663.** 8 of OFF's 29 failures
  fixed (4 decompose + 3 hedge + 1 underspec — the structural gap the old flow gets categorically wrong);
  single path made byte-identical via single-assignment deferral to `route_intent`; latency +31% on fan-out
  turns (parallel). `est_cost` undercounts ON — fan-out subtasks run in `asyncio.gather` child tasks whose
  `record_stage` contextvars don't propagate back; **latency is the honest cost signal**.
- **Root-cause win (1.33e).** Scoped *why* the gain was modest instead of promoting. The dominant fan-out
  failure was a **contextvar leak**, NOT a retrieval cap: the turn pins `set_user_message(compound)`, and every
  subtask's tools key structured-lookup/list-mode/cross-lingual off `get_user_message()`, so a subtask ran its
  deterministic lookup against the whole compound → punt. Facts were retrieved at rank 0; specialists answered
  them correctly STANDALONE. Fix: set the contextvar to the subtask per `_run_subtask` (isolated per asyncio
  task). Verified end-to-end: `dc-3part` (regression) and `cross-late-payment` (both_fail) both recover.
- **Full-199 A/B + DECISION (PROMOTED, default ON).** OFF 0.970 vs ON 0.945 (pre-fix net-negative): the scored
  199 has ~no genuine compounds, so fan-out had nothing to gain there but **over-fired** on 4 same-specialist
  splits (services+services / policy+policy / calendar+calendar). Fixed with a deterministic **same-intent
  collapse** (all-one-intent plan → SINGLE; genuine cross-domain spans ≥2 intents → still fans out) → post-fix
  ON ≈ OFF (neutral), **confirmed on the 5 regressed cases (~10 turns): OFF 5/5, ON 5/5, all 4 over-fires now
  `fanout=False`**. **Decision: PROMOTED** (`ENABLE_FAN_OUT` default ON) — neutral on the current single-domain
  scored set, adds the multi-domain coverage the single router structurally can't, reversible via the flag.
  Also shipped: chat-client **request timeout/retries** (a hung LLM call with no timeout previously froze the
  turn / a fan-out gather — root-caused from repeated eval hangs) + fee-lookup **negation**. Live flow is now
  the dispatch planner; a single-domain question takes the single-specialist path byte-identically.

## Honest caveats / known limitations
- **`policy_conduct` 0.571 is largely a measurement artifact**, not a flow weakness: of 3 fails, 2 are
  eval-scorer issues (token-morphology "temporary"≠"temporarily"; an `expected_source` hardcoded to
  the EN doc while the VI question correctly cited the VI source) and 1 is a borderline generation
  pick. True accuracy ≈ 0.86. The category is tiny (n=7) and LOA-skewed.
- **Single-run eval noise ≈ ±3 cases** (~±2%): a 30-case category swung 0.80↔0.70 on identical logic.
  Multi-run averaging is the top open eval-rigor item.
- **Calendar "period"/grade-release** cases can still fetch the wrong document (registrar blogs outrank
  the Academic Calendar PDF) — candidate for a deterministic structured calendar lookup.
- The golden set is **partly circular/narrow** in places (facts authored from source docs); held-out
  student-phrased cases are tagged `held_out: true`.

