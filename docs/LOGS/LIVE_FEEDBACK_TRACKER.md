# Live-feedback remediation tracker (Phases 1.9 → 1.18)

VinChatbot was deployed to real student testers; **10 concrete failure cases** came back. This is the
single "come-back-to-it" doc: each issue is its own phase, executed **one by one**, with a status
checkbox flipped to `[x]` **only after the user verifies** the result. The **detailed per-phase plans**
are saved in [LIVE_FEEDBACK_PLAN.md](LIVE_FEEDBACK_PLAN.md); each phase also gets its own
`LOGS/PHASE1.x_LOG.md` as it runs.

**Production reference:** `0.885 / 130 cases`; Qdrant `vinuni_documents` (~7,957 pts); models
`gpt-4o-mini` (answer) · `text-embedding-3-small` (1536-d) · `cohere/rerank-v3.5` · `qwen-2.5-7b` (guard).

**House rules (every phase):** `ENABLE_*`/config-gated · fail-open · **one eval at a time** · never
trust a run with network errors · **guards (adversarial/safety/unanswerable) must stay 1.000** · scratch
Qdrant collection for any re-index · promote only winners · secrets stay in `.env` (user fills/rotates).

**Status legend:** `[ ]` todo · `[~]` in progress · `[x]` done (user-verified) · `[-]` deferred.

**Per-phase loop:** implement → offline gates (`pytest -m "not live"` + `ruff`) green → A/B (multi-run
once 1.11 lands) → **report to user** → user verifies → flip checkbox → next phase.

## Status board

| Phase | Issue | Title | Status | Verified | Log |
|---|---|---|---|---|---|
| 1.9  | #1  | Time / current-date awareness | `[x]` | ✅ 2026-06-19 | this file |
| 1.10 | #2  | Chat-time rate limiting | `[x]` | ✅ 2026-06-19 | this file |
| 1.11 | #5  | Consistency: reduce nondeterminism + reactive expansion | `[x]` | ✅ 2026-06-19 (0.923) | this file |
| 1.12 | #4  | Date-format normalization (code shipped) → **validated within 1.13** | `[x]`* | merged → 1.13 | this file |
| 1.13 | #3+#4 | Calendar correctness: parser hardening (AY/event-type/term) + full re-crawl + reshape — **promoted (0.946)** | `[x]`* | ☐ .env switch | PHASE1.13-1.14 |
| 1.14 | #6  | Embedding → **e5-large via OpenRouter** (12/12 probe) + reactive cross-lingual + layer fixes — **promoted (0.946, guards 1.000)** | `[x]`* | ☐ .env switch | PHASE1.13-1.14 |
| 1.15 | #7  | Mass caching + async/parallelization | `[ ]` | ☐ | — |
| 1.16 | #8  | Multi-domain reasoning (single wide retrieval, O(1) rerank) | `[ ]` | ☐ | — |
| 1.17 | #9  | Agent-decided expansion (no extra LLM call) | `[ ]` | ☐ | — |
| 1.18 | #10 | Clarification path + don't-over-refuse (guard scope-precision **S1 done**; soft-scope S2 + clarify pending) | `[~]` | ☐ | — |
| C    | CODEX P0#1 | Per-stage cost/latency ledger + confidently-wrong metric — **shipped** | `[x]`* | ☐ | OUTPUT_GUARDRAILS_AUDITOR_PLAN |
| 1.19 | CODEX P0#2 | Structured calendar lookup (Stage 1) — **A/B 0.918→0.948, calendar_pointlookup 0.9→1.0, −53% calendar cost, 0 regress**; Stage 2 fees + VI no-data fix pending | `[~]` | ☐ .env on + verify | PHASE1.19 |

---

## Phase 1.9 — Time / current-date awareness (Issue #1) — `[x]` done (verified 2026-06-19)

**Problem.** "What semester am I currently in?" / "how long until add-drop?" fail — the bot has no
notion of *now*.
**Root cause.** Zero current-date injection: `prompts.py` BASE_PRINCIPLES, specialist prompts,
`vinuni_agent.py:chat()` (only a language directive), `tools.py` — none see `datetime.now()`. The
Sep→Aug AY-boundary logic exists in `parsers.py:_date_token_to_iso` but is unused at serving time.
**Plan.** (A) inject "today + current AY + term" into the turn message + frame it in BASE_PRINCIPLES;
(B) add a `get_current_datetime` tool for date arithmetic. New `app/core/timeutils.py:current_academic_context`
reuses the AY boundary (no duplicated magic numbers). tz = Asia/Ho_Chi_Minh. Flag `enable_time_awareness`.
**Experiment / gate.** Unit test the AY/term boundaries (Aug 31 vs Sep 1; Jun 18 2026 → Summer,
AY 2025-2026); live smoke "what semester am I in?"; full eval **no regression** (additive). +2-3 golden
cases.
**Implemented (2026-06-18).**
- New `vinchatbot/app/core/timeutils.py`: `current_academic_context()` / `current_time_context()` (tz
  Asia/Ho_Chi_Minh; Sep→Aug boundary mirroring `parsers._date_token_to_iso`; terms Fall/Spring/Summer).
- `vinuni_agent.py:chat()` prepends a "[Bối cảnh thời gian / Time context: …]" preamble each turn
  (gated by `enable_time_awareness`, fail-open).
- `prompts.py` BASE_PRINCIPLES: rule to use the injected date for "hiện tại/sắp tới/còn bao lâu".
- `tools.py`: new `get_current_datetime` tool (today + AY + term as JSON) added to the tool list.
- Config `ENABLE_TIME_AWARENESS=true` (config.py + `.env.example`).
- Tests: `tests/test_timeutils.py` (8 cases, incl. the Jun 18 2026 → Summer 2025-2026 live case).
**Offline gates.** `ruff` clean; `pytest -m "not live"` = **126 passed**, 2 failed = the **pre-existing**
`test_chunker.py` (markdown-header + missing `docx` module), unrelated to this phase.
**Live-test finding + fix.** First live smoke returned the canned refusal: `should_gracefully_degrade`
(guardrails.py:470) refuses any **uncited** answer, and a current-semester answer is derived from the
injected date (no document). **Fix (user chose "deterministic responder"):** `is_pure_time_question()`
(timeutils.py, tight regex) intercepts only pure "which term/year/date is it now?" questions in
`chat()` and answers deterministically from `current_time_context()` (no LLM, no degradation guard),
citing the Academic Calendar. Calendar-DATA questions still flow to the agent.
**Live smoke (2026-06-18, re-run after fix).**
- VI "Hiện tại tôi đang ở học kỳ nào?" → "Hôm nay là 2026-06-18 (Thursday). Bạn đang ở **học kỳ
  Summer**, năm học 2025-2026." + Academic Calendar citation. ✓
- EN "What semester am I currently in?" → "…Summer term, academic year 2025-2026." + citation. ✓
- Negative control "When are this semester's final exams?" → **not** intercepted; agent used the
  injected date to read "this semester" = Summer 2026 and answered with the exam window + citations. ✓
**Detector hardening (stress-tested per user request).** Rewrote `is_pure_time_question` from a loose
single regex into two strict branches (date/weekday with a today/now-anchored quantifier; term/year via
*structural* patterns where the now-sense binds to the subject). Fixes false positives that broke
earlier versions: "what is today's assignment?", "Hạn nộp là ngày mấy?", "Hôm nay là ngày khai giảng?",
"What's the current tuition for this semester?", "Học kỳ nào có môn X?".
**Live probe (2026-06-19).** Intercepted: "what year is it?", "Bây giờ thứ mấy?" (deterministic).
Flowed to the agent (correctly NOT hijacked): "Hạn nộp là ngày mấy?" (→ a drop-deadline answer),
"what is today's assignment?" (→ graceful no-info), "Học kỳ nào có môn Lập trình?" (→ catalog lookup).
**Broader online batch (2026-06-19, 7 cases).** Pure-time intercepts all correct. Date-aware reasoning
flowed to the agent and used "today" correctly: "days until Summer finals" → Aug 24–28, **66 days from
Jun 19** ✓; "weeks until Fall 2026" → Sep 21, **~13 weeks** ✓. **One wrong answer = a Phase 1.13
preview, not a 1.9 defect:** "is add/drop open now?" → "last day … Summer 2026 is **July 15, 2025**"
citing the **AY24-25** calendar PDF — multi-calendar year-confusion. Useful intel: the AY24-25 PDF *is*
indexed and mixes with the current year (feeds 1.13).
**Offline gates (final).** `ruff` clean; `tests/test_timeutils.py` = **45 passed** (AY/term boundaries +
18 positive + 19 adversarial-negative detector cases); full `pytest -m "not live"` green except the 2
pre-existing `test_chunker` failures.
**Open question for the user.** Permanent golden cases for "current semester" are **date-fragile**, so
I did *not* add brittle time-dependent cases to the stable set. Say if you'd prefer a frozen-clock case.
**Verified by user?** ✅ **Signed off 2026-06-19.** (Open item the user declined for now: a frozen-clock
golden test — left out to avoid a date-fragile permanent case.)

---

## Phase 1.10 — Chat-time rate limiting (Issue #2) — `[x]` done (verified 2026-06-19)

**Problem.** No protection against a client hammering `/chat` (cost + abuse).
**Root cause.** No limiter in `main.py`/`routes_chat.py`; only ingest has `crawl_rate_limit_seconds`.
**Brainstorm decision.** Hand-rolled in-process sliding-window middleware (no new dep; mirrors
`request_id_middleware`). **Keyed by client IP** (X-Forwarded-For aware) — *not* conversation_id,
because reading the JSON body inside `@app.middleware("http")` is a known foot-gun (consumes the body
stream under `BaseHTTPMiddleware`); conversation-keying + Redis are the documented multi-replica
upgrade. Fail-open; `/health` + `OPTIONS` exempt.
**Implemented (2026-06-19).**
- `vinchatbot/app/api/ratelimit.py`: `SlidingWindowRateLimiter` (per-key deque, monotonic-clock window)
  + `add_rate_limit_middleware()` returning **429** `{error,detail,retry_after}` + `Retry-After` header.
- Config: `RATE_LIMIT_ENABLED` (default **false**), `RATE_LIMIT_MAX_REQUESTS` (30),
  `RATE_LIMIT_WINDOW_SECONDS` (60) — config.py + `.env.example`.
- Wired in `main.py:create_app()` before `request_id_middleware` (so 429s still carry X-Request-ID).
- Tests: `tests/test_ratelimit.py` (5) — window allow→block→recover, key independence, 429 + Retry-After
  via TestClient, `/health` exempt, disabled=passthrough.
**Gates.** `ruff` clean; rate-limit tests **5 passed**; full `pytest -m "not live"` = **168 passed**
(2 pre-existing `test_chunker` fails only). End-to-end `create_app` check (flag on, max=2): `/nope` →
`[404,404,429]`, 429 body `{"error":"rate_limited",…,"retry_after":60}` + `Retry-After: 60`; `/health`
→ `[200×5]`; the 429 log line carried an X-Request-ID (correlation preserved).
**Verified by user?** ✅ **Signed off 2026-06-19** (user moved on to 1.11).

---

## Phase 1.11 — Consistency: reduce nondeterminism + multi-run eval (Issue #5) — `[~]` *prerequisite*

**Problem.** Same question → different answers.
**Root-cause diagnostic (2026-06-19, layered live experiment — proven, not assumed):**
- **A. LLM query expansion (`expand_query` ×5): NONDETERMINISTIC = the root.** Variant set changes every
  call — different EN translation ("schedule" vs "date" vs "when"), VI wording, even variant *count*
  (4 vs 3) → different multi-query candidate pool → different fused top-k → different evidence → answer.
- **B. Single-query retrieval (`search(q)` ×3): DETERMINISTIC.** Identical ordered chunk_ids all 3 runs.
- **C. Reranker (`rerank(q,docs)` ×2): DETERMINISTIC in effect.** Same order; scores differ only at the
  4th–5th decimal. **The earlier "reranker nondeterminism" assumption was WRONG** — no work needed.
- Second (smaller) root: **answer generation at temp 0.1** varies wording/inclusion even with identical
  evidence.
**Cheap fix (targets the proven root; no new infra/recurring cost).** Plumb a per-call `temperature`
through `build_chat_model`, set **0.0** on (1) expansion → stable variants → stable retrieval (biggest
lever), (2) answer generation, (3) supervisor routing. Prose temperature stays configurable. Optional
tiny in-process expansion cache (also a 1.15 cost/latency win).
**Measure cheaply.** Build `run_eval.py --runs N` as a reusable tool, but validate THIS fix with a small
**consistency probe** (~12 questions ×3 runs; answer + citation stability before/after) — avoids an
expensive N× full-130 eval.
**Gate.** Probe: answer/citation stability ↑ after the fix; one eval run ≥ 0.885, guards 1.000.

**BEFORE baseline — `scripts/consistency_probe.py`, 9 hard student-phrased questions ×3 (current
pipeline, temp 0.1, always-on expansion):** mean distinct_answers **2.56/3**, mean jaccard **0.81**,
fully-stable **2/9**, stable-citation **5/9**. Insights:
- **Two independent roots, separated by the citation-stability signal:** (a) **generation-temp** — Q0
  (LOA) / Q7 (retake) / Q8 (graduation) have **stable citations but 3/3 distinct answers** (jaccard
  0.62–0.88): retrieval identical, only wording varies → **temp=0 on the answer model** fixes these.
  (b) **expansion** — Q4 (late fee) / Q5 (mental-health) / Q6 (cheapest program) have **unstable
  citations**: evidence set changes run-to-run → temp=0 expansion / reactive single-query fixes these.
- **5/9 stable citations but only 2/9 stable answers** → answer-gen temperature is a *major
  independent* root, not just expansion. temp=0 on the answer model is essential, not optional.
- **Reproducible reliability bug:** Q3 "add/drop deadline kỳ này" → model passes an invalid
  `semester` filter → Qdrant **400 → 503 every run**. `_search` passes model-invented filter keys
  through unguarded. Cheap fix: drop filter keys not in the indexed payload fields (fail-open). Feeds
  reliability + ties to the calendar work (1.13).
- Q1 (per-credit + per-sem) **consistently refuses** → confirms the 1.16 hard case; Q6 (cheapest
  program) **works** → the gap is per-credit data + division, not cross-program comparison per se.
- Vague Q2 ("upcoming deadline") → different deadline subsets each run → vagueness amplifies variance
  (1.18 clarification territory). (Phase 1.9 worked: it resolved "sắp tới" against today's date.)
**Implemented so far (2026-06-19):** (1) **crash fix** — `_to_qdrant_filter` drops filter keys not in
the indexed payload set, so a model-invented `semester` filter no longer 400s/503s (was reproducible on
Q3); regression test added. (2) **temp=0 plumbing** — `build_chat_model(temperature=…)`; `LLM_TEMPERATURE=0.0`
on the shared answer/routing model + temp=0 on expansion. Offline: ruff clean, 168 passed (+ the 2
pre-existing chunker fails), new filter test passes.

**AFTER measurement (temp=0 + crash fix), same 9 hard questions ×3:** mean distinct **2.44** (was 2.56),
jaccard **0.75** (was 0.81), fully-stable **2/9**, stable-citation **6/9** (was 5/9). **temp=0 did NOT
fix consistency.** Micro-test root: a *raw* answer call at temp=0 is byte-identical ×3, but **expansion
still varies at temp=0** (2/3 identical, 1 diverged), and a turn is a **chain** (route→expand→ReAct
tool-call→answer) where residual per-call nondeterminism compounds and the answer is conditioned on the
model's own varying reasoning tokens (Q0: stable citations yet 3/3 wordings). Crash fix verified — Q3
now a clean refusal, not an error.

**Pivot (decided with user):** byte-identical answers aren't achievable with a ReAct LLM; reframe the
goal to **substance consistency (same facts + sources)** — by that lens we're already decent (core facts
stable; real failure is Q6 retrieval flip: finds Nursing fee vs refuses). The lever is **deterministic
retrieval = reactive single-query** (single-query proven deterministic; expansion is the churn), with
temp=0 locking the answer given stable context. Keep temp=0 + crash fix (correct + free); implement
reactive single-query next + re-measure with a substance metric.

**Data-integrity note (Qdrant inventory, `scripts/qdrant_inventory.py`):** collection is an
*accumulation*, not a clean last-ingest — 7957 pts, 63 exact-dup points, calendar/academic spans
**2024-2025 (53) + 2026-2027 (34) + 147 with NO academic_year**, plus heavy historical/low-value bulk
(one guidebook = 473 pts; 929 "unknown"; 878 spreadsheet). Doesn't affect the temp A/B (same data both
runs) but **a clean recreate-from-scratch re-index is a prerequisite for the 1.13/1.14 re-index phases**
(ingest has no clear path today → add `--recreate`).
**Reactive single-query implemented (Phase 1.11d, `ENABLE_REACTIVE_EXPANSION`, default off).** `_search`
does ONE deterministic single query first; fans out to LLM expansion only when the top score <
`REACTIVE_EXPANSION_MIN_SCORE` (0.35). Refactored `_search` (extracted `_single_query`/`_expanded_search`);
flag-off path is behavior-identical. Tests: reactive skips expansion when strong / escalates when weak
(2 new); 11 retrieval tests pass. Escalation trigger is a **deterministic score threshold**, NOT a model
decision (a model "should I retry?" call would re-add nondeterminism — that's Phase 1.17's job).

**Probe comparison (9 hard questions ×3):**
| metric | BEFORE (temp0.1, always-on) | temp=0 only | **reactive** |
|---|---|---|---|
| mean distinct_answers | 2.56 | 2.44 | **1.89** |
| mean jaccard | 0.81 | 0.75 | **0.92** |
| fully-stable | 2/9 | 2/9 | **4/9** |
| stable-citation | 5/9 | 6/9 | **7/9** |
| refuse/answer-consistent | — | — | **9/9** |

Clear substance-consistency win (no refuse↔answer flips; Q4/Q5 now perfectly stable). **Recall caveat:**
Q6 (cheapest program) + Q1 (per-credit) now *consistently refuse* — reactive lost the sometimes-correct
Q6 answer. Both are comparison/aggregation = **Phase 1.16**, not an expansion issue, but it flags the
real risk → **must run the full 130-case eval to confirm overall recall ≥ 0.885 before flipping the
default** (and tune the 0.35 threshold if needed).
**Full 130-eval, reactive ON (`eval_20260618T191543Z`, diff vs 0.885 baseline): 0.862 (+3/−6) — GATE
FAILED** (overall < 0.885; **unanswerable 1.0→0.8** = guard regression). Per-category: policy_conduct
**0.571→0.714** (gained), calendar 0.929→0.893, calendar_pointlookup 0.733→0.700, financial
0.875→0.812, unanswerable 1.0→0.8; adversarial/safety/conduct/multiturn/services = 1.0.
**Layer diagnosis of the 6 losses (citations stayed ~1.0 → right source, wrong fact):**
- **5/6 retrieval recall, all Vietnamese** (culture-day/hung-king refused; fall/spring publish-date wrong
  row; MD-tuition wrong number). Root: I made **both** paraphrase AND the VI↔EN cross-lingual variant
  reactive — but cross-lingual (1.8) is a real recall lever; gating it means VI queries lose the English
  net. **Over-gated.**
- **1/6 generation** (unans-future-tuition-en: answered "2031 tuition = 932,400,000" instead of
  refusing) — a refusal/reasoning gap (temp=0 likely made it commit). Needs a "refuse future/speculative
  years" prompt rule.
**Fix (next iteration):** (A) in reactive mode keep **cross-lingual translation always-on**, make only
the **paraphrase flood reactive**; (B) add a refuse-future-dated-questions rule to the financial/base
prompt. Then re-run probe + one full eval.
**Fix applied (2026-06-19):** (A) reactive mode now keeps the **VI↔EN translation always-on** (recall
lever) and gates only the **paraphrase flood**; escalate to paraphrases only when weak. (B) FINANCIAL_PROMPT
rule keyed on **grounding, not time**: state figures only for the exact year/term the source gives;
if that year/term isn't in the source, say so (don't transpose another year's number). Explicitly:
a *future* point is answered normally IF it's in the source (published fee-raise / published AY tariff
or calendar) — only ungrounded years are refused. (Reworded after user flagged that a "refuse-future"
rule would wrongly reject documented future facts like the AY2026-27 calendar.) Tests: new
"cross-lingual stays on by default" test; 12 retrieval tests pass; ruff clean. Cheap probe (reactive +
xling-on): **stable-citation 8/9** (best yet), refuse/answer-consistent **9/9**, mean distinct 2.33
(wording varies more with translation back — cosmetic per the substance reframe).
**Next:** one more full 130-eval to confirm the VI recall losses are recovered (gate ≥0.885, guards 1.000).
**Confirming full eval (`eval_20260619T003818Z`, diff vs 0.885 baseline): 0.923 (+6/−1) — GATE PASSED.**
Guards all 1.000 (unanswerable recovered via the grounding rule). Per-category: financial 0.875→0.938,
calendar_pointlookup 0.733→0.800, policy_conduct 0.571→0.857, calendar 0.929 (held); all 5 VI recall
losses recovered. Only loss: `calendar-summer-evaluation-vi` (1 VI point-lookup, within ±3 noise). **Root cause of that
loss:** NOT the reactive design — for a calendar point-lookup the reactive path is byte-identical to
baseline retrieval (paraphrase already off for calendar since 1.7; cross-lingual on; fuse→rerank-once;
full-section read). The only change is **temp=0**, which locked in a **generation-layer adjacent-row
extraction error**: asked for the *course-evaluation* period (Aug 16–20, 2027) the model returned the
adjacent *final-exam* window (Aug 23–27) — hit the forbidden date. At baseline temp 0.1 the pick was a
coin-flip that landed right; temp=0 made the wrong pick deterministic. → a clean **Phase 1.13** target
(calendar chunks must disambiguate "evaluation period" vs "exam period"); not patching CALENDAR_PROMPT
ad-hoc now.
**PROMOTED:** `ENABLE_REACTIVE_EXPANSION` default → **true** (config.py + .env.example); `baseline.json`
updated to the 0.923 report (new production reference). Offline: 172 passed (2 pre-existing chunker
fails). **New production score 0.923 / 130 (best of the project).**
**Net Phase 1.11 deliverables:** crash fix (filter-key guard), temp=0 (LLM_TEMPERATURE), reactive
expansion (cross-lingual on + paraphrase gated), grounding-keyed refusal rule, `consistency_probe.py`,
`qdrant_inventory.py`. Consistency ↑ (8/9 stable citations, 0 refuse-flips) + cost ↓ (no upfront 4×
fan-out) + quality ↑ (0.885→0.923).
**Result.** Shipped on; 0.923 / guards 1.000. · **Verified by user?** ✅ **Signed off 2026-06-19.**

---

## Phase 1.12 — Expansion overhaul: EN↔VI + date-format normalization (Issue #4) — `[~]`

**Problem.** "events for 6/2026" works but "tháng 6 năm 2026" fails.
**Root cause.** Cross-lingual variant is one stochastic direction per call; **no deterministic date
normalization**.
**Implemented (2026-06-19).** `normalize_date_phrases(query)` in query_engineering.py — pure-regex
detector of month+year in VI/EN/numeric forms that emits the other canonical forms
("tháng 6 năm 2026" ↔ "June 2026" ↔ "6/2026" ↔ "06/2026"); merged into the multi-query set in
`_search`/`_multi_search` (also makes date queries take the multi path even if expansion flags are off).
Gated `ENABLE_DATE_NORMALIZATION` (default true; no-op for non-date queries). Tests: convergence across
3 forms + no-false-positives ("Summer 2026"/"in 2026" → none); 14 retrieval tests pass; offline 174
passed; ruff clean.
**Live check.** VI "tháng 10 năm 2026" and VI "10/2026" now return **identical** events (1-Oct add +
9-Oct course-drop) — the reported divergence is fixed.
**FINDING (separate, pre-existing guard bug — logged, not fixed here):** the EN phrasing "What
deadlines or events are there in October 2026?" is **deterministically refused as out_of_scope** (4/4).
Traced: the **rule tier** returns `needs_scope_router` for that EN "events/deadlines" phrasing → the LLM
scope classifier then wrongly says out_of_scope. VI equivalent + "When is the course drop deadline?"
pass at the rule tier. Runs **before** retrieval, so unrelated to 1.12. → **moved into Phase 1.18**
(don't-over-refuse). Also: guards still run at temp 0.1 (left untouched) — a remaining nondeterminism
source, though this case is deterministic.
**Gate / scope (settled deterministically, not by the noisy eval).** A local scan of all 130 golden
questions shows `normalize_date_phrases` **fires on exactly 2 cases** (`calendar-source-inconsistency-en/vi`,
Jun 2027) — the other **128 are byte-identical to pre-1.12**. Both affected cases are stable (not in any
lost/gained diff → passing). So **all non-calendar domains are confirmed untouched by construction**, and
the 0.869 single-run eval was **100% noise** (none of its 8 losses are among the 2 cases 1.12 touches).
**Eval result `eval_20260619T034725Z` = 0.869** but exonerated as noise (see above); baseline stays 0.923.
**Decisions.** (1) Keep 1.12 ON (provably no-op for 128/130; fixes the real date-phrasing bug; gated
`ENABLE_DATE_NORMALIZATION`). (2) **Do NOT build the translation/expansion cache** — throwaway if 1.14
removes the translation (translation-OFF via multilingual embedding). Seed = skip. Interim noise handling
= **multi-run eval at promotion gates**; **1.14 = the cure**. 1.15's other caches (ingest-embedding,
rerank, hot-Q&A) are independent and still planned.
**Result.** Implemented (code shipped, gated on); scope proven (2/130, both passing) → other domains
untouched; eval delta = noise; cache cut. **`*` Validation MERGED into Phase 1.13** (date-norm + calendar
chunk-reshape scope the same problem → test together against harder calendar cases, one combined eval
clears the noise band). · **Verified by user?** ☐ (with 1.13)

---

## Phase 1.13 — Calendar correctness (date-norm + chunk reshape + year-aware + crawler) (Issue #3 + #4) — `[~]` *large, re-index*

**Problem.** AY2026-27 calendar (Sep 2026→Aug 2027); asking for June 2026 returns June 2027.
**Root cause (chunk shape, not the date parser).** `_calendar_event_to_text` leads with ambiguous
"2026-2027" + relative "15-Jun" (absolute year buried in the ISO tail); substring boost matches "2026"
⊂ "2026-2027" (context.py:162); only the AY2026-27 calendar is ingested.
**Plan (combined — date-norm + calendar data both scope the same date↔calendar matching problem):**
- **(a) Query-side date normalization — DONE (from 1.12), validated here.** `normalize_date_phrases`
  already adds both-language month+year forms to the query.
- **(b) Doc-side chunk reshape** — lead with absolute "Tháng 6 năm 2027 (2027-06-15)" both languages.
- **(c) Year-aware retrieval** — exact AY/month boost (not substring) + optional `academic_year`/`term`
  filter; disambiguate evaluation-period vs exam-period rows (the 1.11 adjacent-row loss).
- **(d) Crawler** — seeds for all AY calendars (AY24-25 PDF + policy PDF + HTML; find AY23-24/25-26).
- **Prereq:** clean recreate-from-scratch re-index (collection is polluted — see 1.11 note); add
  `--recreate` to ingest. **Do the universal fix first; manual per-AY docs are the fallback if it fails.**
**Test (user ask): a HARDER calendar set** — year-disambiguation (June 2026 vs 2027), adjacent-row
(evaluation vs exam; drop vs add deadline), publish-date vs event-date, cross-lingual date, multi-event
listing, term boundaries, holidays (Hung King / Culture Day), cross-AY comparison, honest-no-data for
un-ingested years. Source-verified; added to the golden set.
**Experiment / gate.** Scratch-collection **combined** A/B (date-norm + reshape together) on the harder
set + full 130, **multi-run** to clear the noise band; "6/2026" → correct AY2025-26 or honest "no data"
(never AY2026-27 June); "6/2027" → June 2027; `forbidden_facts` = wrong-year/adjacent date; calendar ≥
baseline; guards 1.000.
**Scratch validation (2026-06-19): `--recreate` re-ingest of local data/raw → `vinuni_documents_v2`
(612 chunks, 0 dupes; AY2026-27 calendar present, reshaped). Hard calendar probe ×2:** mean distinct
**1.30**, jaccard 0.95, **10/10 stable citations, 0 flips** (consistency now excellent).
- **Core bug FIXED:** "tháng 6 năm 2026" no longer returns June-2027 events. June-2027 events correctly
  dated. **Q4 publish-date-vs-event RECOVERED** ("Fall'26 exam schedule published 7 Dec" ✓, a prior
  loss). Wins: course-drop = 9 Oct ✓, add/drop list ✓, "next deadline" via current date = 9 Oct 2026 ✓.
- **PROBLEM 1 — guard over-refusal (1.18) is now the dominant calendar blocker:** 4/10 refused
  out_of_scope, **including legitimate Q1 "What events are in June 2027?" and Q7 "Hung King 2027"**
  (deterministic, both runs). The scope guard blocks "what events / liệt kê … sự kiện" listing phrasings
  before retrieval. → **escalates 1.18 priority** (it's breaking real calendar Q&A, not just an edge case).
- **PROBLEM 2 — same-month adjacent-row residual:** Q2 "Summer'27 *evaluation* period" → returned the
  *exam* window (Aug 23-27) instead of evaluation (Aug 16-20). Reshape disambiguates year+month but NOT
  two event-types in the SAME month → needs an event_type signal/boost or a strict prompt nudge.
- **Caveat:** `v2` is a PARTIAL corpus (local data/raw = 98 docs / 612 chunks vs production's 7957);
  validates the calendar reshape mechanism, not full-scale. June-2026 *real events* still need the
  AY2025-26 calendar crawled in.
**Both residuals fixed (2026-06-19), re-validated on `v2`:**
- **Guard over-refusal (root = hardcoded rule tier, not the LLM):** `SCOPE_TERMS` was missing obvious
  in-scope words, dumping calendar questions into `GRAY_SCOPE_PATTERNS` → the unreliable qwen scope
  router → false out_of_scope. Fix: added `nam hoc, event(s), su kien, holiday(s), ngay le, nghi le,
  commemoration, gio to` to `SCOPE_TERMS` (whole-word matched, so plurals added explicitly). Safe — no
  out-of-scope eval category; benign off-topic handled downstream; gray-zone preserved for generic
  "key dates in <year>". Guard test updated (event-question → allow; generic-dates → router); 23 guard
  tests pass.
- **Same-month adjacent-row:** `CALENDAR_PROMPT` rule added — "Course Evaluation Period ≠ Final Exam
  Period" (mirrors the existing drop≠add rule).
**Re-validation (hard set on `v2`):** all 10 answer correctly — Q1 "June 2027" now answers (was
refused); Q2 evaluation → **16-20 Aug** (was the exam 23-27); Q0 "June 2026" → honest "no events" +
June-2027 clearly labeled 2027; Hung King 16 Apr; course-drop 9 Oct; publish-date 7 Dec; consistency
10/10 stable citations. Offline: ruff clean, 178 passed (2 pre-existing chunker fails).
**This guard fix = the substance of Phase 1.18 (don't-over-refuse), delivered here.**
**Result.** Calendar correctness validated on scratch `v2`: year-confusion + evaluation/exam + guard
over-refusal all fixed. Remaining = production-scale re-ingest + AY2025-26 crawl (June-2026 real events). · **Verified by user?** ☐

---

## Phase 1.14 — Embedding A/B for VI+EN (Issue #6) — `[ ]` *large, re-index*

**Problem/goal.** Find a stronger VI+EN embedding; A/B with & without bilingual expansion vs baseline.
**Plan.** Arm 1 = `text-embedding-3-large` (drop-in, scratch re-index). Arm 2 = Cohere `embed-v4` (new
adapter, `input_type`, COHERE_API_KEY) — best cross-lingual + same vendor as our reranker. BGE-M3 =
free self-hosted fallback. Provider-pluggable config; scratch collection per arm; multi-run eval.
**FOLDED IN (from the 1.11 noise finding): test dropping the LLM cross-lingual translation.** The
always-on VI↔EN translation is the dominant run-to-run nondeterminism source (LLM call varies even at
temp=0 → eval ~±8). A strong multilingual embedding may match a VI query to EN docs **directly** →
translation variant becomes unnecessary. Add a 3rd A/B axis: **translation ON vs OFF** per arm; if an
arm holds VI recall with translation OFF, **remove the translation call** → retrieval deterministic *by
construction* (the real consistency cure, vs the cache/seed masks). Measure recall **and** run-to-run
stability (`consistency_probe.py`).
**Experiment / gate.** Promote only if mean beats the reference by > noise band AND cost acceptable;
guards 1.000; **prefer the config that allows translation OFF without losing VI recall**.

**EMBEDDING SELECTED → `intfloat/multilingual-e5-large` via OpenRouter (2026-06-20).**
- **Cross-lingual probe** (12 VI↔EN pairs, confusable distractors; embeddings only, no LLM): 3-small
  11/12 (MRR .944); **3-large 11/12 (MRR .938)** — same top-1, only bigger margin (English-first
  upgrade, no new bilingual reach); **e5-large 12/12 (MRR 1.000)** — fixes the pair both OpenAI models
  miss. e5 = the genuine bilingual win.
- **No API model worth it:** Cohere embed-v4 / gemini-embedding-001 / Voyage rank above e5 on MTEB but
  need their own native keys (NOT OpenRouter) and e5 already maxes our probe. Skipped.
- **KEY FINDING: OpenRouter DOES serve e5** (`intfloat/multilingual-e5-large`, 1024-d; also `baai/bge-m3`).
  Earlier "OpenRouter only serves OpenAI embeddings" was WRONG (only Cohere had been tested). So e5 =
  12/12 quality, **NO new key, fast API, no local CPU, scalable.** Local fastembed-e5 was wired too but
  is too slow (12 min vs ~3 min / 716 chunks) → OpenRouter path chosen.
- **Bug fixed:** LangChain `OpenAIEmbeddings` tiktoken-tokenizes inputs (OpenAI-only) → e5/bge on
  OpenRouter return "No embedding data received". `build_embeddings` sets
  `check_embedding_ctx_length=False, tiktoken_enabled=False` for non-OpenAI models. New config:
  `EMBEDDING_BACKEND`, `LOCAL_EMBEDDING_MODEL`.
- **Real-corpus retrieval A/B** (716 chunks, 3small vs e5, no answer LLM): calendar-year correct on BOTH
  (parser fix); **e5 wins the VI cases** — Nursing tuition (e5 → real Tariff table; 3-small → wrong 932M)
  and Hung King (e5 → current AY2026-27; 3-small → stale AY2024-25). e5 ≥ 3small everywhere.
**NEXT:** full crawl (max-pages 2000) → full-corpus e5 ingest → eval **bilingual expansion ON vs OFF vs
0.923** (fair, full scale); if e5 holds VI recall with translation OFF → drop the nondeterministic
translation (consistency cure) + promote. Guards must stay 1.000.

**PARSER/CRAWLER HARDENING (2026-06-20) — the real fix for the calendar bug at scale.** Audit of the
ingest pipeline found three bugs that let "June 2026 → June 2027" recur on a full re-ingest:
1. `infer_academic_year` took the FIRST `20xx-20yy` anywhere in the doc (+ a `"2025" in text and "2026"`
   coin-flip) → a calendar could be mislabeled, mislabeling every event's year. **Fixed:** prefer a
   *consecutive* year-range in the TITLE region (near "academic calendar"/"academic year"), then short
   `AY24-25` forms (text/URL), then any consecutive range; **no hardcoded guess** (returns None).
   Also handles en-dash `–` (the AY2026-27 PDF used `2026–2027` → old regex missed it → AY=None).
2. `extract_calendar_events` keyword gate too narrow → dropped "Course Evaluation Period",
   "Commencement", "Orientation", "Registration", VN holidays (Giỗ Tổ/Quốc Khánh). **Fixed:** broadened
   concept list (date requirement still filters noise).
3. `_date_token_to_iso` hardcoded 2025/2026 when no AY → wrong years. **Fixed:** return None.
- **Crawler scope fix:** `_is_policy_allowed_path` rejected `policy.vinuni.edu.vn/vinuni-academic-calendar`
  (`policy_path_out_of_scope`) → added `"calendar" in path`.
- 12 new tests (`tests/test_calendar_parser_hardening.py`), ruff clean, full suite **240 passed**.
- **Validated on a real re-crawl:** every calendar PDF now carries its correct AY (was AY=None), and ISO
  years line up (AY2024-25→2024/2025; AY2026-27→2026/2027). The June-confusion is structurally gone.
- **DATA FINDING:** `policy.vinuni.edu.vn/vinuni-academic-calendar` now **301-redirects to the AY2026-27
  PDF** — the **AY2025-26 calendar is gone**, so **June-2026 real events can't be crawled**. Correct
  behavior = honest no-data for June 2026; June 2027 resolves to the real AY2026-27 events.
**Result.** Parser/crawler hardened + validated; calendar correctness no longer embedding-dependent.
Remaining = full-corpus re-ingest + eval (shared with 1.14). · **Verified by user?** ☐

---

## Phase 1.15 — Mass caching + async/parallelization (Issue #7) — `[ ]`

**Problem/goal.** Little is cached; find async wins.
**Plan.** Caching (flag-gated, cold-cache-transparent): ~~expansion/translation cache~~ **CUT** (throwaway
if 1.14 removes the translation), ingest embedding content-hash cache (~25-30% re-index saving), rerank
cache, optional hot-Q&A answer cache (TTL, off by default). Async: overlap safe guard/retrieval; document
serial routing→specialist. Cache-hit counts in
`_log_turn`.
**Experiment / gate.** Eval no regression on cold cache; measure latency/cost delta.
**Result.** _(pending)_ · **Verified by user?** ☐

---

## Phase 1.16 — Multi-domain reasoning (Issue #8) — `[ ]`

**Problem.** "học phí trên mỗi tín chỉ các ngành?" fails (per-credit tuition across all programs).
**Root cause.** Single-intent routing; 8-chunk cap; `fee_record` has no per-credit/credits fields.
**Plan (no heuristic, O(1) rerank).** Decomposition into N sub-questions = O(N) rerank → **rejected**.
Instead: **single wide retrieval + larger `candidate_k`/`max_k` + rerank ONCE** (Cohere bills per
search call, not per doc → bigger pool is the same price). "List mode" set via the agent's **existing**
tool-call arg (no heuristic, no extra LLM call). Optional `fee_record` per-credit fields for the
compute case. Decomposition only a rare bounded last resort.
**Experiment / gate.** All three queries pass (multi-run); **rerank calls/turn stay O(1)** (`_log_turn`);
single-domain financial no regression; guards 1.000.
**Result.** _(pending)_ · **Verified by user?** ☐

---

## Phase 1.17 — Agent-decided expansion (Issue #9) — `[ ]`

**Problem/goal.** Expansion is always-on in `_search`; the agent should decide.
**Plan (no extra LLM call).** Separate expansion sub-tools = extra LLM calls → **rejected**. Instead:
expansion options as **arguments on the existing search tool call** (`search(query, expand={...})`),
optionally informed by the supervisor's widened routing JSON. Deterministic helpers (1.12 dates,
`is_point_lookup`) run free inside `_search`. Auto-expansion stays default behind the flag until A/B.
**Depends on 1.12 + 1.16.**
**Experiment / gate.** Correct expansion choices with **no increase in LLM calls/turn** (`_log_turn`)
and no added latency on simple queries; A/B ≥ baseline.
**Result.** _(pending)_ · **Verified by user?** ☐

---

## Phase 1.18 — Clarification path + don't-over-refuse (Issue #10 + guard-precision) — `[~]`

**Root cause (read-only audit of the rule tier):** scope is **default-deny** — `allow` only if a
`SCOPE_TERMS` keyword matches (else gray-zone → over-refusing qwen, or hard `out_of_scope`). Plus: whole-
word matching missed plurals ("event"≠"events"); base64 auto-decode could false-positive; 4 keyword
systems drift. Security/safety tiers (regex injection/restricted/abuse + omni-moderation + indirect scan
+ output checks) are sound and stay hard-blocking. **Architecture decision:** scope → a *soft* outcome
(off-topic → no citations → graceful-degradation, which the scorer counts as a refusal); the security
stack is the real guardrail, run independent of scope. **NeMo rejected** (langchain<0.4 pin).

**STAGE 1 — DONE (2026-06-19), always-on, low-risk:**
- `_contains_term` now matches a regular plural for long ascii nouns (`event`→`events`) without
  over-matching short VI tokens (`thi`↛`this`).
- `SCOPE_TERMS` expanded to the missing student-life topics (internship, career, mental-health/tư vấn
  tâm lý, housing, wifi/IT, transcript, health/clinic, parking, insurance, …) + the calendar words.
- **base64 false-positive fix**: decoded text is appended for matching ONLY if it itself matches an
  injection pattern (benign long tokens no longer trip the rule).
- **Guard temp=0** on the LLM injection/scope guard, the gray-scope router, and the Llama-guard path.
- New `tests/test_guard_scope.py` (26): must-allow across all topics (EN+VI, plurals, listing) +
  must-refuse security (injection/restricted/abuse/leet) + must-refuse off-topic (weather/code/
  celebrity/integral). Offline: **204 passed** (2 pre-existing chunker fails), ruff clean; all existing
  security/obfuscation/safety guard tests still pass.

**STAGE 2 — DONE (flag-gated `ENABLE_SOFT_SCOPE`, default off):** `resolve_guardrail_decision` downgrades
a SCOPE refusal to allow (`_soften_scope`) while keeping injection/restricted/abuse verdicts; off-topic
falls to the agent → graceful-degradation. Offline tests (soft-scope on→off-topic allowed at guard;
security still hard-blocks). **Live probe (soft-scope ON):** legit June-2027/tư-vấn-tâm-lý/internship
now **answered with citations** (over-refusal fixed); off-topic (weather/Python/integral) → graceful-
degradation; injection → blocked; self-harm/harassment → abusive_language. All refused or answered
correctly. 218 offline pass.

**🔴 CRITICAL SAFETY FINDING (from live probing) — the moderation tier was DEAD.** Direct test:
`omni-moderation` returned **allow for ALL** of self-harm / weapon / poison / harassment. Root cause:
the OpenAI key 401s ("Incorrect API key") → `assess_safety` **fails OPEN** → silently allowed unsafe
content. The eval never caught it (qwen + scope-refusal covered the cases). Coverage map:
- omni-moderation (dead): 0/4.  qwen guard: self-harm + VI-harassment (misses weapon/poison).
  Llama-Guard-4 (via OpenRouter, working key): self-harm + weapon + poison (misses VI-harassment).
- → **complementary.** **Switched `SAFETY_GUARD_BACKEND` default → `llama_guard`** (config + .env.example);
  qwen kept as the multilingual-abuse complement. **Reliability wrinkle:** in the full pipeline the 12B
  Llama call intermittently fails-open under load (weapon/poison fell back to graceful-degradation) —
  the layered net still refused everything, but safety *detection* isn't 100% reliable yet.
- **Fail-open is the deeper risk:** any safety-backend error = no safety. Consider fail-closed on
  clearly-risky signals and/or a reliable backend.

**OUTPUT-GUARD + PROMPT HARDENING — DONE.** (a) `contains_sensitive_output` now also matches leaked
secret VALUE patterns (`sk-or-v1-…`, `sk-proj-…`, `Bearer <token>`, `api_key=…`, `postgres://user:pass@`),
not just 5 literal markers — so an answer echoing a real key/token/connection-string is blocked
(unit-tested: catches leaks, ignores benign password-reset help + contact emails). (b) **Prompt audit →
added a SAFETY rule to BASE_PRINCIPLES**: refuse self-harm/violence/weapons/harm-to-others (+ self-harm →
empathy + support resources) and never print secrets — an always-on backstop that matters because the
input safety tier proved unreliable. **Defense-in-depth live test (input safety + LLM guard OFF, soft-
scope ON):** all 3 harmful questions still refused (graceful-degradation, no harmful content). 227
offline pass.

**SAFETY BACKEND LOCKED → `openai_moderation` (key patched 2026-06-20).** Head-to-head (valid key):
- **omni-moderation: 8/8 unsafe BLOCKED** (self-harm/weapon/poison/hate/sexual/threat + **VI harassment**)
  and **0/12 benign FALSE-POSITIVES** (incl. traps: stressed→counseling, victim-reporting-harassment,
  "kill a process", "deadline is killing me", self-defense class, heart-attack first-aid) → complete + precise.
- llama_guard: 7/8 (MISSED VI harassment), 0 FP. → omni wins; reverted default to `openai_moderation`
  (free, fast, reliable). llama_guard kept as the no-OpenAI-key fallback; qwen stays as injection backstop.
- **Fail-open hardened:** the swallow-on-error now logs at **WARNING** (safety_guard.py) so a future dead
  key is visible, not silent. (Note: omni can still transiently fail-open under load — the weapon case
  fell to graceful-degradation in a full-pipeline run — but it's logged + the layered net still refuses.)

**REMAINING for 1.18:** the **clarification path** (ReAct prompt rule) + a **live guard-slice eval A/B**
to promote soft-scope (guards must stay 1.000; soft-scope is eval-neutral on safety — both scope-refuse
and graceful-degradation count as refusals).

**Problem/goal.** Two sides of "the bot wrongly declines to help": (a) missing context → it guesses
instead of asking back; (b) the scope guard **over-refuses legitimate in-scope questions**.
**Plan (a) clarification (ReAct-decided, no extra LLM call).** A prompt rule makes "ask vs answer" part
of the agent's **existing** reasoning ("if a required scope — which AY? which program? — is missing, ask
ONE concise question"); free rule-only guards sharpen known cases (calendar year, fee program); a
`clarification` action for the frontend. Tuned to **avoid over-asking**.
**Plan (b) guard over-refusal (moved here from the 1.12 finding).** Reproducible: "What deadlines or
events are there in October 2026?" → deterministically refused out_of_scope; rule tier returns
`needs_scope_router` for that EN phrasing → LLM scope classifier wrongly rejects (VI + "course drop
deadline" pass). Fix = raise rule-tier in-scope recall for legit EN calendar/academic phrasings (and/or
tighten the scope-classifier prompt) **without** lowering adversarial/safety/out-of-scope recall.
**Experiment / gate.** Ambiguous → one clarifying question; clear → answers directly (no over-ask); the
EN-calendar phrasing + a small legit in-scope EN/VI set now **pass** the guard; no extra LLM calls/turn;
adversarial/safety/unanswerable guards **stay 1.000**.
**Result.** _(pending)_ · **Verified by user?** ☐
