# Phase 1.33 — Multi-domain FAN-OUT (decompose → dispatch → synthesize)

> A big, blast-radius-heavy feature behind ONE flag (`ENABLE_FAN_OUT`, default **off**). Single-domain path
> kept **byte-identical** so the ~90% common case cannot regress. Solves TWO single-route failures:
> **(a) compound coverage** ("MD tuition AND when does Fall start" → one specialist, other half dropped) and
> **(b) route ambiguity** (boundary questions the router mis-routes to the wrong single specialist).
> A/B at `--runs 1` (cost-driven), ON vs OFF head-to-head, cache-off. No git commit beyond the pre-fan-out
> checkpoint. Plan: `.claude/plans/can-we-try-to-merry-mango.md`.

## Architecture (built)
`START → supervisor(plan_dispatch) → [single specialist | fanout_node] → END`. A single-assignment plan takes
the existing single-specialist path (byte-identical); a multi-assignment plan fans out.
- **Dispatch planner** (`supervisor.py: plan_dispatch`) emits a PLAN `list[{query,intent}]` in 3 modes:
  SINGLE (~90%, biased hard), DECOMPOSE (distinct sub-questions → different specialists), HEDGE (same question
  to 2 candidate specialists when the owner is ambiguous). Tier-0 fast-path (≤1 domain keyword + no compound
  signal → SINGLE, no LLM); Tier-1 = the planner LLM (`DISPATCH_SYSTEM`). Parse → validate intent ∈ INTENTS →
  fail SAFE to SINGLE.
- **fanout_node** (`graph.py`): subtasks run CONCURRENTLY (`asyncio.gather`), each a FRESH single-subtask
  message (not the whole state), error-isolated (a raising subtask → named gap). Per-subtask empty re-route to
  `services`. Synthesis (`SYNTHESIS_SYSTEM`, VI) merges → emits `(all subtasks' ToolMessages) + synthesis
  AIMessage last` so the service layer unions citations/evidence over the union with NO service change.
- **Service layer**: audit scoped to **groundedness-only** for fused answers (don't run the single-intent
  role-check on a multi-domain answer). Synthesis call recorded in the ledger (also a clean per-case fan-out
  flag: a recorded `synthesis` stage ⇔ this turn fanned out).
- **Config**: `ENABLE_FAN_OUT` (off), `FAN_OUT_MAX_SUBTASKS` (3), `FAN_OUT_REROUTE_MIN_SCORE`, `PLANNER_MODEL`.

## 1.33a — Planner calibration (Stage C) — Tier-0 bug caught by manual inspection
### Trial
Calibrate the 1-vs-many decision on a 50-case adversarial set (anti-over-fire traps, route-ambiguous, genuine
compounds, multi-question, multi-turn, VI). The costly error is OVER-fire (K× cost); UNDER-fire just degrades
to today (safe).
### Experiment
- Initial measurement: decompose 3/16, hedge 0/9 — IDENTICAL across gpt-4o-mini, gemini-2.5-flash,
  claude-haiku-4.5, claude-sonnet-4.5. A stronger model changed NOTHING.
- Manual inspection of the RAW planner output: the models produced PERFECT plans (Sonnet decomposed/hedged
  correctly) — but `classify_intent_confident` Tier-0 returned `single` BEFORE the LLM was called (e.g. "MD
  tuition AND Fall start" → 2 calendar keywords → confident calendar → single). **The bug was upstream of the
  LLM, not the model.**
### Result
Replaced Tier-0 with `_looks_multi` + `len(nonzero)<=1`. The DEFAULT cheap **gpt-4o-mini**: **76% mode-match,
0 under-fire, decompose 16/16, 3 benign over-fires** (cost-not-correctness; hedge-tag cases correctly
decompose). No model upgrade needed — the planner call is tiny (~700 in / ~80 out). Lesson: measure the raw
artifact before blaming the model.

## 1.33b — Build + unit tests (Stages D-E)
15 fan-out unit tests (offline via injected `dispatch_planner` + `model`): JSON parse/fail-safe/cap, single-
subtask FRESH-message invocation, synthesis merge + citation union, `asyncio.gather` error isolation, empty
re-route, single-assignment uses full state, single-assignment DEFERS to the calibrated router, flag-off
byte-identical. Full suite **390 green**, ruff clean. End-to-end smoke (real service): EN+VI decompose merge
both facts with unioned citations; single trap unchanged with flag ON.

## 1.33c — Hard-set A/B v1 (86 cases: 50 fan-out + 16 cross_domain + 11 multihop), cache-off, --runs 1
### Experiment — ON vs OFF head-to-head
- **ON 61/86 (0.709) vs OFF 57/86 (0.663), net +4.** GAINED 9 (4 DECOMPOSE incl. the original
  `cross-tuition-adddrop` coverage failure, **3 HEDGE** — the mis-route fix works, 1 cross, 1 underspecified).
  REGRESSED 5.
- **Cost/latency**: latency mean 12.2s→16.0s (+30%), p95 20.6s→28.4s (+38%) — the real cost (fan-out runs
  K specialists in parallel + a synthesis join). NOTE: `est_cost`/`model_calls` UNDERCOUNT ON — fan-out
  specialists run in `asyncio.gather` child tasks and `record_stage` contextvars don't propagate back, so only
  planner + synthesis are ledgered. **Latency (end-to-end) is the reliable cost signal.** Fan-out rate 58% on
  this adversarial set (by design dense; the full-199 rate is the real cost driver, measured next).
- confidently_wrong 9→15 (8 of 15 were ALREADY cw in OFF; 7 new).

### Regression decode (each general, not case-by-case)
| case | class | cause | fix |
|---|---|---|---|
| `trap-transcript-time-vi` | single-path | planner's single-intent ≠ calibrated `route_intent` (refused) | deferral |
| `multihop-freshman-low-gpa-standing-vi` | single-path | same — planner picked worse single intent | deferral |
| `decompose-md-tuition-weather-en` | golden artifact | correct weather DECLINE says "forecast" → tripped `forbidden_facts:["forecast"]` | (flag golden) |
| `dc-vi-thuvien-datphong-phiphat` | planner drop | planner dropped qualifier "thường" → wrong fine tier (2.000đ vs 10.000đ) | qualifier-preserve |
| `dc-3part-late-fee-...` | retrieval variance | calendar subtask punted on Fall-start (standalone got it) | L2 (pending) |

Plus 3 new-cw safe-fail→confident-wrong (`cross-other-bachelor`, `cross-late-payment`, `dc-vi-rutmon`): the
financial/calendar subtask PUNTED ("not available") or grounded the wrong tier (50% vs 80%) on a narrow
subtask query that a different phrasing finds. **Dominant fan-out failure mode = point-lookup retrieval
variance on narrow decomposed subtask queries.**

### Fixes applied (ON-side only; OFF byte-identical)
1. **Single-assignment deferral**: a SINGLE plan defers to `route_intent` (the planner decides single-vs-multi,
   NOT the single-domain intent) → single-domain routing byte-identical to OFF. Removes 2 regressions.
2. **Planner qualifier preservation** (`DISPATCH_SYSTEM`): copy EVERY qualifier (time window, item/program
   TYPE, term, amount) into the sub-question verbatim. Verified: `dc-vi-thuvien` now retains "thường".
3. Audit groundedness-scoping for fused answers; synthesis cost attribution.

## 1.33d — Hard-set A/B v2 (deferral + qualifier + audit-scope) & v3 (+ L2 reactive loop)
Same 86 cases, same OFF baseline (OFF is byte-identical — the fixes only touch the fan-out branch), cache-off.
Single-run noise is real (the plan anticipated ±3): judge on the NEAR-DETERMINISTIC target flips, not the noisy
aggregate.
- **v2** (deferral + qualifier preservation + audit groundedness-scope): ON 59/86 (0.686). Deferral FIXED the
  single-path `trap-transcript-time-vi`; qualifier fix landed `dc-vi-thuvien` FACTS (now retains "thường" →
  10.000đ, facts_ok flipped True). 7 coverage/hedge gains stable across v1+v2.
- **PUNT class confirmed** (the residual): a financial/calendar subtask answers "no official information
  available" on a fact that EXISTS (a different phrasing finds it). `dc-3part-late-fee` calendar subtask punts
  on Fall-start though the standalone case gets Sep 21. This is the L2 target → built.
- **L2 reactive completeness loop** (`graph.py`): after the gather, any subtask whose answer matches a STRONG
  punt marker ("no official information"/"not available"/"không tìm thấy"/…) is re-run ONCE with a critique +
  its failed attempt ("you answered X; it didn't give the value; the info likely exists — search differently,
  read the full section"). Kept only if the retry produces a non-punt answer (grounded → can recover a real
  value, can't fabricate). Cap=1 outer pass, guarded so the no-punt common case costs zero extra calls. 3 unit
  tests (recover / no-rerun-when-satisfactory / keep-original-when-retry-also-punts). Suite **393 green**.
- **v3** (+ L2): **ON 62/86 (0.721) vs OFF 0.663 — net +5, the best.** L2 cut regressions 5→3 and
  confidently_wrong 16→14. Latency mean 12.2s→16.0s (+31%), p95 +45%.

### v3 regression decode — 1 real, 2 golden-spec
| case | verdict | detail |
|---|---|---|
| `dc-3part-late-fee` | REAL | calendar subtask punts on Fall-start; L2 retried but the retry punted too (phrasing-sensitive retrieval — "When does instruction begin" misses the row "On what date…" hits). 1 case. |
| `dc-vi-thuvien` | golden-spec | facts CORRECT (10.000đ + reserve-stock tier), cited to the REAL source `library-policies-for-users`; golden `expected_source` wrongly demands `room-booking`+`financial-tariff` (the library fine lives in the library policy, not the tariff). |
| `decompose-md-tuition-weather` | golden-spec | correct weather DECLINE trips `forbidden_facts:["forecast"]` ("check weather forecast apps"). |

### Net deterministic verdict (hard set): +8 gains − 1 real regression; the 2 golden-spec cases are
mis-specified tests (the answers are correct). 7 coverage/hedge gains stable across all 3 runs. No anti-over-fire
trap regressed in ANY run. **The gate (targets flip, protected buckets hold) passes.**

## 1.33e — Pre-promotion scoping (cost challenge) → found a real FAN-OUT BUG, not a retrieval cap
Stopped the full-199 A/B mid-run on a cost/ROI challenge and instead scoped *why* ON only beat OFF by ~5, and
which OFF-losses ON actually fixes. Decision (cost + clean attribution): **pivot to the underlying weakness
first, then ONE combined A/B** (fan-out lifts coverage; the weakness caps per-subtask correctness — they
compound, so promoting fan-out *after* is a stronger case). Fan-out stays merged + flag-OFF meanwhile (zero
prod cost).

### Breakdown of the hard set (OFF 57 / ON 62)
- Of OFF's **29 failures, ON fixes 8** — all the structural gap (4 decompose + 3 hedge + 1 underspecified) the
  old flow gets categorically wrong. The 21 ON-still-loses split: **~11 NOT fan-out's job** (single-domain
  corpus / OOS-refusal / cross-lingual / multihop / enum — fan-out correctly didn't engage; old flow fails them
  identically) and **~10 fan-out cases that decomposed but lost on `facts`** — every one ALSO a both_fail in OFF
  (fan-out didn't break them). The small net is because ~⅔ of the 86 are **controls** (54 both-pass traps/single
  + 11 non-addressable) that by design don't differentiate the flows. The set is HARD (adversarial), not easy.

### Root-cause hunt (4 cases: dc-vi-rutmon, cross-late-payment, cross-other-bachelor, dc-3part Fall-start)
1. **Raw retriever**: the gold fact is RETRIEVED, usually at rank 0 (e.g. "21-Sep Fall'26 Instruction Begins"
   score 1.28; "late payment fee is 2.000.000 VND"; "Refund 80% … within two weeks"). **Not a retrieval/embeddings
   problem — no rabbit hole.**
2. **Actual specialist tool** (full `_search`: structured-first/expansion/x-lingual/rerank): also returns the
   fact for 3/4 (cross-other-bachelor pre-empted to Nursing-only by the structured fee lookup).
3. **Specialist STANDALONE** on the subtask: answers 3/4 CORRECTLY (Sep 21 / 2.000.000 / 815,850,000) — only
   `dc-vi-rutmon` is systematically wrong (50% vs 80%, a tiered-table grounding error). So the specialists CAN
   answer; fan-out was failing them.
4. **DECISIVE test** — run the specialist on the subtask but with `get_user_message()` set to the COMPOUND
   (as in fan-out): it now PUNTS (dc-3part, cross-late-payment) ↔ correct when the contextvar = subtask.

**ROOT CAUSE = a contextvar leak.** `vinuni_agent.py:65` pins `set_user_message(request.message)` to the whole
compound for the turn; the tools key structured-lookup / list-mode / cross-lingual off `get_user_message()`, so
EVERY fan-out subtask ran its deterministic lookup against the wrong (compound) text → miss → punt. A
fan-out bug, NOT retrieval quality. The "+5" was suppressed by it.

### Fix
`graph.py` `_run_subtask` + `_rerun_subtask`: `set_user_message(sub["query"])` so each subtask's tools key off
ITS subtask (asyncio.gather gives each subtask an isolated context copy → concurrent sets don't clash). +1
regression-guard unit test (subtask contextvar isolation). Suite **394 green**.

### End-to-end validation (service, ENABLE_FAN_OUT=true)
- `dc-3part-late-fee`: now ALL 3 facts (2,000,000 + Sep 21 + Oct 9) — **regression recovered**.
- `cross-late-payment`: now BOTH facts (2,000,000 + first two weeks) — **both_fail → gain**.
- `cross-other-bachelor`: still misses the tuition — residual = structured fee lookup mismatches "non-Nursing
  Bachelor" (the fee table lists it as "Other Bachelor Programs"/"All majors"); pre-empts before vector. SMALL.

### Residual mini-pivot
- **structured fee-lookup negation (FIXED).** `_classify` substring-matched "nursing" inside "**non-**nursing",
  so "non-Nursing Bachelor" early-returned the Nursing row and pre-empted vector. Added `_negated_programs` —
  a program named only to be EXCLUDED ("non-nursing", "không phải điều dưỡng", "other than …") is dropped, so
  the lookup MISSES → vector retrieval (which carries the full tuition table) answers. +regression test; 31
  structured tests pass; non-negated Nursing/Medicine still resolve. `cross-other-bachelor` now passes
  end-to-end (815,850,000 + Sep 21). Shared change → lifts the single flow too.
- **tiered-table grounding (DEFERRED, generation-side).** refund 80% vs 50% (dc-vi-rutmon): the right tier IS in
  the rank-0 chunk; the LLM picks the wrong row. A structured-refund lookup is disproportionate for 1 case; it
  joins the documented generation-disambiguation tail (nursing-vi 86-vs-126, pol-thesis-days), shared with the
  single flow.

### Verified end-to-end (service, ENABLE_FAN_OUT=true, both fixes): all 3 prior fan-out failures now pass —
`dc-3part-late-fee` (3/3 facts), `cross-late-payment` (2/2), `cross-other-bachelor` (2/2). Suite **395 green**.

### Hard-set re-measure v4 (ALL fixes: contextvar + fee-negation + deferral + qualifier + L2)
**ON 62/86 (0.721) vs OFF 0.663** — 9 gains (incl. the 3 verified recoveries cross-late-payment /
cross-other-bachelor / dc-3part), **0 REAL regressions**: the 4 "regressions" are 2 golden-spec (weather
`forecast`, thuvien `expected_source`) + 2 artifacts (`dc-transcript` answer correct but golden wants "working"
not "business" days; `hedge-merit-eligibility` noise — its twin `hedge-merit-renewal` passes same content).
Latency mean **14.9s** (down from 16.0s v3 — the contextvar fix lets subtasks succeed instead of punt+retry).
The flat +5 aggregate is single-run noise (--runs 1) masking real progress; the deterministic signal (targeted
recoveries landed, latency down, no real regressions, byte-identical single path) is unambiguously positive.

## 1.33f — Full-199 A/B caught a real OVER-FIRE; fixed deterministically (same-intent collapse)
Fresh OFF-199 vs ON-199, all fixes, cache-off, --runs 1 (user chose the rigorous head-to-head).
- **OFF 193/199 (0.970) vs ON 188/199 (0.945) — ON DOWN 5. Net-negative on the scored set.** 0 GAINED, 5
  REGRESSED. Fan-out RATE **27/199 (13.6%)** (realistic; 21/27 of the fanned-out cases passed). cw 3→4.
  Latency mean 9.5s→10.8s; fanned-out subset mean 18.5s. **The scored 199 has ~no genuine cross-domain
  compounds — so fan-out had nothing to GAIN there, but over-fired on some and lost.**
- **Regression decode**: 1 single-path noise (`d9-rectors-enumerate`, fanout=False, enumeration answer-gen
  variance) + **4 SAME-SPECIALIST OVER-FIRES** (all `fanout=True`, planner probe confirmed all-same-intent):
  `exp-program-datascience-vi` (services+services), `ltp-credittransfer` (policy+policy), `pol-finaid-deadline`
  (calendar+calendar), `pol-sexual-misconduct` (policy+policy). Splitting a one-specialist question HURTS —
  narrow subtasks lose coverage, break the citation, or punt; the single path answers all facets from the
  whole-question context. (The prompt's SAME-SPECIALIST rule wasn't enough — gpt-4o-mini still split them.)
- **Fix — deterministic same-intent collapse** (`plan_dispatch`): if a multi-assignment plan's parts ALL share
  one intent → collapse to a SINGLE whole-question assignment (the byte-identical single path). Genuine
  DECOMPOSE/HEDGE always span ≥2 DISTINCT intents → untouched. +2 unit tests; 21 fan-out tests pass. Verified
  live: all 4 over-fires now collapse to n=1; the cross-domain gain (financial+calendar) still fans out.
  Expected post-fix: the 4 over-fires → single → pass (OFF passed them) ⇒ ON ≈ OFF (no regression), fan-out
  rate DROPS (lower cost), hard-set gains preserved.
- **CONFIRMED cheaply** (the 5 regressed cases only, ~10 turns vs 398): OFF 5/5, **ON 5/5** — all 4 over-fires
  now run with `fanout=False` (collapse fired → single path) and pass; `d9-rectors` passes on re-run (it was
  answer-gen noise, never a fan-out regression). The scored-set regression is resolved; ON ≈ OFF.

### Honest verdict (the decisive finding)
Fan-out's value is **multi-domain coverage**, which lives in the authored hard set — **the scored 199 has no
genuine compounds**, so post-fix fan-out is **NEUTRAL there (no regression, no gain)**. Promotion is therefore
not justified by the current scored eval; the feature is **kept merged + flag-OFF** (done, tested, all fixes
landed: contextvar, fee-negation, deferral, qualifier, L2, same-intent collapse), instantly enableable if/when
real student traffic is shown to carry multi-domain questions. The fee-negation fix (shared) stays regardless.
golden_targets test fixes (weather, thuvien) deferred — only relevant if promoting.

## 1.33g — PROMOTED (default ON)
User decision (2026-06-26): **promote fan-out — `ENABLE_FAN_OUT` default ON** (config + `.env`/`.env.example`),
docs updated to "the live flow". Rationale: post over-fire-fix it is **neutral on the single-domain scored set
(no regression)** and adds the **multi-domain coverage the single router structurally can't** (the hard-set
gain); fully reversible via the flag (single-assignment plans defer to `route_intent`, byte-identical). Cost:
the realistic fan-out rate is ~10–14% of turns, each paying ~+latency for parallel specialists + a synthesis
join.
- **Also shipped (reliability, root-caused this session): chat-client request timeout + retries**
  (`LLM_REQUEST_TIMEOUT_S`=60, `LLM_MAX_RETRIES`=2). The full-199 ON eval hung for 80+ min twice — diagnosed via
  CPU watch (35s CPU / 82 min = blocked on a network call). Root cause: `build_chat_model` set NO timeout, so a
  stalled OpenRouter call rode the SDK's 600s default (×retries) and, in a fan-out turn, blocked the whole
  `asyncio.gather`. The fix bounds every call (~180s worst case) — unblocks long eval runs AND removes a real
  prod risk (a stalled upstream freezing a user's turn). Suite 397 green.
- Empirical full-199 ON confirmation was repeatedly blocked by the API stalls; the no-regression call rests on
  the deterministic same-intent collapse + the 5-regressed-case re-run (5/5, all `fanout=False`). The
  timeout-hardened ON-199 can be re-run any time for the aggregate number.
