# Phase 1.27 / A6 — Multi-domain & list mode

> Plan: `.claude/plans/can-we-try-to-merry-mango.md`. Built as 3 flag-gated, eval-gated sub-parts
> (a fees → b calendar → c cross-domain). Baseline before: **0.964/182**, guards 1.000.

## 1.27a — Multi-ROW list mode (general detector + deterministic fee matrix)  — PROMOTED

### Trial
Multi-row questions ("per-credit tuition for ALL programs") fail: the 8-chunk cap + point-lookup narrowing
("answer ONLY the exact value") suppress enumeration. Investigation found **fees are retrieval-solvable** —
the full tuition matrix is one chunk / already in `_fee_matrix`. Fix = detect list intent → widen + enumerate,
and return the matrix deterministically.

### Experiment
- **`query_engineering.is_list_lookup`** — mirror of `is_point_lookup`; list-specific markers
  (`all/each/every/both/list/compare/across`, VI `tất cả/liệt kê/so sánh/toàn bộ`).
- **`tools._search`** — `list_mode` (gated `enable_list_mode`): widen to `retrieval_list_max_k`(20) +
  `expand_sections`, suppress point-lookup, thread `list_mode` to the structured lookup.
- **`structured_lookup._match_fee(list_mode)`** — deterministic full-matrix return (all programs × the asked
  granularity, or whole table) from `_fee_matrix`; 1×1 falls back to the point path. Also normalized hyphens
  so "per-credit" matches the "per credit" granularity keyword.
- **`POINT_LOOKUP_SUFFIX`** — augmented: "if asked for ALL/each/compare, enumerate EVERY matching row"
  (covers the vector path). NOTE: this prompt clause is **not** behind `enable_list_mode` (static suffix on
  calendar+financial) — ships regardless; financial subset confirms it's neutral on financial point-lookups.
- **Config:** `enable_list_mode` (default off), `retrieval_list_max_k` (20).
- **Golden:** `data/eval/golden/fee_list.json` — 6 cases (per-credit/year/semester × EN+VI), `required_facts`
  = every program's value for that granularity, `forbidden_facts` = the other granularities' values
  (catch wrong-row/partial). + 4 structured unit tests + an `is_list_lookup` truth-table test.

**Run 1 (full n=188, `ENABLE_LIST_MODE` on, N=1, `eval_20260622T175725Z`):** fee_list **6/6 ✓**, but 3 LOST.
Decode: `unans-future-tuition-en` + `pol-progchange-vi` = known soft-case noise (no list markers, untouched
by 1.27a); **`fin-library-overdue-fine-vi` = REAL regression** — `is_list_lookup` over-fired on VI **"mỗi
ngày" (per day)** → list mode → `_match_fee` returned the tuition matrix for a *library-fine* question.
**Fix:** dropped rate-ambiguous VI quantifiers (`mỗi/từng/mọi` — "mỗi ngày"=per day, "mỗi tín chỉ"=per credit
are RATES) from `is_list_lookup`; kept `tất cả/liệt kê/…`; added a regression test. All 6 fee_list still fire
via `tất cả`/`liệt kê`.

**Run 2 (subset: fee_list+financial+fee_structured = 26, list mode on, `eval_20260622T180627Z`):** **26/26 =
1.0** — fee_list **6/6**, financial **16/16** (`fin-library-overdue-fine-vi` RECOVERED), fee_structured **4/4**,
LOST/GAINED none. Over-fire fix confirmed.

### Progress
- **PROMOTED** — `.env` `ENABLE_LIST_MODE=true`, `RETRIEVAL_LIST_MAX_K=20` (+ `.env.example`). 351 offline green,
  ruff clean. No git commit.
- **Baseline REFRESHED → 0.968/188** (`eval_20260623T023726Z`, N=1, list-mode on): **0.964→0.968 (+1/−0,
  new=6)**, fee_list 6/6, financial/fee_structured 1.0, **guards 1.000**, **calendar neutral** (0.929 flat,
  calendar_pointlookup 0.944→0.967 via the noisy `calendar-fall-grade-release-en`, calendar_structured 1.0) →
  the un-gated POINT_LOOKUP_SUFFIX change is **confirmed neutral on calendar**. **LOST: none.** `baseline.json`
  updated. (N=1 per the cost steer — soft cases carry noise; re-denoise via `--runs 3` if wanted.)
- Next: 1.27b (calendar list aggregation), then 1.27c (cross-domain fan-out).

## 1.27b — Calendar list aggregation — SHIPPED (same `ENABLE_LIST_MODE` flag)

### Trial
Calendar events are chunked one-per-event (scattered), so "all X deadlines for the year" needs aggregation —
but the structured calendar index already holds every event in memory. Return ALL matching on a list query.

### Experiment
- **`structured_lookup._match_calendar(list_mode)`** — on list intent, after the event-type/concept filter,
  skip the single-term narrowing, apply only an optional month filter, and return the **sorted list** of all
  matching events (`list[_CalEntry]`). **`_format_calendar_list`** renders multi-row bilingual text;
  `lookup()` handles the list return. Deterministic (no vector aggregation). Point path unchanged.
- **Tests:** 3 structured calendar-list unit tests (all grade-release → 3 terms; all add/transfer → both;
  gated-off → MISS). 354 offline green, ruff clean.
- **Golden:** `data/eval/golden/calendar_list.json` — 4 cases (add/transfer + course-drop deadlines, EN+VI),
  REAL AY2026-27 dates (verification-backed via the live lookup), `required_facts` = both of the year's
  deadlines of that type, `forbidden_facts` = the OTHER type's dates (catch wrong-type/partial).
- **Gate (calendar subset, list mode on, `eval_20260623T025149Z`):** **calendar_list 4/4**, calendar 0.929
  (flat), calendar_pointlookup 0.933, calendar_structured 4/4. The 1 LOST (`calendar-fall-grade-release-en`)
  is the **known noisy flake** (no list markers → untouched by 1.27b; flips pass↔fail every run; was GAINED in
  the n=188 baseline). **No real regression; no `is_list_lookup` over-fire on calendar point-lookups.**

### Progress
- **SHIPPED** (no new flag — rides `ENABLE_LIST_MODE`). 354 green. **Baseline refresh to n=192 deferred** per
  the cost steer (the calendar subset + the n=188 full run cover validation; the 4 new cases pass
  deterministically). No git commit.

## Input-understanding work — DEFERRED (user decision 2026-06-23)
- **Multi-question decomposition (Q1) — DEFERRED, not recommended.** The ReAct loop already handles
  multi-part questions adequately: `BASE_PRINCIPLES` step 2 instructs "if results aren't enough to answer
  FULLY (empty / only PARTIAL / missing the asked fact), call the tool AGAIN" — a completeness/partial-coverage
  nudge + the loop can make multiple tool calls. Explicit decompose→answer-each→merge machinery is judged
  redundant. Revisit only if eval evidence (multi-question golden cases) shows the ReAct path under-serves.
- **Vague-path / clarification (Q2) — DEFERRED to the teammate merge.** The "ask ONE clarifying question when
  scope is missing" path (1.26/A5 Part 3) is deferred until the Phase-2/3 team merge (it pairs naturally with
  personalization + the front-end conversational UX). Design saved in `PHASE1.26_PLAN.md`.
- **1.27c cross-domain fan-out — under review** (see below): distinct from Q1 (ReAct can't search *another
  domain's* tools under single-intent routing), but low measured value (no cross-domain golden) → likely defer.