# Phase 1.31 — multi-domain golden + calendar parser data fix

> Baseline progression: 0.969/226 (post-doc-pin) → **0.965/199** (after G7 prune) → **0.98/199** (after build B).
> Guards 1.000 throughout. Master plan: `LOGS/PHASE1.29_PLAN.md` (Phase-1.31 section + consolidated fix-map).

## G7 — golden hygiene + Stage-0.5 multi-domain substrate (DONE)
- **G7a prune:** removed 27 always-pass VI-duplicate cases (12 calendar_pointlookup, 7 financial, 3 fee_list,
  2 conduct, 2 calendar_list, 1 fee_structured) — all passed in 12/12 runs, EN twin kept, no guards/sole-
  feature/ever-failed touched. `baseline.json` refreshed by filter+re-summarize → 0.965/199. ~12% eval compute saved.
- **G7b expansion:** 3 subagents authored 23 verified cross_domain/multihop cases (evidence tables; I
  validated + spot-verified) → 27-case multi-domain substrate (cross_domain 16, multihop 11), tagged
  coverage/multi_question/chained.
- **Stage-0.5 baseline: 22/27.** coverage 9/11, multi_question 3/3, chained 8/9. **G1 (multi-domain
  orchestrator) DEFERRED with evidence:** 3-case ROI; cheap "2+-intent→services" rule regresses 17 passing
  point-lookups (stray keywords); clean LLM-multi-label is a big graph build. Substrate kept for later.

## Build B — calendar keyword-gate fix (PROMOTED ✅)

### Trial
`calendar-victory-day-vi` hedged on a date that IS in the corpus. Root-caused: the structured calendar index
was MISSING Victory Day (`victory`/`30-apr` absent; `hung king` present).

### Experiment
- **Bug (not the initial glued-date hypothesis):** the authoritative calendar PDF lists holidays one-per-line
  (`"30-Apr Victory Day"`), but `_CALENDAR_EVENT_KEYWORDS` in `parsers.py` had no `victory`/`labor`/`culture`/
  `independent study` → the keyword gate dropped 5 real events (Victory Day, Labor Day, Vietnam Culture Day,
  Independent Study Week ×2) from the structured index; the `Version:` line correctly stayed dropped.
- **Fix:** added EN (`victory`, `labor`, `labour`, `culture`, `independent study`, `study week`) + VN
  (`giải phóng`, `lao động`, `văn hóa`) keywords. General — recovers all dropped holidays. +2 regression tests
  in `test_calendar_parser_hardening.py` (holidays captured; `Version:` still excluded). 375 tests, ruff clean.
- **Regen (surgical, NO Qdrant re-embed):** full `ingest_documents.py` always re-embeds, so instead re-parsed
  only the current calendar via `structured_records_from_raw` (fixed extractor) → rebuilt the calendar portion
  of `structured_index.json`. **Additions-only: +5 events, 0 existing lost (116→121).** Structured lookup now
  returns Victory Day = "30 tháng 4 năm 2027" (VI+EN), Vietnam Culture Day = "24 tháng 11 năm 2026".

### Result — PROMOTED
Scored A/B (cache-off, 199 cases): **0.965 → 0.98**, facts 0.97→0.985, **LOST 0**, guards 1.000,
confidently_wrong 3→2, 0 empties, `calendar_pointlookup` 0.889→1.0. GAINED 3: `calendar-victory-day-vi`
(the deterministic fix), `calendar-fall-grade-release-en` + `pol-thesis-days-vi` (both diagnosed flaky/noise,
landed PASS this clean run — may vary). `baseline.json` refreshed to **0.98/199**.
- **Durable gain = victory-day-vi** (structured lookup, deterministic, language-agnostic). The other 2 gains
  are run-to-run noise (not caused by this fix). True durable baseline ≈ 0.975; recorded 0.98 as the snapshot.
- Code fix (keywords) is the durable change; on the next full ingest the structured index rebuilds with all
  holidays (incl. the 3 older calendars not regenerated here — historical, untested, low priority).

### Residual tail (unchanged, deferred — see PHASE1.29_PLAN residual-tail diagnosis)
Generation-side number-disambiguation (`nursing-vi` 86-vs-126; `pol-thesis-days` 3mo-vs-15/30d when it
flakes), `calendar-source-inconsistency` (hard metacognition probe), citation-only (`pol-courseeval-vi`).
System at a mature plateau (0.98/199, guards 1.000).
